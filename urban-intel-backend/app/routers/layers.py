from typing import Optional

from fastapi import APIRouter, Query, Response

from .. import gpkg

router = APIRouter(tags=["layers"])


@router.get("/layers")
def get_layers():
    """List every layer available in the GeoPackage (buildings, roads, pois, landuse, boundaries, coverage_grid, ...)."""
    return {"layers": gpkg.list_layers()}


@router.get("/layers/{name}")
def get_layer(
    name: str,
    limit: Optional[int] = Query(None, le=20000, description="Cap the number of features returned"),
    minx: Optional[float] = None,
    miny: Optional[float] = None,
    maxx: Optional[float] = None,
    maxy: Optional[float] = None,
):
    """Return one layer as GeoJSON. Pass minx/miny/maxx/maxy (lon/lat) to clip to a bounding box,
    e.g. for only loading the buildings visible in the current map viewport."""
    bbox = (minx, miny, maxx, maxy) if None not in (minx, miny, maxx, maxy) else None
    gdf = gpkg.read_layer(name, bbox=bbox, limit=limit)
    return Response(content=gdf.to_json(), media_type="application/geo+json")
