import argparse
import sys
import time

from dotenv import load_dotenv

from utils.app_utils import (
    setup_logging,
    load_config,
    setup_llm,
    setup_rag,
    backup_file,
    run_with_retry,
    generate_report,
    generate_diff,
)
from utils.crew_setup import setup_agents, setup_tasks, setup_crew
from utils.compliance import (
    scan_file_for_compliance,
    write_compliance_artifacts,
    should_fail_quality_gate,
    aggregate_compliance,
)

load_dotenv()


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="CodeBase Agent - Automated Code Refactoring",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
                python main.py                              # Use configs/config.yaml (default)
                python main.py --file target_repo/bad_code.py
                python main.py --config custom_config.yaml
                python main.py --config configs/config.conservative.yaml
                python main.py --aggressive
                python main.py --no-backup
                python main.py --file file1.py --file file2.py
        """,
    )

    parser.add_argument(
        "--file",
        "-f",
        action="append",
        dest="files",
        help="Target file(s) to refactor (can use multiple times)",
    )
    parser.add_argument(
        "--config",
        "-c",
        default="configs/config.yaml",
        help="Configuration file (default: configs/config.yaml)",
    )
    parser.add_argument(
        "--aggressive",
        "-a",
        action="store_true",
        help="Use aggressive refactoring (more changes)",
    )
    parser.add_argument(
        "--conservative",
        action="store_true",
        help="Use conservative refactoring (minimal changes)",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Do not backup original files",
    )
    parser.add_argument(
        "--log-level",
        "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def apply_cli_overrides(config: dict, args: argparse.Namespace, logger) -> dict:
    """Apply CLI overrides to config."""
    if args.files:
        config["processing"]["files"] = args.files
        logger.info(f"Override files: {args.files}")

    if args.aggressive:
        config["processing"]["refactoring_level"] = "aggressive"
        logger.info("Using aggressive refactoring level")

    if args.conservative:
        config["processing"]["refactoring_level"] = "conservative"
        logger.info("Using conservative refactoring level")

    if args.no_backup:
        config["processing"]["backup_originals"] = False
        logger.info("Backup disabled")

    return config


def process_files(config: dict, logger) -> dict:
    """Run full processing workflow for all target files."""
    target_files = config.get("processing", {}).get("files", ["target_repo/_1.py"])
    logger.info(f"Processing {len(target_files)} file(s)")

    llm = setup_llm(config)
    logger.info(f"LLM configured: {config['llm']['model']}")

    rag = setup_rag(config, logger)
    rag_enabled = rag is not None
    if rag_enabled:
        logger.info("RAG system ready - agents can now search the codebase for context")

    results = {}
    cooldown = config.get("retry", {}).get("file_cooldown", 60)

    for idx, target_file in enumerate(target_files):
        if idx > 0 and cooldown > 0:
            logger.info(f"Cooling down {cooldown}s before next file (rate-limit avoidance)")
            time.sleep(cooldown)

        logger.info(f"Processing: {target_file}")
        start_time = time.time()

        try:
            compliance_scan = scan_file_for_compliance(target_file)
            compliance_summary = compliance_scan.get("summary", {})
            logger.info(
                "Compliance pre-scan for %s: critical=%s high=%s medium=%s low=%s",
                target_file,
                compliance_summary.get("critical", 0),
                compliance_summary.get("high", 0),
                compliance_summary.get("medium", 0),
                compliance_summary.get("low", 0),
            )

            backup_path = None
            if config.get("processing", {}).get("backup_originals", True):
                backup_path = backup_file(target_file, logger)

            agents = setup_agents(llm, config, target_file, rag_enabled=rag_enabled)
            tasks = setup_tasks(agents, target_file, config)
            crew = setup_crew(list(agents.values()), tasks, config)
            result = run_with_retry(crew, config, target_file, logger)

            # Generate diff if backup exists and diffs are enabled
            diff_path = None
            output_config = config.get("output", {})
            if backup_path and output_config.get("save_diffs", False):
                diffs_dir = output_config.get("diffs_dir", "diffs")
                diff_path = generate_diff(backup_path, target_file, diffs_dir, logger)

            inference_time = time.time() - start_time
            results[target_file] = {
                "status": "success",
                "backup": backup_path,
                "diff": diff_path,
                "result": str(result)[:200],
                "inference_time": inference_time,
                "compliance": compliance_scan,
            }

        except Exception as e:
            inference_time = time.time() - start_time
            logger.error(f"Failed to process {target_file}: {str(e)}")
            results[target_file] = {
                "status": "failed",
                "error": str(e),
                "inference_time": inference_time,
                "compliance": scan_file_for_compliance(target_file),
            }

    return results


def main() -> None:
    """Main entry point."""
    args = parse_args()
    logger = setup_logging(log_level=args.log_level)
    logger.info("CodeBase Agent Starting")
    logger.info(f"Python {sys.version}")

    try:
        config = load_config(args.config)
        logger.info(f"Loaded config from {args.config}")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)

    config = apply_cli_overrides(config, args, logger)
    results = process_files(config, logger)

    compliance_config = config.get("compliance", {})
    findings_path = compliance_config.get("findings_file", "reports/compliance_findings.json")
    audit_log_path = compliance_config.get("audit_log_file", "reports/compliance_audit_log.jsonl")
    artifacts = write_compliance_artifacts(results, findings_path, audit_log_path)
    logger.info(f"Compliance findings written to {artifacts['findings']}")
    logger.info(f"Compliance audit log written to {artifacts['audit_log']}")

    compliance_summary = aggregate_compliance(results).get("summary", {})
    logger.info(
        "Compliance summary: critical=%s high=%s medium=%s low=%s total=%s",
        compliance_summary.get("critical", 0),
        compliance_summary.get("high", 0),
        compliance_summary.get("medium", 0),
        compliance_summary.get("low", 0),
        compliance_summary.get("total", 0),
    )

    logger.info("Processing complete")
    generate_report(results, config, logger)

    successful = sum(1 for r in results.values() if r.get("status") == "success")
    logger.info(f"Results: {successful}/{len(results)} files processed successfully")

    fail_on_severity = compliance_config.get("fail_on_severity")
    if should_fail_quality_gate(results, fail_on_severity):
        logger.error(
            "Compliance quality gate failed: found issues with severity >= %s",
            fail_on_severity,
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
