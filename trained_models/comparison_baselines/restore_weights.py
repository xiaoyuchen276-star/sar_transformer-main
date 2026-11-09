"""Reassemble byte-exact checkpoints from ordinary Git binary parts."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            sha.update(block)
    return sha.hexdigest()


def matches(path, item):
    return path.is_file() and path.stat().st_size == item['size_bytes'] and digest(path) == item['sha256']


def main():
    base = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=base)
    args = parser.parse_args()
    manifest = json.loads((base / 'manifest.json').read_text(encoding='utf-8'))
    files = [f for m in manifest['methods'] for f in m.get('files', [])]
    for item in files:
        for part in item['parts']:
            if not matches(base / part['path'], part):
                raise SystemExit(f"Missing or corrupt part: {part['path']}")
        target = args.destination / item['path']
        if target.exists() and not matches(target, item):
            raise SystemExit(f'Refusing to overwrite different content: {target}')
    for item in files:
        target = args.destination / item['path']
        if target.exists():
            print(f'Already verified: {target}')
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=target.name+'.', suffix='.tmp', dir=target.parent)
        temp = Path(name)
        try:
            with os.fdopen(fd, 'wb') as output:
                for part in item['parts']:
                    with (base / part['path']).open('rb') as source:
                        shutil.copyfileobj(source, output, 1024 * 1024)
            if not matches(temp, item):
                raise SystemExit(f"Reassembled hash mismatch: {item['path']}")
            if target.exists():
                raise SystemExit(f'Target appeared during restore: {target}')
            temp.rename(target)
        finally:
            if temp.exists():
                temp.unlink()
        print(f'Restored and verified: {target}')
    print(f'Verified {len(files)} complete checkpoint files.')


if __name__ == '__main__':
    main()
