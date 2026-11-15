"""Download the twenty complete SLC products with resumable, verified transfers.

This command prepares data only. It never imports or runs a despeckling model.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common import DATA, IDS, read_json, write_json, sha256


def session():
    s = requests.Session()
    retries = Retry(total=8, connect=8, read=8, backoff_factor=1,
                    status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET", "HEAD"))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s


def regional(url):
    return url.replace("iceye-open-data-catalog.s3.amazonaws.com", "iceye-open-data-catalog.s3.us-west-2.amazonaws.com")


def initialize(root, cache):
    if (root / "manifest.json").exists():
        m = read_json(root / "manifest.json")
        if [x["acquisition_id"] for x in m["scenes"]] != IDS:
            raise ValueError("Existing manifest contains a different cohort")
        return m
    items = read_json(cache)
    by_id = {x["id"].split("_")[3]: x for x in items}

    def fetch(acq):
        item = by_id[acq]
        s = session()
        item_url = next(x["href"] for x in item["links"] if x["rel"] == "self")
        response = s.get(regional(item_url), timeout=(30, 90)); response.raise_for_status()
        item = response.json()
        folder = root / "metadata" / acq
        write_json(folder / "item.json", item)
        products = {}
        for product in ("slc", "grd"):
            response = s.get(regional(item["assets"][product + "-json"]["href"]), timeout=(30, 90))
            response.raise_for_status()
            products[product] = response.json()
            write_json(folder / (product + ".json"), products[product])
        p = products["slc"]["properties"]
        assert item["id"].endswith("_SLF") and p["sar:polarizations"] == ["VV"]
        assert p["processing:software"]["processor"] == "ICEYE_I_1.5.18"
        assert p["sar:looks_range"] == p["sar:looks_azimuth"] == 1
        url = regional(item["assets"]["slc-cog"]["href"])
        response = s.head(url, timeout=(30, 90)); response.raise_for_status()
        length = int(response.headers["Content-Length"])
        record = {"scene_id": acq, "acquisition_id": acq, "item_id": item["id"],
                  "item_url": item_url, "slc_url": url, "bytes": length,
                  "etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified"),
                  "platform": p["platform"], "datetime": p["datetime"], "shape": p["proj:shape"],
                  "looks": 1, "centroid": p["proj:centroid"], "bbox": item["bbox"],
                  "preview_url": regional(item["assets"]["graphic"]["href"])}
        print(f"Metadata {acq}: {length / 1e9:.2f} GB, shape {record['shape']}", flush=True)
        return record

    results = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch, acq) for acq in IDS]):
            record = future.result(); results[record["scene_id"]] = record
    scenes = [results[acq] for acq in IDS]
    required = sum(x["bytes"] for x in scenes)
    # Keep metadata/crops in the project. Select external bulk storage only if
    # the project volume cannot retain the complete cohort plus a 12 GB reserve.
    if shutil.disk_usage(root.anchor).free > required + 12 * 10**9:
        raw = root / "raw"
    elif Path("E:/").exists() and shutil.disk_usage("E:/").free > required + 12 * 10**9:
        raw = Path("E:/SAR_datasets/iceye20/raw")
    else:
        raise RuntimeError(f"Insufficient storage: complete SLC files require {required / 1e9:.2f} GB plus reserve")
    m = {"protocol": "ICEYE20-fullscene-means-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
         "raw_root": str(raw), "total_bytes": required, "scene_count": 20, "scenes": scenes,
         "license": "CC-BY-4.0", "attribution": "ICEYE Open Data",
         "table_iv": "20 complete SLC scenes; equal scene weights; means only",
         "table_v": "20 homogeneous + 20 structural + 20 texture regions, 256x256",
         "table_ii": "unchanged", "inference_executed": False}
    write_json(root / "manifest.json", m)
    print(f"Total {required / 1e9:.2f} GB; raw storage: {raw}", flush=True)
    return m


def download_one(scene, root, raw):
    folder = raw / scene["scene_id"]
    folder.mkdir(parents=True, exist_ok=True)
    target, partial = folder / "SLC.tif", folder / "SLC.tif.part"
    report = root / "download_records" / (scene["scene_id"] + ".json")
    if target.exists() and report.exists():
        record = read_json(report)
        if target.stat().st_size != scene["bytes"] or not record.get("complete"):
            raise RuntimeError(f"Existing file/receipt mismatch: {target}")
        return record
    s = session()
    if not target.exists():
        for attempt in range(15):
            offset = partial.stat().st_size if partial.exists() else 0
            if offset == scene["bytes"]:
                break
            if offset > scene["bytes"]:
                raise RuntimeError(f"Partial file too large: {partial}")
            try:
                headers = {"Accept-Encoding": "identity", "If-Match": scene["etag"]}
                if offset:
                    headers["Range"] = f"bytes={offset}-"
                with s.get(scene["slc_url"], headers=headers, stream=True, timeout=(30, 90)) as response:
                    response.raise_for_status()
                    if offset and (response.status_code != 206 or not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-")):
                        raise RuntimeError("Server did not honor resume range")
                    with partial.open("ab" if offset else "wb") as output:
                        last = time.monotonic()
                        for chunk in response.iter_content(4 * 1024 * 1024):
                            output.write(chunk); offset += len(chunk)
                            if time.monotonic() - last > 30:
                                output.flush()
                                print(f"Download {scene['scene_id']}: {offset / 1e9:.2f}/{scene['bytes'] / 1e9:.2f} GB", flush=True)
                                last = time.monotonic()
                if partial.stat().st_size == scene["bytes"]:
                    break
            except (requests.RequestException, OSError) as exc:
                print(f"Retry {scene['scene_id']} attempt {attempt + 1}: {type(exc).__name__}", flush=True)
                time.sleep(min(10, attempt + 1))
        if not partial.exists() or partial.stat().st_size != scene["bytes"]:
            raise RuntimeError(f"Incomplete download retained for resume: {partial}")
        os.replace(partial, target)
    if target.stat().st_size != scene["bytes"]:
        raise RuntimeError(f"Size mismatch: {target}")
    digest = sha256(target)
    # S3's single-part ETag is an MD5. Multipart ETags are recorded, not
    # incorrectly treated as a content hash.
    etag = scene["etag"].strip('"')
    etag_verified = False
    if "-" not in etag and len(etag) == 32:
        md5 = hashlib.md5()
        with target.open("rb") as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
                md5.update(block)
        if md5.hexdigest() != etag:
            raise RuntimeError(f"MD5 mismatch: {target}")
        etag_verified = True
    record = {"scene_id": scene["scene_id"], "path": str(target), "bytes": target.stat().st_size,
              "sha256": digest, "s3_etag": scene["etag"], "etag_md5_verified": etag_verified,
              "complete": True, "completed_utc": datetime.now(timezone.utc).isoformat()}
    write_json(report, record)
    preview = root / "previews" / (scene["scene_id"] + "_official.png")
    if not preview.exists():
        response = s.get(scene["preview_url"], timeout=(30, 90)); response.raise_for_status()
        preview.parent.mkdir(parents=True, exist_ok=True); preview.write_bytes(response.content)
    print(f"Verified {scene['scene_id']}: SHA256 {digest[:16]}", flush=True)
    return record


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DATA)
    p.add_argument("--catalog-cache", type=Path, default=Path(os.environ["LOCALAPPDATA"]) / "Temp/iceye_standard_slf_audit_20261115.json")
    p.add_argument("--metadata-only", action="store_true")
    p.add_argument("--workers", type=int, default=3)
    a = p.parse_args(); a.root.mkdir(parents=True, exist_ok=True)
    m = initialize(a.root, a.catalog_cache)
    if a.metadata_only:
        return
    remaining = sum(x["bytes"] for x in m["scenes"] if not (Path(m["raw_root"]) / x["scene_id"] / "SLC.tif").exists())
    available = shutil.disk_usage(Path(m["raw_root"]).anchor).free
    # Existing partial bytes have already consumed disk space.
    partial = sum(x.stat().st_size for x in Path(m["raw_root"]).glob("*/SLC.tif.part"))
    if remaining - partial + 5 * 10**9 > available:
        raise RuntimeError("Insufficient free space for remaining downloads")
    with ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures = [pool.submit(download_one, scene, a.root, Path(m["raw_root"])) for scene in m["scenes"]]
        records = [f.result() for f in as_completed(futures)]
    write_json(a.root / "download_complete.json", {"complete": len(records) == 20,
               "scenes": len(records), "bytes": sum(x["bytes"] for x in records)})


if __name__ == "__main__":
    main()
