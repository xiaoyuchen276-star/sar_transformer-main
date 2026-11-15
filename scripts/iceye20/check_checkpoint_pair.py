"""Verify current intensity_v1 model identities and encoder-frozen AMS pairing."""
import argparse
from pathlib import Path
import sys
import torch
from common import ROOT, sha256, write_json


def check(base_path, ams_path):
    sys.path.insert(0, str(ROOT))
    from model_registry import extract_checkpoint_model_metadata
    from numeric_domain import INTENSITY_DOMAIN
    states, reports = [], []
    for path, adaptation in ((base_path, "base"), (ams_path, "ams")):
        payload = torch.load(path, map_location="cpu", weights_only=True)
        identity = extract_checkpoint_model_metadata(payload); config = payload.get("run_config", {})
        if identity["method"] != "ours" or identity["variant"] != "full" or config.get("numeric_domain") != INTENSITY_DOMAIN:
            raise ValueError("Both checkpoints must identify the current full intensity_v1 paper model")
        if (config.get("adaptation") == "ams") != (adaptation == "ams"):
            raise ValueError("Base/AMS checkpoint identity mismatch")
        state = payload.get("state_dict", payload.get("model"))
        if not isinstance(state, dict):
            raise ValueError("Metadata-bearing state_dict/model checkpoint required")
        states.append({k.removeprefix("module."): v for k, v in state.items()})
        reports.append({"path": str(Path(path).resolve()), "sha256": sha256(path), "identity": identity,
                        "numeric_domain": INTENSITY_DOMAIN, "adaptation": adaptation})
    encoder = sorted(k for k in states[0] if k.startswith("log_branch.Tenc."))
    if not encoder or set(states[0]) != set(states[1]):
        raise ValueError("Checkpoint architectures do not match or encoder keys are missing")
    if any(not torch.equal(states[0][k], states[1][k]) for k in encoder):
        raise ValueError("Encoder state differs between base and AMS; this pair is not encoder-frozen adaptation")
    if all(torch.equal(states[0][k], states[1][k]) for k in states[0]):
        raise ValueError("Base and AMS are identical checkpoints")
    return {"base": reports[0], "ams": reports[1], "encoder_tensors_equal": len(encoder), "complete": True}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--base", type=Path, required=True); p.add_argument("--ams", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(); write_json(a.output, check(a.base, a.ams))
