import os
import time
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from tools import read_file_tool, write_file_tool, run_pytest_tool, run_linter_tool, web_search_tool
from crewai import LLM

load_dotenv()  # Loads API key

llm = LLM(
    model="groq/llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.0,  # Deterministic output to reduce tokens
    max_tokens=1024   
)

# Agents definitions
architect = Agent(
    role='System Architect',
    goal='Analyze target_repo/bad_code.py for inefficiencies. Identify: O(n^2) loops, poor naming, missing type hints.',
    backstory='You are a strict, senior staff engineer. Be concise.',
    tools=[read_file_tool, run_linter_tool],
    llm=llm,
    allow_delegation=False,
    max_iter=2
)

developer = Agent(
    role='Python Developer',
    goal='Rewrite code to be efficient (O(n)), PEP8 compliant, fully type-hinted. Save using write_file_tool.',
    backstory='You execute perfectly. Be concise.',
    tools=[read_file_tool, write_file_tool],
    llm=llm,
    allow_delegation=False,
    max_iter=2
)

qa_engineer = Agent(
    role='QA Automation Engineer',
    goal='Write pytest unit tests, save to disk, and run them.',
    backstory='You write rigorous tests and execute them.',
    tools=[read_file_tool, write_file_tool, run_pytest_tool],
    llm=llm,
    allow_delegation=False,
    max_iter=2
)

# Tasks definitions
analysis_task = Task(
    description='Read target_repo/bad_code.py. List the top 5 code smells and how to fix them. Be concise.',
    expected_output='Bulleted list of 5 code smells with fixes.',
    agent=architect
)

refactor_task = Task(
    description='Rewrite target_repo/bad_code.py: fix O(n^2) loops with Sets, add type hints, improve naming. Save to disk.',
    expected_output='Confirmation that file was saved with efficient code.',
    agent=developer
)

test_task = Task(
    description='Write pytest tests for refactored code, save to target_repo/test_bad_code.py, run pytest.',
    expected_output='Pytest output showing all tests pass.',
    agent=qa_engineer
)

# Crew definition - optimized for rate limit avoidance
code_crew = Crew(
    agents=[architect, developer, qa_engineer],
    tasks=[analysis_task, refactor_task, test_task],
    process=Process.sequential, 
    verbose=True,
    memory=False,  # Disable memory to save tokens
    max_rpm=1 
)

def run_with_retry(max_retries=3):
    """Run the crew with exponential backoff retry logic for rate limits."""
    for attempt in range(max_retries):
        try:
            print(f"\nStarting Meta-Agent Crew (Attempt {attempt + 1}/{max_retries})...\n")
            result = code_crew.kickoff()
            print("\n Final result:\n")
            print(result)
            return result
        except Exception as e:
            error_msg = str(e).lower()
            if "rate_limit" in error_msg or "tokens per minute" in error_msg:
                wait_time = (2 ** attempt) * 15  # Exponential backoff: 15s, 30s, 60s
                print(f"\nRate limit hit. Waiting {wait_time}s before retry...\n")
                time.sleep(wait_time)
                if attempt == max_retries - 1:
                    print("Failed after max retries. Please wait a few minutes before trying again.")
                    raise
            else:
                raise

if __name__ == "__main__":
    run_with_retry()