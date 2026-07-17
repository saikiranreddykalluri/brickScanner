"""
LLM prompt construction for code review.
"""

import json
from typing import List, Dict


def build_review_prompt(enabled_rules: List[Dict], response_schema: Dict) -> str:
    """
    Build comprehensive code review prompt for LLM.
    
    Includes:
    1. Role statement
    2. Rules section with all enabled rules
    3. Severity guide
    4. Strict instructions
    5. Response schema
    6. Example valid JSON
    
    Args:
        enabled_rules: List of enabled rule dicts (rule_id, rule_name, rule_description, rule_sample)
        response_schema: Pydantic model_json_schema() output
    
    Returns:
        Formatted prompt string
    """
    
    # Section 1: Role statement
    role_section = """You are an expert Databricks code reviewer specializing in PySpark, Scala, SQL, and Python.
Your job is to review code chunks against a set of predefined rules and provide structured findings."""
    
    # Section 2: Rules section
    rules_section = "## Code Review Rules\n\n"
    for rule in enabled_rules:
        rules_section += f"""### Rule {rule['rule_id']}: {rule['rule_name']}
Category: {rule.get('rule_category', 'General')}
Description: {rule['rule_description']}
Example: {rule.get('rule_sample', 'N/A')}

"""
    
    # Section 4: Severity guide
    severity_section = """## Severity Levels

1. **1-High**: Security risks, data loss potential, production failures, hardcoded secrets, destructive operations without safeguards
2. **2-Medium**: Performance degradation, reliability concerns, resource inefficiency that could impact operations
3. **3-Low**: Minor code quality, style, documentation, or maintainability issues
4. **N/A**: Rule does not apply to this code chunk

"""
    
    # Section 5: Strict instructions
    instructions_section = """## Review Instructions

1. Evaluate EVERY rule against the provided code chunk
2. Return exactly ONE finding per rule (success or N/A, never duplicates)
3. For matching_content: provide an exact substring from the code that triggered the finding
4. For N/A findings: return empty string for matching_content and comment "Not applicable"
5. IGNORE commented-out code (do not flag commented lines)
6. Return ONLY valid JSON, no markdown, no prose, no explanation outside JSON
7. Do not create additional fields beyond the schema
8. All returned JSON must be parseable by Pydantic ReviewResponse model

"""
    
    # Section 6: Response schema
    schema_section = f"""## Response JSON Schema

Your response must conform to this exact schema:

```json
{json.dumps(response_schema, indent=2)}
```

"""
    
    # Section 7: Example valid JSON
    example_section = """{
  "Review": [
    {
      "rule_id": "1",
      "comment": "Found unnecessary collect() call that may cause memory issues",
      "severity": "2-Medium",
      "matchingcontent": "df.collect()"
    },
    {
      "rule_id": "2",
      "comment": "Not applicable",
      "severity": "N/A",
      "matchingcontent": ""
    }
  ]
}
"""
    
    # Section 8: Code to review (placeholder)
    code_section = """## Code to Review

```
{CODE_PLACEHOLDER}
```

"""
    
    full_prompt = (
        role_section + "\n\n"
        + rules_section + "\n"
        + severity_section + "\n"
        + instructions_section + "\n"
        + schema_section + "\n"
        + "## Example Valid Response\n\n"
        + example_section + "\n\n"
        + code_section
    )
    
    return full_prompt


def format_code_chunk_prompt(base_prompt: str, code_chunk: str) -> str:
    """
    Format final prompt with code chunk inserted.
    
    Args:
        base_prompt: Base prompt template from build_review_prompt()
        code_chunk: Code to review
    
    Returns:
        Complete prompt with code chunk
    """
    return base_prompt.replace("{CODE_PLACEHOLDER}", code_chunk)
