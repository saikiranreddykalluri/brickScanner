"""
BrickScanner pipeline: discover -> chunk -> AI review -> persist.

LLM output is validated through Pydantic models (ReviewResponse / RuleReview).
Validated objects are flattened via model_dump(), bridged through a pandas
DataFrame, and written to Delta via spark.createDataFrame(pd_df).
"""

from __future__ import annotations

import re
import traceback
import uuid
from typing import Optional

import pandas as pd
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain.docstore.document import Document
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_databricks import ChatDatabricks
from langchain_text_splitters import (
    Language,
    RecursiveCharacterTextSplitter,
)
from pydantic import ValidationError
from pyspark.sql import DataFrame, SparkSession

from brickscanner import workspace
from brickscanner.config import (
    CHUNK_SIZE,
    DB_TABLES,
    EXCLUSION_LIST,
    LLM_MODEL_NAME,
)
from brickscanner.models import ReviewResponse
from brickscanner.prompts import build_prompt


# ---------------------------------------------------------------------
# Data-layer helpers
# ---------------------------------------------------------------------

def _load_rules(spark: SparkSession) -> list[dict]:
    """Fetch enabled rules from the genai_rule_patterns table."""

    df = spark.sql(
        f"""
        SELECT
            rule_id,
            rule_name,
            rule_description,
            rule_sample
        FROM {DB_TABLES["genai_rule_patterns"]}
        WHERE is_enabled = true
        """
    )

    rules = [row.asDict() for row in df.collect()]
    print(f"[scanner] Loaded {len(rules)} enabled rule(s).")
    return rules


def _load_feedback(spark: SparkSession) -> dict[str, dict]:
    """Fetch historical reviewer feedback keyed by rule_name."""

    df = spark.sql(
        f"""
        SELECT
            rule_name,
            feedback,
            previous_finding_comment
        FROM {DB_TABLES["genai_feedback"]}
        WHERE feedback IS NOT NULL
          AND TRIM(feedback) != ''
        """
    )

    feedback_map = {
        row["rule_name"]: {
            "feedback": row["feedback"],
            "previous_finding_comment": row["previous_finding_comment"],
        }
        for row in df.collect()
    }

    print(f"[scanner] Loaded feedback for {len(feedback_map)} rule(s).")
    return feedback_map


# ---------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------

def _load_llm() -> ChatDatabricks:
    """Initialise the Databricks LLM endpoint."""

    print(f"[scanner] Initialising LLM: {LLM_MODEL_NAME}")

    llm = ChatDatabricks(
        endpoint=LLM_MODEL_NAME,
    )

    print("[scanner] LLM ready.")
    return llm

# ---------------------------------------------------------------------
# Notebook chunking
# ---------------------------------------------------------------------

def _get_notebook_chunks(
    spark: SparkSession,
    include_paths: str,
) -> list[Document]:
    """Discover notebooks under *include_paths*, read code cells, and chunk."""

    print("[scanner] Fetching notebook data...")

    wobj = workspace.get_workspace_client(spark)

    nb_paths = workspace.get_nb_paths(
        wobj,
        include_paths,
        EXCLUSION_LIST,
    )

    if not nb_paths:
        print("[scanner] No notebooks found.")
        return []

    host_url = f"https://{spark.conf.get('spark.databricks.workspaceUrl')}"

    records = workspace.build_notebook_records(
        wobj,
        nb_paths,
        host_url,
    )

    documents = [
        Document(
            page_content="\n".join(item["notebook_code"]),
            metadata={
                "source": item["notebook_path"],
                "notebook_id": item["notebook_id"],
                "notebook_url": item["notebook_url"],
            },
        )
        for item in records
        if item.get("notebook_code")
    ]

    splitter = RecursiveCharacterTextSplitter.from_language(
        language=Language.PYTHON,
        chunk_size=CHUNK_SIZE,
        chunk_overlap=0,
    )

    chunks = splitter.split_documents(documents)

    print(f"[scanner] Split into {len(chunks)} chunk(s).")

    return chunks


# ---------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------

def _parse_response(raw: str) -> ReviewResponse | None:
    """
    Validate the LLM output string into a typed ReviewResponse.
    """

    if not isinstance(raw, str):
        return None

    match = re.search(r"\{[\s\S]*\}", raw)

    if not match:
        print(f"[scanner] Model output could not be parsed: {raw[:200]}")
        return None

    try:
        return ReviewResponse.model_validate_json(match.group(0))

    except ValidationError as exc:
        print(f"[scanner] Response validation failed: {exc}")
        return None


def _process_chunks(
    llm: ChatDatabricks,
    prompt: ChatPromptTemplate,
    documents: list[Document],
) -> tuple[list[dict], list[tuple]]:
    """
    Run the review chain over each chunk.

    Returns:
        (successful_reviews, failed_reviews)
    """

    chain = create_stuff_documents_chain(
        llm=llm,
        prompt=prompt,
        output_parser=StrOutputParser(),
    )

    successes: list[dict] = []
    errors: list[tuple] = []

    for doc in documents:
        try:
            raw = chain.invoke({"context": [doc]})

            response = _parse_response(raw)

            if response is None:
                raise ValueError(
                    f"Could not parse model output: {raw[:300]}"
                )

            successes.append(
                {
                    "metadata": doc.metadata,
                    "resp": response,
                }
            )

        except Exception as exc:
            errors.append(
                (
                    doc.metadata.get("source"),
                    str(exc),
                )
            )

    print(
        f"[scanner] Done -- success: {len(successes)}, "
        f"errors: {len(errors)}"
    )

    return successes, errors

# ---------------------------------------------------------------------
# DataFrame construction
# ---------------------------------------------------------------------

_DF_COLUMNS = [
    "notebook_path",
    "notebook_id",
    "notebook_url",
    "rule_id",
    "comment",
    "severity",
    "matching_content",
]


def _build_results_df(
    spark: SparkSession,
    processed: list[dict],
) -> DataFrame:
    """
    Flatten ReviewResponse objects into a Spark DataFrame.

    Pipeline::

        ReviewResponse
            -> review.model_dump()
            -> list[dict]
            -> pandas.DataFrame
            -> Spark DataFrame
    """

    rows: list[dict] = []

    for item in processed:
        meta: dict = item["metadata"]
        response: ReviewResponse = item["resp"]

        for review in response.Review:
            row = review.model_dump(by_alias=False)

            row["notebook_path"] = meta.get("source")
            row["notebook_id"] = meta.get("notebook_id")
            row["notebook_url"] = meta.get("notebook_url")

            rows.append(row)

    if not rows:
        return spark.createDataFrame(
            pd.DataFrame(columns=_DF_COLUMNS)
        )

    pd_df = pd.DataFrame(rows, columns=_DF_COLUMNS)

    return spark.createDataFrame(pd_df)


# ---------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------

def _save_results(
    spark: SparkSession,
    df: DataFrame,
) -> None:
    """
    Persist scan findings into the genai_output table.
    """

    view = f"tmp_scan_{uuid.uuid4().hex[:8]}"

    df.createOrReplaceTempView(view)

    spark.sql(
        f"""
        INSERT INTO {DB_TABLES["genai_output"]} (

            notebook_id,
            notebook_name,
            notebook_path,
            notebook_url,
            rule_name,
            comment,
            severity,
            matching_content,
            batch_id,
            review_flag,
            review_comments,
            created_by,
            created_ts

        )

        SELECT

            t.notebook_id,

            element_at(
                split(t.notebook_path, '/'),
                -1
            ) AS notebook_name,

            t.notebook_path,
            t.notebook_url,

            g.rule_name,

            t.comment,
            t.severity,
            t.matching_content,

            CAST(
                date_format(
                    current_timestamp(),
                    'yyyyMMddHHmmssSSS'
                ) AS BIGINT
            ) AS batch_id,

            FALSE AS review_flag,
            'Unresolved' AS review_comments,

            current_user() AS created_by,

            current_timestamp() AS created_ts

        FROM {view} t

        LEFT JOIN {DB_TABLES["genai_rule_patterns"]} g
            ON g.rule_id = t.rule_id

        WHERE t.severity IS NOT NULL
          AND t.severity <> 'N/A'
        """
    )

    print("[scanner] Results written successfully.")
 
# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def run(
    spark: SparkSession,
    extractor_type: str,
    include_paths: str = "/Workspace",
    dry_run: bool = False,
) -> Optional[DataFrame]:
    """
    Execute the BrickScanner pipeline.

    Steps:
        1. Load enabled rules.
        2. Load reviewer feedback.
        3. Initialize LLM.
        4. Discover notebooks.
        5. Chunk notebook code.
        6. Review each chunk.
        7. Build Spark DataFrame.
        8. Persist results (or return DataFrame in dry-run mode).

    Args:
        spark:
            Active SparkSession.

        extractor_type:
            Scanner implementation name (reserved for future use).

        include_paths:
            Workspace path(s) to scan.

        dry_run:
            If True, results are returned without writing to Delta.

    Returns:
        Spark DataFrame when dry_run=True, otherwise None.
    """

    print(
        f"[scanner] Starting scan | "
        f"extractor={extractor_type} | "
        f"dry_run={dry_run}"
    )

    try:
        # -------------------------------------------------------------
        # Load rules
        # -------------------------------------------------------------
        rules = _load_rules(spark)

        if not rules:
            print("[scanner] No enabled rules found.")
            return None

        # -------------------------------------------------------------
        # Load historical feedback
        # -------------------------------------------------------------
        feedback = _load_feedback(spark)

        # -------------------------------------------------------------
        # Initialize LLM
        # -------------------------------------------------------------
        llm = _load_llm()

        prompt = build_prompt(
            rules=rules,
            feedback_map=feedback,
        )

        # -------------------------------------------------------------
        # Read & chunk notebooks
        # -------------------------------------------------------------
        chunks = _get_notebook_chunks(
            spark=spark,
            include_paths=include_paths,
        )

        if not chunks:
            print("[scanner] No notebook content found.")
            return None

        print(f"[scanner] Reviewing {len(chunks)} chunk(s)...")

        # -------------------------------------------------------------
        # Run LLM review
        # -------------------------------------------------------------
        processed, errors = _process_chunks(
            llm=llm,
            prompt=prompt,
            documents=chunks,
        )

        if errors:
            print(
                f"[scanner] {len(errors)} chunk(s) failed during processing."
            )

            for notebook, error in errors:
                print(f"  - {notebook}: {error}")

        if not processed:
            print("[scanner] No review results produced.")
            return None

        # -------------------------------------------------------------
        # Convert to Spark DataFrame
        # -------------------------------------------------------------
        df = _build_results_df(
            spark=spark,
            processed=processed,
        )

        # -------------------------------------------------------------
        # Dry run - filter and materialize results
        # -------------------------------------------------------------
        if dry_run:
            result = df.filter("severity != 'N/A'")
            count = result.count()  # Materialize result
            print(f"[scanner] Dry run complete. Found {count} finding(s).")
            return result

        # -------------------------------------------------------------
        # Persist findings
        # -------------------------------------------------------------
        _save_results(
            spark=spark,
            df=df,
        )

        print("[scanner] Scan completed successfully.")

        return None

    except Exception as exc:
        print(f"[scanner] Scan failed: {exc}")
        traceback.print_exc()
        raise

