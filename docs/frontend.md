# Optional score tools

1. Restart ComfyUI after installing the nodes, then refresh the browser.
2. Enable **Settings → YuE2 → Enable optional score tools**.
3. Open **YuE2 Score** in the sidebar.

Off by default. Generation, artifact save/load and API execution work without it.

## Preview and editor nodes

| Node | Use it for |
| --- | --- |
| YuE2 Score Preview | Show a plan's ABC, mode, seed, token count and truncation after execution |
| YuE2 ABC Editor | Hold editable ABC text in the workflow and preview it without generation |

- Branch **Score Preview** from **Plan**, **Apply Edited Score** or **Load Plan**.
- Connect **ABC Editor** to **Apply Edited Score**, together with the original
  plan and model selection.
- The sidebar has **Score**, **ABC** and **Info** views.
- To preview an editor directly, select it under **View score from** and click **Refresh**.

## Try the edit workflow

Open [07_score_inspector.json](../example_workflows/07_score_inspector.json).
Initially, only planning, preview and Save Plan run. Audio generation is muted.

1. Click **Run** to generate the original plan.
2. Under **View score from**, select **1. Inspect generated plan**.
3. Under **Send to an editor**, select **2. Edit ABC here** and click
   **Use score in editor**.
4. Edit ABC on the canvas; click **Refresh** in the sidebar to preview changes
   without generating audio.
5. Unmute **Apply Edited Score (#9)**, **3. Inspect edited plan (#14)**,
   the audio nodes **#5–8**, and **Save Run (#11)**. Click **Run** to continue.

- Keep the request seed fixed to reuse the original plan.
- The `.api.json` companion runs only the initial planning phase.
- API callers can supply ABC directly to **Apply Edited Score**, as in
  [04_edit_and_save.json](../example_workflows/04_edit_and_save.json).

## Copying into an editor

- **Use score in editor** copies exact ABC and switches the inspector to the editor.
- Clear an editor before replacing a different, nonempty score.
  A blocked copy shows a highlighted **Not copied** alert naming the target.
- **Copy ABC to clipboard** is independent of the target editor. Use it to paste
  selected parts if needed.
- Copying cannot fill an editor with a connected ABC input.
- **Refresh** updates the list after adding or removing nodes.

## Which score am I looking at?

- **View score from** uses exact canvas titles followed by node IDs, sorted by title.
- Example 07 follows its numbered titles:
  **1. Inspect generated plan → 2. Edit ABC here → 3. Inspect edited plan**.
- Initially selects the first active preview. Help text names the selected node.
- The inspector stays on your selected source.
- **#13** shows the original plan; **#14** shows applied edits.
  Re-running #13 does not update #14 while its branch is muted.
- Muted/bypassed previews are labelled, and retained output is marked **Last result**.
- To follow a new generation, select **1. Inspect generated plan (#13)**.
  Score and seed update when it completes.

## What is saved?

- ABC widget text is saved with the workflow.
  The sidebar has no separate draft.
- Previews use ComfyUI's node-output cache. Save a plan or copy ABC into an editor
  to keep it independently of that cache.
- Rendering does not rewrite, transpose or retokenize ABC.

## Limits

- Parser warnings are advisory. They do not establish valid model conditioning
  or guarantee that audio will follow every note.
- Empty scores are supported. Above 100,000 characters, notation is skipped;
  complete ABC remains available.
- Only score nodes in the root workflow are listed.
- Subgraph navigation, inline canvas notation, note dragging and MIDI audition
  are not implemented.

## Local and optional

- The bundled abcjs renderer loads only when score tools are enabled.
- No external requests, audio synthesis or soundfonts.
- No Node.js installation or extra Python dependency needed by users.
- Disabling the setting removes the panel and its score display.
  Browser module code stays cached until reload.
