# Bundled YuE2 source

Source: [YuE2](https://github.com/multimodal-art-projection/YuE), revision
`92a73cc7652fcc1f937855e4b765e0a0edd7ff2e`.

Local modifications:

- `yue2/pipeline.py`: hooks for ComfyUI model placement and synthesis offloading;
  opt-out from the upstream process-wide CUDA memory limit.
- `yue2/modeling_yue2.py` and `yue2/nar.py`: per-model attention hooks and an
  injectable synthesis-offload context. Normal nodes retain upstream attention.

[Exact changes](../compat/upstream_patches.json) · [Source hashes](manifest.json)

Original [licenses and notices](licenses/) are retained. These terms are separate
from the license for the original ComfyUI integration code.
