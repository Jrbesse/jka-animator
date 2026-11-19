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
- **Inputs:** `ref_gla` (absolute .gla path), `ref_basepath`, `ref_mode`
  (`RANGE`/`CFG`/`ALL`/`NONE`), `ref_start`, `ref_frames` (RANGE mode),
  `addon_dir` (only if jediacademy is not installed).
- **Effect:** imports the reference GLA as a fresh armature named
  `reference_humanoid` (renames anything out of the `skeleton_root`
  name trap first); it animates independently, the rig is untouched.
- **Errors:** any import failure surfaces as the jediacademy/animkit
  message via `JkaError`.

**`jka_anim.prep_rig`** — *Prep rig for export*
- **Inputs:** none (the scene's `skeleton_root` mirror armature).
- **Effect:** strips IK constraints and zeroes stored pose offsets on the
  mirror, **in memory only** (the .blend is never saved); restores the
  legacy g2 scale for export. Reports the count of stripped constraints.

**`jka_anim.export_gla`** — *Export GLA*
- **Inputs:** `exp_basepath`, `exp_filepath` (absolute, **inside** the
  base path), `exp_glapath` (base-relative in-GLA name), `exp_ref`
  (base-relative reference GLA, default
  `models/players/_humanoid/_humanoid.gla` — copies bone indices),
  `exp_custom_frames` + `exp_frame_start`/`exp_frame_end` (off = the
  scene's current frame range), `addon_dir`.
- **Effect:** exports `skeleton_root` to .gla via the jediacademy add-on,
  restores the legacy g2 scale. Validate afterwards with `check_run`.
- **Errors:** `set the Output file first (inside the Base Path)`; any
  export failure (e.g. `Could not find reference GLA` on an absolute
  `exp_ref`).

### B2 — segments (`animation.cfg`)

**`jka_anim.segments_load`** — *Load segments*
- **Inputs:** `cfg_basepath`, `cfg_character`, `animkit_dir`.
- **Effect:** parses the character's `animation.cfg` into the Segments
  list and drift-checks the scene's actions against the cfg (per row:
  has-action + drift flags). Results: `<n> segments loaded` + warnings.

**`jka_anim.segment_jump`** — *Jump to segment*
- **Inputs:** selected segment row (`seg_selected`), `seg_jump_create`
  (default on).
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
- **Inputs:** `cfg_basepath`, `saber_cfg` (override; empty =
  `<base>/ext_data/saberanims.cfg`).
- **Effect:** parses + validates the sheet; lists each style's `openAnim`.
  A **missing file is not an error** — the engine falls back to its
  built-in style sheet (Results says so).

**`jka_anim.saber_preset_apply`** — *Apply saber preset*
- **Inputs:** `saber_preset` (dropdown: guard + one attack per saber
  style, from the cfg or the built-in fallback sheet).
- **Effect:** three coordinated artifacts, named exactly like the cfg
  segment: (1) the `animation.cfg` segment — added + **saved** when new
  (next free frame, num=20, loop=-1, fps=20; an existing segment's cfg
  values are the truth), (2) the action (loop/fps per the segment),
  (3) the NLA strip. Moves the playhead to the segment start.

### B3 — check + fingers

**`jka_anim.check_run`** — *Run check*
- **Inputs:** `cfg_basepath` + `cfg_character` (the Check box reuses the
  Segments fields) → resolves `<base>/models/players/<character>`.
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
**Reference (matching)**, **Rig**, **Export GLA**, **Segments
(animation.cfg)**, **Events (animevents.cfg)**, **Saber
(saberanims.cfg)**, **Check (Segments base path + character)**, **Fingers
(12 bones: d1/d2/d4 x j1/j2 per hand)**, **Results** — plus the
**Add-on Dir** property when set.

Segment row icons: `NONE` = no action, `ACTION` = action present,
`MODIFIER_OFF` (+ red `* action differs from the cfg` line) = drift.
Event rows display `#<keyframe> <TYPE minus AEV_> <data>`.

### Scene properties (`bpy.types.Scene.jka_anim`)

All properties live on the Scene (persist while the file is open; the
headless scripts use the same values via the CLI).

| Property | Type / default | Meaning |
|----------|----------------|---------|
| `ref_gla` | file, `""` | Reference .gla (absolute path). |
| `ref_basepath` | dir | Mod folder (needed by `Cfg` mode). |
| `ref_mode` | enum, `RANGE` | `RANGE` / `CFG` / `ALL` / `NONE` (see guide §3.1). |
| `ref_start` | int, `0` | Range mode: first frame. |
| `ref_frames` | int, `240` | Range mode: frame count. |
| `exp_basepath` | dir | Mod folder (contains `models/`). |
| `exp_filepath` | file, `""` | Output .gla — absolute, inside the base path. |
| `exp_glapath` | string | Base-relative in-GLA name. |
| `exp_ref` | string, `models/players/_humanoid/_humanoid.gla` | Base-relative reference GLA (bone indices). |
| `exp_custom_frames` | bool, off | Off = scene frame range; on = the two fields below. |
| `exp_frame_start` / `exp_frame_end` | int, `0` / `239` | Custom export range. |
| `addon_dir` | dir, `""` | Only if jediacademy is not installed: the dir containing the `jediacademy` package. |
| `animkit_dir` | dir, `""` | The dir that **contains** the `animkit` package; empty = `$JKA_ANIMKIT_DIR` or the dev clone. |
| `cfg_basepath` | dir | Mod folder containing `models/players/<character>/...`. |
| `cfg_character` | string | Character folder name (or `_humanoid` for the shared skeleton). |
| `saber_cfg` | file, `""` | Explicit `saberanims.cfg` path; empty = `<base>/ext_data/saberanims.cfg`. |
| `segments` | collection of `JkaAnim_Segment` | One row per cfg segment: `name`, `first_frame`, `num_frames`, `loop_frames`, `fps`, `has_action`, `drift`. Read-only display — Load refreshes it; files are edited via the core + the add/save ops. |
| `seg_selected` | int | Selected segment row. |
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
| `results` | collection of `JkaAnim_Result` | `text` + `is_error` — every operator's output. |
