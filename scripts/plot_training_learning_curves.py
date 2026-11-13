"""Plot recorded training losses without smoothing or filling gaps.

Usage:
    python scripts/plot_training_learning_curves.py

The author confirmed these two runs for the manuscript on 2026-11-13.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


MODEL = "TransSARV2_DualFreqNG_Bottle"
TRAIN_COLOR = "#2463A5"
VAL_COLOR = "#C46D21"
EPOCH_FIELDS = (
    "epoch", "batch_size", "initial_lr", "current_lr", "weight_decay",
    "lambda_loss", "train_loss", "val_loss", "val_selfsup_loss",
)


def read_runs(path: Path) -> list[dict]:
    runs = []
    active = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        model = parts[0]
        fields = dict(part.split("=", 1) for part in parts[1:] if "=" in part)
        if parts[1] == "train_start":
            run = {"model": model, "start": fields, "start_line": line_number, "rows": []}
            active[model] = run
            runs.append(run)
        elif parts[1] == "train_end":
            active[model]["end"] = fields
        elif parts[1] == "best_model":
            active[model]["best"] = {
                key: fields[key] for key in ("epoch", "best_val_loss", "best_val_selfsup_loss", "path")
                if key in fields
            }
        elif "epoch" in fields and "train_loss" in fields:
            if model not in active:
                raise ValueError(f"Epoch record without run start at line {line_number}")
            active[model]["rows"].append({
                "source_line": line_number,
                **{key: fields[key] for key in EPOCH_FIELDS if key in fields},
            })
    for run in runs:
        rows = run["rows"]
        if not rows:
            continue
        run["stage"] = "ams" if "val_selfsup_loss" in rows[0] else "supervised"
        epochs = [int(row["epoch"]) for row in rows]
        if epochs != list(range(1, len(rows) + 1)):
            raise ValueError(f"Missing, duplicate, or unordered epochs: {run['model']}")
        for row in rows:
            for field in ("train_loss", "val_loss", "current_lr"):
                if not math.isfinite(float(row[field])):
                    raise ValueError(f"Invalid {field} at source line {row['source_line']}")
            if run["stage"] == "ams" and row["val_loss"] != row["val_selfsup_loss"]:
                raise ValueError("AMS val_loss and val_selfsup_loss differ")
    return runs


def write_csv(path: Path, rows: list[dict]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def values(run: dict, key: str) -> list[float]:
    return [float(row[key]) for row in run["rows"]]


def style_axis(ax, last_epoch: int, ylabel: str) -> None:
    ax.set_xlabel("Epoch")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0.5, last_epoch + 0.5)
    ax.set_xticks([1, 10, 20, 30, 40, 50] if last_epoch == 50 else list(range(1, 9)))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.grid(axis="both", color="#DCE2E8", linewidth=0.6, alpha=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        ax.spines[spine].set_color("#9AA5B1")


def save_figure(fig, output: Path, name: str) -> list[str]:
    outputs = []
    for suffix in ("png", "pdf", "svg"):
        path = output / f"{name}.{suffix}"
        fig.savefig(path, dpi=300, facecolor="white")
        outputs.append(path.name)
    plt.close(fig)
    return outputs


def plot_losses(supervised: dict, ams: dict, output: Path) -> list[str]:
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.35))
    fig.subplots_adjust(left=0.085, right=0.98, bottom=0.27, top=0.75, wspace=0.31)
    fig.suptitle("Training and validation loss", y=0.965, fontsize=14, weight="semibold")
    fig.text(0.5, 0.885, f"{MODEL}  |  May 2026", ha="center", fontsize=10, color="#485566")
    for ax, run, title in zip(axes, (supervised, ams), (
        "(a) Supervised training: 50 epochs", "(b) AMS adaptation: 8 epochs"
    )):
        epochs = values(run, "epoch")
        train = values(run, "train_loss")
        val = values(run, "val_loss")
        labels = ("Training objective", "Validation MSE") if run["stage"] == "supervised" else (
            "Training self-supervised loss", "Validation self-supervised loss"
        )
        ax.plot(epochs, train, color=TRAIN_COLOR, linewidth=1.5, marker="o", markersize=2.7, label=labels[0])
        ax.plot(epochs, val, color=VAL_COLOR, linewidth=1.5, linestyle="--", marker="s", markersize=2.7, label=labels[1])
        best_index = min(range(len(val)), key=val.__getitem__)
        ax.scatter([epochs[best_index]], [val[best_index]], marker="*", s=100, color=VAL_COLOR,
                   edgecolor="#343A40", linewidth=0.6, zorder=5,
                   label=f"Minimum validation loss: epoch {int(epochs[best_index])}")
        style_axis(ax, len(epochs), "Loss")
        ax.margins(y=0.17)
        ax.set_title(title, loc="left", fontsize=11, pad=10, y=1.10)
        ax.legend(loc="upper right", frameon=False, fontsize=8, handlelength=2.3)
    axes[0].ticklabel_format(axis="y", style="sci", scilimits=(-3, -3), useMathText=True)
    fig.text(0.085, 0.12, "Supervised training loss includes TV; validation loss is MSE. AMS uses its self-supervised objective.",
             fontsize=8.2, color="#485566")
    fig.text(0.085, 0.075, "Recorded epoch values; no smoothing. Initial learning rates: supervised 0.0002; AMS 0.000002.",
             fontsize=8.2, color="#485566")
    return save_figure(fig, output, "training_validation_loss")


def plot_paper_panel(run: dict, output: Path) -> list[str]:
    """Export one column-sized figure; the manuscript supplies its caption."""
    with plt.rc_context({
        "font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
        "font.size": 8, "mathtext.fontset": "stix", "axes.labelsize": 8,
        "xtick.labelsize": 7, "ytick.labelsize": 7,
    }):
        fig, ax = plt.subplots(figsize=(3.45, 1.55))
        fig.subplots_adjust(left=0.16, right=0.985, bottom=0.25, top=0.90)
        epochs = values(run, "epoch")
        validation = values(run, "val_loss")
        is_supervised = run["stage"] == "supervised"
        labels = ("Training objective", "Validation MSE") if is_supervised else (
            "Training", "Validation"
        )
        ax.plot(epochs, values(run, "train_loss"), color=TRAIN_COLOR, linewidth=1,
                marker="o", markersize=1.8, label=labels[0])
        ax.plot(epochs, validation, color=VAL_COLOR, linewidth=1, linestyle="--",
                marker="s", markersize=1.8, label=labels[1])
        best_index = min(range(len(validation)), key=validation.__getitem__)
        ax.scatter([epochs[best_index]], [validation[best_index]], marker="*", s=25,
                   color=VAL_COLOR, edgecolor="#343A40", linewidth=0.4, zorder=5)
        style_axis(ax, len(epochs), "Loss")
        ax.tick_params(axis="both", labelsize=7, length=2, pad=2)
        ax.xaxis.label.set_size(8)
        ax.yaxis.label.set_size(8)
        ax.xaxis.labelpad = 1.5
        ax.yaxis.labelpad = 2
        ax.margins(y=0.10)
        ax.legend(loc="upper right", frameon=False, fontsize=7, handlelength=1.8,
                  borderpad=0.1, labelspacing=0.2, handletextpad=0.5)
        if is_supervised:
            ax.ticklabel_format(axis="y", style="sci", scilimits=(-3, -3), useMathText=True)
        return save_figure(fig, output, f"fig_learning_{run['stage']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--paper-dir", type=Path, help="Also copy the two vector figures to this directory")
    args = parser.parse_args()
    root = args.project_root.resolve()
    output = args.output_dir or root / "output" / "learning_curves_20261113" / "paper"
    output.mkdir(parents=True, exist_ok=True)
    source = root / "ExperimentalRecord.txt"
    runs = read_runs(source)
    selected = {}
    for stage, expected_count in (("supervised", 50), ("ams", 8)):
        candidates = [run for run in runs if run["model"] == MODEL and run.get("stage") == stage]
        if len(candidates) != 1:
            raise ValueError(f"Expected one unambiguous {stage} run, found {len(candidates)}")
        run = candidates[0]
        if len(run["rows"]) != expected_count or "end" not in run:
            raise ValueError(f"Incomplete historical {stage} run")
        best = min(run["rows"], key=lambda row: float(row["val_loss"]))
        best_key = "best_val_selfsup_loss" if stage == "ams" else "best_val_loss"
        if best["epoch"] != run["best"]["epoch"] or best["val_loss"] != run["best"][best_key]:
            raise ValueError(f"Best-model summary does not agree with {stage} epoch records")
        selected[stage] = run
        rows = [{"model": MODEL, "stage": stage, "run_started": run["start"]["start_time"],
                 "source_file": "ExperimentalRecord.txt", **row} for row in run["rows"]]
        write_csv(output / f"historical_{stage}_metrics.csv", rows)

    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9, "axes.labelsize": 10,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "pdf.fonttype": 42,
        "ps.fonttype": 42, "svg.fonttype": "none", "axes.unicode_minus": False,
    })
    artifacts = plot_losses(selected["supervised"], selected["ams"], output)
    for run in selected.values():
        artifacts += plot_paper_panel(run, output)
    if args.paper_dir:
        args.paper_dir.mkdir(parents=True, exist_ok=True)
        for stage in selected:
            name = f"fig_learning_{stage}.pdf"
            (args.paper_dir / name).write_bytes((output / name).read_bytes())
    metadata = {
        "source": str(source), "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "model": MODEL, "smoothing": "none", "interpolation": "none; straight lines join observed epochs",
        "runs": {stage: {"start_time": run["start"]["start_time"],
                          "epoch_count": len(run["rows"]),
                          "source_line_first": run["rows"][0]["source_line"],
                          "source_line_last": run["rows"][-1]["source_line"],
                          "best_epoch": int(run["best"]["epoch"])} for stage, run in selected.items()},
        "available_series": ["train_loss", "val_loss"],
        "author_confirmation_date": "2026-11-13",
        "author_confirmation": "Use these 50-epoch supervised and 8-epoch AMS loss records for the manuscript figures.",
        "initial_learning_rates": {"supervised": 2e-4, "ams": 2e-6},
        "artifacts": artifacts,
    }
    (output / "figure_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    notes = f"""现有训练日志与学习曲线（2026-11-13）

已绘制：{MODEL} 的监督训练（50 轮）和 AMS（8 轮）。作者于 2026-11-13 确认这两份记录可直接用于论文学习曲线，并确认学习率分别为 2e-4 和 2e-6。
原始记录：{source}
监督训练：第 251-300 行，2026-05-04；AMS：第 310-317 行，2026-05-06。
两次运行逐轮记录完整，无缺轮、重复轮或非有限值；最小验证损失对应第 47 / 8 轮，与日志的 best_model 条目一致。

文件：
training_validation_loss：两个阶段各自的训练/验证损失（PNG、PDF、SVG）。
fig_learning_supervised / fig_learning_ams：论文中分别使用的两张单栏图（PNG、PDF、SVG）。
historical_supervised_metrics.csv / historical_ams_metrics.csv：逐轮损失、训练参数及来源行号。
figure_metadata.json：数据来源、SHA-256、运行标识及处理说明。

数据口径：
1. 所有图均使用日志原值，不平滑、不补点。监督训练损失包含 TV 项，验证损失为 MSE，二者不等同于同一定义的训练/验证 MSE。
2. AMS 的 val_loss / val_selfsup_loss 是真实 SAR 自监督损失。每个点对应日志中的一轮，星号标记最小验证损失。
3. 初始学习率为监督训练 2e-4、AMS 2e-6。正文实验在另一台机器上运行；图表采用作者确认的损失记录，其他设置以返修稿为准。

其他已检查记录：
- ExperimentalRecord.txt 还包含 5 个其他模型的监督记录（40-50 轮）；.tmp 是相同副本，notebook checkpoint 是较早副本。
- experiments_repro/p0_ablation/full_seed42/epoch_metrics.csv 有 45/100 轮，是 BSDS500 旧协议，未混入上述图。
- experiments_repro/nwpu_p0_ablation/full_seed42/epoch_metrics.csv 只有表头。
- experiments_smoke 中 12 份 epoch_metrics.csv 均只有 1 轮。
- 本地项目搜索未找到 step_metrics.csv、train_progress.jsonl 或 TensorBoard 事件文件。

观察：监督训练和验证损失总体下降，验证端仍有波动；AMS 训练与验证自监督损失均下降。

复现：python scripts/plot_training_learning_curves.py
绘图代码：{Path(__file__).resolve()}
"""
    (output / "README.txt").write_text(notes, encoding="utf-8")
    print(json.dumps({"output": str(output), "runs": metadata["runs"], "artifacts": artifacts}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
