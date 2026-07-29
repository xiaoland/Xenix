from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image, ImageDraw, ImageFont
from rapidocr import EngineType, RapidOCR


ASSETS = {
    "PP-OCRv6_det_small.pth": "fbdc74c97ea7b770ab22cbdc1bba01a52bdf1975efcf3442057356d622b05d54",
    "ch_ptocr_mobile_v2.0_cls_mobile.pth": (
        "bfe13860824b3365c0c7f7ccfcddc8ff11645c60051739ff18bc9913f60c98e1"
    ),
    "PP-OCRv6_rec_small.pth": "0107b2ad694ccc9b1db7cf9ed3ffbc93d1795d9e08d9cf823127243a87bce516",
    "ppocrv6_dict.txt": "b5f2bfe2bdd9448429e3e82b51c789775d9b42f2403d082b00662eb77e401c5d",
    "FZYTK.TTF": "4065a23df6823c8e2b69a0e76d02f02a6470b8774a5e91086609701ad95cc33f",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_assets(root: Path) -> dict[str, dict[str, Any]]:
    evidence: dict[str, dict[str, Any]] = {}
    for name, expected_sha256 in ASSETS.items():
        path = root / name
        assert path.is_file(), path
        actual_sha256 = _sha256(path)
        assert actual_sha256 == expected_sha256, (name, expected_sha256, actual_sha256)
        evidence[name] = {
            "bytes": path.stat().st_size,
            "sha256": actual_sha256,
        }
    return evidence


def _make_fixture(path: Path, font_path: Path) -> list[str]:
    lines = [
        "AMD Radeon GPU 文档识别",
        "ROCm 7.2.1 私有部署",
        "Invoice No. XENIX-2026",
    ]
    image = Image.new("RGB", (1500, 500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(str(font_path), 76)
    for index, line in enumerate(lines):
        draw.text((55, 45 + index * 140), line, fill="black", font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")
    return lines


def _stage_sessions(engine: RapidOCR) -> dict[str, Any]:
    return {
        "det": engine.text_det.session,
        "cls": engine.text_cls.session,
        "rec": engine.text_rec.session,
    }


def _normalized_output(result: Any) -> dict[str, Any]:
    assert result.boxes is not None
    assert result.txts is not None
    assert result.scores is not None
    boxes = np.asarray(result.boxes)
    scores = np.asarray(result.scores)
    assert boxes.ndim == 3 and boxes.shape[1:] == (4, 2), boxes.shape
    assert len(boxes) == len(result.txts) == len(scores)
    assert np.isfinite(boxes).all()
    assert np.isfinite(scores).all()
    assert ((0.0 <= scores) & (scores <= 1.0)).all()
    return {
        "boxes": boxes.tolist(),
        "texts": list(result.txts),
        "scores": scores.tolist(),
        "elapsed_seconds": result.elapse,
        "stage_elapsed_seconds": result.elapse_list,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-root",
        type=Path,
        default=Path("/opt/xenix-rocm-lab/models/rapidocr-3.9.2"),
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("/workspace/xenix-rocm-lab/evidence/rapidocr-fixture.png"),
    )
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    assert args.runs >= 2

    forbidden = {
        name: importlib.util.find_spec(name) is not None
        for name in ("onnxruntime", "paddle", "openvino", "tensorrt")
    }
    assert not any(forbidden.values()), forbidden
    assert torch.cuda.is_available()
    assert torch.version.hip
    assert torch.cuda.device_count() == 1
    device_name = torch.cuda.get_device_name(0)
    capability = torch.cuda.get_device_capability(0)
    assert capability == (11, 0), capability

    assets = _validate_assets(args.model_root)
    source_lines = _make_fixture(args.fixture, args.model_root / "FZYTK.TTF")

    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats(0)
    init_started = time.perf_counter()
    engine = RapidOCR(
        params={
            "Global.model_root_dir": str(args.model_root),
            "Global.font_path": str(args.model_root / "FZYTK.TTF"),
            "EngineConfig.torch.use_cuda": True,
            "EngineConfig.torch.cuda_ep_cfg.device_id": 0,
            "Det.engine_type": EngineType.TORCH,
            "Det.model_path": str(args.model_root / "PP-OCRv6_det_small.pth"),
            "Cls.engine_type": EngineType.TORCH,
            "Cls.model_path": str(args.model_root / "ch_ptocr_mobile_v2.0_cls_mobile.pth"),
            "Rec.engine_type": EngineType.TORCH,
            "Rec.model_path": str(args.model_root / "PP-OCRv6_rec_small.pth"),
            "Rec.rec_keys_path": str(args.model_root / "ppocrv6_dict.txt"),
        }
    )
    torch.cuda.synchronize()
    init_seconds = time.perf_counter() - init_started

    stage_sessions = _stage_sessions(engine)
    stage_devices: dict[str, dict[str, str]] = {}
    observed_input_devices: dict[str, list[str]] = {name: [] for name in stage_sessions}
    hook_handles = []
    for stage, session in stage_sessions.items():
        assert session.device.type == "cuda", (stage, session.device)
        parameter_device = next(session.predictor.parameters()).device
        assert parameter_device.type == "cuda", (stage, parameter_device)
        stage_devices[stage] = {
            "session": str(session.device),
            "parameters": str(parameter_device),
        }

        def record_input(
            _module: torch.nn.Module,
            inputs: tuple[Any, ...],
            *,
            stage_name: str = stage,
        ) -> None:
            tensors = [value for value in inputs if isinstance(value, torch.Tensor)]
            assert tensors
            devices = [str(tensor.device) for tensor in tensors]
            assert all(tensor.device.type == "cuda" for tensor in tensors), devices
            observed_input_devices[stage_name].extend(devices)

        hook_handles.append(session.predictor.register_forward_pre_hook(record_input))

    runs = []
    wall_seconds = []
    for _ in range(args.runs):
        torch.cuda.synchronize()
        started = time.perf_counter()
        result = engine(args.fixture)
        torch.cuda.synchronize()
        wall_seconds.append(time.perf_counter() - started)
        runs.append(_normalized_output(result))
    for handle in hook_handles:
        handle.remove()

    assert all(observed_input_devices.values()), observed_input_devices
    first = runs[0]
    for repeated in runs[1:]:
        assert repeated["texts"] == first["texts"]
        assert np.allclose(repeated["boxes"], first["boxes"], rtol=0.0, atol=1e-5)
        assert np.allclose(repeated["scores"], first["scores"], rtol=0.0, atol=1e-6)

    recognized = "\n".join(first["texts"])
    normalized_recognized = recognized.casefold().replace(" ", "")
    for anchor in ("amd", "radeon", "rocm", "xenix", "2026"):
        assert anchor in normalized_recognized, (anchor, recognized)
    chinese_hits = [
        token for token in ("文档", "识别", "私有", "部署") if token in recognized
    ]
    assert chinese_hits, recognized

    allocated_bytes = torch.cuda.memory_allocated(0)
    peak_allocated_bytes = torch.cuda.max_memory_allocated(0)
    assert allocated_bytes > 0
    assert peak_allocated_bytes >= allocated_bytes
    assert all(math.isfinite(value) and value > 0 for value in wall_seconds)

    evidence = {
        "runtime": {
            "rapidocr": importlib.metadata.version("rapidocr"),
            "torch": torch.__version__,
            "torch_hip": torch.version.hip,
            "device_name": device_name,
            "device_capability": capability,
            "forbidden_runtimes_present": forbidden,
        },
        "assets": assets,
        "fixture": {
            "path": str(args.fixture),
            "source_lines": source_lines,
            "sha256": _sha256(args.fixture),
        },
        "execution": {
            "engine_types": {
                stage: getattr(engine.cfg, stage.capitalize()).engine_type.value
                for stage in stage_sessions
            },
            "stage_devices": stage_devices,
            "observed_input_devices": observed_input_devices,
            "init_seconds": init_seconds,
            "wall_seconds": wall_seconds,
            "allocated_bytes": allocated_bytes,
            "peak_allocated_bytes": peak_allocated_bytes,
        },
        "output": first,
        "recognized_text": recognized,
        "chinese_anchor_hits": chinese_hits,
    }
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
