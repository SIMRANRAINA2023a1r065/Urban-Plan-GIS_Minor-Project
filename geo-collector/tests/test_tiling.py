import geopandas as gpd
from shapely.geometry import LineString, Point, box

import run_tiled
from collectors.osm import OSMCollector
from tiling import make_tiles

BBOX = [74.80, 32.60, 74.90, 32.68]
AOI = box(*BBOX)


def test_tiles_partition_the_aoi():
    tiles = make_tiles(AOI, 5, 0.001)
    assert len(tiles) == 4
    assert abs(sum(t["core"].area for t in tiles) - AOI.area) < 1e-9
    for i, a in enumerate(tiles):
        for b in tiles[i + 1:]:
            assert a["core"].intersection(b["core"]).area < 1e-12


def _world(tiles):
    edge_x = tiles[0]["core"].bounds[2]                      # a real tile edge
    b = [box(74.81 + i * 0.004, 32.61 + j * 0.004, 74.81 + i * 0.004 + 0.0003, 32.61 + j * 0.004 + 0.0003)
         for i in range(20) for j in range(18)]
    b.append(box(edge_x - 0.00015, 32.62, edge_x + 0.00015, 32.6203))     # straddles the edge
    buildings = gpd.GeoDataFrame({"osm_id": [f"way/{i}" for i in range(len(b))], "building": ["yes"] * len(b)},
                                 geometry=b, crs="EPSG:4326")
    roads = gpd.GeoDataFrame({"osmid": ["1", "2"], "highway": ["primary", "residential"], "lanes": ["2", None]},
                             geometry=[LineString([(74.80, 32.60), (74.90, 32.68)]),
                                       LineString([(74.82, 32.62), (74.8205, 32.6205)])], crs="EPSG:4326")
    pois = gpd.GeoDataFrame({"osm_id": ["node/1", "node/2"], "amenity": ["school", "hospital"], "name": ["a", "b"]},
                            geometry=[Point(edge_x, 32.63), Point(74.85, 32.65)], crs="EPSG:4326")
    landuse = gpd.GeoDataFrame({"osm_id": ["way/9000"], "landuse": ["residential"]}, geometry=[AOI], crs="EPSG:4326")
    return buildings, roads, pois, landuse


def test_district_run_has_no_duplicates_and_no_losses(tmp_path, monkeypatch):
    tiles = make_tiles(AOI, 5, 0.001)
    buildings, roads, pois, landuse = _world(tiles)

    def serve(world):   # emulate Overpass: return whole features that touch the requested polygon
        return lambda self, poly: world[world.intersects(poly)]

    monkeypatch.setattr(OSMCollector, "fetch_buildings", serve(buildings))
    monkeypatch.setattr(OSMCollector, "fetch_roads", serve(roads))
    monkeypatch.setattr(OSMCollector, "fetch_pois", serve(pois))
    monkeypatch.setattr(OSMCollector, "fetch_landuse", serve(landuse))
    monkeypatch.setattr(OSMCollector, "fetch_boundaries", lambda self, poly: self.empty())

    cfg = {"paths": {"raw_dir": str(tmp_path / "raw"), "processed_dir": str(tmp_path / "out")},
           "aoi": {"bbox": BBOX}, "tiling": {"tile_km": 5, "overlap_deg": 0.001},
           "osm": {}, "open_buildings": {"enabled": False}, "rasters": {"enabled": False},
           "processing": {"min_building_area_m2": 10, "overlap_threshold": 0.5, "grid_size_m": 1000},
           "output": {"gpkg_name": "d.gpkg", "write_geojson": False}}
    gpkg = run_tiled.run_tiled(cfg, {"no_open_buildings": True, "no_rasters": True})
    read = lambda n: gpd.read_file(gpkg, layer=n)

    assert len(read("buildings")) == len(buildings)          # edge building counted once
    assert len(read("roads")) == 2                           # long road crossing tiles counted once
    assert len(read("pois")) == 2
    lu = read("landuse")
    assert len(lu) == 1 and abs(lu.geometry.iloc[0].area - AOI.area) < 1e-9   # pieces re-joined
    assert (tmp_path / "out" / "tiles.gpkg").exists()


def test_every_feature_has_exactly_one_owner_on_an_irregular_aoi():
    import numpy as np
    from shapely.geometry import Polygon
    from tiling import owned
    aoi = Polygon([(74.80, 32.60), (74.95, 32.62), (74.93, 32.75), (74.85, 32.78), (74.78, 32.70)])
    tiles = make_tiles(aoi, 5, 0.001)
    rng = np.random.default_rng(1)
    pts = [Point(x, y) for x, y in zip(rng.uniform(74.80, 74.93, 400), rng.uniform(32.61, 32.77, 400))]
    pts = [p for p in pts if aoi.contains(p)]
    g = gpd.GeoDataFrame({"source_id": range(len(pts))}, geometry=pts, crs="EPSG:4326")
    counts = np.zeros(len(g), dtype=int)
    for t in tiles:
        counts[list(owned(g, t).index)] += 1
    assert (counts == 1).all()


def test_landuse_pieces_from_different_tiles_are_rejoined():
    import geopandas as gpd
    from tiling import combine
    tiles = make_tiles(AOI, 5, 0.001)
    piece = lambda t: gpd.GeoDataFrame({"source_id": ["way/7"], "class": ["forest"], "name": [None]},
                                       geometry=[t["core"]], crs="EPSG:4326")
    out = combine([(t, {"landuse": piece(t)}) for t in tiles])["landuse"]
    assert len(out) == 1 and abs(out.geometry.iloc[0].area - AOI.area) < 1e-9
