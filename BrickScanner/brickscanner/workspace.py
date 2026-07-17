"""
Workspace discovery and notebook content utilities.

Handles authentication, recursive notebook path listing, content reading,
and job-to-notebook association.
"""

from __future__ import annotations

import json
from typing import Any

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.workspace import ExportFormat
from pyspark.sql import SparkSession


# ---------------------------------------------------------------------
# Notebook content parser
# ---------------------------------------------------------------------


class NBContent:
    """Parse a Jupyter-format notebook and extract unique cell text."""

    def __init__(self, nbdata: dict) -> None:
        self._cells = nbdata.get("cells", []) if nbdata else []

    def get_code_list(self) -> tuple[list[str], list[str]]:
        """
        Return:
            (code_cells, markdown_cells)

        Duplicate cells are removed while preserving order.
        """

        code = list(
            dict.fromkeys(
                "".join(cell.get("source", []))
                for cell in self._cells
                if cell.get("cell_type") == "code"
            )
        )

        markdown = list(
            dict.fromkeys(
                "".join(cell.get("source", []))
                for cell in self._cells
                if cell.get("cell_type") == "markdown"
            )
        )

        return code, markdown


# ---------------------------------------------------------------------
# Format conversion
# ---------------------------------------------------------------------


def _py2nb(py_str: str) -> dict:
    """Convert a Databricks Python script into Jupyter notebook format."""

    header = "# Databricks notebook source\n"
    delimiter = "\n# COMMAND ----------\n\n"

    if py_str.startswith(header):
        py_str = py_str[len(header):]

    cells = [
        {
            "cell_type": "code",
            "metadata": {},
            "source": chunk.splitlines(True),
            "outputs": [],
            "execution_count": None,
        }
        for chunk in py_str.split(delimiter)
    ]

    return {
        "cells": cells,
        "nbformat": 4,
        "nbformat_minor": 1,
        "metadata": {},
    }


# ---------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------


def get_workspace_client(spark: SparkSession) -> WorkspaceClient:
    """Return an authenticated WorkspaceClient."""

    from pyspark.dbutils import DBUtils  # noqa: PLC0415

    dbutils = DBUtils(spark)

    return WorkspaceClient(
        host=f"https://{spark.conf.get('spark.databricks.workspaceUrl')}",
        token=dbutils.notebook.entry_point.getDbutils()
        .notebook()
        .getContext()
        .apiToken()
        .get(),
    )


# ---------------------------------------------------------------------
# Notebook discovery
# ---------------------------------------------------------------------


def get_nb_paths(
    wobj: WorkspaceClient,
    folder_paths: str,
    exclusion_list: list[str],
) -> list[tuple]:
    """
    Recursively list notebooks and .py files under the given folders.
    """

    collected: list[tuple] = []

    def _is_scannable(item: Any) -> bool:
        return (
            item.object_type.value == "NOTEBOOK"
            or (
                item.object_type.value == "FILE"
                and item.path.lower().endswith(".py")
            )
        )
            def _recurse(folder: str) -> None:
        try:
            objects = wobj.workspace.list(folder)

            if not objects:
                return

            for item in objects:
                if (
                    item.object_type
                    and item.object_type.value == "DIRECTORY"
                ):
                    _recurse(item.path)

                elif _is_scannable(item):
                    collected.append(
                        (
                            item.path,
                            item.object_id,
                            item.object_type.value,
                            getattr(item, "language", None),
                            item.created_at,
                            item.modified_at,
                        )
                    )

        except Exception as exc:
            print(f"[workspace] Error listing {folder}: {exc}")

    for folder in (
        f.strip()
        for f in folder_paths.split(",")
        if f.strip()
    ):
        print(f"[workspace] Scanning: {folder}")
        _recurse(folder)

    # Apply exclusion list (suffix match)
    excluded: list[str] = []
    kept: list[tuple] = []

    for entry in collected:
        if any(entry[0].endswith(excl) for excl in exclusion_list):
            excluded.append(entry[0])
        else:
            kept.append(entry)

    if excluded:
        print(f"[workspace] Excluded {len(excluded)} path(s):")
        for path in excluded:
            print(f"  - {path}")

    print(f"[workspace] Found {len(kept)} path(s) to scan.")

    return kept


# ---------------------------------------------------------------------
# Content reading
# ---------------------------------------------------------------------


def read_nb_content(
    wobj: WorkspaceClient,
    path_tuple: tuple,
) -> dict:
    """
    Read and return notebook/.py content as a Jupyter notebook dict.
    """

    path, _, asset_type, *_ = path_tuple

    try:
        if asset_type == "NOTEBOOK":
            with wobj.workspace.download(
                path,
                format=ExportFormat.JUPYTER,
            ) as f:
                return json.load(f)

        elif asset_type == "FILE":
            with wobj.workspace.download(path) as f:
                return _py2nb(
                    f.read().decode("utf-8")
                )

    except Exception as exc:
        print(f"[workspace] Error reading {path}: {exc}")

    return {}


# ---------------------------------------------------------------------
# Job details
# ---------------------------------------------------------------------


def get_job_details(
    wobj: WorkspaceClient,
) -> list[tuple]:
    """
    Return:
        (job_id, format, job_name, task_key, notebook_path)
        for every notebook task.
    """

    details: list[tuple] = []

    for job in wobj.jobs.list(expand_tasks=True):
        if job.settings and job.settings.tasks:
            for task in job.settings.tasks:
                if (
                    task.notebook_task
                    and task.notebook_task.notebook_path
                ):
                    details.append(
                        (
                            job.job_id,
                            job.settings.format.value
                            if job.settings.format
                            else "UNKNOWN",
                            job.settings.name,
                            task.task_key,
                            task.notebook_task.notebook_path,
                        )
                    )

    return details


# ---------------------------------------------------------------------
# Notebook processing
# ---------------------------------------------------------------------


def build_notebook_records(
    wobj: WorkspaceClient,
    nb_paths: list[tuple],
    host_url: str,
) -> list[dict]:
    """
    Process discovered notebooks into enriched records containing metadata,
    code cells, markdown cells and job associations.

    Returns:
        List of dictionaries with notebook metadata and content.
    """

    print(f"[workspace] Processing {len(nb_paths)} notebook(s)...")

    job_details = get_job_details(wobj)
    records: list[dict] = []

    for (
        path,
        nb_id,
        _,
        lang,
        created_at,
        modified_at,
    ) in nb_paths:

        nb_data = read_nb_content(
            wobj,
            (path, nb_id, _, lang, created_at, modified_at),
        )

        if not nb_data:
            continue

        processor = NBContent(nb_data)
        code_list, markdown_list = processor.get_code_list()

        nb_name = path.split("/")[-1]

        related_jobs = [
            job
            for job in job_details
            if job[4].endswith(nb_name)
        ]

        records.append(
            {
                "notebook_id": nb_id,
                "notebook_name": nb_name,
                "notebook_path": path,
                "notebook_url": f"{host_url}/#notebook/{nb_id}",
                "notebook_language": (
                    lang.value if lang else None
                ),
                "notebook_code": code_list,
                "notebook_markdowns": markdown_list,
                "notebook_created_at": created_at,
                "notebook_modified_at": modified_at,
                "job_ids": ",".join(
                    str(job[0]) for job in related_jobs
                ),
                "job_names": ",".join(
                    job[2] for job in related_jobs
                ),
            }
        )

    return records

    