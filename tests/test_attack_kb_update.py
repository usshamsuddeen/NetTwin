"""Tests for scripts/update_attack_kb.py STIX parsing."""
from scripts.update_attack_kb import _build_text, _parse


def test_parse_extracts_active_techniques():
    stix = {
        "type": "bundle",
        "objects": [
            {
                "type": "x-mitre-tactic",
                "name": "Initial Access",
                "x_mitre_shortname": "initial-access",
            },
            {
                "type": "attack-pattern",
                "id": "attack-pattern--1234",
                "name": "Phishing",
                "description": "Adversary sends phishing messages.",
                "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "initial-access"}],
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "T1566", "url": "https://attack.mitre.org/techniques/T1566"}
                ],
            },
            {
                "type": "attack-pattern",
                "id": "attack-pattern--revoked",
                "name": "Old technique",
                "revoked": True,
                "external_references": [
                    {"source_name": "mitre-attack", "external_id": "T9999", "url": "https://attack.mitre.org/techniques/T9999"}
                ],
            },
        ],
    }
    techniques, tactics = _parse(stix)
    assert len(techniques) == 1
    assert techniques[0]["id"] == "T1566"
    assert techniques[0]["name"] == "Phishing"
    assert "Initial Access" in techniques[0]["text"]
    assert tactics == {"initial-access": "Initial Access"}


def test_build_text_includes_description_and_tactics():
    technique = {
        "name": "Test Technique",
        "description": "A description.",
        "kill_chain_phases": [{"kill_chain_name": "mitre-attack", "phase_name": "defense-evasion"}],
        "external_references": [{"source_name": "mitre-attack", "url": "https://example.com"}],
    }
    tactics = {"defense-evasion": "Defense Evasion"}
    text = _build_text(technique, tactics)
    assert "Test Technique" in text
    assert "A description." in text
    assert "Defense Evasion" in text
    assert "https://example.com" in text
