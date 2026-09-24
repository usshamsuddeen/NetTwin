"""Fetch MITRE ATT&CK STIX and build data/attack_kb.json with optional embeddings."""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

KB_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"


def _fetch(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "nettwin-kb-updater/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def _build_text(technique: dict[str, Any], tactics: dict[str, str]) -> str:
    parts = [technique.get("name", "")]
    desc = _clean(technique.get("description", ""))
    if desc:
        parts.append(desc)
    phases = technique.get("kill_chain_phases", [])
    tactic_names = []
    for phase in phases:
        if phase.get("kill_chain_name") == "mitre-attack":
            tid = phase.get("phase_name", "")
            if tid in tactics:
                tactic_names.append(tactics[tid])
    if tactic_names:
        parts.append("Tactics: " + ", ".join(tactic_names))
    for ref in technique.get("external_references", []):
        if ref.get("source_name") == "mitre-attack" and "url" in ref:
            parts.append(ref["url"])
            break
    return _clean(" ".join(parts))


def _parse(stix: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    tactics: dict[str, str] = {}
    techniques: list[dict[str, Any]] = []
    for obj in stix.get("objects", []):
        t = obj.get("type")
        if t == "x-mitre-tactic":
            short = obj.get("x_mitre_shortname", "")
            name = obj.get("name", "")
            if short and name:
                tactics[short] = name
        elif t == "attack-pattern":
            revoked = obj.get("revoked", False)
            deprecated = obj.get("x_mitre_deprecated", False)
            if revoked or deprecated:
                continue
            tid = None
            for ref in obj.get("external_references", []):
                if ref.get("source_name") == "mitre-attack":
                    tid = ref.get("external_id")
                    break
            if not tid:
                continue
            text = _build_text(obj, tactics)
            techniques.append({
                "id": tid,
                "name": obj.get("name", ""),
                "text": text,
                "url": next((r["url"] for r in obj.get("external_references", [])
                             if r.get("source_name") == "mitre-attack"), ""),
            })
    return techniques, tactics


def _add_embeddings(techniques: list[dict[str, Any]], provider: str, model: str,
                    ollama_url: str) -> None:
    # Local import so the script can still produce a TF-IDF KB without deps.
    try:
        from nettwin.llm.embeddings import OllamaEmbedder, BedrockEmbedder
    except Exception as exc:
        print(f"embedding module unavailable: {exc}; skipping embeddings")
        return

    embedder = None
    if provider == "ollama":
        from nettwin.config import LLMSettings
        s = LLMSettings(ollama_url=ollama_url, embedding_model=model)
        embedder = OllamaEmbedder(s)
    elif provider == "bedrock":
        from nettwin.config import LLMSettings
        s = LLMSettings(embedding_model=model)
        embedder = BedrockEmbedder(s)
    else:
        print(f"unknown embedding provider {provider}; skipping embeddings")
        return

    import asyncio

    async def _embed() -> None:
        texts = [t["text"] for t in techniques]
        embs = await embedder.embed(texts)
        for t, emb in zip(techniques, embs):
            t["embedding"] = emb

    asyncio.run(_embed())


def main() -> None:
    parser = argparse.ArgumentParser(description="Update NetTwin ATT&CK knowledge base")
    parser.add_argument("--url", default=KB_URL, help="MITRE ATT&CK STIX URL")
    parser.add_argument("--out", default="data/attack_kb.json", help="output JSON path")
    parser.add_argument("--embed", choices=["ollama", "bedrock"], help="compute embeddings")
    parser.add_argument("--model", default="nomic-embed-text", help="embedding model name")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama base URL")
    args = parser.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Fetching {args.url} ...")
    stix = _fetch(args.url)
    techniques, tactics = _parse(stix)
    print(f"Parsed {len(techniques)} active techniques and {len(tactics)} tactics")

    if args.embed:
        print(f"Computing {args.embed} embeddings with {args.model} ...")
        _add_embeddings(techniques, args.embed, args.model, args.ollama_url)

    with out_path.open("w", encoding="utf-8") as fh:
        json.dump(techniques, fh, indent=2)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
