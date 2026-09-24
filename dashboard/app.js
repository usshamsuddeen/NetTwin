"use strict";
/* ============================================================
   NetTwin 3.0 — World-Class Dashboard Engine
   Interactive topology, live attacks, conformal prediction,
   autonomous response, and instant visual feedback.
   ============================================================ */

const VW = 1280, VH = 760;
const API_BASE = (location.protocol === "file:" || !location.host) ? "http://127.0.0.1:8000" : "";
const WS_BASE = (location.protocol === "file:" || !location.host) ? "ws://127.0.0.1:8000/ws" : `ws://${location.host}/ws`;

const state = {
  nodes: {}, links: {}, nodeList: [], linkList: [],
  latest: null, anomalies: {}, attacks: [], alerts: [],
  forecast: null, selected: null, whatifHighlight: new Set(),
  netSeries: { tp: [], lat: [], loss: [], anom: [] },
  tickMs: 1000, alertThreshold: 0.72,
  paused: false, speedMultiplier: 1.0,
  syncEntities: {}, research: null, risk: null, response: null,
  selectedAlert: null, riskOverlay: false, syncDetailEntity: null,
  view: { scale: 1, dx: 0, dy: 0 },
  chartHover: { canvasId: null, idx: -1, x: -1, y: -1, visible: false },
};

/* ---- Color Palette ---- */
const C = {
  cyan: "#06b6d4", cyanLight: "#22d3ee", cyanGlow: "rgba(6,182,212,0.35)",
  blue: "#3b82f6", blueGlow: "rgba(59,130,246,0.3)",
  emerald: "#10b981", emeraldLight: "#34d399", emeraldGlow: "rgba(16,185,129,0.35)",
  amber: "#f59e0b", amberLight: "#fbbf24", amberGlow: "rgba(245,158,11,0.35)",
  rose: "#f43f5e", roseLight: "#fb7185", roseGlow: "rgba(244,63,94,0.35)",
  violet: "#a78bfa", violetGlow: "rgba(167,139,250,0.35)",
  textPri: "#e8edf5", textSec: "#8b9ec0", textMuted: "#556b8c",
  bg1: "#0a1020", bg2: "#0d1526", bg3: "#111d33", bg4: "#162540",
  borderSub: "rgba(255,255,255,0.05)", borderDef: "rgba(255,255,255,0.08)",
};

/* ============================================================
   TOAST NOTIFICATION SYSTEM
   ============================================================ */
function showToast(title, message, type = "info", duration = 3500) {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const t = document.createElement("div");
  t.className = `toast ${type}`;
  const icon = type === "success" ? "✓" : type === "danger" ? "✕" : type === "warning" ? "⚠" : "ℹ";
  t.innerHTML = `<span class="toast-icon">${icon}</span><div class="toast-body"><div class="toast-title">${escapeHtml(title)}</div><div>${escapeHtml(message)}</div></div>`;
  container.appendChild(t);
  setTimeout(() => {
    t.classList.add("toast-out");
    setTimeout(() => t.remove(), 320);
  }, duration);
}

/* ============================================================
   ACTIVE CAMPAIGN BANNER & BUTTON HIGHLIGHTS
   ============================================================ */
function updateActiveCampaigns(attacks) {
  state.attacks = attacks || [];
  const banner = document.getElementById("active-campaign-banner");
  const bannerTitle = document.getElementById("active-campaign-title");
  const bannerDesc = document.getElementById("active-campaign-desc");
  const btns = document.querySelectorAll(".atk-btn");

  btns.forEach(b => b.classList.remove("active-running"));

  const activeList = (state.attacks || []).filter(a => a.active);
  if (activeList.length > 0) {
    const atk = activeList[0];
    const kind = atk.attack_type || atk.type || "attack";
    const target = atk.target_id || "broadcast";
    const dur = atk.duration_s ? `${atk.duration_s}s` : "continuous";

    if (bannerTitle) bannerTitle.textContent = `ACTIVE ATTACK: ${kind.toUpperCase()}`;
    if (bannerDesc) bannerDesc.textContent = `Target: ${target} | Duration: ${dur} | Started at t=${atk.start_tick}`;
    if (banner) banner.classList.remove("hidden");

    btns.forEach(b => {
      if (b.dataset.atk === kind) b.classList.add("active-running");
    });
  } else {
    if (banner) banner.classList.add("hidden");
  }
}

/* ============================================================
   WEBSOCKET WITH AUTO-RECONNECT
   ============================================================ */
let ws = null, backoff = 500;
function connect() {
  try {
    ws = new WebSocket(WS_BASE);
    ws.onopen = () => {
      backoff = 500;
      setConn(true);
      showToast("System Connected", "Real-time twin telemetry feed active.", "success", 2500);
    };
    ws.onclose = () => {
      setConn(false);
      setTimeout(connect, backoff);
      backoff = Math.min(backoff * 2, 8000);
    };
    ws.onerror = () => {
      try { ws.close(); } catch(e) {}
    };
    ws.onmessage = (ev) => handleMessage(JSON.parse(ev.data));
  } catch (err) {
    console.warn("WebSocket init error:", err);
    setTimeout(connect, 3000);
  }
}
function setConn(up) {
  const dot = document.getElementById("conn-dot");
  const lbl = document.getElementById("conn-label");
  if (dot) dot.className = "dot " + (up ? "up" : "down");
  if (lbl) lbl.textContent = up ? "live" : "reconnecting";
}

function handleMessage(msg) {
  if (msg.type === "snapshot") {
    state.topologyName = (msg.topology && msg.topology.name) || "default";
    state.topologyTitle = (msg.topology && msg.topology.title) || "Enterprise Network";
    state.tiers = (msg.topology && msg.topology.tiers) || [];
    state.nodeList = msg.topology.nodes;
    state.linkList = msg.topology.links;
    state.nodes = Object.fromEntries(msg.topology.nodes.map(n => [n.id, n]));
    state.links = Object.fromEntries(msg.topology.links.map(l => [l.id, l]));
    state.alerts = msg.alerts || [];
    state.attacks = msg.attacks || [];
    state.tickMs = msg.config.tick_ms;
    state.alertThreshold = msg.config.alert_threshold;
    const rateEl = document.getElementById("tick-rate");
    if (rateEl) rateEl.textContent = (msg.config.tick_ms / 1000).toFixed(2) + "s";
    if (msg.sync) { for (const e of msg.sync) state.syncEntities[e.entity_id] = e; renderSyncList(); }
    if (msg.response) { state.response = msg.response; renderResponsePanel(); }
    
    // Sync topology dropdown and tier strip visibility
    const topoSelect = document.getElementById("topology-select");
    if (topoSelect) {
      topoSelect.value = state.topologyName === "aws-3tier" ? "aws-3tier" : "default";
    }
    const tierStrip = document.getElementById("tier-health-strip");
    if (tierStrip) {
      tierStrip.style.display = (state.topologyName === "aws-3tier" || state.tiers.length > 0) ? "flex" : "none";
    }

    if (msg.organization) updateOrgTopbar(msg.organization);
    buildTargetSelects();
    renderAlerts();
    initParticles();
    updateActiveCampaigns(state.attacks);
  } else if (msg.type === "telemetry") {
    state.latest = msg;
    if (msg.organization) updateOrgTopbar(msg.organization);
    state.anomalies = msg.anomalies || {};
    state.attacks = msg.attacks || [];
    if (msg.sync) {
      for (const [eid, e] of Object.entries(msg.sync)) {
        state.syncEntities[eid] = { ...(state.syncEntities[eid] || {}), entity_id: eid, ...e };
      }
      renderSyncList();
    }
    pushSeries(msg.kpis);
    updateHeader(msg);
    updateActiveCampaigns(state.attacks);
    if (state.selected) updateInspectorLive();
  } else if (msg.type === "org_connected") {
    if (msg.organization) updateOrgTopbar(msg.organization);
  } else if (msg.type === "alerts") {
    state.alerts = msg.alerts || [];
    renderAlerts();
  } else if (msg.type === "attack_events") {
    state.attacks = msg.attacks || [];
    updateActiveCampaigns(state.attacks);
  } else if (msg.type === "forecast") {
    state.forecast = msg.forecast;
  } else if (msg.type === "research") {
    state.research = msg.research;
    renderResearchStrip();
  } else if (msg.type === "risk") {
    state.risk = msg.risk;
    renderRiskPaths();
  } else if (msg.type === "response") {
    state.response = msg.response;
    renderResponsePanel();
  }
}

function pushSeries(k) {
  if (!k) return;
  const s = state.netSeries;
  s.tp.push(k.total_throughput_mbps);
  s.lat.push(k.avg_latency_ms);
  s.loss.push(k.avg_loss_pct);
  const anomVals = Object.values(state.anomalies);
  s.anom.push(anomVals.length ? Math.max(...anomVals) : 0);
  for (const key of ["tp", "lat", "loss", "anom"]) {
    if (s[key].length > 300) s[key].shift();
  }
}

/* ============================================================
   HEADER / GAUGE
   ============================================================ */
function updateHeader(msg) {
  animateNumber("tick-count", msg.tick);
  const hh = Math.floor(msg.hour), mm = Math.floor((msg.hour - hh) * 60);
  const clockEl = document.getElementById("sim-clock");
  if (clockEl) {
    clockEl.textContent = String(hh).padStart(2, "0") + ":" + String(mm).padStart(2, "0");
  }
  const h = msg.health.net;
  animateNumber("health-val", Math.round(h));
  drawGauge(h);

  // Cloud KPI and Tier Health Strip Updates
  updateCloudMetrics(msg);
  updateTierHealthStrip(msg.health);
}

function updateCloudMetrics(msg) {
  const isCloud = state.topologyName === "aws-3tier" || !!state.nodes["alb"];
  const albStat = document.getElementById("cloud-alb-stat");
  const errStat = document.getElementById("cloud-err-stat");
  const rdsStat = document.getElementById("cloud-rds-stat");

  if (albStat) albStat.style.display = isCloud ? "flex" : "none";
  if (errStat) errStat.style.display = isCloud ? "flex" : "none";
  if (rdsStat) rdsStat.style.display = isCloud ? "flex" : "none";

  if (isCloud && msg.nodes) {
    const albM = msg.nodes["alb"] || { tp: 0, pps: 0, loss: 0 };
    const albAnom = (state.anomalies && state.anomalies["alb"]) || 0;
    const dbM = msg.nodes["db1"] || { tp: 0, cpu: 0 };

    // ALB Request Rate (e.g. "1.2k req/s")
    const reqs = albM.pps > 0 ? Math.round(albM.pps) : Math.round((albM.tp || 1.2) * 280);
    const reqsStr = reqs >= 1000 ? (reqs / 1000).toFixed(1) + "k req/s" : reqs + " req/s";
    const albReqsEl = document.getElementById("alb-reqs");
    if (albReqsEl) albReqsEl.textContent = reqsStr;

    // HTTP 500 error percentage: scaled with loss and anomaly
    const errPct = Math.min(99.9, Math.max(0.0, (albM.loss * 4.2) + (albAnom * 35.0)));
    const errEl = document.getElementById("alb-500s");
    if (errEl) {
      errEl.textContent = errPct.toFixed(1) + "%";
      errEl.className = errPct > 5.0 ? "kpi-danger" : errPct > 1.0 ? "kpi-amber" : "kpi-green";
    }

    // RDS active connections
    const rdsConns = Math.round(45 + (dbM.cpu * 0.8) + (dbM.tp * 1.5));
    const rdsEl = document.getElementById("rds-conns");
    if (rdsEl) rdsEl.textContent = String(rdsConns);
  }
}

function updateTierHealthStrip(health) {
  const strip = document.getElementById("tier-health-strip");
  if (!strip) return;
  const isCloud = state.topologyName === "aws-3tier" || !!state.nodes["alb"];
  strip.style.display = isCloud ? "flex" : "none";
  if (!isCloud || !health || !health.nodes) return;

  const nodeH = health.nodes;
  const avg = (ids) => {
    const vals = ids.map(id => nodeH[id]).filter(v => v !== undefined);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 100.0;
  };

  const tiers = [
    { id: "ingress", name: "Public Ingress", h: avg(["igw", "waf", "alb"]) },
    { id: "web", name: "Web Tier (ASG)", h: avg(["web1", "web2"]) },
    { id: "app", name: "App Tier (ECS)", h: avg(["app1", "app2"]) },
    { id: "db", name: "Database Tier (RDS)", h: avg(["db1"]) },
    { id: "storage", name: "Storage (S3)", h: avg(["s3"]) },
  ];

  for (const t of tiers) {
    const dot = document.getElementById(`dot-${t.id}`);
    const metric = document.getElementById(`tier-metric-${t.id}`);
    const status = t.h >= 80 ? "HEALTHY" : t.h >= 50 ? "DEGRADED" : "CRITICAL";
    const dotClass = t.h >= 80 ? "healthy" : t.h >= 50 ? "degraded" : "critical";
    if (dot) dot.className = `tier-dot ${dotClass}`;
    if (metric) {
      metric.textContent = `${status} (${Math.round(t.h)})`;
      metric.style.color = t.h >= 80 ? C.emeraldLight : t.h >= 50 ? C.amberLight : C.roseLight;
    }
  }
}

function animateNumber(elId, newVal) {
  const el = document.getElementById(elId);
  if (!el) return;
  const cur = parseInt(el.textContent) || 0;
  if (cur === newVal) return;
  el.textContent = newVal;
  el.style.transition = "none";
  el.style.color = newVal > cur ? C.emeraldLight : newVal < cur ? C.roseLight : "";
  requestAnimationFrame(() => {
    el.style.transition = "color 600ms ease";
    setTimeout(() => { el.style.color = ""; }, 600);
  });
}

function drawGauge(val) {
  const c = document.getElementById("health-gauge");
  if (!c) return;
  const ctx = c.getContext("2d");
  const w = c.width, h = c.height, cx = w / 2, cy = h - 6, r = 48;
  ctx.clearRect(0, 0, w, h);

  // Background arc
  ctx.lineWidth = 10;
  ctx.lineCap = "round";
  ctx.strokeStyle = C.bg3;
  ctx.beginPath(); ctx.arc(cx, cy, r, Math.PI, 2 * Math.PI); ctx.stroke();

  // Value arc with gradient
  const frac = Math.max(0, Math.min(1, val / 100));
  const grad = ctx.createLinearGradient(cx - r, cy, cx + r, cy);
  if (val > 80) {
    grad.addColorStop(0, C.emerald); grad.addColorStop(1, C.emeraldLight);
  } else if (val > 55) {
    grad.addColorStop(0, C.amber); grad.addColorStop(1, C.amberLight);
  } else {
    grad.addColorStop(0, C.rose); grad.addColorStop(1, C.roseLight);
  }
  ctx.strokeStyle = grad;
  ctx.shadowColor = val > 80 ? C.emeraldGlow : val > 55 ? C.amberGlow : C.roseGlow;
  ctx.shadowBlur = 12;
  ctx.beginPath();
  ctx.arc(cx, cy, r, Math.PI, Math.PI + frac * Math.PI);
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Tick marks
  ctx.lineWidth = 1;
  for (let i = 0; i <= 10; i++) {
    const a = Math.PI + (i / 10) * Math.PI;
    const len = i % 5 === 0 ? 8 : 4;
    ctx.strokeStyle = C.textMuted;
    ctx.beginPath();
    ctx.moveTo(cx + (r - len) * Math.cos(a), cy + (r - len) * Math.sin(a));
    ctx.lineTo(cx + (r + 2) * Math.cos(a), cy + (r + 2) * Math.sin(a));
    ctx.stroke();
  }

  const col = val > 80 ? C.emerald : val > 55 ? C.amber : C.rose;
  const hv = document.getElementById("health-val");
  if (hv) hv.style.color = col;
}

/* ============================================================
   TOPOLOGY CANVAS — Particles, Halos & Dynamic Attacks
   ============================================================ */
const topoCanvas = document.getElementById("topology");
const tctx = topoCanvas ? topoCanvas.getContext("2d") : null;
let dashOffset = 0, pulseT = 0;

let particles = [];
const MAX_PARTICLES = 120;

function initParticles() {
  particles = [];
  if (!state.linkList.length) return;
  for (let i = 0; i < MAX_PARTICLES && i < state.linkList.length * 4; i++) {
    const link = state.linkList[i % state.linkList.length];
    particles.push({
      linkId: link.id, src: link.src, dst: link.dst,
      t: Math.random(), speed: 0.004 + Math.random() * 0.006,
      size: 1.5 + Math.random() * 1.5, opacity: 0.4 + Math.random() * 0.4,
    });
  }
}

function updateParticles() {
  if (state.paused) return;
  const mult = state.speedMultiplier || 1.0;
  for (const p of particles) {
    const link = state.links[p.linkId];
    if (!link) continue;
    const m = state.latest && state.latest.links[p.linkId];
    const util = m ? m.util : 10;
    p.speed = (0.003 + (util / 100) * 0.015) * mult;
    p.t += p.speed;
    if (p.t > 1) {
      p.t = 0;
      if (Math.random() < 0.3) { const tmp = p.src; p.src = p.dst; p.dst = tmp; }
    }
  }
}

function topoTransform() {
  const rect = topoCanvas.getBoundingClientRect();
  const dpr = window.devicePixelRatio || 1;
  if (topoCanvas.width !== rect.width * dpr || topoCanvas.height !== rect.height * dpr) {
    topoCanvas.width = rect.width * dpr;
    topoCanvas.height = rect.height * dpr;
  }
  const sx = topoCanvas.width / VW, sy = topoCanvas.height / VH;
  const baseS = Math.min(sx, sy);
  const s = baseS * state.view.scale;
  const ox = (topoCanvas.width - VW * s) / 2 + state.view.dx * dpr;
  const oy = (topoCanvas.height - VH * s) / 2 + state.view.dy * dpr;
  return { s, ox, oy, baseS, dpr };
}
function toScreen(t, x, y) { return [t.ox + x * t.s, t.oy + y * t.s]; }
function toVirtual(t, x, y) { return [(x - t.ox) / t.s, (y - t.oy) / t.s]; }

function healthColor(h) {
  if (h > 80) return C.emerald;
  if (h > 55) return C.amber;
  return C.rose;
}
function healthGlow(h) {
  if (h > 80) return C.emeraldGlow;
  if (h > 55) return C.amberGlow;
  return C.roseGlow;
}
function utilColor(u) {
  if (u < 50) return C.emerald;
  if (u < 85) return C.amber;
  return C.rose;
}

function drawNodeShape(ctx, kind, x, y, r) {
  ctx.beginPath();
  switch (kind) {
    case "core_router":
      ctx.moveTo(x, y - r); ctx.lineTo(x + r, y); ctx.lineTo(x, y + r); ctx.lineTo(x - r, y);
      ctx.closePath(); break;
    case "distribution_switch":
    case "edge_switch":
      if (ctx.roundRect) ctx.roundRect(x - r, y - r, 2 * r, 2 * r, 3);
      else ctx.rect(x - r, y - r, 2 * r, 2 * r);
      break;
    case "server":
      if (ctx.roundRect) ctx.roundRect(x - r, y - r * 0.8, 2 * r, 1.6 * r, 4);
      else ctx.rect(x - r, y - r * 0.8, 2 * r, 1.6 * r);
      break;
    case "firewall": {
      for (let i = 0; i < 6; i++) {
        const a = Math.PI / 6 + i * Math.PI / 3;
        const px = x + r * Math.cos(a), py = y + r * Math.sin(a);
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      }
      ctx.closePath(); break;
    }
    case "attacker":
      ctx.moveTo(x, y - r); ctx.lineTo(x + r, y + r * 0.8); ctx.lineTo(x - r, y + r * 0.8);
      ctx.closePath(); break;
    case "internet_gateway":
      ctx.arc(x, y, r, 0, 2 * Math.PI);
      ctx.moveTo(x + r * 0.6, y);
      ctx.arc(x, y, r * 0.6, 0, 2 * Math.PI);
      break;
    case "iot":
      ctx.arc(x, y, r * 0.65, 0, 2 * Math.PI); break;
    default:
      ctx.arc(x, y, r, 0, 2 * Math.PI);
  }
}

const NODE_R = { internet_gateway: 22, firewall: 18, core_router: 20, distribution_switch: 15,
  edge_switch: 13, server: 15, workstation: 10, iot: 9, attacker: 16 };

function renderTopology() {
  if (!topoCanvas || !tctx) return;
  const t = topoTransform();
  const ctx = tctx;
  ctx.clearRect(0, 0, topoCanvas.width, topoCanvas.height);
  const tele = state.latest;
  const linkData = tele ? tele.links : {};
  const health = tele ? tele.health : { nodes: {}, links: {} };

  // Draw AWS Tier / Subnet Bounding Enclosures (Windows 11 Mica / Acrylic Style)
  if (state.tiers && state.tiers.length) {
    for (const tier of state.tiers) {
      if (!tier.box) continue;
      const [bx1, by1] = toScreen(t, tier.box.x1, tier.box.y1);
      const [bx2, by2] = toScreen(t, tier.box.x2, tier.box.y2);
      const bw = bx2 - bx1, bh = by2 - by1;
      if (bw <= 0 || bh <= 0) continue;

      ctx.save();
      // Acrylic tint & Fluent dash
      ctx.fillStyle = "rgba(0, 120, 212, 0.035)";
      ctx.strokeStyle = "rgba(96, 205, 255, 0.22)";
      ctx.lineWidth = 1;
      ctx.setLineDash([5, 5]);

      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(bx1, by1, bw, bh, 10);
      else ctx.rect(bx1, by1, bw, bh);
      ctx.fill();
      ctx.stroke();
      ctx.setLineDash([]);

      // Subnet Header Pill
      const pillText = `${tier.name.toUpperCase()} [${tier.cidr}]`;
      const fontSize = Math.max(9, Math.round(9.5 * (t.s / dprSafe())));
      ctx.font = `600 ${fontSize}px 'Cascadia Code', monospace`;
      const tm = ctx.measureText(pillText);
      const pw = tm.width + 16, ph = 18;

      ctx.fillStyle = "rgba(14, 23, 42, 0.88)";
      ctx.strokeStyle = "rgba(96, 205, 255, 0.35)";
      ctx.beginPath();
      if (ctx.roundRect) ctx.roundRect(bx1 + 10, by1 - 9, pw, ph, 4);
      else ctx.rect(bx1 + 10, by1 - 9, pw, ph);
      ctx.fill();
      ctx.stroke();

      ctx.fillStyle = "#60cdff";
      ctx.fillText(pillText, bx1 + 18, by1 + 3);
      ctx.restore();
    }
  }

  // Determine attack links and nodes
  const attackLinks = new Set();
  const attackNodes = new Set();
  for (const atk of state.attacks) {
    if (!atk.active) continue;
    attackNodes.add(atk.target_id);
    if (atk.source_id) attackNodes.add(atk.source_id);
    const path = findPath(atk.source_id, atk.target_id);
    for (let i = 0; i + 1 < path.length; i++) {
      const lid = linkBetween(path[i], path[i + 1]);
      if (lid) attackLinks.add(lid);
    }
  }

  // Draw links
  for (const link of state.linkList) {
    const a = state.nodes[link.src], b = state.nodes[link.dst];
    if (!a || !b) continue;
    const [x1, y1] = toScreen(t, a.x, a.y);
    const [x2, y2] = toScreen(t, b.x, b.y);
    const m = linkData[link.id];
    const util = m ? m.util : 0;
    const underAtk = attackLinks.has(link.id);

    if (underAtk || util > 70) {
      ctx.save();
      ctx.strokeStyle = underAtk ? C.roseGlow : C.amberGlow;
      ctx.lineWidth = 6;
      ctx.globalAlpha = 0.35;
      ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
      ctx.restore();
    }

    const linkCol = underAtk ? C.rose : utilColor(util);
    ctx.strokeStyle = linkCol;
    ctx.lineWidth = underAtk ? 2.5 : 1 + Math.min(2.5, util / 35);
    ctx.globalAlpha = 0.8;
    ctx.setLineDash([6, 8]);
    ctx.lineDashOffset = -dashOffset * (underAtk ? 3 : 1);
    ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
  }

  // Draw particles
  updateParticles();
  for (const p of particles) {
    const srcNode = state.nodes[p.src], dstNode = state.nodes[p.dst];
    if (!srcNode || !dstNode) continue;
    const [x1, y1] = toScreen(t, srcNode.x, srcNode.y);
    const [x2, y2] = toScreen(t, dstNode.x, dstNode.y);
    const px = x1 + (x2 - x1) * p.t;
    const py = y1 + (y2 - y1) * p.t;
    const isAtk = attackLinks.has(p.linkId);
    const m = state.latest && state.latest.links[p.linkId];
    const util = m ? m.util : 10;

    ctx.beginPath();
    ctx.arc(px, py, p.size * Math.max(0.8, t.s / dprSafe()), 0, 2 * Math.PI);
    ctx.fillStyle = isAtk ? C.rose : util > 70 ? C.amber : C.cyan;
    ctx.globalAlpha = p.opacity * (isAtk ? 0.95 : 0.65);
    ctx.shadowColor = isAtk ? C.roseGlow : C.cyanGlow;
    ctx.shadowBlur = isAtk ? 8 : 4;
    ctx.fill();
    ctx.shadowBlur = 0;
    ctx.globalAlpha = 1;
  }

  // Draw nodes
  for (const node of state.nodeList) {
    const [x, y] = toScreen(t, node.x, node.y);
    const r = (NODE_R[node.kind] || 12) * Math.max(0.7, t.s / dprSafe());
    const h = health.nodes ? (health.nodes[node.id] ?? 100) : 100;
    const anom = state.anomalies[node.id] || 0;
    const isUnderAttack = attackNodes.has(node.id);
    let col = node.kind === "attacker" ? C.rose : healthColor(h);

    if (state.riskOverlay && state.risk && state.risk.nodes) {
      const p = state.risk.nodes[node.id] || 0;
      col = p > 0.7 ? C.rose : p > 0.45 ? C.amber : p > 0.25 ? C.blue : C.emerald;
    }

    // Health halo
    if (h < 95 || anom > 0.3) {
      const haloR = r + 8 + (anom > 0.5 ? 4 * Math.sin(pulseT * 5) : 0);
      const haloGrad = ctx.createRadialGradient(x, y, r, x, y, haloR + 6);
      haloGrad.addColorStop(0, anom >= 0.72 ? "rgba(244,63,94,0.3)" : anom >= 0.5 ? "rgba(245,158,11,0.25)" : "rgba(6,182,212,0.12)");
      haloGrad.addColorStop(1, "transparent");
      ctx.fillStyle = haloGrad;
      ctx.beginPath(); ctx.arc(x, y, haloR + 6, 0, 2 * Math.PI); ctx.fill();
    }

    // Attack shake
    let dx = 0, dy = 0;
    if (isUnderAttack && node.kind !== "attacker") {
      dx = Math.sin(pulseT * 20) * 2.5;
      dy = Math.cos(pulseT * 15) * 2;
    }

    // Node body
    ctx.shadowColor = col;
    ctx.shadowBlur = h < 70 ? 16 : anom > 0.5 ? 14 : 6;
    drawNodeShape(ctx, node.kind, x + dx, y + dy, r);
    const nodeGrad = ctx.createRadialGradient(x + dx, y + dy - r * 0.3, 0, x + dx, y + dy, r * 1.2);
    nodeGrad.addColorStop(0, C.bg3);
    nodeGrad.addColorStop(1, C.bg1);
    ctx.fillStyle = nodeGrad;
    ctx.fill();
    ctx.strokeStyle = col;
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Node selection ring
    if (state.selected === node.id) {
      ctx.beginPath(); ctx.arc(x + dx, y + dy, r + 6, 0, 2 * Math.PI);
      ctx.strokeStyle = C.cyan; ctx.lineWidth = 2; ctx.setLineDash([4, 4]);
      ctx.lineDashOffset = -dashOffset * 2; ctx.stroke(); ctx.setLineDash([]);
    }

    // Node label
    ctx.fillStyle = isUnderAttack ? C.roseLight : state.selected === node.id ? "#fff" : C.textPri;
    ctx.font = `600 ${Math.max(10, Math.round(11 * t.s / dprSafe()))}px 'Inter', sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText(node.label || node.id, x + dx, y + dy + r + 13);
  }
}

function dprSafe() { return window.devicePixelRatio || 1; }

function findPath(src, dst) {
  if (!src || !dst) return [];
  const prev = { [src]: null };
  const q = [src];
  while (q.length) {
    const cur = q.shift();
    if (cur === dst) break;
    for (const link of state.linkList) {
      let nxt = null;
      if (link.src === cur) nxt = link.dst;
      else if (link.dst === cur) nxt = link.src;
      if (nxt && !(nxt in prev)) { prev[nxt] = cur; q.push(nxt); }
    }
  }
  if (!(dst in prev)) return [];
  const path = [dst];
  while (path[path.length - 1] !== src) path.push(prev[path[path.length - 1]]);
  return path.reverse();
}
function linkBetween(a, b) {
  for (const link of state.linkList) {
    if ((link.src === a && link.dst === b) || (link.src === b && link.dst === a)) return link.id;
  }
  return null;
}

/* ============================================================
   CANVAS INTERACTION: Hover, Tooltip & Entity Selection
   ============================================================ */
let hoverEntity = null;
if (topoCanvas) {
  topoCanvas.addEventListener("mousemove", (ev) => {
    const rect = topoCanvas.getBoundingClientRect();
    const t = topoTransform();
    const dpr = window.devicePixelRatio || 1;
    const [vx, vy] = toVirtual(t, (ev.clientX - rect.left) * dpr, (ev.clientY - rect.top) * dpr);

    let found = null, best = 32;
    for (const node of state.nodeList) {
      const d = Math.hypot(node.x - vx, node.y - vy);
      if (d < best) { best = d; found = node.id; }
    }

    // If no node near, check links
    if (!found) {
      let bestLinkDist = 14;
      for (const link of state.linkList) {
        const a = state.nodes[link.src], b = state.nodes[link.dst];
        if (!a || !b) continue;
        const l2 = (b.x - a.x) ** 2 + (b.y - a.y) ** 2;
        let dist = 999;
        if (l2 === 0) dist = Math.hypot(vx - a.x, vy - a.y);
        else {
          let u = ((vx - a.x) * (b.x - a.x) + (vy - a.y) * (b.y - a.y)) / l2;
          u = Math.max(0, Math.min(1, u));
          const px = a.x + u * (b.x - a.x), py = a.y + u * (b.y - a.y);
          dist = Math.hypot(vx - px, vy - py);
        }
        if (dist < bestLinkDist) {
          bestLinkDist = dist;
          found = link.id;
        }
      }
    }

    hoverEntity = found;
    topoCanvas.style.cursor = found ? "pointer" : "default";

    const tip = document.getElementById("tooltip");
    if (found && state.latest && tip) {
      if (state.nodes[found]) {
        const n = state.nodes[found], m = state.latest.nodes[found] || { tp: 0, pps: 0, lat: 0, loss: 0, cpu: 0, mem: 0 };
        const h = state.latest.health.nodes[found];
        const hCol = healthColor(h ?? 100);
        tip.innerHTML = `<h5>${n.label} <span style="font-weight:400;color:${C.textMuted}">${n.kind}</span></h5>` +
          `<span style="color:${hCol};font-weight:700">health ${h ? h.toFixed(0) : "--"}/100</span><br>` +
          `tp ${m.tp.toFixed(1)} Mbps | ${m.pps.toFixed(0)} pps<br>` +
          `lat ${m.lat.toFixed(1)} ms | loss ${m.loss.toFixed(2)}%<br>` +
          `cpu ${m.cpu.toFixed(0)}% | mem ${m.mem.toFixed(0)}%`;
      } else if (state.links[found]) {
        const l = state.links[found], m = state.latest.links[found] || { tp: 0, util: 0, lat: 0, loss: 0 };
        tip.innerHTML = `<h5>Link: ${found}</h5>` +
          `${l.src} ↔ ${l.dst} (${l.bandwidth_mbps} Mbps)<br>` +
          `util: <b>${m.util.toFixed(1)}%</b> | tp ${m.tp.toFixed(1)} Mbps<br>` +
          `lat: ${m.lat.toFixed(2)} ms | loss: ${m.loss.toFixed(2)}%`;
      }
      tip.style.left = (ev.clientX - rect.left + 16) + "px";
      tip.style.top = (ev.clientY - rect.top + 12) + "px";
      tip.classList.remove("hidden");
    } else if (tip) {
      tip.classList.add("hidden");
    }
  });

  topoCanvas.addEventListener("mouseleave", () => {
    const tip = document.getElementById("tooltip");
    if (tip) tip.classList.add("hidden");
  });

  topoCanvas.addEventListener("click", () => {
    if (wasDragging) { wasDragging = false; return; }
    if (hoverEntity) selectEntity(hoverEntity);
  });
}

/* ---- Zoom & Pan Controls ---- */
let panning = false, wasDragging = false, panStart = { x: 0, y: 0, dx: 0, dy: 0 };
if (topoCanvas) {
  topoCanvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const rect = topoCanvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const t = topoTransform();
    const mx = (ev.clientX - rect.left) * dpr, my = (ev.clientY - rect.top) * dpr;
    const vx = (mx - t.ox) / t.s, vy = (my - t.oy) / t.s;
    const factor = ev.deltaY < 0 ? 1.12 : 0.88;
    const newScale = Math.max(0.4, Math.min(5, state.view.scale * factor));
    const newS = t.baseS * newScale;
    state.view.dx = mx / dpr - (vx * newS + (topoCanvas.width / dpr - VW * newS) / 2);
    state.view.dy = my / dpr - (vy * newS + (topoCanvas.height / dpr - VH * newS) / 2);
    state.view.scale = newScale;
  }, { passive: false });

  topoCanvas.addEventListener("mousedown", (ev) => {
    if (ev.button !== 0) return;
    panning = true;
    wasDragging = false;
    panStart = { x: ev.clientX, y: ev.clientY, dx: state.view.dx, dy: state.view.dy };
    topoCanvas.style.cursor = "grabbing";
  });
  window.addEventListener("mousemove", (ev) => {
    if (!panning) return;
    if (Math.hypot(ev.clientX - panStart.x, ev.clientY - panStart.y) > 4) {
      wasDragging = true;
    }
    state.view.dx = panStart.dx + (ev.clientX - panStart.x);
    state.view.dy = panStart.dy + (ev.clientY - panStart.y);
  });
  window.addEventListener("mouseup", () => {
    panning = false;
    if (topoCanvas) topoCanvas.style.cursor = hoverEntity ? "pointer" : "default";
  });

  const zoomInBtn = document.getElementById("topo-zoom-in");
  if (zoomInBtn) {
    zoomInBtn.addEventListener("click", () => {
      state.view.scale = Math.min(4.0, state.view.scale * 1.25);
      showToast("Zoom", `View scale: ${(state.view.scale * 100).toFixed(0)}%`, "info", 1000);
    });
  }
  const zoomOutBtn = document.getElementById("topo-zoom-out");
  if (zoomOutBtn) {
    zoomOutBtn.addEventListener("click", () => {
      state.view.scale = Math.max(0.4, state.view.scale / 1.25);
      showToast("Zoom", `View scale: ${(state.view.scale * 100).toFixed(0)}%`, "info", 1000);
    });
  }
  const zoomFitBtn = document.getElementById("topo-fit");
  if (zoomFitBtn) {
    zoomFitBtn.addEventListener("click", () => {
      state.view.scale = 1.0;
      state.view.dx = 0;
      state.view.dy = 0;
      showToast("View Reset", "Topology centered (100%)", "info", 1200);
    });
  }
}

/* ============================================================
   INSPECTOR PANEL
   ============================================================ */
function selectEntity(id) {
  state.selected = id;
  const inspTitle = document.getElementById("insp-id");
  if (inspTitle) inspTitle.textContent = id;
  updateInspectorLive();
  showToast("Inspecting Entity", `Loading telemetry for ${id}`, "info", 1800);
  fetch(`${API_BASE}/api/metrics?entity=${encodeURIComponent(id)}&window=120`)
    .then(r => r.ok ? r.json() : null)
    .then(data => { if (data && state.selected === id) renderInspectorCharts(data.series); });
}

function updateInspectorLive() {
  const id = state.selected;
  if (!id || !state.latest) return;
  const body = document.getElementById("insp-body");
  if (!body) return;
  const isNode = !!state.nodes[id];
  const h = isNode ? state.latest.health.nodes[id] : state.latest.health.links[id];
  const anom = state.latest.anomalies[id] || 0;
  const rows = [];
  const kv = (k, v) => rows.push(`<div class="insp-row"><span class="k">${k}</span><span>${v}</span></div>`);
  if (isNode) {
    const n = state.nodes[id], m = state.latest.nodes[id] || { tp: 0, tx: 0, rx: 0, pps: 0, fan: 0, lat: 0, jit: 0, loss: 0, cpu: 0, mem: 0 };
    const isCloud = state.topologyName === "aws-3tier" || !!state.nodes["alb"];
    if (isCloud) {
      if (id === "alb") {
        kv("AWS Service", "Application Load Balancer (v2)");
        kv("Target Groups", "tg-web (2/2 targets healthy)");
        kv("p99 Latency", `${(m.lat * 1.5).toFixed(1)} ms`);
        kv("500 Error Rate", `${Math.min(99.9, m.loss * 4.2).toFixed(1)}%`);
      } else if (id === "waf") {
        kv("AWS Service", "AWS WAF v2 WebACL");
        kv("Rule Action", "Block / RateLimit (1000/5m)");
        kv("Inspected Traffic", `${(m.tp * 1.15).toFixed(1)} Mbps`);
      } else if (id === "web1" || id === "web2") {
        kv("AWS Service", `EC2 Auto Scaling (${id === "web1" ? "AZ-1a" : "AZ-1b"})`);
        kv("Instance Type", "c6i.xlarge (4 vCPU, 8GB)");
        kv("Worker Threads", `${Math.round(20 + m.tp * 12)} active`);
      } else if (id === "app1" || id === "app2") {
        kv("AWS Service", `ECS Fargate (${id === "app1" ? "orders-api" : "auth-api"})`);
        kv("DB Connection Pool", `${Math.round(15 + m.cpu * 0.4)} / 64 max`);
      } else if (id === "db1") {
        kv("AWS Service", "Amazon RDS Aurora PostgreSQL");
        kv("Active Connections", `${Math.round(45 + m.cpu * 0.8)}`);
        kv("Buffer Hit Ratio", "99.4%");
      } else if (id === "s3") {
        kv("AWS Service", "Amazon S3 Lakehouse Bucket");
        kv("Encryption", "aws/s3 (SSE-KMS enabled)");
      }
    }
    kv("type", `${n.kind}${n.role ? " / " + n.role : ""}`);
    kv("throughput", `${m.tp.toFixed(1)} Mbps (tx ${m.tx.toFixed(1)} / rx ${m.rx.toFixed(1)})`);
    kv("packet rate", `${m.pps.toFixed(0)} pps, fanout ${m.fan}`);
    kv("latency", `${m.lat.toFixed(2)} ms, jitter ${m.jit.toFixed(2)} ms`);
    kv("packet loss", `${m.loss.toFixed(2)}%`);
    kv("cpu / mem", `${m.cpu.toFixed(0)}% / ${m.mem.toFixed(0)}%`);
  } else {
    const l = state.links[id] || { src: "?", dst: "?", bandwidth_mbps: 0 }, m = state.latest.links[id] || { tp: 0, util: 0, lat: 0, loss: 0, drop: 0 };
    kv("endpoints", `${l.src} ↔ ${l.dst}`);
    kv("capacity", `${l.bandwidth_mbps} Mbps`);
    kv("throughput", `${m.tp.toFixed(1)} Mbps (${m.util.toFixed(1)}% util)`);
    kv("latency", `${m.lat.toFixed(2)} ms`);
    kv("loss / dropped", `${m.loss.toFixed(2)}% / ${m.drop.toFixed(1)} Mbps`);
  }
  const openAlerts = state.alerts.filter(a => a.entity_id === id);
  const hVal = (h ?? 100).toFixed(0);
  const hCol = healthColor(h ?? 100);
  body.innerHTML =
    `<div class="insp-health" style="color:${hCol}">${hVal}<span style="font-size:14px;color:${C.textMuted}">/100</span></div>` +
    `<div class="insp-row"><span class="k">anomaly score</span><span style="color:${anom >= 0.72 ? C.rose : anom >= 0.5 ? C.amber : C.textSec}">${anom.toFixed(3)}</span></div>` +
    rows.join("") +
    `<canvas class="insp-canvas" id="insp-chart1"></canvas>` +
    `<canvas class="insp-canvas" id="insp-chart2"></canvas>` +
    (openAlerts.length ? `<div class="insp-alerts"><b style="color:${C.amber}">⚠ OPEN ALERTS</b>` +
      openAlerts.map(a => `<div>[${a.severity}] ${a.message}</div>`).join("") + `</div>` : "");
  if (state._inspSeries) drawInspectorCharts(state._inspSeries, isNode);
}

function renderInspectorCharts(series) {
  state._inspSeries = series;
  const isNode = !!state.nodes[state.selected];
  drawInspectorCharts(series, isNode);
}
function drawInspectorCharts(series, isNode) {
  const c1 = document.getElementById("insp-chart1");
  const c2 = document.getElementById("insp-chart2");
  if (!c1 || !c2) return;
  const key1 = isNode ? "throughput_mbps" : "utilization_pct";
  miniChart(c1, series.map(s => s[key1]), C.cyan, isNode ? "throughput Mbps" : "utilization %");
  miniChart(c2, series.map(s => s.packet_loss_pct), C.rose, "loss %");
}

function miniChart(canvas, values, color, label) {
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w) return;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.scale(dpr, dpr);
  const max = Math.max(...values, 1e-6) * 1.15;

  ctx.strokeStyle = C.borderSub;
  ctx.lineWidth = 1;
  for (let i = 1; i < 4; i++) {
    const gy = 14 + (h - 18) * i / 4;
    ctx.beginPath(); ctx.moveTo(4, gy); ctx.lineTo(w - 4, gy); ctx.stroke();
  }

  ctx.fillStyle = C.textMuted; ctx.font = "500 9px 'Inter', sans-serif";
  ctx.fillText(`${label}  max ${max.toFixed(1)}`, 4, 10);

  const grad = ctx.createLinearGradient(0, 14, 0, h);
  grad.addColorStop(0, color + "30");
  grad.addColorStop(1, "transparent");
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = 4 + (w - 8) * i / Math.max(1, values.length - 1);
    const y = h - 4 - (h - 18) * v / max;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(w - 4, h); ctx.lineTo(4, h); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();

  ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath();
  values.forEach((v, i) => {
    const x = 4 + (w - 8) * i / Math.max(1, values.length - 1);
    const y = h - 4 - (h - 18) * v / max;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
}

/* ============================================================
   ALERTS FEED
   ============================================================ */
function renderAlerts() {
  const feed = document.getElementById("alerts-feed");
  const countEl = document.getElementById("alert-count");
  if (!feed || !countEl) return;
  countEl.textContent = state.alerts.length;
  countEl.style.display = state.alerts.length ? "" : "none";

  feed.innerHTML = state.alerts.map(a => {
    const ts = new Date(a.updated_at * 1000).toLocaleTimeString();
    const conf = (a.confidence != null && a.confidence >= 0)
      ? ` <span class="conf-tag">conf ${(a.confidence * 100).toFixed(0)}%</span>` : "";
    const sevIcon = a.severity === "critical" ? "🔴" : a.severity === "info" ? "🔵" : "🟡";
    return `<div class="alert-item ${a.severity} ${state.selectedAlert === a.id ? "selected" : ""}" data-sel="${a.id}">
      <div class="ahead"><span>${sevIcon} [${a.severity.toUpperCase()}] ${a.entity_id}${conf}</span><span>${ts}</span></div>
      <div class="amsg">${escapeHtml(a.message)}${a.hits > 1 ? ` (×${a.hits})` : ""}</div>
      <button class="ack" data-ack="${a.id}">ack</button>
    </div>`;
  }).join("") || `<div style="color:${C.textMuted};padding:12px;text-align:center;font-style:italic">No active alerts — network healthy</div>`;
  feed.scrollTop = feed.scrollHeight;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const alertsFeedEl = document.getElementById("alerts-feed");
if (alertsFeedEl) {
  alertsFeedEl.addEventListener("click", (ev) => {
    const ackId = ev.target.dataset && ev.target.dataset.ack;
    if (ackId) {
      fetch(`${API_BASE}/api/alerts/${ackId}/ack`, { method: "POST" });
      showToast("Alert Acknowledged", `Muted alert ${ackId}`, "info", 2000);
      return;
    }
    const item = ev.target.closest("[data-sel]");
    if (item) selectAlert(item.dataset.sel);
  });
}

function selectAlert(alertId) {
  state.selectedAlert = alertId === state.selectedAlert ? null : alertId;
  renderAlerts();
  if (!state.selectedAlert) return;
  const alert = state.alerts.find(a => a.id === alertId);
  if (alert) {
    selectEntity(alert.entity_id);
    showToast("Investigating Alert", `${alert.severity.toUpperCase()} on ${alert.entity_id}`, "warning", 2500);
  }
  Promise.all([
    fetch(`${API_BASE}/api/explain/${alertId}`).then(r => r.ok ? r.json() : null),
    fetch(`${API_BASE}/api/rootcause/${alertId}`).then(r => r.ok ? r.json() : null),
  ]).then(([explain, rootcause]) => {
    if (state.selectedAlert === alertId) renderAlertDetail(explain, rootcause);
  });
}

function renderAlertDetail(explain, rootcause) {
  const body = document.getElementById("insp-body");
  if (!body) return;
  let html = "";
  if (explain && explain.attributions && explain.attributions.length) {
    html += `<div class="insp-section"><h6>EXPLAINABILITY — Feature Attribution</h6>`;
    for (const a of explain.attributions.slice(0, 6)) {
      const w = Math.min(100, a.contribution * 100);
      html += `<div class="attr-bar-row"><span class="aname">${a.feature}</span>
        <span class="attr-bar"><span class="attr-fill" style="width:${w}%"></span></span>
        <span class="attr-z">z=${a.z}</span></div>`;
    }
    html += `</div>`;
  }
  if (rootcause && rootcause.chain && rootcause.chain.length) {
    html += `<div class="insp-section"><h6>ROOT CAUSE CHAIN</h6>`;
    rootcause.chain.forEach((c, i) => {
      html += `<div class="chain-item"><span class="cscore">${c.causal_score.toFixed(2)}</span>
        <span class="cent">${c.entity_id}</span>
        <span style="color:${C.textMuted}">anom ${c.anomaly_score.toFixed(2)} expl ${c.explained.toFixed(2)}</span></div>`;
      if (i < rootcause.chain.length - 1) html += `<div class="chain-arrow">↓</div>`;
    });
    html += `</div>`;
  }
  if (html) body.insertAdjacentHTML("beforeend", html);
}

/* ============================================================
   CHARTS (Throughput, Latency, Anomaly, Loss)
   ============================================================ */
class Chart {
  constructor(canvasId, opts) {
    this.canvas = document.getElementById(canvasId);
    this.opts = opts;
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext("2d");
    this.setupHover();
  }
  setupHover() {
    this.canvas.addEventListener("mousemove", (ev) => {
      const rect = this.canvas.getBoundingClientRect();
      const series = this.opts.series();
      if (!series.length || !series[0].values.length) return;
      const count = series[0].values.length;
      const x = ev.clientX - rect.left;
      const idx = Math.max(0, Math.min(count - 1, Math.round((x - 6) / (rect.width - 12) * (count - 1))));
      state.chartHover = { canvasId: this.canvas.id, idx, x, y: ev.clientY - rect.top, visible: true };
    });
    this.canvas.addEventListener("mouseleave", () => {
      state.chartHover.visible = false;
    });
  }
  draw() {
    if (!this.canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const w = this.canvas.clientWidth, h = this.canvas.clientHeight;
    if (!w || !h) return;
    this.canvas.width = w * dpr; this.canvas.height = h * dpr;
    const ctx = this.ctx;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);

    const series = this.opts.series();
    if (!series.length || !series[0].values.length) {
      ctx.fillStyle = C.textMuted; ctx.font = "500 11px 'Inter', sans-serif";
      ctx.textAlign = "center"; ctx.fillText("Awaiting telemetry stream...", w / 2, h / 2);
      return;
    }

    const allVals = series.flatMap(s => s.values);
    const max = Math.max(...allVals, 1e-6) * (this.opts.yMaxMult || 1.2);

    // Grid lines
    ctx.strokeStyle = C.borderSub;
    ctx.lineWidth = 1;
    for (let i = 1; i <= 3; i++) {
      const gy = 14 + (h - 22) * i / 4;
      ctx.beginPath(); ctx.moveTo(6, gy); ctx.lineTo(w - 6, gy); ctx.stroke();
    }

    // Series lines
    for (const s of series) {
      const vals = s.values;
      const grad = ctx.createLinearGradient(0, 14, 0, h);
      grad.addColorStop(0, s.color + "28");
      grad.addColorStop(1, "transparent");
      ctx.beginPath();
      vals.forEach((v, i) => {
        const x = 6 + (w - 12) * i / Math.max(1, vals.length - 1);
        const y = h - 6 - (h - 22) * v / max;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.lineTo(w - 6, h); ctx.lineTo(6, h); ctx.closePath();
      ctx.fillStyle = grad; ctx.fill();

      ctx.strokeStyle = s.color;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      vals.forEach((v, i) => {
        const x = 6 + (w - 12) * i / Math.max(1, vals.length - 1);
        const y = h - 6 - (h - 22) * v / max;
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();

      // Latest value dot
      if (vals.length) {
        const lx = w - 6, ly = h - 6 - (h - 22) * vals[vals.length - 1] / max;
        ctx.beginPath(); ctx.arc(lx, ly, 3, 0, 2 * Math.PI);
        ctx.fillStyle = s.color; ctx.fill();
      }
    }
  }
}

const charts = [
  new Chart("ch-tp", {
    series: () => {
      const base = [{ values: state.netSeries.tp, color: C.cyan, label: "throughput Mbps" }];
      if (state.forecast && state.forecast.points) {
        base.push({ values: state.forecast.points.map(p => p.mean), color: C.emeraldLight, label: "conformal forecast" });
      }
      return base;
    },
  }),
  new Chart("ch-lat", { series: () => [{ values: state.netSeries.lat, color: C.amber, label: "latency ms" }] }),
  new Chart("ch-anom", {
    series: () => [{ values: state.netSeries.anom, color: C.rose, label: "max anomaly" }],
    yMaxMult: 1.05,
  }),
  new Chart("ch-loss", { series: () => [{ values: state.netSeries.loss, color: C.violet, label: "loss %" }] }),
];

/* ============================================================
   MAIN RENDER LOOP
   ============================================================ */
let lastChartDraw = 0;
function loop(ts) {
  if (!state.paused) {
    dashOffset += 0.35 * (state.speedMultiplier || 1.0);
    pulseT += 0.016 * (state.speedMultiplier || 1.0);
  }
  renderTopology();
  if (ts - lastChartDraw > 400) {
    lastChartDraw = ts;
    for (const c of charts) c.draw();
  }
  updateChartTooltip();
  requestAnimationFrame(loop);
}

function updateChartTooltip() {
  const tip = document.getElementById("chart-tooltip");
  if (!tip) return;
  if (!state.chartHover.visible || state.chartHover.idx < 0) {
    tip.classList.add("hidden");
    return;
  }
  const idx = state.chartHover.idx;
  const chart = charts.find(c => c.canvas && c.canvas.id === state.chartHover.canvasId);
  if (!chart) return;
  const lines = chart.opts.series().map(s => {
    const v = s.values[idx];
    return `<span style="color:${s.color}">●</span> ${s.label}: <b>${v != null ? v.toFixed(2) : "--"}</b>`;
  });
  tip.innerHTML = lines.join("<br>");
  const pane = document.getElementById("charts-row");
  if (pane) {
    const rect = pane.getBoundingClientRect();
    tip.style.left = (rect.left + state.chartHover.x + 16) + "px";
    tip.style.top = (rect.top + state.chartHover.y + 12) + "px";
    tip.classList.remove("hidden");
  }
}

/* ============================================================
   CONTROLS: Attacks, Sim Clock, Speed, Drawers
   ============================================================ */
function buildTargetSelects() {
  const targets = state.nodeList.filter(n => ["server", "workstation"].includes(n.kind));
  if (!targets.length) return;
  const opts = targets.map(n => `<option value="${n.id}">${n.label} (${n.id})</option>`).join("");
  const atkTarget = document.getElementById("atk-target");
  if (atkTarget) atkTarget.innerHTML = opts;
  const wiTarget = document.getElementById("wi-target");
  if (wiTarget) wiTarget.innerHTML = opts;
  const wiNode = document.getElementById("wi-node");
  if (wiNode) {
    wiNode.innerHTML = state.nodeList.filter(n => !["attacker"].includes(n.kind))
      .map(n => `<option value="${n.id}">${n.label} (${n.id})</option>`).join("");
  }
  const wiLink = document.getElementById("wi-link");
  if (wiLink && state.linkList.length) {
    wiLink.innerHTML = state.linkList.map(l => `<option value="${l.id}">${l.id}</option>`).join("");
  }
}

// Attack Buttons
document.querySelectorAll(".atk-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const atkType = btn.dataset.atk;
    const targetId = (document.getElementById("atk-target") && document.getElementById("atk-target").value) || "web1";
    const durationS = Number((document.getElementById("atk-duration") && document.getElementById("atk-duration").value)) || 60;

    showToast("Launching Attack", `Injecting ${atkType.toUpperCase()} targeting ${targetId}...`, "warning", 3000);

    fetch(`${API_BASE}/api/attacks/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type: atkType, target_id: targetId, duration_s: durationS })
    })
    .then(r => {
      if (!r.ok) return r.json().then(d => { throw new Error(d.detail || "Attack failed"); });
      return r.json();
    })
    .then(ev => {
      showToast("Attack Active", `${atkType.toUpperCase()} running on ${targetId} (${durationS}s)`, "danger", 4000);
      updateActiveCampaigns([ev]);
    })
    .catch(err => {
      showToast("Attack Error", err.message, "danger", 4000);
    });
  });
});

// Stop Attacks
function stopAllAttacks() {
  fetch(`${API_BASE}/api/attacks/stop`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({})
  })
  .then(r => r.json())
  .then(() => {
    state.attacks = [];
    updateActiveCampaigns([]);
    showToast("Attacks Stopped", "All active attacks terminated. Restoring baseline telemetry.", "success", 3500);
  })
  .catch(err => {
    showToast("Stop Error", err.message, "danger", 3000);
  });
}
const stopBtn = document.getElementById("atk-stop");
if (stopBtn) stopBtn.addEventListener("click", stopAllAttacks);
const bannerStopBtn = document.getElementById("banner-stop-btn");
if (bannerStopBtn) bannerStopBtn.addEventListener("click", stopAllAttacks);

// Pause / Resume
const pauseBtn = document.getElementById("pause-btn");
if (pauseBtn) {
  pauseBtn.addEventListener("click", () => {
    state.paused = !state.paused;
    const watermark = document.getElementById("pause-watermark");
    pauseBtn.textContent = state.paused ? "▶ Resume" : "Pause";
    pauseBtn.classList.toggle("active", state.paused);
    if (watermark) watermark.classList.toggle("hidden", !state.paused);

    showToast(state.paused ? "Simulation Paused" : "Simulation Resumed",
              state.paused ? "Clock, telemetry and model updates held." : "Simulation loop running.",
              state.paused ? "warning" : "info", 2500);

    fetch(`${API_BASE}/api/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paused: state.paused })
    });
  });
}

// Speed Slider
const speedSlider = document.getElementById("speed-slider");
if (speedSlider) {
  speedSlider.addEventListener("input", (ev) => {
    const speed = Number(ev.target.value);
    const speedVal = document.getElementById("speed-val");
    if (speedVal) speedVal.textContent = speed.toFixed(2).replace(/0+$/, "").replace(/\.$/, ".0") + "x";
    const tickMs = Math.round(1000 / speed);
    const rateEl = document.getElementById("tick-rate");
    if (rateEl) rateEl.textContent = (tickMs / 1000).toFixed(2) + "s";
    state.speedMultiplier = speed;
    fetch(`${API_BASE}/api/config`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tick_ms: tickMs })
    });
  });
}

// Reset Twin
const resetBtn = document.getElementById("reset-btn");
if (resetBtn) {
  resetBtn.addEventListener("click", () => {
    fetch(`${API_BASE}/api/twin/reset`, { method: "POST" })
      .then(r => r.json())
      .then(d => {
        state.netSeries = { tp: [], lat: [], loss: [], anom: [] };
        state.whatifHighlight.clear();
        showToast("Twin Reset", `Telemetry, detectors and predictor recalibrated at tick ${d.tick}.`, "success", 3500);
      })
      .catch(err => {
        showToast("Reset Failed", err.message, "danger", 3000);
      });
  });
}

/* ============================================================
   DRAWER PANELS MANAGEMENT
   ============================================================ */
function toggleDrawer(drawerId, btnId) {
  const drawer = document.getElementById(drawerId);
  const btn = document.getElementById(btnId);
  if (!drawer) return false;
  const isOpening = drawer.classList.contains("hidden");

  // Close all other drawers
  ["whatif-panel", "chat-panel", "sync-panel", "response-panel", "cloud-traffic-panel"].forEach(id => {
    if (id !== drawerId) {
      const d = document.getElementById(id);
      if (d) d.classList.add("hidden");
    }
  });
  ["whatif-toggle", "chat-toggle", "sync-toggle", "response-toggle", "cloud-traffic-toggle"].forEach(id => {
    if (id !== btnId) {
      const b = document.getElementById(id);
      if (b) b.classList.remove("active");
    }
  });

  drawer.classList.toggle("hidden", !isOpening);
  if (btn) btn.classList.toggle("active", isOpening);
  return isOpening;
}

const whatifToggle = document.getElementById("whatif-toggle");
if (whatifToggle) {
  whatifToggle.addEventListener("click", () => {
    buildTargetSelects();
    toggleDrawer("whatif-panel", "whatif-toggle");
  });
}

const chatToggle = document.getElementById("chat-toggle");
if (chatToggle) {
  chatToggle.addEventListener("click", () => {
    toggleDrawer("chat-panel", "chat-toggle");
  });
}

const cloudTrafficToggle = document.getElementById("cloud-traffic-toggle");
if (cloudTrafficToggle) {
  cloudTrafficToggle.addEventListener("click", () => {
    const open = toggleDrawer("cloud-traffic-panel", "cloud-traffic-toggle");
    if (open) refreshCloudTrafficStatus();
  });
}

document.querySelectorAll(".close").forEach(b => {
  b.addEventListener("click", () => {
    const target = document.getElementById(b.dataset.close);
    if (target) target.classList.add("hidden");
    ["whatif-toggle", "chat-toggle", "sync-toggle", "response-toggle", "cloud-traffic-toggle"].forEach(id => {
      const btn = document.getElementById(id);
      if (btn) btn.classList.remove("active");
    });
  });
});

/* ---- What-If Scenario Sandbox ---- */
const wiKind = document.getElementById("wi-kind");
if (wiKind) {
  wiKind.addEventListener("change", (ev) => {
    const kind = ev.target.value;
    const show = (id, on) => {
      const el = document.getElementById(id);
      if (el) el.classList.toggle("hidden", !on);
    };
    show("wi-link-row", kind === "link_failure");
    show("wi-node-row", kind === "node_failure");
    show("wi-mult-row", kind === "surge");
    show("wi-atk-row", kind === "attack");
    show("wi-target-row", kind === "attack");
  });
}

// Quick Drill Presets
document.querySelectorAll(".preset-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const preset = btn.dataset.preset;
    const kindSelect = document.getElementById("wi-kind");
    if (!kindSelect) return;
    if (preset === "ddos_alb") {
      kindSelect.value = "attack";
      kindSelect.dispatchEvent(new Event("change"));
      const wiAtk = document.getElementById("wi-atk");
      if (wiAtk) wiAtk.value = "ddos";
      const wiTarget = document.getElementById("wi-target");
      if (wiTarget) wiTarget.value = "alb";
    } else if (preset === "web1_crash") {
      kindSelect.value = "node_failure";
      kindSelect.dispatchEvent(new Event("change"));
      const wiNode = document.getElementById("wi-node");
      if (wiNode) wiNode.value = "web1";
    } else if (preset === "sqli_db1") {
      kindSelect.value = "attack";
      kindSelect.dispatchEvent(new Event("change"));
      const wiAtk = document.getElementById("wi-atk");
      if (wiAtk) wiAtk.value = "lateral";
      const wiTarget = document.getElementById("wi-target");
      if (wiTarget) wiTarget.value = "db1";
    } else if (preset === "iot_botnet") {
      kindSelect.value = "attack";
      kindSelect.dispatchEvent(new Event("change"));
      const wiAtk = document.getElementById("wi-atk");
      if (wiAtk) wiAtk.value = "exfiltration";
      const wiTarget = document.getElementById("wi-target");
      if (wiTarget) wiTarget.value = "s3";
    } else if (preset === "core_cut") {
      kindSelect.value = "link_failure";
      kindSelect.dispatchEvent(new Event("change"));
      const wiLink = document.getElementById("wi-link");
      if (wiLink && wiLink.options.length) {
        let found = false;
        for (let i = 0; i < wiLink.options.length; i++) {
          if (wiLink.options[i].value.includes("alb") && wiLink.options[i].value.includes("web")) {
            wiLink.selectedIndex = i;
            found = true;
            break;
          }
        }
        if (!found) wiLink.selectedIndex = 0;
      }
    } else if (preset === "surge_5x") {
      kindSelect.value = "surge";
      kindSelect.dispatchEvent(new Event("change"));
      const wiMult = document.getElementById("wi-mult");
      if (wiMult) wiMult.value = "5.0";
    }
    showToast("Preset Loaded", `Configured ${preset.replace(/_/g, " ")}. Click 'Run Scenario'.`, "info", 2200);
  });
});

const wiRun = document.getElementById("wi-run");
if (wiRun) {
  wiRun.addEventListener("click", () => {
    const kind = (document.getElementById("wi-kind") && document.getElementById("wi-kind").value) || "node_failure";
    const params = {};
    if (kind === "link_failure") params.link_id = (document.getElementById("wi-link") && document.getElementById("wi-link").value) || "edge3-web1";
    if (kind === "node_failure") params.node_id = (document.getElementById("wi-node") && document.getElementById("wi-node").value) || "web1";
    if (kind === "surge") params.multiplier = Number((document.getElementById("wi-mult") && document.getElementById("wi-mult").value)) || 3;
    if (kind === "attack") {
      params.type = (document.getElementById("wi-atk") && document.getElementById("wi-atk").value) || "ddos";
      params.target_id = (document.getElementById("wi-target") && document.getElementById("wi-target").value) || "web1";
    }
    const results = document.getElementById("wi-results");
    if (results) results.innerHTML = `<div style="color:${C.cyanLight};text-align:center;padding:24px"><span class="pulse-icon">⏳</span> Evaluating counterfactual sandbox...</div>`;

    showToast("Running What-If", "Evaluating scenario impact across digital twin clone...", "info", 2500);

    fetch(`${API_BASE}/api/whatif`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scenario: { kind, params },
        horizon_ticks: Number((document.getElementById("wi-horizon") && document.getElementById("wi-horizon").value)) || 30
      })
    })
    .then(r => r.json())
    .then(res => {
      if (res.detail) {
        if (results) results.innerHTML = `<div class="wi-summary" style="color:${C.rose}">Error: ${escapeHtml(String(res.detail))}</div>`;
        return;
      }
      state.whatifHighlight = new Set((res.affected_entities || []).filter(a => a.entity_kind === "node").map(a => a.entity_id));
      const items = (res.affected_entities || []).map(a =>
        `<div class="wi-item ${a.entity_kind}-aff">` +
        (a.entity_kind === "node"
          ? `<b>${a.entity_id}</b>: health ${a.health_before} → ${a.health_after} (tp ${a.throughput_delta_mbps >= 0 ? "+" : ""}${a.throughput_delta_mbps} Mbps)`
          : `<b>${a.entity_id}</b>: util ${a.util_before_pct}% → ${a.util_after_pct}%`) + `</div>`).join("");
      const sat = (res.saturation_timeline || []).map(s =>
        `<div class="wi-item link-aff">t+${s.tick_offset}: ${s.link_id} hits <b>${s.utilization_pct}%</b> util</div>`).join("");
      if (results) {
        results.innerHTML = `<div class="wi-summary">${escapeHtml(res.summary)}<br>` +
          `<span class="drop">Projected health drop: ${res.projected_health_drop}</span> ` +
          `(baseline ${res.baseline_network_health} → scenario ${res.scenario_network_health})</div>` +
          `<h4 style="color:${C.textMuted};margin:10px 0 6px;font-size:10px;letter-spacing:1.5px">AFFECTED ENTITIES</h4>` +
          (items || `<div class='wi-item' style='color:${C.textMuted}'>No direct node impairment</div>`) +
          `<h4 style="color:${C.textMuted};margin:10px 0 6px;font-size:10px;letter-spacing:1.5px">SATURATION TIMELINE</h4>` +
          (sat || `<div class='wi-item' style='color:${C.textMuted}'>No saturation projected</div>`);
      }
      showToast("Scenario Evaluated", `Predicted Health: ${res.scenario_network_health}/100 (drop: ${res.projected_health_drop})`, res.projected_health_drop > 10 ? "danger" : "success", 4000);
    })
    .catch(err => {
      if (results) results.innerHTML = `<div class="wi-summary" style="color:${C.rose}">Evaluation error: ${escapeHtml(String(err))}</div>`;
    });
  });
}

/* ---- Analyst Chat ---- */
function renderMarkdownish(text) {
  let html = escapeHtml(text);
  html = html.replace(/^## (.*)$/gm, "<h2>$1</h2>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  return html;
}
function addChatMsg(role, text, meta) {
  const box = document.getElementById("chat-messages");
  if (!box) return;
  const div = document.createElement("div");
  div.className = `chat-msg ${role}`;
  div.innerHTML = `<div class="meta">${meta || ""}</div><div class="bubble">${role === "assistant" ? renderMarkdownish(text) : escapeHtml(text)}</div>`;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
}
function sendChat() {
  const input = document.getElementById("chat-input");
  if (!input) return;
  const q = input.value.trim();
  if (!q) return;
  input.value = "";
  addChatMsg("user", q, "you");
  const box = document.getElementById("chat-messages");
  const typing = document.createElement("div");
  typing.className = "typing";
  typing.textContent = "analyst is synthesizing security evidence...";
  if (box) { box.appendChild(typing); box.scrollTop = box.scrollHeight; }

  fetch(`${API_BASE}/api/analyst/ask`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question: q })
  })
  .then(r => r.json())
  .then(res => {
    typing.remove();
    if (res.detail) { addChatMsg("assistant", "Error: " + String(res.detail), "system"); return; }
    const chatMode = document.getElementById("chat-mode");
    if (chatMode) {
      chatMode.textContent = res.mode;
      chatMode.className = "badge " + (res.mode === "ollama" ? "ollama" : "fallback");
    }
    addChatMsg("assistant", res.answer, `${res.mode} · ${res.model} · ${res.elapsed_s}s`);
  })
  .catch(err => {
    typing.remove();
    addChatMsg("assistant", "Request failed: " + err, "system");
  });
}

const chatSendBtn = document.getElementById("chat-send");
if (chatSendBtn) chatSendBtn.addEventListener("click", sendChat);
const chatInput = document.getElementById("chat-input");
if (chatInput) {
  chatInput.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") sendChat();
  });
}

// Chat Prompt Pills
document.querySelectorAll(".pill-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const q = btn.dataset.query;
    if (chatInput) chatInput.value = q;
    sendChat();
  });
});

/* ---- Sync / Fidelity Panel ---- */
const syncToggle = document.getElementById("sync-toggle");
if (syncToggle) {
  syncToggle.addEventListener("click", () => {
    const open = toggleDrawer("sync-panel", "sync-toggle");
    if (open) {
      fetch(`${API_BASE}/api/sync`).then(r => r.json()).then(d => {
        const fidBadge = document.getElementById("sync-net-fid");
        if (fidBadge) {
          fidBadge.textContent = `net fidelity ${d.network_fidelity}${d.udp_listening ? "" : " (udp off)"}`;
        }
        state.syncEntities = Object.fromEntries(d.entities.map(e => [e.entity_id, e]));
        renderSyncList();
      });
    }
  });
}

function renderSyncList() {
  const list = document.getElementById("sync-list");
  const panel = document.getElementById("sync-panel");
  if (!list || (panel && panel.classList.contains("hidden"))) return;
  const entities = Object.values(state.syncEntities)
    .filter(e => e.mode || e.entity_id)
    .sort((a, b) => (a.entity_id > b.entity_id ? 1 : -1));
  if (!entities.length) {
    list.innerHTML = `<div style="color:${C.textMuted};padding:14px;font-style:italic">No live real feeds active.
      Ingesting from internal twin simulation loop.</div>`;
    return;
  }
  list.innerHTML = entities.map(e => {
    const f = e.fidelity ?? 100;
    const col = f >= 70 ? C.emerald : f >= 50 ? C.amber : C.rose;
    return `<div class="sync-row" data-sync-entity="${e.entity_id}">
      <span class="sid">${e.entity_id}</span>
      <span class="mode-badge mode-${e.mode}">${e.mode}</span>
      <span class="fid-bar"><span class="fid-fill" style="width:${f}%;background:${col}"></span></span>
      <span class="fval">${f.toFixed(0)}</span>
    </div>`;
  }).join("");
}

const syncListEl = document.getElementById("sync-list");
if (syncListEl) {
  syncListEl.addEventListener("click", (ev) => {
    const row = ev.target.closest("[data-sync-entity]");
    if (!row) return;
    const eid = row.dataset.syncEntity;
    state.syncDetailEntity = eid;
    const detail = document.getElementById("sync-detail");
    const nameEl = document.getElementById("sync-entity");
    if (detail) detail.classList.remove("hidden");
    if (nameEl) nameEl.textContent = eid;
    fetch(`${API_BASE}/api/sync/fidelity?entity=${encodeURIComponent(eid)}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d && state.syncDetailEntity === eid) drawSyncChart(d); });
  });
}

function drawSyncChart(d) {
  const canvas = document.getElementById("sync-chart");
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w) return;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const pairs = d.pairs.throughput_mbps || [];
  const sim = pairs.map(p => p[0]), real = pairs.map(p => p[1]);
  const max = Math.max(...sim, ...real, 1e-6) * 1.15;

  ctx.strokeStyle = C.borderSub;
  for (let i = 1; i < 4; i++) {
    const gy = 14 + (h - 24) * i / 4;
    ctx.beginPath(); ctx.moveTo(4, gy); ctx.lineTo(w - 4, gy); ctx.stroke();
  }

  ctx.fillStyle = C.textMuted; ctx.font = "500 9px 'Inter', sans-serif";
  ctx.fillText(`throughput Mbps  mode=${d.mode} fidelity=${d.fidelity}`, 4, 10);

  const drawLine = (vals, color) => {
    const grad = ctx.createLinearGradient(0, 14, 0, h - 4);
    grad.addColorStop(0, color + "25");
    grad.addColorStop(1, "transparent");
    ctx.beginPath();
    vals.forEach((v, i) => {
      const x = 4 + (w - 8) * i / Math.max(1, vals.length - 1);
      const y = h - 4 - (h - 18) * v / max;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.lineTo(4 + (w - 8), h - 4); ctx.lineTo(4, h - 4);
    ctx.closePath(); ctx.fillStyle = grad; ctx.fill();

    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath();
    vals.forEach((v, i) => {
      const x = 4 + (w - 8) * i / Math.max(1, vals.length - 1);
      const y = h - 4 - (h - 18) * v / max;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();
  };
  drawLine(sim, C.cyan);
  drawLine(real, C.emerald);

  ctx.fillStyle = C.cyan; ctx.fillRect(4, h - 11, 10, 3);
  ctx.fillStyle = C.textSec; ctx.fillText("twin (sim)", 18, h - 5);
  ctx.fillStyle = C.emerald; ctx.fillRect(80, h - 11, 10, 3);
  ctx.fillStyle = C.textSec; ctx.fillText("real feed", 94, h - 5);
}

/* ---- Research Strip ---- */
function sparkline(canvasId, values, color, target) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  if (!w || !h) return;
  canvas.width = w * dpr; canvas.height = h * dpr;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  if (!values || !values.length) return;
  const max = Math.max(...values, target || 0, 1e-6) * 1.05;

  if (target != null) {
    const y = h - 2 - (h - 4) * target / max;
    ctx.strokeStyle = C.amber + "55"; ctx.setLineDash([3, 3]);
    ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    ctx.setLineDash([]);
  }

  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color + "30");
  grad.addColorStop(1, "transparent");
  ctx.beginPath();
  values.forEach((v, i) => {
    const x = w * i / Math.max(1, values.length - 1);
    const y = h - 2 - (h - 4) * v / max;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.closePath();
  ctx.fillStyle = grad; ctx.fill();

  ctx.strokeStyle = color; ctx.lineWidth = 1.2; ctx.beginPath();
  values.forEach((v, i) => {
    const x = w * i / Math.max(1, values.length - 1);
    const y = h - 2 - (h - 4) * v / max;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();
}

function renderResearchStrip() {
  const r = state.research;
  if (!r) return;
  sparkline("rs-fidelity", r.fidelity_trend, C.cyan, 70);
  const rf = document.getElementById("rs-fidelity-val");
  if (rf) rf.textContent = r.fidelity_now != null ? r.fidelity_now.toFixed(0) : "--";
  sparkline("rs-coverage", r.coverage_trend, C.emerald, 0.9);
  const rc = document.getElementById("rs-coverage-val");
  if (rc) rc.textContent = r.coverage_now != null ? r.coverage_now.toFixed(2) : "--";
  const ra = document.getElementById("rs-agreement");
  if (ra) ra.textContent = r.detector_agreement != null ? (r.detector_agreement * 100).toFixed(0) + "%" : "--";
  const rd = document.getElementById("rs-drift");
  if (rd) {
    rd.textContent = r.drift_count;
    rd.style.color = r.drift_count ? C.amber : "";
  }
  sparkline("rs-reward", r.reward_trend, C.violet, null);
  const rr = document.getElementById("rs-reward-val");
  if (rr) rr.textContent = r.cumulative_reward.toFixed(1);
  const rl = document.getElementById("rs-latency");
  if (rl) rl.textContent = r.detection_latency_avg_ticks != null ? r.detection_latency_avg_ticks + "t" : "--";
}

/* ---- Risk Overlay ---- */
const riskToggle = document.getElementById("risk-toggle");
if (riskToggle) {
  riskToggle.addEventListener("click", () => {
    state.riskOverlay = !state.riskOverlay;
    riskToggle.classList.toggle("active", state.riskOverlay);
    const rp = document.getElementById("risk-paths");
    if (rp) rp.classList.toggle("hidden", !state.riskOverlay);
    showToast("Risk Heatmap", state.riskOverlay ? "Displaying node compromise risk distribution" : "Risk overlay deactivated", "info", 2000);
    if (state.riskOverlay && !state.risk) {
      fetch(`${API_BASE}/api/risk`).then(r => r.json()).then(d => {
        state.risk = { network_risk: d.network_risk, top_paths: d.top_paths,
                       nodes: Object.fromEntries(d.nodes.map(n => [n.entity_id, n.compromise])) };
        renderRiskPaths();
      });
    }
  });
}

function renderRiskPaths() {
  const risk = state.risk;
  if (!risk) return;
  const rn = document.getElementById("risk-net");
  if (rn) rn.textContent = `net risk ${risk.network_risk}`;
  const rpl = document.getElementById("risk-paths-list");
  if (rpl) {
    rpl.innerHTML = (risk.top_paths || []).map(p =>
      `<div class="risk-path-item">${p.path.join(" → ")} 
       <span style="color:${C.textMuted}">p=${p.probability} loss=${p.expected_loss}</span></div>`
    ).join("") || `<div class="risk-path-item" style="color:${C.textMuted}">no paths</div>`;
  }
}

/* ---- Response Panel ---- */
const responseToggle = document.getElementById("response-toggle");
if (responseToggle) {
  responseToggle.addEventListener("click", () => {
    const open = toggleDrawer("response-panel", "response-toggle");
    if (open) {
      fetch(`${API_BASE}/api/response/recommendations`).then(r => r.json()).then(d => {
        if (state.response) state.response.mode = d.mode;
        renderResponsePanel();
      });
    }
  });
}

function renderResponsePanel() {
  const panel = document.getElementById("response-panel");
  if (!panel || panel.classList.contains("hidden")) return;
  const resp = state.response;
  if (!resp) return;
  const rm = document.getElementById("resp-mode");
  if (rm) rm.value = resp.mode;
  const rewards = (resp.rewards || []).filter(r => r.reward != null);
  const cum = rewards.reduce((s, r) => s + r.reward, 0);
  const rcr = document.getElementById("resp-cum-reward");
  if (rcr) rcr.textContent = cum.toFixed(2);
  const proposed = (resp.actions || []).filter(a => a.status === "proposed");
  const count = document.getElementById("resp-count");
  if (count) {
    count.textContent = proposed.length;
    count.classList.toggle("hidden", !proposed.length);
  }

  const canvas = document.getElementById("resp-reward-chart");
  if (canvas && canvas.clientWidth) {
    const dpr = window.devicePixelRatio || 1;
    canvas.width = canvas.clientWidth * dpr; canvas.height = canvas.clientHeight * dpr;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    let acc = 0;
    const vals = rewards.map(r => (acc += r.reward));
    if (vals.length) {
      const lo = Math.min(...vals, 0), hi = Math.max(...vals, 1e-6);
      const grad = ctx.createLinearGradient(0, 0, 0, canvas.clientHeight);
      grad.addColorStop(0, C.violet + "30");
      grad.addColorStop(1, "transparent");
      ctx.beginPath();
      vals.forEach((v, i) => {
        const x = 4 + (canvas.clientWidth - 8) * i / Math.max(1, vals.length - 1);
        const y = canvas.clientHeight - 4 - (canvas.clientHeight - 16) * (v - lo) / (hi - lo || 1);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.lineTo(4 + (canvas.clientWidth - 8), canvas.clientHeight);
      ctx.lineTo(4, canvas.clientHeight); ctx.closePath();
      ctx.fillStyle = grad; ctx.fill();

      ctx.strokeStyle = C.violet; ctx.lineWidth = 1.5; ctx.beginPath();
      vals.forEach((v, i) => {
        const x = 4 + (canvas.clientWidth - 8) * i / Math.max(1, vals.length - 1);
        const y = canvas.clientHeight - 4 - (canvas.clientHeight - 16) * (v - lo) / (hi - lo || 1);
        i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
      });
      ctx.stroke();
    }
    ctx.fillStyle = C.textMuted; ctx.font = "500 9px 'Inter', sans-serif";
    ctx.fillText("cumulative reward", 4, 10);
  }

  const rlist = document.getElementById("resp-list");
  if (rlist) {
    rlist.innerHTML = (resp.actions || []).map(a => {
      const sb = a.sandbox || {};
      const pred = sb.predicted_delta != null
        ? `<span class="${sb.improves ? "improves" : "no-improve"}">sandbox: ${sb.baseline_health} → ${sb.action_health} (${sb.predicted_delta >= 0 ? "+" : ""}${sb.predicted_delta})</span>`
        : "";
      const params = Object.entries(a.params || {}).filter(([, v]) => v != null && v !== "")
        .map(([k, v]) => `${k}=${v}`).join(" ");
      const btns = a.status === "proposed"
        ? `<button data-apply="${a.id}">approve & apply</button>`
        : a.status === "applied"
          ? `<button data-revert="${a.id}">revert</button>` : "";
      const rew = a.reward != null ? ` reward ${a.reward >= 0 ? "+" : ""}${a.reward}` : "";
      return `<div class="resp-item">
        <span class="resp-status">${a.status}${rew}</span>
        <span class="rk">${a.kind}</span> <span class="rparams">${escapeHtml(params)}</span>
        <div class="rbox">${pred}</div>${btns}</div>`;
    }).join("") || `<div style="color:${C.textMuted};padding:12px;text-align:center;font-style:italic">No response actions pending. Proposals trigger on alerts.</div>`;
  }
}

const respListEl = document.getElementById("resp-list");
if (respListEl) {
  respListEl.addEventListener("click", (ev) => {
    const applyId = ev.target.dataset && ev.target.dataset.apply;
    const revertId = ev.target.dataset && ev.target.dataset.revert;
    if (applyId) {
      showToast("Applying Policy", `Actuating ${applyId}...`, "warning", 2500);
      fetch(`${API_BASE}/api/response/apply`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: applyId })
      })
      .then(r => r.json()).then(() => fetch(`${API_BASE}/api/response/recommendations`)
        .then(r => r.json()).then(d => {
          showToast("Policy Applied", `Action ${applyId} active.`, "success", 3000);
          state.response = { ...state.response, actions: d.recommendations.concat(
            (state.response.actions || []).filter(a => a.status !== "proposed")) };
          renderResponsePanel();
        }));
    }
    if (revertId) {
      showToast("Reverting Policy", `Rolling back ${revertId}...`, "info", 2000);
      fetch(`${API_BASE}/api/response/revert`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: revertId })
      }).then(() => {
        showToast("Policy Reverted", `Action ${revertId} rolled back.`, "success", 2500);
      });
    }
  });
}

const respModeSelect = document.getElementById("resp-mode");
if (respModeSelect) {
  respModeSelect.addEventListener("change", (ev) => {
    fetch(`${API_BASE}/api/response/mode`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mode: ev.target.value })
    });
    showToast("Response Mode Updated", `Bandit agent set to '${ev.target.value}' mode.`, "info", 2500);
  });
}

/* ---- AWS Cloud Traffic Streamer Controls ---- */
let cloudPollerInterval = null;

function refreshCloudTrafficStatus() {
  fetch(`${API_BASE}/api/cloud-traffic/stream/status`)
    .then(r => r.json())
    .then(d => {
      const s = d.stats || {};
      const statusEl = document.getElementById("cloud-stat-status");
      const recordsEl = document.getElementById("cloud-stat-records");
      const rateEl = document.getElementById("cloud-stat-rate");
      const attackEl = document.getElementById("cloud-stat-attack");
      const badge = document.getElementById("cloud-stream-badge");
      if (statusEl) {
        statusEl.textContent = s.is_active ? "STREAMING (LIVE)" : "IDLE";
        statusEl.style.color = s.is_active ? C.emeraldLight : C.textMuted;
      }
      if (recordsEl) recordsEl.textContent = (s.records_streamed || 0).toLocaleString();
      if (rateEl) rateEl.textContent = `${s.rate_eps || 0} eps`;
      if (attackEl) attackEl.textContent = s.current_attack_type || "None";
      if (badge) {
        badge.textContent = s.is_active ? `STREAMING: ${s.rate_eps || 0} EPS` : "0 MB LOCAL DISK";
        badge.className = "badge " + (s.is_active ? "ollama" : "fallback");
      }
      if (!s.is_active && cloudPollerInterval) {
        clearInterval(cloudPollerInterval);
        cloudPollerInterval = null;
      }
    })
    .catch(() => {});
}

const cloudStartBtn = document.getElementById("cloud-stream-start");
if (cloudStartBtn) {
  cloudStartBtn.addEventListener("click", () => {
    const dataset = document.getElementById("cloud-dataset-select")?.value || "cse2018_ddos_loic_hoic";
    const speed = parseFloat(document.getElementById("cloud-speed-select")?.value) || 5.0;
    const attackOnly = document.getElementById("cloud-attack-only")?.checked || false;

    showToast("Connecting to AWS S3", `Initiating in-memory stream for ${dataset} (0 MB disk, $0 cost)...`, "info", 3000);
    fetch(`${API_BASE}/api/cloud-traffic/stream/start`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dataset, speed, attack_only: attackOnly, sample_pct: 100.0, batch_size: 16 })
    })
    .then(r => r.json())
    .then(d => {
      showToast("AWS Cloud Stream Active", `Streaming directly from AWS Open Data (S3) at ${speed}x speed.`, "success", 3500);
      refreshCloudTrafficStatus();
      if (!cloudPollerInterval) {
        cloudPollerInterval = setInterval(refreshCloudTrafficStatus, 1000);
      }
    })
    .catch(err => {
      showToast("Stream Error", "Failed to start AWS cloud stream: " + err, "danger", 4000);
    });
  });
}

const cloudStopBtn = document.getElementById("cloud-stream-stop");
if (cloudStopBtn) {
  cloudStopBtn.addEventListener("click", () => {
    fetch(`${API_BASE}/api/cloud-traffic/stream/stop`, { method: "POST" })
      .then(r => r.json())
      .then(d => {
        const count = d.result?.records_streamed || 0;
        showToast("Stream Stopped", `AWS S3 stream terminated. Total records streamed: ${count}.`, "info", 3000);
        refreshCloudTrafficStatus();
      });
  });
}

/* ============================================================
   BOOT INITIALIZATION
   ============================================================ */
fetch(`${API_BASE}/api/health`).then(r => r.json()).then(h => {
  const badge = document.getElementById("llm-badge");
  if (badge) {
    badge.textContent = h.llm.mode === "ollama" ? `ollama: ${h.llm.model}` : "rule fallback";
    badge.className = "badge " + (h.llm.mode === "ollama" ? "ollama" : "fallback");
  }
}).catch(() => {});

// Topology switcher initialization
const topoSelect = document.getElementById("topology-select");
if (topoSelect) {
  fetch(`${API_BASE}/api/topology/list`)
    .then(r => r.json())
    .then(data => {
      if (data && data.topologies && data.topologies.length) {
        topoSelect.innerHTML = "";
        data.topologies.forEach(t => {
          const opt = document.createElement("option");
          opt.value = t.name;
          opt.textContent = `${t.name === "aws-3tier" ? "☁" : "🏢"} ${t.title} (${t.node_count} Nodes)`;
          if (t.active) opt.selected = true;
          topoSelect.appendChild(opt);
        });
      }
    })
    .catch(() => {});

  topoSelect.addEventListener("change", (ev) => {
    const topoName = ev.target.value;
    showToast("Switching Topology", `Loading ${topoName} network twin architecture...`, "info", 2500);
    fetch(`${API_BASE}/api/topology/switch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ topology_name: topoName })
    })
    .then(r => r.json())
    .then(res => {
      if (res.status === "ok") {
        showToast("Topology Activated", `Activated ${res.topology?.title || topoName} (${res.topology?.node_count || 0} nodes)`, "success", 3500);
        state.panX = 0;
        state.panY = 0;
        state.zoom = 1;
      } else {
        showToast("Switch Failed", res.detail || "Error switching topology", "danger", 3500);
      }
    })
    .catch(err => {
      showToast("Switch Error", err.message, "danger", 3500);
    });
  });
}

/* ============================================================
   ORGANIZATION NETWORK ONBOARDING & TWIN SYNTHESIS CONTROLLER
   ============================================================ */
function updateOrgTopbar(org) {
  if (!org) return;
  state.activeOrg = org;
  const nameEl = document.getElementById("topbar-org-name");
  const vpcEl = document.getElementById("topbar-org-vpc");
  const syncEl = document.getElementById("topbar-org-sync");
  if (nameEl) nameEl.textContent = org.org_name || "Enterprise Cloud";
  if (vpcEl) vpcEl.textContent = `VPC: ${org.vpc_id || "vpc-prod"}`;
  if (syncEl) syncEl.textContent = `SYNC ${org.sync_status === "SYNCHRONIZED" ? "99.4%" : "100%"}`;
}

function openOrgModal() {
  const modal = document.getElementById("org-modal");
  if (modal) modal.classList.remove("hidden");
}

function closeOrgModal() {
  const modal = document.getElementById("org-modal");
  if (modal) modal.classList.add("hidden");
}

// Tab navigation in modal
document.querySelectorAll(".modal-tabs .tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".modal-tabs .tab-btn").forEach(b => b.classList.remove("active"));
    document.querySelectorAll(".modal-body .tab-content").forEach(tc => tc.classList.remove("active"));
    btn.classList.add("active");
    const targetId = btn.dataset.tab;
    const targetContent = document.getElementById(targetId);
    if (targetContent) targetContent.classList.add("active");
  });
});

// Profile cards selection in Tab 3
document.querySelectorAll(".profile-card").forEach(card => {
  card.addEventListener("click", () => {
    document.querySelectorAll(".profile-card").forEach(c => c.classList.remove("selected"));
    card.classList.add("selected");
  });
});

// Modal open/close listeners
const reconnectBtn = document.getElementById("reconnect-org-btn");
if (reconnectBtn) {
  reconnectBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    openOrgModal();
  });
}

const orgBadgeContainer = document.getElementById("org-badge-container");
if (orgBadgeContainer) {
  orgBadgeContainer.addEventListener("click", openOrgModal);
}

const orgModalClose = document.getElementById("org-modal-close");
if (orgModalClose) orgModalClose.addEventListener("click", closeOrgModal);

const orgCancelBtn = document.getElementById("org-cancel-btn");
if (orgCancelBtn) orgCancelBtn.addEventListener("click", closeOrgModal);

// Synthesis Animation & Connection Dispatcher
async function runDigitalTwinSynthesis(payload) {
  const overlay = document.getElementById("org-synthesis-overlay");
  const subTitle = document.getElementById("synthesis-subtitle");
  if (overlay) overlay.classList.remove("hidden");

  const steps = ["step-auth", "step-discover", "step-topology", "step-conformal", "step-online"];
  steps.forEach(s => {
    const el = document.getElementById(s);
    if (el) { el.classList.remove("active", "done"); }
  });

  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  // Step 1: Auth & Handshake
  const s1 = document.getElementById("step-auth");
  if (s1) s1.classList.add("active");
  if (subTitle) subTitle.textContent = `Establishing cryptographic handshake with ${payload.org_name}...`;
  await sleep(350);
  if (s1) { s1.classList.remove("active"); s1.classList.add("done"); }

  // Step 2: Discovering Subnets & Gateways
  const s2 = document.getElementById("step-discover");
  if (s2) s2.classList.add("active");
  if (subTitle) subTitle.textContent = `Discovering subnets and instances in VPC ${payload.vpc_id || "10.0.0.0/16"}...`;
  await sleep(380);
  if (s2) { s2.classList.remove("active"); s2.classList.add("done"); }

  // Step 3: Graph Topology Synthesis
  const s3 = document.getElementById("step-topology");
  if (s3) s3.classList.add("active");
  if (subTitle) subTitle.textContent = "Synthesizing graph topology and routing matrix...";
  
  // Call backend API in parallel with animation
  let resData = null;
  try {
    const res = await fetch(`${API_BASE}/api/org/connect`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    resData = await res.json();
  } catch (err) {
    console.error("Org connect error:", err);
  }

  await sleep(360);
  if (s3) { s3.classList.remove("active"); s3.classList.add("done"); }

  // Step 4: Calibrating Conformal Prediction Interval Baselines
  const s4 = document.getElementById("step-conformal");
  if (s4) s4.classList.add("active");
  if (subTitle) subTitle.textContent = "Calibrating conformal anomaly thresholds and empirical traffic distribution...";
  await sleep(400);
  if (s4) { s4.classList.remove("active"); s4.classList.add("done"); }

  // Step 5: Digital Twin Online
  const s5 = document.getElementById("step-online");
  if (s5) s5.classList.add("active", "done");
  if (subTitle) subTitle.textContent = `Digital Twin synchronized for ${payload.org_name}!`;
  await sleep(300);

  if (resData && resData.organization) {
    updateOrgTopbar(resData.organization);
    try { localStorage.setItem("nettwin_org", JSON.stringify(resData.organization)); } catch(e) {}
  } else {
    updateOrgTopbar(payload);
    try { localStorage.setItem("nettwin_org", JSON.stringify(payload)); } catch(e) {}
  }

  showToast("Digital Twin Synthesized", `Active Organization: ${payload.org_name} (${payload.topology_name || "aws-3tier"})`, "success", 4000);

  if (overlay) overlay.classList.add("hidden");
  closeOrgModal();

  // Reset viewport to center topology
  state.panX = 0; state.panY = 0; state.zoom = 1;
}

// Submit Button Handler
const orgSubmitBtn = document.getElementById("org-submit-btn");
if (orgSubmitBtn) {
  orgSubmitBtn.addEventListener("click", () => {
    const activeTab = document.querySelector(".modal-tabs .tab-btn.active")?.dataset.tab;
    let payload = {};

    if (activeTab === "tab-aws") {
      payload = {
        org_name: document.getElementById("org-aws-name")?.value || "Acme Financial Corp",
        environment: document.getElementById("org-aws-env")?.value || "AWS Production (us-east-1)",
        vpc_id: document.getElementById("org-aws-vpc")?.value || "vpc-07b94a12ec8",
        cidr: document.getElementById("org-aws-cidr")?.value || "10.0.0.0/16",
        region: document.getElementById("org-aws-region")?.value || "us-east-1",
        ingest_mode: "aws_vpc_mirror",
        topology_name: "aws-3tier",
      };
    } else if (activeTab === "tab-live") {
      payload = {
        org_name: document.getElementById("org-live-name")?.value || "Global Data Center",
        environment: "Enterprise On-Premises",
        vpc_id: "lan-core-01",
        cidr: "10.0.1.0/24",
        region: "datacenter",
        ingest_mode: "live_agent",
        topology_name: "default",
      };
    } else if (activeTab === "tab-profiles") {
      const selectedProfile = document.querySelector(".profile-card.selected")?.dataset.profile || "aws-3tier";
      if (selectedProfile === "aws-3tier") {
        payload = {
          org_name: "Acme Cloud Architecture",
          environment: "AWS Production (us-east-1)",
          vpc_id: "vpc-07b94a12ec8",
          cidr: "10.0.0.0/16",
          region: "us-east-1",
          ingest_mode: "aws_vpc_mirror",
          topology_name: "aws-3tier",
        };
      } else if (selectedProfile === "fintech-zero-trust") {
        payload = {
          org_name: "FinTech Banking Enclave",
          environment: "AWS Zero-Trust VPC",
          vpc_id: "vpc-0bf45819ad3",
          cidr: "10.200.0.0/16",
          region: "us-east-1",
          ingest_mode: "aws_vpc_mirror",
          topology_name: "aws-3tier",
        };
      } else {
        payload = {
          org_name: "Enterprise Campus Network",
          environment: "Campus Backbone Infrastructure",
          vpc_id: "lan-backbone-01",
          cidr: "172.16.0.0/16",
          region: "campus",
          ingest_mode: "live_agent",
          topology_name: "default",
        };
      }
    } else if (activeTab === "tab-upload") {
      payload = {
        org_name: "Custom Infrastructure Twin",
        environment: "Uploaded Custom Topology",
        vpc_id: "custom-vpc-01",
        cidr: "10.0.0.0/16",
        region: "custom",
        ingest_mode: "config_upload",
        topology_name: "aws-3tier",
      };
    }

    runDigitalTwinSynthesis(payload);
  });
}

// Quick Demo Connect Button
const orgQuickConnectBtn = document.getElementById("org-quick-connect-btn");
if (orgQuickConnectBtn) {
  orgQuickConnectBtn.addEventListener("click", () => {
    runDigitalTwinSynthesis({
      org_name: "Acme Financial Corp",
      environment: "AWS Production (us-east-1)",
      vpc_id: "vpc-07b94a12ec8",
      cidr: "10.0.0.0/16",
      region: "us-east-1",
      ingest_mode: "aws_vpc_mirror",
      topology_name: "aws-3tier",
    });
  });
}

// Organization current state initialization
fetch(`${API_BASE}/api/org/current`)
  .then(r => r.json())
  .then(d => {
    if (d && d.organization) {
      updateOrgTopbar(d.organization);
    }
  })
  .catch(() => {});

// First-time onboarding trigger: if no organization stored in localStorage, open modal
try {
  const savedOrg = localStorage.getItem("nettwin_org");
  if (!savedOrg) {
    setTimeout(openOrgModal, 500);
  }
} catch (e) {}

// Launch system
connect();
requestAnimationFrame(loop);
