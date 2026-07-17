"""
LLM prompt templates for BrickScanner.

Keeping prompts separate from pipeline logic makes them easy to tune
without touching processing code. The response-format section is
derived directly from the Pydantic models in `brickscanner.models`
so the prompt and parser always stay in sync.
"""

from __future__ import annotations

import json

from langchain.prompts import ChatPromptTemplate

from brickscanner.models import ReviewResponse


# ---------------------------------------------------------------------
# Severity Guide
# ---------------------------------------------------------------------

SEVERITY_GUIDE = """
SEVERITY CLASSIFICATION GUIDE

Assign severity based on the IMPACT of the violation, not just whether it exists.

1-High:
Critical issues such as security vulnerabilities, data loss,
data corruption, production failures, or exposure of secrets.

Examples:
- Hardcoded secrets
- SQL Injection risks
- Unbounded collect() crashing clusters

2-Medium:
Performance, reliability, or maintainability issues without
immediate data risk.

Examples:
- display()/show() in production
- collect() on large datasets
- Missing exception handling
- Deprecated APIs
- Inefficient joins

3-Low:
Minor code quality/style issues.

Examples:
- Naming issues
- Missing docstrings
- Unused imports
- Verbose logic
"""


# ---------------------------------------------------------------------
# Instructions
# ---------------------------------------------------------------------

INSTRUCTIONS = """
INSTRUCTIONS

1. Evaluate the code against EVERY rule.
2. Every rule must produce exactly one finding.
3. For each finding:
   - Identify the matching code.
   - Assign one severity.
   - Explain:
       a) what is wrong
       b) why it matters
       c) a corrected code snippet
4. If a rule does not apply:
   severity = "N/A"
   matchingcontent = "Matching content not found"
5. If the rule is followed correctly:
   severity = "N/A"
   matchingcontent = "No violation found"
6. Never hallucinate issues.
7. matchingcontent must be copied EXACTLY from the reviewed code.
8. One code snippet cannot receive multiple severities.
9. Ignore commented code.

STRICT FORMATTING

- Output ONLY one valid JSON object.
- No markdown.
- No explanations.
- JSON must validate using ReviewResponse.model_validate_json().
- Use \\n for newlines inside strings.
- Escape double quotes.
- No trailing commas.
- severity must be one of:
    "1-High"
    "2-Medium"
    "3-Low"
    "N/A"
"""


# ---------------------------------------------------------------------
# Schema section
# ---------------------------------------------------------------------

def _build_response_schema_section() -> str:
    """Generate response schema directly from Pydantic."""

    schema = ReviewResponse.model_json_schema()

    example = {
        "Review": [
            {
                "rule_id": "1",
                "comment": (
                    "Issue: Hardcoded password.\\n"
                    "Impact: Credentials exposed.\\n"
                    "Better Alternative: Use dbutils.secrets.get()."
                ),
                "severity": "1-High",
                "matchingcontent": 'password = "abc123"',
            },
            {
                "rule_id": "2",
                "comment": "No issues found.",
                "severity": "N/A",
                "matchingcontent": "No violation found",
            },
        ]
    }

    return (
        "\nRESPONSE SCHEMA\n\n"
        + json.dumps(schema, indent=2)
        + "\n\nEXAMPLE OUTPUT\n\n"
        + json.dumps(example, separators=(",", ":"))
        + "\n"
    )


# ---------------------------------------------------------------------
# Public factory
# ---------------------------------------------------------------------

def build_prompt(
    rules: list[dict],
    feedback_map: dict[str, dict],
) -> ChatPromptTemplate:
    """
    Build ChatPromptTemplate embedding rules and historical feedback.
    """

    escaped_rules = (
        json.dumps(rules)
        .replace("{", "{{")
        .replace("}", "}}")
    )

    feedback_lines: list[str] = []

    for rule in rules:
        entry = feedback_map.get(rule.get("rule_name", ""))

        if entry and entry.get("feedback"):
            fb = (
                entry["feedback"]
                .replace("{", "{{")
                .replace("}", "}}")
            )

            line = f"- {rule['rule_name']}: {fb}"

            if entry.get("previous_finding_comment"):
                prev = (
                    entry["previous_finding_comment"]
                    .replace("{", "{{")
                    .replace("}", "}}")
                )
                line += f" | Previous Finding: {prev}"

            feedback_lines.append(line)

    feedback_section = ""

    if feedback_lines:
        feedback_section = (
            "\n###\n"
            "HISTORICAL REVIEWER FEEDBACK\n"
            "Use these observations to calibrate severity.\n"
            + "\n".join(feedback_lines)
            + "\n"
        )

    schema_section = (
        _build_response_schema_section()
        .replace("{", "{{")
        .replace("}", "}}")
    )

    template = (
        "You are an expert code reviewer specializing in "
        "Spark, Scala, SQL and Python.\n\n"
        "Review the provided code against every rule.\n\n"
        "###\nRULES\n"
        + escaped_rules
        + "\n###\n"
        + feedback_section
        + "\nCODE TO REVIEW\n"
        "{context}\n\n"
        + SEVERITY_GUIDE
        + "\n"
        + INSTRUCTIONS
        + "\n"
        + schema_section
    )

    return ChatPromptTemplate.from_template(template)