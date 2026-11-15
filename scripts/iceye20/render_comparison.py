"""Assemble shared-scale full-scene, H/S/T and ratio comparisons from saved results."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw
from common import DATA, METHODS, LABELS, manifest


def render_scene(results, scene_id):
    methods = ["noisy", *METHODS]
    output = results / "comparisons" / scene_id; output.mkdir(parents=True, exist_ok=True)
    for stem in ["full_scene_preview", "full_ratio_preview", "homogeneous_preview", "structural_preview",
                 "texture_preview", "homogeneous_ratio_preview", "structural_ratio_preview", "texture_ratio_preview"]:
        first = results / "scenes" / scene_id / "noisy" / (stem + ".png")
        if not first.exists():
            continue
        with Image.open(first) as image:
            full = stem.startswith("full_")
            width = 900 if full else 256
            height = round(image.height * width / image.width)
        columns = 2 if full else 5
        rows = (len(methods) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * width, rows * (height + 28)), "white")
        draw = ImageDraw.Draw(sheet)
        for index, method in enumerate(methods):
            x, y = (index % columns) * width, (index // columns) * (height + 28)
            draw.text((x + 8, y + 6), f"{scene_id} / {LABELS.get(method, 'Noisy')}", fill="black")
            path = results / "scenes" / scene_id / method / (stem + ".png")
            if path.exists():
                with Image.open(path) as image:
                    sheet.paste(image.resize((width, height), Image.Resampling.LANCZOS), (x, y + 28))
            else:
                draw.text((x + 8, y + 42), "No completed result", fill="red")
        sheet.save(output / (stem + "_comparison.png"))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True); p.add_argument("--root", type=Path, default=DATA)
    p.add_argument("--scene")
    a = p.parse_args()
    for item in manifest(a.root)["scenes"]:
        if not a.scene or item["scene_id"] == a.scene:
            render_scene(a.results, item["scene_id"])
