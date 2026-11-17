"""Urban Planning Intelligence backend -- matches the React/Leaflet frontend's API contract.

Routes (see frontend README):
  POST /api/buildings/extract        form: image (GeoTIFF)
  POST /api/roads/extract            form: image (GeoTIFF)
  POST /api/layers/upload/{name}     form: file (GeoJSON)   name = buildings | roads
  POST /api/connectivity             form: max_dist (metres)
  POST /api/vegetation/change        form: before, after (GeoTIFF), red, nir (1-based band numbers)
  GET  /api/layers, /api/layers/{name}, /api/stats
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pyproj import CRS, Transformer
from rasterio import features
from rasterio.enums import Resampling
from rasterio.transform import Affine
from rasterio.warp import reproject, transform_geom
from scipy import ndimage as ndi
from shapely.geometry import LineString, mapping, shape
from shapely.ops import transform as shp_transform, unary_union
from shapely.strtree import STRtree
from skimage.filters import threshold_otsu
from skimage.morphology import skeletonize

# ---------------------------------------------------------------- setup
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
LAYER_DIR = DATA_DIR / "layers"
LAYER_DIR.mkdir(parents=True, exist_ok=True)
META_FILE = DATA_DIR / "meta.json"

LAYER_NAMES = ["buildings", "roads", "buildings_connectivity", "settlements", "vegetation_loss", "vegetation_gain"]
UPLOADABLE = {"buildings", "roads"}
MAX_SIDE = 2048  # rasters larger than this are downsampled before analysis

app = FastAPI(title="Urban Planning Intelligence API", version="1.0.0")
origins = [o.strip() for o in os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


# ---------------------------------------------------------------- storage
def empty_fc():
    return {"type": "FeatureCollection", "features": []}


def load_layer(name):
    p = LAYER_DIR / f"{name}.geojson"
    return json.loads(p.read_text()) if p.exists() else empty_fc()


def save_layer(name, fc):
    (LAYER_DIR / f"{name}.geojson").write_text(json.dumps(fc))


def load_meta():
    return json.loads(META_FILE.read_text()) if META_FILE.exists() else {}


def save_meta(meta):
    META_FILE.write_text(json.dumps(meta))


def fc_from_geoms(geoms, props=None):
    props = props or [{}] * len(geoms)
    return {"type": "FeatureCollection",
            "features": [{"type": "Feature", "geometry": mapping(g), "properties": p}
                         for g, p in zip(geoms, props)]}


# ---------------------------------------------------------------- geometry helpers
def utm_transformer(lon, lat):
    zone = int((lon + 180) // 6) + 1
    epsg = (32600 if lat >= 0 else 32700) + zone
    return Transformer.from_crs(4326, epsg, always_xy=True)


def to_metric(geoms):
    """Project lon/lat shapely geoms to a local UTM zone (metres)."""
    if not geoms:
        return []
    c = geoms[0].centroid
    t = utm_transformer(c.x, c.y)
    return [shp_transform(t.transform, g) for g in geoms]


def fc_geoms(fc):
    out = []
    for f in fc["features"]:
        if f.get("geometry"):
            try:
                out.append(shape(f["geometry"]))
            except Exception:
                pass
    return out


# ---------------------------------------------------------------- raster helpers
def save_upload(up: UploadFile) -> str:
    suffix = Path(up.filename or "x.tif").suffix or ".tif"
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        shutil.copyfileobj(up.file, f)
    return path


def open_raster(path):
    try:
        return rasterio.open(path)
    except Exception:
        raise HTTPException(400, "Could not read the file as a GeoTIFF.")


def read_bands(path, band_idx):
    """Read 1-based bands, downsampled if big. Returns (array[b,h,w] float32, transform, crs, valid mask)."""
    with open_raster(path) as ds:
        if ds.count < max(band_idx):
            raise HTTPException(400, f"Raster has {ds.count} band(s); need band {max(band_idx)}.")
        if ds.crs is None:
            raise HTTPException(400, "GeoTIFF has no CRS / georeferencing.")
        s = min(1.0, MAX_SIDE / max(ds.width, ds.height))
        h, w = max(1, int(ds.height * s)), max(1, int(ds.width * s))
        arr = ds.read(band_idx, out_shape=(len(band_idx), h, w),
                      resampling=Resampling.bilinear).astype("float32")
        tr = ds.transform * Affine.scale(ds.width / w, ds.height / h)
        valid = np.isfinite(arr).all(axis=0)
        if ds.nodata is not None:
            valid &= (arr != ds.nodata).all(axis=0)
        return arr, tr, ds.crs, valid


def stretch(band, valid):
    lo, hi = np.percentile(band[valid], (2, 98)) if valid.any() else (0, 1)
    return np.clip((band - lo) / max(hi - lo, 1e-6), 0, 1)


def drop_small(mask, min_px):
    lab, n = ndi.label(mask)
    if n == 0:
        return mask
    sizes = np.bincount(lab.ravel())
    keep = sizes >= min_px
    keep[0] = False
    return keep[lab]


def to_lonlat(geom_dict, crs):
    if CRS.from_user_input(crs).to_epsg() == 4326:
        return geom_dict
    return transform_geom(crs, "EPSG:4326", geom_dict)


def vectorize_mask(mask, tr, crs, min_area_px=1):
    geoms = []
    for g, v in features.shapes(mask.astype("uint8"), mask=mask, transform=tr):
        if v == 1:
            geoms.append(shape(to_lonlat(g, crs)))
    return geoms


def pixel_area_m2(tr, crs, lat):
    if CRS.from_user_input(crs).is_geographic:
        return abs(tr.a) * 111320 * np.cos(np.radians(lat)) * abs(tr.e) * 110540
    return abs(tr.a * tr.e)


# ---------------------------------------------------------------- extraction (classical CV baseline)
def rgb_from(path):
    n = 3
    with open_raster(path) as ds:
        n = min(3, ds.count)
    idx = [1, 2, 3] if n == 3 else [1, 1, 1]
    arr, tr, crs, valid = read_bands(path, idx)
    arr = np.stack([stretch(b, valid) for b in arr])
    return arr, tr, crs, valid


def segment_buildings(rgb, valid):
    r, g, b = rgb
    bright = (r + g + b) / 3
    exg = 2 * g - r - b                       # excess-green: high on vegetation
    thr = threshold_otsu(bright[valid])
    mask = (bright > thr) & (exg <= 0.05) & valid
    mask = ndi.binary_closing(ndi.binary_opening(mask, iterations=1), iterations=1)
    return drop_small(mask, 12)


def segment_roads(rgb, valid):
    r, g, b = rgb
    bright = (r + g + b) / 3
    sat = rgb.max(axis=0) - rgb.min(axis=0)
    exg = 2 * g - r - b
    lo, hi = np.percentile(bright[valid], 15), threshold_otsu(bright[valid])
    mask = (sat < np.median(sat[valid])) & (bright > lo) & (bright <= hi) & (exg <= 0.05) & valid
    mask = ndi.binary_opening(mask, iterations=1)
    return drop_small(mask, 60)


def trace_skeleton(sk, min_len=8):
    rr, cc = np.nonzero(sk)
    pts = set(zip(rr.tolist(), cc.tolist()))

    def nbrs(p):
        r, c = p
        return [(r + dr, c + dc) for dr in (-1, 0, 1) for dc in (-1, 0, 1)
                if (dr or dc) and (r + dr, c + dc) in pts]

    nodes = {p for p in pts if len(nbrs(p)) != 2}
    seen, lines = set(), []
    for n in nodes:
        for nb in nbrs(n):
            if (n, nb) in seen:
                continue
            path, prev, cur = [n, nb], n, nb
            seen.add((n, nb))
            while cur not in nodes:
                nxt = [q for q in nbrs(cur) if q != prev]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                path.append(cur)
            seen.add((cur, prev))
            if len(path) >= min_len:
                lines.append(path)
    return lines


# ---------------------------------------------------------------- endpoints: extraction
@app.post("/api/buildings/extract")
def extract_buildings(image: UploadFile = File(...)):
    path = save_upload(image)
    try:
        rgb, tr, crs, valid = rgb_from(path)
        mask = segment_buildings(rgb, valid)
        geoms = [g.simplify(abs(tr.a) * 0.5) for g in vectorize_mask(mask, tr, crs)]
        geoms = [g for g in geoms if not g.is_empty]
        mg = to_metric(geoms)
        props = [{"id": i + 1, "area_m2": round(m.area, 1)} for i, m in enumerate(mg)]
        save_layer("buildings", fc_from_geoms(geoms, props))
        return {"layer": "buildings", "count": len(geoms), "message": f"Extracted {len(geoms)} buildings."}
    finally:
        os.remove(path)


@app.post("/api/roads/extract")
def extract_roads(image: UploadFile = File(...)):
    path = save_upload(image)
    try:
        rgb, tr, crs, valid = rgb_from(path)
        sk = skeletonize(segment_roads(rgb, valid))
        tol = abs(tr.a) * 1.5
        lines = []
        for p in trace_skeleton(sk):
            xy = [tr * (c + 0.5, r + 0.5) for r, c in p]
            ls = LineString(xy).simplify(tol)
            if not ls.is_empty:
                lines.append(shape(to_lonlat(mapping(ls), crs)))
        mg = to_metric(lines)
        props = [{"id": i + 1, "length_m": round(m.length, 1)} for i, m in enumerate(mg)]
        save_layer("roads", fc_from_geoms(lines, props))
        return {"layer": "roads", "count": len(lines), "message": f"Extracted {len(lines)} road segments."}
    finally:
        os.remove(path)


@app.post("/api/layers/upload/{name}")
def upload_layer(name: str, file: UploadFile = File(...)):
    if name not in UPLOADABLE:
        raise HTTPException(400, f"Only {sorted(UPLOADABLE)} can be uploaded.")
    try:
        fc = json.loads(file.file.read())
    except Exception:
        raise HTTPException(400, "File is not valid JSON.")
    if fc.get("type") == "Feature":
        fc = {"type": "FeatureCollection", "features": [fc]}
    if fc.get("type") != "FeatureCollection":
        raise HTTPException(400, "Expected a GeoJSON FeatureCollection (EPSG:4326).")
    kinds = {"buildings": ("Polygon", "MultiPolygon"), "roads": ("LineString", "MultiLineString")}[name]
    feats = [f for f in fc["features"] if f.get("geometry") and f["geometry"]["type"] in kinds]
    if not feats:
        raise HTTPException(400, f"No {'/'.join(kinds)} features found for layer '{name}'.")
    for i, f in enumerate(feats):
        f["properties"] = f.get("properties") or {}
        f["properties"].setdefault("id", i + 1)
    save_layer(name, {"type": "FeatureCollection", "features": feats})
    return {"layer": name, "count": len(feats), "message": f"Loaded {len(feats)} features into '{name}'."}


# ---------------------------------------------------------------- endpoints: connectivity
@app.post("/api/connectivity")
def connectivity(max_dist: float = Form(200)):
    b_fc, r_fc = load_layer("buildings"), load_layer("roads")
    b_geoms = fc_geoms(b_fc)
    r_geoms = fc_geoms(r_fc)
    if not b_geoms or not r_geoms:
        raise HTTPException(400, "Extract or upload both buildings and roads first.")
    # project everything with the SAME UTM zone (from the first building)
    c = b_geoms[0].centroid
    t = utm_transformer(c.x, c.y)
    zone = int((c.x + 180) // 6) + 1
    inv = Transformer.from_crs((32600 if c.y >= 0 else 32700) + zone, 4326, always_xy=True)
    proj = lambda g: shp_transform(t.transform, g)
    unproj = lambda g: shp_transform(inv.transform, g)
    bm = [proj(g) for g in b_geoms]
    cents = [g.centroid for g in bm]
    roads = [proj(g) for g in r_geoms]

    idx, dist = STRtree(roads).query_nearest(cents, return_distance=True, all_matches=False)
    d = np.full(len(cents), np.inf)
    d[idx[0]] = dist
    poor = d > max_dist

    # layer 1: EVERY building, flagged poor / not poor (frontend colours by `poor`)
    feats = []
    for i, g in enumerate(b_geoms):
        feats.append({"type": "Feature", "geometry": mapping(g),
                      "properties": {"id": i + 1, "area_m2": round(bm[i].area, 1),
                                     "dist_to_road": round(float(d[i]), 1),
                                     "poor": bool(poor[i])}})
    save_layer("buildings_connectivity", {"type": "FeatureCollection", "features": feats})

    # layer 2: settlements = clusters of buildings less than ~120 m apart
    merged = unary_union([g.buffer(60) for g in bm])
    comps = list(merged.geoms) if hasattr(merged, "geoms") else [merged]
    pt_tree = STRtree(cents)
    sfeats = []
    for comp in comps:
        members = pt_tree.query(comp, predicate="contains")
        if len(members) == 0:
            continue
        pct = 100 * float(poor[members].sum()) / len(members)
        sfeats.append({"type": "Feature", "geometry": mapping(unproj(comp.simplify(5))),
                       "properties": {"buildings": int(len(members)),
                                      "mean_dist_m": round(float(np.mean(d[members])), 1),
                                      "pct_poor": round(pct, 1),
                                      "poorly_connected": bool(pct >= 50)}})
    save_layer("settlements", {"type": "FeatureCollection", "features": sfeats})

    n_poor = int(poor.sum())
    meta = load_meta()
    meta["connectivity"] = {
        "max_dist_m": max_dist,
        "buildings_checked": len(cents),
        "poorly_connected": n_poor,
        "pct_poorly_connected": round(100 * n_poor / len(cents), 1),
        "mean_dist_m": round(float(np.mean(d[np.isfinite(d)])), 1),
        "settlements": len(sfeats),
        "poor_settlements": sum(1 for f in sfeats if f["properties"]["poorly_connected"]),
    }
    save_meta(meta)
    return {"layer": "buildings_connectivity", **meta["connectivity"],
            "message": f"{n_poor} of {len(cents)} buildings are more than {max_dist:g} m from a road."}


# ---------------------------------------------------------------- endpoints: vegetation
def ndvi_on_grid(path, red, nir, grid=None):
    if grid is None:
        arr, tr, crs, valid = read_bands(path, [red, nir])
        r, n = arr
    else:
        tr, crs, (h, w) = grid
        with open_raster(path) as ds:
            if ds.count < max(red, nir):
                raise HTTPException(400, f"'after' raster has {ds.count} band(s); need band {max(red, nir)}.")
            out = []
            for bi in (red, nir):
                dst = np.zeros((h, w), dtype="float32")
                reproject(rasterio.band(ds, bi), dst, dst_transform=tr, dst_crs=crs,
                          resampling=Resampling.bilinear)
                out.append(dst)
        r, n = out
        valid = np.isfinite(r) & np.isfinite(n) & ((r != 0) | (n != 0))
    with np.errstate(divide="ignore", invalid="ignore"):
        nd = (n - r) / (n + r)
    valid &= np.isfinite(nd)
    return np.where(valid, nd, np.nan), valid, (tr, crs, nd.shape)


@app.post("/api/vegetation/change")
def vegetation_change(before: UploadFile = File(...), after: UploadFile = File(...),
                      red: int = Form(3), nir: int = Form(4)):
    pb, pa = save_upload(before), save_upload(after)
    try:
        nb, vb, grid = ndvi_on_grid(pb, red, nir)
        na, va, _ = ndvi_on_grid(pa, red, nir, grid)
        tr, crs, _ = grid
        valid = vb & va
        delta = na - nb
        veg_b, veg_a = (nb > 0.3) & valid, (na > 0.3) & valid
        loss = drop_small((delta < -0.15) & veg_b & valid, 6)
        gain = drop_small((delta > 0.15) & veg_a & valid, 6)

        lat = tr.f + tr.e * nb.shape[0] / 2
        if not CRS.from_user_input(crs).is_geographic:
            lat = Transformer.from_crs(crs, 4326, always_xy=True).transform(tr.c, tr.f)[1]
        px = pixel_area_m2(tr, crs, lat)

        for name, m, kind in (("vegetation_loss", loss, "loss"), ("vegetation_gain", gain, "gain")):
            geoms = [g.simplify(abs(tr.a) * 0.5) for g in vectorize_mask(m, tr, crs)]
            mg = to_metric(geoms)
            save_layer(name, fc_from_geoms(geoms, [{"change": kind, "area_m2": round(x.area, 1)} for x in mg]))

        ha = lambda m: round(float(m.sum()) * px / 10_000, 2)
        meta = load_meta()
        meta["vegetation"] = {
            "green_before_ha": ha(veg_b), "green_after_ha": ha(veg_a),
            "loss_ha": ha(loss), "gain_ha": ha(gain),
            "net_change_ha": round(ha(veg_a) - ha(veg_b), 2),
            "net_change_pct": round(100 * (veg_a.sum() - veg_b.sum()) / max(veg_b.sum(), 1), 1),
            "mean_ndvi_before": round(float(np.nanmean(nb)), 3),
            "mean_ndvi_after": round(float(np.nanmean(na)), 3),
        }
        save_meta(meta)
        v = meta["vegetation"]
        return {**v, "message": f"Green cover changed by {v['net_change_ha']} ha ({v['net_change_pct']}%)."}
    finally:
        os.remove(pb)
        os.remove(pa)


# ---------------------------------------------------------------- endpoints: read
@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/layers")
def list_layers():
    return LAYER_NAMES


@app.get("/api/layers/{name}")
def get_layer(name: str):
    if name not in LAYER_NAMES:
        raise HTTPException(404, f"Unknown layer '{name}'.")
    return load_layer(name)


@app.get("/api/stats")
def stats():
    out = dict(load_meta())
    b = to_metric(fc_geoms(load_layer("buildings")))
    r = to_metric(fc_geoms(load_layer("roads")))
    out["buildings"] = {"count": len(b), "total_area_m2": round(sum(g.area for g in b), 1)}
    out["roads"] = {"count": len(r), "total_length_km": round(sum(g.length for g in r) / 1000, 2)}
    out["layers"] = {n: len(load_layer(n)["features"]) for n in LAYER_NAMES}
    return out


@app.delete("/api/layers")
def reset():
    for n in LAYER_NAMES:
        (LAYER_DIR / f"{n}.geojson").unlink(missing_ok=True)
    META_FILE.unlink(missing_ok=True)
    return {"status": "cleared"}