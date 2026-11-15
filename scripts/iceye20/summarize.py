"""Generate mean-only Table IV/V Markdown and JSON; never creates Excel files."""
from __future__ import annotations
import argparse
from pathlib import Path
import numpy as np
from common import DATA, METHODS, LABELS, manifest, read_json, write_json

METRICS = ("ENL", "M-index", "EPI", "RGPI")
CATEGORIES = ("homogeneous", "structural", "texture")


def average(rows, metric, expected):
    values = [row["values"][metric] for row in rows if row["values"].get(metric) is not None]
    return {"mean": float(np.mean(values)) if values else None, "valid_n": len(values), "expected_n": expected}


def cells(values):
    return " | ".join("—" if values[k]["mean"] is None else format(values[k]["mean"], ".2f" if k == "ENL" else ".4f") for k in METRICS)


def summarize(results, root=DATA):
    scenes = manifest(root)["scenes"]
    iv, v, missing = [], [], []
    for scene in scenes:
        for method in ["noisy", *METHODS]:
            folder = results / "scenes" / scene["scene_id"] / method
            if not (folder / "evaluation.json").exists():
                missing.append({"scene_id": scene["scene_id"], "method": method}); continue
            if not read_json(folder / "evaluation.json")["complete"]:
                raise ValueError("Unexpected incomplete evaluation receipt")
            iv.append(read_json(folder / "table_iv.json")); v.extend(read_json(folder / "table_v.json"))
    table_iv, table_v, notes = [], [], []
    for method in ["noisy", *METHODS]:
        rows = [x for x in iv if x["method"] == method]
        values = {k: average(rows, k, 20) for k in METRICS}
        table_iv.append({"method": method, "metrics": values})
        for metric, item in values.items():
            if item["valid_n"] != 20 and not (method == "noisy" and metric == "M-index"):
                notes.append(f"Table IV {LABELS.get(method, 'Noisy')} / {metric}: {item['valid_n']}/20 valid scenes.")
    for method in ("ours_base", "ours_ams"):
        category_results = []
        for category in CATEGORIES:
            rows = [x for x in v if x["method"] == method and x["category"] == category]
            values = {k: average(rows, k, 20) for k in METRICS}
            item = {"method": method, "category": category, "regions": 20, "metrics": values}
            table_v.append(item); category_results.append(item)
            for metric, value in values.items():
                if value["valid_n"] != 20:
                    notes.append(f"Table V {category} / {LABELS[method]} / {metric}: {value['valid_n']}/20 valid regions.")
        values = {}
        for metric in METRICS:
            means = [x["metrics"][metric]["mean"] for x in category_results]
            values[metric] = {"mean": float(np.mean(means)) if all(x is not None for x in means) else None,
                              "valid_n": sum(x["metrics"][metric]["valid_n"] for x in category_results), "expected_n": 60}
        table_v.append({"method": method, "category": "Average", "regions": 60, "metrics": values})
    noisy_enl = {category: average([x for x in v if x["method"] == "noisy" and x["category"] == category], "ENL", 20)
                 for category in CATEGORIES}
    means = [noisy_enl[x]["mean"] for x in CATEGORIES]
    noisy_enl["Average"] = {"mean": float(np.mean(means)) if all(x is not None for x in means) else None,
                            "valid_n": sum(noisy_enl[x]["valid_n"] for x in CATEGORIES), "expected_n": 60}
    write_json(results / "summary.json", {"aggregation": "arithmetic means only", "table_iv": table_iv,
               "table_v": table_v, "noisy_enl_by_region_type": noisy_enl, "missing_runs": missing,
               "effective_sample_notes": notes, "all_expected_evaluations_present": not missing})
    lines = ["TABLE IV. Mean No-Reference Results on 20 Full ICEYE SAR Scenes", "",
             "| Method | ENL | M-index ↓ | EPI | RGPI |", "|---|---:|---:|---:|---:|"]
    lines += [f"| {LABELS.get(row['method'], 'Noisy')} | {cells(row['metrics'])} |" for row in table_iv]
    lines += ["", "Each scene has equal weight. ENL is averaged over ten input-fixed 64×64 ROIs per scene.", "",
              "TABLE V. Mean No-Reference Results by Region Type on ICEYE SAR Images", "",
              "| Region type | Regions | Model | ENL | M-index ↓ | EPI | RGPI |", "|---|---:|---|---:|---:|---:|---:|"]
    for category in [*CATEGORIES, "Average"]:
        for method in ("ours_base", "ours_ams"):
            row = next(x for x in table_v if x["category"] == category and x["method"] == method)
            lines.append(f"| {category.title()} | {row['regions']} | {LABELS[method]} | {cells(row['metrics'])} |")
    lines += ["", "Each category contains twenty fixed 256×256 regions. Average gives equal weight to the three category means.",
              "ENL is a smoothness diagnostic and is not ranked. Noisy M-index is undefined. Table II is unchanged."]
    input_enl_text = [f"{category.title()} = " + ("—" if value["mean"] is None else f"{value['mean']:.2f}")
                      for category, value in noisy_enl.items()]
    lines += ["", "Noisy ENL: " + "; ".join(input_enl_text) + "."]
    if notes:
        lines += ["", "Effective sample counts:", "", *["- " + note for note in notes]]
    if missing:
        lines += ["", f"INCOMPLETE: {len(missing)} scene/method evaluations have not completed; see summary.json."]
    (results / "TABLE_IV_TABLE_V.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results", type=Path, required=True); p.add_argument("--root", type=Path, default=DATA)
    a = p.parse_args(); summarize(a.results, a.root)
