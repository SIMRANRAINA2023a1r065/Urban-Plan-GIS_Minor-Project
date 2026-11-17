"""All paths come from environment variables (see .env.example) so the backend
can point at wherever your geo-collector's data/processed folder actually lives."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Default assumes this backend folder sits next to geo-collector/, e.g.:
#   Minor_Project/
#     geo-collector/data/processed/jammu_phase1.gpkg
#     geointel-frontend/
#     urban-intel-backend/        <- this project
DEFAULT_PROCESSED = BASE_DIR.parent / "geo-collector" / "data" / "processed"

PROCESSED_DIR = Path(os.getenv("GEO_PROCESSED_DIR", str(DEFAULT_PROCESSED)))
GPKG_NAME = os.getenv("GEO_GPKG_NAME", "jammu_phase1.gpkg")
GPKG_PATH = PROCESSED_DIR / GPKG_NAME

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
