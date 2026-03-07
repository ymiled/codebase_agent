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
)
from utils.crew_setup import setup_agents, setup_tasks, setup_crew

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

    for target_file in target_files:
        logger.info(f"Processing: {target_file}")
        start_time = time.time()

        try:
            backup_path = None
            if config.get("processing", {}).get("backup_originals", True):
                backup_path = backup_file(target_file, logger)

            agents = setup_agents(llm, config, target_file, rag_enabled=rag_enabled)
            tasks = setup_tasks(*agents, target_file, config)
            crew = setup_crew(agents, tasks, config)
            result = run_with_retry(crew, config, target_file, logger)

            inference_time = time.time() - start_time
            results[target_file] = {
                "status": "success",
                "backup": backup_path,
                "result": str(result)[:200],
                "inference_time": inference_time,
            }

        except Exception as e:
            inference_time = time.time() - start_time
            logger.error(f"Failed to process {target_file}: {str(e)}")
            results[target_file] = {
                "status": "failed",
                "error": str(e),
                "inference_time": inference_time,
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

    logger.info("Processing complete")
    generate_report(results, config, logger)

    successful = sum(1 for r in results.values() if r.get("status") == "success")
    logger.info(f"Results: {successful}/{len(results)} files processed successfully")


if __name__ == "__main__":
    main()
