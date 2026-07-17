"""
Example:
    from brickscanner import run

    run(
        spark,
        extractor_type="genai",
        include_paths="/Workspace/..."
    )
"""

__all__ = ["run"]


def run(*args, **kwargs):
    """
    Lazy entry point — scanner (and langchain) are imported only
    when run() is called.

    This ensures notebooks that only need `brickscanner.config`
    or `brickscanner.workspace` (e.g. Rule_Reviewer,
    Submit_Rule_Feedback) do not require langchain to be installed.
    """

    from .scanner import run as _run  # deferred import
    return _run(*args, **kwargs)