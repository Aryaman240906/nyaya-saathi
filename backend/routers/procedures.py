"""Procedures router — lookup and browse legal procedure workflows."""
from __future__ import annotations
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from models.schemas import ProcedureWorkflow
import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/procedures", tags=["procedures"])

_procedures: dict[str, dict] = {}


def load_procedures():
    """Load all procedure workflow JSON files."""
    global _procedures
    _procedures = {}
    proc_dir = config.PROCEDURES_DIR
    if not proc_dir.exists():
        logger.warning("Procedures directory does not exist: %s", proc_dir)
        return

    for json_file in sorted(proc_dir.glob("*.json")):
        try:
            data = json.loads(json_file.read_text(encoding="utf-8"))
            pid = data.get("id", json_file.stem)
            _procedures[pid] = data
            logger.info("Loaded procedure: %s", pid)
        except Exception as e:
            logger.error("Failed to load procedure %s: %s", json_file.name, e)

    logger.info("Total procedures loaded: %d", len(_procedures))


@router.get("")
async def list_procedures():
    """List all available procedure workflows."""
    return [
        {
            "id": pid,
            "title": proc.get("title", ""),
            "title_hi": proc.get("title_hi", ""),
            "description": proc.get("description", ""),
            "category": proc.get("category", ""),
        }
        for pid, proc in _procedures.items()
    ]


@router.get("/{procedure_id}")
async def get_procedure(procedure_id: str):
    """Get a specific procedure workflow by ID."""
    if procedure_id not in _procedures:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return _procedures[procedure_id]
