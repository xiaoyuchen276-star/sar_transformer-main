"""Reproduce RGPI measurements for the seven existing ICEYE restorations."""
from __future__ import annotations

import csv
from datetime import datetime
import hashlib
import json
from pathlib import Path
import platform
import sys
from time import perf_counter
from zoneinfo import ZoneInfo

import numpy as np
import scipy

from rgpi_metric import DIRECTIONS, evaluate, prepare_reference


ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / "output/fig3_iceye_paris_20261109"
EXP = SCENE / "seven_methods"
OUT = EXP / "rgpi"
METHODS = [
    ("SAR-BM3D", "sarbm3d"), ("SAR2SAR", "sar2sar"),
    ("SDUDNet", "sdudnet"), ("Trans-SAR", "transsar"),
    ("CL-SAR", "cl_sar"), ("MERLIN", "merlin"),
    ("MuLoG-DRUNet", "mulog_drunet"),
]


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_array(path):
    values = np.load(path, mmap_mode="r")
    if values.shape != (3072, 3072) or not np.isfinite(values).all() or np.any(values <= 0):
        raise ValueError(f"Expected strictly positive, finite 3072x3072 data: {path}")
    return values


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    start = perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    selection = json.loads((SCENE / "fig3_selection.json").read_text(encoding="utf-8"))
    regions = {key: (v["row_start"], v["col_start"], v["height"], v["width"])
               for key, v in selection["rois"].items()}
    sources = {"GRD": EXP / "noisy_intensity.npy",
               "projected_SLC": EXP / "slc_observed_on_grd_sigma0.npy"}
    outputs = {name: EXP / "runs" / key /
               ("denoised_grd_sigma0.npy" if key == "merlin" else "denoised.npy")
               for name, key in METHODS}
    arrays = {key: read_array(path) for key, path in sources.items()}
    row, col, height, width = regions["H"]
    effective_looks = {}
    for key, array in arrays.items():
        patch = array[row:row + height, col:col + width].astype(np.float64)
        effective_looks[key] = float(patch.mean() ** 2 / patch.var(ddof=1))
    metadata_path = next((SCENE / "raw").glob("*_GRD.json"))
    properties = json.loads(metadata_path.read_text(encoding="utf-8"))["properties"]
    # Assert against scene metadata, rather than silently assuming the look count.
    looks_keys = {k: v for k, v in properties.items() if "looks" in k.lower()}
    numeric_looks = [float(v) for v in looks_keys.values() if isinstance(v, (int, float))]
    if 1.0 not in numeric_looks or 5.0 not in numeric_looks:
        raise ValueError(f"Review nominal look metadata: {looks_keys}")
    nominal_looks = 5.0
    print(f"Input H ENL (ddof=1): {effective_looks}", flush=True)

    protocols = [
        ("GRD_nominal_L5", "GRD", nominal_looks,
         [name for name, key in METHODS if key != "merlin"], True),
        ("projected_SLC_H_estimated_L", "projected_SLC", effective_looks["projected_SLC"],
         ["MERLIN"], True),
        ("GRD_H_estimated_L_sensitivity", "GRD", effective_looks["GRD"],
         [name for name, key in METHODS if key != "merlin"], False),
        ("MERLIN_against_GRD_L5_auxiliary", "GRD", nominal_looks, ["MERLIN"], False),
    ]
    all_rows, details, identities = [], [], {}
    for protocol, product, looks, method_names, primary in protocols:
        print(f"Preparing {protocol}", flush=True)
        reference = prepare_reference(arrays[product], looks, variance_ddof=1)
        identity = evaluate(reference, arrays[product], regions)
        identities[protocol] = identity
        for name in method_names:
            values = read_array(outputs[name])
            measured = evaluate(reference, values, regions)
            for region, result in measured.items():
                if result["valid_pair_fraction"] != 1.0 or not np.isfinite(result["rgpi"]):
                    raise AssertionError(f"Invalid score or support: {protocol}/{name}/{region}")
                if result["rgpi"] > identity[region]["rgpi"] + 1e-9:
                    raise AssertionError("Conditional likelihood exceeds identity-input maximum")
            note = ""
            if name == "SDUDNet":
                note = "8-bit dB display-domain adapter; inverse-mapped intensity"
            if name == "MERLIN":
                note = ("Projected SLC; effective L estimated from H; separate input protocol"
                        if primary else "Common-GRD diagnostic; includes SLC-to-GRD mismatch")
            result_row = {"method": name, "protocol": protocol, "primary": primary,
                          "input_product": product, "L": looks}
            result_row.update({f"RGPI_{region}": measured[region]["rgpi"]
                               for region in ("Whole", "H", "S", "T")})
            result_row["note"] = note
            all_rows.append(result_row)
            details.append({"method": name, "protocol": protocol, "regions": measured})
            print(f"{name}: " + ", ".join(f"{region}={measured[region]['rgpi']:.8f}"
                                          for region in ("Whole", "H", "S", "T")), flush=True)
        del reference

    method_order = {name: i for i, (name, _) in enumerate(METHODS)}
    primary_rows = sorted((r for r in all_rows if r["primary"]), key=lambda r: method_order[r["method"]])
    write_csv(OUT / "rgpi.csv", primary_rows)
    write_csv(OUT / "rgpi_all_protocols.csv", all_rows)

    provenance = []
    for role, path in [*( (f"input_{k}", p) for k, p in sources.items()),
                       *((f"output_{k}", p) for k, p in outputs.items()),
                       ("roi_selection", SCENE / "fig3_selection.json"),
                       ("grd_metadata", metadata_path),
                       ("metric_implementation", Path(__file__).with_name("rgpi_metric.py")),
                       ("evaluation_script", Path(__file__))]:
        provenance.append({"role": role, "path": str(path.relative_to(ROOT)),
                           "bytes": path.stat().st_size, "sha256": sha256(path)})
    report = {
        "created_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "reference": "https://doi.org/10.3390/rs14040856",
        "equations": [15, 17, 18],
        "implementation": "Float64 weighted mean log-density; independent equation-based implementation",
        "parameters": {
            "domain": "linear intensity; saved scientific arrays; no display transform or gain",
            "patch_size": 3, "patch_pixels": 9, "weight_window": 7,
            "directions_numerator_denominator_dy_dx": DIRECTIONS,
            "local_variance_ddof": 1, "H_ENL_variance_ddof": 1,
            "weight": "clip((var-mean^2/L)/((1+1/L)*var),0,1); zero for var=0",
            "boundary": "exclude outer 3-pixel whole-image border; no evaluated padding",
            "roi_context": "full-image neighborhoods; aggregate centers in original H/S/T coordinates",
            "zero_handling": "exclude direction if any nonpositive/nonfinite pixel in paired 3x3 patches; invalid noisy 7x7 excluded",
            "normalization": "number of valid pixel-direction pairs, including zero-weight pairs",
            "logarithm": "natural; gammaln and logaddexp; no PDF clipping",
        },
        "shape": [3072, 3072], "regions_row_col_height_width": regions,
        "GRD_look_metadata": looks_keys, "effective_looks_from_H": effective_looks,
        "interpretation": [
            "Larger is better for local gradient preservation on the same input and L.",
            "Not bounded by 0 and 1; not an overall despeckling score.",
            "Identity/no filtering maximizes this conditional likelihood; interpret with ENL and M-index.",
            "MERLIN primary result uses projected SLC with estimated effective L, and must not be ranked against GRD primary scores.",
            "MERLIN common-GRD auxiliary includes differences between acquisition products and projection.",
            "H has little structural content; its small weights make it a secondary gradient diagnostic.",
            "Projected SLC L is a homogeneous-ROI moment estimate, not an exact independent-speckle model after resampling.",
        ],
        "primary_results": primary_rows, "all_results": all_rows,
        "detailed_results": details, "identity_diagnostics": identities,
        "files": provenance,
        "runtime": {"python": sys.version, "numpy": np.__version__, "scipy": scipy.__version__,
                    "platform": platform.platform(), "seconds": perf_counter() - start},
    }
    (OUT / "rgpi_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    print(f"Saved results to {OUT}; {perf_counter() - start:.1f} s", flush=True)


if __name__ == "__main__":
    main()
