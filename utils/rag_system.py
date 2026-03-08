"""
RAG (Retrieval-Augmented Generation) System for Codebase Agent

This module handles:
- Embedding code files using sentence-transformers
- Storing embeddings in ChromaDB
- Retrieving relevant code context for refactoring tasks
- Smart chunking for large files
"""

import os
import logging
from pathlib import Path
from typing import List, Dict, Tuple
import chromadb
from sentence_transformers import SentenceTransformer
import hashlib
from tqdm.auto import tqdm


logger = logging.getLogger(__name__)


class RAGCodebaseIndex:
    """Manages embedding and retrieval of codebase context."""
    
    def __init__(self, 
                 collection_name: str = "codebase",
                 persist_directory: str = "rag_data",
                 model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize RAG system with ChromaDB and embedding model.
        
        Args:
            collection_name: Name of the ChromaDB collection
            persist_directory: Where to store the vector database
            model_name: Sentence-transformer model for embeddings
        """
        self.persist_directory = persist_directory
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Initializing RAG system with model: {model_name}")
        
        # Initialize persistent ChromaDB client
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "Code snippets from the codebase"}
        )
        logger.info(f"Using collection: {collection_name}")
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer(model_name)
        logger.info("RAG system initialized successfully")
    
    def _chunk_code(self, code: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Split code into overlapping chunks for better context preservation.
        
        Args:
            code: The source code to chunk
            chunk_size: Maximum characters per chunk
            overlap: Number of characters to overlap between chunks
            
        Returns:
            List of code chunks
        """
        lines = code.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line) + 1  # + 1 for newline
            
            if current_size + line_size > chunk_size and current_chunk:
                # Save current chunk
                chunks.append('\n'.join(current_chunk))
                
                # Start new chunk with overlap (last few lines)
                overlap_lines = []
                overlap_size = 0
                for prev_line in reversed(current_chunk):
                    if overlap_size + len(prev_line) < overlap:
                        overlap_lines.insert(0, prev_line)
                        overlap_size += len(prev_line) + 1
                    else:
                        break
                
                current_chunk = overlap_lines
                current_size = overlap_size
            
            current_chunk.append(line)
            current_size += line_size
        
        # Add the last chunk
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def _generate_chunk_id(self, file_path: str, chunk_index: int, content: str) -> str:
        """Generate a unique ID for a code chunk."""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        return f"{file_path}:chunk_{chunk_index}:{content_hash}"
    
    def index_file(self, file_path: str, force_reindex: bool = False) -> int:
        """
        Index a single file by chunking and embedding it.
        
        Args:
            file_path: Path to the file to index
            force_reindex: Whether to reindex even if already indexed
            
        Returns:
            Number of chunks indexed
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                code = f.read()
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return 0
        
        if not code.strip():
            return 0
        
        # Chunk the code
        chunks = self._chunk_code(code)
        
        if not chunks:
            return 0
        
        embeddings = self.embedding_model.encode(chunks).tolist()
        
        ids = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            chunk_id = self._generate_chunk_id(file_path, i, chunk)
            ids.append(chunk_id)
            metadatas.append({
                "file_path": file_path,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "file_name": os.path.basename(file_path)
            })
        
        # Add to ChromaDB
        try:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=chunks,
                metadatas=metadatas
            )
            logger.info(f"Indexed {file_path}: {len(chunks)} chunks")
            return len(chunks)
        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            return 0
    
    def index_directory(self, directory: str, file_extensions: List[str] = None) -> Dict[str, int]:
        """
        Index all files in a directory recursively.
        
        Args:
            directory: Root directory to index
            file_extensions: List of extensions to include (e.g., ['.py', '.js'])
            
        Returns:
            Dictionary mapping file paths to number of chunks indexed
        """
        if file_extensions is None:
            file_extensions = ['.py']  # Default to Python files
        
        results = {}
        directory_path = Path(directory)
        
        if not directory_path.exists():
            logger.error(f"Directory does not exist: {directory}")
            return results
        
        # Find all matching files
        files_to_index = []
        for ext in file_extensions:
            files_to_index.extend(directory_path.rglob(f"*{ext}"))
        
        logger.info(f"Found {len(files_to_index)} files to index in {directory}")
        
        # Filter files before indexing (for accurate progress totals).
        filtered_files = [
            file_path
            for file_path in files_to_index
            if '__pycache__' not in str(file_path) and 'test' not in str(file_path).lower()
        ]

        iterator = filtered_files
        iterator = tqdm(
            filtered_files,
            desc=f"RAG indexing [{directory}]",
            unit="file",
            dynamic_ncols=True,
        )

        for file_path in iterator:
            # Skip test files and __pycache__
            if '__pycache__' in str(file_path) or 'test' in str(file_path).lower():
                continue
            
            chunks_indexed = self.index_file(str(file_path))
            results[str(file_path)] = chunks_indexed
        
        logger.info(f"Indexing complete: {len(results)} files, {sum(results.values())} total chunks")
        return results
    
    def search(self, query: str, n_results: int = 5, filter_dict: Dict = None) -> List[Dict]:
        """
        Search for relevant code snippets using semantic similarity.
        
        Args:
            query: The search query (natural language or code)
            n_results: Number of results to return
            filter_dict: Optional metadata filters
            
        Returns:
            List of dicts containing code snippets and metadata
        """
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query]).tolist()
        
        # Search ChromaDB
        try:
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                where=filter_dict
            )
            
            # Format results
            formatted_results = []
            if results['documents'] and results['documents'][0]:
                for i in range(len(results['documents'][0])):
                    formatted_results.append({
                        'code': results['documents'][0][i],
                        'file_path': results['metadatas'][0][i]['file_path'],
                        'file_name': results['metadatas'][0][i]['file_name'],
                        'chunk_index': results['metadatas'][0][i]['chunk_index'],
                        'distance': results['distances'][0][i] if 'distances' in results else None
                    })
            
            return formatted_results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []
    
    def search_for_file(self, file_path: str, query: str, n_results: int = 3) -> List[str]:
        """
        Search for relevant context when refactoring a specific file.
        
        Args:
            file_path: The file being refactored
            query: What to search for (e.g., "similar functions", "error handling patterns")
            n_results: Number of relevant snippets to return
            
        Returns:
            List of relevant code snippets with context
        """
        # Build comprehensive search query
        file_name = os.path.basename(file_path)
        enhanced_query = f"{query} {file_name}"
        
        # Search, excluding the file being refactored
        results = self.search(enhanced_query, n_results=n_results)
        
        # Filter out the target file itself
        filtered_results = [
            r for r in results 
            if r['file_path'] != file_path
        ][:n_results]
        
        # Format as context strings
        context_snippets = []
        for result in filtered_results:
            snippet = f"""
                # From: {result['file_name']} (relevance: {1 - result['distance']:.2f})
                ```python
                {result['code']}
                ```
                """.strip()
            context_snippets.append(snippet)
        
        return context_snippets
    
    def get_collection_stats(self) -> Dict:
        """Get statistics about the indexed codebase."""
        try:
            count = self.collection.count()
            return {
                "total_chunks": count,
                "collection_name": self.collection.name,
                "persist_directory": self.persist_directory
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
    
    def clear_collection(self):
        """Clear all indexed data (useful for re-indexing)."""
        try:
            self.client.delete_collection(name=self.collection.name)
            self.collection = self.client.create_collection(
                name=self.collection.name,
                metadata={"description": "Code snippets from the codebase"}
            )
            logger.info("Collection cleared successfully")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}")
