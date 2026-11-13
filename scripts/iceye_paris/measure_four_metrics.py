"""Measure the saved Paris crop without display transforms or output clipping."""
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
import classic_sar_metrics as classic

SCENE=ROOT/'output/fig3_iceye_paris_20261109'
EXP=SCENE/'seven_methods'
OUT=EXP/'metrics_20261114'
METHODS=[('Noisy','noisy'),('SAR-BM3D','sarbm3d'),('SAR2SAR','sar2sar'),
         ('SDUDNet','sdudnet'),('Trans-SAR','transsar'),('CL-SAR','cl_sar'),
         ('MERLIN','merlin'),('MuLoG-DRUNet','mulog_drunet')]


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def stable_local_stats(array,window=25):
    """Population moments by separable Welford, avoiding integral subtraction."""
    h,w=array.shape
    ow=w-window+1
    hm=np.empty((h,ow),dtype=np.float64)
    hv=np.empty_like(hm)
    for row in range(0,h,128):
        end=min(row+128,h)
        mean=np.zeros((end-row,ow),dtype=np.float64)
        m2=np.zeros_like(mean)
        for k in range(window):
            values=array[row:end,k:k+ow]
            delta=values-mean
            mean+=delta/(k+1)
            m2+=delta*(values-mean)
        hm[row:end]=mean
        hv[row:end]=m2/window
    oh=h-window+1
    result_mean=np.empty((oh,ow),dtype=np.float64)
    result_var=np.empty_like(result_mean)
    for row in range(0,oh,128):
        end=min(row+128,oh)
        mean=np.zeros((end-row,ow),dtype=np.float64)
        m2=np.zeros_like(mean)
        within=np.zeros_like(mean)
        for k in range(window):
            values=hm[row+k:end+k]
            delta=values-mean
            mean+=delta/(k+1)
            m2+=delta*(values-mean)
            within+=hv[row+k:end+k]
        result_mean[row:end]=mean
        result_var[row:end]=(within+m2)/window
    return result_mean,result_var


def coverage(length,kernel):
    return np.convolve(np.ones(length-kernel+1),np.ones(kernel))


def homogeneity(q,window=25):
    # Exact rearrangement of the mean over all local horizontal GLCMs.
    weights=1/(1+np.square(q[:,:-1]-q[:,1:],dtype=np.float64))
    rc=coverage(q.shape[0],window)
    cc=coverage(q.shape[1]-1,window-1)
    return float(np.einsum('i,ij,j->',rc,weights,cc,optimize=False)/
                 ((q.shape[0]-window+1)*(q.shape[1]-window+1)*window*(window-1)))


def validate_numerics():
    rng=np.random.default_rng(16)
    array=rng.gamma(2,1,(96,112))
    array[35,60]=5e6
    mean,var=stable_local_stats(array)
    maximum=0.0
    for row,col in [(0,0),(24,45),(36,61),(48,60),(71,87)]:
        patch=array[row:row+25,col:col+25]
        np.testing.assert_allclose(mean[row,col],patch.mean(),rtol=1e-13)
        np.testing.assert_allclose(var[row,col],patch.var(),rtol=1e-13)
        maximum=max(maximum,float(abs(var[row,col]-patch.var())/patch.var()))
    q=rng.integers(0,8,(96,112),dtype=np.int16)
    old=classic._mean_horizontal_haralick_homogeneity(q,25)
    new=homogeneity(q)
    np.testing.assert_allclose(new,old,rtol=1e-13)
    return {'welford_direct_window_max_relative_variance_error':maximum,
            'homogeneity_rearrangement_absolute_error':abs(old-new)}


def measure(item):
    name,key=item
    start=time.perf_counter()
    output_path=OUT/f'{key}.json'
    product='projected_SLC' if key=='merlin' else 'GRD'
    source=EXP/('slc_observed_on_grd_sigma0.npy' if key=='merlin' else 'noisy_intensity.npy')
    path=source if key=='noisy' else EXP/'runs'/key/('denoised_grd_sigma0.npy' if key=='merlin' else 'denoised.npy')
    noisy=np.load(source).astype(np.float64)
    estimate=np.load(path).astype(np.float64)
    assert noisy.shape==estimate.shape==(3072,3072)
    assert np.isfinite(estimate).all() and np.all(estimate>0)
    roi=json.loads((SCENE/'fig3_selection.json').read_text())['rois']['H']
    r,c,h,w=(roi[k] for k in ['row_start','col_start','height','width'])
    patch=estimate[r:r+h,c:c+w]
    enl=float(patch.mean()**2/patch.var(ddof=1))
    epi=classic.edge_preservation_index(noisy,estimate)
    # Independent row-block check for EPI aggregation.
    def diagonal_sum(a):
        return sum(float(np.abs(a[i:min(i+128,3071),:-1]-a[i+1:min(i+128,3071)+1,1:]).sum())
                   for i in range(0,3071,128))
    np.testing.assert_allclose(epi,diagonal_sum(estimate)/diagonal_sum(noisy),rtol=1e-13)
    report={'method':name,'key':key,'input_product':product,'input_sha256':digest(source),
            'output_sha256':digest(path),'ENL_H':enl,'EPI_Whole':epi,
            'shape':[3072,3072],'H_row_col_height_width':[r,c,h,w]}
    if key=='noisy':
        report['M']={'valid':False,'reason':'identity ratio is constant; M-index not defined',
                     'mean_variant':None,'sum_variant':None}
    else:
        ratio=noisy/estimate
        # All observations and estimates are strictly positive: no ratio floor.
        rm,rv=stable_local_stats(ratio)
        nm=np.load(OUT/f'{product}_local_mean.npy',mmap_mode='r')
        nv=np.load(OUT/f'{product}_local_variance.npy',mmap_mode='r')
        noisy_enl=nm**2/np.maximum(nv,1e-12)
        ratio_enl=rm**2/np.maximum(rv,1e-12)
        re=np.abs(noisy_enl-ratio_enl)/np.maximum(noisy_enl,1e-12)
        ru=np.abs(1-rm)
        selected=np.isfinite(re)&np.isfinite(ru)&(noisy_enl>0)&(re<=.03)&(ru<=.03)
        count=int(selected.sum())
        result={'valid':count>0,'reason':'' if count else 'no_window_satisfies_3_percent_tolerances',
                'window':25,'tolerance':.03,'levels':8,'shuffles':100,'seed':42,
                'selected_windows':count,'total_windows':int(selected.size),
                'ratio_floor_pixels':0,'ratio_min':float(ratio.min()),'ratio_max':float(ratio.max())}
        if count:
            first_mean=float((.5*(re[selected]+ru[selected])).mean())
            first_sum=first_mean*count
        del rm,rv,re,ru,selected,noisy_enl,ratio_enl
        q=classic._quantize_equal_width(ratio,8)
        bins=np.bincount(q.ravel(),minlength=8)
        result['quantization_bin_counts']=bins.tolist()
        result['largest_bin_fraction']=float(bins.max()/q.size)
        del ratio
        if count:
            original=homogeneity(q)
            np.testing.assert_allclose(original,classic._mean_horizontal_haralick_homogeneity(q,25),rtol=1e-12)
            rng=np.random.default_rng(42)
            shuffled=[]
            for i in range(100):
                shuffled.append(homogeneity(rng.permutation(q.ravel()).reshape(q.shape)))
                if (i+1)%20==0:
                    print(f'{name}: permutation {i+1}/100',flush=True)
            shuffle_mean=float(np.mean(shuffled))
            delta_h=100*abs(original-shuffle_mean)/original
            result.update(first_order_mean=first_mean,first_order_sum=first_sum,
                          homogeneity_original=original,homogeneity_shuffled_mean=shuffle_mean,
                          delta_h=delta_h,mean_variant=first_mean+delta_h,sum_variant=first_sum+delta_h)
        else:
            result.update(first_order_mean=None,first_order_sum=None,delta_h=None,mean_variant=None,sum_variant=None)
        report['M']=result
    report['seconds']=time.perf_counter()-start
    output_path.write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    print(f'{name} complete: ENL={enl:.6f}, EPI={epi:.8f}, M={report["M"]["mean_variant"]}',flush=True)
    return report


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--assemble-only',action='store_true')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    validation=validate_numerics()
    cached=json.loads((EXP/'rgpi/rgpi_report.json').read_text())
    for record in cached['files']:
        assert digest(ROOT/record['path'])==record['sha256'],record['path']
    if not args.assemble_only:
        for product,filename in [('GRD','noisy_intensity.npy'),('projected_SLC','slc_observed_on_grd_sigma0.npy')]:
            mean,var=stable_local_stats(np.load(EXP/filename).astype(np.float64))
            np.save(OUT/f'{product}_local_mean.npy',mean)
            np.save(OUT/f'{product}_local_variance.npy',var)
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            jobs={pool.submit(measure,item):item for item in METHODS}
            for job in as_completed(jobs):
                job.result()
    report={'created_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
            'numerical_validation':validation,'rgpi_cache_all_source_hashes_match':True,
            'script_sha256':digest(__file__),'classic_metric_sha256':digest(ROOT/'classic_sar_metrics.py'),
            'scopes':{'ENL':'fixed 384x384 homogeneous H, sample variance ddof=1',
                      'M':'whole crop; all valid 25x25 sliding windows with stride 1',
                      'EPI':'whole crop; lower-right diagonal absolute-difference sum ratio',
                      'RGPI':'whole crop excluding outer 3-pixel border, cached formula implementation'},
            'M_primary_convention':'Gomez 2017 Eq.(1),(3): first_order_sum + delta_h; no division by selected-window count',
            'M_legacy_convention':'mean_variant is retained only as the project prior first_order_mean + delta_h implementation',
            'M_numerics':'separable Welford population variance; algebraically equivalent local-GLCM averaging; no ratio denominator flooring',
            'M_source':'https://www.mdpi.com/2072-4292/9/4/389',
            'comparison_notes':['MERLIN uses projected SLC and its input-derived effective L; it is a separate input protocol.',
                                'SDUDNet uses an 8-bit display input and inverse display mapping.',
                                'Extreme ratios collapse 8-bin global quantization for several methods; M is not a sufficient standalone quality rank.',
                                'These are one-crop measurements, not multi-scene benchmark means.'],
            'results':[json.loads((OUT/f'{key}.json').read_text()) for _,key in METHODS]}
    rows=[]
    for item in report['results']:
        source=EXP/('slc_observed_on_grd_sigma0.npy' if item['key']=='merlin' else 'noisy_intensity.npy')
        output=source if item['key']=='noisy' else EXP/'runs'/item['key']/('denoised_grd_sigma0.npy' if item['key']=='merlin' else 'denoised.npy')
        assert digest(source)==item['input_sha256'] and digest(output)==item['output_sha256']
        item['M_index']=item['M']['sum_variant']
        if item['key']=='noisy':
            item['RGPI_Whole']=cached['identity_diagnostics']['GRD_nominal_L5']['Whole']['rgpi']
            item['RGPI_L']=5.0
        else:
            old=next(x for x in cached['primary_results'] if x['method']==item['method'])
            item['RGPI_Whole']=old['RGPI_Whole']
            item['RGPI_L']=old['L']
        rows.append({'method':item['method'],'ENL_H':item['ENL_H'],
                     'M_index':item['M_index'],'EPI_Whole':item['EPI_Whole'],
                     'RGPI_Whole':item['RGPI_Whole'],'input_product':item['input_product'],
                     'RGPI_L':item['RGPI_L'],'M_valid':item['M']['valid'],
                     'M_selected_windows':item['M'].get('selected_windows',0),
                     'M_legacy_mean_variant':item['M']['mean_variant'],
                     'M_reason':item['M']['reason']})
    (OUT/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False),encoding='utf-8')
    with (OUT/'metrics.csv').open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print('All eight rows measured',flush=True)


if __name__=='__main__':
    main()
