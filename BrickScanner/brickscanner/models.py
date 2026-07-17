"""
Pydantic output models for BrickScanner LLM responses.

These models define the exact JSON contract the LLM must honour.
Using Pydantic gives us validated, typed access to every finding
without manual dict traversal, and makes the expected schema
self-documenting in the prompt.

Usage::

    from brickscanner.models import ReviewResponse

    parsed = ReviewResponse.model_validate(json_dict)   # validate
    flat_rows = [r.model_dump() for r in parsed.Review]  # to list[dict]
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RuleReview(BaseModel):
    """
    A single rule evaluation finding returned by the LLM.

    `matching_content` uses a camelCase alias (`matchingcontent`) that
    matches the JSON key the LLM produces. `model_dump()` returns the
    snake_case Python name, which aligns with the Delta table column.
    """

    model_config = ConfigDict(populate_by_name=True)

    rule_id: str = Field(
        ...,
        description="The rule_id from genai_rule_patterns being evaluated.",
    )

    comment: str = Field(
        ...,
        description=(
            "Single-line string. Use \\n for newlines. Must cover: "
            "(a) what the issue is, (b) why it matters, (c) a corrected code snippet."
        ),
    )

    severity: Literal["1-High", "2-Medium", "3-Low", "N/A"] = Field(
        ...,
        description="Severity level, or N/A if the rule does not apply.",
    )

    matching_content: str = Field(
        alias="matchingcontent",
        description=(
            "Exact substring copied from the reviewed code. "
            "Use 'No violation found' when severity is N/A."
        ),
    )


class ReviewResponse(BaseModel):
    """Top-level envelope returned by the LLM for each code chunk."""

    Review: list[RuleReview] = Field(
        ...,
        description="Exactly one RuleReview per rule — no duplicates, no omissions.",
    )