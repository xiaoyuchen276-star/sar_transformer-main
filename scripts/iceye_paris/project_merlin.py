"""Area-average the native SLC power and MERLIN estimate to the GRD view."""
import json
from pathlib import Path

import numpy as np
from scipy.ndimage import map_coordinates

ROOT=Path(__file__).resolve().parents[2]
SCENE=ROOT/'output/fig3_iceye_paris_20261109'
EXP=SCENE/'seven_methods'
CF=1.412387683883416e-05


def project(values,coordinates):
    # Native-to-GRD sample spacings are 1.44 range and 2.81 azimuth pixels.
    # Integrate the bilinear interpolant at 4x4 points in each GRD pixel.
    row_step=float(np.median(np.diff(coordinates[0,:,0])))
    col_step=float(np.median(np.diff(coordinates[1,0,:])))
    result=np.empty((3072,3072),dtype=np.float32)
    offsets=(np.arange(4)+0.5)/4-0.5
    for row in range(0,3072,128):
        region=slice(row,row+128)
        center=coordinates[:,region]
        total=np.zeros((128,3072),dtype=np.float64)
        for dr in offsets:
            for dc in offsets:
                samples=center+np.array([dr*row_step,dc*col_step])[:,None,None]
                total+=map_coordinates(values,samples,order=1,mode='nearest',prefilter=False)
        result[region]=total/16
    return result


def main():
    coordinates=np.load(EXP/'grd_to_slc_coordinates.npy',mmap_mode='r')
    metadata=json.loads(next((SCENE/'raw').glob('*_GRD.json')).read_text())['properties']
    # The supplied coefficients span the near/far metadata angles over the
    # full 20000-row range axis, in pixel coordinates.
    coefficients=metadata['iceye:incidence_angle_coeffs']
    theta=np.polynomial.polynomial.polyval(np.arange(3072)+512,coefficients)
    sigma_factor=CF*np.sin(np.deg2rad(theta))[:,None]
    noisy_path=EXP/'slc_observed_on_grd_sigma0.npy'
    complex_image=np.load(EXP/'slc_complex_native.npy',mmap_mode='r')
    native_power=complex_image.real**2+complex_image.imag**2
    calibrated=project(native_power,coordinates)*sigma_factor
    np.save(noisy_path,calibrated.astype(np.float32))
    print('Projected SLC observation',flush=True)
    native_result=EXP/'runs/merlin/denoised.npy'
    if native_result.exists():
        native=np.load(native_result,mmap_mode='r')
        projected=project(native,coordinates)*sigma_factor
        np.save(EXP/'runs/merlin/denoised_grd_sigma0.npy',projected.astype(np.float32))
        roi=json.loads((SCENE/'fig3_selection.json').read_text())['rois']['H']
        region=np.s_[roi['row_start']:roi['row_start']+roi['height'],roi['col_start']:roi['col_start']+roi['width']]
        grd=np.load(EXP/'noisy_intensity.npy',mmap_mode='r')
        gain=float(grd[region].mean(dtype=np.float64)/calibrated[region].mean(dtype=np.float64))
        report={'input':'native complex SLC','native_output':'denoised.npy',
                'projection':'bilinear interpolant integrated with 4x4 samples per GRD cell',
                'calibration':'sigma0 = CF * SLC_DN_power * sin(incidence_angle)',
                'calibration_factor':CF,'incidence_angle_range_deg':[float(theta.min()),float(theta.max())],
                'coordinates':'grd_to_slc_coordinates.npy',
                'ratio_numerator':'slc_observed_on_grd_sigma0.npy',
                'output':'denoised_grd_sigma0.npy',
                'display_product_gain':gain,'display_product_gain_source':'mean(GRD observed H) / mean(projected SLC observed H)',
                'display_product_gain_applied_to_scientific_array':False,
                'input_scale_discrepancy_H_before_matching':1/gain}
        (EXP/'runs/merlin/projection.json').write_text(json.dumps(report,indent=2))
        run_path=EXP/'runs/merlin/run.json'
        run_report=json.loads(run_path.read_text())
        run_report.update({'projection_pending':False,'projection_report':'projection.json'})
        run_path.write_text(json.dumps(run_report,indent=2),encoding='utf-8')
        print('Projected MERLIN estimate',flush=True)


if __name__=='__main__':
    main()
