"""Decode ONE complete SLC into disposable, memory-mapped inference inputs.

Invoked by the future experiment runner, not by the current download/crop job.
"""
import argparse
from pathlib import Path
import numpy as np
from common import DATA, manifest, write_json, read_json, sha256, scene_path
from slc import SLC
from array_utils import blocks, mmap_new, view


def prepare(scene, destination, root=DATA):
    destination = Path(destination)
    receipt = destination / "input.json"
    source_receipt = read_json(root / "download_records" / (scene["scene_id"] + ".json"))
    if receipt.exists():
        record = read_json(receipt)
        if record["source_sha256"] != source_receipt["sha256"]:
            raise RuntimeError("Decoded cache belongs to a different input")
        for name in ("intensity.npy", "complex.npy", "valid.npy"):
            if not (destination / name).exists():
                raise FileNotFoundError(destination / name)
            array = np.load(destination / name, mmap_mode="r", allow_pickle=False)
            if list(array.shape) != scene["shape"]:
                raise ValueError("Decoded input cache has the wrong native dimensions")
        return record
    destination.mkdir(parents=True, exist_ok=True)
    if sha256(scene_path(scene, root)) != source_receipt["sha256"]:
        raise ValueError("Raw SLC contents changed after the download receipt was recorded")
    power = mmap_new(destination / "intensity.npy", scene["shape"])
    complex_image = mmap_new(destination / "complex.npy", scene["shape"], "complex64")
    valid = mmap_new(destination / "valid.npy", scene["shape"], "bool")
    total, count, minimum, maximum = 0.0, 0, float("inf"), 0.0
    with SLC(scene, root) as source:
        for index, box in enumerate(blocks(source.shape, 1024)):
            values = source.read(box)
            mask = source.valid(box)
            z = source.read(box, complex_data=True)
            if not np.isfinite(values).all() or not np.isfinite(z).all():
                raise ValueError("Nonfinite decoded SLC data")
            view(power, box)[:] = values
            view(complex_image, box)[:] = z
            view(valid, box)[:] = mask
            if np.any(mask):
                selected = values[mask]
                total += float(selected.sum()); count += selected.size
                minimum = min(minimum, float(selected.min())); maximum = max(maximum, float(selected.max()))
            if index % 100 == 0:
                print(f"Decode {scene['scene_id']}: block {index}", flush=True)
        if count == 0:
            raise ValueError("No valid positive SLC samples")
        power.flush(); complex_image.flush(); valid.flush()
        record = {"scene_id": scene["scene_id"], "shape": scene["shape"],
                  "source_sha256": source_receipt["sha256"], "encoding": source.encoding(),
                  "valid_count": count, "valid_fraction": count / power.size,
                  "intensity_mean": total / count, "intensity_peak": maximum,
                  "intensity_min_positive": minimum, "normalization_scope": "one whole scene, never per inference tile",
                  "script_sha256": sha256(__file__), "complete": True}
    write_json(receipt, record)
    return record


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DATA); p.add_argument("--scene", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    prepare(next(x for x in manifest(a.root)["scenes"] if x["scene_id"] == a.scene), a.output, a.root)
