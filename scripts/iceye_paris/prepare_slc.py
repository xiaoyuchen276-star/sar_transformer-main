"""Download the native complex window covering the fixed GRD display crop."""
import hashlib
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import RPCTransformer
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / 'output/fig3_iceye_paris_20261109'
OUT = SCENE / 'seven_methods'
NAME = 'ICEYE_U09WX2_20251028T000519Z_6785560_X56_SLF'
URL = f'https://iceye-open-data-catalog.s3.us-west-2.amazonaws.com/data/spot-fine/{NAME}/{NAME}_SLC.tif'


def main():
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', GDAL_HTTP_CONNECTTIMEOUT='30',
                      GDAL_HTTP_TIMEOUT='120', GDAL_HTTP_MAX_RETRY='4',
                      CPL_VSIL_CURL_ALLOWED_EXTENSIONS='.tif', GDAL_HTTP_MULTIRANGE='YES'):
        with rasterio.open(URL) as source, rasterio.open(SCENE / 'crops/fig3_view_sigma0.tif') as target:
            with RPCTransformer(target.rpcs) as ground, RPCTransformer(source.rpcs) as slant:
                # One common ellipsoidal height for both products.
                lon, lat = ground.xy([0,0,3071,3071], [0,3071,0,3071], zs=[0]*4)
                rows, cols = slant.rowcol(lon, lat, zs=[0]*4, op=lambda x:x)
                r0, c0 = (int(np.floor((min(v)-128)/64)*64) for v in (rows, cols))
                r1, c1 = (int(np.ceil((max(v)+128)/64)*64) for v in (rows, cols))
                window = Window(c0,r0,c1-c0,r1-r0)
                print(f'SLC window {window}, native complex pixels', flush=True)
                destination = OUT/'slc_complex_native.npy'
                if not destination.exists():
                    channels = source.read(window=window)
                    amplitude, phase = channels
                    if np.any(amplitude<0) or np.max(np.abs(phase))>np.pi+1e-5:
                        raise ValueError('Unexpected ICEYE amplitude/phase encoding')
                    complex_image = (amplitude * np.exp(1j*phase)).astype(np.complex64)
                    np.save(destination,complex_image)
                    print('Saved complex SLC',complex_image.shape,flush=True)
                # RPC pixel coordinates refer to corners. scipy array coordinates
                # refer to centers, hence the subtraction of half a pixel.
                coordinates = np.empty((2,3072,3072), dtype=np.float32)
                for row in range(0,3072,128):
                    rr,cc=np.mgrid[row:row+128,0:3072]
                    x,y=ground.xy(rr.ravel(),cc.ravel(),zs=np.zeros(rr.size))
                    sr,sc=slant.rowcol(x,y,zs=np.zeros(rr.size),op=lambda x:x)
                    coordinates[0,row:row+128]=np.asarray(sr).reshape(128,3072)-r0-0.5
                    coordinates[1,row:row+128]=np.asarray(sc).reshape(128,3072)-c0-0.5
                np.save(OUT/'grd_to_slc_coordinates.npy',coordinates)
                assert coordinates.min()>0
                assert coordinates[0].max()<r1-r0-1 and coordinates[1].max()<c1-c0-1
                record={'url':URL,'native_shape':[source.height,source.width],
                        'window':{'row_start':r0,'col_start':c0,'height':r1-r0,'width':c1-c0},
                        'mapping':'GRD pixel center -> RPC at ellipsoid height 0 m -> SLC pixel center',
                        'native_input_resampled':False,'source_rpc':source.rpcs.to_dict(),
                        'band_encoding':'band 1 linear amplitude, band 2 phase in radians',
                        'complex_conversion':'S = amplitude * exp(1j * phase)',
                        'native_input_sha256':hashlib.sha256(destination.read_bytes()).hexdigest()}
                (OUT/'slc_input.json').write_text(json.dumps(record,indent=2))
                print('SLC and GRD correspondence prepared',flush=True)


if __name__=='__main__':
    main()
