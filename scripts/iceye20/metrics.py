"""Whole-support ENL, strict M-index, diagonal EPI, and RGPI.

Reductions are accumulated over unique pixels/windows. This module never
averages tile M-indices, changes masks by method, or substitutes missing ROIs.
Only means are exported; no SD, bootstrap, CI, or significance testing.
"""
from __future__ import annotations
import sys
import numpy as np
from scipy.special import gammaln
from common import ROOT
from array_utils import blocks, view

sys.path.insert(0, str(ROOT))
from classic_sar_metrics import _local_mean_variance, _box_sum_valid
from scripts.iceye_paris.rgpi_metric import prepare_reference, _block_features, _log_ratio, DIRECTIONS


CONFIG = {"M_window": 25, "M_tolerance": 0.03, "M_levels": 8, "M_shuffles": 100,
          "seed": 42, "relative_intensity_floor": 1e-6, "variance_floor": 1e-12,
          "EPI": "single lower-right diagonal pairing, absolute-difference sum ratio",
          "RGPI": "Ma 2022 formula; four directions; 3x3 blocks; 7x7 Lee weights; ddof=1; L=1",
          "summary": "arithmetic means only", "mask": "input-defined positive and raster-valid support"}


def validate(noisy, estimate, valid):
    if noisy.ndim != 2 or noisy.shape != estimate.shape or noisy.shape != valid.shape:
        raise ValueError("Expected matching two-dimensional input, prediction and input mask")
    for box in blocks(noisy.shape):
        mask = view(valid, box)
        if not np.isfinite(view(noisy, box)[mask]).all() or not np.isfinite(view(estimate, box)[mask]).all():
            raise ValueError("Nonfinite value on frozen input support; cannot shrink the mask")
        if np.any(view(noisy, box)[mask] <= 0) or np.any(view(estimate, box)[mask] < 0):
            raise ValueError("Invalid intensity on frozen input support")


def enl(estimate, valid, rois):
    values, records = [], []
    for item in rois:
        box = item["box"] if isinstance(item, dict) else item
        x = np.asarray(view(estimate, box), dtype=np.float64)
        mask = view(valid, box)
        if not mask.all() or not np.isfinite(x).all():
            records.append({"box": box, "value": None, "reason": "invalid_support"}); continue
        variance, mean = float(x.var(ddof=0)), float(x.mean())
        value = mean * mean / variance if variance > 0 else None
        records.append({"box": box, "value": value, "reason": "zero_variance" if value is None else ""})
        if value is not None:
            values.append(value)
    # Incomplete support is explicitly missing, never a changed ROI average.
    return {"value": float(np.mean(values)) if len(values) == len(rois) and values else None,
            "valid_rois": len(values), "expected_rois": len(rois), "rois": records}


def epi(noisy, estimate, valid):
    numerator = denominator = 0.0; pairs = 0
    shape = (noisy.shape[0] - 1, noisy.shape[1] - 1)
    for r, c, h, w in blocks(shape):
        first, second = (r, c, h, w), (r + 1, c + 1, h, w)
        mask = view(valid, first) & view(valid, second)
        numerator += float(np.abs(np.asarray(view(estimate, first), dtype=float) - view(estimate, second))[mask].sum())
        denominator += float(np.abs(np.asarray(view(noisy, first), dtype=float) - view(noisy, second))[mask].sum())
        pairs += int(mask.sum())
    return {"value": numerator / denominator if denominator > 0 else None,
            "numerator": numerator, "denominator": denominator, "valid_pairs": pairs}


def rgpi(noisy, estimate, valid, looks=1.0):
    numerator, count, weight_sum = 0.0, 0, 0.0
    alpha = 9 * looks
    constant = gammaln(2 * alpha) - 2 * gammaln(alpha)
    for r, c, h, w in blocks((noisy.shape[0] - 6, noisy.shape[1] - 6)):
        box = (r, c, h + 6, w + 6)
        y = np.where(view(valid, box), view(noisy, box), 0).astype(float)
        x = np.asarray(view(estimate, box), dtype=float)
        reference = prepare_reference(y, looks, variance_ddof=1)
        mean3, valid3 = _block_features(x)
        for i, pair in enumerate(DIRECTIONS):
            log_q, output_valid = _log_ratio(mean3, valid3, pair)
            mask = reference.valid_gradients[i]
            if np.any(mask & ~output_valid):
                return {"value": None, "reason": "nonpositive_output_on_input_fixed_RGPI_support"}
            log_Q = reference.log_gradients[i]
            delta = log_q - log_Q
            log_pdf = constant - log_Q - 2 * alpha * np.logaddexp(delta / 2, -delta / 2)
            numerator += float((reference.weight * log_pdf)[mask].sum())
            count += int(mask.sum()); weight_sum += float(reference.weight[mask].sum())
    return {"value": numerator / count if count else None, "valid_pairs": count,
            "weight_sum": weight_sum, "looks": looks, "mask_depends_on_output": False}


def homogeneity(quantized, valid, window):
    total = 0.0; count = 0
    for r, c, h, w in blocks((quantized.shape[0] - window + 1, quantized.shape[1] - window + 1)):
        box = (r, c, h + window - 1, w + window - 1)
        q = np.asarray(view(quantized, box), dtype=np.int16)
        pair_weights = 1 / (1 + (q[:, :-1] - q[:, 1:]).astype(float) ** 2)
        local = _box_sum_valid(pair_weights, window, window - 1) / (window * (window - 1))
        mask = _box_sum_valid(np.asarray(view(valid, box), dtype=float), window, window) == window**2
        total += float(local[mask].sum()); count += int(mask.sum())
    return total / count if count else None


def m_index(noisy, estimate, valid, intensity_scale, config=CONFIG):
    window, tol, levels = config["M_window"], config["M_tolerance"], config["M_levels"]
    eps, veps = config["relative_intensity_floor"], config["variance_floor"]
    first_sum = 0.0; selected_count = total_windows = 0
    for r, c, h, w in blocks((noisy.shape[0] - window + 1, noisy.shape[1] - window + 1)):
        box = (r, c, h + window - 1, w + window - 1)
        y = np.asarray(view(noisy, box), dtype=float) / intensity_scale
        x = np.asarray(view(estimate, box), dtype=float) / intensity_scale
        mask = _box_sum_valid(np.asarray(view(valid, box), dtype=float), window, window) == window**2
        ratio = y / np.maximum(x, eps)
        ym, yv = _local_mean_variance(y, window); rm, rv = _local_mean_variance(ratio, window)
        ye, re = ym**2 / np.maximum(yv, veps), rm**2 / np.maximum(rv, veps)
        r_enl = np.abs(ye - re) / np.maximum(ye, veps)
        r_mean = np.abs(1 - rm)
        selected = mask & np.isfinite(r_enl) & np.isfinite(r_mean) & (ye > 0) & (r_enl <= tol) & (r_mean <= tol)
        first_sum += float((r_enl + r_mean)[selected].sum())
        selected_count += int(selected.sum()); total_windows += int(mask.sum())
    details = {"selected_windows": selected_count, "input_valid_windows": total_windows,
               "window": window, "tolerance": tol, "levels": levels,
               "shuffles": config["M_shuffles"], "seed": config["seed"],
               "intensity_scale": intensity_scale, "relative_floor": eps}
    if not selected_count:
        return {"value": None, "reason": "no_textureless_window_satisfies_paper_tolerance", **details}
    low, high = float("inf"), float("-inf"); floored = total = 0
    for box in blocks(noisy.shape):
        mask = view(valid, box)
        if not mask.any():
            continue
        y = np.asarray(view(noisy, box), dtype=float) / intensity_scale
        x = np.asarray(view(estimate, box), dtype=float) / intensity_scale
        ratios = (y / np.maximum(x, eps))[mask]
        low = min(low, float(ratios.min())); high = max(high, float(ratios.max()))
        floored += int(((x < eps) & mask).sum()); total += int(mask.sum())
    # uint8 buffers keep the full-scene permutation in memory without allocating
    # whole-image float64 local-statistic maps. No ratio clipping is performed.
    quantized = np.zeros(noisy.shape, dtype=np.uint8)
    occupancy = np.zeros(levels, dtype=np.int64)
    for box in blocks(noisy.shape):
        mask = view(valid, box)
        y = np.asarray(view(noisy, box), dtype=float) / intensity_scale
        x = np.asarray(view(estimate, box), dtype=float) / intensity_scale
        ratios = y / np.maximum(x, eps)
        q = np.minimum(np.floor((ratios - low) / (high - low) * levels), levels - 1) if high > low else np.zeros_like(ratios)
        q = np.clip(q, 0, levels - 1).astype(np.uint8)
        view(quantized, box)[:] = q
        occupancy += np.bincount(q[mask], minlength=levels)
    original = homogeneity(quantized, valid, window)
    if original is None or original <= veps:
        return {"value": None, "reason": "original_homogeneity_is_zero_or_missing", **details}
    flat_mask = np.asarray(valid, dtype=bool).ravel()
    values = quantized.ravel()[flat_mask]
    shuffled = np.zeros_like(quantized)
    rng = np.random.default_rng(config["seed"])
    hs = []
    for index in range(config["M_shuffles"]):
        shuffled.ravel()[flat_mask] = rng.permutation(values)
        hs.append(homogeneity(shuffled, valid, window))
        if index % 10 == 0:
            print(f"Whole-support M-index shuffle {index + 1}/{config['M_shuffles']}", flush=True)
    mean_h = float(np.mean(hs)); first = 0.5 * first_sum / selected_count
    delta = 100 * abs(original - mean_h) / original
    return {"value": first + delta, "first_order_residual": first, "delta_h": delta,
            "original_homogeneity": original, "shuffled_homogeneity_mean": mean_h,
            "ratio_min": low, "ratio_max": high, "quantization_bin_counts": occupancy.tolist(),
            "ratio_floor_fraction": floored / total, **details}


def evaluate(noisy, estimate, valid, rois, *, intensity_scale, looks=1.0, identity=False):
    validate(noisy, estimate, valid)
    results = {"ENL": enl(estimate, valid, rois), "EPI": epi(noisy, estimate, valid),
               "RGPI": rgpi(noisy, estimate, valid, looks)}
    results["M-index"] = {"value": None, "reason": "undefined_for_noisy_identity"} if identity else m_index(noisy, estimate, valid, intensity_scale)
    return {"values": {key: value["value"] for key, value in results.items()},
            "details": results, "metric_config": CONFIG}
