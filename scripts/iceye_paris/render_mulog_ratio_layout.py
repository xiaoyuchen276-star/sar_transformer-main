"""Compose the Paris comparison using the author-corrected panel labels.

Uses the existing scientific display exports without recomputing or remapping data.
Run from any directory with Python and Pillow.
"""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
SCENE = ROOT / 'output/fig3_iceye_paris_20261109'
FIGURES = SCENE / 'seven_methods/figures'
OUT = FIGURES / 'mulog_ratio_layout'
FONT_PATHS = [
    Path('/System/Library/Fonts/Supplemental/Times New Roman.ttf'),
    Path('C:/Windows/Fonts/times.ttf'),
    Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'),
]
SOURCES = [
    ('a', 'Noisy', 'panels/a_noisy.png'),
    ('b', 'SAR-BM3D', 'panels/b_sar-bm3d.png'),
    ('c', 'SAR2SAR', 'panels/c_sar2sar.png'),
    ('d', 'SDUDNet*', 'panels/d_sdudnet.png'),
    ('e', 'Trans-SAR', 'panels/f_cl-sar.png'),
    ('f', 'Ours-base', 'panels/e_trans-sar.png'),
    ('g', 'Ours+AMS', 'panels/h_mulog-drunet.png'),
    ('h', 'Ours+AMS ratio', 'ratios/h_mulog-drunet_ratio.png'),
]


def font(size):
    for path in FONT_PATHS:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise FileNotFoundError('Install Times New Roman or DejaVu Serif.')


def main():
    OUT.mkdir(exist_ok=True)
    side, gap, pad, title, foot = 768, 18, 20, 42, 156
    width = 4 * side + 3 * gap + 2 * pad
    height = 2 * (side + title) + gap + 2 * pad + foot
    canvas = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(canvas)
    rois = json.loads((SCENE / 'fig3_selection.json').read_text())['rois']
    colors = {'H': '#ffcb36', 'S': '#ff706d', 'T': '#26cce2'}
    for index, (letter, name, source) in enumerate(SOURCES):
        row, col = divmod(index, 4)
        x = pad + col * (side + gap)
        y = pad + row * (side + title + gap)
        draw.text((x + side / 2, y + 4), f'({letter}) {name}',
                  font=font(28), fill='black', anchor='mt')
        with Image.open(FIGURES / source) as image:
            assert image.size == (3072, 3072), (source, image.size)
            view = image.convert('RGB').resize((side, side), Image.Resampling.BOX)
        if index == 0:
            markings = ImageDraw.Draw(view)
            for key, roi in rois.items():
                scale = side / 3072
                x0, y0 = roi['col_start'] * scale, roi['row_start'] * scale
                x1 = x0 + roi['width'] * scale
                y1 = y0 + roi['height'] * scale
                markings.rectangle((x0, y0, x1, y1), outline=colors[key], width=3)
                markings.text((x0 + 5, y0 + 3), key, font=font(23),
                              fill=colors[key], stroke_width=1, stroke_fill='black')
        canvas.paste(view, (x, y + title))

    y = height - foot + 18
    barwidth = 360
    gradient = Image.new('L', (256, 1))
    gradient.putdata(list(range(256)))
    gradient = gradient.resize((barwidth, 16))
    for center, label, limits in [
        (width * .32, '(a)-(g) Intensity (dB)', (-18, 0)),
        (width * .76, '(h) Ratio (dB)', (-5, 5)),
    ]:
        left = int(center - barwidth / 2)
        canvas.paste(gradient, (left, y))
        draw.rectangle((left, y, left + barwidth - 1, y + 15), outline='black')
        draw.text((left - 16, y), label, font=font(23), fill='black', anchor='rt')
        for fraction, value in [(0, limits[0]), (.5, sum(limits) / 2), (1, limits[1])]:
            draw.text((left + fraction * (barwidth - 1), y + 21), f'{value:g}',
                      font=font(21), fill='black', anchor='mt')
    footer = [
        '* SDUDNet uses the 8-bit display input. (h): 10 log10(input intensity / panel (g) output intensity); 0 dB = ratio 1.',
        'ICEYE Open Data (CC BY 4.0). Same 3072 x 3072 view. H / S / T mark the three inspection regions.',
    ]
    for index, line in enumerate(footer):
        draw.text((pad, y + 65 + index * 27), line, font=font(22), fill='#333333')
    full = OUT / 'comparison_8panel.png'
    canvas.save(full, dpi=(300, 300))
    canvas.thumbnail((1800, 1800), Image.Resampling.LANCZOS)
    canvas.save(OUT / 'comparison_preview.png')
    provenance = {
        'note': 'Author corrected the historical filenames and run-record attribution on 2026-11-15; current panel labels govern manuscript attribution.',
        'author_statement': '旧的文件名和运行记录标错了，以现在的标注为准',
        'panels': [
            {'panel': letter, 'display_label': name, 'source_image': source}
            for letter, name, source in SOURCES
        ],
        'historical_source_labels': {'e': 'CL-SAR', 'f': 'Trans-SAR', 'g': 'MuLoG-DRUNet', 'h': 'MuLoG-DRUNet ratio'},
        'author_corrected_labels': {'e': 'Trans-SAR', 'f': 'Ours-base', 'g': 'Ours+AMS', 'h': 'Ours+AMS ratio'},
    }
    (OUT / 'label_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(full)


if __name__ == '__main__':
    main()
