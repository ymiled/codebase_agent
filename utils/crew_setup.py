from typing import Any

from crewai import Agent, Task, Crew, Process, LLM

from utils.compliance import RULES
from utils.tools import (
    read_file_tool,
    write_to_file_tool,
    run_pytest_tool,
    run_linter_tool,
    rag_search_tool,
    rag_context_tool,
    analyze_dependencies_tool,
    run_benchmark_tool,
    check_compliance_tool,
)


def setup_agents(llm: LLM, config: dict, target_file: str, rag_enabled: bool = False) -> dict[str, Agent]:
    """Create agents with config settings. Only enabled agents are returned."""
    agent_config = config.get("agents", {})
    agents: dict[str, Agent] = {}

    analyst_tools: list[Any] = [read_file_tool, run_linter_tool, analyze_dependencies_tool]
    developer_tools: list[Any] = [read_file_tool, write_to_file_tool, check_compliance_tool]
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
            goal=(
                f"Rewrite {target_file} to be efficient (O(n)), PEP8 compliant, fully type-hinted, "
                "and free of compliance violations. "
                "WORKFLOW: 1) read_file_tool to read the file, 2) refactor the code, "
                "3) write_to_file_tool to save, 4) check_compliance_tool with the file path to validate "
                "— if violations are found, read the file, fix them, write again, and re-check. "
                "NEVER write `except Exception` — always use specific "
                "exception types like ValueError, TypeError, OSError, KeyError."
            ),
            backstory="You execute perfectly by learning from existing code patterns. You always use tools to read and write files. Be concise.",
            tools=developer_tools,
            llm=llm,
            allow_delegation=False,
            max_iter=agent_config.get("developer", {}).get("max_iter", 4),
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


def _format_findings_for_prompt(findings: list[dict]) -> str:
    """Format compliance findings as a concise string for agent prompts."""
    if not findings:
        return "No compliance findings from pre-scan."
    lines = []
    for f in findings:
        lines.append(f"- [{f.get('severity', '?').upper()}] {f.get('rule_id', '?')}: "
                      f"{f.get('description', '')} (line {f.get('line', '?')})")
    return "\n".join(lines)


def _format_banned_patterns() -> str:
    """Build a short reference of banned regex patterns from compliance rules."""
    lines = []
    for r in RULES:
        if r["severity"] in ("critical", "high", "medium"):
            lines.append(
                f"- {r['rule_id']} ({r['severity']}): regex `{r['regex']}` — {r['description']} "
                f"Fix: {r['recommendation']}"
            )
    return "\n".join(lines)


def build_compliance_repair_task(developer_agent: Agent, target_file: str, findings: list[dict]) -> Task:
    """Create a focused repair task that feeds post-scan findings back to the developer."""
    banned_patterns = _format_banned_patterns()
    findings_text = _format_findings_for_prompt(findings)

    # Build concrete per-finding fix examples
    fix_lines = []
    for f in findings:
        line = f.get("line", "?")
        evidence = f.get("evidence", "")
        rule = f.get("rule_id", "")
        if "except Exception" in evidence or "except:" in evidence:
            fix_lines.append(
                f"  Line {line}: change `{evidence.strip()}` to a specific type "
                f"like `except (ValueError, TypeError, KeyError) as e:` or just `except ValueError as e:`"
            )
        elif "execute" in evidence.lower() and ("f\"" in evidence or "f\'" in evidence):
            fix_lines.append(
                f"  Line {line}: replace f-string SQL with parameterized query "
                f"e.g. cursor.execute('INSERT INTO t VALUES (?, ?)', (val1, val2))"
            )
        elif "open" in evidence.lower() and "'w'" in evidence:
            fix_lines.append(
                f"  Line {line} ({rule}): wrap the file write with structured logging. "
                f"Add logger.info() before and after the open() call."
            )
        else:
            fix_lines.append(
                f"  Line {line} ({rule}): `{evidence.strip()}` — see recommendation above"
            )
    concrete_fixes = "\n".join(fix_lines)

    return Task(
        description=(
            f"The file {target_file} was refactored but STILL has compliance violations.\n\n"
            f"REMAINING FINDINGS (you MUST fix ALL of these):\n{findings_text}\n\n"
            f"CONCRETE FIXES NEEDED:\n{concrete_fixes}\n\n"
            f"STEP 1: Use read_file_tool to read {target_file}\n"
            f"STEP 2: Fix the specific lines listed above\n"
            f"STEP 3: Use write_to_file_tool to save the fixed file to {target_file}\n\n"
            f"BANNED PATTERNS (your code must NOT match these regexes):\n{banned_patterns}\n\n"
            "CRITICAL — the regex `except\\s+Exception` matches ANY `except Exception` including "
            "`except Exception as e:`. You MUST replace every such line with SPECIFIC exception types.\n"
            "WRONG: except Exception as e:\n"
            "RIGHT: except (ValueError, TypeError) as e:\n"
            "RIGHT: except ValueError as e:\n"
            "RIGHT: except OSError as e:\n\n"
            "For file writes (open(..., 'w')), the regex `open\\s*\\(\\s*[\"'][^\"']+[\"']\\s*,\\s*[\"']w[\"']` "
            "flags them. Fix by REMOVING direct open() calls in business logic, or wrapping them with "
            "structured logging (logger.info before and after the write).\n\n"
            "You MUST call read_file_tool and write_to_file_tool. Do NOT just describe fixes."
        ),
        expected_output=f"Confirmation that {target_file} was read, fixed, and saved with write_to_file_tool.",
        agent=developer_agent,
    )


def setup_tasks(
    agents: dict[str, Agent],
    target_file: str,
    config: dict,
    compliance_findings: list[dict] | None = None,
) -> list[Task]:
    """Create tasks for enabled agents."""
    tasks: list[Task] = []
    _refactoring_level = config.get("processing", {}).get("refactoring_level", "aggressive")
    findings_text = _format_findings_for_prompt(compliance_findings or [])

    if "analyst" in agents:
        tasks.append(Task(
            description=(
                f"Read {target_file}. The compliance pre-scan found these issues:\n{findings_text}\n\n"
                "Verify each finding above, identify any additional issues the regex missed, and list "
                "the top 5 compliance and reliability findings with severity "
                "(critical/high/medium/low), evidence, and concrete fix. Prioritize AML/KYC impact first. "
                f"Also analyze all cross-file dependencies for {target_file} and report the dependency graph."
            ),
            expected_output="Bulleted list of 5 compliance findings with severity, evidence, and fixes, plus a dependency graph.",
            agent=agents["analyst"],
        ))

    if "developer" in agents:
        banned_patterns = _format_banned_patterns()
        tasks.append(Task(
            description=(
                f"Rewrite {target_file}: fix O(n^2) loops with Sets, add type hints, improve naming.\n\n"
                f"COMPLIANCE FINDINGS from pre-scan (you MUST fix ALL of these):\n{findings_text}\n\n"
                f"BANNED CODE PATTERNS — the automated compliance scanner uses these regexes. "
                f"Your output MUST NOT match ANY of them:\n{banned_patterns}\n\n"
                "MANDATORY VALIDATION STEP — after writing the file with write_to_file_tool, "
                "you MUST call check_compliance_tool with the file path to verify compliance. "
                "If it reports violations, read the file, fix them, write again, and re-check "
                "until it returns PASSED.\n\n"
                "KEY RULES:\n"
                "- NEVER write `except Exception`. Use specific types like `except ValueError`, "
                "`except TypeError`, `except OSError`, `except (TypeError, ValueError)`, etc.\n"
                "- NEVER use bare `except:`. Always specify the exception type.\n"
                "- NEVER use f-string or .format() inside cursor.execute(). Use parameterized queries: "
                "cursor.execute('INSERT INTO t VALUES (?, ?)', (val1, val2))\n"
                "- NEVER use eval(), exec(), or shell=True.\n"
                "- Avoid top-level mutable globals like SOME_NAME = []. Use function-scoped variables "
                "or immutable types (tuple, frozenset).\n"
                "- Do NOT use os._exit(). Use sys.exit() instead.\n"
                "- Wrap ALL file writes (open(..., 'w')) with structured logging — log before and after "
                "the write, and handle write failures. Example:\n"
                "    logger.info('Writing report to %s', path)\n"
                "    with open(path, 'w') as f:\n"
                "        f.write(content)\n"
                "    logger.info('Report written successfully')\n\n"
                "Save the rewritten file using write_to_file_tool."
            ),
            expected_output="Confirmation that file was saved with compliant, efficient code that avoids all banned patterns.",
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
