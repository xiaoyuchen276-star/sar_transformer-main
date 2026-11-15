"""ICEYE COG decoding: GDAL scale/offset, inverse mapping, native SLC grid."""
from __future__ import annotations
import numpy as np
import rasterio
from rasterio.windows import Window
from common import DATA, metadata, scene_path


class SLC:
    def __init__(self, scene, root=DATA, *, remote=False):
        self.scene = scene
        self.properties = metadata(scene, root)["properties"]
        self.ds = rasterio.open(scene["slc_url"] if remote else scene_path(scene, root))
        self.shape = (self.ds.height, self.ds.width)
        if list(self.shape) != scene["shape"] or self.ds.count != 2:
            raise ValueError("SLC raster shape/bands do not match frozen metadata")
        self.mapping = self.properties["iceye:amplitude_mapping"]
        if self.mapping["function"] not in ("power", "minmax", "clip"):
            raise ValueError("Unsupported amplitude mapping")
        if self.ds.tags(1).get("NAME", "").upper() != "AMPLITUDE" or self.ds.tags(2).get("NAME", "").upper() != "PHASE":
            raise ValueError("Expected explicitly named amplitude and phase bands")
        self.scales, self.offsets = self.ds.scales, self.ds.offsets

    def decode_amplitude(self, code):
        mapped = np.asarray(code, dtype=np.float64) * self.scales[0] + self.offsets[0]
        if self.mapping["function"] == "power":
            params = self.mapping["parameters"]
            mapped = mapped ** (1.0 / params["exponent"]) / params.get("scale", 1.0)
        if not np.isfinite(mapped).all() or (mapped < 0).any():
            raise ValueError("Invalid decoded amplitude")
        return mapped

    def read(self, box=None, *, complex_data=False):
        window = None if box is None else Window(box[1], box[0], box[3], box[2])
        if complex_data:
            code = self.ds.read(window=window)
            amp = self.decode_amplitude(code[0])
            phase = code[1].astype(np.float64) * self.scales[1] + self.offsets[1]
            if np.max(np.abs(phase)) > np.pi + 1e-4:
                raise ValueError("Decoded phase outside [-pi, pi]")
            return (amp * np.exp(1j * phase)).astype(np.complex64)
        code = self.ds.read(1, window=window)
        return self.decode_amplitude(code) ** 2

    def valid(self, box):
        window = Window(box[1], box[0], box[3], box[2])
        code = self.ds.read(1, window=window)
        # Input-defined positive support, shared by every method.
        return (self.ds.read_masks(1, window=window) > 0) & (code > 0)

    def display_overview(self, width=1800):
        height = max(1, round(self.shape[0] * width / self.shape[1]))
        code = self.ds.read(1, out_shape=(height, width), resampling=rasterio.enums.Resampling.average)
        # An existing overview is a display aid only. Nonlinear mapped values
        # averaged by GDAL must never become scientific intensity input.
        lo, hi = np.percentile(code[code > 0], [1, 99.5])
        return np.rint(np.clip((code.astype(float) - lo) / (hi - lo), 0, 1) * 255).astype(np.uint8)

    def encoding(self):
        return {"dtype": list(self.ds.dtypes), "scales": list(self.scales),
                "offsets": list(self.offsets), "amplitude_mapping": self.mapping,
                "amplitude_formula": "A = (DN * band_scale + band_offset) ** (1 / exponent) / mapping_scale",
                "phase_formula": "phase = phase_DN * phase_band_scale + phase_band_offset",
                "intensity_units": "native decoded amplitude squared (DN^2); not GRD sigma0",
                "calibration_factor_metadata": self.properties.get("iceye:calibration_factor")}

    def close(self):
        self.ds.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def tiles(shape, core=512, halo=0):
    h, w = shape
    for row in range(0, h, core):
        for col in range(0, w, core):
            height, width = min(core, h - row), min(core, w - col)
            r0, c0 = max(0, row - halo), max(0, col - halo)
            r1, c1 = min(h, row + height + halo), min(w, col + width + halo)
            yield (row, col, height, width), (r0, c0, r1 - r0, c1 - c0)


def array_window(array, box):
    r, c, h, w = box
    return np.asarray(array[r:r + h, c:c + w])
