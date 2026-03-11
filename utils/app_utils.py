import difflib
import os
import time
import sys
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Any, Dict

import yaml
from crewai import Crew, LLM

from utils.tools import set_rag_instance
from utils.rag_system import RAGCodebaseIndex


def setup_logging(log_file: str = "logs/codebase_agent.log", log_level: str = "INFO") -> logging.Logger:
    """Configure logging to both console and file."""
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("codebase_agent")
    logger.setLevel(logging.DEBUG)

    # Prevent duplicate handlers when rerunning in same process.
    if logger.handlers:
        logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    console_format = logging.Formatter(
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)

    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def load_config(config_file: str = "configs/config.yaml") -> dict:
    """Load configuration from YAML file.

    Supports both direct paths (e.g. configs/config.yaml) and bare filenames
    (e.g. config.yaml) by checking the configs directory automatically.
    """
    resolved_path = config_file
    if not os.path.exists(resolved_path):
        candidate_in_configs = os.path.join("configs", config_file)
        if os.path.exists(candidate_in_configs):
            resolved_path = candidate_in_configs
        else:
            raise FileNotFoundError(f"Config file not found: {config_file}")

    with open(resolved_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def backup_file(file_path: str, logger: logging.Logger) -> Optional[str]:
    """Create a backup of the original file."""
    backup_dir = Path("backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)

    original_file = Path(file_path)
    backup_path = backup_dir / original_file.name

    if original_file.exists():
        shutil.copy2(original_file, backup_path)
        logger.info(f"Backed up {file_path} to {backup_path}")
        return str(backup_path)
    return None


def setup_llm(config: dict) -> LLM:
    """Initialize LLM with config settings."""
    llm_config = config.get("llm", {})
    return LLM(
        model=llm_config.get("model", "groq/llama-3.3-70b-versatile"),
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=llm_config.get("temperature", 0.0),
        max_tokens=llm_config.get("max_tokens", 1024),
    )


def setup_rag(config: dict, logger: logging.Logger) -> Optional[RAGCodebaseIndex]:
    """Initialize RAG system and optionally index configured directories."""
    rag_config = config.get("rag", {})

    if not rag_config.get("enable", False):
        logger.info("RAG is disabled in config")
        return None

    try:
        logger.info("Initializing RAG system...")
        rag = RAGCodebaseIndex(
            collection_name=rag_config.get("collection_name", "codebase"),
            persist_directory=rag_config.get("persist_directory", "rag_data"),
            model_name=rag_config.get("embedding_model", "all-MiniLM-L6-v2"),
        )

        set_rag_instance(rag)

        if rag_config.get("index_on_startup", True):
            logger.info("Indexing codebase for RAG...")
            directories_to_index = rag_config.get("index_directories", ["target_repo"])

            for directory in directories_to_index:
                if os.path.exists(directory):
                    results = rag.index_directory(directory, file_extensions=[".py"])
                    dir_chunks = sum(results.values())
                    dir_files = len(results)
                    logger.info(f"{directory}: {dir_chunks} chunks from {dir_files} files")
                else:
                    logger.warning(f"{directory}: directory not found (skipping)")

            stats = rag.get_collection_stats()
            logger.info(
                f"RAG indexing complete: {stats.get('total_chunks', 0)} total chunks in database"
            )

        return rag

    except Exception as e:
        logger.error(f"Failed to initialize RAG: {e}")
        logger.warning("Continuing without RAG support")
        return None


def run_with_retry(crew: Crew, config: dict, target_file: str, logger: logging.Logger) -> Any:
    """Run the crew with exponential backoff retry logic."""
    retry_config = config.get("retry", {})
    max_retries = retry_config.get("max_retries", 3)
    backoff_multiplier = retry_config.get("backoff_multiplier", 15)

    for attempt in range(max_retries):
        try:
            logger.info(f"Processing: {target_file} (Attempt {attempt + 1}/{max_retries})")
            result = crew.kickoff()
            logger.info(f"Completed: {target_file}")
            return result
        except Exception as e:
            error_msg = str(e).lower()
            if "rate_limit" in error_msg or "tokens per minute" in error_msg or "tokens per day" in error_msg:
                wait_time = (2 ** attempt) * backoff_multiplier
                logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                if attempt == max_retries - 1:
                    logger.error(f"Failed {target_file} after {max_retries} retries.")
                    raise
            elif "tool_use_failed" in error_msg or "failed_generation" in error_msg:
                wait_time = (2 ** attempt) * backoff_multiplier
                logger.warning(
                    f"LLM generated malformed tool call for {target_file} "
                    f"(attempt {attempt + 1}/{max_retries}). Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
                if attempt == max_retries - 1:
                    logger.error(f"Failed {target_file} after {max_retries} retries (tool_use_failed).")
                    raise
            else:
                logger.error(f"Error processing {target_file}: {str(e)}")
                raise

    raise RuntimeError(f"Exhausted retries for {target_file}")


def _aggregate_quality_summary(results: dict) -> Dict[str, float]:
    summary = {
        "files_with_metrics": 0,
        "avg_mi_delta": 0.0,
        "avg_cc_delta": 0.0,
        "avg_halstead_bugs_delta": 0.0,
        "avg_signal_to_noise": 0.0,
    }

    mi_deltas = []
    cc_deltas = []
    bug_deltas = []
    stn_scores = []

    for result in results.values():
        quality = result.get("quality_metrics") or {}
        comparison = quality.get("comparison") or {}
        if comparison.get("status") != "ok":
            continue

        delta = comparison.get("delta") or {}
        signal = comparison.get("signal_to_noise") or {}

        summary["files_with_metrics"] += 1
        mi_deltas.append(float(delta.get("maintainability_index", 0.0)))
        cc_deltas.append(float(delta.get("cyclomatic_avg", 0.0)))
        bug_deltas.append(float(delta.get("halstead_bugs", 0.0)))
        stn_scores.append(float(signal.get("score", 0.0)))

    file_count = summary["files_with_metrics"]
    if file_count:
        summary["avg_mi_delta"] = sum(mi_deltas) / file_count
        summary["avg_cc_delta"] = sum(cc_deltas) / file_count
        summary["avg_halstead_bugs_delta"] = sum(bug_deltas) / file_count
        summary["avg_signal_to_noise"] = sum(stn_scores) / file_count

    return summary


def _format_delta(value: float, prefer_positive: bool) -> str:
    if value > 0:
        prefix = "+"
    else:
        prefix = ""
    indicator = "improved" if (value > 0 and prefer_positive) or (value < 0 and not prefer_positive) else "degraded"
    if abs(value) < 1e-9:
        indicator = "neutral"
    return f"{prefix}{value:.2f} ({indicator})"


def generate_report(results: dict, config: dict, logger: logging.Logger) -> None:
    """Generate an HTML report of refactoring results."""
    report_file = config.get("output", {}).get("report_file", "reports/refactoring_report.html")
    Path(report_file).parent.mkdir(parents=True, exist_ok=True)

    compliance_summary = {"critical": 0, "high": 0, "medium": 0, "low": 0, "total": 0}
    quality_summary = _aggregate_quality_summary(results)
    for result in results.values():
        file_summary = (result.get("compliance") or {}).get("summary", {})
        compliance_summary["critical"] += file_summary.get("critical", 0)
        compliance_summary["high"] += file_summary.get("high", 0)
        compliance_summary["medium"] += file_summary.get("medium", 0)
        compliance_summary["low"] += file_summary.get("low", 0)
        compliance_summary["total"] += file_summary.get("total", 0)

    html_content = f"""
    <html>
    <head>
        <title>CodeBase Agent Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; background: #f9f9f9; }}
            h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }}
            h2 {{ color: #555; margin-top: 25px; }}
            h3 {{ color: #777; }}
            .success {{ color: #4CAF50; font-weight: bold; }}
            .error {{ color: #f44336; font-weight: bold; }}
            .warning {{ color: #ff9800; font-weight: bold; }}
            .file-section {{ background: white; padding: 20px; margin: 15px 0; border-left: 5px solid #4CAF50; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .file-section.failed {{ border-left-color: #f44336; }}
            .summary {{ background: linear-gradient(135deg, #e8f5e9 0%, #c8e6c9 100%); padding: 20px; margin: 20px 0; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
            .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
            .metric-value {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
            .metric-label {{ font-size: 14px; color: #666; }}
            .detail {{ background: #f5f5f5; padding: 10px; margin: 10px 0; border-radius: 4px; font-family: monospace; }}
            .section-title {{ background: #e3f2fd; padding: 10px; margin: 15px 0 10px 0; border-left: 4px solid #2196F3; font-weight: bold; }}
            .subtle {{ color: #666; font-size: 13px; }}
            table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
            th {{ background: #f5f5f5; padding: 10px; text-align: left; border-bottom: 2px solid #ddd; }}
            td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
            tr:hover {{ background: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h1>CodeBase Agent Analysis Report</h1>
        <p><em>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
        
        <div class="summary">
            <h2 style="margin-top: 0;">Summary</h2>
            <div class="metric">
                <div class="metric-value">{len(results)}</div>
                <div class="metric-label">Files Analyzed</div>
            </div>
            <div class="metric">
                <div class="metric-value"><span class="success">{sum(1 for r in results.values() if r.get('status') == 'success')}</span></div>
                <div class="metric-label">Successful</div>
            </div>
            <div class="metric">
                <div class="metric-value"><span class="error">{sum(1 for r in results.values() if r.get('status') == 'failed')}</span></div>
                <div class="metric-label">Failed</div>
            </div>
            <div class="metric">
                <div class="metric-value">{sum(r.get('inference_time', 0) for r in results.values()):.1f}s</div>
                <div class="metric-label">Total Processing Time</div>
            </div>
        </div>

        <div class="summary" style="background: linear-gradient(135deg, #fff8e1 0%, #ffe0b2 100%);">
            <h2 style="margin-top: 0;">Compliance Findings</h2>
            <div class="metric">
                <div class="metric-value" style="color:#c62828;">{compliance_summary['critical']}</div>
                <div class="metric-label">Critical</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color:#e65100;">{compliance_summary['high']}</div>
                <div class="metric-label">High</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color:#f57f17;">{compliance_summary['medium']}</div>
                <div class="metric-label">Medium</div>
            </div>
            <div class="metric">
                <div class="metric-value" style="color:#33691e;">{compliance_summary['low']}</div>
                <div class="metric-label">Low</div>
            </div>
            <div class="metric">
                <div class="metric-value">{compliance_summary['total']}</div>
                <div class="metric-label">Total Findings</div>
            </div>
        </div>

        <div class="summary" style="background: linear-gradient(135deg, #e1f5fe 0%, #b3e5fc 100%);">
            <h2 style="margin-top: 0;">Code Quality Metrics</h2>
            <div class="metric">
                <div class="metric-value">{int(quality_summary['files_with_metrics'])}</div>
                <div class="metric-label">Files Compared</div>
            </div>
            <div class="metric">
                <div class="metric-value">{quality_summary['avg_mi_delta']:+.2f}</div>
                <div class="metric-label">Avg MI Delta</div>
            </div>
            <div class="metric">
                <div class="metric-value">{quality_summary['avg_cc_delta']:+.2f}</div>
                <div class="metric-label">Avg CC Delta</div>
            </div>
            <div class="metric">
                <div class="metric-value">{quality_summary['avg_halstead_bugs_delta']:+.4f}</div>
                <div class="metric-label">Avg Halstead Bugs Delta</div>
            </div>
            <div class="metric">
                <div class="metric-value">{quality_summary['avg_signal_to_noise']:+.2f}</div>
                <div class="metric-label">Avg Signal-to-Noise Score</div>
            </div>
            <p class="subtle">Interpretation: CC and Halstead deltas should trend negative; MI and signal-to-noise should trend positive.</p>
        </div>

        <table>
            <tr>
                <th>File</th>
                <th>Status</th>
                <th>Time (s)</th>
                <th>Backup Location</th>
            </tr>
    """

    for file_name, result in results.items():
        status_class = "success" if result.get("status") == "success" else "error"
        status_text = result.get("status", "Unknown").upper()
        inference_time = result.get("inference_time", 0)
        time_str = f"{inference_time:.2f}" if inference_time else "N/A"
        backup_loc = result.get("backup", "N/A")

        html_content += f"""
            <tr>
                <td>{file_name}</td>
                <td class="{status_class}">{status_text}</td>
                <td>{time_str}</td>
                <td>{backup_loc}</td>
            </tr>
        """

    html_content += """
        </table>

        <h2>Detailed Results</h2>
    """

    for file_name, result in results.items():
        status_class = "file-section" if result.get("status") == "success" else "file-section failed"
        status_text = result.get("status", "Unknown").upper()
        
        html_content += f"""
        <div class="{status_class}">
            <h3>{file_name} <span class="{'success' if result.get('status') == 'success' else 'error'}">({status_text})</span></h3>
            <p><strong>Analysis Time:</strong> {result.get('inference_time', 0):.2f}s</p>
        """

        if result.get("status") == "success":
            comp = (result.get("compliance") or {}).get("summary", {})
            quality = result.get("quality_metrics") or {}
            before = quality.get("before") or {}
            after = quality.get("after") or {}
            comparison = quality.get("comparison") or {}
            html_content += f"""
            <p><strong>Backup Location:</strong> {result.get('backup', 'N/A')}</p>
            <p><strong>Compliance:</strong> critical={comp.get('critical', 0)}, high={comp.get('high', 0)}, medium={comp.get('medium', 0)}, low={comp.get('low', 0)}</p>
            
            """
            if comparison.get("status") == "ok":
                delta = comparison.get("delta") or {}
                line_changes = comparison.get("line_changes") or {}
                signal = comparison.get("signal_to_noise") or {}
                html_content += f"""
                <div class="section-title">Quality Metrics (Before → After)</div>
                <p><strong>Cyclomatic Avg:</strong> {before.get('cyclomatic', {}).get('average', 'N/A')} → {after.get('cyclomatic', {}).get('average', 'N/A')} | Delta: {_format_delta(float(delta.get('cyclomatic_avg', 0.0)), prefer_positive=False)}</p>
                <p><strong>Maintainability Index:</strong> {before.get('maintainability_index', 'N/A')} → {after.get('maintainability_index', 'N/A')} | Delta: {_format_delta(float(delta.get('maintainability_index', 0.0)), prefer_positive=True)}</p>
                <p><strong>Halstead Bugs:</strong> {before.get('halstead', {}).get('bugs', 'N/A')} → {after.get('halstead', {}).get('bugs', 'N/A')} | Delta: {_format_delta(float(delta.get('halstead_bugs', 0.0)), prefer_positive=False)}</p>
                <p><strong>Code Size:</strong> LOC {before.get('code_size', {}).get('loc', 'N/A')} → {after.get('code_size', {}).get('loc', 'N/A')} (delta {int(delta.get('loc', 0)):+d})</p>
                <p><strong>Signal-to-Noise:</strong> score={signal.get('score', 0)} | improved={signal.get('improved_metrics', 0)} degraded={signal.get('degraded_metrics', 0)} | lines changed={line_changes.get('total', 0)}</p>
                """
            else:
                html_content += f"""
                <div class="detail" style="background: #fffde7; color: #7f6000;">
                    <strong>Quality Metrics:</strong> unavailable ({comparison.get('error', 'not_computed')})
                </div>
                """
        else:
            html_content += f"""
            <div class="detail" style="background: #ffebee; color: #c62828;">
                <strong>Error:</strong> {result.get('error', 'Unknown error')}
            </div>
            """

        html_content += """
        </div>
        """

    html_content += """
        <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; color: #999; font-size: 12px;">
            <p>CodeBase Agent - Automated Code Analysis & Refactoring System</p>
            <p>Powered by CrewAI with RAG, Dependency Analysis & Performance Benchmarking</p>
        </footer>
    </body>
    </html>
    """

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Report saved to {report_file}")


def generate_diff(original_path: str, modified_path: str, output_dir: str, logger: logging.Logger) -> Optional[str]:
    """Generate a unified diff between the backup (original) and the current (modified) file."""
    try:
        with open(original_path, "r", encoding="utf-8") as f:
            original_lines = f.readlines()
        with open(modified_path, "r", encoding="utf-8") as f:
            modified_lines = f.readlines()

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"original/{Path(modified_path).name}",
            tofile=f"refactored/{Path(modified_path).name}",
        )
        diff_text = "".join(diff)

        if not diff_text:
            logger.info(f"No changes detected for {modified_path}")
            return None

        Path(output_dir).mkdir(parents=True, exist_ok=True)
        diff_file = Path(output_dir) / f"{Path(modified_path).stem}.diff"
        diff_file.write_text(diff_text, encoding="utf-8")
        logger.info(f"Diff saved to {diff_file}")
        return str(diff_file)
    except Exception as e:
        logger.warning(f"Failed to generate diff: {e}")
        return None
