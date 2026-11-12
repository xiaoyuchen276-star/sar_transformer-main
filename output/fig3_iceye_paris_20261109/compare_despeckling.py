"""Render matched ICEYE GRD intensity and ratio images on the original crop grid."""

import csv
import json
from pathlib import Path
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from matplotlib.patches import Rectangle
import numpy as np
from PIL import Image
from scipy.ndimage import uniform_filter

SCENE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCENE_DIR.parents[1]))
from evaluate_icsps2026_lee import lee_mmse

LOOKS = 5
LEE_WINDOW = 5
INTENSITY_DB = (-18, 0)
RATIO_DB = (-5, 5)
REGIONS = {
    "H": ("Homogeneous field", "#ffca42"),
    "S": ("Roof edges", "#ff746e"),
    "T": ("Residential texture", "#40c9e1"),
}


def to_db(values):
    return 10 * np.log10(values)


def draw_comparison(path, panels, regions, attribution, overview):
    nrows = 1 if overview else len(regions)
    fig, axes = plt.subplots(nrows, len(panels), squeeze=False,
                             figsize=(13.2, 3.35 if overview else 8.45), dpi=200)
    fig.subplots_adjust(left=0.023 if overview else 0.14, right=0.983,
                        top=0.88 if overview else 0.935, bottom=0.25 if overview else 0.13,
                        wspace=0.075, hspace=0.06)
    for row, (key, region) in enumerate([(None, None)] if overview else regions.items()):
        for col, (label, array, limits) in enumerate(panels):
            ax = axes[row, col]
            if overview:
                source = Image.fromarray(to_db(array).astype(np.float32))
                shown = np.asarray(source.resize((768, 768), Image.Resampling.BOX))
            else:
                shown = to_db(array[region])
            ax.imshow(shown, cmap="gray", vmin=limits[0], vmax=limits[1],
                      interpolation="nearest", extent=(0, array.shape[1] if overview else shown.shape[1],
                                                        array.shape[0] if overview else shown.shape[0], 0))
            ax.set_axis_off()
            if row == 0:
                ax.set_title(label, fontsize=11, pad=8)
            if overview and col == 0:
                for name, (ys, xs) in regions.items():
                    color = REGIONS[name][1]
                    ax.add_patch(Rectangle((xs.start, ys.start), xs.stop - xs.start,
                                           ys.stop - ys.start, fill=False, linewidth=1.4, edgecolor=color))
                    ax.text(xs.start + 25, ys.start + 30, name, va="top", color=color,
                            fontsize=10, weight="bold", bbox={"facecolor": "#151515", "pad": 1.2})
            if not overview and col == 0:
                ax.text(-0.10, 0.50, f"{key}  {REGIONS[key][0]}", transform=ax.transAxes,
                        ha="right", va="center", fontsize=10, color="#1c1c1c")

    for limits, positions, unit in [(INTENSITY_DB, (0.20, 0.25), "Intensity (dB)"),
                                    (RATIO_DB, (0.65, 0.23), "Ratio (dB)")]:
        left, width = positions
        cax = fig.add_axes((left, 0.155 if overview else 0.080, width, 0.020 if overview else 0.012))
        colorbar = fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(*limits), cmap="gray"),
                               cax=cax, orientation="horizontal", ticks=[limits[0], sum(limits) / 2, limits[1]])
        colorbar.ax.tick_params(labelsize=8, length=2, pad=2)
        colorbar.set_label(unit, fontsize=9, labelpad=2)
    fig.text(0.98, 0.025, attribution, ha="right", fontsize=8, color="#454545")
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def main():
    selection = json.loads((SCENE_DIR / "fig3_selection.json").read_text(encoding="utf-8"))
    with Image.open(SCENE_DIR / "crops/fig3_view_sigma0.tif") as source:
        noisy = np.asarray(source, dtype=np.float64)
    if noisy.shape != (3072, 3072) or not np.isfinite(noisy).all() or np.any(noisy <= 0):
        raise ValueError("Expected the strictly positive 3072 × 3072 ICEYE intensity crop")
    # The repository's Lee implementation expects [0, 1]. One reversible
    # scale for the whole crop puts it in range without percentile clipping.
    scale = noisy.max()
    lee = lee_mmse(noisy / scale, LOOKS, LEE_WINDOW, eps=1e-12 / scale**2).astype(np.float64) * scale
    boxcar = uniform_filter(noisy, size=LEE_WINDOW, mode="reflect")
    estimates = {"Lee-MMSE": lee, "Boxcar": boxcar}
    regions = {}
    for name, roi in selection["rois"].items():
        x, y = roi["col_start"], roi["row_start"]
        regions[name] = (slice(y, y + roi["height"]), slice(x, x + roi["width"]))

    output = SCENE_DIR / "analysis"
    output.mkdir(exist_ok=True)
    panels = [("Observed GRD", noisy, INTENSITY_DB)]
    rows, ratio_panels = [], []
    for name, estimate in estimates.items():
        if estimate.shape != noisy.shape or not np.isfinite(estimate).all() or np.any(estimate <= 0):
            raise ValueError(f"{name} has invalid ratio denominators")
        ratio = noisy / estimate
        panels.append((name, estimate, INTENSITY_DB))
        ratio_panels.append((f"{name} ratio", ratio, RATIO_DB))
        for key, region in {"Whole crop": np.s_[:, :], **regions}.items():
            x, y, r = noisy[region], estimate[region], ratio[region]
            q05, q95 = np.quantile(r, [0.05, 0.95])
            rows.append({"method": name, "region": key, "pixels": r.size,
                         "ratio_mean": r.mean(), "ratio_q05": q05, "ratio_q95": q95,
                         "output_to_input_mean": y.mean() / x.mean(),
                         "input_enl": x.mean()**2 / x.var(ddof=1) if key == "H" else "",
                         "output_enl": y.mean()**2 / y.var(ddof=1) if key == "H" else ""})
    with (output / "ratio_statistics.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    attribution = "Source: ICEYE Open Data (CC BY 4.0). Cropped, calibrated and filtered."
    draw_comparison(output / "whole_crop_comparison.png", panels + ratio_panels, regions, attribution, True)
    draw_comparison(output / "roi_comparison.png", panels + ratio_panels, regions, attribution, False)


if __name__ == "__main__":
    main()
