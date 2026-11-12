"""Export a pixel-exact scientific crop, calibrated intensity, and labeled previews."""
from pathlib import Path
import hashlib
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import rasterio
from rasterio.control import GroundControlPoint
from rasterio.rpc import RPC
from rasterio.windows import Window

ROOT=Path(__file__).resolve().parent
SCENE='ICEYE_U09WX2_20251028T000519Z_6785560_X56_SLF'
SOURCE=ROOT/'raw'/f'{SCENE}_GRD.tif'
PARENT_METADATA=ROOT/'raw'/f'{SCENE}_GRD.json'
CF=json.loads(PARENT_METADATA.read_text())['properties']['iceye:calibration_factor']
X,Y,SIZE=3328,512,3072
ROIS={
    'H': {'col_start':2624,'row_start':1696,'width':384,'height':384,'description':'Relatively homogeneous field interior'},
    'S': {'col_start':1200,'row_start':1424,'width':384,'height':384,'description':'Roof edges and corners'},
    'T': {'col_start':320,'row_start':256,'width':384,'height':384,'description':'Dense residential scattering texture'},
}
DISPLAY_DB=(-18.,0.)

def show(dn):
    sigma=CF*dn.astype(np.float64)**2
    db=10*np.log10(np.maximum(sigma,1e-12))
    return Image.fromarray(np.rint(255*np.clip((db+18)/18,0,1)).astype(np.uint8))

def digest(path):
    result=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024*1024),b''):
            result.update(block)
    return result.hexdigest()

with rasterio.open(SOURCE) as src:
    amplitude=src.read(1,window=Window(X,Y,SIZE,SIZE))
    intensity=(CF*amplitude.astype(np.float64)**2).astype(np.float32)
    points,gcp_crs=src.gcps
    shifted_points=[GroundControlPoint(row=p.row-Y,col=p.col-X,x=p.x,y=p.y,z=p.z,id=p.id,info=p.info) for p in points]
    rpc_values=src.rpcs.to_dict()
    rpc_values['line_off']-=Y
    rpc_values['samp_off']-=X
    shifted_rpc=RPC(**rpc_values)
    products={}
    for name,array,domain in [
        ('fig3_view_amplitude.tif',amplitude,'Original uint16 amplitude DN; unchanged pixel values'),
        ('fig3_view_sigma0.tif',intensity,'Calibrated linear sigma0 intensity; float32'),
    ]:
        target=ROOT/'crops'/name
        profile={'driver':'GTiff','height':SIZE,'width':SIZE,'count':1,
                 'dtype':array.dtype,'tiled':True,'blockxsize':256,'blockysize':256,
                 'compress':'deflate','nodata':0,'gcps':shifted_points,'crs':gcp_crs}
        with rasterio.open(target,'w',**profile) as dst:
            dst.write(array,1)
            dst.update_tags(ns='RPC',**shifted_rpc.to_gdal())
            dst.update_tags(SOURCE_SCENE=SCENE,SOURCE_COL_START=str(X),SOURCE_ROW_START=str(Y),
                            PIXEL_DOMAIN=domain,CALIBRATION_FACTOR=str(CF),
                            SOURCE_METADATA=str(PARENT_METADATA),
                            PROCESSING='Contiguous original-grid window; no spatial resampling or despeckling')
        with rasterio.open(target) as check:
            if not np.array_equal(check.read(1),array):
                raise RuntimeError(f'Pixel verification failed: {name}')
            assert len(check.gcps[0])==len(points)
            assert abs(check.rpcs.line_off-shifted_rpc.line_off)<1e-8
            assert abs(check.rpcs.samp_off-shifted_rpc.samp_off)<1e-8
        products[name]={'size_bytes':target.stat().st_size,'sha256':digest(target),'domain':domain}

    shown=show(amplitude)
    shown.save(ROOT/'previews'/'fig3_view.png')
    annotated=shown.resize((1536,1536),Image.Resampling.NEAREST).convert('RGB')
    draw=ImageDraw.Draw(annotated)
    font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',40)
    colors={'H':'#ffd43b','S':'#ff6767','T':'#35d6ee'}
    for key,region in ROIS.items():
        x,y,w,h=[region[k] for k in ['col_start','row_start','width','height']]
        draw.rectangle((x/2,y/2,(x+w)/2,(y+h)/2),outline=colors[key],width=5)
        draw.text((x/2+8,y/2+7),key,font=font,fill=colors[key],stroke_width=2,stroke_fill='black')
        patch=intensity[y:y+h,x:x+w].astype(np.float64)
        means=patch.reshape(4,h//4,4,w//4).mean(axis=(1,3))
        region['parent_col_start']=X+x
        region['parent_row_start']=Y+y
        region['sigma0_mean']=float(patch.mean())
        region['sigma0_enl_diagnostic']=float(patch.mean()**2/patch.var(ddof=1))
        region['subblock_mean_cv_4x4']=float(means.std(ddof=1)/means.mean())
        region['subblock_mean_min_max_relative_to_roi_mean']=[float(means.min()/patch.mean()),float(means.max()/patch.mean())]
        shown.crop((x,y,x+w,y+h)).save(ROOT/'previews'/f'roi_{key}_native.png')
    annotated.save(ROOT/'previews'/'fig3_view_regions.png')
    full=Image.open(ROOT/'previews'/'full_grd_overview.png').convert('RGB')
    draw=ImageDraw.Draw(full)
    draw.rectangle((X/8,Y/8,(X+SIZE)/8,(Y+SIZE)/8),outline='#ffd43b',width=6)
    draw.text((X/8,Y/8+SIZE/8+10),'Fig. 3 view',font=font,fill='#ffd43b',stroke_width=2,stroke_fill='black')
    full.save(ROOT/'previews'/'full_grd_selected_view.png')

record={
    'scene':SCENE,'source_file':str(SOURCE),'source_download':json.loads((ROOT/'raw'/'download_verification.json').read_text()),
    'parent_metadata':str(PARENT_METADATA),'coordinate_convention':'zero-based; half-open [start,start+size)',
    'crop':{'col_start':X,'row_start':Y,'width':SIZE,'height':SIZE,'nominal_extent_m':[768.,768.]},
    'pixel_spacing_m':[.25,.25],'resolution_m':[.495875,.5],
    'selection_reason':'Compact continuous view with residential texture, regular roofs/roads, and field interiors',
    'radiometry':{'input':'uint16 scaled amplitude','sigma0_formula':'calibration_factor * float64(DN)^2',
                  'calibration_factor':CF,'output_dtype':'float32','amplitude_mapping_tag_present':False},
    'display':{'transform':'10*log10(sigma0)','limits_db':DISPLAY_DB,'normalization_scope':'shared fixed window for all current previews',
               'native_crop_png_size':[SIZE,SIZE],'annotated_preview_size':[1536,1536],
               'annotation_preview_resampling':'nearest','note':'Display clipping does not alter scientific TIFF values'},
    'spatial_processing':'No resampling, rotation, reprojection, or despeckling of scientific crops',
    'georeferencing':'All parent GCP pixel coordinates shifted by crop origin; RPC line/samp offsets shifted; parent metadata stored separately',
    'rois':ROIS,'products':products,
    'validation':{'amplitude_crop_pixel_exact':True,'intensity_file_roundtrip_exact':True,'adjusted_gcp_rpc_checked':True},
    'attribution':'ICEYE Open Data, CC BY 4.0',
    'radiometric_reference':'https://sar.iceye.com/6.0.6/foundations/radiometric/#calibration-correction',
}
(ROOT/'fig3_selection.json').write_text(json.dumps(record,indent=2))
print(json.dumps({'crop':record['crop'],'rois':ROIS,'products':products},indent=2))
