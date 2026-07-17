"""
Pydantic models for LLM response parsing and validation.
"""

from typing import List, Literal
from pydantic import BaseModel, Field, field_validator


class RuleReview(BaseModel):
    """
    Individual rule review result from LLM.
    
    Attributes:
        rule_id: Rule identifier
        comment: Reviewer comment or finding description
        severity: Severity level (1-High, 2-Medium, 3-Low, N/A)
        matching_content: Exact substring from code that triggered the finding
    """
    rule_id: str
    comment: str
    severity: Literal["1-High", "2-Medium", "3-Low", "N/A"]
    matching_content: str = Field(
        ...,
        alias="matchingcontent"  # LLM may return lowercase or alternate case
    )
    
    model_config = {
        "populate_by_name": True,  # Allow both 'matching_content' and 'matchingcontent'
        "str_strip_whitespace": True,
    }
    
    @field_validator("severity")
    @classmethod
    def validate_severity(cls, v):
        """Ensure severity is one of the allowed values."""
        allowed = ["1-High", "2-Medium", "3-Low", "N/A"]
        if v not in allowed:
            raise ValueError(f"Severity must be one of {allowed}, got '{v}'")
        return v
    
    @field_validator("matching_content")
    @classmethod
    def validate_matching_content(cls, v):
        """Ensure matching_content is not empty."""
        if not v or not v.strip():
            raise ValueError("matching_content cannot be empty")
        return v


class ReviewResponse(BaseModel):
    """
    Top-level response structure from LLM containing list of rule reviews.
    
    Attributes:
        Review: List of RuleReview objects
    """
    Review: List[RuleReview] = Field(default_factory=list)
    
    model_config = {
        "str_strip_whitespace": True,
    }
    
    @field_validator("Review")
    @classmethod
    def validate_review_list(cls, v):
        """Ensure Review list is not empty."""
        if not v or len(v) == 0:
            raise ValueError("Review list cannot be empty")
        return v
