"""Bounded-memory array and patch helpers (no GIS or model imports)."""
from pathlib import Path
import numpy as np


def blocks(shape, size=512):
    h, w = shape
    for r in range(0, h, size):
        for c in range(0, w, size):
            yield r, c, min(size, h - r), min(size, w - c)


def view(array, box):
    r, c, h, w = box
    return array[r:r + h, c:c + w]


def reflected(array, row, col, height, width):
    def index(start, n, limit):
        if limit == 1:
            return np.zeros(n, dtype=np.int64)
        i = np.arange(start, start + n) % (2 * limit - 2)
        return np.where(i >= limit, 2 * limit - 2 - i, i)
    return np.asarray(array[np.ix_(index(row, height, array.shape[0]), index(col, width, array.shape[1]))])


def mmap_new(path, shape, dtype="float32"):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing array: {path}")
    return np.lib.format.open_memmap(path, mode="w+", dtype=dtype, shape=shape)


def starts(length, patch=256, stride=64):
    values = list(range(0, length - patch + 1, stride))
    if not values or values[-1] != length - patch:
        values.append(length - patch)
    return values


def axis_counts(length, positions, patch):
    count = np.zeros(length, dtype=np.float64)
    for start in positions:
        count[start:start + patch] += 1
    return count
