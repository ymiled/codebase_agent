from crewai.tools import tool
import re
import subprocess
import os
from langchain_community.tools import DuckDuckGoSearchRun
from utils.rag_system import RAGCodebaseIndex
from utils.compliance import RULES

# Global RAG instance (will be initialized in main.py)
_rag_instance = None

def set_rag_instance(rag: RAGCodebaseIndex):
    """Set the global RAG instance for tools to use."""
    global _rag_instance
    _rag_instance = rag

@tool("Read File Tool")
def read_file_tool(file_path: str) -> str:
    """Reads the content of a file. Use this to analyze code."""
    try:
        with open(file_path, 'r') as f:
            return f.read()
    except Exception as e:
        return f"Failed to read file: {str(e)}"

@tool("Write to File Tool")
def write_to_file_tool(file_path: str, content: str) -> str:
    """Overwrites a file with new content. Extremely useful for refactoring."""
    try:
        real_path = os.path.realpath(file_path)
        allowed_dir = os.path.realpath("target_repo")
        if not real_path.startswith(allowed_dir + os.sep) and real_path != allowed_dir:
            return "Error: Unauthorized path. Only write to target_repo/"

        with open(file_path, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {file_path}"
    except Exception as e:
        return f"Failed to write file: {str(e)}"

@tool("Run Pytest Tool")
def run_pytest_tool(test_file_path: str) -> str:
    """Runs pytest on the specified file and returns the output."""
    try:
        result = subprocess.run(
            ['pytest', test_file_path, '-v'], 
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return f"Tests Passed!\n{result.stdout}"
        else:
            return f"Tests Failed!\n{result.stdout}\n{result.stderr}"
    except Exception as e:
        return f"Test execution failed: {str(e)}"


search_inner = DuckDuckGoSearchRun()

@tool("web_search_tool")
def web_search_tool(query: str):
    """Search the internet for Python best practices, documentation, and latest library updates."""
    return search_inner.run(query)

@tool("Run Linter Tool")
def run_linter_tool(file_path: str) -> str:
    """Runs flake8 on the code to find syntax and style errors."""
    result = subprocess.run(['flake8', file_path], capture_output=True, text=True)
    return result.stdout if result.stdout else "Linting passed with no errors."

@tool("RAG Search Tool")
def rag_search_tool(query: str, n_results: str = "3") -> str:
    """
    Search the codebase for relevant code examples and patterns using semantic search.
    Use this to find similar functions, patterns, or best practices already in the codebase.
    
    Args:
        query: What to search for (e.g., "error handling", "list comprehension", "sorting algorithms")
        n_results: Number of relevant code snippets to return as a string (default: "3")
    
    Returns:
        Relevant code snippets with file paths and context
    """
    global _rag_instance
    
    # Groq LLM sometimes passes n_results as a string; coerce to int
    try:
        n_results_int = int(n_results)
    except (TypeError, ValueError):
        n_results_int = 3
    
    if _rag_instance is None:
        return "RAG system not initialized. Enable 'rag.enable' in config.yaml"
    
    try:
        results = _rag_instance.search(query, n_results=n_results_int)
        
        if not results:
            return f"No relevant code found for: {query}"
        
        # Format results for agent consumption
        formatted_output = f"Found {len(results)} relevant code snippets for '{query}':\n\n"
        
        for i, result in enumerate(results, 1):
            relevance = 1 - result['distance'] if result['distance'] else 1.0
            formatted_output += f"--- Result {i} (relevance: {relevance:.2f}) ---\n"
            formatted_output += f"File: {result['file_path']}\n"
            formatted_output += f"Code:\n```python\n{result['code']}\n```\n\n"
        
        return formatted_output
    except Exception as e:
        return f"RAG search failed: {str(e)}"

@tool("RAG Context Tool")
def rag_context_tool(file_path: str, query: str = "similar patterns and implementations") -> str:
    """
    Retrieve relevant codebase context when refactoring a specific file.
    Automatically finds similar code, patterns, and best practices from other files.
    
    Args:
        file_path: The file being refactored
        query: What kind of context to retrieve (optional)
    
    Returns:
        Relevant code snippets that can inform the refactoring
    """
    global _rag_instance
    
    if _rag_instance is None:
        return "RAG system not initialized. Enable 'rag.enable' in config.yaml"
    
    try:
        context_snippets = _rag_instance.search_for_file(
            file_path=file_path,
            query=query,
            n_results=3
        )
        
        if not context_snippets:
            return f"No relevant context found in the codebase for {file_path}"
        
        output = f"Relevant codebase context for refactoring {os.path.basename(file_path)}:\n\n"
        output += "\n\n".join(context_snippets)
        
        return output
    except Exception as e:
        return f"Failed to retrieve context: {str(e)}"

@tool("Analyze Dependencies Tool")
def analyze_dependencies_tool(target_file: str, search_directory: str = "target_repo") -> str:
    """
    Analyze cross-file dependencies for a target file.
    Finds all imports FROM this file and all imports TO this file from other files.
    
    Args:
        target_file: The file to analyze (e.g., 'target_repo/bad_code_1.py')
        search_directory: Directory to search for files that depend on target (default: 'target_repo')
    
    Returns:
        A dependency graph showing relationships between files
    """
    import ast
    import re
    
    try:
        # Read target file
        if not os.path.exists(target_file):
            return f"Error: Target file {target_file} not found"
        
        with open(target_file, 'r') as f:
            target_content = f.read()
        
        # Parse imports from target file
        try:
            tree = ast.parse(target_content)
            imports_from_target = set()
            functions_in_target = set()
            classes_in_target = set()
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports_from_target.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports_from_target.add(node.module)
                elif isinstance(node, ast.FunctionDef):
                    functions_in_target.add(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes_in_target.add(node.name)
        except SyntaxError as e:
            return f"Syntax error in target file: {e}"
        
        # Find files that import from target
        imports_to_target = []
        if os.path.exists(search_directory):
            for root, dirs, files in os.walk(search_directory):
                for file in files:
                    if file.endswith('.py') and file != os.path.basename(target_file):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r') as f:
                                content = f.read()
                            
                            # Search for imports of target module
                            target_name = os.path.splitext(os.path.basename(target_file))[0]
                            if target_name in content and ('import ' + target_name in content or 'from ' + target_name in content):
                                imports_to_target.append(file_path)
                        except:
                            pass
        
        # Build dependency report
        report = f"=== Dependency Analysis for {os.path.basename(target_file)} ===\n\n"
        report += f"IMPORTS FROM THIS FILE:\n"
        report += f"  External modules: {', '.join(sorted(imports_from_target)) if imports_from_target else 'None'}\n\n"
        report += f"EXPORTS FROM THIS FILE:\n"
        report += f"  Functions: {', '.join(sorted(functions_in_target)) if functions_in_target else 'None'}\n"
        report += f"  Classes: {', '.join(sorted(classes_in_target)) if classes_in_target else 'None'}\n\n"
        report += f"FILES THAT DEPEND ON THIS FILE:\n"
        if imports_to_target:
            for dep_file in imports_to_target:
                report += f"  - {dep_file}\n"
        else:
            report += "  None found\n"
        
        return report
        
    except Exception as e:
        return f"Dependency analysis failed: {str(e)}"

@tool("Run Benchmark Tool")
def run_benchmark_tool(original_file: str, refactored_file: str = None) -> str:
    """
    Run performance benchmarks comparing original vs refactored code.
    If no refactored file provided, searches for a *_test.py version.
    
    Args:
        original_file: Path to original file (or the refactored one to compare)
        refactored_file: Path to refactored version (optional)
    
    Returns:
        Benchmark results with timing comparisons
    """
    import timeit
    import tempfile
    import importlib.util
    
    try:
        # Determine which files to benchmark
        original = original_file
        refactored = refactored_file
        
        # Try to find test file if refactored not specified
        if not refactored:
            base_name = original.replace('.py', '')
            potential_test = base_name + '_test.py'
            if os.path.exists(potential_test):
                refactored = potential_test
            else:
                return f"Cannot benchmark: no refactored file found. Provide refactored_file path."
        
        if not os.path.exists(original) or not os.path.exists(refactored):
            return f"File not found: original={os.path.exists(original)}, refactored={os.path.exists(refactored)}"
        
        # Extract main functions to benchmark
        def extract_main_function(file_path):
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Find first function definition
            match = re.search(r'def (\w+)\(', content)
            if match:
                return match.group(1), content
            return None, content
        
        original_func_name, original_code = extract_main_function(original)
        refactored_func_name, refactored_code = extract_main_function(refactored)
        
        if not original_func_name or not refactored_func_name:
            return "Could not find function definitions to benchmark"
        
        # Run benchmarks
        try:
            original_time = timeit.timeit(
                f'{original_func_name}([1, 2, 3, 4, 5])',
                setup=original_code,
                number=1000
            )
        except:
            original_time = None
        
        try:
            refactored_time = timeit.timeit(
                f'{refactored_func_name}([1, 2, 3, 4, 5])',
                setup=refactored_code,
                number=1000
            )
        except:
            refactored_time = None
        
        # Generate report
        report = f"=== Performance Benchmark Report ===\n\n"
        report += f"Original file: {original}\n"
        report += f"Refactored file: {refactored}\n\n"
        
        if original_time and refactored_time:
            improvement = ((original_time - refactored_time) / original_time) * 100
            speedup = original_time / refactored_time
            
            report += f"Original ({original_func_name}): {original_time:.6f}s for 1000 iterations\n"
            report += f"Refactored ({refactored_func_name}): {refactored_time:.6f}s for 1000 iterations\n\n"
            
            if improvement > 0:
                report += f"Improvement: {improvement:.2f}% faster ({speedup:.2f}x speedup)\n"
            else:
                report += f"Regression: {abs(improvement):.2f}% slower\n"
        else:
            report += "Could not complete benchmarks - verify functions are executable\n"
        
        return report
        
    except Exception as e:
        return f"Benchmark failed: {str(e)}"


@tool("Check Compliance Tool")
def check_compliance_tool(file_path: str) -> str:
    """
    Check a file for compliance violations AFTER writing it.
    Call this after write_to_file_tool to verify no banned patterns remain.
    If violations are found, read the file, fix the issues, write again, and re-check.

    Args:
        file_path: Path to the Python file to validate (e.g. 'target_repo/bad_code_1.py').

    Returns:
        A report listing any compliance violations found, or confirmation that the code is clean.
    """
    if not os.path.exists(file_path):
        return f"File not found: {file_path}"
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
    except OSError as e:
        return f"Cannot read file: {e}"

    findings = []
    lines = code.splitlines()
    for rule in RULES:
        if rule["severity"] not in ("critical", "high", "medium"):
            continue
        pattern = re.compile(rule["regex"], flags=re.IGNORECASE | re.MULTILINE)
        for idx, line in enumerate(lines, start=1):
            if pattern.search(line):
                # Context-aware suppression for file-write rule:
                # If logger/logging call is within 2 lines above, the write is audited.
                if rule["rule_id"] == "AML-OPS-001":
                    context_start = max(0, idx - 3)  # 2 lines above (0-based)
                    nearby = lines[context_start:idx - 1]  # lines above the match
                    if any("logger." in l or "logging." in l for l in nearby):
                        continue
                findings.append(
                    f"  Line {idx} [{rule['severity'].upper()}] {rule['rule_id']}: "
                    f"{rule['description']} — matched `{line.strip()[:120]}` — "
                    f"Fix: {rule['recommendation']}"
                )
    if not findings:
        return "COMPLIANCE CHECK PASSED — no violations found."
    return (
        f"COMPLIANCE CHECK FAILED — {len(findings)} violation(s) found:\n"
        + "\n".join(findings)
        + "\n\nFix these issues, write the file again, and re-check."
    )