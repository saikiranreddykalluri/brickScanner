"""
Central configuration for BrickScanner.

All catalog, schema, table, LLM, and scan settings live here.
Change these values to target a different environment.
"""

from __future__ import annotations

from typing import Final


# ---------------------------------------------------------------------
# Catalog / Schema
# ---------------------------------------------------------------------

CATALOG_NAME: Final[str] = "gen_qa"
SCHEMA_NAME: Final[str] = "utils"


# ---------------------------------------------------------------------
# Table references (fully qualified)
# ---------------------------------------------------------------------

DB_TABLES: Final[dict[str, str]] = {
    "genai_rule_patterns": f"{CATALOG_NAME}.{SCHEMA_NAME}.genai_rule_patterns",
    "genai_output": f"{CATALOG_NAME}.{SCHEMA_NAME}.genai_output",
    "genai_feedback": f"{CATALOG_NAME}.{SCHEMA_NAME}.genai_feedback",
}


# ---------------------------------------------------------------------
# LLM settings
# ---------------------------------------------------------------------

LLM_MODEL_NAME: Final[str] = "databricks-meta-llama-3-3-70b-instruct"
CHUNK_SIZE: Final[int] = 10_000  # characters per LLM invocation
CHUNK_OVERLAP: Final[int] = 0  # characters to overlap between chunks

# ---------------------------------------------------------------------
# Paths excluded from every scan
# ---------------------------------------------------------------------
# Add any path suffix that should never be scanned.

EXCLUSION_LIST: Final[list[str]] = [
    "/CLOUD_BIS_AI_POC/BricksScanner/brickscanner/genai_extractor/utils.py",
    "/CLOUD_BIS_AI_POC/BricksScanner/Manage_Rules",
]