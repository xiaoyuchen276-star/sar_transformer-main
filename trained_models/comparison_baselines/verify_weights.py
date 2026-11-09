"""Verify downloaded comparison checkpoints without deserializing model code."""
import hashlib
import json
from pathlib import Path


def main():
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    errors = []
    count = 0
    for method in manifest['methods']:
        for item in method.get('files', []):
            path = root / item['path']
            if not path.is_file():
                errors.append(f"Missing: {item['path']} (run restore_weights.py)")
                continue
            if path.stat().st_size != item['size_bytes']:
                errors.append(f"Size mismatch: {item['path']}")
                continue
            sha = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    sha.update(block)
            if sha.hexdigest() != item['sha256']:
                errors.append(f"SHA-256 mismatch: {item['path']}")
                continue
            count += 1
            print(f"OK {method['method']}: {item['path']}")
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'Verified {count} checkpoint files.')


if __name__ == '__main__':
    main()
