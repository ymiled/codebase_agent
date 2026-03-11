import difflib
from pathlib import Path
from typing import Any, Dict, Optional


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _count_changed_lines(before_source: str, after_source: str) -> Dict[str, int]:
    added = 0
    removed = 0

    for line in difflib.ndiff(before_source.splitlines(), after_source.splitlines()):
        if line.startswith("+ "):
            added += 1
        elif line.startswith("- "):
            removed += 1

    return {
        "added": added,
        "removed": removed,
        "total": added + removed,
    }


def _build_signal_to_noise(
    before_metrics: Dict[str, Any],
    after_metrics: Dict[str, Any],
    lines_changed: int,
) -> Dict[str, Any]:
    comparisons = {
        "cyclomatic_avg": ("down", _to_float(before_metrics["cyclomatic"]["average"]), _to_float(after_metrics["cyclomatic"]["average"])),
        "cyclomatic_max": ("down", _to_float(before_metrics["cyclomatic"]["max"]), _to_float(after_metrics["cyclomatic"]["max"])),
        "maintainability_index": ("up", _to_float(before_metrics["maintainability_index"]), _to_float(after_metrics["maintainability_index"])),
        "halstead_difficulty": ("down", _to_float(before_metrics["halstead"]["difficulty"]), _to_float(after_metrics["halstead"]["difficulty"])),
        "halstead_effort": ("down", _to_float(before_metrics["halstead"]["effort"]), _to_float(after_metrics["halstead"]["effort"])),
        "halstead_bugs": ("down", _to_float(before_metrics["halstead"]["bugs"]), _to_float(after_metrics["halstead"]["bugs"])),
    }

    improved = 0
    degraded = 0
    unchanged = 0

    for direction, before_value, after_value in comparisons.values():
        if abs(after_value - before_value) < 1e-9:
            unchanged += 1
            continue

        if direction == "down":
            if after_value < before_value:
                improved += 1
            else:
                degraded += 1
        else:
            if after_value > before_value:
                improved += 1
            else:
                degraded += 1

    considered = len(comparisons)
    net_gain = improved - degraded
    score = (net_gain / considered) * 100.0 if considered else 0.0
    efficiency = (improved / max(1, lines_changed)) * 100.0

    return {
        "improved_metrics": improved,
        "degraded_metrics": degraded,
        "unchanged_metrics": unchanged,
        "considered_metrics": considered,
        "net_gain": net_gain,
        "score": round(score, 2),
        "efficiency_per_100_lines_changed": round(efficiency, 2),
    }


def compute_quality_metrics(file_path: str) -> Dict[str, Any]:
    """Compute quality metrics for a Python source file.

    Returns a stable dictionary shape even when analysis fails so callers can
    safely include results in reports.
    """
    path = Path(file_path)
    if not path.exists():
        return {
            "status": "error",
            "error": "file_not_found",
            "file": file_path,
        }

    source = path.read_text(encoding="utf-8", errors="ignore")

    try:
        from radon.complexity import cc_visit
        from radon.metrics import h_visit, mi_visit
        from radon.raw import analyze
    except ImportError:
        return {
            "status": "error",
            "error": "radon_not_installed",
            "file": file_path,
        }

    try:
        blocks = cc_visit(source)
        complexities = [getattr(block, "complexity", 0) for block in blocks]
        cc_total = sum(complexities)
        cc_avg = cc_total / len(complexities) if complexities else 0.0
        cc_max = max(complexities) if complexities else 0.0

        mi_score = _to_float(mi_visit(source, multi=True))

        halstead = h_visit(source)
        halstead_total = getattr(halstead, "total", None)

        raw = analyze(source)

        return {
            "status": "ok",
            "file": file_path,
            "cyclomatic": {
                "average": round(cc_avg, 2),
                "max": round(_to_float(cc_max), 2),
                "total": round(_to_float(cc_total), 2),
                "function_count": len(complexities),
            },
            "maintainability_index": round(mi_score, 2),
            "halstead": {
                "difficulty": round(_to_float(getattr(halstead_total, "difficulty", 0.0)), 2),
                "effort": round(_to_float(getattr(halstead_total, "effort", 0.0)), 2),
                "bugs": round(_to_float(getattr(halstead_total, "bugs", 0.0)), 4),
                "volume": round(_to_float(getattr(halstead_total, "volume", 0.0)), 2),
            },
            "code_size": {
                "loc": int(getattr(raw, "loc", 0)),
                "lloc": int(getattr(raw, "lloc", 0)),
                "sloc": int(getattr(raw, "sloc", 0)),
                "comments": int(getattr(raw, "comments", 0)),
                "multi": int(getattr(raw, "multi", 0)),
                "blank": int(getattr(raw, "blank", 0)),
            },
        }
    except Exception as exc:
        return {
            "status": "error",
            "error": f"metrics_failed: {exc}",
            "file": file_path,
        }


def compare_quality_metrics(
    before_metrics: Optional[Dict[str, Any]],
    after_metrics: Optional[Dict[str, Any]],
    before_file_path: Optional[str],
    after_file_path: Optional[str],
) -> Dict[str, Any]:
    """Compare two quality metric snapshots and compute deltas and efficiency."""
    if not before_metrics or not after_metrics:
        return {
            "status": "error",
            "error": "missing_metrics",
        }

    if before_metrics.get("status") != "ok" or after_metrics.get("status") != "ok":
        return {
            "status": "error",
            "error": "metrics_unavailable",
            "before_status": before_metrics.get("status"),
            "after_status": after_metrics.get("status"),
            "before_error": before_metrics.get("error"),
            "after_error": after_metrics.get("error"),
        }

    before_source = ""
    after_source = ""

    if before_file_path and Path(before_file_path).exists():
        before_source = Path(before_file_path).read_text(encoding="utf-8", errors="ignore")
    if after_file_path and Path(after_file_path).exists():
        after_source = Path(after_file_path).read_text(encoding="utf-8", errors="ignore")

    line_changes = _count_changed_lines(before_source, after_source)
    signal_to_noise = _build_signal_to_noise(before_metrics, after_metrics, line_changes["total"])

    return {
        "status": "ok",
        "delta": {
            "cyclomatic_avg": round(
                _to_float(after_metrics["cyclomatic"]["average"]) - _to_float(before_metrics["cyclomatic"]["average"]),
                2,
            ),
            "cyclomatic_max": round(
                _to_float(after_metrics["cyclomatic"]["max"]) - _to_float(before_metrics["cyclomatic"]["max"]),
                2,
            ),
            "maintainability_index": round(
                _to_float(after_metrics["maintainability_index"]) - _to_float(before_metrics["maintainability_index"]),
                2,
            ),
            "halstead_difficulty": round(
                _to_float(after_metrics["halstead"]["difficulty"]) - _to_float(before_metrics["halstead"]["difficulty"]),
                2,
            ),
            "halstead_effort": round(
                _to_float(after_metrics["halstead"]["effort"]) - _to_float(before_metrics["halstead"]["effort"]),
                2,
            ),
            "halstead_bugs": round(
                _to_float(after_metrics["halstead"]["bugs"]) - _to_float(before_metrics["halstead"]["bugs"]),
                4,
            ),
            "loc": int(after_metrics["code_size"]["loc"] - before_metrics["code_size"]["loc"]),
            "lloc": int(after_metrics["code_size"]["lloc"] - before_metrics["code_size"]["lloc"]),
            "comments": int(after_metrics["code_size"]["comments"] - before_metrics["code_size"]["comments"]),
        },
        "line_changes": line_changes,
        "signal_to_noise": signal_to_noise,
    }
