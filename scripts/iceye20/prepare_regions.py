"""Prepare H/S/T crops and fixed ENL ROIs from noisy SLC data only.

No denoiser, model checkpoint, or restoration metric is imported or executed.
The class proposals use input spatial statistics; contact sheets are exported
for visual review before freezing the final region manifest.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import time
import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, sobel

from common import DATA, manifest, read_json, write_json, sha256
from slc import SLC

CLASSES = ("homogeneous", "structural", "texture")


def preview(x):
    z = np.log1p(np.maximum(x, 0))
    lo, hi = np.percentile(z, [1, 99.5])
    return np.rint(np.clip((z - lo) / max(hi - lo, 1e-12), 0, 1) * 255).astype(np.uint8)


def features(x):
    mean = float(x.mean())
    smooth = gaussian_filter(np.log(np.maximum(x / mean, 1e-8)), 2.0)
    gx, gy = sobel(smooth, axis=1), sobel(smooth, axis=0)
    a, b, d = float(np.mean(gx * gx)), float(np.mean(gx * gy)), float(np.mean(gy * gy))
    coherence = float(np.sqrt((a - d) ** 2 + 4 * b * b) / max(a + d, 1e-12))
    blocks = x.reshape(8, 32, 8, 32).mean(axis=(1, 3))
    cv_blocks = float(blocks.std() / mean)
    grid = np.log(np.maximum(blocks / mean, 1e-8))
    rough = float(np.mean(np.abs(np.diff(grid, axis=0))) + np.mean(np.abs(np.diff(grid, axis=1))))
    return {"mean": mean, "cv": float(x.std() / mean), "block_cv": cv_blocks,
            "coherence": coherence, "edge_energy": a + d, "roughness": rough}


def overlap(a, b, margin=0):
    r, c, h, w = a; rr, cc, hh, ww = b
    return r < rr + hh + margin and rr < r + h + margin and c < cc + ww + margin and cc < c + w + margin


def roi_candidates(x, size, count):
    candidates = []
    for r in range(0, x.shape[0] - size + 1, size):
        for c in range(0, x.shape[1] - size + 1, size):
            a = x[r:r + size, c:c + size]
            if not np.isfinite(a).all() or np.any(a <= 0):
                continue
            mean = float(a.mean()); cv2 = float(a.var() / mean**2)
            # A slowly varying local mean is the input-only homogeneity check.
            half = size // 2
            means = a.reshape(2, half, 2, half).mean(axis=(1, 3))
            trend = float(means.std() / mean)
            if trend <= 0.30 and 0.20 <= cv2 <= 2.0:
                candidates.append({"box": [r, c, size, size], "cv2": cv2, "mean_trend": trend,
                                   "score": trend + 0.1 * abs(cv2 - 1)})
    candidates.sort(key=lambda v: (v["score"], v["box"]))
    return candidates[:count]


def prepare_scene(scene, root):
    sid = scene["scene_id"]
    destination = root / "regions" / sid
    record_path = destination / "selection.json"
    if record_path.exists():
        return read_json(record_path)
    destination.mkdir(parents=True, exist_ok=True)
    with SLC(scene, root) as source:
        overview = source.display_overview()
        Image.fromarray(overview).save(destination / "full_scene_overview.png")
        h, w = source.shape
        candidates = []
        # Fixed regular lattice; no inference outputs enter region selection.
        rows = np.linspace(256, h - 512, 16).round().astype(int)
        cols = np.linspace(256, w - 512, 56).round().astype(int)
        for r in rows:
            for c in cols:
                box = [int(r), int(c), 256, 256]
                x = source.read(box)
                if not source.valid(box).all() or np.any(x <= 0) or not np.isfinite(x).all():
                    continue
                feature = features(x)
                small = roi_candidates(x, 32, 5)
                candidates.append({"box": box, **feature, "enl_rois_local": small})
        if len(candidates) < 30:
            raise RuntimeError(f"Too few valid input candidates: {sid}")
        brightness_floor = float(np.percentile([x["mean"] for x in candidates], 10))
        eligible = [x for x in candidates if x["mean"] >= brightness_floor and len(x["enl_rois_local"]) == 5]
        if len(eligible) < 3:
            raise RuntimeError(f"Not enough regions with valid fixed ENL support: {sid}")
        rankings = {
            "homogeneous": sorted(eligible, key=lambda x: x["block_cv"] + 0.1 * x["roughness"]),
            "structural": sorted(eligible, key=lambda x: -(x["coherence"] * np.log1p(x["edge_energy"]) * np.log1p(x["block_cv"]))),
            "texture": sorted(eligible, key=lambda x: -(1 - x["coherence"]) * x["roughness"] * np.log1p(x["edge_energy"])),
        }
        chosen, shortlists = {}, {}
        for category in CLASSES:
            shortlist = []
            for candidate in rankings[category]:
                if any(overlap(candidate["box"], other["box"], 256) for other in shortlist):
                    continue
                shortlist.append(candidate)
                if len(shortlist) == 8:
                    break
            shortlists[category] = shortlist
            chosen[category] = next(x for x in shortlist if not any(overlap(x["box"], y["box"]) for y in chosen.values()))
            sheet = Image.new("RGB", (4 * 256, 2 * 286), "white")
            draw = ImageDraw.Draw(sheet)
            for i, candidate in enumerate(shortlist):
                x = source.read(candidate["box"])
                sheet.paste(Image.fromarray(preview(x)), ((i % 4) * 256, (i // 4) * 286 + 30))
                draw.text(((i % 4) * 256 + 3, (i // 4) * 286 + 6),
                          f"{sid} {category} #{i} cv={candidate['block_cv']:.2f}", fill="black")
            sheet.save(destination / (category + "_candidates.jpg"), quality=95)

        enl = []
        # Scene ENL ROIs are selected independently of Table V classes.
        for candidate in rankings["homogeneous"]:
            box = candidate["box"]
            if any(abs(box[0] - other["box"][0]) < h / 8 and abs(box[1] - other["box"][1]) < w / 12 for other in enl):
                continue
            x = source.read(box)
            local = roi_candidates(x, 64, 1)
            if not local:
                continue
            item = local[0].copy(); rr, cc, hh, ww = item["box"]
            item["box"] = [rr + box[0], cc + box[1], hh, ww]
            enl.append(item)
            if len(enl) == 10:
                break
        if len(enl) != 10:
            raise RuntimeError(f"Cannot find ten dispersed homogeneous ENL ROIs: {sid}")
        record = {"scene_id": sid, "native_shape": list(source.shape), "encoding": source.encoding(),
                  "candidate_count": len(candidates), "brightness_floor": brightness_floor,
                  "selection_source": "noisy input only; no model outputs or restoration metrics",
                  "visual_review": "pending", "table_iv_enl_rois": enl,
                  "table_v": chosen, "shortlists": shortlists,
                  "selection_script_sha256": sha256(__file__)}
        write_json(destination / "candidates.json", candidates)
        write_json(record_path, record)
        export_scene(scene, record, root, source)
        return record


def export_scene(scene, record, root, source=None):
    if source is None:
        with SLC(scene, root) as opened:
            return export_scene(scene, record, root, opened)
    for category, choice in record["table_v"].items():
        output = root / "table_v" / category; output.mkdir(parents=True, exist_ok=True)
        name = scene["scene_id"]
        power = source.read(choice["box"]).astype(np.float32)
        np.save(output / (name + "_intensity.npy"), power, allow_pickle=False)
        np.save(output / (name + "_complex.npy"), source.read(choice["box"], complex_data=True), allow_pickle=False)
        Image.fromarray(preview(power)).save(output / (name + "_preview.png"))
        write_json(output / (name + ".json"), {"scene_id": name, "category": category, **choice,
                    "shape": [256, 256], "source_raster_sha256": read_json(root / "download_records" / (name + ".json"))["sha256"],
                    "intensity_sha256": sha256(output / (name + "_intensity.npy")),
                    "complex_sha256": sha256(output / (name + "_complex.npy"))})


def contact_sheets(root):
    m = manifest(root)
    for category in CLASSES:
        sheet = Image.new("RGB", (5 * 256, 4 * 282), "white")
        draw = ImageDraw.Draw(sheet)
        for index, scene in enumerate(m["scenes"]):
            path = root / "table_v" / category / (scene["scene_id"] + "_preview.png")
            if not path.exists():
                continue
            x, y = (index % 5) * 256, (index // 5) * 282
            sheet.paste(Image.open(path), (x, y + 26))
            draw.text((x + 4, y + 5), f"{index + 1:02d}  {scene['scene_id']}", fill="black")
        folder = root / "previews"; folder.mkdir(parents=True, exist_ok=True)
        sheet.save(folder / ("table_v_" + category + ".jpg"), quality=96)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DATA)
    p.add_argument("--watch", action="store_true", help="Wait for verified downloads, then prepare each newly complete scene")
    p.add_argument("--scene", nargs="*")
    p.add_argument("--contact-sheets-only", action="store_true")
    a = p.parse_args()
    if a.contact_sheets_only:
        contact_sheets(a.root); return
    scenes = [x for x in manifest(a.root)["scenes"] if not a.scene or x["scene_id"] in a.scene]
    while scenes:
        prepared = []
        for scene in scenes:
            receipt = a.root / "download_records" / (scene["scene_id"] + ".json")
            if not receipt.exists():
                continue
            print(f"Preparing input regions {scene['scene_id']}", flush=True)
            prepare_scene(scene, a.root); prepared.append(scene)
            contact_sheets(a.root)
            print(f"Prepared {scene['scene_id']}: H/S/T + ten ENL ROIs", flush=True)
        scenes = [x for x in scenes if x not in prepared]
        if scenes and not a.watch:
            raise RuntimeError(f"Downloads not yet complete: {[x['scene_id'] for x in scenes]}")
        if scenes:
            time.sleep(10)
    contact_sheets(a.root)


if __name__ == "__main__":
    main()
