from typing import Any

from crewai import Agent, Task, Crew, Process, LLM

from utils.tools import (
    read_file_tool,
    write_to_file_tool,
    run_pytest_tool,
    run_linter_tool,
    rag_search_tool,
    rag_context_tool,
    analyze_dependencies_tool,
    run_benchmark_tool,
)


def setup_agents(llm: LLM, config: dict, target_file: str, rag_enabled: bool = False) -> dict[str, Agent]:
    """Create agents with config settings. Only enabled agents are returned."""
    agent_config = config.get("agents", {})
    agents: dict[str, Agent] = {}

    analyst_tools: list[Any] = [read_file_tool, run_linter_tool, analyze_dependencies_tool]
    developer_tools: list[Any] = [read_file_tool, write_to_file_tool]
    qa_tools: list[Any] = [read_file_tool, write_to_file_tool, run_pytest_tool, run_benchmark_tool]

    if rag_enabled:
        analyst_tools.extend([rag_search_tool, rag_context_tool])
        developer_tools.extend([rag_search_tool, rag_context_tool])
        qa_tools.append(rag_search_tool)

    if agent_config.get("analyst", {}).get("enable", True):
        agents["analyst"] = Agent(
            role="Code Analyst",
            goal=(
                f"Analyze {target_file} for compliance and operational risk. "
                "Prioritize AML/KYC-relevant issues such as missing auditability, unsafe data handling, "
                "weak validation, and risky transaction paths. "
                "Map all cross-file dependencies to assess the blast radius of any refactoring."
            ),
            backstory="You are a strict, senior staff engineer who learns from existing codebase patterns. Be concise.",
            tools=analyst_tools,
            llm=llm,
            allow_delegation=False,
            max_iter=agent_config.get("analyst", {}).get("max_iter", 2),
        )

    if agent_config.get("developer", {}).get("enable", True):
        agents["developer"] = Agent(
            role="Python Developer",
            goal=f"Rewrite {target_file} to be efficient (O(n)), PEP8 compliant, fully type-hinted. Use RAG to find best practices from the codebase. Save using write_to_file_tool.",
            backstory="You execute perfectly by learning from existing code patterns. Be concise.",
            tools=developer_tools,
            llm=llm,
            allow_delegation=False,
            max_iter=agent_config.get("developer", {}).get("max_iter", 2),
        )

    if agent_config.get("qa_engineer", {}).get("enable", True):
        agents["qa_engineer"] = Agent(
            role="QA & Performance Engineer",
            goal=(
                f"Write pytest unit tests for {target_file}, save to disk, and run them. "
                "Then benchmark original vs refactored code and report any speedup or regression."
            ),
            backstory="You write rigorous tests and performance benchmarks, learning from existing patterns.",
            tools=qa_tools,
            llm=llm,
            allow_delegation=False,
            max_iter=agent_config.get("qa_engineer", {}).get("max_iter", 2),
        )

    return agents


def setup_tasks(
    agents: dict[str, Agent],
    target_file: str,
    config: dict,
) -> list[Task]:
    """Create tasks for enabled agents."""
    tasks: list[Task] = []
    _refactoring_level = config.get("processing", {}).get("refactoring_level", "aggressive")

    if "analyst" in agents:
        tasks.append(Task(
            description=(
                f"Read {target_file}. List the top 5 compliance and reliability findings with severity "
                "(critical/high/medium/low), evidence, and concrete fix. Prioritize AML/KYC impact first. "
                f"Also analyze all cross-file dependencies for {target_file} and report the dependency graph."
            ),
            expected_output="Bulleted list of 5 compliance findings with severity, evidence, and fixes, plus a dependency graph.",
            agent=agents["analyst"],
        ))

    if "developer" in agents:
        tasks.append(Task(
            description=f"Rewrite {target_file}: fix O(n^2) loops with Sets, add type hints, improve naming. Save to disk.",
            expected_output="Confirmation that file was saved with efficient code.",
            agent=agents["developer"],
        ))

    if "qa_engineer" in agents:
        test_file = target_file.replace(".py", "_test.py") if "_test" not in target_file else target_file
        tasks.append(Task(
            description=(
                f"Write pytest tests for refactored code, save to {test_file}, run pytest. "
                f"Then benchmark original vs refactored {target_file} and report timing improvements."
            ),
            expected_output="Pytest output showing all tests pass plus benchmark report with speedup percentage.",
            agent=agents["qa_engineer"],
        ))

    return tasks


def setup_crew(agents: list[Agent], tasks: list[Task], config: dict) -> Crew:
    """Create the CrewAI crew."""
    crew_config = config.get("crew", {})
    process = Process.sequential if crew_config.get("process") == "sequential" else Process.hierarchical

    return Crew(
        agents=agents,
        tasks=tasks,
        process=process,
        verbose=crew_config.get("verbose", True),
        memory=crew_config.get("memory", False),
        max_rpm=crew_config.get("max_rpm", 1),
    )
