# Staged generation

1. Restart ComfyUI after installing the nodes.
2. Open [03_yue2_staged.json](../example_workflows/03_yue2_staged.json).
3. Choose the model and VAE, enter style and lyrics, then click **Run**.

- The final **Save Audio (Advanced)** node saves FLAC in `output/audio/`.

## What each node does

| Node | Purpose |
| --- | --- |
| YuE2 Model Loader | Validate model selections; weights load when a stage runs |
| YuE2 Request | Style, lyrics, score mode, seed and optional ABC |
| YuE2 Sampling | Official sampling defaults and synthesis steps |
| YuE2 Plan | Create a tokenized plan and ABC score text |
| YuE2 Semantic | Generate reusable song tokens from the plan |
| YuE2 Synthesize | Turn song tokens into acoustic latents |
| YuE2 Decode | Decode latents into stereo AUDIO at 48 kHz |

## Sampling and score modes

- **Sampling is optional** on Plan, Semantic and Synthesize. An unconnected stage
  uses its official defaults; it does not inherit another node's settings.
- The example connects one sampling configuration to all three stages.
- **`cot=off`** skips the score and uses upstream's guidance for that mode.
- **Supplied ABC** requires `full` or `melody` and is freshly tokenized.
- **Apply Edited Score** rebuilds an existing plan from new ABC text.
- Custom guidance controls are not implemented.

## Duration and decoding

- **Token limits are ceilings, not target durations.** Generation can stop naturally
  or hit a limit; `run_info.truncated` records the difference.
- Lower token limits and fewer synthesis steps can speed up execution checks.
  Use the defaults for normal quality evaluation.
- **Tiled decoding** defaults to 1024 core frames, with upstream overlap around each tile.
- **Full decoding** ignores tile size and can use more VRAM.

## Optional synthesis offload

- Enable **`offload_ar` on YuE2 Synthesize**, or open
  [06_yue2_synthesis_offload.json](../example_workflows/06_yue2_synthesis_offload.json).
- Experimental, **off by default**, and currently CUDA only.
- After cache preparation, ComfyUI moves token-generation layers to CPU and
  restores them between chunks.
- Can reduce VRAM use, with extra transfers and CPU RAM use.
  Preparation still needs the full model.
- Keeps attention, precision, sampling and chunk boundaries unchanged.
  The effective setting is recorded in the run information.

[VRAM estimates and measured examples](vram.md)

## Reusing results

- ComfyUI can cache each stage's output.
- Change decoding settings to reuse existing latents.
- Branch from semantic tokens to try different synthesis settings without
  generating those tokens again.
- Each stage releases its models on completion or failure.
  The cached loader output holds no live runtime.
- Repeated checkpoint hashing and model loading add overhead.

## Console progress

Messages begin with **`[YuE2]`** and show:

- Selected models and device.
- File verification, model loading and generation phases, with elapsed times.
- Generation counts at most once every 15 seconds, plus completion messages.
- Token counts instead of a percentage, because song length is not fixed.
  Reaching a token limit produces a warning.
- Final audio duration after decoding.

Cached nodes do not run again or print new stage messages.

CUDA stages also log allocated/reserved memory before and after cleanup.
These snapshots are kept in run info; **they are not peak measurements**.
See [VRAM usage](vram.md).

## Run information and saved artifacts

- `YUE2_PLAN`, `YUE2_SEMANTIC` and `YUE2_LATENTS` retain results and their origin/settings.
- `YUE2_RUN_INFO` records the request, stage history, effective settings,
  checkpoint/tokenizer hashes, timings and truncation. Branches copy their history.
- Artifacts from a different generator/tokenizer are rejected.
  The selected decoder's identity is recorded when decoding.
- Normal audio saving does not export intermediate tokens or latents.
  Use [Save Plan or Save Run](artifacts.md) to save and reload them.
- Generation uses upstream attention.
