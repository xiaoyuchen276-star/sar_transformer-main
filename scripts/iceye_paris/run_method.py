"""Run the seven requested released methods on the fixed ICEYE Paris view."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / 'output/fig3_iceye_paris_20261109'
EXPERIMENT = SCENE / 'seven_methods'
CF = 1.412387683883416e-05
sys.path.insert(0, str(ROOT))


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def adapter(name):
    path = ROOT / 'scripts' / name
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location('paris_' + path.parent.name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tiled_forward(forward, tensor, core=512, halo=128):
    """Retain contextual tile centers, using one preprocessed image globally."""
    import torch
    height, width = tensor.shape[-2:]
    output = torch.empty_like(tensor)
    with torch.inference_mode():
        for row in range(0, height, core):
            for col in range(0, width, core):
                bottom, right = min(row+core, height), min(col+core, width)
                r0, c0 = max(0, row-halo), max(0, col-halo)
                r1, c1 = min(height, bottom+halo), min(width, right+halo)
                prediction = forward(tensor[..., r0:r1, c0:c1])
                output[..., row:bottom, col:right] = prediction[..., row-r0:bottom-r0, col-c0:right-c0]
    return output


def sar2sar(noisy, out):
    run = adapter('sar2sar/run_local.py')
    package, provenance = run.validate_official_package()
    amplitude = np.asarray(Image.open(SCENE/'crops/fig3_view_amplitude.tif'), dtype=np.float32)
    restored, execution = run.infer(amplitude, package, stride=64, threads=4)
    return CF * restored.astype(np.float64)**2, {
        'source': provenance, 'execution': execution, 'input_domain': 'original GRD amplitude DN',
        'inverse': 'sigma0 = calibration_factor * restored_DN_amplitude**2',
        'input_hash': digest(SCENE/'crops/fig3_view_amplitude.tif')}


def cl_sar(noisy, out):
    import torch
    run = adapter('cl_sar/run_local.py')
    run.configure_runtime()
    model, provenance = run.build_model(torch.device('cuda'))
    normalized, normalization = run.prepare_input(noisy, 'intensity', 1.0)
    raw = tiled_forward(model, torch.from_numpy(normalized)[None,None].cuda())[0,0].cpu().numpy()
    np.save(out/'network_raw.npy', raw)
    return run.restore_output(raw, normalization), {'source': provenance, 'normalization': normalization,
        'tiling': {'core':512, 'halo':128}, 'clipped_output_fraction':float(np.mean((raw<0)|(raw>1)))}


def sdudnet(noisy, out):
    import torch
    run = adapter('sdudnet/run_local.py')
    torch.set_num_threads(4)
    model, provenance = run.build_model('real', torch.device('cuda'))
    display = np.asarray(Image.open(SCENE/'previews/fig3_view.png'), dtype=np.float32)/255
    raw = tiled_forward(lambda tile:model(tile)[0], torch.from_numpy(display)[None,None].cuda())[0,0].cpu().numpy()
    np.save(out/'network_raw_display.npy',raw)
    restored_db = -18 + 18*np.clip(raw.astype(np.float64),0,1)
    return 10**(restored_db/10), {'source':provenance, 'tiling':{'core':512,'halo':128},
        'input_domain':'8-bit dB display, same adapter as the supplied eight-panel export',
        'input_hash':digest(SCENE/'previews/fig3_view.png'), 'display_limits_db':[-18,0],
        'output_inverse':'10**((-18+18*clip(prediction,0,1))/10)',
        'input_display_clipped_fraction':float(np.mean((noisy<10**(-1.8))|(noisy>1))),
        'output_display_clipped_fraction':float(np.mean((raw<0)|(raw>1)))}


def transsar(noisy, out):
    import torch
    run = adapter('transsar/run_umbra_official.py')
    repo = ROOT/'external/TransSAR_official'
    checkpoint = ROOT/'trained_models/comparison_baselines/trans-sar/model.pth'
    if digest(checkpoint)!=run.EXPECTED_CHECKPOINT_SHA256:
        raise ValueError('Trans-SAR checkpoint mismatch')
    if run.git_output(repo,'rev-parse','HEAD')!=run.OFFICIAL_COMMIT:
        raise ValueError('Trans-SAR source mismatch')
    torch.set_num_threads(4)
    model, key_transform, tensors = run.load_strict_model(run.import_official_model(repo),checkpoint,torch.device('cuda'))
    scale=float(noisy.max())
    network_input=(255*np.sqrt(noisy/scale)+1)/256
    # (3072+2*128-256) is divisible by the original 192-pixel stride.
    raw, tiling=run.infer_tiled(model,network_input,torch.device('cuda'),256,64,128)
    amplitude=(256*raw-1)/255
    np.save(out/'network_raw_amplitude.npy',amplitude)
    return scale*np.clip(amplitude,0,1)**2, {'source_commit':run.OFFICIAL_COMMIT,
        'checkpoint':str(checkpoint),'checkpoint_sha256':digest(checkpoint),
        'strict_state_tensors':tensors,'key_transform':key_transform,'tiling':tiling,
        'input_domain':'globally peak-normalized amplitude with official (255*A+1)/256 mapping',
        'intensity_scale':scale,'output_clipped_fraction':float(np.mean((amplitude<0)|(amplitude>1)))}


def mulog_drunet(noisy, out):
    import torch
    run = adapter('mulog_drunet/run_local.py')
    run.configure_runtime()
    denoiser,core,_,provenance=run.build_denoiser(torch.device('cuda'))
    original=denoiser.model

    class ContextualModel(torch.nn.Module):
        def forward(self,image,sigma):
            print('DRUNet contextual pass',flush=True)
            return tiled_forward(lambda tile:original(tile,sigma),image)

    denoiser.model=ContextualModel()
    original_prox=core.ad.proxfishtipp

    def bounded_prox(z, covariance, weight, pca, y, looks):
        # The published Newton update is pixelwise. Smaller sequential row
        # batches preserve that update while bounding temporary matrix memory.
        result=np.empty_like(z)
        for row in range(0,z.shape[0],64):
            region=slice(row,row+64)
            result[region]=core.ad.subproxfishtipp(z[region],covariance[region],weight,pca,y[region],looks,K=10)
        return result

    with run.compatibility(core):
        small=noisy[:96,:64].astype(np.float64)
        reference=core.mulog(small,5,lambda y,s:y,'T',2)
        core.ad.proxfishtipp=bounded_prox
        chunked=core.mulog(small,5,lambda y,s:y,'T',2)
    prox_error=float(np.max(np.abs(reference-chunked)))
    np.testing.assert_allclose(chunked,reference,rtol=1e-12,atol=1e-12)
    try:
        result,elapsed,imaginary_max=run.predict(noisy.astype(np.float64),5,10,denoiser,core)
    finally:
        core.ad.proxfishtipp=original_prox
    return result,{'source':provenance,'looks':5,'looks_source':'GRD metadata 1 range x 5 azimuth looks',
        'iterations':10,'seconds':elapsed,'imaginary_residue_max':imaginary_max,'Newton_row_batch':64,
        'Newton_row_batch_validation_max_absolute_error':prox_error,
        'tiling':{'DRUNet_core':512,'DRUNet_halo':128,'ADMM_and_quantiles':'whole image'},
        'denoiser_calls':denoiser.calls}


def merlin(noisy,out):
    import torch
    run=adapter('merlin/run_weighted_overlap.py')
    if digest(run.CHECKPOINT)!='25a978b0d53b5b5307ca2ba57b6368a86493c4eeff24efe6ba58987b2e154a56':
        raise ValueError('MERLIN checkpoint mismatch')
    torch.set_num_threads(4)
    image=np.load(EXPERIMENT/'slc_complex_native.npy',mmap_mode='r')
    torch.manual_seed(0)
    torch.backends.cudnn.benchmark=False
    print('MERLIN native SLC',image.shape,flush=True)
    run.install_unused_gdal_import_stub()
    from deepdespeckling.merlin import merlin_denoiser as official
    denoiser=official.MerlinDenoiser(model_name='spotlight',symetrise=True)
    model=denoiser.load_model(patch_size=256).eval()
    rows=denoiser.initialize_axis_range(image.shape[0],256,64)
    cols=denoiser.initialize_axis_range(image.shape[1],256,64)
    axis,window=run.positive_hann_window(256)
    accum_real=np.zeros(image.shape,dtype=np.float64)
    accum_imag=np.zeros(image.shape,dtype=np.float64)
    row_weights=np.zeros(image.shape[0],dtype=np.float64)
    col_weights=np.zeros(image.shape[1],dtype=np.float64)
    for row in rows:
        row_weights[row:row+256]+=axis
    for col in cols:
        col_weights[col:col+256]+=axis
    window_scale=np.outer(axis,axis).max()
    started=time.perf_counter()
    with torch.inference_mode():
        for index,row in enumerate(rows):
            for col in cols:
                tile=image[row:row+256,col:col+256]
                real,imag=official.symetrise_real_and_imaginary_parts(
                    tile.real.reshape(1,256,256,1),tile.imag.reshape(1,256,256,1))
                for component,accumulator in ((real,accum_real),(imag,accum_imag)):
                    tensor=torch.tensor(component,device=denoiser.device,dtype=torch.float32)
                    tensor=(torch.log(tensor.square()+1e-3)-2*denoiser.m)/(2*(denoiser.M-denoiser.m))
                    prediction=model(tensor).cpu().numpy()[0,0]
                    accumulator[row:row+256,col:col+256]+=prediction*window
            print(f'MERLIN rows {index+1}/{len(rows)}',flush=True)
    intensity=np.empty(image.shape,dtype=np.float32)
    for row in range(0,image.shape[0],256):
        region=slice(row,row+256)
        weights=row_weights[region,None]*col_weights[None,:]/window_scale
        real_amp=official.denormalize_sar_image(accum_real[region]/weights,denoiser.M,denoiser.m)
        imag_amp=official.denormalize_sar_image(accum_imag[region]/weights,denoiser.M,denoiser.m)
        intensity[region]=0.5*(real_amp**2+imag_amp**2)
    elapsed=time.perf_counter()-started
    return intensity, {'input_domain':'native single-look complex SLC DN',
        'input_hash':digest(EXPERIMENT/'slc_complex_native.npy'),
        'checkpoint':str(run.CHECKPOINT),'checkpoint_sha256':digest(run.CHECKPOINT),
        'patch':256,'stride':64,'blend':'positive Hann in normalized log domain',
        'seconds':elapsed,'native_shape':list(image.shape),
        'projection_pending':True}


METHODS={'sar2sar':sar2sar,'cl_sar':cl_sar,'sdudnet':sdudnet,'transsar':transsar,
         'mulog_drunet':mulog_drunet,'merlin':merlin}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('method',choices=METHODS)
    args=parser.parse_args()
    out=EXPERIMENT/'runs'/args.method
    out.mkdir(parents=True,exist_ok=True)
    if (out/'run.json').exists():
        print(args.method,'already completed',flush=True)
        return
    started=time.perf_counter()
    noisy=np.load(EXPERIMENT/'noisy_intensity.npy')
    prediction,report=METHODS[args.method](noisy,out)
    if not np.isfinite(prediction).all() or np.any(prediction<0):
        raise ValueError('Nonfinite or negative restored intensity')
    if args.method!='merlin' and prediction.shape!=noisy.shape:
        raise ValueError('Output does not cover the full display crop')
    np.save(out/'denoised.npy',prediction.astype(np.float32))
    report.update({'method':args.method,'complete':True,'total_seconds':time.perf_counter()-started,
                   'shape':list(prediction.shape),'minimum':float(prediction.min()),
                   'maximum':float(prediction.max()),'mean':float(prediction.mean(dtype=np.float64)),
                   'zero_fraction':float(np.mean(prediction==0)),
                   'output_sha256':digest(out/'denoised.npy'),'script_sha256':digest(__file__)})
    (out/'run.json').write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    print(args.method,'complete',report['total_seconds'],flush=True)


if __name__=='__main__':
    main()
