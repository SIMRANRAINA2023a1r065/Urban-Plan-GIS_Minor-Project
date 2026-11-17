import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["roadmap"])
ROADMAP_PATH = Path(__file__).resolve().parent.parent.parent / "roadmap.json"


@router.get("/roadmap")
def get_roadmap():
    """The 12-week Phase 1 backlog, as data -- so the frontend's timeline can fetch
    this instead of hardcoding the week list in index.html."""
    return json.loads(ROADMAP_PATH.read_text())
