from typing import Any, Tuple

from crewai import Agent, Task, Crew, Process, LLM

from utils.tools import (
    read_file_tool,
    write_to_file_tool,
    run_pytest_tool,
    run_linter_tool,
    rag_search_tool,
    rag_context_tool,
)


def setup_agents(llm: LLM, config: dict, target_file: str, rag_enabled: bool = False) -> Tuple[Agent, Agent, Agent]:
    """Create agents with config settings."""
    agent_config = config.get("agents", {})

    # Tool signatures differ; keep this list generic for composition.
    architect_tools: list[Any] = [read_file_tool, run_linter_tool]
    developer_tools: list[Any] = [read_file_tool, write_to_file_tool]
    qa_tools: list[Any] = [read_file_tool, write_to_file_tool, run_pytest_tool]

    if rag_enabled:
        architect_tools.extend([rag_search_tool, rag_context_tool])
        developer_tools.extend([rag_search_tool, rag_context_tool])
        qa_tools.append(rag_search_tool)

    architect = Agent(
        role="System Architect",
        goal=f"Analyze {target_file} for inefficiencies. Identify: O(n^2) loops, poor naming, missing type hints. Use RAG tools to find similar patterns in the codebase.",
        backstory="You are a strict, senior staff engineer who learns from existing codebase patterns. Be concise.",
        tools=architect_tools,
        llm=llm,
        allow_delegation=False,
        max_iter=agent_config.get("architect", {}).get("max_iter", 2),
    )

    developer = Agent(
        role="Python Developer",
        goal=f"Rewrite {target_file} to be efficient (O(n)), PEP8 compliant, fully type-hinted. Use RAG to find best practices from the codebase. Save using write_to_file_tool.",
        backstory="You execute perfectly by learning from existing code patterns. Be concise.",
        tools=developer_tools,
        llm=llm,
        allow_delegation=False,
        max_iter=agent_config.get("developer", {}).get("max_iter", 2),
    )

    qa_engineer = Agent(
        role="QA Automation Engineer",
        goal=f"Write pytest unit tests for {target_file}, save to disk, and run them. Use RAG to find existing test patterns.",
        backstory="You write rigorous tests and execute them, learning from existing test patterns.",
        tools=qa_tools,
        llm=llm,
        allow_delegation=False,
        max_iter=agent_config.get("qa_engineer", {}).get("max_iter", 2),
    )

    return architect, developer, qa_engineer


def setup_tasks(
    architect: Agent,
    developer: Agent,
    qa_engineer: Agent,
    target_file: str,
    config: dict,
) -> Tuple[Task, Task, Task]:
    """Create tasks for the agents."""
    _refactoring_level = config.get("processing", {}).get("refactoring_level", "aggressive")

    analysis_task = Task(
        description=f"Read {target_file}. List the top 5 code smells and how to fix them. Be concise.",
        expected_output="Bulleted list of 5 code smells with fixes.",
        agent=architect,
    )

    refactor_task = Task(
        description=f"Rewrite {target_file}: fix O(n^2) loops with Sets, add type hints, improve naming. Save to disk.",
        expected_output="Confirmation that file was saved with efficient code.",
        agent=developer,
    )

    test_file = target_file.replace(".py", "_test.py") if "_test" not in target_file else target_file
    test_task = Task(
        description=f"Write pytest tests for refactored code, save to {test_file}, run pytest.",
        expected_output="Pytest output showing all tests pass.",
        agent=qa_engineer,
    )

    return analysis_task, refactor_task, test_task


def setup_crew(agents: Tuple[Agent, Agent, Agent], tasks: Tuple[Task, Task, Task], config: dict) -> Crew:
    """Create the CrewAI crew."""
    crew_config = config.get("crew", {})
    process = Process.sequential if crew_config.get("process") == "sequential" else Process.hierarchical

    return Crew(
        agents=list(agents),
        tasks=list(tasks),
        process=process,
        verbose=crew_config.get("verbose", True),
        memory=crew_config.get("memory", False),
        max_rpm=crew_config.get("max_rpm", 1),
    )
