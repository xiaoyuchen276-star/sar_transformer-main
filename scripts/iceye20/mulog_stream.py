"""Memory-mapped D=1 MuLoG with global ADMM and global log quantiles.

The author's scalar Newton proximal operator and released DRUNet are reused.
Only Gaussian network evaluation is contextual/tiled. Scalar reductions and
state storage are streamed; no per-tile ADMM or per-tile normalization is used.
Numerical execution/equivalence checks have NOT been run for this new runner.
"""
from __future__ import annotations
import math
import numpy as np
from scipy.special import digamma, polygamma
from array_utils import mmap_new, blocks, view
from common import sha256


def run(noisy, output, info, folder, device):
    import torch
    import torch.nn.functional as F
    from method_worker import adapter
    author = adapter("mulog_drunet/run_local.py"); author.configure_runtime()
    denoiser, core, _, provenance = author.build_denoiser(torch.device(device))
    h, w = noisy.shape; looks = 1.0; iterations = 10
    sigma = float(np.sqrt(polygamma(1, looks)))
    paths = []

    def allocate(name):
        path = folder / ("mulog_" + name + ".npy"); paths.append(path)
        return mmap_new(path, noisy.shape, "float64")

    covariance, x, z, e, xn, zn = [allocate(name) for name in ("covariance", "x", "z", "e", "xn", "zn")]
    random = np.random.RandomState(4242)
    logsum = 0.0
    for r in range(0, h, 32):
        sl = slice(r, min(h, r + 32))
        c = np.maximum(np.asarray(noisy[sl], dtype=float), info["intensity_min_positive"])
        c *= 1 + 1e-6 * (2 * random.rand(*c.shape) - 1)
        covariance[sl] = c
        logsum += float(np.log(c).sum())
    b = logsum / noisy.size + np.log(looks) - digamma(looks)
    pca = {"A": np.ones((1, 1)), "b": np.array([b]), "sigma": np.array([[sigma]])}
    for r in range(0, h, 32):
        sl = slice(r, min(h, r + 32))
        x[sl] = (np.log(covariance[sl]) + np.log(looks) - digamma(looks) - b) / sigma

    calls = []
    quantile_path = folder / "mulog_quantiles.npy"

    def gaussian(get, target, noise_sigma):
        # The author's quantile chooses ceil((n-1)*p), not NumPy's default
        # interpolated percentile. Partition keeps those order statistics.
        q = mmap_new(quantile_path, (noisy.size,), "float64")
        for r in range(0, h, 32):
            hh = min(32, h - r)
            q[r*w:(r+hh)*w] = get((r, 0, hh, w)).ravel()
        indices = (math.ceil((q.size - 1) * 0.003), math.ceil((q.size - 1) * 0.997))
        q.partition(indices)
        lo, hi = float(q[indices[0]]), float(q[indices[1]])
        del q; quantile_path.unlink()
        if not np.isfinite(lo + hi) or hi <= lo:
            raise ValueError("Degenerate global DRUNet quantile range")
        sig = torch.tensor([noise_sigma / (hi - lo)], dtype=torch.float32, device=device)
        with torch.inference_mode():
            for r, c, hh, ww in blocks(noisy.shape, 512):
                r0, c0 = max(0, r - 128), max(0, c - 128)
                r1, c1 = min(h, r + hh + 128), min(w, c + ww + 128)
                values = get((r0, c0, r1-r0, c1-c0))
                tensor = torch.tensor(((values-lo)/(hi-lo))[None, None], dtype=torch.float32, device=device)
                ph, pw = (-values.shape[0]) % 8, (-values.shape[1]) % 8
                if ph or pw:
                    tensor = F.pad(tensor, (0, pw, 0, ph), mode="replicate")
                prediction = denoiser.model(tensor, sig)[0, 0].cpu().numpy()
                view(target, (r, c, hh, ww))[:] = prediction[r-r0:r-r0+hh, c-c0:c-c0+ww] * (hi-lo) + lo
        target.flush()
        calls.append({"sigma": float(noise_sigma), "global_quantile_003": lo, "global_quantile_997": hi})

    gaussian(lambda box, current=x: np.asarray(view(current, box)), z, 1.0)
    for r in range(0, h, 32):
        sl = slice(r, min(h, r + 32)); e[sl] = z[sl] - x[sl]; x[sl] = z[sl] + e[sl]
    beta, previous_difference = 3.0, float("inf")
    with author.compatibility(core):
        for iteration in range(iterations):
            for r in range(0, h, 32):
                sl = slice(r, min(h, r + 32))
                c = np.asarray(covariance[sl])
                y = (np.log(c) + np.log(looks) - digamma(looks) - b) / sigma
                xn[sl] = core.ad.subproxfishtipp((z[sl] + e[sl])[..., None], c[..., None, None],
                            1 / beta, pca, y[..., None], looks, K=10)[..., 0]
            if iteration == iterations - 1:
                break
            gaussian(lambda box, current=xn, residual=e: np.asarray(view(current, box) - view(residual, box)), zn, np.sqrt(1 / beta))
            dx2 = dz2 = de2 = 0.0
            for r in range(0, h, 32):
                sl = slice(r, min(h, r + 32))
                dx = x[sl] - xn[sl]; dz = z[sl] - zn[sl]
                delta_e = zn[sl] - xn[sl]
                dx2 += float(np.sum(dx * dx)); dz2 += float(np.sum(dz * dz)); de2 += float(np.sum(delta_e * delta_e))
                e[sl] += delta_e; x[sl] = xn[sl]; z[sl] = zn[sl]
            difference = np.sqrt(dx2) + np.sqrt(dz2) + np.sqrt(de2)
            if difference > 0.95 * previous_difference:
                beta *= 1.05
            previous_difference = difference
            print(f"MuLoG global ADMM {iteration + 1}/{iterations}, beta={beta:.6g}", flush=True)
    for r in range(0, h, 32):
        sl = slice(r, min(h, r + 32)); output[sl] = np.exp(xn[sl] * sigma + b)
    # c is a NumPy view of the last mapped covariance rows. Release it before
    # unlinking on Windows, where an open mapping prevents file removal.
    del c, covariance, x, z, e, xn, zn
    for path in paths:
        path.unlink()
    return {"source": provenance, "looks": looks, "iterations": iterations, "Newton_iterations": 10,
            "global_pca_b": float(b), "global_sigma": sigma, "denoiser_calls": calls,
            "ADMM_scope": "whole image", "quantile_scope": "whole image; exact author order statistics",
            "tiling": {"DRUNet_core": 512, "halo": 128}, "scalar_D1_diagonal_loading": "identity",
            "streaming_adapter_sha256": sha256(__file__), "adapter_numerically_executed": True}
