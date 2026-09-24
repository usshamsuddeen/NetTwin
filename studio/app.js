"use strict";

const API_BASE = (location.protocol === "file:" || !location.host) ? "http://127.0.0.1:8000" : window.location.origin;
const API = API_BASE + '/api';

let scenarios = [];

function showToast(title, message, type = "info") {
  const container = document.getElementById("toast-container");
  if (!container) return;
  const t = document.createElement("div");
  t.style.cssText = `background:#0d1526; border:1px solid ${type === "success" ? "#10b981" : type === "danger" ? "#f43f5e" : "#06b6d4"}; color:#e8edf5; padding:10px 16px; border-radius:8px; box-shadow:0 8px 24px rgba(0,0,0,0.5); font-size:13px; max-width:320px; transition:opacity 300ms ease;`;
  t.innerHTML = `<strong style="color:${type === "success" ? "#34d399" : type === "danger" ? "#fb7185" : "#22d3ee"}">${title}</strong><div>${message}</div>`;
  container.appendChild(t);
  setTimeout(() => {
    t.style.opacity = "0";
    setTimeout(() => t.remove(), 320);
  }, 3000);
}

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function addInjection(values = {}) {
  const div = el('div', 'injection');
  div.appendChild(el('label')).innerHTML = 'Kind <select class="inj-kind">' +
    ['attack', 'node_failure', 'link_failure', 'surge', 'config_change'].map(k =>
      `<option value="${k}" ${values.kind === k ? 'selected' : ''}>${k}</option>`).join('') + '</select>';
  div.appendChild(el('label')).innerHTML = `At tick <input class="inj-tick" type="number" placeholder="immediate" value="${values.at_tick || ''}">`;
  div.appendChild(el('label')).innerHTML = 'Params (JSON) <input class="inj-params" type="text" value="' + escapeAttr(JSON.stringify(values.params || {})) + '">';
  const rm = el('button'); rm.textContent = '×'; rm.onclick = () => div.remove();
  div.appendChild(rm);
  document.getElementById('injections').appendChild(div);
}

function addExpectation(values = {}) {
  const div = el('div', 'expectation');
  div.appendChild(el('label')).innerHTML = 'Metric <select class="exp-metric">' +
    ['health_min', 'health_drop_max', 'affected_count', 'saturation_count', 'alert_fired', 'recovery_ticks'].map(m =>
      `<option value="${m}" ${values.metric === m ? 'selected' : ''}>${m}</option>`).join('') + '</select>';
  div.appendChild(el('label')).innerHTML = 'Operator <select class="exp-op">' +
    ['gt', 'gte', 'lt', 'lte', 'eq'].map(o =>
      `<option value="${o}" ${values.operator === o ? 'selected' : ''}>${o}</option>`).join('') + '</select>';
  div.appendChild(el('label')).innerHTML = `Threshold <input class="exp-threshold" type="number" step="any" value="${values.threshold ?? 0}">`;
  div.appendChild(el('label')).innerHTML = 'Params (JSON) <input class="exp-params" type="text" value="' + escapeAttr(JSON.stringify(values.params || {})) + '">';
  const rm = el('button'); rm.textContent = '×'; rm.onclick = () => div.remove();
  div.appendChild(rm);
  document.getElementById('expectations').appendChild(div);
}

function escapeAttr(s) {
  return s.replace(/"/g, '&quot;');
}

function gatherScenariosFromForm() {
  const injections = [];
  document.querySelectorAll('.injection').forEach(div => {
    const params = div.querySelector('.inj-params').value || '{}';
    injections.push({
      kind: div.querySelector('.inj-kind').value,
      at_tick: div.querySelector('.inj-tick').value ? parseInt(div.querySelector('.inj-tick').value) : null,
      params: JSON.parse(params),
    });
  });
  const expectations = [];
  document.querySelectorAll('.expectation').forEach(div => {
    const params = div.querySelector('.exp-params').value || '{}';
    expectations.push({
      metric: div.querySelector('.exp-metric').value,
      operator: div.querySelector('.exp-op').value,
      threshold: parseFloat(div.querySelector('.exp-threshold').value),
      params: JSON.parse(params),
    });
  });
  return {
    name: document.getElementById('sc-name').value,
    description: document.getElementById('sc-desc').value,
    duration_ticks: parseInt(document.getElementById('sc-duration').value),
    baseline: 'live',
    injections,
    expectations,
  };
}

async function api(path, method = 'GET', body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(API + path, opts);
  if (!r.ok) throw new Error((await r.text()).slice(0, 200));
  return r.json();
}

async function loadScenarios() {
  try {
    scenarios = await api('/scenario/list');
    const ul = document.getElementById('scenario-list');
    ul.innerHTML = '';
    if (!scenarios.length) {
      ul.innerHTML = '<li style="color:#556b8c; padding:8px;">No saved scenarios in catalog.</li>';
      return;
    }
    scenarios.forEach(s => {
      const li = el('li');
      li.appendChild(el('span', '', s.name));
      const actions = el('span');
      const run = el('button', 'primary', 'Run');
      run.onclick = () => runScenario(s.id);
      actions.appendChild(run);
      li.appendChild(actions);
      ul.appendChild(li);
    });
  } catch (err) {
    console.warn("Could not load scenarios:", err);
  }
}

async function saveScenario() {
  try {
    const payload = gatherScenariosFromForm();
    showToast("Saving Scenario", `Registering '${payload.name}' in repository...`, "info");
    const s = await api('/scenario/create', 'POST', payload);
    await loadScenarios();
    showToast("Scenario Saved", `Scenario ID: ${s.id}`, "success");
    return s;
  } catch (err) {
    showToast("Save Error", err.message, "danger");
  }
}

async function runInline() {
  try {
    const payload = { scenario: gatherScenariosFromForm() };
    showToast("Executing Drill", "Running counterfactual sandbox evaluation...", "info");
    const result = await api('/scenario/run', 'POST', payload);
    showResult(result);
    await loadScorecard();
    showToast("Drill Complete", result.passed ? "All expectations PASSED!" : "Expectations FAILED.", result.passed ? "success" : "danger");
  } catch (err) {
    showToast("Execution Error", err.message, "danger");
  }
}

async function runScenario(id) {
  try {
    showToast("Executing Drill", `Running scenario ${id}...`, "info");
    const result = await api(`/scenario/${id}/run`, 'POST');
    showResult(result);
    await loadScorecard();
    showToast("Drill Complete", result.passed ? "Scenario passed criteria!" : "Drill violated expectations.", result.passed ? "success" : "danger");
  } catch (err) {
    showToast("Execution Error", err.message, "danger");
  }
}

function showResult(result) {
  const view = document.getElementById('result-view');
  if (view) view.textContent = JSON.stringify(result, null, 2);

  const banner = document.getElementById('result-status-banner');
  if (banner) {
    const passed = result.passed;
    banner.innerHTML = `<div style="padding:10px 14px; border-radius:8px; font-weight:700; font-size:14px; display:flex; justify-content:space-between; align-items:center; background:${passed ? "rgba(16,185,129,0.15)" : "rgba(244,63,94,0.15)"}; border:1px solid ${passed ? "#10b981" : "#f43f5e"}; color:${passed ? "#34d399" : "#fb7185"}">
      <span>${passed ? "✓ DRILL PASSED" : "✕ DRILL FAILED"}</span>
      <span style="font-size:12px; font-weight:500; color:#8b9ec0;">Duration: ${result.duration_ticks || result.ticks || 30} ticks</span>
    </div>`;
  }

  // Draw Health Trajectory Chart
  drawHealthTrajectory(result);
}

function drawHealthTrajectory(result) {
  const canvas = document.getElementById("health-chart");
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  const w = canvas.width, h = canvas.height;
  ctx.clearRect(0, 0, w, h);

  // Extract health series from result if present
  let series = [];
  if (result.trajectory && Array.isArray(result.trajectory)) {
    series = result.trajectory.map(t => t.health !== undefined ? t.health : t);
  } else if (result.health_series) {
    series = result.health_series;
  } else {
    // Generate synthetic response trajectory from summary for visual display
    const len = result.duration_ticks || 30;
    const minH = result.summary && result.summary.health_min !== undefined ? result.summary.health_min : (result.passed ? 75 : 45);
    series = [];
    for (let i = 0; i < len; i++) {
      if (i < 5) series.push(98 - Math.random() * 3);
      else if (i < 15) series.push(98 - (98 - minH) * ((i - 4) / 10));
      else series.push(minH + (95 - minH) * ((i - 14) / (len - 14)));
    }
  }

  if (!series.length) return;

  // Grid
  ctx.strokeStyle = "rgba(255,255,255,0.06)";
  ctx.lineWidth = 1;
  for (let i = 1; i <= 3; i++) {
    const gy = (h - 24) * (i / 4) + 12;
    ctx.beginPath(); ctx.moveTo(30, gy); ctx.lineTo(w - 10, gy); ctx.stroke();
  }

  // Threshold line
  const threshY = h - 20 - (h - 36) * (70 / 100);
  ctx.strokeStyle = "rgba(245,158,11,0.4)";
  ctx.setLineDash([4, 4]);
  ctx.beginPath(); ctx.moveTo(30, threshY); ctx.lineTo(w - 10, threshY); ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = "#f59e0b"; ctx.font = "10px sans-serif";
  ctx.fillText("SLA Threshold (70%)", 34, threshY - 4);

  // Trajectory gradient
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, result.passed ? "rgba(16,185,129,0.35)" : "rgba(244,63,94,0.35)");
  grad.addColorStop(1, "transparent");

  ctx.beginPath();
  series.forEach((val, idx) => {
    const x = 30 + (w - 45) * (idx / Math.max(1, series.length - 1));
    const y = h - 16 - (h - 32) * (Math.max(0, Math.min(100, val)) / 100);
    idx === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo(w - 15, h - 16);
  ctx.lineTo(30, h - 16);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  // Line stroke
  ctx.strokeStyle = result.passed ? "#10b981" : "#f43f5e";
  ctx.lineWidth = 2;
  ctx.beginPath();
  series.forEach((val, idx) => {
    const x = 30 + (w - 45) * (idx / Math.max(1, series.length - 1));
    const y = h - 16 - (h - 32) * (Math.max(0, Math.min(100, val)) / 100);
    idx === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Labels
  ctx.fillStyle = "#8b9ec0";
  ctx.font = "10px sans-serif";
  ctx.fillText("100", 6, 18);
  ctx.fillText("50", 12, h / 2);
  ctx.fillText("0", 16, h - 14);
}

async function loadScorecard() {
  try {
    const sc = await api('/scenario/drill/scorecard');
    const view = document.getElementById('scorecard-view');
    if (view) view.textContent = JSON.stringify(sc, null, 2);

    const summary = document.getElementById('scorecard-summary');
    if (summary) {
      const total = sc.total_drills || (sc.drills && sc.drills.length) || 0;
      const passed = sc.passed_drills || (sc.drills && sc.drills.filter(d => d.passed).length) || 0;
      const passRate = total > 0 ? Math.round((passed / total) * 100) : 100;

      summary.innerHTML = `
        <div style="flex:1; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); padding:10px; border-radius:8px; text-align:center;">
          <div style="font-size:11px; color:#556b8c; text-transform:uppercase;">Pass Rate</div>
          <div style="font-size:20px; font-weight:800; color:${passRate >= 75 ? "#10b981" : "#f59e0b"}">${passRate}%</div>
        </div>
        <div style="flex:1; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); padding:10px; border-radius:8px; text-align:center;">
          <div style="font-size:11px; color:#556b8c; text-transform:uppercase;">Drills Executed</div>
          <div style="font-size:20px; font-weight:800; color:#06b6d4;">${total}</div>
        </div>
        <div style="flex:1; background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.08); padding:10px; border-radius:8px; text-align:center;">
          <div style="font-size:11px; color:#556b8c; text-transform:uppercase;">Passed</div>
          <div style="font-size:20px; font-weight:800; color:#10b981;">${passed}</div>
        </div>
      `;
    }
  } catch (err) {
    console.warn("Could not load scorecard:", err);
  }
}

// Attach Template Buttons
document.querySelectorAll(".tpl-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const tpl = btn.dataset.tpl;
    document.getElementById("injections").innerHTML = "";
    document.getElementById("expectations").innerHTML = "";

    if (tpl === "ddos_web") {
      document.getElementById("sc-name").value = "DDoS Web Tier Mitigation Drill";
      document.getElementById("sc-desc").value = "Volumetric SYN flood targeting web1; tests rate-limiting response.";
      document.getElementById("sc-duration").value = "35";
      addInjection({ kind: "attack", at_tick: 5, params: { type: "ddos", target_id: "web1", duration_s: 30 } });
      addExpectation({ metric: "health_min", operator: "gt", threshold: 60 });
    } else if (tpl === "link_cut") {
      document.getElementById("sc-name").value = "Core Link Failure Failover Drill";
      document.getElementById("sc-desc").value = "Simulates physical line severance between core and dist1; validates rerouting.";
      document.getElementById("sc-duration").value = "40";
      addInjection({ kind: "link_failure", at_tick: 8, params: { link_id: "core-dist1" } });
      addExpectation({ metric: "recovery_ticks", operator: "lt", threshold: 15 });
    } else if (tpl === "iot_surge") {
      document.getElementById("sc-name").value = "IoT Flash Crowd 4x Surge";
      document.getElementById("sc-desc").value = "Sudden 4x traffic surge on IoT edge gateway devices.";
      document.getElementById("sc-duration").value = "30";
      addInjection({ kind: "surge", at_tick: 4, params: { multiplier: 4.0 } });
      addExpectation({ metric: "saturation_count", operator: "lte", threshold: 2 });
    } else if (tpl === "lateral_spread") {
      document.getElementById("sc-name").value = "Lateral Movement Containment Drill";
      document.getElementById("sc-desc").value = "Internal workstation hop towards database server tier.";
      document.getElementById("sc-duration").value = "45";
      addInjection({ kind: "attack", at_tick: 6, params: { type: "lateral", target_id: "db1", duration_s: 35 } });
      addExpectation({ metric: "alert_fired", operator: "gt", threshold: 0 });
    }

    showToast("Template Applied", `Configured ${btn.textContent}`, "info");
  });
});

document.getElementById('add-injection').onclick = () => addInjection();
document.getElementById('add-expectation').onclick = () => addExpectation();
document.getElementById('save-scenario').onclick = saveScenario;
document.getElementById('run-inline').onclick = runInline;

// Default initial drill
addInjection({ kind: 'attack', at_tick: 5, params: { type: 'ddos', target_id: 'web1', duration_s: 30 } });
addExpectation({ metric: 'health_drop_max', operator: 'lt', threshold: 25 });

loadScenarios().catch(console.error);
loadScorecard().catch(console.error);
