from crewai.tools import tool
import subprocess
import os
from langchain_community.tools import DuckDuckGoSearchRun
from utils.rag_system import RAGCodebaseIndex

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

@tool("RAG Search Tool")
def rag_search_tool(query: str, n_results: int = 3) -> str:
    """
    Search the codebase for relevant code examples and patterns using semantic search.
    Use this to find similar functions, patterns, or best practices already in the codebase.
    
    Args:
        query: What to search for (e.g., "error handling", "list comprehension", "sorting algorithms")
        n_results: Number of relevant code snippets to return (default: 3)
    
    Returns:
        Relevant code snippets with file paths and context
    """
    global _rag_instance
    
    if _rag_instance is None:
        return "RAG system not initialized. Enable 'rag.enable' in config.yaml"
    
    try:
        results = _rag_instance.search(query, n_results=n_results)
        
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