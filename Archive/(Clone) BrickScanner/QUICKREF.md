# BrickScanner Quick Reference

## Installation in Databricks Notebook

```python
# Step 1: Add to sys.path
import sys
sys.path.insert(0, "/Workspace/Users/sai_kalluri@bcbsil.com/CLOUD_BIS_AI_POC/BrickScanner")

# Step 2: Import main entry point
import brickscanner

# Step 3: Run scanner
result_df = brickscanner.run(
    spark,
    include_paths="/Workspace/path/to/code",
    dry_run=True  # Preview mode
)
```

## Core Imports

```python
# Scanner pipeline
from brickscanner import run
from brickscanner.scanner import _load_rules, _process_chunks

# Configuration
from brickscanner.config import (
    CATALOG_NAME, SCHEMA_NAME, DB_TABLES, 
    CHUNK_SIZE, LLM_MODEL_NAME
)

# Validation models
from brickscanner.models import RuleReview, ReviewResponse

# Workspace utilities
from brickscanner.workspace import (
    get_workspace_client, get_nb_paths, read_nb_content
)

# Prompts
from brickscanner.prompts import build_review_prompt, format_code_chunk_prompt
```

## Common Tasks

### Query Results

```sql
-- All findings
SELECT * FROM gen_qa.analytics_bis_bronze.genai_output
ORDER BY created_ts DESC, severity DESC;

-- High severity only
SELECT * FROM gen_qa.analytics_bis_bronze.genai_output
WHERE severity = '1-High'
ORDER BY created_ts DESC;

-- By rule
SELECT rule_name, COUNT(*) as cnt
FROM gen_qa.analytics_bis_bronze.genai_output
GROUP BY rule_name
ORDER BY cnt DESC;

-- Latest batch
SELECT DISTINCT batch_id
FROM gen_qa.analytics_bis_bronze.genai_output
ORDER BY batch_id DESC LIMIT 1;
```

### Add Custom Rule

In any notebook:

```python
sys.path.insert(0, "/Workspace/.../BrickScanner")
from brickscanner.config import DB_TABLES

table = DB_TABLES["genai_rule_patterns"]
spark.sql(f"""
    INSERT INTO {table} 
    (rule_name, rule_description, rule_category, rule_sample, is_enabled)
    VALUES 
    ('my-rule', 'Description', 'Category', 'sample code', true)
""")
```

### Enable/Disable Rules

```python
sys.path.insert(0, "/Workspace/.../BrickScanner")
from brickscanner.config import DB_TABLES

table = DB_TABLES["genai_rule_patterns"]

# Disable a rule
spark.sql(f"UPDATE {table} SET is_enabled = false WHERE rule_name = 'rule-name'")

# Enable a rule
spark.sql(f"UPDATE {table} SET is_enabled = true WHERE rule_name = 'rule-name'")
```

### Manual Scan via Python

```python
import sys
sys.path.insert(0, "/Workspace/.../BrickScanner")
import brickscanner

# Dry run (returns DataFrame)
results_df = brickscanner.run(
    spark,
    include_paths="/Workspace/path1,/Workspace/path2",
    dry_run=True
)

# Production run (persists findings)
brickscanner.run(
    spark,
    include_paths="/Workspace/production/code",
    dry_run=False
)
```

## Pydantic Model Examples

### Creating a Finding Manually

```python
from brickscanner.models import RuleReview, ReviewResponse

# Single finding
finding = RuleReview(
    rule_id="1",
    comment="Unnecessary collect() call",
    severity="2-Medium",
    matching_content="df.collect()"
)

# Multiple findings response
response = ReviewResponse(
    Review=[
        RuleReview(
            rule_id="1",
            comment="Issue found",
            severity="1-High",
            matching_content="problematic_code"
        ),
        RuleReview(
            rule_id="2",
            comment="Not applicable",
            severity="N/A",
            matching_content=""
        ),
    ]
)

# Validate & export
print(response.model_dump_json(indent=2))
```

### Parsing LLM Response

```python
from brickscanner.models import ReviewResponse
import json

# Raw LLM output (may have markdown/prose)
raw_output = '''
Here are the findings:

```json
{
  "Review": [
    {"rule_id": "1", "comment": "Found issue", "severity": "2-Medium", "matchingcontent": "code_snippet"}
  ]
}
```
'''

# Parse (extracts JSON automatically)
try:
    response = ReviewResponse.model_validate_json(raw_output)
except:
    # Fallback: regex extract JSON
    import re
    json_match = re.search(r'\{[\s\S]*\}', raw_output)
    if json_match:
        response = ReviewResponse.model_validate_json(json_match.group(0))
```

## Configuration Examples

### Change Catalog/Schema

```python
# In brickscanner/config.py
CATALOG_NAME = "my_catalog"
SCHEMA_NAME = "my_schema"

DB_TABLES = {
    "genai_rule_patterns": f"{CATALOG_NAME}.{SCHEMA_NAME}.genai_rule_patterns",
    "genai_output": f"{CATALOG_NAME}.{SCHEMA_NAME}.genai_output",
}
```

### Adjust Chunk Size

```python
# In brickscanner/config.py
# For faster processing (fewer LLM calls):
CHUNK_SIZE = 20000  # Larger chunks

# For more granular review (more LLM calls):
CHUNK_SIZE = 5000   # Smaller chunks
```

### Add Exclusion Paths

```python
# In brickscanner/config.py
EXCLUSION_LIST = [
    "/Workspace/Users/Admin",
    "/Workspace/Shared/Internal",
    "/Workspace/Shared/Test",
    "_archived",
    "_backup",
    ".test",
    "temp",
]
```

### Change LLM Model

```python
# In brickscanner/config.py
LLM_MODEL_NAME = "databricks-meta-llama-3-70b-instruct"  # Alternative model
```

## Error Handling

### Safe Scanning with Error Capture

```python
import sys
sys.path.insert(0, "/Workspace/.../BrickScanner")
import brickscanner
import logging

logging.getLogger("[scanner]").setLevel(logging.DEBUG)

try:
    brickscanner.run(
        spark,
        include_paths="/Workspace/data",
        dry_run=False
    )
except ValueError as e:
    print(f"Validation error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

### Retry Logic

```python
import sys
sys.path.insert(0, "/Workspace/.../BrickScanner")
import brickscanner
import time

max_retries = 3
retry_count = 0

while retry_count < max_retries:
    try:
        brickscanner.run(spark, include_paths="/Workspace/data", dry_run=False)
        break
    except Exception as e:
        retry_count += 1
        if retry_count < max_retries:
            print(f"Attempt {retry_count} failed, retrying in 10s...")
            time.sleep(10)
        else:
            raise
```

## Performance Tips

### Profile Scan Performance

```python
import time
import sys
sys.path.insert(0, "/Workspace/.../BrickScanner")
import brickscanner

start = time.time()
result_df = brickscanner.run(
    spark,
    include_paths="/Workspace/data",
    dry_run=True
)
elapsed = time.time() - start

print(f"Scan completed in {elapsed:.1f}s")
print(f"Findings: {result_df.count()}")
print(f"Rate: {result_df.count() / elapsed:.1f} findings/sec")
```

### Parallel Batch Scanning

```python
from concurrent.futures import ThreadPoolExecutor
import sys
sys.path.insert(0, "/Workspace/.../BrickScanner")
import brickscanner

paths = [
    "/Workspace/data/pipeline1",
    "/Workspace/data/pipeline2",
    "/Workspace/data/pipeline3",
]

def scan_path(path):
    return brickscanner.run(spark, include_paths=path, dry_run=False)

# Sequential (recommended for Databricks)
for path in paths:
    scan_path(path)
```

## Troubleshooting Commands

### Check Installation

```python
import sys
sys.path.insert(0, "/Workspace/.../BrickScanner")

try:
    from brickscanner.config import CATALOG_NAME, SCHEMA_NAME, DB_TABLES
    print(f"✓ Config loaded: {CATALOG_NAME}.{SCHEMA_NAME}")
    print(f"✓ Tables: {DB_TABLES}")
except Exception as e:
    print(f"✗ Error: {e}")
```

### Verify Tables

```python
sys.path.insert(0, "/Workspace/.../BrickScanner")
from brickscanner.config import DB_TABLES

# Check rules table
rule_count = spark.sql(f"SELECT COUNT(*) FROM {DB_TABLES['genai_rule_patterns']}").collect()[0][0]
print(f"Rules: {rule_count}")

# Check output table
output_count = spark.sql(f"SELECT COUNT(*) FROM {DB_TABLES['genai_output']}").collect()[0][0]
print(f"Findings: {output_count}")
```

### Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Enable debug for all BrickScanner modules
for module in ["[scanner]", "[workspace]", "[db_setup]"]:
    logging.getLogger(module).setLevel(logging.DEBUG)
```

---

**Quick Links:**
- 📖 [Full README](README.md)
- 📋 [Deployment Guide](DEPLOYMENT.md)
- 🎯 [Original Spec](AgentPrompt.md)
