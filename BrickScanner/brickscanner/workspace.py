"""
Databricks workspace utilities for discovering and reading notebooks and Python files.
"""

import json
import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger("[workspace]")


class NBContent:
    """
    Notebook content extractor.
    
    Deduplicates and separates notebook cells into code and markdown.
    """
    
    def __init__(self, notebook_dict: Dict):
        """
        Initialize with notebook JSON dictionary.
        
        Args:
            notebook_dict: Notebook JSON structure from Databricks export
        """
        self.notebook_dict = notebook_dict
        self.code_cells = []
        self.markdown_cells = []
        self._parse_cells()
    
    def _parse_cells(self):
        """Parse notebook cells into code and markdown, deduplicating."""
        cells = self.notebook_dict.get("cells", [])
        seen_code = dict.fromkeys([])  # Preserve order deduplication
        seen_markdown = dict.fromkeys([])
        
        for cell in cells:
            cell_type = cell.get("cell_type", "")
            source = cell.get("source", [])
            
            # Handle source as list or string
            if isinstance(source, list):
                source_str = "".join(source)
            else:
                source_str = str(source)
            
            if not source_str.strip():
                continue
            
            if cell_type == "code":
                if source_str not in seen_code:
                    seen_code[source_str] = None
                    self.code_cells.append(source_str)
            elif cell_type == "markdown":
                if source_str not in seen_markdown:
                    seen_markdown[source_str] = None
                    self.markdown_cells.append(source_str)
        
        # Deduplication with order preservation
        self.code_cells = list(dict.fromkeys(self.code_cells))
        self.markdown_cells = list(dict.fromkeys(self.markdown_cells))


def _py2nb(py_str: str) -> str:
    """
    Convert Databricks Python script format to notebook-like code cells.
    
    Databricks exports .py files with markdown headers as comments.
    This extracts executable code and treats comments as documentation.
    
    Args:
        py_str: Python script content
    
    Returns:
        Extracted code suitable for review
    """
    lines = py_str.split("\n")
    code_lines = []
    
    for line in lines:
        # Skip Databricks magic commands at module level
        if line.strip().startswith("# Databricks notebook source"):
            continue
        # Keep executable code and comments
        code_lines.append(line)
    
    return "\n".join(code_lines)


def get_workspace_client(spark):
    """
    Get authenticated Databricks WorkspaceClient from current notebook context.
    
    Args:
        spark: SparkSession from notebook context
    
    Returns:
        databricks.sdk.service.iam.WorkspaceClient: Authenticated workspace client
    
    Raises:
        RuntimeError: If not running in Databricks notebook context
    """
    try:
        from databricks.sdk import WorkspaceClient
        from databricks.sdk.core import Config
        
        # In Databricks notebooks, authentication is implicit
        # WorkspaceClient() will use current session token
        client = WorkspaceClient()
        return client
    except Exception as e:
        logger.error(f"Failed to get workspace client: {e}")
        raise RuntimeError("Must run in Databricks notebook context") from e


def get_nb_paths(
    wobj,
    folder_paths: List[str],
    exclusion_list: List[str]
) -> List[Tuple]:
    """
    Recursively discover notebook and Python file paths in workspace.
    
    Args:
        wobj: WorkspaceClient instance
        folder_paths: List of workspace paths to scan (e.g., ["/Workspace/..."])
        exclusion_list: List of suffixes to exclude (matched against path endings)
    
    Returns:
        List of tuples: (path, object_id, type, language, created_at, modified_at)
    """
    results = []
    
    if not folder_paths:
        logger.warning("No folder paths provided for discovery")
        return results
    
    for folder_path in folder_paths:
        try:
            _recursive_list(wobj, folder_path, exclusion_list, results)
        except Exception as e:
            logger.warning(f"Error discovering path {folder_path}: {e}")
    
    logger.info(f"[workspace] Discovered {len(results)} files")
    return results


def _recursive_list(wobj, path: str, exclusion_list: List[str], results: List[Tuple]):
    """
    Recursively list workspace objects, filtering by type and exclusion rules.
    
    Args:
        wobj: WorkspaceClient instance
        path: Current path to list
        exclusion_list: Exclusion suffix list
        results: Accumulator for valid paths
    """
    try:
        objects = wobj.workspace.list_workspace(path)
        
        for obj in objects:
            # Check exclusion list
            if any(obj.path.endswith(suffix) for suffix in exclusion_list):
                logger.debug(f"Skipping excluded path: {obj.path}")
                continue
            
            # Include notebooks and Python files
            if obj.object_type.name == "NOTEBOOK":
                # Databricks notebooks don't have explicit file extensions
                results.append((
                    obj.path,
                    obj.object_id,
                    "NOTEBOOK",
                    "python",  # Assume Python; could inspect metadata
                    obj.created_at,
                    obj.modified_at,
                ))
            elif obj.object_type.name == "FILE" and obj.path.endswith(".py"):
                results.append((
                    obj.path,
                    obj.object_id,
                    "FILE",
                    "python",
                    obj.created_at,
                    obj.modified_at,
                ))
            elif obj.object_type.name == "DIRECTORY":
                # Recurse into subdirectories
                _recursive_list(wobj, obj.path, exclusion_list, results)
    
    except Exception as e:
        logger.debug(f"Error listing {path}: {e}")


def read_nb_content(wobj, path_tuple: Tuple) -> str:
    """
    Read notebook or Python file content from workspace.
    
    Args:
        wobj: WorkspaceClient instance
        path_tuple: Tuple from get_nb_paths: (path, object_id, type, language, ...)
    
    Returns:
        Extracted code string suitable for analysis
    """
    path, obj_id, obj_type, language, *_ = path_tuple
    
    try:
        if obj_type == "NOTEBOOK":
            # Export notebook as Jupyter format
            response = wobj.workspace.export_workspace(path, format="JUPYTER")
            notebook_content = json.loads(response.content.decode("utf-8"))
            nb = NBContent(notebook_content)
            # Combine code and markdown for review
            all_cells = nb.code_cells + nb.markdown_cells
            return "\n".join(all_cells)
        
        elif obj_type == "FILE":
            # Read .py file directly
            response = wobj.workspace.get_status(path)
            file_content = wobj.workspace.export_workspace(path, format="SOURCE")
            code_str = file_content.content.decode("utf-8")
            return _py2nb(code_str)
    
    except Exception as e:
        logger.error(f"Error reading {path}: {e}")
        return ""
    
    return ""
