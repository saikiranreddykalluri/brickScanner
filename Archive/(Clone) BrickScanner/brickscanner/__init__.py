"""
BrickScanner: AI-powered Databricks code-review system.

Public entry point for the scanner module.
Lazy imports to keep module lightweight for import-only scenarios.
"""


def run(*args, **kwargs):
    """
    Execute a BrickScanner run.
    
    Lazy-import scanner.run to avoid requiring LangChain for config/workspace-only imports.
    
    Args:
        *args: Positional arguments passed to scanner.run()
        **kwargs: Keyword arguments passed to scanner.run()
    
    Returns:
        DataFrame or None depending on dry_run flag
    """
    from brickscanner.scanner import run as scanner_run
    return scanner_run(*args, **kwargs)
