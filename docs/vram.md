# VRAM usage

- **Synthesis uses the most VRAM.** Longer songs generally need more memory.
- Planning and semantic generation peaked around **7–8 GiB** in the measured run; tiled audio decoding used about **2.7 GiB**.
- Models are unloaded after each stage. Most VRAM was released after generation in testing.

## Will my GPU run it?

These are **best-effort estimates based on observed memory use**, not tested requirements. Only the RTX 5090 has been tested here. Applies to the current unquantized CUDA path on modern NVIDIA GPUs (RTX 30 series or newer).

| VRAM | Example desktop GPUs | Rough expectation |
| --- | --- | --- |
| 8 GB or less | RTX 4060 | Unlikely to fit a complete song with the current implementation. |
| 12 GB | RTX 4070 | Very tight; short runs with offloading may fit, but expect out-of-memory failures. |
| 16 GB | RTX 4060 Ti **16 GB**, RTX 4080 | Plausible for shorter songs; try `offload_ar`. Longer songs may exceed capacity. |
| 24 GB | RTX 3090, RTX 4090 | More room for longer songs; offloading may still be needed. |
| 32 GB | RTX 5090 | Tested with complete songs over five minutes. Still workload-dependent. |

- Song length, score complexity and other GPU use affect whether a run fits. These are capacity estimates, not speed estimates.
- GPU memory specifications: [RTX 30](https://www.nvidia.com/en-us/geforce/graphics-cards/30-series/rtx-3090-3090ti/), [RTX 40](https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/), [RTX 5090](https://www.nvidia.com/en-us/geforce/graphics-cards/50-series/rtx-5090/).

## Measured examples

- Tested on an **RTX 5090**, with BF16 generation, default sampling and tiled decoding.
- These are **active PyTorch allocation peaks**, not total GPU usage or minimum card sizes. Leave room for reserved memory, ComfyUI and other applications.

| Synthesis workload | Default | With `offload_ar` |
| --- | ---: | ---: |
| 2 min 37 sec song | 10.2 GiB | 9.5 GiB |
| 5 min synthetic test* | 17.1 GiB | 13.7 GiB |

*Repeated song tokens to test memory use at greater length; actual songs will vary.*

## Reducing memory use

- Enable **`offload_ar` on YuE2 Synthesize**, or open [06_yue2_synthesis_offload.json](../example_workflows/06_yue2_synthesis_offload.json).
- Optional and off by default; currently CUDA only. Moves part of the model to CPU during synthesis.
- Uses extra system RAM and may add transfer time. Tested outputs matched the default path.
- Preparation still loads the full model, so offloading cannot guarantee a song will fit.
- Keep **YuE2 Decode** in `tiled` mode, and avoid other GPU workloads during generation.
