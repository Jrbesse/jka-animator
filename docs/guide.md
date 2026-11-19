# JKA Anim Tools — user guide

End-to-end: from an uninstalled machine to a validated, in-engine-verified
character animation. Target machine: Windows with Blender 4.1+ (5.3.0
tested). Every command, path, operator name, and panel label below is
checked against the shipped code — if you see something different, the
panel label is the truth and the guide is stale.

**Scope:** animation side only. The finished model (`.glm` mesh + weights,
`.skin`, textures) is an *input*; you author and export animation
(`.gla` frames + the `animation.cfg` / `animevents.cfg` that drive it).

---

## 1. Install

Get the zip from the
[releases](https://github.com/Jrbesse/jka-animator/releases):
`jka-anim-suite-X.Y.Z.zip`. Unzipping gives one folder:

```
jka-anim-suite-X.Y.Z\
  README-install.md        ← the install sheet (this section)
  addons\
    jka_anim_tools\        ← this suite (MIT)
    jediacademy\           ← the GLA import/export add-on (GPL, hard dependency)
  lib\
    animkit\               ← the JKA format library the suite imports (MIT, pure Python)
```

1. **Copy the two add-on folders** into your Blender add-ons directory:
   - Windows default: `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons`
     (Blender → Edit → Preferences → Add-ons shows you the exact location).
   - Copy **both** `addons\jka_anim_tools` and `addons\jediacademy`
     (the folders, not the zip).
2. **Enable both add-ons** in Preferences → Add-ons:
   - *Jedi Academy Import/Export Tools* (`jediacademy`)
   - *JKA Animation Tools* (`jka_anim_tools`)
3. **Point the suite at animkit.** In the JKA N-panel (3D view → **N** →
   **JKA** tab), in the *Segments (animation.cfg)* box, set **AnimKit Dir**
   to the `lib` folder of the unzipped release:

   ```
   C:\...\jka-anim-suite-X.Y.Z\lib
   ```

   It must be the folder that **contains** `animkit\`. Alternative: set the
   environment variable `JKA_ANIMKIT_DIR` to that same `lib` folder.
4. Verify: press **N** in the 3D view → the **JKA** tab (the last of the
   tabs: Item / Tool / View / Animation / JKA) shows the boxes from §2.

> The suite loads `jediacademy` on demand if it is not already enabled,
> using the optional **Add-on Dir** field (bottom of the panel) — but
> enabling it in Preferences is the normal path.

---

## 2. The JKA panel

All state lives in the scene (it persists while the file is open). The
boxes, top to bottom:

| Box | What it drives |
|-----|----------------|
| **Reference (matching)** | Import a reference `.gla` to pose against. |
| **Rig** | Prep the rig for export (strip contamination). |
| **Export GLA** | Write the `.gla`. |
| **Segments (animation.cfg)** | The segment table: load / jump / apply / add. |
| **Events (animevents.cfg)** | Footsteps/sounds/effects: load / add / remove / save. |
| **Saber (saberanims.cfg)** | Saber attack sheet: validate / apply preset. |
| **Check (Segments base path + character)** | Run the validation gate. |
| **Fingers (12 bones: d1/d2/d4 x j1/j2 per hand)** | FIST / OPEN / GRASP presets. |
| **Results** | Every operator's output: notes, warnings, errors (error lines get a red icon). |

Most boxes need a **base path** — *your mod folder*, i.e. the directory
that **contains** `models\...`. A working character tree looks like:

```
<base>\models\players\<character>\
  model.glm                 ← the finished model (input)
  model_default.skin        ← skin (input)
  model.gla                 ← animations (this suite writes this)
  animation.cfg             ← segment table (this suite edits this)
  animevents.cfg            ← events (this suite edits this)
<base>\ext_data\saberanims.cfg   ← optional saber sheet
```

For `_humanoid`-skeleton characters (the normal case), the *reference*
skeleton tree `<base>\models\players\_humanoid\_humanoid.gla` is what the
export aligns to.

---

## 3. The authoring loop

The full loop for one new segment:

```
Load reference → (optional) Prep rig → Jump to segment → pose + key
→ finger presets → Export GLA → Run check → in-engine play
```

### 3.1 Load reference (pose against a stock animation)

In **Reference (matching)**:

- **Reference GLA** — absolute path to a `.gla` to import. The stock
  skeleton file (`<base>\models\players\_humanoid\_humanoid.gla` — 1,663
  segments in the stock cfg) is the usual choice.
- **Base Path** — your mod folder (needed for `Cfg` mode).
- **Import mode**:
  - `Range` (default) — one action over `Start frame .. Start+Frames-1`.
    Fast; right for working on a single segment.
  - `Cfg` — one NLA strip per `animation.cfg` segment: scrub by segment
    name. Slower on big skeletons (several minutes for the full
    `_humanoid` on a weak CPU).
  - `All` — every frame in one action. Slow.
  - `None` — geometry only, no animation.
- **Start frame / Frames** — the range for `Range` mode (segment start
  frames are in the Segments box, §3.3).

Press **Load reference GLA**. The reference arrives as a second armature
named `reference_humanoid` and animates independently; your rig stays
untouched. Scrub the timeline, pose your rig to match, and insert
keyframes into your segment's action as you go.

*Why the button exists:* the jediacademy importer would otherwise reuse
any existing object named `skeleton_root` and silently key the reference
onto your rig's mirror armature. The operator does a rename dance around
that trap.

### 3.2 Prep rig (before any export)

The rig `.blend` ships contaminated: stored pose offsets + IK constraints.
Exporting it raw writes a degenerate frame stream. **Prep rig for export**
strips the IK constraints and zeroes the stored pose offsets — **in memory
only**, the `.blend` is never saved. The result reports how many
constraints were stripped.

Run this once per session, after opening the rig and before exporting.

### 3.3 Segments (animation.cfg)

This box is the engine's segment table, live.

1. Set **Cfg Base Path** (mod folder), **Character** (the folder name
   under `models\players`, e.g. `assassin_droid` — or `_humanoid` for the
   shared skeleton), and **AnimKit Dir** (§1).
2. Press **Load segments**. Each row is one cfg segment:
   `NAME  first..last` with an icon —
   - empty icon: no Blender action for this segment yet
   - action icon: an action with this name exists
   - *modifier-off* icon + a red `* action differs from the cfg` line:
     **drift** — the action's loop/fps don't match the cfg
3. Select a row, then:
   - **Jump to segment** — moves the playhead to the segment's first
     frame; with the *Create action/strip if missing* checkbox (default on)
     it also creates the action + NLA strip named exactly like the segment
     (the engine's naming contract).
   - **Apply to action** — writes the cfg's loop/fps into the action
     (clears drift). Blender can only express loop yes/no; a cfg loop
     point `N>0` stays in the cfg, read-only here.
4. Pose + keyframe in the timeline as usual. The armature's active action
   is the segment; keys land there.
5. **Add segment** — type a name + first frame / frames / loop point / fps
   and press **Add segment**. The row is appended **and the cfg is saved
   immediately** (line-preserving write: untouched lines are byte-identical).

Loop-point semantics (engine): `-1` = no loop, `0` = loop from the segment
start (the standard looping marker — every base-game loop uses it), `N>0`
= loop point inside the segment.

**New segment names:** the engine knows a fixed enum of animation names
(~1,589). A name it does not know gets a red engine warning and is
**ignored** (the check surfaces this as a warning — see §4). New tokens
require a two-line engine-side addition (see the
[validation reference](reference/validation.md#new-anim-names)).

### 3.4 Finger presets

Keying the 12 engine finger bones (`l/r_d1_j1, d1_j2, d2_j1, d2_j2,
d4_j1, d4_j2`) by hand is fiddly. The **Fingers** box poses them in one
click, **relative to wherever each hand currently is** (the hands are
never touched):

| Button | What it is |
|--------|------------|
| **Grasp** | Halfway between fist and open (per-bone slerp midpoint). |
| **Fist** | Clenched blaster grip — derived from `BOTH_P6_S6_TR` (the right-hand grip frame + its mirror). |
| **Open** | Relaxed weapon-stand hand — `BOTH_STAND1`. |

Behavior: if the armature has an active action, the 12 bones are **keyed
at the current frame**; otherwise they're posed without keys (the Results
box says which happened). Typical use: scrub to a frame, click a preset,
key the rest of the body around it.

### 3.5 Importing a `.xsi` clip (Max-authored animation) — status

Classic JKA clips were authored in 3ds Max and exported as Softimage|XSI
dotXSI files on the JKA character skeleton. The suite's `.xsi` pipeline
lives in the shipped `lib\animkit` (`xsi.py` parser + `xsigrift.py`
graft): parse the dotXSI, re-express every bone onto the stock skeleton's
local frames, graft the frames into the `_humanoid` GLA pool, and add the
cfg segment.

**Status in v0.1.0:** the pipeline is a **headless script pipeline, not a
panel button yet.** The pilot (`BOTH_WALK_MINIGUN`) ran it end to end and
passed the in-engine check (decision #19); the general case — a panel
import face plus the 4 remaining Max clips — is the next release's work.
For now, the interactive path is §3.1–3.4 (reference matching + keying).

### 3.6 Export GLA

In **Export GLA**:

- **Base Path** — your mod folder.
- **Output File** — absolute path of the `.gla` to write. It **must sit
  inside** the Base Path (the in-GLA name is derived from it).
- **GLA Path** — the base-relative name stored *inside* the GLA, e.g.
  `models/players/mychar/mychar.gla` or
  `models/players/_humanoid/_humanoid.gla` when appending to the shared
  skeleton.
- **Reference** — base-relative reference GLA used to copy **bone
  indices** (default `models/players/_humanoid/_humanoid.gla`). Must be
  base-relative; absolute paths fail with "Could not find reference GLA".
- **Custom frame range** — off (default): the scene's current frame range
  is exported; on: the two frame fields.

Press **Export GLA**. It exports `skeleton_root` via the jediacademy
add-on and restores the legacy Ghoul2 scale (0.64 on the stock
`_humanoid`; the value comes from the GLA's `fScale`).
**Then run the check** (§3.7) — the export path is byte-stable, but the
gate is what proves the file is engine-legal.

Two export caveats (both reproducible):

- **Never export a raw rig `.blend`.** Prep first (§3.2) — otherwise the
  first frame is degenerate (all bones collapse to the root origin).
- **A frame exactly at rest encodes degenerate.** The exporter writes
  frames as deltas from the Blender rest pose; a perfectly-at-rest frame
  becomes an all-identity pool entry, which the engine decodes as every
  bone at the root origin. Near-rest frames are fine — authored segments
  (walks, swings, idles) will not sit exactly at rest.

### 3.7 Run check (the validation gate)

The **Check** box uses the Segments box's **Cfg Base Path + Character**.
Press **Run check**: it validates the whole directory the way the engine
parses it — GLM, GLA, `animation.cfg`, `animevents.cfg`, `model_default.skin`
— and fills the **Results** box:

1. A summary line: `check <name>: OK (N warnings)` or
   `check <name>: FAILED (N errors, M warnings)` — the summary line carries
   the error icon when the check failed.
2. Every **error** (red): the engine rejects this file or reads it
   corruptly. Must be fixed before shipping.
3. Every **warning**: the engine *tolerates* this (tolerance is
   documented per finding) — review, usually fix, sometimes accept.

A **clean check is necessary but not sufficient**: it proves the file is
engine-legal, not that the animation looks right. The final gate is
§3.8.

`Character` may also be the skeleton dir name `_humanoid` — a skeleton-only
dir (GLA + cfgs, no `model.glm`) validates fine (the engine never loads it
as a character; you'll see one informational warning).

### 3.8 In-engine play (final gate)

Launch the mod in your engine build (OpenJK / JKA: Enhanced) and play the
character / segment in a map. On the development side this runs on the
shared gdesk VM (OpenJK build + the mod's pk3, `+map academy1`); on your
side any working launch that loads the character is the same check.

What you're looking for:

- The **segment resolves** — no `WARNING: Unknown token` for your segment
  name at load (new tokens need the engine-side addition,
  [validation ref](reference/validation.md#new-anim-names)).
- The character **plays the motion** (no T-posing, no missing-anim
  stutter, no floating limbs).
- Fingers/hands look like the presets you keyed (no teleported fingers —
  the presets are hand-relative, so this also catches a rig that isn't
  the `_humanoid` skeleton).

---

## 4. Troubleshooting

Everything below is a **real message from the shipped code** — exact
text, what it means, what to do.

### 4.1 Check findings (from `Run check`)

*Directory / model*

| Message (abridged) | Severity | Meaning / fix |
|---|---|---|
| `model.glm not found` | error | The dir has neither a model nor a `.gla`. A skeleton-only dir needs at least one `.gla` (you'll get an informational warning instead). |
| `skeleton dir (no model.glm) — checking X + cfgs only` | warning | Informational: the engine never loads this as a character; only the GLA + cfgs were checked. |
| `numBones=0` / `numLODs=0` | error | The GLM header is corrupt or truncated. |
| `surface 'X' bone ref N out of range (numBones=M)` | error | A surface references bone N which doesn't exist. Re-export the model or fix the weighting. |
| `surface 'X' triangle indexes out of range` | error | A triangle points past the vertex array — corrupt geometry. |
| `surface 'X': N/M verts reference a bone index >= K ... the engine reads this OOB (no bounds check, tr_ghoul2.cpp) ...` | warning | Those vertices skin to whatever the out-of-bounds bytes give (undefined). Fix the weighting to reference only the surface's listed bones. |
| `surface 'X' has no geometry in any LOD` | warning | An empty surface; harmless but usually a mistake. |
| `duplicate surface names in hierarchy` | error | Two surfaces share a name — the engine can't disambiguate. |
| `no surface at hierarchy index 0 (engine expects one)` | error | Hierarchy table is malformed. |
| `surface 0 'X' has parent N (engine expects root -1)` | warning | The root surface should have no parent. |
| `referenced animation 'X' not found (tried: ...)` | error | The GLM's `animName` points at a GLA that isn't where the engine looks (character dir, parent dir, or the `models/` root). |

*GLA (the animation file)*

| Message | Severity | Meaning / fix |
|---|---|---|
| `bone 0 'X' parent=N (engine expects root with parent -1)` | error | The first bone must be the root. |
| `bone i 'X' has parent -1 (only bone 0 may be root)` | error | Exactly one root, at index 0. |
| `bone i 'X' parent N out of range` / `child N out of range` | error | The hierarchy table references a non-existent bone. |
| (parse failure, e.g. truncated header) | error | The file is not a valid v6 GLA — don't hand-edit bytes; re-export. |
| `GLM has 53 bones, GLA has 72 — engine remaps between JK2(72)/JKA(53) humanoid skeletons` | warning | The JK2/JKA skeleton remap; expected when mixing JK2-derived GLAs. |
| `bone count mismatch: GLM N vs GLA M` | error | The GLA's skeleton doesn't match the model's. |

*animation.cfg*

| Message | Severity | Meaning / fix |
|---|---|---|
| `not found (tried: ...) — the engine cannot play this model` | error | The character has no segment table. Add `animation.cfg` (or `<skeleton>.cfg`). |
| `line N: 'X' firstFrame F < 0` | error | Negative start frame — fix the segment row. |
| `line N: 'X' loopFrames=L outside engine range -1..127 (parser would assert)` | error | The engine asserts this range; -1 (no loop) .. 127. |
| `line N: 'X' runs to frame L but GLA only has F frames (0..F-1)` | error | The segment extends past the end of the GLA. Add the frames (export) or shorten the segment. |
| `line N: 'X' firstFrame F >= GLA frame count` | error | The segment starts past the end of the GLA. |
| `line N: 'X' is not a known engine anim name — the game will WARN and IGNORE this segment` | warning | The engine has no such token. Fix the name, or add the token to the engine ([below](#new-anim-names)). |
| `line N: duplicate segment 'X' (last one wins)` | warning | Two rows, one name — the second silently wins. |
| `line N: 'X' fps=0 (engine clamps to 1)` | warning | The engine substitutes 1; set a real fps. |
| `line N: 'X' loopFrames=L exceeds numFrames=N (loop extends past the segment)` | warning | The loop point is outside the segment. |

*animevents.cfg*

| Message | Severity | Meaning / fix |
|---|---|---|
| `line N: event on 'X' — no matching segment in animation.cfg (event will never fire)` | warning | The event's animation doesn't exist as a segment; dead data. |
| `line N: 'AEV_...' keyFrame K outside segment 'X' (0..N-1)` | error | Key frames are **relative to the segment start**, range 0..numFrames-1. |
| `line N: sound range lo..hi unusual` | warning | Expected `0 < lo <= hi` for AEV_SOUND. |
| `line N: chance C outside 0..100` | warning | Probabilities are 0–100. |
| `line N: unknown footstep 'X' — the engine (case-insensitive) will treat it as an invalid type` | warning | Use one of the engine's footstep types (e.g. `FOOTSTEP_R`, `FOOTSTEP_L`, `FOOTSTEP_HEAVY_R`, `FOOTSTEP_HEAVY_L`). |

*model_default.skin*

| Message | Severity | Meaning / fix |
|---|---|---|
| `line N: surface 'X' not in model (engine ignores it)` | warning | A skin entry for a surface the GLM doesn't have — ignored, dead data. |
| (parse/read failure) | error | The skin file is unreadable/corrupt. |

**If a check itself crashes** (`check crashed on ...`), that is a *tool
bug*, not a finding about your files — the operator reports it as an error
rather than a failed check. Report it; don't paper over it.

### 4.2 Panel errors (operator `JkaError`s)

| Message | Fix |
|---|---|
| `set the Base Path and Character (cfg section) first` | Fill the Segments box fields. |
| `no segments loaded — press Load in the Segments box` | Press **Load segments** first. |
| `pick the target segment (Events box)` / `target segment selection is stale — press Load (Segments)` | Choose a segment in the Events dropdown (it lists the loaded segments); re-Load if the table changed. |
| `give the new segment a name` / `segment 'X' already exists` | Name it uniquely. |
| `no action named 'X' — press Jump (create) first` | **Jump to segment** with create on, then **Apply to action**. |
| `action 'X' has no g2_sequence_prop (created outside the jediacademy importer)` | The action predates the importer's property; recreate it via Jump. |
| `no saberanims.cfg at X — the engine uses its built-in style sheet` | Informational: the sheet is optional. |
| `write blocked — see the Results box` | Validate-on-write failed; the `animevents.cfg` file was **not touched** — read the red lines. |
| `check: no such directory: ... — expected a character or skeleton dir under models/players/ in the basepath` | Cfg Base Path + Character must resolve to `<base>\models\players\<character>`. |
| `no armature in the scene (load the IK rig first)` / `bone 'X' missing from ... — the rig must be the _humanoid skeleton` | The finger presets need the `_humanoid`-skeleton rig loaded. |
| `NOT keyed (no active action on the armature)` | Informational: the preset posed the fingers but there was no active action to key into. |
| `Could not find reference GLA` (jediacademy) | The Export **Reference** field must be **base-relative**. |

### 4.3 New anim names

A segment name that isn't in the engine's enum produces the red
"not a known engine anim name" warning and the segment is ignored in
game. Registering a new token is a two-line engine change (one enum entry
in `code/game/anims.h` + one `ENUM2STRING` row in `code/cgame/animtable.h`)
— that's how `BOTH_WALK_MINIGUN` landed (PR #1 on the OpenJK fork). Until
the token is registered, the segment is Blender-side data only.

### 4.4 Recurring gotchas

- **Drifted actions** (the `* action differs from the cfg` line): press
  **Apply to action** on the selected row — it writes the cfg's loop/fps
  back and clears the flag.
- **The cfg resolves from the skeleton dir, not the character dir.** For
  `_humanoid`-skeleton characters the engine reads
  `models\players\_humanoid\animation.cfg` — so appending a segment to a
  *shared* skeleton means the cfg edit lands there. Point the Segments box
  at `_humanoid` when working on the shared skeleton.
- **Saved `.blend` is never touched by the suite** — prep is in-memory;
  the cfg/GLA files are the only things written (and only by the explicit
  save/export buttons).
- **`animkit` import errors** (`animkit ... did not load`): the AnimKit
  Dir is wrong — it must contain the `animkit\` folder, not be the folder
  itself.
