"""SecurityAnalyst: LLM-backed analyst with rule-based fallback."""
from __future__ import annotations

import json
import logging
import time
from typing import Any

from nettwin.config import Settings
from nettwin.llm.providers import OllamaProvider, build_provider
from nettwin.models import AnalystAnswer

from .kb import KnowledgeBase
from .prompts import SYSTEM_PROMPT

log = logging.getLogger("nettwin.llm.analyst")

_MITRE = {
    "ddos": ("T1498", "Network Denial of Service"),
    "portscan": ("T1046", "Network Service Discovery"),
    "exfiltration": ("T1041", "Exfiltration Over C2 Channel"),
    "lateral": ("T1021", "Remote Services (lateral movement)"),
    "bruteforce": ("T1110", "Brute Force"),
}


class SecurityAnalyst:
    def __init__(self, settings: Settings, app_state: Any) -> None:
        self.s = settings.llm
        self.state = app_state  # object with .twin, .detector, .alerts, .engine
        self.kb = KnowledgeBase(settings)
        self.provider = build_provider(settings, settings.aws.region)
        self._history: dict[str, list[dict[str, str]]] = {}

    # ---- provider plumbing -------------------------------------------------
    async def available(self) -> bool:
        return await self.provider.available()

    def _session_history(self, session_id: str = "default") -> list[dict[str, str]]:
        return self._history.setdefault(session_id, [])

    async def build_context(self) -> dict[str, Any]:
        twin = self.state.twin
        det = self.state.detector
        alerts = self.state.alerts
        engine = self.state.engine
        scored = sorted(det.scores.items(), key=lambda kv: kv[1], reverse=True)
        anomalies = []
        for entity_id, score in scored[:8]:
            if score < 0.3:
                break
            sig = det.signals.get(entity_id, {})
            anomalies.append({"entity": entity_id, "score": round(score, 2),
                              "top_metric": sig.get("top_metric"),
                              "metrics": sig.get("metrics", {})})
        evidence_text = " ".join(
            [a.get("top_metric") or "" for a in anomalies]
            + [atk.get("attack_type", "") for atk in
               [a.event.model_dump() for a in engine.attacks.values()]]
            + [al.get("message", "") for al in [x.model_dump() for x in alerts.active()[:5]]])
        techniques = await self.kb.retrieve(evidence_text + " " + "network security", k=3)
        return {
            "tick": engine.tick,
            "network_health": twin.network_health,
            "kpis": twin.kpis.model_dump(),
            "top_anomalies": anomalies,
            "active_alerts": [a.model_dump() for a in alerts.active()[:10]],
            "active_attacks": [a.event.model_dump() for a in engine.attacks.values()],
            "techniques": techniques,
        }

    # ---- main entry --------------------------------------------------------
    async def ask(self, question: str, session_id: str = "default") -> AnalystAnswer:
        started = time.time()
        context = await self.build_context()
        history = self._session_history(session_id)
        if await self.available():
            try:
                recent = "\n".join(
                    f"Q: {h['q']}\nA: {h['a']}" for h in history[-self.s.conversation_history:])
                prompt = (f"Context:\n{json.dumps(context, indent=1)[:6000]}\n\n"
                          f"Recent conversation:\n{recent}\n\n"
                          f"Operator question: {question}")
                answer = await self.provider.generate(prompt, system=SYSTEM_PROMPT)
                if answer:
                    history.append({"q": question, "a": answer})
                    mode = self.provider.__class__.__name__.lower().replace("provider", "")
                    model = self.s.model if isinstance(self.provider, OllamaProvider) else self.s.bedrock_model
                    return AnalystAnswer(mode=mode, model=model, answer=answer,
                                         context_used=context,
                                         elapsed_s=round(time.time() - started, 2))
            except Exception:
                log.exception("llm generate failed")
        answer = RuleBasedAnalyst().answer(question, context)
        return AnalystAnswer(mode="fallback", model="rule-based",
                             answer=answer, context_used=context,
                             elapsed_s=round(time.time() - started, 2))


class RuleBasedAnalyst:
    """Structured, evidence-driven analysis without an LLM."""

    def answer(self, question: str, ctx: dict[str, Any]) -> str:
        anomalies = ctx.get("top_anomalies", [])
        alerts = ctx.get("active_alerts", [])
        attacks = ctx.get("active_attacks", [])
        health = ctx.get("network_health", 100.0)
        kpis = ctx.get("kpis", {})
        lines: list[str] = []

        q = question.lower()
        lines.append("## Incident summary")
        if not anomalies and not attacks:
            lines.append(
                f"No active anomalies detected. Network health is **{health:.0f}/100** "
                f"with {kpis.get('total_throughput_mbps', 0):.0f} Mbps aggregate throughput, "
                f"{kpis.get('avg_latency_ms', 0):.1f} ms average link latency and "
                f"{kpis.get('avg_loss_pct', 0):.2f}% average loss.")
            lines.append("\n## Watch items")
            lines.append("- Baselines are within normal range; continue monitoring diurnal load ramps.")
            if "forecast" in q or "capacity" in q:
                lines.append(f"- Forecast: max link utilization is "
                             f"{kpis.get('max_link_util_pct', 0):.0f}%; no saturation projected.")
            return "\n".join(lines)

        guess, evidence = self._classify(anomalies, attacks)
        sev = "CRITICAL" if any(a.get("severity") == "critical" for a in alerts) else "WARNING"
        lines.append(f"Severity: **{sev}** | Network health **{health:.0f}/100** | "
                     f"Anomalous entities: {len(anomalies)} | Active alerts: {len(alerts)}")
        for atk in attacks:
            lines.append(f"- Simulator attack active: `{atk['attack_type']}` "
                         f"targeting `{atk.get('target_id')}`")

        lines.append("\n## Assessment (likely attack type)")
        lines.append(f"**{guess}**")
        for e in evidence:
            lines.append(f"- {e}")

        lines.append("\n## Blast radius")
        affected = [a["entity"] for a in anomalies[:6]]
        lines.append(f"- Affected entities: {', '.join(f'`{e}`' for e in affected)}")
        lines.append(f"- Max link utilization: {kpis.get('max_link_util_pct', 0):.0f}%, "
                     f"avg loss {kpis.get('avg_loss_pct', 0):.2f}%")

        lines.append("\n## Recommended actions")
        for rec in self._mitigations(guess, anomalies):
            lines.append(f"- {rec}")

        lines.append("\n## MITRE ATT&CK")
        for key, (tid, name) in _MITRE.items():
            if key in guess.lower():
                lines.append(f"- **{tid}** - {name}")
        for tech in ctx.get("techniques", []):
            if not any(tid == tech["id"] for tid, _ in _MITRE.values()):
                lines.append(f"- **{tech['id']}** - {tech['name']} (retrieved, score {tech['score']})")
        lines.append("\n*Analysis by rule-based fallback (Ollama not reachable). "
                     "Install Ollama and `ollama pull llama3.2` for LLM-powered answers.*")
        return "\n".join(lines)

    def _classify(self, anomalies: list[dict[str, Any]],
                  attacks: list[dict[str, Any]]) -> tuple[str, list[str]]:
        evidence: list[str] = []
        metrics = {a.get("top_metric") for a in anomalies}
        if attacks:
            kind = attacks[0]["attack_type"]
            label = {"ddos": "Distributed Denial of Service (volumetric flood)",
                     "portscan": "Port scan / network reconnaissance",
                     "exfiltration": "Data exfiltration",
                     "lateral": "Lateral movement",
                     "bruteforce": "Brute-force authentication attack"}.get(kind, kind)
            evidence.append(f"Active attack event of type `{kind}` in the twin.")
        elif "fanout" in metrics:
            label = "Port scan / reconnaissance"
            evidence.append("High connection fanout with tiny flows from a single source.")
        elif "bytes_ratio" in metrics:
            label = "Data exfiltration"
            evidence.append("Server egress/ingress byte ratio shifted toward sustained upload.")
        elif "pps" in metrics:
            label = "Brute force or packet-rate flood"
            evidence.append("Packet rate far above baseline with small payloads.")
        elif "utilization_pct" in metrics or "throughput_mbps" in metrics:
            label = "Volumetric DDoS flood"
            evidence.append("Throughput / link utilization saturating above capacity.")
        else:
            label = "Unclassified anomaly"
            evidence.append("Metric deviation from adaptive baseline detected.")
        for a in anomalies[:4]:
            m = a.get("metrics", {})
            evidence.append(
                f"`{a['entity']}` score {a['score']:.2f} - "
                f"{m.get('throughput_mbps', 0):.1f} Mbps, {m.get('pps', 0):.0f} pps, "
                f"loss {m.get('packet_loss_pct', 0):.2f}%, fanout {m.get('fanout', '-')}")
        return label, evidence

    def _mitigations(self, guess: str, anomalies: list[dict[str, Any]]) -> list[str]:
        g = guess.lower()
        top = anomalies[0]["entity"] if anomalies else "the affected entity"
        if "ddos" in g or "flood" in g:
            return [f"Rate-limit or blackhole ingress traffic toward {top} at the perimeter (fw1/igw).",
                    "Enable upstream scrubbing / anycast absorption; verify CDN offload.",
                    "Review bandwidth headroom on saturated links from the saturation timeline."]
        if "scan" in g or "recon" in g:
            return ["Block the scanning source at the perimeter firewall.",
                    "Alert on fanout > threshold per source; tighten east-west ACLs.",
                    "Check whether the scan preceded any connection from scanned hosts."]
        if "exfil" in g:
            return [f"Isolate {top} from outbound internet pending forensic capture.",
                    "Inspect TLS destinations and DLP logs for the egress window.",
                    "Rotate credentials and keys stored on the affected server."]
        if "lateral" in g:
            return [f"Quarantine {top} and reset credentials used on it.",
                    "Audit SMB/SSH admin paths between internal hosts.",
                    "Hunt for the initial compromise vector on the first host in the chain."]
        if "brute" in g:
            return ["Enforce SSH key-only auth and rate-limit auth attempts (fail2ban).",
                    "Block the source IP at fw1; review auth logs for successful logins.",
                    "Enable MFA on all remote-access services."]
        return ["Investigate the top-scoring entity; capture packets for confirmation.",
                "Correlate with change windows before treating as hostile."]
