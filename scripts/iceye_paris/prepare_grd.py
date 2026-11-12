"""Prepare the unmodified, calibrated Paris GRD crop for the seven methods."""
import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.io import savemat

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / 'output/fig3_iceye_paris_20261109'
EXP = SCENE / 'seven_methods'
SOURCE_HASH = '3ab5c55bc1ae2fd8cfeb5c622da34b0ea4f4836d60e31ceb9b3ab034dd381088'


def main():
    source = SCENE / 'crops/fig3_view_sigma0.tif'
    with source.open('rb') as stream:
        checksum = hashlib.file_digest(stream, 'sha256').hexdigest()
    if checksum != SOURCE_HASH:
        raise ValueError('The selected scientific crop has changed')
    noisy = np.asarray(Image.open(source), dtype=np.float32)
    assert noisy.shape == (3072, 3072)
    assert np.isfinite(noisy).all() and np.all(noisy > 0)
    EXP.mkdir(parents=True, exist_ok=True)
    (EXP / 'logs').mkdir(exist_ok=True)
    np.save(EXP / 'noisy_intensity.npy', noisy)
    savemat(EXP / 'input.mat', {'noisy': noisy}, do_compression=True)
    record = {
        'source': {'path': str(source), 'sha256': checksum},
        'roi': {'height': 3072, 'width': 3072, 'row_start': 512, 'col_start': 3328},
        'domain': 'calibrated GRD sigma0',
        'display': {'shared_db_limits': [-18, 0]},
        'looks': 5,
    }
    (EXP / 'input.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(EXP)


if __name__ == '__main__':
    main()
