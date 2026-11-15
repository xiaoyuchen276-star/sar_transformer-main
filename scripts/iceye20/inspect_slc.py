"""Inspect product encoding; read-only image metadata and a small sample."""
import json
import rasterio
from rasterio.windows import Window
from common import DATA, manifest, write_json

if __name__ == "__main__":
    scene = manifest()["scenes"][0]
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_CONNECTTIMEOUT="30",
                      GDAL_HTTP_TIMEOUT="90", GDAL_HTTP_MAX_RETRY="4"):
        with rasterio.open(scene["slc_url"]) as ds:
            a = ds.read(window=Window(20000, 5000, 64, 64))
            report = {"dtypes": ds.dtypes, "scales": ds.scales, "offsets": ds.offsets,
                      "descriptions": ds.descriptions, "tags1": ds.tags(1), "tags2": ds.tags(2),
                      "tags": ds.tags(), "nodata": ds.nodatavals, "block_shapes": ds.block_shapes,
                      "sample": [{"min": float(x.min()), "max": float(x.max()),
                                  "mean": float(x.mean())} for x in a]}
            write_json(DATA / "encoding_inspection.json", report)
            print(json.dumps({k: v for k, v in report.items() if k != "tags"}, indent=2), flush=True)
