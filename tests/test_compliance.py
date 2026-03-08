import pytest
import tempfile
import os
from pathlib import Path

from utils.compliance import (
    scan_file_for_compliance,
    aggregate_compliance,
    should_fail_quality_gate,
    write_compliance_artifacts,
    _build_finding,
    RULES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_py_file(tmp_path):
    """Create a temp Python file with known compliance issues."""
    code = '''\
import os

GLOBAL_LIST = []

def risky():
    try:
        x = 1 / 0
    except Exception as e:
        pass

def sql_query(user_input):
    import sqlite3
    conn = sqlite3.connect("test.db")
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM users WHERE name = '{user_input}'")

api_key = "sk-secret-12345"
'''
    p = tmp_path / "sample.py"
    p.write_text(code, encoding="utf-8")
    return str(p)


@pytest.fixture
def clean_py_file(tmp_path):
    """A file that triggers no compliance rules."""
    code = '''\
def add(a: int, b: int) -> int:
    return a + b
'''
    p = tmp_path / "clean.py"
    p.write_text(code, encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# scan_file_for_compliance
# ---------------------------------------------------------------------------

class TestScanFile:
    def test_detects_critical_exception_swallowing(self, tmp_py_file):
        result = scan_file_for_compliance(tmp_py_file)
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "AML-AUDIT-001" in rule_ids

    def test_detects_sql_injection(self, tmp_py_file):
        result = scan_file_for_compliance(tmp_py_file)
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "AML-SEC-001" in rule_ids

    def test_detects_hardcoded_secret(self, tmp_py_file):
        result = scan_file_for_compliance(tmp_py_file)
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "AML-SEC-002" in rule_ids

    def test_detects_global_mutable_state(self, tmp_py_file):
        result = scan_file_for_compliance(tmp_py_file)
        rule_ids = [f["rule_id"] for f in result["findings"]]
        assert "AML-DATA-001" in rule_ids

    def test_summary_counts(self, tmp_py_file):
        result = scan_file_for_compliance(tmp_py_file)
        summary = result["summary"]
        assert summary["total"] > 0
        assert summary["critical"] >= 1  # at least exception + SQL injection
        assert summary["high"] >= 1  # at least hardcoded secret

    def test_clean_file_has_no_findings(self, clean_py_file):
        result = scan_file_for_compliance(clean_py_file)
        assert result["summary"]["total"] == 0
        assert result["findings"] == []

    def test_missing_file_returns_error(self):
        result = scan_file_for_compliance("/nonexistent/file.py")
        assert result["error"] == "file_not_found"
        assert result["findings"] == []
        assert result["summary"]["total"] == 0

    def test_finding_structure(self, tmp_py_file):
        result = scan_file_for_compliance(tmp_py_file)
        finding = result["findings"][0]
        expected_keys = {
            "rule_id", "severity", "category", "file", "line",
            "evidence", "description", "recommendation", "source", "timestamp",
        }
        assert expected_keys == set(finding.keys())
        assert finding["source"] == "deterministic_regex"


# ---------------------------------------------------------------------------
# _build_finding
# ---------------------------------------------------------------------------

class TestBuildFinding:
    def test_truncates_evidence(self):
        rule = RULES[0]
        long_line = "x" * 500
        finding = _build_finding(rule, "test.py", 1, long_line)
        assert len(finding["evidence"]) <= 240

    def test_returns_correct_fields(self):
        rule = RULES[0]
        finding = _build_finding(rule, "test.py", 42, "except Exception as e:")
        assert finding["rule_id"] == rule["rule_id"]
        assert finding["line"] == 42
        assert finding["file"] == "test.py"


# ---------------------------------------------------------------------------
# aggregate_compliance
# ---------------------------------------------------------------------------

class TestAggregateCompliance:
    def test_aggregates_across_files(self, tmp_py_file, clean_py_file):
        results = {
            "file1": {"compliance": scan_file_for_compliance(tmp_py_file)},
            "file2": {"compliance": scan_file_for_compliance(clean_py_file)},
        }
        agg = aggregate_compliance(results)
        assert agg["summary"]["total"] > 0
        assert agg["summary"]["affected_files"] == 1  # only file1 has findings

    def test_empty_results(self):
        agg = aggregate_compliance({})
        assert agg["summary"]["total"] == 0
        assert agg["summary"]["affected_files"] == 0

    def test_handles_missing_compliance_key(self):
        results = {"file1": {"status": "failed"}}
        agg = aggregate_compliance(results)
        assert agg["summary"]["total"] == 0


# ---------------------------------------------------------------------------
# should_fail_quality_gate
# ---------------------------------------------------------------------------

class TestQualityGate:
    def test_fails_on_critical(self, tmp_py_file):
        results = {"f": {"compliance": scan_file_for_compliance(tmp_py_file)}}
        assert should_fail_quality_gate(results, "critical") is True

    def test_passes_when_no_threshold(self, tmp_py_file):
        results = {"f": {"compliance": scan_file_for_compliance(tmp_py_file)}}
        assert should_fail_quality_gate(results, None) is False

    def test_passes_clean_file(self, clean_py_file):
        results = {"f": {"compliance": scan_file_for_compliance(clean_py_file)}}
        assert should_fail_quality_gate(results, "critical") is False

    def test_invalid_threshold_returns_false(self, tmp_py_file):
        results = {"f": {"compliance": scan_file_for_compliance(tmp_py_file)}}
        assert should_fail_quality_gate(results, "unknown") is False


# ---------------------------------------------------------------------------
# write_compliance_artifacts
# ---------------------------------------------------------------------------

class TestWriteArtifacts:
    def test_writes_json_and_jsonl(self, tmp_path, tmp_py_file):
        results = {"f": {"compliance": scan_file_for_compliance(tmp_py_file)}}
        findings_path = str(tmp_path / "findings.json")
        audit_path = str(tmp_path / "audit.jsonl")

        paths = write_compliance_artifacts(results, findings_path, audit_path)
        assert Path(paths["findings"]).exists()
        assert Path(paths["audit_log"]).exists()

        import json
        with open(findings_path, "r") as f:
            data = json.load(f)
        assert "summary" in data
        assert "findings" in data
        assert data["summary"]["total"] > 0

    def test_creates_parent_directories(self, tmp_path, clean_py_file):
        results = {"f": {"compliance": scan_file_for_compliance(clean_py_file)}}
        deep_path = str(tmp_path / "a" / "b" / "findings.json")
        audit_path = str(tmp_path / "a" / "b" / "audit.jsonl")

        paths = write_compliance_artifacts(results, deep_path, audit_path)
        assert Path(paths["findings"]).exists()
