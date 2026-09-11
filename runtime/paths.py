"""Resolve checkpoint directories only within configured model roots."""

import json
from pathlib import Path, PureWindowsPath


KINDS = {"yue2": "yue2", "yue2_vae": "yue2_vae"}


def validate_checkpoint(directory, kind):
    expected = KINDS[kind]
    directory = Path(directory).resolve()
    config = directory / "config.json"
    required = [config]
    if kind == "yue2":
        required.append(directory / "qwen.tiktoken")
    index = directory / "model.safetensors.index.json"
    if index.is_file():
        data = json.loads(index.read_text(encoding="utf-8"))
        shards = set(data["weight_map"].values())
        if not shards:
            raise ValueError(f"Empty checkpoint index: {index}")
        for name in shards:
            if ":" in name or Path(name).name != name or PureWindowsPath(name).name != name or not name.endswith(".safetensors"):
                raise ValueError("Checkpoint index contains an invalid shard path")
        required.extend(directory / name for name in shards)
        required.append(index)
    else:
        required.append(directory / "model.safetensors")
    for file in required:
        if not file.is_file():
            raise FileNotFoundError(f"Missing YuE2 checkpoint file: {file}")
        if file.suffix in {".safetensors", ".tiktoken"}:
            with file.open("rb") as stream:
                if stream.read(80).startswith(b"version https://git-lfs.github.com/spec/v1"):
                    raise ValueError(f"Git LFS pointer instead of model data: {file}. Download the actual file from the model repository")
    if json.loads(config.read_text(encoding="utf-8")).get("model_type") != expected:
        raise ValueError(f"Expected {expected} model_type in {config}")
    return directory


class ModelPaths:
    def __init__(self, folder_paths):
        self.folders = folder_paths
        for kind in KINDS:
            folder_paths.add_model_folder_path(kind, str(Path(folder_paths.models_dir) / kind))

    def list(self, kind):
        names = set()
        for base in self.folders.get_folder_paths(kind):
            root = Path(base).resolve()
            if not root.is_dir():
                continue
            for config in root.rglob("config.json"):
                directory = config.parent.resolve()
                if not directory.is_relative_to(root):
                    continue
                try:
                    validate_checkpoint(directory, kind)
                except (OSError, ValueError, KeyError, TypeError):
                    continue
                names.add(root.name if directory == root else directory.relative_to(root).as_posix())
        return sorted(names)

    def resolve(self, kind, name):
        if not isinstance(name, str) or not name or PureWindowsPath(name).drive or Path(name).is_absolute():
            raise ValueError("Select a relative YuE2 checkpoint directory")
        if ".." in name.replace("\\", "/").split("/"):
            raise ValueError("YuE2 model paths cannot contain '..'")
        for base in self.folders.get_folder_paths(kind):
            root = Path(base).resolve()
            if name == root.name and (root / "config.json").is_file():
                return validate_checkpoint(root, kind)
            directory = (root / name).resolve()
            if not directory.is_relative_to(root):
                raise ValueError("YuE2 checkpoint is outside its configured model root")
            if directory.is_dir():
                return validate_checkpoint(directory, kind)
        roots = ", ".join(self.folders.get_folder_paths(kind))
        raise FileNotFoundError(f"YuE2 model {name!r} not found. Place its checkpoint under {roots}, or configure extra_model_paths.yaml")
