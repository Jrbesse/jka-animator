# Operator & panel reference

Complete reference for the add-on's registered classes, verified against
the live registry: `packaging/b4_register_smoke.py` run on a freshly
built release zip (Blender 5.3.0, `--factory-startup`) reports
**15/15 operators + panel `JKA_PT_Main` registered**, unregister clean.

All 15 operators live in the `jka_anim` sub-block. Operators are thin
delegates: they read the scene properties below, call the bpy-free core,
and report via `self.report()` and the Results collection.

## The 15 operators

### B1 — reference, rig, export

**`jka_anim.load_reference`** — *Load reference GLA*
- **Inputs:** `ref_gla` (base-relative or absolute .gla; default
  `models/players/_humanoid/_humanoid.gla`), the shared `basepath` (if
  empty it is derived from `ref_gla` — walk up to the folder containing
  `models/players`), `ref_mode` (`RANGE`/`CFG`/`ALL`/`NONE`), `ref_start`,
  `ref_frames` (RANGE mode), `addon_dir` (only if jediacademy is not
  installed).
- **Effect:** imports the reference GLA as a fresh armature named
  `reference_humanoid` (renames anything out of the `skeleton_root`
  name trap first); it animates independently, the rig is untouched.
  Afterwards the reference is re-aligned to the rig mirror's world
  transform (identity parent-inverse) — a replacement model's
  `scene_root` convention rotation cannot leave it on the wrong plane.
  In CFG mode the first strip's action becomes the armature's
  `data_action` so the keys are visible.
- **Errors:** any import failure surfaces as the jediacademy/animkit
  message via `JkaError`; the base-path derivation errors name the
  missing piece.

**`jka_anim.prep_rig`** — *Prep rig for export*
- **Inputs:** none (the scene's `skeleton_root` mirror armature).
- **Effect:** strips IK constraints and zeroes stored pose offsets on the
  mirror, **in memory only** (the .blend is never saved); restores the
  legacy g2 scale for export. Reports the count of stripped constraints.

**`jka_anim.export_gla`** — *Export GLA*
- **Inputs:** the shared `basepath` + `character` (the output, in-GLA
  path and reference are **derived**:
  `<base>/models/players/<char>/<char>.gla`), `exp_ref` (base-relative
  reference GLA, default `models/players/_humanoid/_humanoid.gla` —
  copies bone indices), `exp_custom_frames` + `exp_frame_start`/
  `exp_frame_end` (off = the scene's current frame range), `addon_dir`.
- **Effect:** exports `skeleton_root` to .gla via the jediacademy add-on,
  restores the legacy g2 scale. Validate afterwards with `check_run`.
- **Errors:** `no Base Path set — set it at the top of the panel (the
  mod folder that contains models/players)`; `set the Character (the
  folder under models/players, e.g. assassin_droid) so the output path
  can be derived`; any export failure (e.g. `Could not find reference
  GLA` on an absolute `exp_ref`).

### B2 — segments (`animation.cfg`)

**`jka_anim.segments_load`** — *Load segments*
- **Inputs:** the shared `basepath` + `character`, `animkit_dir`
  (override; empty = the bundled copy).
- **Effect:** parses the character's `animation.cfg` into the Segments
  list and drift-checks the scene's actions against the cfg (per row:
  has-action + drift flags). Results: `<n> segments loaded` + warnings.

**`jka_anim.segment_jump`** — *Jump to segment*
- **Inputs:** selected segment row (`seg_selected`), `seg_jump_create`
  (default on), the **Rig target** (`target_arm` — where the action's
  NLA strip lands; default the working skeleton).
- **Effect:** sets the playhead to the segment's first frame; when
  `seg_jump_create`, creates the action (named exactly like the segment,
  with the cfg's loop/fps in its `g2_sequence_prop`) and NLA strip when
  missing. Reports each created artifact.

**`jka_anim.segment_apply`** — *Apply to action*
- **Inputs:** selected segment row.
- **Effect:** writes the cfg's loop/fps into the action's
  `g2_sequence_prop`; clears the row's drift flag. Blender can only
  express loop yes/no — a cfg loop point `N>0` stays read-only.
- **Errors:** `no action named 'X' — press Jump (create) first`;
  `action 'X' has no g2_sequence_prop (created outside the jediacademy
  importer)`.

**`jka_anim.segment_add`** — *Add segment*
- **Inputs:** `seg_new_name`, `seg_new_first`, `seg_new_num`,
  `seg_new_loop` (-1 none / 0 loop / N loop point), `seg_new_fps`.
- **Effect:** appends the segment to `animation.cfg` and **saves
  immediately** (line-preserving write — untouched lines byte-identical);
  mirrors the row into the panel.
- **Errors:** `give the new segment a name`; `segment 'X' already exists`.

### B2 — events (`animevents.cfg`)

**`jka_anim.events_load`** — *Load events*
- **Inputs:** `evt_block` (`LOWER`/`UPPER` — the engine's block names; the
  file headers are `LOWEREVENTS`/`UPPEREVENTS`), `evt_segment` (the loaded
  Segments).
- **Effect:** lists the events of the chosen block + segment.

**`jka_anim.event_add`** — *Add event*
- **Inputs:** `evt_new_type` (the 6 editable `AEV_*` types — see
  [formats](formats.md#animeventscfg)), `evt_new_key`, `evt_new_data`
  (space-separated fields per type; the panel prints the expected
  layout under the field).
- **Effect:** appends the event **in memory** — press Save to write.

**`jka_anim.event_remove`** — *Remove event*
- **Inputs:** selected event row (`evt_selected`).
- **Effect:** removes it **in memory** — press Save to write.

**`jka_anim.events_save`** — *Save events*
- **Effect:** **validate-on-write** — reparses + validates the edited
  events against the segment table, then writes `animevents.cfg`. On
  validation failure the file is **not touched**; every error line lands
  in the Results box (red) with `write blocked — see the Results box`.

### B2 — saber (`saberanims.cfg`)

**`jka_anim.saber_validate`** — *Validate saber cfg*
- **Inputs:** the shared `basepath`, `saber_cfg` (override; empty =
  `<base>/ext_data/saberanims.cfg`).
- **Effect:** parses + validates the sheet; lists each style's `openAnim`.
  A **missing file is not an error** — the engine falls back to its
  built-in style sheet (Results says so).

**`jka_anim.saber_preset_apply`** — *Apply saber preset*
- **Inputs:** `saber_preset` (dropdown: guard + one attack per saber
  style, from the cfg or the built-in fallback sheet), the **Rig
  target** (`target_arm` — the armature the NLA strip lands on; default
  the working skeleton).
- **Effect:** three coordinated artifacts, named exactly like the cfg
  segment: (1) the `animation.cfg` segment — added + **saved** when new
  (next free frame, num=20, loop=-1, fps=20; an existing segment's cfg
  values are the truth), (2) the action (loop/fps per the segment),
  (3) the NLA strip. Moves the playhead to the segment start.

### B2 — import (GLA → rig)

**`jka_anim.anim_import`** — *Import animation* (two panel buttons:
*Import segment into rig*, *Import custom range into rig*)
- **Inputs:** the **Rig target** (`target_arm`), the operator property
  `custom` (false = the picked `imp_segment`, true = the typed custom
  range), `imp_segment` (a loaded Segments row; `""` = custom), and for
  custom: `imp_name`, `imp_first`, `imp_frames`, `imp_fps`. The source
  GLA is the derived reference GLA (`ref_gla` override or
  `<base>/models/players/<char>/<char>.gla` / `model.gla` / stock
  `_humanoid`).
- **Effect:** RANGE-imports the frame range via the jediacademy
  importer onto a throwaway `skeleton_root` (renaming the working
  mirror to `rig_armature` first when it still wears the name), then
  retargets the imported action onto the target rig:
  - bones whose ENTIRE ancestor chain matches name-for-name in both
    rigs: the source's keyed `location` + `rotation_quaternion` are
    copied **verbatim** — bit-exact (the form the GLA importer keyed
    and the exporter re-samples), so the re-exported GLA round-trips
    unchanged;
  - bones where the target's parent differs (the IK rig's chained
    finger bones): parent-relative **re-aim** — per frame, per bone,
    in the target's topological order,
    `W_t = M_t(parent_t) @ M_src(parent_src)⁻¹ @ W_src` (root:
    `W_t = W_src`), every term composed from keyed fcurve locals + rest
    `matrix_local` (no evaluated `pose_bone.matrix` reads — stale in
    `--background`);
  - target-only bones (IK controls) are never touched;
  - a new action named exactly like the segment (or the typed name)
    with the cfg's loop/fps in `g2_sequence_prop` (custom ranges:
    loop=False, typed fps), keyed `location` + `rotation_quaternion`
    per frame at the absolute range frames;
  - an NLA strip on the target; a timeline marker at the range's first
    frame (deduped by name).
  - **Re-import replaces** the existing action of the same name (its
    strips on every armature are removed first — no `NAME.001`).
- **Errors:** `no segments loaded — press Load in the Segments box`
  (via the stale-selection guard); `give the custom import a name`;
  `the custom range needs at least 1 frame`; `frames A..B are outside
  the GLA (it holds N)`; the name-dance collision `both 'skeleton_root'
  and 'rig_armature' objects exist`.

**`jka_anim.markers_from_segments`** — *Markers from segments*
- **Inputs:** the loaded Segments, `marker_offset` (default 0 — the
  GLA workflow is 0-based like the engine).
- **Effect:** one timeline marker per segment on
  `first_frame + marker_offset`; existing markers of the same name are
  **moved**, not duplicated.

**`jka_anim.markers_clear`** — *Clear markers*
- **Effect:** removes every timeline marker in the scene.

### B3 — check + fingers

**`jka_anim.check_run`** — *Run check*
- **Inputs:** the shared `basepath` + `character` (the Check box reuses
  the **Base** box — there is no separate check path) → resolves
  `<base>/models/players/<character>`.
- **Effect:** runs animkit's `check` over the directory (GLM + GLA +
  cfgs + skin; see [validation](validation.md)) and fills Results:
  summary line (error icon when failed), then errors, then warnings.
  A crash inside animkit's check is reported as a tool-bug error, never
  as a finding.
- **Errors:** `check: no such directory: ... — expected a character or
  skeleton dir under models/players/ in the basepath`.

**`jka_anim.finger_preset`** — *Finger preset* (×3 panel buttons:
Grasp / Fist / Open)
- **Inputs:** the operator property `preset` ∈ `GRASP`/`FIST`/`OPEN`.
- **Effect:** poses the 12 engine finger bones
  (`l/r_d1_j1, l/r_d1_j2, l/r_d2_j1, l/r_d2_j2, l/r_d4_j1, l/r_d4_j2`)
  to the preset, **relative to each hand's current pose** (hands never
  touched); keys them at the current frame when the armature has an
  active action (Results says which happened). On rigs whose
  `skeleton_root` is a passive mirror, the operator follows the copy
  constraint to the driver armature and poses that.
  - **FIST** = `BOTH_P6_S6_TR` pool frame 10370 — the right-hand blaster
    grip + its rig mirror (no stock segment clenches both hands).
  - **OPEN** = `BOTH_STAND1` pool frame 14578 — the stock relaxed
    weapon-stand hand.
  - **GRASP** = per-bone quaternion slerp midpoint of FIST↔OPEN +
    translation midpoint.
- **Errors:** `no armature in the scene (load the IK rig first)`;
  `bone 'X' missing from <arm> — the rig must be the _humanoid skeleton`.

## The panel (`JKA_PT_Main`)

3D view → sidebar (**N**) → category **JKA**. Boxes, top to bottom:
**Base (set once — everything derives from it)**, **Reference
(matching)**, **Rig**, **Export GLA**, **Segments (animation.cfg)**,
**Animation (import into a rig)**, **Labels (timeline markers)**,
**Events (animevents.cfg)**, **Check (Base Path + Character)**,
**Fingers (12 bones: d1/d2/d4 x j1/j2 per hand)**, **Saber
(saberanims.cfg — JA-Enhanced event mapping, optional)**, **Results**,
**Dependencies (leave empty when installed in Preferences)** — every
field carries a visible label. Settings
(basepath, character, ranges, overrides) are persisted to a JSON in the
user config dir and restored on the next session (auto-disabled in
headless).

Segment row icons: `NONE` = no action, `ACTION` = action present,
`MODIFIER_OFF` (+ red `* action differs from the cfg` line) = drift.
Event rows display `#<keyframe> <TYPE minus AEV_> <data>`.

### Scene properties (`bpy.types.Scene.jka_anim`)

All properties live on the Scene (persist while the file is open; the
headless scripts use the same values via the CLI).

| Property | Type / default | Meaning |
|----------|----------------|---------|
| `basepath` | dir, `""` | The ONE mod folder — the directory that contains `models/players`. Set once; the reference GLA, export output, in-GLA name, cfgs and check all derive from it. |
| `character` | string, `_humanoid` | The folder under `models/players` (a real character or `_humanoid`). |
| `ref_gla` | file, `""` | Reference .gla (base-relative or absolute). Empty = derive: `<base>/models/players/<character>/<character>.gla` when present, else the NPC convention `model.gla`, else the stock `_humanoid` GLA. |
| `ref_mode` | enum, `RANGE` | `RANGE` / `CFG` / `ALL` / `NONE` (see guide §3.1). |
| `ref_start` | int, `0` | Range mode: first frame. |
| `ref_frames` | int, `240` | Range mode: frame count. |
| `exp_ref` | string, `models/players/_humanoid/_humanoid.gla` | Base-relative reference GLA (bone indices). |
| `exp_custom_frames` | bool, off | Off = scene frame range; on = the two fields below. |
| `exp_frame_start` / `exp_frame_end` | int, `0` / `239` | Custom export range. |
| `addon_dir` | dir, `""` | Only if the separately-installed `jediacademy` is not enabled in Preferences: the dir containing the `jediacademy` package. |
| `animkit_dir` | dir, `""` | Override; empty = the copy **bundled** in the add-on (`lib/animkit`). |
| `saber_cfg` | file, `""` | Explicit `saberanims.cfg` path; empty = `<base>/ext_data/saberanims.cfg`. |
| `segments` | collection of `JkaAnim_Segment` | One row per cfg segment: `name`, `first_frame`, `num_frames`, `loop_frames`, `fps`, `has_action`, `drift`. Read-only display — Load refreshes it; files are edited via the core + the add/save ops. |
| `seg_selected` | int | Selected segment row. |
| `seg_filter` | string, `""` | Substring filter for the segment list (the list draws at most 50 rows). |
| `seg_jump_create` | bool, on | Jump: also create the action + NLA strip when missing. |
| `seg_new_name` / `seg_new_first` / `seg_new_num` / `seg_new_loop` / `seg_new_fps` | string / `0` / `20` / `-1` / `20` | The Add-segment fields (`seg_new_loop`: -1 none, 0 loop, N loop point). |
| `events` | collection of `JkaAnim_Event` | One row per event of the selected block+segment: `etype`, `key_frame`, `data`, `line`, `block_index`. |
| `evt_selected` | int | Selected event row. |
| `evt_block` | enum, `LOWER` | `LOWER` / `UPPER` (engine names; file headers `LOWEREVENTS` / `UPPEREVENTS`). |
| `evt_segment` | enum (loaded segments) | The segment whose events are listed. |
| `evt_new_type` | enum, `AEV_SOUND` | The 6 editable event types (formats §animevents.cfg). |
| `evt_new_key` | int, `0` | Key frame, relative to the segment start. |
| `evt_new_data` | string | Space-separated data fields (the panel prints the layout). |
| `saber_preset` | enum (re-read from cfg each redraw) | Guard + one attack per style. |
| `target_arm` | enum (armature objects; scene UI state) | The **Rig target** for Jump / Saber / Import. Stored id = the armature object name; a stale id (renamed/deleted) is healed to the default at draw. Default resolution: `skeleton_root` / `rig_armature` (the working skeleton, under either name), else the first armature. |
| `imp_segment` | enum (`""` + loaded segments) | The Import box's segment pick; `""` = the custom range below. |
| `imp_name` / `imp_first` / `imp_frames` / `imp_fps` | string / `0` / `20` / `20` | The custom-range import fields (name, first frame, frame count, fps). |
| `marker_offset` | int, `0` | Frames added to each timeline marker's first frame (0-based by default; 1 for 1-based work). |
| `results` | collection of `JkaAnim_Result` | `text` + `is_error` — every operator's output. |
