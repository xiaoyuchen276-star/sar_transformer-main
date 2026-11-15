"""Shared paths and immutable scene identifiers for the ICEYE20 experiment."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "datasets" / "iceye20"
IDS = ["4075951", "4559972", "4810237", "9001826", "9361035", "9361030",
       "10175124", "10175035", "10183224", "10187815", "10247036", "10249170",
       "10252498", "10253070", "10253169", "10254608", "10288127", "10329202",
       "10331151", "10331459"]
METHODS = ["sarbm3d", "sar2sar", "sdudnet", "transsar", "cl_sar", "merlin",
           "mulog_drunet", "ours_base", "ours_ams"]
LABELS = dict(zip(METHODS, ["SAR-BM3D", "SAR2SAR", "SDUDNet", "Trans-SAR", "CL-SAR",
                          "MERLIN", "MuLoG-DRUNet", "Ours-base", "Ours+AMS"]))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def manifest(root=DATA):
    return read_json(Path(root) / "manifest.json")


def scene_path(scene, root=DATA):
    return Path(manifest(root)["raw_root"]) / scene["scene_id"] / "SLC.tif"


def metadata(scene, root=DATA):
    return read_json(Path(root) / "metadata" / scene["scene_id"] / "slc.json")
