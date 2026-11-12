"""Verify saved results, record checksums, and bundle the requested previews."""
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
from PIL import Image
from scipy.io import loadmat

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT/'output/fig3_iceye_paris_20261109'
EXP = SCENE/'seven_methods'
METHODS = ['sarbm3d','sar2sar','sdudnet','transsar','cl_sar','merlin','mulog_drunet']


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    noisy=np.load(EXP/'noisy_intensity.npy')
    np.testing.assert_array_equal(noisy,np.asarray(Image.open(SCENE/'crops/fig3_view_sigma0.tif')))
    source=json.loads((ROOT/'external/sarbm3d/provenance.json').read_text())
    for filename,checksum in source['files_sha256'].items():
        assert digest(Path(source['package_root'])/filename)==checksum, filename
    bm=loadmat(EXP/'runs/sarbm3d/result.mat')
    np.testing.assert_array_equal(noisy,bm['noisy'])
    np.save(EXP/'runs/sarbm3d/denoised.npy',bm['denoised'].astype(np.float32))
    bm_report={'method':'sarbm3d','complete':True,'source':source,
               'input_domain':'square root of calibrated GRD intensity',
               'output_domain':'calibrated GRD intensity',
               'looks':float(bm['looks'].item()),'core':int(bm['core'].item()),
               'halo':int(bm['halo'].item()),'seconds':float(bm['seconds'].item()),
               'output_sha256':digest(EXP/'runs/sarbm3d/denoised.npy'),
               'mat_sha256':digest(EXP/'runs/sarbm3d/result.mat'),
               'script_sha256':digest(ROOT/'scripts/iceye_paris/run_sarbm3d_tiles.m')}
    (EXP/'runs/sarbm3d/run.json').write_text(json.dumps(bm_report,indent=2),encoding='utf-8')
    checks=[]
    for method in METHODS:
        directory=EXP/'runs'/method
        report=json.loads((directory/'run.json').read_text())
        assert report['complete']
        native=directory/'denoised.npy'
        assert digest(native)==report['output_sha256'],method
        path=directory/('denoised_grd_sigma0.npy' if method=='merlin' else 'denoised.npy')
        array=np.load(path,mmap_mode='r')
        assert array.shape==noisy.shape and np.isfinite(array).all() and np.all(array>=0),method
        assert not np.array_equal(array,noisy),method
        checks.append({'method':method,'aligned_array':str(path.relative_to(EXP)).replace('\\','/'),
                       'sha256':digest(path),'shape':list(array.shape),'dtype':str(array.dtype),
                       'minimum':float(array.min()),'maximum':float(array.max()),
                       'zero_fraction':float(np.mean(array==0)),'all_finite':True})
    pngs=sorted((EXP/'figures').rglob('*.png'))
    assert len(list((EXP/'figures/panels').glob('*.png')))==9
    for path in pngs:
        with Image.open(path) as im:
            im.verify()
    manifest={'scene':SCENE.name,'all_seven_complete':True,'input_unchanged':True,
              'input':json.loads((EXP/'input.json').read_text()),'results':checks,
              'merlin_projection':json.loads((EXP/'runs/merlin/projection.json').read_text()),
              'sar2sar_parity':json.loads((EXP/'sar2sar_validation/verification.json').read_text()),
              'figure_checksums':{str(p.relative_to(EXP)).replace('\\','/'):digest(p) for p in pngs},
              'script_checksums':{p.name:digest(p) for p in sorted((ROOT/'scripts/iceye_paris').glob('*')) if p.is_file()}}
    manifest_path=EXP/'verification.json'
    manifest_path.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    archive=EXP/'seven_methods_previews.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=1) as bundle:
        for path in sorted((EXP/'figures').rglob('*')):
            if path.is_file():
                bundle.write(path,path.relative_to(EXP))
        for path in [manifest_path,EXP/'input.json',EXP/'slc_input.json',EXP/'sar2sar_validation/verification.json']+sorted((EXP/'runs').glob('*/*.json')):
            bundle.write(path,path.relative_to(EXP))
        bundle.writestr('README.txt',
            'ICEYE Paris - original and seven despeckling methods\n\n'
            'figures/comparison_8panel.png: shared -18 to 0 dB display; MERLIN input-matched display gain.\n'
            'figures/comparison_8panel_metadata_scale.png: metadata calibration without that display gain.\n'
            'figures/panels/: the eight requested native 3072 x 3072 PNGs, plus the MERLIN metadata-scale view.\n'
            'figures/roi_H_8panel.png, roi_S_8panel.png, roi_T_8panel.png: native 384 x 384 regions.\n'
            'figures/ratio_8panel.png and roi_*_ratios.png: input/output intensity ratios, -5 to +5 dB.\n'
            'figures/roi_statistics.csv: linear-domain statistics.\n\n'
            'SDUDNet uses the existing 8-bit display-domain adapter. Its output is mapped back through the display formula.\n'
            'SAR2SAR produces dark patches on this ICEYE scene. A separate H-region run is bitwise equal to the authors original test procedure.\n'
            'MERLIN uses native same-acquisition complex SLC, then approximate RPC alignment and area integration to the GRD grid.\n'
            'Its ratios use the corresponding projected SLC observation. The main comparison matches display scale using input H means only.\n'
            'The product-scale discrepancy remains in scientific arrays and the metadata-scale comparison.\n'
            'Run manifests record weights, inputs, tiling, projection, and validation. Scientific NPY arrays remain in the project runs directory.\n'
            'Scripts expect to run inside the source project with its installed method environments.\n\n'
            'Image source: ICEYE Open Data, CC BY 4.0. Cropping, intensity conversion, despeckling and annotations have been applied.\n'
            'https://sar.iceye.com/6.0.6/opendata/opendata/\n'
            'https://creativecommons.org/licenses/by/4.0/\n')
        for path in sorted((ROOT/'scripts/iceye_paris').glob('*')):
            if path.is_file():
                bundle.write(path,Path('scripts')/path.name)
    print(json.dumps({'verified_methods':len(checks),'verified_pngs':len(pngs),
                      'archive':str(archive),'archive_bytes':archive.stat().st_size},indent=2))


if __name__=='__main__':
    main()
