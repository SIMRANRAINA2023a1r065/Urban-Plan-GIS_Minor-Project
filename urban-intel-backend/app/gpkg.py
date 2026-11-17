"""Thin read layer over the GeoPackage that run.py / run_tiled.py produce.
We never write to it here -- the backend only serves what the pipeline already built."""
from typing import Optional, Tuple

import fiona
import geopandas as gpd
from fastapi import HTTPException

from .config import GPKG_PATH


def _require_gpkg():
    if not GPKG_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"GeoPackage not found at {GPKG_PATH}. "
                "Run the geo-collector pipeline first (python run.py in geo-collector/), "
                "or set GEO_PROCESSED_DIR / GEO_GPKG_NAME in .env to point at the right folder."
            ),
        )


def list_layers():
    _require_gpkg()
    return fiona.listlayers(str(GPKG_PATH))


def read_layer(name: str, bbox: Optional[Tuple[float, float, float, float]] = None,
               limit: Optional[int] = None) -> gpd.GeoDataFrame:
    layers = list_layers()
    if name not in layers:
        raise HTTPException(status_code=404, detail=f"Layer '{name}' not found. Available layers: {layers}")
    gdf = gpd.read_file(str(GPKG_PATH), layer=name, bbox=bbox) if bbox else gpd.read_file(str(GPKG_PATH), layer=name)
    if limit:
        gdf = gdf.head(limit)
    return gdf
