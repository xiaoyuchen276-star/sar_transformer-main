"""Apply recorded input-only visual review, audit crops, and seal data coordinates.

This is data preparation, not denoising or restoration-metric evaluation.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from common import DATA, manifest, read_json, write_json, sha256
from prepare_regions import CLASSES, export_scene, contact_sheets, overlap, preview
from slc import SLC


def finish(root, reviews):
    m = manifest(root)
    if len(m["scenes"]) != 20 or len({x["acquisition_id"] for x in m["scenes"]}) != 20:
        raise ValueError("Expected twenty unique acquisition IDs")
    review = read_json(reviews)
    if set(review["reviewed_scenes"]) != {x["scene_id"] for x in m["scenes"]}:
        raise ValueError("All twenty scenes require an actual recorded input review")
    seal_path = root / "dataset_seal.json"
    if seal_path.exists():
        raise FileExistsError("Coordinates are already sealed; version a new dataset before changing them")
    records, inputs, roi_panels = [], [], []
    for scene in m["scenes"]:
        sid = scene["scene_id"]
        folder = root / "regions" / sid
        record = read_json(folder / "selection.json")
        changes = review.get("changes", {}).get(sid, {})
        for category, value in changes.items():
            record["table_v"][category] = record["shortlists"][category][value["candidate_index"]]
        choices = list(record["table_v"].values())
        if any(overlap(a["box"], b["box"]) for i, a in enumerate(choices) for b in choices[i+1:]):
            raise ValueError(f"Overlapping H/S/T regions in {sid}")
        receipt = read_json(root / "download_records" / (sid + ".json"))
        path = Path(receipt["path"])
        if not receipt["complete"] or path.stat().st_size != scene["bytes"] or receipt["bytes"] != scene["bytes"]:
            raise ValueError(f"Incomplete raw product {sid}")
        with SLC(scene, root) as source:
            export_scene(scene, record, root, source)
            canvas = Image.fromarray(source.display_overview()).convert("RGB")
            draw = ImageDraw.Draw(canvas)
            sx, sy = canvas.width / source.shape[1], canvas.height / source.shape[0]
            colors = {"homogeneous": "lime", "structural": "red", "texture": "cyan"}
            for category, choice in record["table_v"].items():
                r, c, h, w = choice["box"]
                if (h, w) != (256, 256) or r < 0 or c < 0 or r + h > source.shape[0] or c + w > source.shape[1]:
                    raise ValueError("Invalid crop coordinates")
                crop_path = root / "table_v" / category / (sid + "_intensity.npy")
                x = np.load(crop_path, allow_pickle=False)
                expected = source.read(choice["box"]).astype(np.float32)
                if not np.array_equal(x, expected) or not source.valid(choice["box"]).all():
                    raise ValueError("Crop differs from its parent SLC or includes invalid input")
                z = np.load(root / "table_v" / category / (sid + "_complex.npy"), allow_pickle=False)
                np.testing.assert_allclose(z.real.astype(float)**2 + z.imag.astype(float)**2, x, rtol=3e-7, atol=1e-9)
                local_rois = choice["enl_rois_local"]
                if len(local_rois) != 5:
                    raise ValueError("Each region needs five input-fixed ENL sub-ROIs")
                for roi in local_rois:
                    rr, cc, hh, ww = roi["box"]
                    if (hh, ww) != (32, 32) or min(rr, cc) < 0 or max(rr+hh, cc+ww) > 256:
                        raise ValueError("Invalid ENL sub-ROI")
                draw.rectangle((c*sx, r*sy, (c+w)*sx, (r+h)*sy), outline=colors[category], width=2)
                draw.text((c*sx+4, r*sy+4), category[0].upper(), fill=colors[category])
                records.append({"region_id": f"{sid}_{category}", "scene_id": sid, "category": category,
                                "box": choice["box"], "enl_rois_local": local_rois,
                                "intensity_path": str(crop_path.relative_to(root)), "intensity_sha256": sha256(crop_path),
                                "complex_path": str((root / "table_v" / category / (sid + "_complex.npy")).relative_to(root)),
                                "complex_sha256": sha256(root / "table_v" / category / (sid + "_complex.npy"))})
            enl_arrays = []
            for index, roi in enumerate(record["table_iv_enl_rois"]):
                if roi["box"][2:] != [64, 64] or not source.valid(roi["box"]).all():
                    raise ValueError("Invalid scene-level ENL ROI")
                value = source.read(roi["box"]).astype(np.float32); enl_arrays.append(value)
                roi_panels.append((sid, index + 1, preview(value)))
            if len(enl_arrays) != 10:
                raise ValueError("Expected ten ENL ROIs per scene")
            np.save(folder / "table_iv_enl_intensity.npy", np.stack(enl_arrays), allow_pickle=False)
            canvas.save(folder / "full_scene_regions.png")
            inputs.append({"scene_id": sid, "bytes": scene["bytes"], "sha256": receipt["sha256"],
                           "native_shape": list(source.shape), "encoding": source.encoding(),
                           "table_iv_enl_rois": record["table_iv_enl_rois"],
                           "slc_metadata_sha256": sha256(root / "metadata" / sid / "slc.json")})
        record["visual_review"] = "assistant_reviewed_noisy_contact_sheets_before_any_inference"
        record["review_changes"] = changes
        record["reviewed_utc"] = datetime.now(timezone.utc).isoformat()
        write_json(folder / "selection.json", record)
    if len(records) != 60 or any(sum(x["category"] == category for x in records) != 20 for category in CLASSES):
        raise ValueError("Expected 20 regions per category")
    contact_sheets(root)
    sheet = Image.new("RGB", (10 * 96, 20 * 104), "white"); draw = ImageDraw.Draw(sheet)
    for i, (sid, index, array) in enumerate(roi_panels):
        x, y = (i % 10)*96, (i // 10)*104
        sheet.paste(Image.fromarray(array).resize((80, 80), Image.Resampling.NEAREST), (x+8, y+22))
        draw.text((x+3, y+2), f"{sid}/{index}", fill="black")
    sheet.save(root / "previews" / "table_iv_enl_200.jpg", quality=96)
    write_json(root / "regions_manifest.json", {"table_iv": inputs, "table_v": records,
               "table_ii": "unchanged", "table_iv_units": "20 full acquisitions", "table_v_units": "60 local regions",
               "summary": "means only", "inference_executed": False})
    seal = {"protocol": m["protocol"], "sealed_utc": datetime.now(timezone.utc).isoformat(),
            "manifest_sha256": sha256(root / "manifest.json"),
            "regions_manifest_sha256": sha256(root / "regions_manifest.json"),
            "review_notes_sha256": sha256(reviews), "raw_scene_count": 20, "table_v_regions": 60,
            "table_iv_enl_rois": 200, "table_v_enl_subrois": 300,
            "data_audit_complete": True, "inference_executed": False, "restoration_metrics_executed": False}
    write_json(seal_path, seal)
    print(f"Sealed 20 full scenes, 60 H/S/T regions, 200 + 300 ENL ROIs: {seal_path}", flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DATA); p.add_argument("--review-notes", type=Path, required=True)
    a = p.parse_args(); finish(a.root, a.review_notes)
