# BrickScanner

AI-powered Databricks code-review system powered by Databricks-hosted LLMs and Pydantic validation.

## Table of Contents

1. [What is BrickScanner?](#what-is-brickscanner)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Prerequisites](#prerequisites)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [Usage](#usage)
8. [API Reference](#api-reference)
9. [Quality Improvements](#quality-improvements)
10. [Troubleshooting](#troubleshooting)

## What is BrickScanner?

BrickScanner is an enterprise-grade code-review automation system for Databricks workspaces. It:

- **Discovers** notebooks and Python files recursively under workspace paths
- **Evaluates** code against a configurable rules catalog using Databricks-hosted Claude LLM
- **Validates** LLM output with strict Pydantic schemas to prevent hallucination
- **Persists** actionable findings into Delta tables for reporting and auditing
- **Supports** Git-based changed-file scanning via GitHub API
- **Orchestrates** batch scans of multiple workspace groups with summary reporting

### Key Features

✓ **Automatic discovery** of notebooks and `.py` files  
✓ **LLM-powered review** with 35+ predefined rules  
✓ **Strict validation** prevents invalid findings from being persisted  
✓ **Delta persistence** for audit trail and reporting  
✓ **Git integration** for CI/CD pipelines (scan only changed files)  
✓ **Batch orchestration** for multi-group scanning campaigns  
✓ **Extensible rules** - add custom rules via `DB_Setup` helper  
✓ **MEE commons awareness** - flags reimplemented utilities  
✓ **Configurable severity** - categorize findings by business impact  

## Architecture

### End-to-End Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ Workspace Discovery                                             │
│ • Recursively scan include_paths                                │
│ • Include: notebooks + .py files                                │
│ • Exclude: paths matching suffix exclusion list                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│ Content Extraction & Chunking                                   │
│ • Export notebooks as Jupyter JSON                              │
│ • Read .py files directly                                       │
│ • Split into semantic chunks (PYTHON language splitter)         │
│ • Max chunk size: 10,000 chars                                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│ Rule Loading                                                    │
│ • Query genai_rule_patterns table                               │
│ • Fetch enabled rules only                                      │
│ • Build dynamic LLM prompt with all rules                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│ LLM Review (Databricks Claude Sonnet 4)                         │
│ • Send chunk + prompt + schema                                  │
│ • LLM evaluates EVERY rule                                      │
│ • Returns JSON with rule findings                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│ Response Parsing & Validation                                   │
│ • Regex extract JSON from LLM response                          │
│ • Validate via Pydantic ReviewResponse model                    │
│ • Strict field validation; fail fast on error                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│ Results Persistence                                             │
│ • Filter out N/A severity findings                              │
│ • Join rule_id to rule_name from rules table                    │
│ • Add batch_id (timestamp yyyyMMddHHmmssSSS)                    │
│ • Insert into genai_output Delta table                          │
└─────────────────────────────────────────────────────────────────┘
```

### Key Components

**`brickscanner` Python Package:**
- `config.py` - Centralized configuration (catalog, schema, LLM, tables, rules)
- `models.py` - Pydantic schemas for LLM response validation
- `workspace.py` - Databricks workspace client utilities
- `prompts.py` - LLM prompt construction
- `scanner.py` - Main scanning pipeline orchestration

**Databricks Notebooks:**
- `DB_Setup` - Initialize tables and seed default rules
- `Run_BrickScanner` - Ad-hoc scanner execution with widgets
- `Run_BrickScanner_Git` - GitHub-based changed-file scanning
- `Scan_Orchestrator` - Batch scan orchestration with summary reporting

**Delta Tables:**
- `gen_qa.analytics_bis_bronze.genai_rule_patterns` - Rules master catalog
- `gen_qa.analytics_bis_bronze.genai_output` - Code review findings

## Project Structure

```
BrickScanner/
├── brickscanner/                    # Python package
│   ├── __init__.py                  # Public run() entry point (lazy imports)
│   ├── config.py                    # Centralized configuration
│   ├── models.py                    # Pydantic validation schemas
│   ├── prompts.py                   # LLM prompt construction
│   ├── scanner.py                   # Main scanning pipeline
│   └── workspace.py                 # Databricks workspace utilities
│
├── notebooks/                       # Databricks notebooks
│   ├── DB_Setup.py                  # Initialize tables + seed rules
│   ├── Run_BrickScanner.py          # Ad-hoc scanner execution
│   ├── Run_BrickScanner_Git.py      # Git-based scan
│   └── Scan_Orchestrator.py         # Batch orchestration
│
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
└── AgentPrompt.md                   # System prompt (reference)
```

## Prerequisites

- **Databricks workspace** (Unity Catalog or non-UC)
- **Catalog & Schema** access to `gen_qa.analytics_bis_bronze` (or configured alternate)
- **Python 3.10+** in Databricks cluster
- **Secret scope** for GitHub PAT (if using Git scanning)
  - Scope: `github`
  - Key: `github_pat`
  - Value: GitHub Personal Access Token with repo read permissions

## Installation

### 1. Upload Project to Databricks

```bash
# From local workspace root
databricks workspace import-dir . /Workspace/Users/sai_kalluri@bcbsil.com/CLOUD_BIS_AI_POC/BrickScanner
```

Or manually upload files to Databricks workspace.

### 2. Create Secret Scope (Optional, for Git scanning)

```
databricks secrets put-secret github github_pat --string-value <YOUR_GITHUB_PAT>
```

### 3. Initialize Tables and Rules

Execute the `DB_Setup` notebook once to:
- Create `genai_rule_patterns` table with identity columns
- Create `genai_output` table with proper schema
- Seed 35 default best-practice rules

## Configuration

All configuration is centralized in `brickscanner/config.py`:

```python
# Databricks catalog and schema
CATALOG_NAME = "gen_qa"
SCHEMA_NAME = "analytics_bis_bronze"

# LLM configuration
LLM_MODEL_NAME = "databricks-claude-sonnet-4-6"
CHUNK_SIZE = 10000

# Fully qualified table names
DB_TABLES = {
    "genai_rule_patterns": "gen_qa.analytics_bis_bronze.genai_rule_patterns",
    "genai_output": "gen_qa.analytics_bis_bronze.genai_output",
}

# Exclusion list: paths ending with these suffixes are skipped
EXCLUSION_LIST = [
    "/Workspace/Users/Admin",
    "/Workspace/Shared/Internal",
    "_archived",
    "_temp",
]

# GitHub configuration (for Git scanning)
GITHUB_SECRET_SCOPE = "github"
GITHUB_SECRET_KEY = "github_pat"
GITHUB_ORG = "hcsc-core"
GITHUB_COMMITS_LIMIT = 1
```

**To customize:**
1. Edit `config.py` directly
2. Change catalog/schema if using alternate location
3. Add paths to `EXCLUSION_LIST` to skip sensitive areas
4. Adjust `CHUNK_SIZE` based on LLM token limits (10,000 is conservative)

## Usage

### Quick Start: Dry Run

1. Open `Run_BrickScanner` notebook
2. Set widgets:
   - `include_paths`: `/Workspace/Users/...` (comma-separated for multiple)
   - `dry_run`: ✓ (checked)
   - `run_setup`: ☐ (unchecked, if DB_Setup already run)
3. Run all cells
4. Review returned findings DataFrame

### Production Scan

1. Open `Run_BrickScanner` notebook
2. Set widgets:
   - `include_paths`: `/Workspace/Users/data,/Workspace/Shared/ETL`
   - `dry_run`: ☐ (unchecked)
   - `run_setup`: ☐ (unchecked)
3. Run all cells
4. Scanner persists findings to `genai_output` table
5. Query results:

```sql
SELECT 
    notebook_path,
    rule_name,
    severity,
    comment,
    matching_content,
    created_ts
FROM gen_qa.analytics_bis_bronze.genai_output
WHERE created_ts >= current_date()
ORDER BY severity DESC, created_ts DESC
```

### Git-Based Scanning (CI/CD)

Execute `Run_BrickScanner_Git` to scan only changed files from a GitHub branch:

1. Open `Run_BrickScanner_Git` notebook
2. Set widgets:
   - `repo_full_path`: `hcsc-core/data-pipeline` (org/repo)
   - `branch_name`: `feature/my-changes`
3. Notebook queries GitHub API for changed files in last 1 commit
4. Converts repo paths to workspace paths
5. Applies exclusion list
6. Invokes `Run_BrickScanner` with changed files only

### Batch Orchestration

Execute `Scan_Orchestrator` to run multiple named scan groups:

1. Edit `SCAN_BATCHES` dict in `Scan_Orchestrator` notebook
2. Map batch names to workspace paths:
   ```python
   SCAN_BATCHES = {
       "data_pipeline": "/Workspace/Users/.../data",
       "ml_pipeline": "/Workspace/Users/.../ml",
       "etl_jobs": "/Workspace/Shared/ETL",
   }
   ```
3. Run notebook
4. Orchestrator executes each batch sequentially
5. Captures status, timing, and errors
6. Prints summary table with results

## API Reference

### `brickscanner.run()`

**Entry Point**

```python
import brickscanner

result_df = brickscanner.run(
    spark,
    extractor_type="genai",
    include_paths="/Workspace/Users/...,/Workspace/Shared/...",
    dry_run=False
)
```

**Parameters:**
- `spark` (SparkSession) - Active Databricks session
- `extractor_type` (str) - Type of extractor; always "genai"
- `include_paths` (str) - Comma-separated workspace paths to scan
- `dry_run` (bool) - If True, return DataFrame without persisting; if False, persist and return None

**Returns:**
- On `dry_run=True`: Filtered DataFrame of findings
- On `dry_run=False`: None (results persisted to `genai_output`)

**Raises:**
- `ValueError` - If `include_paths` is empty or unrecoverable error occurs

### Pydantic Models

**`RuleReview`** - Individual rule finding

```python
from brickscanner.models import RuleReview

review = RuleReview(
    rule_id="1",
    comment="Unnecessary collect() call detected",
    severity="2-Medium",
    matching_content="df.collect()"  # Exact substring from code
)
```

**`ReviewResponse`** - Top-level response structure

```python
from brickscanner.models import ReviewResponse

response = ReviewResponse(
    Review=[
        RuleReview(...),
        RuleReview(...),
    ]
)
```

### Rules Format

**Adding Custom Rules:**

In `DB_Setup` notebook:

```python
add_rule(
    spark,
    rule_name="custom-rule",
    description="My custom rule description",
    category="Pyspark-Custom",
    sample="Code example",
    enabled=True
)
```

**Default Rules** (35 total):

| Rule ID | Category | Purpose |
|---------|----------|---------|
| unintended-collect | Pyspark-Coding | Avoid unnecessary `collect()` |
| unintended-stmt | Pyspark-Coding | Avoid `display`, `show`, `print`, `count` in production |
| pandas | Pyspark-Coding | Avoid pandas conversion for large-scale processing |
| checking-empty | Pyspark-Coding | Avoid `df.count()==0`; prefer `isEmpty` |
| leverage-commons-utils | Pyspark-Coding | Flag code reimplementing commons utilities |
| hard-coded-secrets | Pyspark-Coding | Avoid hardcoded secrets, credentials, API URLs |
| (30 more) | Various | Performance, optimization, SQL best practices |

See `config.py` or query `genai_rule_patterns` table for full list.

### Severity Levels

```
1-High       - Security risks, data loss potential, production failures
2-Medium     - Performance degradation, reliability concerns
3-Low        - Code quality, style, documentation issues
N/A          - Rule does not apply (filtered from persistence)
```

## Quality Improvements

### Validation & Safety

✓ **Pydantic schemas** prevent invalid findings from being persisted  
✓ **Strict field validation** (severity enum, matching_content non-empty)  
✓ **Regex extraction** of JSON from LLM response (handles markdown/prose)  
✓ **Error logging** with `[scanner]`, `[workspace]`, `[db_setup]` prefixes  
✓ **Fail-fast** on unrecoverable errors  

### Code Quality

✓ **Type hints** throughout  
✓ **Docstrings** on all classes and functions  
✓ **No wildcard imports**  
✓ **Safe boolean parsing** (avoid `eval()`)  
✓ **Explicit logging** levels (info, warning, error)  

### Performance

✓ **Lazy imports** in package `__init__.py` (lightweight for config-only imports)  
✓ **Chunking** of large notebooks (10,000 char max per LLM invocation)  
✓ **Batch filtering** (N/A findings excluded at query time)  
✓ **Delta table optimization** (deletion vectors, identity columns)  

### Extensibility

✓ **Configurable rules** - add custom rules without code changes  
✓ **Configurable paths** - scan any workspace location  
✓ **Configurable exclusions** - skip sensitive areas  
✓ **Plug-in LLM** - replace `CHAT_DATABRICKS` endpoint in config  

## Troubleshooting

### Common Issues

**Q: "Failed to get workspace client"**  
A: Ensure running in Databricks notebook context with implicit authentication.

**Q: "No enabled rules found"**  
A: Run `DB_Setup` notebook to seed default rules. Check `genai_rule_patterns` table for `is_enabled = true`.

**Q: "Failed to parse response"**  
A: LLM returned invalid JSON. Check LLM logs for errors. Verify `ReviewResponse` schema matches prompt instructions.

**Q: "Table not found: gen_qa.analytics_bis_bronze.genai_rule_patterns"**  
A: Run `DB_Setup` notebook to create tables. Or edit `config.py` to use alternate catalog/schema.

**Q: GitHub API errors (401 Unauthorized)**  
A: Verify GitHub PAT secret is set correctly:
```
databricks secrets put-secret github github_pat --string-value <TOKEN>
```

**Q: Scan hangs or times out**  
A: Reduce `CHUNK_SIZE` in `config.py` or set shorter `timeout_seconds` in notebook.run() calls. Large notebooks may require longer timeouts.

### Debug Logging

Enable debug logging in notebooks:

```python
import logging
logging.getLogger("[scanner]").setLevel(logging.DEBUG)
logging.getLogger("[workspace]").setLevel(logging.DEBUG)
```

### Performance Tuning

**Increase scan speed:**
- Increase `CHUNK_SIZE` (trades LLM invocations for context window)
- Add more paths to `EXCLUSION_LIST` to skip unnecessary areas
- Use `Run_BrickScanner_Git` to scan only changed files in CI/CD

**Reduce costs:**
- Use dry-run mode to test configuration
- Run scans during off-peak hours
- Filter rules by enabling only critical rules in `genai_rule_patterns`

### Sample Queries

**Find all High-severity findings:**
```sql
SELECT * FROM gen_qa.analytics_bis_bronze.genai_output
WHERE severity = '1-High'
ORDER BY created_ts DESC
```

**Findings by rule name:**
```sql
SELECT rule_name, COUNT(*) as count
FROM gen_qa.analytics_bis_bronze.genai_output
GROUP BY rule_name
ORDER BY count DESC
```

**Recent scans (last 24 hours):**
```sql
SELECT DISTINCT batch_id, COUNT(*) as findings
FROM gen_qa.analytics_bis_bronze.genai_output
WHERE created_ts >= current_timestamp() - INTERVAL 1 DAY
GROUP BY batch_id
ORDER BY batch_id DESC
```

## Support & Contributing

For issues, feature requests, or questions:
1. Check this README troubleshooting section
2. Review notebook logs for error messages
3. Query `genai_output` and `genai_rule_patterns` tables for data issues
4. Contact the BrickScanner team

---

**Version:** 1.0  
**Last Updated:** 2026-07-14  
**Maintained By:** Data Quality & Governance Team
