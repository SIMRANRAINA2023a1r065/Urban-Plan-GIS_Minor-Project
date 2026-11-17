"""OpenStreetMap collector using osmnx: buildings, roads, POIs, land use, boundaries."""
import logging

import geopandas as gpd
import osmnx as ox

from .base import BaseCollector, retry

log = logging.getLogger(__name__)

ox.settings.use_cache = True
ox.settings.requests_timeout = 180

BUILDING_EXTRA = ["height", "building:levels", "amenity", "shop", "office", "landuse"]
ROAD_KEEP = ["osmid", "highway", "name", "length", "oneway", "lanes", "maxspeed",
             "bridge", "tunnel", "surface", "geometry"]
DEFAULT_POI_TAGS = {"amenity": True, "shop": True, "public_transport": True,
                    "railway": ["station", "halt"], "highway": ["bus_stop"],
                    "tourism": True, "healthcare": True}
DEFAULT_LANDUSE_TAGS = {"landuse": True, "natural": True, "leisure": True}
DEFAULT_BOUNDARY_TAGS = {"boundary": "administrative"}


def _nothing_found(exc):
    """True when OSM simply has nothing there (an empty tile), as opposed to a real failure."""
    n = type(exc).__name__
    msg = str(exc).lower()
    return ("InsufficientResponse" in n or "EmptyOverpass" in n
            or "no graph nodes" in msg or "no graph edges" in msg)


class OSMCollector(BaseCollector):
    name = "osm"

    def __init__(self, cfg, raw_dir, refresh=False):
        super().__init__(cfg, raw_dir, refresh)
        url = self.cfg.get("overpass_url")      # optional: use another Overpass server if the default one is slow
        if url and hasattr(ox.settings, "overpass_url"):
            ox.settings.overpass_url = url

    @retry(times=3, delay=10)
    def _features(self, label, aoi_poly, tags, extra_cols, geom="polygon"):
        cached = self.load_cache(label)
        if cached is not None:
            return cached
        log.info("[osm] downloading %s ...", label)
        try:
            gdf = ox.features_from_polygon(aoi_poly, tags=tags)
        except Exception as exc:  # noqa: BLE001
            if _nothing_found(exc):
                log.warning("[osm] no %s returned for this AOI", label)
                return self.empty()
            raise
        gdf = gdf.reset_index()
        idcol = "id" if "id" in gdf else ("osmid" if "osmid" in gdf else None)
        elcol = "element" if "element" in gdf else ("element_type" if "element_type" in gdf else None)
        if idcol and elcol:
            gdf["osm_id"] = gdf[elcol].astype(str) + "/" + gdf[idcol].astype(str)
        if geom == "polygon":
            gdf = gdf[gdf.geometry.type.isin(["Polygon", "MultiPolygon"])].copy()
        else:  # points of interest: collapse polygons to one representative point
            gdf = gdf[gdf.geometry.type.isin(["Point", "Polygon", "MultiPolygon"])].copy()
            gdf["geometry"] = gdf.geometry.representative_point()
        wanted = ["osm_id", "name"] + list(tags.keys()) + list(extra_cols) + ["geometry"]
        keep = list(dict.fromkeys(c for c in wanted if c in gdf.columns))
        gdf = gpd.GeoDataFrame(gdf[keep], geometry="geometry", crs=gdf.crs)
        self.save_cache(gdf, label)
        log.info("[osm] %d %s", len(gdf), label)
        return gdf

    def fetch_buildings(self, aoi_poly):
        return self._features("buildings", aoi_poly,
                              self.cfg.get("building_tags", {"building": True}), BUILDING_EXTRA)

    def fetch_pois(self, aoi_poly):
        return self._features("pois", aoi_poly, self.cfg.get("poi_tags", DEFAULT_POI_TAGS), [], "point")

    def fetch_landuse(self, aoi_poly):
        return self._features("landuse", aoi_poly,
                              self.cfg.get("landuse_tags", DEFAULT_LANDUSE_TAGS), [])

    def fetch_boundaries(self, aoi_poly):
        return self._features("boundaries", aoi_poly, DEFAULT_BOUNDARY_TAGS, ["admin_level"])

    @retry(times=3, delay=10)
    def fetch_roads(self, aoi_poly):
        cached = self.load_cache("roads")
        if cached is not None:
            return cached
        log.info("[osm] downloading road network ...")
        try:
            graph = ox.graph_from_polygon(
                aoi_poly, network_type=self.cfg.get("network_type", "all"),
                simplify=True, retain_all=True, truncate_by_edge=True)
        except Exception as exc:  # noqa: BLE001
            if _nothing_found(exc):
                log.warning("[osm] no roads returned for this AOI")
                return self.empty()
            raise
        ox.save_graphml(graph, self.cache_path("roads_graph", "graphml"))
        edges = ox.graph_to_gdfs(graph, nodes=False).reset_index()
        keep = [c for c in ["u", "v"] + ROAD_KEEP if c in edges.columns]
        edges = gpd.GeoDataFrame(edges[keep], geometry="geometry", crs=edges.crs)
        self.save_cache(edges, "roads")
        log.info("[osm] %d road segments", len(edges))
        return edges
