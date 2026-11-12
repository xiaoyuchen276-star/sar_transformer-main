"""Download the authorized public GRD with verified HTTP byte ranges."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen
import hashlib
import json
import os
import threading
import time

ROOT = Path(__file__).resolve().parent
SCENE = 'ICEYE_U09WX2_20251028T000519Z_6785560_X56_SLF'
URL = f'https://iceye-open-data-catalog.s3.us-west-2.amazonaws.com/data/spot-fine/{SCENE}/{SCENE}_GRD.tif'
FINAL = ROOT / 'raw' / f'{SCENE}_GRD.tif'
PART = FINAL.with_suffix('.tif.part')
STATE = ROOT / 'raw' / 'download_ranges.json'

with urlopen(Request(URL, method='HEAD'), timeout=60) as response:
    total = int(response.headers['Content-Length'])
    etag = response.headers.get('ETag')
if FINAL.exists() and FINAL.stat().st_size == total:
    print('Complete file already exists.', flush=True)
    raise SystemExit(0)
if STATE.exists():
    state = json.loads(STATE.read_text())
    if state['etag'] != etag or state['total'] != total:
        raise RuntimeError('Remote file changed; preserve existing partial file.')
else:
    state = {'url': URL, 'etag': etag, 'total': total,
             'prefix': PART.stat().st_size if PART.exists() else 0, 'done': []}
    STATE.write_text(json.dumps(state, indent=2))

fd = os.open(PART, os.O_RDWR | os.O_CREAT, 0o644)
lock = threading.Lock()
completed = state['prefix'] + sum(b-a+1 for a,b in state['done'])
starting_completed = completed
start_time = time.monotonic()
chunk = 8 * 1024 * 1024
done = {tuple(item) for item in state['done']}
ranges = [(a, min(a+chunk, total)-1) for a in range(state['prefix'], total, chunk)]
stop = threading.Event()

def report():
    while not stop.wait(10):
        elapsed = time.monotonic() - start_time
        with lock:
            value = completed
        print(f'{value / total:.1%}: {value/1e6:.1f}/{total/1e6:.1f} MB; '
              f'{(value-starting_completed)/1e6/max(elapsed,1):.2f} MB/s', flush=True)

def fetch(bounds):
    global completed
    if bounds in done:
        return
    a, b = bounds
    for attempt in range(5):
        try:
            headers = {'Range': f'bytes={a}-{b}', 'If-Match': etag}
            with urlopen(Request(URL, headers=headers), timeout=90) as response:
                if response.status != 206 or response.headers.get('Content-Range') != f'bytes {a}-{b}/{total}':
                    raise RuntimeError('Unexpected byte range response')
                position = a
                while True:
                    block = response.read(1024*1024)
                    if not block:
                        break
                    if position+len(block) > b+1:
                        raise RuntimeError('Response exceeds byte range')
                    written = os.pwrite(fd, block, position)
                    if written != len(block):
                        raise RuntimeError('Incomplete local write')
                    position += len(block)
                if position != b+1:
                    raise RuntimeError('Incomplete response')
            with lock:
                completed += b-a+1
                state['done'].append([a,b])
                temporary = STATE.with_suffix('.json.tmp')
                temporary.write_text(json.dumps(state, indent=2))
                temporary.replace(STATE)
            return
        except Exception as error:
            if attempt == 4:
                raise
            print(f'Retry {bounds}, {type(error).__name__}', flush=True)
            time.sleep(2*(attempt+1))

threading.Thread(target=report, daemon=True).start()
try:
    with ThreadPoolExecutor(max_workers=24) as pool:
        list(pool.map(fetch, ranges))
    os.fsync(fd)
finally:
    stop.set()
    os.close(fd)
if PART.stat().st_size != total or completed != total:
    raise RuntimeError('File size or completed range count mismatch')
digest = hashlib.sha256()
with PART.open('rb') as source:
    for block in iter(lambda: source.read(8*1024*1024), b''):
        digest.update(block)
PART.replace(FINAL)
record = {'url': URL, 'file': str(FINAL), 'size_bytes': total,
          'etag': etag, 'sha256': digest.hexdigest(),
          'download_seconds': time.monotonic()-start_time}
(ROOT/'raw'/'download_verification.json').write_text(json.dumps(record, indent=2))
print(json.dumps(record, indent=2), flush=True)
