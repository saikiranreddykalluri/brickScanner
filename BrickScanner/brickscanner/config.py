"""
BrickScanner configuration.

Centralized environment and table configuration.
"""

# Databricks catalog and schema
CATALOG_NAME = "brickscanner"
SCHEMA_NAME = "bs_schema"

# LLM configuration
LLM_MODEL_NAME = "databricks-claude-sonnet-4-6"
CHUNK_SIZE = 10000

# Fully qualified table names
DB_TABLES = {
    "genai_rule_patterns": f"{CATALOG_NAME}.{SCHEMA_NAME}.genai_rule_patterns",
    "genai_output": f"{CATALOG_NAME}.{SCHEMA_NAME}.genai_output",
}

# Exclusion list: paths ending with these suffixes are skipped
# Suffix-matched, not exact-path-only
EXCLUSION_LIST = [
    "/Workspace/Users/Admin",
    "/Workspace/Shared/Internal",
    "/Workspace/Shared/Admin",
    "_archived",
    "_temp",
    ".test",
]

# GitHub configuration
GITHUB_SECRET_SCOPE = "github"
GITHUB_SECRET_KEY = "github_pat"
GITHUB_ORG = "hcsc-core"
GITHUB_COMMITS_LIMIT = 1

# Severity levels
SEVERITY_LEVELS = ["1-High", "2-Medium", "3-Low", "N/A"]
