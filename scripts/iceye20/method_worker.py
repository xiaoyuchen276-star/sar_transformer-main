"""One full-scene inference worker, executed only when explicitly invoked.

Each baseline runs in its existing dedicated environment. Full results are
memory mapped; patch indices never become statistical sample identifiers.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys
import time
import numpy as np

from common import ROOT, METHODS, read_json, write_json, sha256
from array_utils import blocks, view, reflected, mmap_new, starts, axis_counts


def adapter(relative):
    path = ROOT / "scripts" / relative
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("iceye20_" + path.parent.name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module; spec.loader.exec_module(module)
    return module


def load_ours(checkpoint, device, adaptation):
    import torch
    sys.path.insert(0, str(ROOT))
    from model_registry import build_model, extract_checkpoint_model_metadata
    from experiment_protocol import load_checkpoint_strict
    from numeric_domain import INTENSITY_DOMAIN
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    identity = extract_checkpoint_model_metadata(payload)
    config = payload.get("run_config", {})
    if identity.get("method") != "ours" or identity.get("variant") != "full" or config.get("numeric_domain") != INTENSITY_DOMAIN:
        raise ValueError("Requires the current full intensity_v1 paper model, not a historical amplitude checkpoint")
    if (config.get("adaptation") == "ams") != (adaptation == "ams"):
        raise ValueError("Checkpoint adaptation identity does not match requested label")
    model = build_model("ours", variant="full", numeric_domain=INTENSITY_DOMAIN, checkpoint_metadata=payload)
    load_checkpoint_strict(model, checkpoint, map_location="cpu")
    model.to(device).eval()
    return model, {"checkpoint": str(checkpoint), "sha256": sha256(checkpoint), "identity": identity,
                   "numeric_domain": INTENSITY_DOMAIN, "adaptation": adaptation}


def contextual_network(method, noisy, output, info, checkpoint, device):
    import torch
    torch.manual_seed(42); torch.set_num_threads(4)
    torch.backends.cudnn.benchmark = False; torch.backends.cudnn.deterministic = True
    torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
    device = torch.device(device)
    peak = info["intensity_peak"]
    if method in ("ours_base", "ours_ams"):
        model, provenance = load_ours(checkpoint, device, "ams" if method == "ours_ams" else "base")
        transform = lambda x: x / peak
        forward = lambda x: model(x)
        invert = lambda x: x * peak
        domain = "linear intensity / whole-scene peak; multiply output by same peak"
    elif method == "sdudnet":
        run = adapter("sdudnet/run_local.py")
        model, provenance = run.build_model("real", device)
        transform = lambda x: x / peak
        forward = lambda x: model(x)[0]
        invert = lambda x: x * peak
        domain = "linear intensity / whole-scene peak; no display or dB conversion"
    elif method == "cl_sar":
        run = adapter("cl_sar/run_local.py"); run.configure_runtime()
        model, provenance = run.build_model(device)
        amin, amax = np.sqrt(info["intensity_min_positive"]), np.sqrt(peak)
        transform = lambda x: np.abs((np.sqrt(x) - amin) / (amax - amin))
        invert = lambda x: (np.clip(x, 0, 1) * (amax - amin) + amin) ** 2
        forward = lambda x: model(x)
        domain = "official amplitude normalization using whole-scene min-positive and max"
    elif method == "transsar":
        run = adapter("transsar/run_umbra_official.py")
        repo = ROOT / "external/TransSAR_official"
        weight = ROOT / "trained_models/comparison_baselines/trans-sar/model.pth"
        if sha256(weight) != run.EXPECTED_CHECKPOINT_SHA256 or run.git_output(repo, "rev-parse", "HEAD") != run.OFFICIAL_COMMIT:
            raise ValueError("Official Trans-SAR provenance mismatch")
        model, transform_name, count = run.load_strict_model(run.import_official_model(repo), weight, device)
        provenance = {"checkpoint": str(weight), "sha256": sha256(weight), "commit": run.OFFICIAL_COMMIT,
                      "key_transform": transform_name, "state_tensors": count}
        transform = lambda x: (255 * np.sqrt(x / peak) + 1) / 256
        invert = lambda x: np.maximum((256 * x - 1) / 255, 0) ** 2 * peak
        forward = lambda x: model(x)
        domain = "official amplitude mapping with one whole-scene peak"
    else:
        raise ValueError(method)
    total = ((noisy.shape[0] + 191) // 192) * ((noisy.shape[1] + 191) // 192)
    with torch.inference_mode():
        for index, (r, c, h, w) in enumerate(blocks(noisy.shape, 192), 1):
            source = reflected(noisy, r - 32, c - 32, 256, 256).astype(np.float64)
            x = np.ascontiguousarray(transform(source), dtype=np.float32)
            y = forward(torch.from_numpy(x)[None, None].to(device))[0, 0].float().cpu().numpy()
            if y.shape != (256, 256) or not np.isfinite(y).all():
                raise ValueError(f"Invalid network output at {r},{c}")
            view(output, (r, c, h, w))[:] = invert(y[32:32 + h, 32:32 + w].astype(np.float64))
            if index == 1 or index % 200 == 0:
                output.flush(); print(f"{method}: {index}/{total} contextual patches", flush=True)
    return {"source": provenance, "input_output_transform": domain,
            "tiling": {"patch": 256, "core": 192, "halo": 32, "boundary": "reflect",
                       "assembly": "retain contextual centers", "whole_forward_equivalence_claimed": False}}


def sar2sar(noisy, output, folder):
    run = adapter("sar2sar/run_local.py")
    from official_adapter import normalize, denormalize, OUTPUT_TENSOR, NORMALIZATION
    package, provenance = run.validate_official_package()
    tf = run.tf; tf.compat.v1.disable_eager_execution()
    graph = tf.Graph(); checkpoint = package / "checkpoint/SAR2SAR-tensorflow-98550"
    with graph.as_default():
        saver = tf.compat.v1.train.import_meta_graph(str(checkpoint) + ".meta", clear_devices=True)
    config = tf.compat.v1.ConfigProto(device_count={"GPU": 0}, intra_op_parallelism_threads=4, inter_op_parallelism_threads=1)
    accumulator = mmap_new(folder / "normalized_log_sum.npy", noisy.shape, "float64")
    rows, cols = starts(noisy.shape[0]), starts(noisy.shape[1])
    wr, wc = axis_counts(noisy.shape[0], rows, 256), axis_counts(noisy.shape[1], cols, 256)
    with tf.compat.v1.Session(graph=graph, config=config) as session:
        saver.restore(session, str(checkpoint))
        inp = graph.get_tensor_by_name("noisy_image:0"); train = graph.get_tensor_by_name("is_training:0")
        out = graph.get_tensor_by_name(OUTPUT_TENSOR)
        for index, r in enumerate(rows):
            for c in cols:
                x = normalize(np.sqrt(np.asarray(noisy[r:r + 256, c:c + 256], dtype=np.float64)))
                pred = session.run(out, {inp: x[None, :, :, None], train: False})[0, :, :, 0]
                accumulator[r:r + 256, c:c + 256] += pred
            if index % 20 == 0:
                print(f"SAR2SAR row {index + 1}/{len(rows)}", flush=True)
    for box in blocks(noisy.shape):
        r, c, h, w = box
        normalized = view(accumulator, box) / (wr[r:r+h, None] * wc[None, c:c+w])
        view(output, box)[:] = denormalize(normalized) ** 2
    del accumulator; (folder / "normalized_log_sum.npy").unlink()
    return {"source": provenance, "normalization": NORMALIZATION, "patch": 256, "stride": 64,
            "assembly": "official uniform average in normalized log-amplitude domain"}


def merlin(complex_image, output, folder, device):
    import torch
    run = adapter("merlin/run_weighted_overlap.py")
    run.install_unused_gdal_import_stub()
    sys.path.insert(0, str(ROOT / "external/deepdespeckling"))
    from deepdespeckling.merlin import merlin_denoiser as official
    if sha256(run.CHECKPOINT) != "25a978b0d53b5b5307ca2ba57b6368a86493c4eeff24efe6ba58987b2e154a56":
        raise ValueError("MERLIN checkpoint mismatch")
    denoiser = official.MerlinDenoiser(model_name="spotlight", symetrise=True)
    denoiser.device = torch.device(device)
    model = denoiser.load_model(patch_size=256).to(denoiser.device).eval()
    accumulators = [mmap_new(folder / (name + ".npy"), output.shape, "float64") for name in ("real_sum", "imag_sum")]
    rows, cols = starts(output.shape[0]), starts(output.shape[1])
    wr, wc = axis_counts(output.shape[0], rows, 256), axis_counts(output.shape[1], cols, 256)
    with torch.inference_mode():
        for index, r in enumerate(rows):
            for c in cols:
                z = complex_image[r:r+256, c:c+256]
                components = official.symetrise_real_and_imaginary_parts(z.real[None, :, :, None], z.imag[None, :, :, None])
                for component, accumulator in zip(components, accumulators):
                    tensor = torch.tensor(component, dtype=torch.float32, device=denoiser.device)
                    tensor = (torch.log(tensor.square() + 1e-3) - 2 * denoiser.m) / (2 * (denoiser.M - denoiser.m))
                    accumulator[r:r+256, c:c+256] += model(tensor)[0, 0].cpu().numpy()
            if index % 20 == 0:
                print(f"MERLIN row {index + 1}/{len(rows)}", flush=True)
    for box in blocks(output.shape):
        r, c, h, w = box; weight = wr[r:r+h, None] * wc[None, c:c+w]
        ar = official.denormalize_sar_image(view(accumulators[0], box) / weight, denoiser.M, denoiser.m)
        ai = official.denormalize_sar_image(view(accumulators[1], box) / weight, denoiser.M, denoiser.m)
        view(output, box)[:] = 0.5 * (ar.astype(float) ** 2 + ai.astype(float) ** 2)
    del accumulator, accumulators
    for name in ("real_sum.npy", "imag_sum.npy"):
        (folder / name).unlink()
    return {"checkpoint": str(run.CHECKPOINT), "sha256": sha256(run.CHECKPOINT), "patch": 256,
            "stride": 64, "symmetrize": True, "assembly": "official uniform average in normalized log-power domain",
            "input": "native decoded complex SLC; no projection or fitted gain"}


def sarbm3d(noisy, output, folder, matlab):
    config = {"input": str(Path(noisy.filename).resolve()), "input_offset": noisy.offset,
              "output": str(Path(output.filename).resolve()), "output_offset": output.offset,
              "height": noisy.shape[0], "width": noisy.shape[1], "project": str(ROOT), "looks": 1,
              "core": 512, "halo": 64, "workers": 4}
    path = folder / "matlab_job.json"; write_json(path, config)
    code = "addpath('" + str(Path(__file__).parent).replace("'", "''") + "'); sarbm3d_scene('" + str(path.resolve()).replace("'", "''") + "');"
    output.flush()
    subprocess.run([matlab, "-batch", code], check=True, cwd=ROOT)
    return {"algorithm": "author SARBM3D_v10", "input_domain": "decoded amplitude sqrt(Y)",
            "looks": 1, "core": 512, "halo": 64, "assembly": "contextual centers"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--method", choices=METHODS, required=True)
    p.add_argument("--input-dir", type=Path, required=True); p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--checkpoint", type=Path); p.add_argument("--device", default="cuda")
    p.add_argument("--matlab", default="matlab")
    a = p.parse_args()
    if a.method.startswith("ours_") and (a.checkpoint is None or not a.checkpoint.is_file()):
        p.error("A current formal checkpoint must be explicitly supplied")
    if a.output_dir.exists() and any(a.output_dir.iterdir()):
        raise FileExistsError("Choose a fresh method output directory; partial runs are not treated as complete")
    a.output_dir.mkdir(parents=True, exist_ok=True)
    noisy = np.load(a.input_dir / "intensity.npy", mmap_mode="r", allow_pickle=False)
    valid = np.load(a.input_dir / "valid.npy", mmap_mode="r", allow_pickle=False)
    info = read_json(a.input_dir / "input.json")
    output = mmap_new(a.output_dir / "denoised.npy", noisy.shape)
    start = time.monotonic()
    if a.method in ("ours_base", "ours_ams", "sdudnet", "transsar", "cl_sar"):
        report = contextual_network(a.method, noisy, output, info, a.checkpoint, a.device)
    elif a.method == "sar2sar":
        report = sar2sar(noisy, output, a.output_dir)
    elif a.method == "merlin":
        report = merlin(np.load(a.input_dir / "complex.npy", mmap_mode="r"), output, a.output_dir, a.device)
    elif a.method == "sarbm3d":
        report = sarbm3d(noisy, output, a.output_dir, a.matlab)
    else:
        from mulog_stream import run
        report = run(noisy, output, info, a.output_dir, a.device)
    epsilon = 1e-6 * info["intensity_mean"]
    floored = negative = valid_count = 0
    for box in blocks(noisy.shape):
        x, mask = view(output, box), view(valid, box)
        if not np.isfinite(x).all():
            raise ValueError("Nonfinite output; method/scene fails")
        negative += int(np.sum((x < 0) & mask)); floored += int(np.sum((x < epsilon) & mask))
        valid_count += int(mask.sum())
        # One declared physical/numerical positivity projection for all methods.
        # Input masks are never narrowed in response to a method's output.
        np.maximum(x, epsilon, out=x)
    output.flush()
    report.update({"method": a.method, "scene_id": info["scene_id"], "shape": list(noisy.shape),
                   "source_sha256": info["source_sha256"], "complete": True,
                   "seconds": time.monotonic() - start, "output_sha256": sha256(a.output_dir / "denoised.npy"),
                   "positivity_projection": {"floor": epsilon, "relative_to_input_mean": 1e-6,
                      "negative_fraction_before_projection": negative / valid_count,
                      "floor_fraction": floored / valid_count}, "script_sha256": sha256(__file__)})
    write_json(a.output_dir / "run.json", report)


if __name__ == "__main__":
    main()
