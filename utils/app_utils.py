import os
import time
import sys
import logging
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Any

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
            if "rate_limit" in error_msg or "tokens per minute" in error_msg:
                wait_time = (2 ** attempt) * backoff_multiplier
                logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                if attempt == max_retries - 1:
                    logger.error(f"Failed {target_file} after {max_retries} retries.")
                    raise
            else:
                logger.error(f"Error processing {target_file}: {str(e)}")
                raise

    raise RuntimeError(f"Exhausted retries for {target_file}")


def generate_report(results: dict, config: dict, logger: logging.Logger) -> None:
    """Generate an HTML report of refactoring results."""
    report_file = config.get("output", {}).get("report_file", "reports/refactoring_report.html")
    Path(report_file).parent.mkdir(parents=True, exist_ok=True)

    html_content = f"""
    <html>
    <head>
        <title>CodeBase Agent Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            .success {{ color: green; }}
            .error {{ color: red; }}
            .file {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
            .summary {{ background: #e8f5e9; padding: 15px; margin: 10px 0; border-radius: 5px; }}
        </style>
    </head>
    <body>
        <h1>CodeBase Agent Refactoring Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <div class="summary">
            <h2>Summary</h2>
            <p>Total files processed: {len(results)}</p>
            <p>Successful: {sum(1 for r in results.values() if r.get('status') == 'success')}</p>
            <p>Failed: {sum(1 for r in results.values() if r.get('status') == 'failed')}</p>
        </div>
    """

    for file_name, result in results.items():
        status_class = "success" if result.get("status") == "success" else "error"
        inference_time = result.get("inference_time", 0)
        time_str = f"{inference_time:.2f}s" if inference_time else "N/A"
        html_content += f"""
        <div class="file">
            <h3 class="{status_class}">{file_name}</h3>
            <p><strong>Status:</strong> {result.get('status', 'Unknown')}</p>
            <p><strong>Inference Time:</strong> {time_str}</p>
            <p><strong>Backup:</strong> {result.get('backup', 'N/A')}</p>
        </div>
        """

    html_content += """
    </body>
    </html>
    """

    with open(report_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    logger.info(f"Report saved to {report_file}")
