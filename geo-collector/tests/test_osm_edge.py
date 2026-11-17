import osmnx as ox
from shapely.geometry import box

from collectors.osm import OSMCollector

POLY = box(74.80, 32.60, 74.81, 32.61)


def test_empty_tile_is_not_a_failure(tmp_path, monkeypatch):
    def no_nodes(*a, **k):
        raise ValueError("Found no graph nodes within the requested polygon.")
    monkeypatch.setattr(ox, "graph_from_polygon", no_nodes)
    roads = OSMCollector({}, tmp_path).fetch_roads(POLY)
    assert roads.empty


def test_real_errors_are_still_raised(tmp_path, monkeypatch):
    import collectors.base as base
    monkeypatch.setattr(base.time, "sleep", lambda s: None)
    def boom(*a, **k):
        raise ConnectionError("timed out")
    monkeypatch.setattr(ox, "graph_from_polygon", boom)
    try:
        OSMCollector({}, tmp_path).fetch_roads(POLY)
        assert False, "should have raised"
    except ConnectionError:
        pass


def test_custom_overpass_url(tmp_path):
    old = ox.settings.overpass_url
    try:
        OSMCollector({"overpass_url": "https://example.org/api/interpreter"}, tmp_path)
        assert ox.settings.overpass_url == "https://example.org/api/interpreter"
    finally:
        ox.settings.overpass_url = old
