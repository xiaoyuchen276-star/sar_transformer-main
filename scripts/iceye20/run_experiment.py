"""Run the frozen twenty-scene benchmark. NOT executed during data preparation.

Explicit current Ours checkpoint paths are required. Completed methods resume
only under an identical data/config/source binding. Full predictions are
temporary by default: metrics, full previews, ratio previews, and Table V
arrays are retained. --keep-full retains all 180 full predictions instead.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import numpy as np
from common import ROOT, DATA, METHODS, manifest, read_json, write_json, sha256

ENVIRONMENTS = {"sarbm3d": ".venv-iceye20", "sar2sar": ".venv-sar2sar",
                "sdudnet": ".venv-sdudnet", "transsar": ".venv-ours-legacy", "cl_sar": ".venv-cl-sar",
                "merlin": ".venv-merlin", "mulog_drunet": ".venv-mulog-drunet",
                "ours_base": ".venv-ours-legacy", "ours_ams": ".venv-ours-legacy"}


def python_for(method):
    path = ROOT / ENVIRONMENTS[method] / "Scripts/python.exe"
    if not path.is_file():
        raise FileNotFoundError(path)
    return path


def bound_file(root, relative, expected):
    path = root / relative
    if not path.is_file() or sha256(path) != expected:
        raise ValueError(f"Frozen data changed: {path}")


def remove_work_arrays(folder, allowed_root):
    folder, allowed_root = folder.resolve(), allowed_root.resolve()
    if folder == allowed_root or not folder.is_relative_to(allowed_root):
        raise ValueError("Refusing cleanup outside this experiment's dedicated work directory")
    # Only arrays created by this runner are removed; no recursive directory deletion.
    for filename in ("intensity.npy", "complex.npy", "valid.npy", "denoised.npy"):
        path = folder / filename
        if path.exists():
            path.unlink()
    if (folder / "input.json").exists():
        (folder / "input.json").unlink()


def archive_incomplete(folder, work, enabled):
    if not folder.exists() or not any(folder.iterdir()):
        return
    if not enabled:
        raise RuntimeError(f"Partial work remains at {folder}; use --retry-incomplete to archive it before rerunning")
    archived = folder.with_name(folder.name + "_incomplete_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
    if folder.resolve() == work or not folder.resolve().is_relative_to(work) or not archived.resolve().is_relative_to(work):
        raise ValueError("Refusing to move an incomplete directory outside the dedicated work root")
    folder.rename(archived)


def method_complete(result, keep_full):
    marker = result / "method_complete.json"
    if not marker.exists():
        return False
    record = read_json(marker)
    if not record.get("complete") or record["keep_full"] != keep_full:
        return False
    for name in ("evaluation.json", "inference.json", "table_iv.json", "table_v.json"):
        if not (result / name).is_file():
            raise FileNotFoundError(result / name)
    if keep_full:
        archive = read_json(result / "full_prediction.json")
        path = Path(archive["path"])
        if not path.is_file() or path.stat().st_size != archive["bytes"]:
            raise ValueError(f"Completed full prediction archive is missing or truncated: {path}")
    return True


def finalize_method(scratch, result, work, full_root, sid, method):
    """Commit a method only after evaluation and prediction retention finish."""
    evaluation = read_json(result / "evaluation.json")
    receipt = result / "inference.json"
    run = read_json(receipt if receipt.exists() else scratch / "run.json")
    if (not evaluation.get("complete") or run["method"] != method or run["scene_id"] != sid
            or run["source_sha256"] != evaluation["source_sha256"]
            or run["output_sha256"] != evaluation["prediction_sha256"]):
        raise ValueError("Evaluation and inference receipts disagree")
    write_json(receipt, run)
    source = scratch / "denoised.npy"
    if full_root is not None:
        target = full_root / sid / method / "denoised.npy"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            if not source.is_file() or sha256(source) != run["output_sha256"]:
                raise ValueError("Cannot archive a missing or changed full prediction")
            if source.anchor.lower() == target.anchor.lower():
                source.rename(target)
            else:
                # A failed cross-volume copy cannot masquerade as a completed archive.
                partial = target.with_suffix(".npy.partial")
                shutil.copyfile(source, partial)
                if sha256(partial) != run["output_sha256"]:
                    raise ValueError("Full prediction copy failed its SHA-256 check")
                partial.rename(target)
        if sha256(target) != run["output_sha256"]:
            raise ValueError("Archived prediction no longer matches its inference receipt")
        write_json(result / "full_prediction.json", {"path": str(target), "sha256": run["output_sha256"],
                                                     "bytes": target.stat().st_size})
    remove_work_arrays(scratch, work)
    write_json(result / "method_complete.json", {"complete": True, "keep_full": full_root is not None,
               "prediction_sha256": run["output_sha256"], "finished_utc": datetime.now(timezone.utc).isoformat()})
    if (result / "failure.json").exists():
        (result / "failure.json").unlink()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--root", type=Path, default=DATA)
    p.add_argument("--results", type=Path, default=ROOT / "output/iceye20")
    p.add_argument("--work-root", type=Path)
    p.add_argument("--base-checkpoint", type=Path, required=True)
    p.add_argument("--ams-checkpoint", type=Path, required=True)
    p.add_argument("--device", default="cuda")
    p.add_argument("--matlab", default="matlab")
    p.add_argument("--keep-full", action="store_true")
    p.add_argument("--retry-incomplete", action="store_true", help="Move an incomplete method work directory aside before rerunning it")
    p.add_argument("--full-output-root", type=Path, help="Required with --keep-full; needs space for all full-scene arrays")
    a = p.parse_args(); a.root = a.root.resolve(); a.results = a.results.resolve()
    if a.keep_full != (a.full_output_root is not None):
        p.error("Use --keep-full and --full-output-root together")
    if a.full_output_root is not None:
        a.full_output_root = a.full_output_root.resolve()
    seal = read_json(a.root / "dataset_seal.json")
    bound_file(a.root, "manifest.json", seal["manifest_sha256"])
    bound_file(a.root, "regions_manifest.json", seal["regions_manifest_sha256"])
    bound_file(a.root, "review_notes.json", seal["review_notes_sha256"])
    if not seal.get("data_audit_complete") or seal["raw_scene_count"] != 20 or seal["table_v_regions"] != 60:
        raise ValueError("The complete twenty-scene data preparation must finish first")
    m = manifest(a.root)
    work = (a.work_root or Path(m["raw_root"]).parent / "work").resolve()
    work.mkdir(parents=True, exist_ok=True); a.results.mkdir(parents=True, exist_ok=True)
    for method in METHODS:
        python_for(method)
    if not shutil.which(a.matlab) and not Path(a.matlab).is_file():
        raise FileNotFoundError("MATLAB is required for the official SAR-BM3D binary")
    for path in (a.base_checkpoint, a.ams_checkpoint):
        if not path.is_file():
            raise FileNotFoundError(path)
    scripts = Path(__file__).parent
    source_files = [scripts / name for name in ("run_experiment.py", "method_worker.py", "mulog_stream.py", "metrics.py",
                    "evaluate_output.py", "summarize.py", "prepare_arrays.py", "slc.py", "array_utils.py", "sarbm3d_scene.m",
                    "check_checkpoint_pair.py", "common.py", "render_comparison.py")]
    source_files += [ROOT / name for name in ("classic_sar_metrics.py", "scripts/iceye_paris/rgpi_metric.py",
                    "transform_main.py", "numeric_domain.py", "model_registry.py", "ablation_config.py", "experiment_protocol.py")]
    source_files += sorted((ROOT / "arch").rglob("*.py"))
    for name in ("sar2sar", "sdudnet", "transsar", "cl_sar", "merlin", "mulog_drunet"):
        source_files += sorted((ROOT / "scripts" / name).glob("*.py"))
    config = {"protocol": m["protocol"], "dataset_seal_sha256": sha256(a.root / "dataset_seal.json"),
              "base_checkpoint": str(a.base_checkpoint.resolve()), "base_sha256": sha256(a.base_checkpoint),
              "ams_checkpoint": str(a.ams_checkpoint.resolve()), "ams_sha256": sha256(a.ams_checkpoint),
              "methods": METHODS, "device": a.device, "matlab": str(Path(shutil.which(a.matlab) or a.matlab).resolve()),
              "work_root": str(work), "keep_full": a.keep_full,
              "full_output_root": str(a.full_output_root.resolve()) if a.full_output_root else None,
              "source_sha256": {str(path.relative_to(ROOT)): sha256(path) for path in source_files},
              "summary": "means only; no SD/CI", "table_ii": "unchanged"}
    config_path = a.results / "run_config.json"
    if config_path.exists() and read_json(config_path) != config:
        raise ValueError("Existing results use different data, code, or weights. Choose a new --results directory")
    work_config_path = work / "run_config.json"
    if work_config_path.exists() and read_json(work_config_path) != config:
        raise ValueError("Existing work files use different data, code, or weights. Choose a new --work-root directory")
    if not work_config_path.exists() and any(work.iterdir()):
        raise ValueError("A nonempty work directory without a matching run_config.json cannot be reused")
    subprocess.run([str(python_for("ours_base")), str(scripts / "check_checkpoint_pair.py"),
                    "--base", str(a.base_checkpoint.resolve()), "--ams", str(a.ams_checkpoint.resolve()),
                    "--output", str(a.results / "checkpoint_pair.json")], check=True, cwd=ROOT)
    write_json(config_path, config)
    write_json(work_config_path, config)
    pixels = [int(np.prod(x["shape"])) for x in m["scenes"]]
    # Worst-case streaming MuLoG: inputs 13 B/pixel, output 4, and seven
    # float64 global state/partition buffers (56). Process one method at a time.
    required_work = max(pixels) * 73 + 5 * 10**9
    if a.keep_full:
        a.full_output_root.mkdir(parents=True, exist_ok=True)
        required = sum(n * 4 for scene, n in zip(m["scenes"], pixels) for method in METHODS
                       if not (a.full_output_root / scene["scene_id"] / method / "denoised.npy").exists())
        if a.full_output_root.anchor.lower() == work.anchor.lower():
            required += required_work
        if shutil.disk_usage(a.full_output_root).free < required:
            raise RuntimeError(f"Full prediction archive needs approximately {required / 1e9:.1f} GB free on its volume")
    from prepare_arrays import prepare
    from evaluate_output import evaluate_one
    from summarize import summarize
    from render_comparison import render_scene
    failures = []
    for scene in m["scenes"]:
        sid = scene["scene_id"]
        paths = [a.results / "scenes" / sid / method for method in ["noisy", *METHODS]]
        input_dir = work / sid / "input"
        if ((paths[0] / "evaluation.json").exists()
                and all(method_complete(path, a.keep_full) for path in paths[1:])):
            render_scene(a.results, sid)
            remove_work_arrays(input_dir, work)
            continue
        if not (input_dir / "input.json").exists():
            archive_incomplete(input_dir, work, a.retry_incomplete)
        cached_input_bytes = sum(path.stat().st_size for path in input_dir.glob("*.npy"))
        pending = [method for method, path in zip(METHODS, paths[1:])
                   if not method_complete(path, a.keep_full)]
        # Account for reusable decoded inputs on a resumed scene. A partial
        # inference directory is preserved, so its bytes are not credited here.
        bytes_per_pixel = 73 if "mulog_drunet" in pending else 33 if "merlin" in pending else 25
        needed = max(0, int(np.prod(scene["shape"])) * bytes_per_pixel - cached_input_bytes) + 5 * 10**9
        if shutil.disk_usage(work).free < needed:
            raise RuntimeError(f"Scene {sid} needs about {needed / 1e9:.1f} GB additional free working space")
        prepare(scene, input_dir, a.root)
        noisy_output = a.results / "scenes" / sid / "noisy"
        if not (noisy_output / "evaluation.json").exists():
            evaluate_one(a.root, input_dir, None, noisy_output, "noisy")
        for method in METHODS:
            result = a.results / "scenes" / sid / method
            scratch = work / sid / method
            if method_complete(result, a.keep_full):
                remove_work_arrays(scratch, work)
                continue
            try:
                # The process may have stopped after evaluation but before
                # prediction archiving/cleanup. Resume that commit directly.
                if (result / "evaluation.json").exists():
                    finalize_method(scratch, result, work, a.full_output_root, sid, method)
                    continue
                # Finished inference can resume evaluation after interruption.
                if not (scratch / "run.json").exists():
                    archive_incomplete(scratch, work, a.retry_incomplete)
                    command = [str(python_for(method)), str(scripts / "method_worker.py"), "--method", method,
                               "--input-dir", str(input_dir), "--output-dir", str(scratch), "--device", a.device,
                               "--matlab", a.matlab]
                    if method in ("ours_base", "ours_ams"):
                        command += ["--checkpoint", str((a.base_checkpoint if method == "ours_base" else a.ams_checkpoint).resolve())]
                    subprocess.run(command, check=True, cwd=ROOT)
                run = read_json(scratch / "run.json")
                if run["source_sha256"] != read_json(input_dir / "input.json")["source_sha256"] or run["method"] != method:
                    raise ValueError("Inference receipt does not match the current scene/method")
                if sha256(scratch / "denoised.npy") != run["output_sha256"]:
                    raise ValueError("Prediction contents no longer match the inference receipt")
                evaluate_one(a.root, input_dir, scratch / "denoised.npy", result, method)
                finalize_method(scratch, result, work, a.full_output_root, sid, method)
            except (subprocess.CalledProcessError, ValueError, RuntimeError, OSError) as exc:
                failure = {"scene_id": sid, "method": method, "error_type": type(exc).__name__, "message": str(exc)}
                failures.append(failure); write_json(result / "failure.json", failure)
                summarize(a.results, a.root)
                render_scene(a.results, sid)
                write_json(a.results / "completion.json", {"complete": False, "failures_this_invocation": failures,
                           "finished_utc": datetime.now(timezone.utc).isoformat(),
                           "status": "stopped at the first incomplete method; completed results retained"})
                raise SystemExit(f"Stopped at {sid}/{method}: {exc}") from exc
        summarize(a.results, a.root)
        render_scene(a.results, sid)
        if all(method_complete(path, a.keep_full) for path in paths[1:]):
            remove_work_arrays(input_dir, work)
    summarize(a.results, a.root)
    summary = read_json(a.results / "summary.json")
    complete = not summary["missing_runs"] and all(method_complete(a.results / "scenes" / scene["scene_id"] / method, a.keep_full)
                                                  for scene in m["scenes"] for method in METHODS)
    write_json(a.results / "completion.json", {"complete": complete, "failures_this_invocation": failures,
               "finished_utc": datetime.now(timezone.utc).isoformat(), "inference_executed": True,
               "mean_only_tables": str(a.results / "TABLE_IV_TABLE_V.md")})


if __name__ == "__main__":
    main()
