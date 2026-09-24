"""MITRE ATT&CK knowledge base with embedding vector similarity + TF-IDF fallback."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np

from nettwin.llm.embeddings import build_embedder

TECHNIQUES: list[dict[str, str]] = [
    {"id": "T1498", "name": "Network Denial of Service",
     "text": "volumetric ddos flood udp amplification saturate bandwidth link utilization loss mitigation rate limit blackhole scrubbing upstream"},
    {"id": "T1499", "name": "Endpoint Denial of Service",
     "text": "resource exhaustion service crash flood cpu memory mitigation restart service resource limits"},
    {"id": "T1046", "name": "Network Service Discovery",
     "text": "port scan sweep enumeration syn tiny packets fanout reconnaissance mitigation block source ids fanout threshold segmentation"},
    {"id": "T1041", "name": "Exfiltration Over C2 Channel",
     "text": "data exfiltration sustained egress upload bytes ratio server outbound tls mitigation dlp isolate rotate credentials block destination"},
    {"id": "T1048", "name": "Exfiltration Over Alternative Protocol",
     "text": "exfiltration dns icmp alternative protocol tunneling mitigation inspect dns payload length egress filtering"},
    {"id": "T1021", "name": "Remote Services",
     "text": "lateral movement ssh smb rdp winrm internal host to host compromise chain mitigation segment audit admin paths mfa"},
    {"id": "T1021.004", "name": "Remote Services: SSH",
     "text": "ssh lateral movement remote login key mitigation key-only auth disable password"},
    {"id": "T1110", "name": "Brute Force",
     "text": "brute force password guessing repeated authentication attempts ssh small flows mitigation fail2ban lockout mfa rate limit auth"},
    {"id": "T1110.001", "name": "Password Guessing",
     "text": "password guessing credential attack login failures mitigation lockout policy mfa"},
    {"id": "T1071", "name": "Application Layer Protocol",
     "text": "c2 command control beacon http https tls periodic small connections mitigation egress proxy detect beaconing interval"},
    {"id": "T1071.001", "name": "Web Protocols",
     "text": "c2 over http https web beacon mitigation tls inspection domain reputation"},
    {"id": "T1572", "name": "Protocol Tunneling",
     "text": "tunneling ssh dns encapsulation covert channel mitigation protocol inspection"},
    {"id": "T1190", "name": "Exploit Public-Facing Application",
     "text": "exploit web server public facing vulnerability injection mitigation patch waf"},
    {"id": "T1133", "name": "External Remote Services",
     "text": "external remote services vpn initial access mitigation mfa patch gateway"},
    {"id": "T1059", "name": "Command and Scripting Interpreter",
     "text": "command execution shell script powershell mitigation logging constrained language mode"},
    {"id": "T1055", "name": "Process Injection",
     "text": "process injection dll memory mitigation edr code integrity"},
    {"id": "T1078", "name": "Valid Accounts",
     "text": "valid accounts stolen credentials login anomaly mitigation conditional access impossible travel"},
    {"id": "T1098", "name": "Account Manipulation",
     "text": "account manipulation persistence privilege mitigation audit privilege changes"},
    {"id": "T1485", "name": "Data Destruction",
     "text": "data destruction wiper delete mitigation backup immutable snapshots"},
    {"id": "T1490", "name": "Inhibit System Recovery",
     "text": "delete backup shadow copies ransomware recovery mitigation offline backup"},
    {"id": "T1486", "name": "Data Encrypted for Impact",
     "text": "ransomware encrypt files smb spread mitigation segmentation backup edr"},
    {"id": "T1567", "name": "Exfiltration Over Web Service",
     "text": "exfiltration cloud storage web service upload mitigation cloud dlp block unsanctioned"},
    {"id": "T1557", "name": "Adversary-in-the-Middle",
     "text": "man in the middle arp spoofing interception mitigation arp inspection tls pinning"},
    {"id": "T1200", "name": "Hardware Additions",
     "text": "rogue device hardware raspberry pi network access mitigation nac 802.1x"},
    {"id": "T1095", "name": "Non-Application Layer Protocol",
     "text": "c2 icmp raw socket non-application protocol mitigation icmp filtering ids"},
    {"id": "T1105", "name": "Ingress Tool Transfer",
     "text": "download tool malware transfer http mitigation egress filtering application allowlist"},
    {"id": "T1219", "name": "Remote Access Software",
     "text": "remote access tools teamviewer anydesk unauthorized mitigation block unauthorized rmm"},
]

_TOKEN = re.compile(r"[a-z0-9.]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _cosine_similarity(query: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return matrix @ query


def _load_kb(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data if isinstance(data, list) else data.get("techniques", [])


class KnowledgeBase:
    """Hybrid KB: dense embeddings when available, TF-IDF otherwise."""

    def __init__(self, settings: Any | None = None,
                 data_dir: str | Path = "data") -> None:
        self._settings = settings
        self._data_dir = Path(data_dir)
        self._embedder: Any | None = None
        self.docs: list[dict[str, Any]] = []
        self.embeddings: np.ndarray | None = None
        self._tfidf_ready = False
        self.vocab: dict[str, int] = {}
        self.idf: np.ndarray | None = None
        self.matrix: np.ndarray | None = None
        self._load()

    # ---- loading -----------------------------------------------------------
    def _load(self) -> None:
        file_kb = _load_kb(self._data_dir / "attack_kb.json")
        source = file_kb if file_kb else TECHNIQUES
        self.docs = [dict(d) for d in source]
        # Normalize embeddings if present.
        embs = []
        for d in self.docs:
            emb = d.get("embedding")
            if emb and isinstance(emb, list):
                embs.append(np.array(emb, dtype=np.float32))
            else:
                embs.append(None)
        if all(e is not None for e in embs):
            self.embeddings = np.stack(embs)
        else:
            self.embeddings = None
        self._build_tfidf()
        if self._settings is not None:
            region = getattr(getattr(self._settings, "aws", None), "region", "us-east-1")
            self._embedder = build_embedder(self._settings, region)

    def _build_tfidf(self) -> None:
        self.vocab = {}
        for doc in self.docs:
            for tok in _tokens(doc.get("text", "") + " " + doc.get("name", "")):
                self.vocab.setdefault(tok, len(self.vocab))
        n_docs = len(self.docs)
        if n_docs == 0 or not self.vocab:
            self._tfidf_ready = False
            return
        df = np.zeros(len(self.vocab))
        doc_tokens = [_tokens(d.get("text", "") + " " + d.get("name", "")) for d in self.docs]
        for toks in doc_tokens:
            for tok in set(toks):
                df[self.vocab[tok]] += 1
        self.idf = np.log((1 + n_docs) / (1 + df)) + 1.0
        self.matrix = np.stack([self._vectorize(toks) for toks in doc_tokens])
        norms = np.linalg.norm(self.matrix, axis=1) + 1e-9
        self.matrix = self.matrix / norms[:, None]
        self._tfidf_ready = True

    def _vectorize(self, toks: list[str]) -> np.ndarray:
        vec = np.zeros(len(self.vocab))
        for tok in toks:
            idx = self.vocab.get(tok)
            if idx is not None:
                vec[idx] += 1.0
        if vec.sum() > 0:
            vec = vec / vec.sum()
        return vec * self.idf

    # ---- retrieval ---------------------------------------------------------
    async def retrieve(self, query: str, k: int = 3,
                       min_score: float = 0.01) -> list[dict[str, Any]]:
        # Try dense retrieval first.
        dense = await self._dense_retrieve(query, k, min_score)
        if dense is not None:
            return dense
        return self._tfidf_retrieve(query, k, min_score)

    async def _dense_retrieve(self, query: str, k: int,
                              min_score: float) -> list[dict[str, Any]] | None:
        if self.embeddings is None or self._embedder is None:
            return None
        try:
            qemb = await self._embedder.embed_one(query)
        except Exception:
            return None
        if not qemb:
            return None
        qv = np.array(qemb, dtype=np.float32)
        norm = float(np.linalg.norm(qv))
        if norm < 1e-9:
            return None
        qv = qv / norm
        sims = self.embeddings @ qv
        top = np.argsort(-sims)[:k]
        return [{"id": self.docs[i]["id"], "name": self.docs[i]["name"],
                 "score": round(float(sims[i]), 3)}
                for i in top if sims[i] > min_score]

    def _tfidf_retrieve(self, query: str, k: int,
                        min_score: float) -> list[dict[str, Any]]:
        if not self._tfidf_ready or self.matrix is None:
            return []
        qv = self._vectorize(_tokens(query))
        norm = np.linalg.norm(qv)
        if norm < 1e-9:
            return []
        qv = qv / norm
        sims = self.matrix @ qv
        top = np.argsort(-sims)[:k]
        return [{"id": self.docs[i]["id"], "name": self.docs[i]["name"],
                 "score": round(float(sims[i]), 3)}
                for i in top if sims[i] > min_score]
