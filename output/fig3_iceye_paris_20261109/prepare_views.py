"""Render unfiltered scientific data and extract candidate windows without resampling."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import rasterio
from rasterio.enums import Resampling
from rasterio.windows import Window

ROOT = Path(__file__).resolve().parent
SCENE = 'ICEYE_U09WX2_20251028T000519Z_6785560_X56_SLF'
SOURCE = ROOT/'raw'/f'{SCENE}_GRD.tif'
PROPERTIES = json.loads((ROOT/'raw'/f'{SCENE}_GRD.json').read_text())['properties']
CF = PROPERTIES['iceye:calibration_factor']
DISPLAY_DB = (-18., 0.)
CANDIDATES = {'A': (1792,2304,4096,4096), 'B': (3328,512,4096,4096)}

def display(dn):
    intensity = CF * dn.astype(np.float64)**2
    db = 10*np.log10(np.maximum(intensity,1e-12))
    pixels = np.rint(255*np.clip((db-DISPLAY_DB[0])/(DISPLAY_DB[1]-DISPLAY_DB[0]),0,1)).astype(np.uint8)
    pixels[dn==0] = 0
    return Image.fromarray(pixels)

def font(size):
    return ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',size)

with rasterio.open(SOURCE) as src:
    tags=src.tags()
    if 'amplitude_mapping' in json.dumps(tags).lower():
        raise RuntimeError('Review amplitude mapping before radiometric conversion.')
    report={'source':str(SOURCE),'width':src.width,'height':src.height,
            'dtype':src.dtypes[0], 'crs':str(src.crs),'transform':list(src.transform),
            'gcp_count':len(src.gcps[0]),'gcp_crs':str(src.gcps[1]),
            'rpc_present':src.rpcs is not None,'calibration_factor':CF,
            'intensity_formula':'sigma0 = calibration_factor * float(DN)^2',
            'display':{'domain':'10*log10(sigma0)','limits_db':DISPLAY_DB,
                       'purpose':'display only; original and crop DN are unchanged'},
            'candidates':{}}
    overview=src.read(1,out_shape=(2500,2500),resampling=Resampling.nearest)
    overview_image=display(overview)
    overview_image.save(ROOT/'previews'/'full_grd_overview.png')
    marked=overview_image.convert('RGB');draw=ImageDraw.Draw(marked)
    for name,(x,y,w,h) in CANDIDATES.items():
        window=Window(x,y,w,h)
        array=src.read(1,window=window)
        np.save(ROOT/'crops'/f'candidate_{name}_amplitude_dn.npy',array)
        shown=display(array)
        shown.resize((1536,1536),Image.Resampling.NEAREST).save(ROOT/'previews'/f'candidate_{name}_preview.png')
        box=(x/8,y/8,(x+w)/8,(y+h)/8)
        color={'A':'#ffcf33','B':'#35bdf6'}[name]
        draw.rectangle(box,outline=color,width=6)
        draw.text((box[0]+10,box[1]+10),name,font=font(44),fill=color,stroke_width=2,stroke_fill='black')
        report['candidates'][name]={'col_start':x,'row_start':y,'width':w,'height':h,
             'coordinate_convention':'zero-based, half-open',
             'nominal_extent_m':[w*.25,h*.25],
             'dn_range':[int(array.min()),int(array.max())],
             'zero_fraction':float(np.mean(array==0)),
             'uint16_max_fraction':float(np.mean(array==65535))}
    marked.save(ROOT/'previews'/'candidate_locations.png')
    (ROOT/'selection_working.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
