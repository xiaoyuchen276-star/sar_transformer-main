"""Recheck saved ICEYE RGPI scores and the identity-likelihood ceiling.

Keeps the existing measurement records intact. Also exports small, real-data
probes for the author's protected MATLAB implementation.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.io import savemat
from scipy.ndimage import correlate
from scipy.stats import betaprime

from evaluate_rgpi import EXP, METHODS, OUT, ROOT, read_array, sha256
from rgpi_metric import DIRECTIONS, evaluate, prepare_reference


AUDIT = OUT / "audit_20261114"


def explicit_sample_oracle(noisy, restored, looks, centers, reference):
    """Independent patch slicing and Beta-prime PDF on real-data centers."""
    local = np.stack([noisy[r-3:r+4, c-3:c+4] for r, c in centers]).astype(np.float64)
    variance = local.var(axis=(1, 2), ddof=1)
    mean = local.mean(axis=(1, 2))
    weight = np.clip((variance - mean**2 / looks) / ((1 + 1/looks)*variance), 0, 1)
    cached_weight = reference.weight[centers[:, 0]-3, centers[:, 1]-3]
    alpha = 9 * looks
    oracle, implementation, gaps = [], [], []
    for direction, pair in enumerate(DIRECTIONS):
        Q_parts, q_parts = [], []
        for dr, dc in pair:
            Q_parts.append(np.array([np.mean(noisy[r+dr-1:r+dr+2, c+dc-1:c+dc+2], dtype=np.float64)
                                     for r, c in centers]))
            q_parts.append(np.array([np.mean(restored[r+dr-1:r+dr+2, c+dc-1:c+dc+2], dtype=np.float64)
                                     for r, c in centers]))
        Q, q = Q_parts[0]/Q_parts[1], q_parts[0]/q_parts[1]
        score = weight * (betaprime.logpdf(Q/q, alpha, alpha) - np.log(q))
        identity = weight * (betaprime.logpdf(np.ones_like(Q), alpha, alpha) - np.log(Q))
        delta = np.log(q/Q)
        gaps.append(weight * 2*alpha*(np.logaddexp(delta/2, -delta/2) - np.log(2)))
        oracle.append(score)
        implementation.append(identity - score)
    return {
        "centers": len(centers),
        "direct_beta_prime_mean": float(np.mean(oracle)),
        "max_weight_error_against_full_image_cache": float(np.max(np.abs(weight-cached_weight))),
        "max_gap_identity_error": float(np.max(np.abs(np.array(implementation)-np.array(gaps)))),
    }


def full_image_gap(reference, restored):
    """Independent nine-tap patch sums, then nonnegative log-cosh penalty."""
    mean = correlate(np.asarray(restored, dtype=np.float64), np.full((3, 3), 1/9), mode="constant")
    h, w = mean.shape
    total = 0.0
    smallest = float("inf")
    for index, pair in enumerate(DIRECTIONS):
        patches = [mean[3+dr:h-3+dr, 3+dc:w-3+dc] for dr, dc in pair]
        if np.any(patches[0] <= 0) or np.any(patches[1] <= 0):
            raise ValueError("The full-image identity bound requires common positive support")
        delta = np.log(patches[0]) - np.log(patches[1]) - reference.log_gradients[index]
        penalty = 18*reference.looks*reference.weight*(np.logaddexp(delta/2, -delta/2)-np.log(2))
        total += penalty.sum(dtype=np.float64)
        smallest = min(smallest, float(penalty.min()))
    return float(total/(4*reference.weight.size)), smallest


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    previous = json.loads((OUT / "rgpi_report.json").read_text(encoding="utf-8"))
    hashes = [{"path": item["path"], "matches": sha256(ROOT / item["path"]) == item["sha256"]}
              for item in previous["files"]]
    if not all(item["matches"] for item in hashes):
        raise AssertionError("A source file changed since the prior measurement")
    inputs = {"GRD": read_array(EXP / "noisy_intensity.npy"),
              "projected_SLC": read_array(EXP / "slc_observed_on_grd_sigma0.npy")}
    outputs = {name: read_array(EXP / "runs" / key /
               ("denoised_grd_sigma0.npy" if key == "merlin" else "denoised.npy"))
               for name, key in METHODS}
    regions = previous["regions_row_col_height_width"]
    rng = np.random.default_rng(20261114)
    centers = rng.integers(3, 3069, size=(512, 2))
    for row, col, height, width in regions.values():
        centers = np.concatenate([centers, np.column_stack([
            rng.integers(row, row+height, size=128), rng.integers(col, col+width, size=128)])])
    results = []
    for product, looks in (("GRD", 5.0), ("projected_SLC", previous["effective_looks_from_H"]["projected_SLC"])):
        noisy = inputs[product]
        reference = prepare_reference(noisy, looks)
        identity = evaluate(reference, noisy, regions)
        for row in previous["primary_results"]:
            if row["input_product"] != product:
                continue
            name = row["method"]
            restored = outputs[name]
            score = evaluate(reference, restored, regions)
            gap, minimum = full_image_gap(reference, restored)
            item = {"method": name, "input_product": product, "L": looks,
                    "identity": identity, "fresh_result": score,
                    "previous_whole_score": row["RGPI_Whole"],
                    "fresh_minus_previous": score["Whole"]["rgpi"]-row["RGPI_Whole"],
                    "independent_full_image_penalty": gap,
                    "minimum_point_penalty": minimum,
                    "gap_equation_absolute_error": abs(identity["Whole"]["rgpi"]-score["Whole"]["rgpi"]-gap),
                    "sample_oracle": explicit_sample_oracle(noisy, restored, looks, centers, reference)}
            if abs(item["fresh_minus_previous"]) > 1e-10 or item["gap_equation_absolute_error"] > 1e-7 or minimum < -1e-12:
                raise AssertionError(item)
            results.append(item)
            print(f"{name}: identity={identity['Whole']['rgpi']:.10f}, restored={score['Whole']['rgpi']:.10f}, "
                  f"drop={gap:.10f}, gap_error={item['gap_equation_absolute_error']:.3g}", flush=True)
        del reference
    report = {"created_at": datetime.now(timezone.utc).isoformat(), "file_hash_checks": hashes,
              "paper": "https://doi.org/10.3390/rs14040856", "results": results,
              "identity_gap_formula": "mean(2 * 9 * L * W * log(cosh(0.5 * log(q/Q)))) >= 0",
              "interpretation": "For fixed input, L, weights, and support, identity is a likelihood ceiling; not a despeckling-quality baseline."}
    (AUDIT / "recheck.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False), encoding="utf-8")
    # Author-program comparisons use independent 128x128 crops, excluding the
    # crop boundary in the formula calculation. Do not substitute these for whole-image results.
    probe_regions = [("H", 1696, 2624), ("S", 1424, 1200)]
    probe = {"method_names": np.array([name for name, _ in METHODS], dtype=object),
             "region_names": np.array([name for name, _, _ in probe_regions], dtype=object),
             "slc_looks": previous["effective_looks_from_H"]["projected_SLC"]}
    for product, data in inputs.items():
        probe[product] = np.stack([data[r:r+128, c:c+128] for _, r, c in probe_regions], axis=2).astype(np.float64)
    probe["outputs"] = np.stack([np.stack([outputs[name][r:r+128, c:c+128] for name, _ in METHODS], axis=2)
                                  for _, r, c in probe_regions], axis=3).astype(np.float64)
    savemat(AUDIT / "author_probe.mat", probe)
    probe_results = []
    for region_index, (region, r, c) in enumerate(probe_regions):
        for method_index, (name, _) in enumerate(METHODS):
            product = "projected_SLC" if name == "MERLIN" else "GRD"
            looks = probe["slc_looks"] if name == "MERLIN" else 5.0
            noisy = probe[product][:, :, region_index]
            ref = prepare_reference(noisy, looks)
            probe_results.append({"region": region, "method": name,
                                  "formula_identity": evaluate(ref, noisy)["Whole"]["rgpi"],
                                  "formula_filtered": evaluate(ref, probe["outputs"][:, :, method_index, region_index])["Whole"]["rgpi"]})
    (AUDIT / "formula_probe.json").write_text(json.dumps(probe_results, indent=2, allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
