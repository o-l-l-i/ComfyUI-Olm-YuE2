# Example workflows

Start with **[03_yue2_staged.json](03_yue2_staged.json)** for your first song.

- Open `.json` files in ComfyUI.
- Matching `.api.json` files are for API clients, not the canvas.
- Model selections match files directly in `models/yue2/` and `models/yue2_vae/`.
  For other folder names, select the matching dropdown entries.

| Workflow | Use it for |
| --- | --- |
| [03 — Staged generation](03_yue2_staged.json) | Style and lyrics to saved audio |
| [07 — Score inspector](07_score_inspector.json) | Plan first, inspect/edit, then enable audio generation |
| [04 — Edit and save](04_edit_and_save.json) | Supplied ABC and reusable plan/run artifacts |
| [05 — Load a run](05_load_run.json) | Export audio from a previously saved run |
| [06 — Synthesis offload](06_yue2_synthesis_offload.json) | Experimental CUDA memory reduction |

## 03 — YuE2 staged generation

1. Select the model and VAE by folder name in **YuE2 Model Loader**.
2. Enter style and lyrics in **YuE2 Request**, or try the included English song.
3. Click **Run**. **Save Audio (Advanced)** saves FLAC in `output/audio/`.

**Settings**

- Uses upstream defaults: up to 4096 ABC tokens, 9000 semantic tokens and
  32 midpoint synthesis steps.
- Token limits are ceilings, not song durations. Reaching one can truncate the
  score or song; `run_info` records this. Generation may take several minutes.
- Optional supplied ABC is freshly tokenized. Use `full` or `melody` score mode;
  `off` generates without a score.
- The example seed is fixed. Branch a semantic output to reuse its exact tokens
  with different synthesis settings.

**Execution**

- Uses the regular YuE2 nodes and ComfyUI's built-in audio saver.
- Each stage loads and releases its models. File verification and loading repeat.
- For the API version, change loader inputs to match your model dropdown entries.

## 04 — Edit a score and save the run

1. Select the model and VAE.
2. Edit the second ABC text in **Apply Edited Score**, then click **Run**.

- Starts with a supplied ABC melody and uses official generation defaults.
- **Apply Edited Score** freshly tokenizes the changes; the original plan stays reusable.
- **Save Plan** and **Save Run** keep versioned artifacts in `output/yue2/`.
- Also saves FLAC audio. See [artifact details](../docs/artifacts.md).

## 05 — Load saved audio

1. In **Load Run**, replace the placeholder with one of your completed runs.
2. Click **Run** to export its saved audio as FLAC. No model is needed.

- To import a run, copy its complete artifact folder into `input/yue2/`
  and refresh the dropdowns.
- Other outputs can feed score editing, semantic generation, synthesis or decoding.

## 06 — Experimental synthesis offload

- Uses the same generation stages as example 03, with `offload_ar` enabled on
  **YuE2 Synthesize** and upstream generation defaults.
- Requires CUDA. ComfyUI moves token-generation layers to CPU during synthesis.
- Preparation still loads the full model. Offloading adds transfers and CPU RAM
  use; it cannot guarantee that a song fits a particular GPU.
- Saves audio with the prefix `audio/YuE2_offload`.

[VRAM estimates and measured examples](../docs/vram.md)

## 07 — Inspect and edit a score

1. Enable **Settings → YuE2 → Enable optional score tools**.
2. Click **Run** to generate, preview and save the original plan.
   Audio generation starts muted.
3. Open **YuE2 Score** in the sidebar. Under **View score from**, choose
   **1. Inspect generated plan**.
4. Under **Send to an editor**, choose **2. Edit ABC here** and click
   **Use score in editor**. Clear the editor first if it contains a different score.
5. Edit the ABC on the canvas. The sidebar now shows that editor;
   click **Refresh** to inspect your changes.
6. Unmute **Apply Edited Score (#9)**, **3. Inspect edited plan (#14)**,
   the audio nodes **#5–8**, and **Save Run (#11)**. Click **Run** to generate audio.

- Keep the request seed fixed to reuse the source plan.
- **Save Plan** keeps the original; **Save Run** retains the edited plan and result.
- You can leave visualization disabled and paste ABC directly into the editor.
- The `.api.json` companion runs only the initial planning phase.

[Score tools guide](../docs/frontend.md)
