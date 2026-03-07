"""
LLM-Powered Codebase generator

Generates a diverse collection of Python code files using LLMs.
This creates a rich codebase for RAG to learn patterns from.
"""

import os
import time
from pathlib import Path
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

# Code categories to generate
CODE_TEMPLATES = [
    {
        "category": "data_structures",
        "files": [
            "linked_list.py",
            "binary_tree.py",
            "hash_table.py",
            "stack.py",
            "queue.py"
        ],
        "prompt": "Write a complete, well-documented Python implementation of {filename} with type hints, error handling, and comprehensive docstrings. Include __init__, common operations, and edge case handling."
    },
    {
        "category": "algorithms",
        "files": [
            "sorting_algorithms.py",
            "searching_algorithms.py",
            "graph_algorithms.py",
            "dynamic_programming.py",
            "string_algorithms.py"
        ],
        "prompt": "Write production-quality Python code for {filename} with multiple algorithm implementations, type hints, O(n) complexity comments, and error handling."
    },
    {
        "category": "utils",
        "files": [
            "validators.py",
            "string_utils.py",
            "file_utils.py",
            "date_utils.py",
            "math_utils.py"
        ],
        "prompt": "Write a Python utility module {filename} with 5-7 useful helper functions, full type hints, error handling with try-except, and detailed docstrings."
    },
    {
        "category": "api",
        "files": [
            "user_service.py",
            "auth_service.py",
            "payment_service.py",
            "notification_service.py",
            "cache_service.py"
        ],
        "prompt": "Write a Python service class for {filename} with async methods, proper error handling, logging, type hints, and dependency injection pattern."
    },
    {
        "category": "models",
        "files": [
            "user_model.py",
            "product_model.py",
            "order_model.py",
            "payment_model.py",
            "config_model.py"
        ],
        "prompt": "Write a Python data model class for {filename} using dataclasses or Pydantic, with validation, type hints, and serialization methods (to_dict, from_dict)."
    },
    {
        "category": "database",
        "files": [
            "db_connector.py",
            "query_builder.py",
            "migrations.py",
            "orm_helpers.py",
            "transaction_manager.py"
        ],
        "prompt": "Write Python database code for {filename} with connection pooling, error handling, context managers, type hints, and proper resource cleanup."
    },
    {
        "category": "testing",
        "files": [
            "test_helpers.py",
            "fixtures.py",
            "mock_data.py",
            "test_factories.py",
            "assertions.py"
        ],
        "prompt": "Write Python testing utilities for {filename} with pytest fixtures, mock generators, assertion helpers, and well-documented examples."
    },
    {
        "category": "parsers",
        "files": [
            "json_parser.py",
            "xml_parser.py",
            "csv_parser.py",
            "yaml_parser.py",
            "config_parser.py"
        ],
        "prompt": "Write a robust Python parser for {filename} with error handling, validation, type conversion, and support for nested structures."
    }
]

def setup_llm():
    """Initialize the LLM."""
    return LLM(
        model="groq/llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.7,  # Higher for more creative/diverse code
        max_tokens=2048
    )

def generate_code_file(llm: LLM, category: str, filename: str, prompt_template: str, output_dir: Path) -> bool:
    """
    Generate a single code file using LLM.
    
    Args:
        llm: The LLM instance
        category: Code category (data_structures, algorithms, etc.)
        filename: Name of the file to generate
        prompt_template: Prompt template with {filename} placeholder
        output_dir: Base output directory
        
    Returns:
        True if successful, False otherwise
    """
    # Create category directory
    category_dir = output_dir / category
    category_dir.mkdir(parents=True, exist_ok=True)
    
    # Build prompt
    prompt = prompt_template.format(filename=filename.replace('.py', ''))
    prompt += "\n\nIMPORTANT: Return ONLY the Python code, no explanations or markdown. Start with imports."
    
    print(f"  Generating {category}/{filename}...", end=" ")
    
    try:
        response = llm.call([{"role": "user", "content": prompt}])
        
        # Clean up response (remove markdown if present)
        code = response
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()
        
        output_file = category_dir / filename
        output_file.write_text(code, encoding='utf-8')
        
        print(f"({len(code)} chars)")
        return True
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False


def main():
    """Main generation function."""
    print("=" * 70)
    print("LLM-Powered Codebase Generator")
    print("=" * 70)
    print("\nThis will generate diverse Python code for RAG to learn from.\n")
    
    # Setup
    output_dir = Path("synthetic_codebase")
    print(f"Output directory: {output_dir}/\n")
    
    llm = setup_llm()
    print("LLM initialized\n")
    
    # Statistics
    stats = {
        'total_files': 0,
        'successful': 0,
        'failed': 0,
        'categories': len(CODE_TEMPLATES),
        'category_counts': {}
    }
    
    # Generate all code files
    for template in CODE_TEMPLATES:
        category = template['category']
        files = template['files']
        prompt = template['prompt']
        
        print(f"Category: {category} ({len(files)} files)")
        
        category_success = 0
        for filename in files:
            stats['total_files'] += 1
            
            # Generate file
            success = generate_code_file(llm, category, filename, prompt, output_dir)
            
            if success:
                stats['successful'] += 1
                category_success += 1
            else:
                stats['failed'] += 1
            
            # Rate limiting - be nice to the API
            time.sleep(2)
        
        stats['category_counts'][category] = category_success
        print()
        
    # Final summary
    print("Generation complete!")
    print(f"\nSummary:")
    print(f"  Total files: {stats['total_files']}")
    print(f"  Successful: {stats['successful']}")
    print(f"  Failed: {stats['failed']}")
    print(f"\nLocation: {output_dir.absolute()}/")
    print(f"\nNext steps:")
    print(f"  1. Update config.yaml to index this directory:")
    print(f"     rag:")
    print(f"       enable: true")
    print(f"  2. Or manually index:")
    print(f"     python -c \"from utils.rag_system import RAGCodebaseIndex; rag = RAGCodebaseIndex(); rag.index_directory('synthetic_codebase')\"")
    print(f"  3. Run your agent: python main.py")
    print()

if __name__ == "__main__":
    main()
