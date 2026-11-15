"""Concurrent range transfers into complete original SLC files; resumable."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import threading
import time

import requests
from common import DATA, manifest, read_json, write_json, sha256
from download import session

LOCAL = threading.local()
LOCK = threading.Lock()


def transfer(scene, target, start, end):
    if not hasattr(LOCAL, "http"):
        LOCAL.http = session()
    for attempt in range(12):
        try:
            with LOCAL.http.get(scene["slc_url"], stream=True,
                                headers={"Range": f"bytes={start}-{end}", "If-Match": scene["etag"],
                                         "Accept-Encoding": "identity"}, timeout=(30, 90)) as response:
                response.raise_for_status()
                expected = f"bytes {start}-{end}/{scene['bytes']}"
                if response.status_code != 206 or response.headers.get("Content-Range") != expected:
                    raise RuntimeError(f"Range mismatch: {response.headers.get('Content-Range')}")
                count = 0
                with target.open("r+b", buffering=0) as stream:
                    stream.seek(start)
                    for block in response.iter_content(1024 * 1024):
                        count += len(block)
                        if count > end - start + 1:
                            raise RuntimeError("Range response exceeded requested bytes")
                        stream.write(block)
                if count != end - start + 1:
                    raise IOError("Truncated range response")
                return start
        except (requests.RequestException, OSError):
            if attempt == 11:
                raise
            time.sleep(min(10, 1 + attempt))
    raise AssertionError("unreachable")


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DATA)
    p.add_argument("--workers", type=int, default=32)
    p.add_argument("--chunk-mib", type=int, default=32)
    a = p.parse_args(); m = manifest(a.root); raw = Path(m["raw_root"])
    chunk = a.chunk_mib * 1024**2
    jobs, states, paths, scenes = [], {}, {}, {}
    for scene in m["scenes"]:
        sid = scene["scene_id"]; scenes[sid] = scene
        folder = raw / sid; folder.mkdir(parents=True, exist_ok=True)
        final, part = folder / "SLC.tif", folder / "SLC.tif.ranged.part"
        receipt = a.root / "download_records" / (sid + ".json")
        if final.exists() and receipt.exists():
            assert final.stat().st_size == scene["bytes"]
            continue
        statefile = folder / "ranges.json"
        if final.exists() and not receipt.exists() and statefile.exists():
            state = read_json(statefile)
            expected_ranges = (state["bytes"] - state["prefix"] + state["chunk"] - 1) // state["chunk"]
            if len(state["done"]) != expected_ranges or final.stat().st_size != scene["bytes"]:
                raise RuntimeError(f"Incomplete receipt cannot be recovered: {folder}")
            write_json(receipt, {"scene_id": sid, "path": str(final), "bytes": final.stat().st_size,
                       "sha256": sha256(final), "s3_etag": scene["etag"], "etag_md5_verified": False,
                       "range_validator": "If-Match plus exact Content-Range and byte count",
                       "complete": True, "completed_utc": datetime.now(timezone.utc).isoformat()})
            continue
        if statefile.exists():
            state = read_json(statefile)
            assert state["etag"] == scene["etag"] and state["bytes"] == scene["bytes"]
            assert state["chunk"] == chunk and part.stat().st_size == scene["bytes"]
        else:
            if part.exists() or final.exists():
                raise RuntimeError(f"Untracked file: {folder}")
            prefix = folder / "SLC.tif.part"
            offset = prefix.stat().st_size if prefix.exists() else 0
            if shutil.disk_usage(raw.anchor).free < scene["bytes"] - offset + 5 * 10**9:
                raise RuntimeError("Insufficient space to preallocate the cohort")
            if prefix.exists():
                os.replace(prefix, part)
            with part.open("ab") as stream:
                stream.truncate(scene["bytes"])
            state = {"etag": scene["etag"], "bytes": scene["bytes"], "prefix": offset,
                     "chunk": chunk, "done": []}
            write_json(statefile, state)
        states[sid], paths[sid] = state, (part, final, statefile, receipt)
        done = set(state["done"])
        for start in range(state["prefix"], scene["bytes"], chunk):
            if start not in done:
                jobs.append((sid, start, min(start + chunk - 1, scene["bytes"] - 1)))
    total = sum(end - start + 1 for _, start, end in jobs)
    print(f"Range download: {len(jobs)} ranges, {total / 1e9:.2f} GB remaining, {a.workers} workers", flush=True)
    beginning = last = time.monotonic(); completed = 0
    with ThreadPoolExecutor(a.workers) as pool:
        futures = {pool.submit(transfer, scenes[sid], paths[sid][0], start, end): (sid, start, end)
                   for sid, start, end in jobs}
        for future in as_completed(futures):
            sid, start, end = futures[future]; future.result()
            state = states[sid]; state["done"].append(start)
            write_json(paths[sid][2], state)
            completed += end - start + 1
            expected_ranges = (state["bytes"] - state["prefix"] + chunk - 1) // chunk
            if len(state["done"]) == expected_ranges:
                part, final, _, receipt = paths[sid]
                os.replace(part, final)
                # Run the final sequential read in this coordinator so no file
                # becomes marked complete before its contents have been read.
                digest = sha256(final)
                write_json(receipt, {"scene_id": sid, "path": str(final), "bytes": final.stat().st_size,
                           "sha256": digest, "s3_etag": state["etag"], "etag_md5_verified": False,
                           "range_validator": "If-Match plus exact Content-Range and byte count",
                           "complete": True, "completed_utc": datetime.now(timezone.utc).isoformat()})
                print(f"Verified full scene {sid}: {digest[:16]}", flush=True)
            if time.monotonic() - last >= 30:
                elapsed = time.monotonic() - beginning
                print(f"Transfer {completed / 1e9:.2f}/{total / 1e9:.2f} GB; {completed / elapsed / 1e6:.2f} MB/s", flush=True)
                write_json(a.root / "download_progress.json", {"remaining_at_start_bytes": total,
                           "transferred_this_run_bytes": completed, "remaining_bytes": total-completed,
                           "average_MB_per_second": completed / elapsed / 1e6,
                           "updated_utc": datetime.now(timezone.utc).isoformat()})
                last = time.monotonic()
    records = [read_json(a.root / "download_records" / (x["scene_id"] + ".json")) for x in m["scenes"]]
    write_json(a.root / "download_complete.json", {"complete": True, "scenes": len(records),
               "bytes": sum(x["bytes"] for x in records)})


if __name__ == "__main__":
    main()
