import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}

RULES: List[Dict[str, str]] = [
    {
        "rule_id": "AML-AUDIT-001",
        "severity": "critical",
        "category": "auditability",
        "cwe": "CWE-392",
        "owasp": "",
        "regulation": "SOX Section 802, PCI DSS Req 10",
        "description": "Silent exception swallows operational failures.",
        "regex": r"except\s+Exception",
        "recommendation": "Capture exception details and emit structured audit logs.",
    },
    {
        "rule_id": "AML-AUDIT-002",
        "severity": "high",
        "category": "auditability",
        "cwe": "CWE-392",
        "owasp": "",
        "regulation": "SOX Section 802",
        "description": "Bare except can hide compliance-significant failures.",
        "regex": r"except\s*:",
        "recommendation": "Use explicit exception types and log failure context.",
    },
    {
        "rule_id": "AML-SEC-001",
        "severity": "critical",
        "category": "security",
        "cwe": "CWE-89",
        "owasp": "A03:2021 Injection",
        "regulation": "PCI DSS Req 6.5.1",
        "description": "Potential SQL injection in f-string query execution.",
        "regex": r"execute\s*\(\s*f[\"']",
        "recommendation": "Use parameterized queries, never format SQL with user data.",
    },
    {
        "rule_id": "AML-SEC-002",
        "severity": "high",
        "category": "security",
        "cwe": "CWE-798",
        "owasp": "A07:2021 Identification and Authentication Failures",
        "regulation": "PCI DSS Req 3, Req 8",
        "description": "Possible hardcoded secret/token.",
        "regex": r"(api[_-]?key|secret|token|password)\s*=\s*[\"'][^\"']+[\"']",
        "recommendation": "Load secrets from environment variables or a secret manager.",
    },
    {
        "rule_id": "AML-RISK-001",
        "severity": "high",
        "category": "risk_controls",
        "cwe": "CWE-863",
        "owasp": "A01:2021 Broken Access Control",
        "regulation": "FATF Rec 10, EU 6AMLD Art 18",
        "description": "Hardcoded whitelist or bypass list detected.",
        "regex": r"(whitelist|allowlist|bypass)\s*=\s*\[",
        "recommendation": "Move risk decisions to configurable policy + auditable decision logs.",
    },
    {
        "rule_id": "AML-KYC-001",
        "severity": "high",
        "category": "sanctions_screening",
        "cwe": "CWE-862",
        "owasp": "A01:2021 Broken Access Control",
        "regulation": "FATF Rec 6, FATF Rec 16, OFAC SDN, EU Sanctions",
        "description": "Transaction/payment path without screening checks.",
        "regex": r"(execute_payment|process_transaction|transfer_funds)\s*\(",
        "recommendation": "Enforce sanctions and PEP screening before transaction execution.",
    },
    {
        "rule_id": "AML-DATA-001",
        "severity": "medium",
        "category": "data_integrity",
        "cwe": "CWE-1108",
        "owasp": "",
        "regulation": "FATF Rec 11",
        "description": "Noisy global mutable state can break deterministic risk evaluation.",
        "regex": r"^[A-Z_][A-Z0-9_]*\s*=\s*\[",
        "recommendation": "Use scoped state or immutable data structures with explicit ownership.",
    },
    {
        "rule_id": "AML-DATA-002",
        "severity": "medium",
        "category": "data_integrity",
        "cwe": "CWE-705",
        "owasp": "",
        "regulation": "SOX Section 802",
        "description": "Use of os._exit bypasses cleanup and audit flush.",
        "regex": r"os\._exit\s*\(",
        "recommendation": "Raise controlled shutdown events and ensure audit buffers flush.",
    },
    {
        "rule_id": "AML-OPS-001",
        "severity": "medium",
        "category": "auditability",
        "cwe": "CWE-778",
        "owasp": "A09:2021 Security Logging and Monitoring Failures",
        "regulation": "PCI DSS Req 10, FATF Rec 11",
        "description": "File writes in business logic path without structured logging.",
        "regex": r"open\s*\(\s*[\"'][^\"']+[\"']\s*,\s*[\"']w[\"']",
        "recommendation": "Wrap file output with structured operation logs and failure handling.",
    },
    {
        "rule_id": "AML-RES-001",
        "severity": "low",
        "category": "data_integrity",
        "cwe": "CWE-704",
        "owasp": "",
        "regulation": "",
        "description": "Type checks with type(...) reduce reliability in validation paths.",
        "regex": r"\btype\s*\(",
        "recommendation": "Use isinstance and normalize inputs in a single validator function.",
    },
]


def _build_finding(rule: Dict[str, str], file_path: str, line_number: int, line_text: str) -> Dict[str, Any]:
    finding = {
        "rule_id": rule["rule_id"],
        "severity": rule["severity"],
        "category": rule["category"],
        "file": file_path,
        "line": line_number,
        "evidence": line_text.strip()[:240],
        "description": rule["description"],
        "recommendation": rule["recommendation"],
        "source": "deterministic_regex",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    if rule.get("cwe"):
        finding["cwe"] = rule["cwe"]
    if rule.get("owasp"):
        finding["owasp"] = rule["owasp"]
    if rule.get("regulation"):
        finding["regulation"] = rule["regulation"]
    return finding


def scan_file_for_compliance(file_path: str) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    path_obj = Path(file_path)

    if not path_obj.exists():
        return {
            "file": file_path,
            "error": "file_not_found",
            "findings": [],
            "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0},
        }

    lines = path_obj.read_text(encoding="utf-8", errors="ignore").splitlines()

    for rule in RULES:
        pattern = re.compile(rule["regex"], flags=re.IGNORECASE | re.MULTILINE)
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                findings.append(_build_finding(rule, file_path, idx, line))

    counts = Counter(f["severity"] for f in findings)
    summary = {
        "critical": counts.get("critical", 0),
        "high": counts.get("high", 0),
        "medium": counts.get("medium", 0),
        "low": counts.get("low", 0),
        "total": len(findings),
    }

    return {
        "file": file_path,
        "findings": findings,
        "summary": summary,
    }


def aggregate_compliance(results: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    all_findings: List[Dict[str, Any]] = []
    affected_files = 0

    for file_result in results.values():
        compliance = file_result.get("compliance") or {}
        findings = compliance.get("findings", [])
        if findings:
            affected_files += 1
            all_findings.extend(findings)

    counts = Counter(f["severity"] for f in all_findings)

    return {
        "summary": {
            "critical": counts.get("critical", 0),
            "high": counts.get("high", 0),
            "medium": counts.get("medium", 0),
            "low": counts.get("low", 0),
            "total": len(all_findings),
            "affected_files": affected_files,
        },
        "findings": all_findings,
    }


def should_fail_quality_gate(results: Dict[str, Dict[str, Any]], threshold: Optional[str]) -> bool:
    if not threshold:
        return False

    threshold_level = SEVERITY_ORDER.get(str(threshold).lower())
    if not threshold_level:
        return False

    compliance = aggregate_compliance(results)
    for finding in compliance.get("findings", []):
        if SEVERITY_ORDER.get(finding.get("severity", "low"), 0) >= threshold_level:
            return True
    return False


def write_compliance_artifacts(
    results: Dict[str, Dict[str, Any]],
    findings_path: str,
    audit_log_path: str,
) -> Dict[str, str]:
    compliance = aggregate_compliance(results)

    findings_file = Path(findings_path)
    audit_file = Path(audit_log_path)
    findings_file.parent.mkdir(parents=True, exist_ok=True)
    audit_file.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "summary": compliance["summary"],
        "findings": compliance["findings"],
    }
    findings_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with audit_file.open("w", encoding="utf-8") as f:
        for finding in compliance["findings"]:
            f.write(json.dumps(finding) + "\n")

    return {
        "findings": str(findings_file),
        "audit_log": str(audit_file),
    }
