import json

from fastapi import APIRouter, HTTPException

from ..config import PROCESSED_DIR

router = APIRouter(tags=["summary"])


@router.get("/summary")
def get_summary():
    """coverage_summary.json from the pipeline: feature counts, per-source status (ok/FAILED/skipped), etc."""
    path = PROCESSED_DIR / "coverage_summary.json"
    if not path.exists():
        raise HTTPException(404, f"{path} not found. Run the geo-collector pipeline first.")
    return json.loads(path.read_text())


@router.get("/data-dictionary")
def get_data_dictionary():
    """DATA_DICTIONARY.md that write_dictionary() produces, returned as raw markdown."""
    path = PROCESSED_DIR / "DATA_DICTIONARY.md"
    if not path.exists():
        raise HTTPException(404, f"{path} not found. Run the geo-collector pipeline first.")
    return {"markdown": path.read_text()}
