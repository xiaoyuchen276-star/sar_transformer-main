"""Export the original plus seven restorations with shared display windows."""
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.io import loadmat

ROOT=Path(__file__).resolve().parents[2]
SCENE=ROOT/'output/fig3_iceye_paris_20261109'
EXP=SCENE/'seven_methods'
NAMES=['Noisy','SAR-BM3D','SAR2SAR','SDUDNet','Trans-SAR','CL-SAR','MERLIN','MuLoG-DRUNet']
STEMS=['a_noisy','b_sar-bm3d','c_sar2sar','d_sdudnet','e_trans-sar','f_cl-sar','g_merlin','h_mulog-drunet']
KEYS=['noisy','sarbm3d','sar2sar','sdudnet','transsar','cl_sar','merlin','mulog_drunet']
COLORS={'H':'#ffcb36','S':'#ff706d','T':'#26cce2'}
REGION_NAMES={'H':'Homogeneous field','S':'Roof edges','T':'Residential texture'}


def font(size):
    return ImageFont.truetype('C:/Windows/Fonts/times.ttf',size)


def display(values,limits):
    valid=np.isfinite(values)
    pixels=np.rint(255*np.clip((np.where(valid,values,limits[0])-limits[0])/(limits[1]-limits[0]),0,1)).astype(np.uint8)
    result=Image.fromarray(pixels).convert('RGB')
    if not valid.all():
        color=np.asarray(result).copy()
        color[~valid]=(220,70,150)
        result=Image.fromarray(color)
    return result


def make_figure(images,labels,path,side,footer,limits,rois=None):
    gap=18
    title=42 if side>=512 else 32
    pad=20
    foot=132 if side>=512 else 120
    width=4*side+3*gap+2*pad
    height=2*(side+title)+gap+2*pad+foot
    canvas=Image.new('RGB',(width,height),'white')
    draw=ImageDraw.Draw(canvas)
    for index,(im,label) in enumerate(zip(images,labels)):
        row,col=divmod(index,4)
        x=pad+col*(side+gap)
        y=pad+row*(side+title+gap)
        draw.text((x+side/2,y+4),label,font=font(28 if side>=512 else 22),fill='black',anchor='mt')
        view=im.resize((side,side),Image.Resampling.BOX) if im.size!=(side,side) else im.copy()
        if index==0 and rois:
            markings=ImageDraw.Draw(view)
            for key,roi in rois.items():
                scale=side/3072
                x0,y0=roi['col_start']*scale,roi['row_start']*scale
                x1,y1=x0+roi['width']*scale,y0+roi['height']*scale
                markings.rectangle((x0,y0,x1,y1),outline=COLORS[key],width=3)
                markings.text((x0+5,y0+3),key,font=font(23),fill=COLORS[key],stroke_width=1,stroke_fill='black')
        canvas.paste(view,(x,y+title))
    y=height-foot+18
    barwidth=280
    gradient=Image.fromarray(np.tile(np.arange(256,dtype=np.uint8),(12,1))).resize((barwidth,14))
    barleft=(width-barwidth)//2
    canvas.paste(gradient,(barleft,y))
    draw.rectangle((barleft,y,barleft+barwidth,y+14),outline='black')
    unit='Intensity (dB)' if limits==(-18,0) else 'Ratio (dB)'
    for fraction,value in [(0,limits[0]),(.5,sum(limits)/2),(1,limits[1])]:
        draw.text((barleft+fraction*barwidth,y+18),f'{value:g}',font=font(19),fill='black',anchor='mt')
    draw.text((barleft-12,y+2),unit,font=font(20),fill='black',anchor='rt')
    for index,line in enumerate(footer):
        draw.text((pad,y+46+index*24),line,font=font(20 if side>=512 else 17),fill='#333333')
    canvas.save(path,dpi=(300,300))


def main():
    out=EXP/'figures'
    panels=out/'panels'
    ratios_dir=out/'ratios'
    panels.mkdir(parents=True,exist_ok=True)
    ratios_dir.mkdir(exist_ok=True)
    noisy=np.load(EXP/'noisy_intensity.npy')
    values={'noisy':noisy,'sarbm3d':loadmat(EXP/'runs/sarbm3d/result.mat',variable_names=['denoised'])['denoised']}
    for key in KEYS[2:]:
        filename='denoised_grd_sigma0.npy' if key=='merlin' else 'denoised.npy'
        values[key]=np.load(EXP/'runs'/key/filename)
    slc_noisy=np.load(EXP/'slc_observed_on_grd_sigma0.npy')
    projection=json.loads((EXP/'runs/merlin/projection.json').read_text())
    merlin_display_gain=projection['display_product_gain']
    regions=json.loads((SCENE/'fig3_selection.json').read_text())['rois']
    shown=[]
    metadata_scale_images=[]
    ratio_images=[display(10*np.log10(noisy),(-18,0))]
    statistics=[]
    captions=['(a) Noisy','(b) SAR-BM3D','(c) SAR2SAR','(d) SDUDNet*','(e) Trans-SAR','(f) CL-SAR','(g) MERLIN**','(h) MuLoG-DRUNet']
    ratio_labels=['Noisy (-18 to 0 dB)']+[f'{name} ratio'+('**' if key=='merlin' else '*' if key=='sdudnet' else '') for name,key in zip(NAMES[1:],KEYS[1:])]
    for name,key,stem in zip(NAMES,KEYS,STEMS):
        estimate=values[key]
        if estimate.shape!=(3072,3072) or not np.isfinite(estimate).all() or np.any(estimate<0):
            raise ValueError(f'Invalid output {key}')
        image=display(10*np.log10(np.maximum(estimate,1e-12)),(-18,0))
        metadata_scale_images.append(image.copy())
        if key=='merlin':
            image.save(panels/f'{stem}_metadata_scale.png',dpi=(300,300))
            image=display(10*np.log10(np.maximum(estimate*merlin_display_gain,1e-12)),(-18,0))
        image.save(panels/f'{stem}.png',dpi=(300,300))
        shown.append(image)
        if key=='noisy':
            continue
        numerator=slc_noisy if key=='merlin' else noisy
        ratio=np.full(noisy.shape,np.nan,dtype=np.float32)
        np.divide(numerator,estimate,out=ratio,where=estimate>0)
        with np.errstate(divide='ignore', invalid='ignore'):
            ratio_image=display(10*np.log10(ratio),(-5,5))
        ratio_image.save(ratios_dir/f'{stem}_ratio.png',dpi=(300,300))
        ratio_images.append(ratio_image)
        for region,roi in {'Whole crop':None,**regions}.items():
            selection=np.s_[:,:] if roi is None else np.s_[roi['row_start']:roi['row_start']+roi['height'],roi['col_start']:roi['col_start']+roi['width']]
            r=ratio[selection]
            valid=np.isfinite(r)
            source=numerator[selection].astype(np.float64)
            restored=estimate[selection].astype(np.float64)
            statistics.append({'method':name,'region':region,'pixels':r.size,'valid_ratio_fraction':float(valid.mean()),
                               'ratio_mean':float(r[valid].mean(dtype=np.float64)),
                               'ratio_std':float(r[valid].std(dtype=np.float64,ddof=1)),
                               'output_to_input_mean':float(restored.mean()/source.mean()),
                               'input_enl_H':float(source.mean()**2/source.var(ddof=1)) if region=='H' else '',
                               'output_enl_H':float(restored.mean()**2/restored.var(ddof=1)) if region=='H' else '',
                               'input_product':'projected SLC' if key=='merlin' else 'GRD',
                               'display_domain_adapter':key=='sdudnet'})
    foot=['* SDUDNet uses the 8-bit display input.  ** MERLIN uses SLC with an input-derived display scale match.',
          'ICEYE Open Data (CC BY 4.0). Same 3072 x 3072 view. H / S / T mark the three inspection regions.']
    make_figure(shown,captions,out/'comparison_8panel.png',768,foot,(-18,0),regions)
    make_figure(metadata_scale_images,captions,out/'comparison_8panel_metadata_scale.png',768,
                ['* SDUDNet uses display input. ** MERLIN uses SLC. All panels use the metadata intensity scale.',
                 'ICEYE Open Data (CC BY 4.0). Fixed -18 to 0 dB window.'],(-18,0),regions)
    make_figure(ratio_images,ratio_labels,out/'ratio_8panel.png',768,
                ['Ratios use input / output linear intensity. MERLIN uses its corresponding projected SLC input.',
                 '* SDUDNet uses the display-domain adapter. Pink denotes undefined ratios. ICEYE Open Data (CC BY 4.0).'],(-5,5))
    for key,roi in regions.items():
        x,y=roi['col_start'],roi['row_start']
        box=(x,y,x+roi['width'],y+roi['height'])
        footer=[f'{key}  {REGION_NAMES[key]}. 384 x 384 pixels. * SDUDNet display input. ** MERLIN SLC, input-scaled display.',
                'Shared display window. ICEYE Open Data (CC BY 4.0).']
        make_figure([im.crop(box) for im in shown],captions,out/f'roi_{key}_8panel.png',384,footer,(-18,0))
        make_figure([im.crop(box) for im in ratio_images],ratio_labels,out/f'roi_{key}_ratios.png',384,
                    [f'{key}  {REGION_NAMES[key]}. Ratios use each method\'s corresponding input.',
                     '* SDUDNet display input. ** MERLIN projected SLC input. ICEYE Open Data (CC BY 4.0).'],(-5,5))
    with (out/'roi_statistics.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(statistics[0]))
        writer.writeheader()
        writer.writerows(statistics)
    preview=Image.open(out/'comparison_8panel.png')
    preview.thumbnail((1800,1800),Image.Resampling.LANCZOS)
    preview.save(out/'comparison_preview.png')
    print(out.resolve())


if __name__=='__main__':
    main()
