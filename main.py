import os
import time
import sys
import argparse
import logging
import shutil
from typing import Any, Optional
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import yaml
from crewai import Agent, Task, Crew, Process
from tools import read_file_tool, write_file_tool, run_pytest_tool, run_linter_tool
from crewai import LLM

load_dotenv()


def setup_logging(log_file: str = "logs/codebase_agent.log"):
    """Configure logging to both console and file."""
    Path(log_file).parent.mkdir(parents=True, exist_ok=True) 
    
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    
    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger

def load_config(config_file: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"Config file not found: {config_file}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    return config

# Backup utilities
def backup_file(file_path: str) -> Optional[str]:
    """Create a backup of the original file."""
    backup_dir = Path("backups") / datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    original_file = Path(file_path)
    backup_file = backup_dir / original_file.name
    
    if original_file.exists():
        shutil.copy2(original_file, backup_file)
        logger.info(f"Backed up {file_path} to {backup_file}")
        return str(backup_file)
    return None


# LLM setup
def setup_llm(config: dict) -> LLM:
    """Initialize LLM with config settings."""
    llm_config = config.get('llm', {})
    return LLM(
        model=llm_config.get('model', 'groq/llama-3.3-70b-versatile'),
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=llm_config.get('temperature', 0.0),
        max_tokens=llm_config.get('max_tokens', 1024)
    )

# Agents setup
def setup_agents(llm: LLM, config: dict, target_file: str) -> tuple:
    """Create agents with config settings."""
    agent_config = config.get('agents', {})
    
    architect = Agent(
        role='System Architect',
        goal=f'Analyze {target_file} for inefficiencies. Identify: O(n^2) loops, poor naming, missing type hints.',
        backstory='You are a strict, senior staff engineer. Be concise.',
        tools=[read_file_tool, run_linter_tool],
        llm=llm,
        allow_delegation=False,
        max_iter=agent_config.get('architect', {}).get('max_iter', 2)
    )
    
    developer = Agent(
        role='Python Developer',
        goal=f'Rewrite {target_file} to be efficient (O(n)), PEP8 compliant, fully type-hinted. Save using write_file_tool.',
        backstory='You execute perfectly. Be concise.',
        tools=[read_file_tool, write_file_tool],
        llm=llm,
        allow_delegation=False,
        max_iter=agent_config.get('developer', {}).get('max_iter', 2)
    )
    
    qa_engineer = Agent(
        role='QA Automation Engineer',
        goal=f'Write pytest unit tests for {target_file}, save to disk, and run them.',
        backstory='You write rigorous tests and execute them.',
        tools=[read_file_tool, write_file_tool, run_pytest_tool],
        llm=llm,
        allow_delegation=False,
        max_iter=agent_config.get('qa_engineer', {}).get('max_iter', 2)
    )
    
    return architect, developer, qa_engineer

# Tasks setup
def setup_tasks(architect, developer, qa_engineer, target_file: str, config: dict) -> tuple:
    """Create tasks for the agents."""
    refactoring_level = config.get('processing', {}).get('refactoring_level', 'aggressive')
    
    analysis_task = Task(
        description=f'Read {target_file}. List the top 5 code smells and how to fix them. Be concise.',
        expected_output='Bulleted list of 5 code smells with fixes.',
        agent=architect
    )
    
    refactor_task = Task(
        description=f'Rewrite {target_file}: fix O(n^2) loops with Sets, add type hints, improve naming. Save to disk.',
        expected_output='Confirmation that file was saved with efficient code.',
        agent=developer
    )
    
    test_file = target_file.replace('.py', '_test.py') if '_test' not in target_file else target_file
    test_task = Task(
        description=f'Write pytest tests for refactored code, save to {test_file}, run pytest.',
        expected_output='Pytest output showing all tests pass.',
        agent=qa_engineer
    )
    
    return analysis_task, refactor_task, test_task

# Crew setup
def setup_crew(agents: tuple, tasks: tuple, config: dict) -> Crew:
    """Create the CrewAI crew."""
    crew_config = config.get('crew', {})
    process = Process.sequential if crew_config.get('process') == 'sequential' else Process.hierarchical
    
    return Crew(
        agents=list(agents),
        tasks=list(tasks),
        process=process,
        verbose=crew_config.get('verbose', True),
        memory=crew_config.get('memory', False),
        max_rpm=crew_config.get('max_rpm', 1)
    )

# Retry logic
def run_with_retry(crew: Crew, config: dict, target_file: str) -> Any:
    """Run the crew with exponential backoff retry logic."""
    retry_config = config.get('retry', {})
    max_retries = retry_config.get('max_retries', 3)
    backoff_multiplier = retry_config.get('backoff_multiplier', 15)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"\n{'='*70}")
            logger.info(f"Processing: {target_file} (Attempt {attempt + 1}/{max_retries})")
            logger.info(f"{'='*70}\n")
            
            result = crew.kickoff()
            
            logger.info(f"\nCOMPLETED: {target_file}")
            logger.info(f"{'='*70}\n")
            
            return result
        except Exception as e:
            error_msg = str(e).lower()
            if "rate_limit" in error_msg or "tokens per minute" in error_msg:
                wait_time = (2 ** attempt) * backoff_multiplier
                logger.warning(f"Rate limit hit. Waiting {wait_time}s before retry...\n")
                time.sleep(wait_time)
                if attempt == max_retries - 1:
                    logger.error(f"Failed {target_file} after {max_retries} retries.")
                    raise
            else:
                logger.error(f"Error processing {target_file}: {str(e)}")
                raise

    raise RuntimeError(f"Unable to process {target_file} after {max_retries} retries")

# Report generation
def generate_report(results: dict, config: dict):
    """Generate an HTML report of refactoring results."""
    report_file = config.get('output', {}).get('report_file', 'reports/refactoring_report.html')
    Path(report_file).parent.mkdir(parents=True, exist_ok=True)

    total_inference_time = sum(
        r.get('inference_time_seconds', 0.0)
        for r in results.values()
        if isinstance(r.get('inference_time_seconds', 0.0), (int, float))
    )
    successful_count = sum(1 for r in results.values() if r.get('status') == 'success')
    failed_count = sum(1 for r in results.values() if r.get('status') == 'failed')
    average_inference_time = (
        total_inference_time / len(results)
        if results else 0.0
    )
    
    html_content = f"""
    <html>
    <head>
        <title>CodeBase Agent Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            h1 {{ color: #333; }}
            .success {{ color: green; }}
            .file {{ background: #f5f5f5; padding: 15px; margin: 10px 0; border-left: 4px solid #4CAF50; }}
            .summary {{ background: #e8f5e9; padding: 15px; margin: 10px 0; border-radius: 5px; }}
            pre {{ background: #f9f9f9; padding: 10px; overflow-x: auto; }}
        </style>
    </head>
    <body>
        <h1>CodeBase Agent Refactoring Report</h1>
        <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <div class="summary">
            <h2>Summary</h2>
            <p>Total files processed: {len(results)}</p>
            <p>Successful: {successful_count}</p>
            <p>Failed: {failed_count}</p>
            <p>Total inference time: {total_inference_time:.2f}s</p>
            <p>Average inference time per file: {average_inference_time:.2f}s</p>
        </div>
    """
    
    for file_name, result in results.items():
        status_class = "success" if result.get('status') == 'success' else "error"
        html_content += f"""
        <div class="file">
            <h3 class="{status_class}">{file_name}</h3>
            <p><strong>Status:</strong> {result.get('status', 'Unknown')}</p>
            <p><strong>Backup:</strong> {result.get('backup', 'N/A')}</p>
            <p><strong>Inference time:</strong> {result.get('inference_time_seconds', 0.0):.2f}s</p>
        </div>
        """
    
    html_content += """
    </body>
    </html>
    """
    
    with open(report_file, 'w') as f:
        f.write(html_content)
    
    logger.info(f"Report saved to {report_file}")



def main():
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description='CodeBase Agent - Automated Code Refactoring',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            python main.py                              # Use config.yaml (default)
            python main.py --file target_repo/bad_code.py
            python main.py --config custom_config.yaml
            python main.py --aggressive
            python main.py --no-backup
            python main.py --file file1.py --file file2.py
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        action='append',
        dest='files',
        help='Target file(s) to refactor (can use multiple times)'
    )
    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Configuration file (default: config.yaml)'
    )
    parser.add_argument(
        '--aggressive', '-a',
        action='store_true',
        help='Use aggressive refactoring (more changes)'
    )
    parser.add_argument(
        '--conservative',
        action='store_true',
        help='Use conservative refactoring (minimal changes)'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Do not backup original files'
    )
    parser.add_argument(
        '--log-level', '-l',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    global logger
    logger = setup_logging()
    logger.info("CodeBase Agent starting")
    logger.info(f"Python {sys.version}")
    
    # Load configuration
    try:
        config = load_config(args.config)
        logger.info(f"Loaded config from {args.config}")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    
    # Override config with CLI arguments
    if args.files:
        config['processing']['files'] = args.files
        logger.info(f"Override files: {args.files}")
    
    if args.aggressive:
        config['processing']['refactoring_level'] = 'aggressive'
        logger.info("Using aggressive refactoring level")
    
    if args.conservative:
        config['processing']['refactoring_level'] = 'conservative'
        logger.info("Using conservative refactoring level")
    
    if args.no_backup:
        config['processing']['backup_originals'] = False
        logger.info("Backup disabled")
    
    # Get target files
    target_files = config.get('processing', {}).get('files', ['target_repo/bad_code.py'])
    logger.info(f"Processing {len(target_files)} file(s)")
    
    # Setup LLM
    llm = setup_llm(config)
    logger.info(f"LLM configured: {config['llm']['model']}")
    
    # Process each file
    results = {}
    
    for target_file in target_files:
        logger.info(f"\n{'─'*70}")
        logger.info(f"Processing: {target_file}")
        logger.info(f"{'─'*70}")
        
        try:
            # Backup original file
            backup_path = None
            if config.get('processing', {}).get('backup_originals', True):
                backup_path = backup_file(target_file)
            
            # Setup agents and tasks
            agents = setup_agents(llm, config, target_file)
            tasks = setup_tasks(agents[0], agents[1], agents[2], target_file, config)
            
            # Create and run crew
            crew = setup_crew(agents, tasks, config)
            inference_start = time.perf_counter()
            result = run_with_retry(crew, config, target_file)
            inference_time_seconds = time.perf_counter() - inference_start
            logger.info(f"Inference time for {target_file}: {inference_time_seconds:.2f}s")
            
            results[target_file] = {
                'status': 'success',
                'backup': backup_path,
                'inference_time_seconds': inference_time_seconds,
                'result': str(result)[:200]  # Truncate for report
            }
            
        except Exception as e:
            logger.error(f"Failed to process {target_file}: {str(e)}")
            results[target_file] = {
                'status': 'failed',
                'inference_time_seconds': 0.0,
                'error': str(e)
            }
    
    # Generate report
    logger.info(f"\n{'='*70}")
    logger.info("Processing complete")
    logger.info(f"{'='*70}")
    generate_report(results, config)
    
    # Summary
    successful = sum(1 for r in results.values() if r.get('status') == 'success')
    logger.info(f"\nResults: {successful}/{len(results)} files processed successfully")

if __name__ == "__main__":
    main()