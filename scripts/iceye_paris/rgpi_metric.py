"""Ratio Gradient Preservation Index, Ma et al., Remote Sensing 2022.

Reference: https://doi.org/10.3390/rs14040856, equations 15, 17, 18.
All inputs are linear intensity. This module computes the weighted mean log
conditional density, not a ratio-image statistic or an image-quality total.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.ndimage import minimum_filter, uniform_filter
from scipy.special import gammaln


# Numerator block center, denominator block center (row, column).
DIRECTIONS = (
    ((-2, 0), (2, 0)),
    ((0, -2), (0, 2)),
    ((-2, -2), (2, 2)),
    ((-2, 2), (2, -2)),
)


def _intensity(image):
    array = np.asarray(image, dtype=np.float64)
    if array.ndim != 2 or min(array.shape) < 7:
        raise ValueError("Expected a two-dimensional intensity image >= 7x7")
    return array


def _block_features(image):
    valid = np.isfinite(image) & (image > 0)
    clean = np.where(valid, image, 0.0)
    mean = uniform_filter(clean, size=3, mode="constant")
    valid_block = minimum_filter(valid, size=3, mode="constant", cval=0)
    return mean, valid_block


def _shift(array, offset):
    """Block-center values for image centers with a valid 7x7 support."""
    dy, dx = offset
    h, w = array.shape
    return array[3 + dy : h - 3 + dy, 3 + dx : w - 3 + dx]


def _log_ratio(mean, valid, pair):
    numerator = _shift(mean, pair[0])
    denominator = _shift(mean, pair[1])
    mask = _shift(valid, pair[0]) & _shift(valid, pair[1])
    mask &= (numerator > 0) & (denominator > 0)
    result = np.zeros(numerator.shape, dtype=np.float64)
    result[mask] = np.log(numerator[mask]) - np.log(denominator[mask])
    return result, mask


@dataclass
class RGPIReference:
    shape: tuple
    looks: float
    weight: np.ndarray
    log_gradients: tuple
    valid_gradients: tuple
    variance_ddof: int


def prepare_reference(noisy, looks, *, variance_ddof=1):
    """Cache all noisy-input-dependent quantities for paired comparisons.

    Local sample variance uses ddof=1 by default (MATLAB var convention).
    Negative Lee weights are clipped to zero, consistent with W in [0,1].
    No padding is evaluated: centers within three pixels of the edge are omitted.
    """
    noisy = _intensity(noisy)
    if not np.isfinite(looks) or looks <= 0:
        raise ValueError("looks must be finite and positive")
    if variance_ddof not in (0, 1):
        raise ValueError("variance_ddof must be zero or one")
    valid = np.isfinite(noisy) & (noisy > 0)
    clean = np.where(valid, noisy, 0.0)
    mean7 = uniform_filter(clean, size=7, mode="constant")[3:-3, 3:-3]
    moment2 = uniform_filter(clean * clean, size=7, mode="constant")[3:-3, 3:-3]
    variance = np.maximum(moment2 - mean7 * mean7, 0.0)
    variance *= 49.0 / (49 - variance_ddof)
    weight = np.zeros(variance.shape, dtype=np.float64)
    nonconstant = variance > 0
    weight[nonconstant] = (
        variance[nonconstant] - mean7[nonconstant] ** 2 / looks
    ) / ((1.0 + 1.0 / looks) * variance[nonconstant])
    np.clip(weight, 0, 1, out=weight)
    valid7 = minimum_filter(valid, size=7, mode="constant", cval=0)[3:-3, 3:-3]
    mean3, valid3 = _block_features(noisy)
    gradients, masks = [], []
    for pair in DIRECTIONS:
        gradient, mask = _log_ratio(mean3, valid3, pair)
        gradients.append(gradient)
        masks.append(mask & valid7)
    return RGPIReference(noisy.shape, float(looks), weight, tuple(gradients),
                         tuple(masks), variance_ddof)


def evaluate(reference, denoised, regions=None):
    """Evaluate whole image and requested regions using existing full-image context.

    Regions use (row_start, col_start, height, width). ROI centers retain context
    from the original image; only the full-image three-pixel border is omitted.
    A zero in either 3x3 block excludes the corresponding direction. The
    denominator is the count of valid pixel-direction pairs, including W=0.
    """
    denoised = _intensity(denoised)
    if denoised.shape != reference.shape:
        raise ValueError("Input and output shapes differ")
    h, w = reference.shape
    selections = {"Whole": (slice(None), slice(None))}
    for name, (row, col, height, width) in (regions or {}).items():
        if min(row, col) < 0 or row + height > h or col + width > w:
            raise ValueError(f"ROI {name} extends outside input")
        selections[name] = (
            slice(max(row, 3) - 3, min(row + height, h - 3) - 3),
            slice(max(col, 3) - 3, min(col + width, w - 3) - 3),
        )
    totals = {name: {"sum": 0.0, "valid_pairs": 0, "weight_sum": 0.0,
                     "direction_scores": []} for name in selections}
    mean3, valid3 = _block_features(denoised)
    alpha = 9.0 * reference.looks
    log_constant = gammaln(2 * alpha) - 2 * gammaln(alpha)
    for index, pair in enumerate(DIRECTIONS):
        log_q, valid_q = _log_ratio(mean3, valid3, pair)
        log_Q = reference.log_gradients[index]
        valid = valid_q & reference.valid_gradients[index]
        delta = log_q - log_Q
        # Algebraic Eq. 15 in log space; no PDF exponentiation or PDF floor.
        log_pdf = log_constant - log_Q - 2 * alpha * np.logaddexp(delta / 2, -delta / 2)
        weighted = reference.weight * log_pdf
        for name, selection in selections.items():
            mask = valid[selection]
            count = int(mask.sum())
            subtotal = float(weighted[selection][mask].sum(dtype=np.float64))
            totals[name]["sum"] += subtotal
            totals[name]["valid_pairs"] += count
            totals[name]["weight_sum"] += float(reference.weight[selection][mask].sum())
            totals[name]["direction_scores"].append(subtotal / count if count else None)
    results = {}
    for name, values in totals.items():
        shape = reference.weight[selections[name]].shape
        count = values["valid_pairs"]
        results[name] = {
            "rgpi": values["sum"] / count if count else None,
            "looks": reference.looks,
            "center_pixels": int(np.prod(shape)),
            "valid_pairs": count,
            "valid_pair_fraction": count / (4 * np.prod(shape)),
            "mean_weight": values["weight_sum"] / count if count else None,
            "direction_scores": values["direction_scores"],
        }
    return results
