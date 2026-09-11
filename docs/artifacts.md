# Score editing and saved artifacts

`YuE2 Apply Edited Score` accepts a model selection, an existing plan and edited
ABC text. It preserves the request's style, lyrics, seed and score mode, then
uses upstream planning to tokenize the new ABC and rebuild its prefix. It does
not mutate the original plan or reuse its token IDs. The new provenance records
the source plan's hash in `edited_from`. The source must use `full` or `melody`;
`off` requests do not accept ABC.

Use [`04_edit_and_save.json`](../example_workflows/04_edit_and_save.json) for an
example with an initial score and a different edited melody. It saves the edited
plan, generates audio and saves the complete run. The initial supplied score
bypasses model-based planning; semantic generation still uses the selected model.

## Saving

| Node | Inputs | Result |
| --- | --- | --- |
| YuE2 Save Plan | Plan and a name | Exact plan, ABC, provenance and workflow metadata |
| YuE2 Save Run | Latents, the corresponding Decode AUDIO and Decode run_info, and a name | Complete reusable run including the plan, semantics, latents and audio |

Connect Save Run directly to the corresponding Synthesize and Decode outputs.
Audio must be the original float32 stereo decode at 48 kHz with its original
length. Save an independently processed listening copy with ComfyUI's audio
nodes. Stage histories are checked to reject mixed provenance; this check cannot
prove that a custom node has not altered samples while retaining the metadata.

Saves use `output/yue2/<name>-<unique-id>/`. Names allow letters, digits,
underscores and hyphens. Existing artifacts are never overwritten. Files are
written and checked in a temporary folder before the completed folder is
published. Save nodes return a reference such as `output/run-<unique-id>`.

## Loading

`YuE2 Load Plan` loads either a saved plan or the plan inside a saved run.
`YuE2 Load Run` returns plan, semantic, latents, AUDIO and run_info. Import does
not load model weights or regenerate tokens. Reconnect a returned intermediate
to a generation stage to continue from it; that stage verifies generator and
tokenizer identity against the selected model. A different VAE is recorded if
used for a fresh decode.

The import dropdowns discover immediate subfolders under `output/yue2/` and
`input/yue2/`. To transfer an artifact, copy the whole completed folder into
`input/yue2/` and refresh the node definitions or reload the page. Select it by
its `input/` or `output/` reference. Absolute paths and traversal are rejected.
[`05_load_run.json`](../example_workflows/05_load_run.json) loads saved audio and
exports a FLAC through the built-in audio node, without requiring the model.

## Format version 1

Every artifact contains `manifest.json`, `plan.json`, `score.abc`, `prompt.json`
and `workflow.json`. A run also contains `semantic.json`, `latent_info.json`,
`run_info.json`, `latents.npy` and `audio.npy`. Token IDs remain integers in JSON;
latents and audio use lossless float32 NumPy arrays. Audio is stored as
`[samples,2]` at 48 kHz; latent shape is `[semantic_tokens,64]`.

The manifest hashes every payload file. Import verifies hashes, supported
version, required filenames, numeric shapes and compatible stage histories.
No pickle, archive extraction, embedded Python or model downloading is used.
Checksums detect changed files; they are not signatures authenticating an author.
Saved arrays are copied into writable graph values, so editing a loaded value
cannot modify the on-disk artifact through a memory mapping.

Do not edit `score.abc` inside a completed artifact: that invalidates its hash.
Copy the text into Apply Edited Score and save the new plan. Workflow metadata
is retained when supplied by ComfyUI; a headless API request without canvas
metadata has `null` in `workflow.json`. The API prompt is recorded separately;
ComfyUI's execution-only `is_changed` cache annotations are excluded.
The artifact contains no model weights. Raw audio uses about 384 KB per second;
FLAC listening copies remain the responsibility of ComfyUI's audio saver.
