from crewai.tools import tool
import subprocess
import os
from langchain_community.tools import DuckDuckGoSearchRun

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
        if "target_repo" not in file_path:
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