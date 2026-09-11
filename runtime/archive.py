"""Versioned local artifacts: JSON and numeric NPY, never pickle or executable code."""

from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import uuid

from .artifacts import PlanArtifact, SemanticArtifact, LatentArtifact
from .._vendor.yue2.protocol import SongRequest, GenerationConfig, CODEC_SIZE, VOCAB_SIZE, EOD


PLAN_FILES = {"plan.json", "score.abc", "prompt.json", "workflow.json"}
RUN_FILES = PLAN_FILES | {"semantic.json", "latents.npy", "latent_info.json", "audio.npy", "run_info.json"}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")


def plan_identity(plan):
    return hashlib.sha256(canonical({"value": asdict(plan.value), "info": plan.info})).hexdigest()


def root(folders, location):
    host = Path(folders.get_output_directory() if location == "output" else folders.get_input_directory()).resolve()
    target = (host / "yue2").resolve()
    if not target.is_relative_to(host):
        raise ValueError("YuE2 artifact folder must stay inside the ComfyUI input/output directory")
    return target


def resolve(folders, name):
    if not isinstance(name, str):
        raise ValueError("Select a YuE2 artifact folder")
    location, separator, leaf = name.partition("/")
    if location not in {"input", "output"} or not separator or not re.fullmatch(r"[\w .-]+", leaf) or leaf in {".", ".."}:
        raise ValueError("Artifact must be input/name or output/name without traversal")
    base = root(folders, location)
    target = (base / leaf).resolve()
    if not target.is_relative_to(base) or target == base:
        raise ValueError("Artifact is outside its configured folder")
    return target


def list_archives(folders, kind):
    names = []
    for location in ("input", "output"):
        base = root(folders, location)
        if not base.is_dir():
            continue
        for child in base.iterdir():
            if child.name.startswith(".") or not child.is_dir():
                continue
            try:
                directory = resolve(folders, f"{location}/{child.name}")
                file = directory / "manifest.json"
                if file.is_symlink() or file.stat().st_size > 65536:
                    continue
                manifest = json.loads(file.read_text(encoding="utf-8"))
                if isinstance(manifest, dict) and manifest.get("version") == 1 and manifest.get("kind") in ({"plan", "run"} if kind == "plan" else {"run"}):
                    names.append(f"{location}/{child.name}")
            except (OSError, ValueError):
                continue
    return sorted(names)


def fingerprint(folders, name):
    directory = resolve(folders, name)
    return tuple((p.name, p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ctime_ns)
                 for p in sorted(directory.iterdir()) if p.is_file())


def _info(value, stages, request):
    if value.get("version") != 1 or value.get("request") != request.to_dict():
        raise ValueError("Artifact request/provenance mismatch")
    if [s["stage"] for s in value["stages"]] != stages:
        raise ValueError("Artifact stage history is incomplete or out of order")
    for stage in value["stages"]:
        provenance = stage["provenance"]
        GenerationConfig.from_dict(provenance["config"]["generation"])
        if not provenance["weights"]["mot"] or not provenance["weights"]["vae"] or not provenance["tokenizer_sha256"]:
            raise ValueError("Artifact lacks model/tokenizer identity")
    return value


def _plan(document, score):
    from .._vendor.yue2.pipeline import SymbolicPlan

    value = document["value"]
    request = SongRequest(**value["request"])
    if value["abc"] is not None and not isinstance(value["abc"], str):
        raise ValueError("Invalid ABC text")
    if (value["abc"] or "") != score:
        raise ValueError("Score text disagrees with saved plan; apply edits with YuE2 Apply Edited Score")
    for name, bound in (("abc_ids", EOD), ("prefix", VOCAB_SIZE)):
        tokens = value[name]
        if not isinstance(tokens, list) or len(tokens) > 24576 or any(type(t) is not int or not 0 <= t < bound for t in tokens):
            raise ValueError("Invalid saved plan tokens")
    if not value["prefix"] or type(value["truncated"]) is not bool:
        raise ValueError("Invalid saved plan")
    plan = SymbolicPlan(request, value["abc"], value["abc_ids"], value["prefix"], value["timing"], value["truncated"])
    info = _info(document["info"], ["plan"], request)
    if info["truncated"] != {"abc": plan.truncated}:
        raise ValueError("Saved plan truncation metadata disagrees")
    return PlanArtifact(plan, info)


def _read(folders, name):
    directory = resolve(folders, name)
    manifest_path = directory / "manifest.json"
    if manifest_path.is_symlink() or manifest_path.stat().st_size > 65536:
        raise ValueError("Invalid artifact manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("version") != 1 or manifest.get("kind") not in {"plan", "run"}:
        raise ValueError("Unsupported YuE2 artifact version or kind")
    expected = PLAN_FILES if manifest["kind"] == "plan" else RUN_FILES
    if not isinstance(manifest.get("files"), dict) or set(manifest["files"]) != expected:
        raise ValueError("Artifact manifest has missing or unexpected files")
    for filename in expected:
        file = directory / filename
        if file.is_symlink() or not file.is_file() or file.resolve().parent != directory:
            raise ValueError(f"Invalid artifact file: {filename}")
        limit = 512 * 1024 * 1024 if file.suffix == ".npy" else 32 * 1024 * 1024
        if file.stat().st_size > limit or digest(file) != manifest["files"][filename]:
            raise ValueError(f"Artifact integrity failed: {filename}; use an editing node for score changes")
    return directory, manifest["kind"]


def _json(directory, name):
    return json.loads((directory / name).read_text(encoding="utf-8"))


def load_plan(folders, name):
    directory, _ = _read(folders, name)
    return _plan(_json(directory, "plan.json"), (directory / "score.abc").read_bytes().decode("utf-8"))


def load_run(folders, name):
    import numpy as np
    import torch
    from .._vendor.yue2.pipeline import SemanticResult

    directory, kind = _read(folders, name)
    if kind != "run":
        raise ValueError("Select a saved run, not a plan")
    plan = _plan(_json(directory, "plan.json"), (directory / "score.abc").read_bytes().decode("utf-8"))
    data = _json(directory, "semantic.json")
    tokens = data["tokens"]
    if not isinstance(tokens, list) or not 1 <= len(tokens) <= 24576 or any(type(t) is not int or not 0 <= t < CODEC_SIZE for t in tokens):
        raise ValueError("Invalid semantic tokens")
    if type(data["truncated"]) is not bool:
        raise ValueError("Invalid semantic truncation state")
    request = plan.value.request
    semantic = SemanticArtifact(SemanticResult(plan.value, tokens, data["timing"], data["truncated"]),
                                _info(data["info"], ["plan", "semantic"], request))
    from contextlib import ExitStack

    # Explicitly close mappings on failure so Windows can remove incomplete saves.
    with ExitStack() as cleanup:
        z = np.load(directory / "latents.npy", allow_pickle=False, mmap_mode="r")
        cleanup.callback(z._mmap.close)
        a = np.load(directory / "audio.npy", allow_pickle=False, mmap_mode="r")
        cleanup.callback(a._mmap.close)
        if z.dtype != np.float32 or z.shape != (len(tokens), 64) or not np.isfinite(z).all():
            raise ValueError("Invalid saved latents")
        if a.dtype != np.float32 or a.shape != (len(tokens) * 1920 - 64, 2) or not np.isfinite(a).all():
            raise ValueError("Invalid saved stereo audio")
        latent = LatentArtifact(z.copy(), semantic, _info(_json(directory, "latent_info.json"), ["plan", "semantic", "synthesize"], request))
        info = _info(_json(directory, "run_info.json"), ["plan", "semantic", "synthesize", "decode"], request)
        _history(plan, semantic, latent, info)
        return plan, semantic, latent, {"waveform": torch.from_numpy(a.copy().T).unsqueeze(0), "sample_rate": 48000}, info



def _history(plan, semantic, latent, info):
    for previous, current in ((plan.info, semantic.info), (semantic.info, latent.info), (latent.info, info)):
        if current["stages"][:-1] != previous["stages"]:
            raise ValueError("Saved stage histories do not share the same source")
        if any(current["truncated"].get(key) != value for key, value in previous["truncated"].items()):
            raise ValueError("Saved truncation state changed between stages")
    if info["truncated"] != {"abc": plan.value.truncated, "semantic": semantic.value.truncated}:
        raise ValueError("Saved truncation metadata disagrees with tokens")


def save(folders, prefix, plan=None, *, latents=None, audio=None, run_info=None, prompt=None, workflow=None):
    import numpy as np

    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", prefix):
        raise ValueError("Artifact name must be 1–80 letters, digits, underscores or hyphens")
    kind = "run" if latents is not None else "plan"
    if kind == "run":
        semantic = latents.semantic
        plan_info = deepcopy(semantic.info)
        plan_info["stages"] = plan_info["stages"][:1]
        plan_info["truncated"] = {"abc": semantic.value.plan.truncated}
        plan = PlanArtifact(semantic.value.plan, plan_info)
        _history(plan, semantic, latents, run_info)
        if audio["sample_rate"] != 48000 or tuple(audio["waveform"].shape[:2]) != (1, 2) or audio["waveform"].ndim != 3:
            raise ValueError("Save Run needs YuE2 stereo AUDIO at 48 kHz")
    base = root(folders, "output")
    base.mkdir(parents=True, exist_ok=True)
    name = prefix + "-" + uuid.uuid4().hex
    destination = base / name
    temporary = base / (".partial-" + name)
    temporary.mkdir()
    try:
        saved_prompt = None if prompt is None else {
            node_id: {key: value for key, value in node.items() if key != "is_changed"}
            for node_id, node in prompt.items()}
        documents = {"plan.json": {"value": asdict(plan.value), "info": plan.info},
                     "prompt.json": saved_prompt, "workflow.json": workflow}
        if kind == "run":
            documents.update({"semantic.json": {"tokens": semantic.value.tokens, "timing": semantic.value.timing,
                              "truncated": semantic.value.truncated, "info": semantic.info},
                              "latent_info.json": latents.info, "run_info.json": run_info})
            np.save(temporary / "latents.npy", latents.value, allow_pickle=False)
            np.save(temporary / "audio.npy", audio["waveform"].detach().cpu().numpy()[0].T, allow_pickle=False)
        for filename, document in documents.items():
            (temporary / filename).write_bytes(canonical(document))
        (temporary / "score.abc").write_bytes((plan.value.abc or "").encode("utf-8"))
        files = PLAN_FILES if kind == "plan" else RUN_FILES
        (temporary / "manifest.json").write_bytes(canonical({"version": 1, "kind": kind,
            "files": {filename: digest(temporary / filename) for filename in sorted(files)}}))
        # Validate the same representation the importer will consume before publication.
        temp_name = "output/" + temporary.name
        load_run(folders, temp_name) if kind == "run" else load_plan(folders, temp_name)
        temporary.rename(destination)
    finally:
        if temporary.exists():
            for file in temporary.iterdir():
                file.unlink()
            temporary.rmdir()
    return "output/" + name
