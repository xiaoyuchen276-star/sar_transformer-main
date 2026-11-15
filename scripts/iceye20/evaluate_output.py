"""Evaluate one complete result and extract the frozen Table V coordinates."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
from PIL import Image
from common import DATA, read_json, write_json, sha256
from metrics import evaluate
from array_utils import view


def save_previews(noisy, prediction, input_info, output):
    stride = max(1, int(np.ceil(noisy.shape[1] / 1800)))
    y = np.asarray(noisy[::stride, ::stride], dtype=float)
    x = np.asarray(prediction[::stride, ::stride], dtype=float)
    positive = y[y > 0]
    lo, hi = np.percentile(np.log1p(positive), [1, 99.5])
    def display(array):
        return np.rint(np.clip((np.log1p(np.maximum(array, 0)) - lo) / (hi-lo), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(display(x)).save(output / "full_scene_preview.png")
    ratio = y / np.maximum(x, 1e-6 * input_info["intensity_mean"])
    Image.fromarray(np.rint(np.clip(ratio / 3, 0, 1) * 255).astype(np.uint8)).save(output / "full_ratio_preview.png")
    return {"log1p_display_limits_from_input": [float(lo), float(hi)], "preview_sampling_stride": stride,
            "ratio_display_limits": [0, 3], "scientific_arrays_display_stretched": False}


def evaluate_one(root, input_dir, prediction_path, output, method):
    output = Path(output); output.mkdir(parents=True, exist_ok=True)
    info = read_json(input_dir / "input.json")
    selections = read_json(root / "regions_manifest.json")
    scene = next(x for x in selections["table_iv"] if x["scene_id"] == info["scene_id"])
    noisy = np.load(input_dir / "intensity.npy", mmap_mode="r", allow_pickle=False)
    valid = np.load(input_dir / "valid.npy", mmap_mode="r", allow_pickle=False)
    prediction = noisy if method == "noisy" else np.load(prediction_path, mmap_mode="r", allow_pickle=False)
    if prediction.shape != noisy.shape:
        raise ValueError("Prediction does not cover the full native scene")
    table_iv = evaluate(noisy, prediction, valid, scene["table_iv_enl_rois"],
                        intensity_scale=info["intensity_mean"], identity=method == "noisy")
    write_json(output / "table_iv.json", {"scene_id": info["scene_id"], "method": method, **table_iv})
    table_v = []
    display = save_previews(noisy, prediction, info, output)
    lo, hi = display["log1p_display_limits_from_input"]
    for region in selections["table_v"]:
        if region["scene_id"] != info["scene_id"]:
            continue
        y = np.asarray(view(noisy, region["box"]), dtype=np.float32)
        x = np.asarray(view(prediction, region["box"]), dtype=np.float32)
        mask = np.asarray(view(valid, region["box"]))
        if method in ("ours_base", "ours_ams", "noisy"):
            result = evaluate(y, x, mask, region["enl_rois_local"],
                              intensity_scale=info["intensity_mean"], identity=method == "noisy")
            table_v.append({"scene_id": info["scene_id"], "region_id": region["region_id"],
                            "category": region["category"], "method": method, **result})
        # Preserve all methods' high-resolution regions for visual comparisons,
        # while Table V numeric comparisons remain scoped to the two Ours models.
        category = region["category"]
        np.save(output / (category + "_intensity.npy"), x, allow_pickle=False)
        ratio = y / np.maximum(x, 1e-6 * info["intensity_mean"])
        np.save(output / (category + "_ratio.npy"), ratio, allow_pickle=False)
        pixels = np.rint(np.clip((np.log1p(np.maximum(x, 0)) - lo) / (hi-lo), 0, 1) * 255).astype(np.uint8)
        Image.fromarray(pixels).save(output / (category + "_preview.png"))
        Image.fromarray(np.rint(np.clip(ratio / 3, 0, 1) * 255).astype(np.uint8)).save(output / (category + "_ratio_preview.png"))
    write_json(output / "table_v.json", table_v)
    write_json(output / "evaluation.json", {"scene_id": info["scene_id"], "method": method,
               "complete": True, "display": display, "whole_scene_shape": list(noisy.shape),
               "source_sha256": info["source_sha256"], "regions_manifest_sha256": sha256(root / "regions_manifest.json"),
               "prediction_sha256": None if method == "noisy" else sha256(prediction_path)})


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DATA); p.add_argument("--input-dir", type=Path, required=True)
    p.add_argument("--prediction", type=Path); p.add_argument("--output", type=Path, required=True)
    p.add_argument("--method", required=True)
    a = p.parse_args(); evaluate_one(a.root, a.input_dir, a.prediction, a.output, a.method)
