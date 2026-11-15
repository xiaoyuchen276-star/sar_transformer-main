"""Small read-only range probe for transfer diagnostics; no model execution."""
from concurrent.futures import ThreadPoolExecutor
import os
import time
import requests
from common import manifest


def probe(use_environment):
    s = requests.Session()
    s.trust_env = use_environment
    start = time.monotonic()
    try:
        r = s.get(manifest()["scenes"][0]["slc_url"], headers={"Range": "bytes=1048576-5242879"}, timeout=(20, 40))
        r.raise_for_status()
        return {"environment_proxy": use_environment, "status": r.status_code,
                "bytes": len(r.content), "seconds": round(time.monotonic() - start, 2)}
    except requests.RequestException as exc:
        return {"environment_proxy": use_environment, "error": type(exc).__name__,
                "seconds": round(time.monotonic() - start, 2)}


if __name__ == "__main__":
    print("Proxy configured:", bool(os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")), flush=True)
    with ThreadPoolExecutor(2) as pool:
        for result in pool.map(probe, (True, False)):
            print(result, flush=True)
