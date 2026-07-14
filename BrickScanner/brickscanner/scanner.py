"""
BrickScanner main scanning pipeline.

Orchestrates discovery, LLM invocation, parsing, and persistence of code review findings.
"""

import logging
import re
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.types import (
    StructType, StructField, StringType, LongType, TimestampType
)
import pandas as pd

from brickscanner.config import (
    DB_TABLES, CHUNK_SIZE, LLM_MODEL_NAME, EXCLUSION_LIST
)
from brickscanner.models import ReviewResponse
from brickscanner.workspace import (
    get_workspace_client, get_nb_paths, read_nb_content
)
from brickscanner.prompts import build_review_prompt, format_code_chunk_prompt

logger = logging.getLogger("[scanner]")


def _load_rules(spark: SparkSession) -> List[Dict]:
    """
    Load enabled rules from Databricks table.
    
    Args:
        spark: SparkSession
    
    Returns:
        List of rule dicts with keys: rule_id, rule_name, rule_description, rule_sample
    """
    try:
        table_name = DB_TABLES["genai_rule_patterns"]
        df = spark.sql(f"SELECT rule_id, rule_name, rule_description, rule_category, rule_sample FROM {table_name} WHERE is_enabled = true")
        rules = []
        for row in df.collect():
            rules.append({
                "rule_id": str(row.rule_id),
                "rule_name": row.rule_name,
                "rule_description": row.rule_description,
                "rule_category": row.rule_category,
                "rule_sample": row.rule_sample,
            })
        logger.info(f"[scanner] Loaded {len(rules)} enabled rules")
        return rules
    except Exception as e:
        logger.error(f"[scanner] Failed to load rules: {e}")
        raise


def _load_llm():
    """
    Instantiate Databricks LLM chat client.
    
    Returns:
        ChatDatabricks instance configured for LLM_MODEL_NAME
    """
    try:
        from langchain_databricks import ChatDatabricks
        llm = ChatDatabricks(endpoint_name=LLM_MODEL_NAME)
        logger.info(f"[scanner] Initialized LLM: {LLM_MODEL_NAME}")
        return llm
    except Exception as e:
        logger.error(f"[scanner] Failed to load LLM: {e}")
        raise


def _get_notebook_chunks(spark: SparkSession, include_paths: List[str]):
    """
    Discover workspace notebooks/Python files and split into chunks.
    
    Uses RecursiveCharacterTextSplitter from LangChain for semantic splitting.
    
    Args:
        spark: SparkSession
        include_paths: List of workspace paths to scan
    
    Returns:
        List of LangChain Document objects with metadata
    """
    try:
        from langchain.text_splitter import RecursiveCharacterTextSplitter, Language
        from langchain.schema import Document
        
        wobj = get_workspace_client(spark)
        
        # Discover paths
        nb_paths = get_nb_paths(wobj, include_paths, EXCLUSION_LIST)
        logger.info(f"[scanner] Found {len(nb_paths)} files to scan")
        
        # Read and chunk
        documents = []
        for path_tuple in nb_paths:
            path = path_tuple[0]
            try:
                content = read_nb_content(wobj, path_tuple)
                if not content or len(content) < 100:
                    logger.debug(f"Skipping empty/too-small file: {path}")
                    continue
                
                # Create text splitter
                splitter = RecursiveCharacterTextSplitter.from_language(
                    language=Language.PYTHON,
                    chunk_size=CHUNK_SIZE,
                    chunk_overlap=0
                )
                
                # Split into chunks
                chunks = splitter.split_text(content)
                
                for i, chunk in enumerate(chunks):
                    doc = Document(
                        page_content=chunk,
                        metadata={
                            "source": path,
                            "chunk_index": i,
                            "total_chunks": len(chunks),
                        }
                    )
                    documents.append(doc)
                
                logger.debug(f"[scanner] Split {path} into {len(chunks)} chunks")
            except Exception as e:
                logger.warning(f"[scanner] Error processing {path}: {e}")
        
        logger.info(f"[scanner] Created {len(documents)} total chunks")
        return documents
    except Exception as e:
        logger.error(f"[scanner] Failed to create chunks: {e}")
        raise


def _parse_response(raw_output: str) -> Optional[ReviewResponse]:
    """
    Extract and validate JSON from LLM response.
    
    Regex-extracts JSON block, then validates via Pydantic ReviewResponse.
    
    Args:
        raw_output: Raw LLM response (may contain prose or markdown)
    
    Returns:
        Validated ReviewResponse object, or None on failure
    """
    try:
        # Try direct JSON parse first
        try:
            parsed = ReviewResponse.model_validate_json(raw_output)
            return parsed
        except Exception:
            pass
        
        # Regex extract JSON
        json_match = re.search(r'\{[\s\S]*\}', raw_output)
        if not json_match:
            logger.warning("[scanner] No JSON found in LLM response")
            return None
        
        json_str = json_match.group(0)
        parsed = ReviewResponse.model_validate_json(json_str)
        return parsed
    except Exception as e:
        logger.error(f"[scanner] Failed to parse response: {e}")
        logger.debug(f"Raw output: {raw_output[:500]}")
        return None


def _process_chunks(
    llm,
    prompt_template: str,
    documents: List
) -> Tuple[List[Dict], List[str]]:
    """
    Process each document chunk through LLM.
    
    Uses langchain create_stuff_documents_chain for RAG-style prompt formatting.
    
    Args:
        llm: ChatDatabricks instance
        prompt_template: Base prompt from build_review_prompt()
        documents: List of LangChain Document objects
    
    Returns:
        Tuple of (successes list, errors list)
        - successes: List of dicts with source metadata + parsed response
        - errors: List of error strings
    """
    try:
        from langchain.chains.combine_documents import create_stuff_documents_chain
        from langchain_core.prompts import ChatPromptTemplate
        
        successes = []
        errors = []
        
        # Create chain
        prompt = ChatPromptTemplate.from_template(prompt_template)
        chain = create_stuff_documents_chain(llm, prompt)
        
        logger.info(f"[scanner] Processing {len(documents)} chunks through LLM")
        
        for idx, doc in enumerate(documents):
            try:
                # Invoke chain
                response = chain.invoke({
                    "context": [doc],
                    "question": "Review this code against all rules"
                })
                
                # Parse response
                parsed = _parse_response(response)
                if parsed:
                    # Flatten parsed findings with source metadata
                    for review in parsed.Review:
                        finding = {
                            "source": doc.metadata.get("source"),
                            "chunk_index": doc.metadata.get("chunk_index", 0),
                            "rule_id": review.rule_id,
                            "comment": review.comment,
                            "severity": review.severity,
                            "matching_content": review.matching_content,
                        }
                        successes.append(finding)
                else:
                    errors.append(f"Chunk {idx}: Could not parse response")
            
            except Exception as e:
                errors.append(f"Chunk {idx}: {str(e)}")
            
            if (idx + 1) % 10 == 0:
                logger.info(f"[scanner] Processed {idx + 1}/{len(documents)} chunks")
        
        logger.info(f"[scanner] Completed processing: {len(successes)} findings, {len(errors)} errors")
        return successes, errors
    except Exception as e:
        logger.error(f"[scanner] Failed to process chunks: {e}")
        raise


def _build_results_df(spark: SparkSession, processed: List[Dict]) -> DataFrame:
    """
    Flatten processed findings into Spark DataFrame.
    
    Args:
        spark: SparkSession
        processed: List of finding dicts from _process_chunks
    
    Returns:
        Spark DataFrame with columns: notebook_path, notebook_id, notebook_url, rule_id, comment, severity, matching_content
    """
    try:
        # Convert to pandas first for flexibility
        data = []
        for finding in processed:
            notebook_path = finding.get("source", "unknown")
            # Derive notebook_name from path (last component)
            notebook_name = notebook_path.split("/")[-1] if notebook_path else "unknown"
            # Construct notebook_url
            notebook_url = f"https://adb-WORKSPACE_ID.azuredatabricks.net/?o=WORKSPACE_ID#notebook/{notebook_path}"
            
            data.append({
                "notebook_path": notebook_path,
                "notebook_id": finding.get("source"),  # Could be enhanced
                "notebook_name": notebook_name,
                "notebook_url": notebook_url,
                "rule_id": finding.get("rule_id"),
                "comment": finding.get("comment"),
                "severity": finding.get("severity"),
                "matching_content": finding.get("matching_content"),
            })
        
        pdf = pd.DataFrame(data)
        
        # Convert to Spark DataFrame
        schema = StructType([
            StructField("notebook_path", StringType(), True),
            StructField("notebook_id", StringType(), True),
            StructField("notebook_name", StringType(), True),
            StructField("notebook_url", StringType(), True),
            StructField("rule_id", StringType(), True),
            StructField("comment", StringType(), True),
            StructField("severity", StringType(), True),
            StructField("matching_content", StringType(), True),
        ])
        
        df = spark.createDataFrame(pdf, schema=schema)
        logger.info(f"[scanner] Built results DataFrame: {df.count()} rows")
        return df
    except Exception as e:
        logger.error(f"[scanner] Failed to build results DataFrame: {e}")
        raise


def _save_results(spark: SparkSession, df: DataFrame) -> None:
    """
    Save findings to genai_output table.
    
    Joins rule_id to rule_name, adds batch_id, filters out N/A severity.
    
    Args:
        spark: SparkSession
        df: Results DataFrame from _build_results_df
    """
    try:
        # Filter out N/A severity
        df_filtered = df.filter(df.severity != "N/A")
        
        if df_filtered.count() == 0:
            logger.info("[scanner] No non-N/A findings to persist")
            return
        
        # Join to rules table for rule_name
        rules_table = DB_TABLES["genai_rule_patterns"]
        rules_df = spark.sql(f"SELECT rule_id, rule_name FROM {rules_table}")
        
        # Convert rule_id to string for join
        rules_df = rules_df.withColumn("rule_id", rules_df.rule_id.cast(StringType()))
        df_joined = df_filtered.join(rules_df, on="rule_id", how="left")
        
        # Generate batch_id from timestamp (yyyyMMddHHmmssSSS as BIGINT)
        batch_id = int(datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3])
        
        # Add metadata columns
        df_final = df_joined.select(
            "notebook_id",
            "notebook_name",
            "notebook_path",
            "notebook_url",
            "rule_name",
            "comment",
            "severity",
            "matching_content",
        ).withColumn(
            "batch_id", pd.Timestamp(datetime.now()).value
        ).withColumn(
            "created_by", spark.sql("SELECT current_user()").collect()[0][0]
        ).withColumn(
            "created_ts", spark.sql("SELECT current_timestamp()").collect()[0][0]
        )
        
        # Insert into table
        output_table = DB_TABLES["genai_output"]
        df_final.write.insertInto(output_table)
        
        logger.info(f"[scanner] Persisted {df_final.count()} findings to {output_table}")
    except Exception as e:
        logger.error(f"[scanner] Failed to save results: {e}")
        raise


def run(
    spark: SparkSession,
    extractor_type: str = "genai",
    include_paths: str = "/Workspace",
    dry_run: bool = False
) -> Optional[DataFrame]:
    """
    Execute full BrickScanner pipeline.
    
    Orchestrates:
    1. Load enabled rules
    2. Discover and chunk notebooks/Python files
    3. Process chunks through LLM
    4. Build and validate results
    5. Persist findings (unless dry_run)
    
    Args:
        spark: SparkSession
        extractor_type: Type of extractor (default "genai")
        include_paths: Comma-separated workspace paths to scan
        dry_run: If True, return DataFrame without persisting
    
    Returns:
        Filtered DataFrame of findings on dry_run, None otherwise
        
    Raises:
        ValueError: On unrecoverable errors
    """
    try:
        logger.info(f"[scanner] Starting BrickScanner run (dry_run={dry_run})")
        
        # Parse include_paths
        if isinstance(include_paths, str):
            paths_list = [p.strip() for p in include_paths.split(",") if p.strip()]
        else:
            paths_list = include_paths
        
        if not paths_list:
            raise ValueError("include_paths cannot be empty")
        
        logger.info(f"[scanner] Scanning paths: {paths_list}")
        
        # Load rules
        rules = _load_rules(spark)
        if not rules:
            logger.warning("[scanner] No enabled rules found")
            return None
        
        # Load LLM
        llm = _load_llm()
        
        # Get notebook chunks
        documents = _get_notebook_chunks(spark, paths_list)
        if not documents:
            logger.warning("[scanner] No documents found to scan")
            return None
        
        # Build prompt
        from brickscanner.models import ReviewResponse
        schema = ReviewResponse.model_json_schema()
        prompt_template = build_review_prompt(rules, schema)
        
        # Process chunks
        successes, errors = _process_chunks(llm, prompt_template, documents)
        
        if errors:
            logger.warning(f"[scanner] {len(errors)} processing errors encountered")
        
        # Build DataFrame
        df = _build_results_df(spark, successes)
        
        # Persist or return
        if dry_run:
            logger.info("[scanner] Dry run mode: returning DataFrame without persisting")
            return df
        else:
            _save_results(spark, df)
            logger.info("[scanner] BrickScanner run completed successfully")
            return None
    
    except Exception as e:
        logger.error(f"[scanner] Unrecoverable error: {e}")
        raise
