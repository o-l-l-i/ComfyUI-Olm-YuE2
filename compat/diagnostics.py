"""Read installed distributions without importing models or initializing CUDA."""

from importlib import metadata
import json
import platform
import sys


PACKAGES = ("torch", "transformers", "huggingface-hub", "safetensors",
            "tiktoken", "numpy", "accelerate", "soundfile")


def diagnose():
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = None
    return {
        "python": platform.python_version(),
        "executable": sys.executable,
        "platform": platform.platform(),
        "packages": versions,
        "missing_runtime": [n for n in PACKAGES if n != "soundfile" and versions[n] is None],
        "missing_optional": [n for n in ("soundfile",) if versions[n] is None],
        "validation": "Version inventory only; run CPU smoke tests and checkpoint validation separately.",
    }


if __name__ == "__main__":
    print(json.dumps(diagnose(), indent=2))
