# Format notes — cfgs, GLA, GLM

The engine is ground truth (OpenJK source: `code/game/NPC_stats.cpp`,
`code/rd-common/mdx_format.h`, `shared/rd-rend2/tr_ghoul2.cpp`,
`code/qcommon/matcomp.cpp`). `jka-animkit` is the reference
implementation of these formats (parsers + the `check` gate); the
add-on's cfg layer imports animkit and never re-parses.

## animation.cfg

**Grammar** — flat 5-token lines, no braces:

```
<ANIM_NAME> <firstFrame> <numFrames> [loopFrames] [fps]
```

Engine parser facts (`G_ParseAnimationFile`, NPC_stats.cpp):

- Fields are read with `atoi`/`atof`: `"12abc"` → 12, `"abc"` → 0 (the
  engine asserts ranges in debug but keeps going; the parser mirrors that
  and warns instead of raising).
- The engine counts a line as a segment iff `loopFrames != -1` — and an
  **absent** `loopFrames` reads as -1, so it is still a segment.
- `loopFrames`: `-1` = no loop; `0` = loop from the segment start (the
  standard looping marker — every base-game looping anim uses it, e.g.
  `BOTH_RUN1`, `BOTH_WALK1`, `BOTH_STAND1`); `N>0` = loop point inside
  the segment. Asserted range: `-1 <= loopFrames < 128`.
- `firstFrame` is 0-based into GLA frames (asserted `0 <= firstFrame <
  65536`); `numFrames` is a count; `fps` frames per second (negative =
  backwards; 0 is clamped to 1 by the engine).
- Unknown `ANIM_NAME` → red warning, segment **ignored** (the cfg still
  loads). `ROOT` is a recognized skeleton marker, not an error.
- The parse buffer caps cfg size at 80,000 bytes.
- **No `+model` lines** (that is the JA1 shape).

**Path resolution (engine and `check` mirror it):** the cfg resolves
relative to the *skeleton*, not the character:
`models/players/<skeleton>/<skeleton>.cfg`, falling back to
`models/players/<skeleton>/animation.cfg`. Characters on the `_humanoid`
skeleton therefore read `models/players/_humanoid/animation.cfg` — not
their own dir. One GLA per skeleton: `models/players/<skeleton>/<skeleton>.gla`.

**The add-on's contract:** for any engine-acceptable cfg, the writer
re-emits byte-identical **modulo `//` comments** — untouched lines
re-emit from their original source (CRLF/tabs/alignment survive). `Save`
is validate-on-write.

## animevents.cfg

**Grammar** — braced blocks of flat event lines (no per-event braces):

```
LOWEREVENTS
{
  <ANIM_NAME> <AEV_TYPE> <keyFrame> <event data...>
  ...
}
UPPEREVENTS
{
  ...
}
```

Engine parser facts (`G_ParseAnimationEvtFile` + `ParseAnimationEvtBlock`,
NPC_stats.cpp):

- The top level accepts the file headers `LOWEREVENTS` / `UPPEREVENTS`
  (unknown top-level tokens are skipped by the engine). The engine's
  constants are `LOWER` / `UPPER` — the panel speaks engine names and
  normalizes to the file headers.
- Per line: `ANIM_NAME` is matched case-insensitively; unknown → the rest
  of the line is skipped (no event stored). Unknown/absent `AEV_TYPE` →
  the line effectively dies the same way.
- **Line-confinement:** a malformed token stops parsing *that line only*;
  the block continues.
- `keyFrame` is `atoi`d and **clamped to `numFrames-1`** (with a warning
  when out of range) — it is relative to the segment's start, i.e. valid
  range `0..numFrames-1`.
- `AEV_SABER_SWING` / `AEV_SABER_SPIN` are valid names with **no switch
  case** — the engine silently discards those lines (file-level saber
  swings come from `AEV_SOUND` with saber sound paths, converted at
  runtime). They are therefore not editable in the panel.

**The editable `AEV_*` types** — exactly the NPC_stats switch cases, with
the data fields the engine actually reads (panel help text, same order):

| Type | Data fields |
|------|-------------|
| `AEV_SOUND` | `soundPath lowest highest chance` |
| `AEV_SOUNDCHAN` | `chan soundPath lowest highest chance` |
| `AEV_FOOTSTEP` | `footstepType probability` (types: `FOOTSTEP_R/L`, `FOOTSTEP_HEAVY_R/L`, case-insensitive) |
| `AEV_EFFECT` | `effectPath boltName probability` (`special` = hard-coded effect; bolt `none`/`NULL` = none) |
| `AEV_FIRE` | `altfire probability` |
| `AEV_MOVE` | `forwardPush rightPush upPush` (asserted ±32767) |

**Validate-on-write** (shared with `check`): events on unknown segments
warn (they will never fire); key frames outside the segment are errors;
`AEV_SOUND` range/chance and footstep types are range-checked.

## saberanims.cfg

`<base>/ext_data/saberanims.cfg` — **optional**: the engine falls back to
its built-in `s_defaultStyleSheet` (wp_saber.c) when absent, so a missing
file is not an error (the validate op says so in Results).

- 7 styles: `fast`, `medium`, `strong`, `desann`, `tavion`, `dual`,
  `staff`.
- Per style, `openAnim` = the attack (entry swing) anim; every style's
  `neutralAnim` = `BOTH_STAND1` (the guard preset).
- Built-in fallback `openAnim` values: fast `BOTH_H1_S1_TR`, medium
  `BOTH_H1_S1_T_`, strong `BOTH_H1_S1_BL`, desann `BOTH_H1_S1_BR`, tavion
  `BOTH_H1_S1_TL`, dual `BOTH_H6_S6_T_`, staff `BOTH_H7_S7_T_`.
- Preset defaults for a **new** segment: `num=20`, `fps=20`, `loop=-1`
  (swings don't loop); new segments start at `max(first+num)` over the
  loaded table. For an **existing** segment the cfg is the truth.

## GLA (Ghoul2 animation, v6)

**Header** (100 bytes, little-endian, struct `<ii64sf6i`):
`ident` ("2LGA"), `version` (6), `name[64]`, `fScale` (model scale, e.g.
0.64), `numFrames`, `ofsFrames`, `numBones`, `ofsCompBonePool`, `ofsSkel`,
`ofsEnd`. (The name field is **64 bytes** — `MAX_QPATH`; reading it as
1024 shifts every later offset to garbage.)

**Skeleton table** @ `ofsSkel`: one record per bone, `<64s I i 12f 12f i`
(172 bytes base + child ints): name, flags, parent index (-1 = root),
`BasePoseMat` (3×4 row-major, translation at columns 3/7/11), child
indices.

**Frame pool** @ `ofsFrames`: `numFrames × numBones` 3-byte LE pool
indices; byte offset for (frame, bone) = `frame*numBones*3 + bone*3`,
value = `b0 | b1<<8 | b2<<16`. The pool indexes the compressed bone pool.

**Compressed bone pool** @ `ofsCompBonePool`: 14 bytes/bone = 7 × u16 —
quaternion w,x,y,z as `u/16383 − 2.0` (grid 1/16383 over [−2, 2]) and
translation x,y,z as `u/64 − 512` (grid 1/64 over [−512, 511]).
`pool size = (ofsEnd − ofsCompBonePool)/14`; the max index in the frame
table must be < pool size. The frame pool and compressed pool are
adjacent: `ofsFrames + numFrames×numBones×3 == ofsCompBonePool`.

**Playback** (rend2): decompress (the exact inverse above), then walk the
bone chain (`final[0] = rootMatrix @ local[0]`;
`final[b] = final[parent] @ local[b]`). For JA player models
(`GHOUL2_NEWORIGIN` unset) `rootMatrix` is **not** the mathematical
identity — it is the 90°-about-Z `identityMatrix` (rows
`(0,−1,0,0),(1,0,0,0),(0,0,1,0)`). Vertex skinning uses the **SmoothLow
round trip** of the walk (temporal mix at `r_ghoul2animsmooth=0.3` +
base-pose re-normalization), not the raw walk.

**Writer caveat (the C2 trap):** decoded pool quaternions are generally
non-unit (u16 quantization), and an **all-identity pool decodes to every
bone at the root origin**, not the base pose — "identity" ≠ "at rest" in
this format. A writer that encodes frames as deltas from the Blender rest
pose emits an all-identity pool for an exactly-at-rest frame; near-rest
frames are fine.

## GLM (Ghoul2 model, v6)

**Header** (164 bytes, `<ii64s64s7i`): `ident`, `version`, `name[64]`,
`animName[64]` (the pak-relative GLA name, e.g.
`models/players/_humanoid/_humanoid`), `animIndex`, `numBones`, `numLODs`,
`ofsLODs`, `numSurfaces`, `ofsSurfHierarchy`, `ofsEnd`.

- **LODs** @ `ofsLODs`: repeated `numLODs` times; per LOD = `[ofsEnd]` +
  a `numSurfaces`-int surface-offset table + the surface data. The LOD
  `ofsEnd` is **relative to the current LOD header** (the engine walks
  `lod += lod->ofsEnd`) — not file-absolute.
- **Surface hierarchy table** @ `ofsSurfHierarchy`: records
  `<64s I 64s 3i>` (name, hierarchy index, parent name + 3 ints).
- **Surface header** (40 bytes, 10 ints): ident, thisSurfaceIndex,
  ofsHeader, numVerts, ofsVerts, numTriangles, ofsTriangles,
  numBoneReferences, ofsBoneReferences, ofsEnd — **all offsets relative
  to the surface header**.
- **Vertex: 32 bytes** = normal (3f) + coords (3f) + packed uint + 4
  weight bytes. **No inline UVs** — texCoords live in a separate vec2 (8
  B) array immediately after the vertex array.
- **Vertex packing:** bone refs at bits 0/5/10/15 (5 bits each → max 32
  refs/surface), weight count at bits 30:31 (max 4 weights/vert), weight
  = `val/1023` (the last weight = 1 − sum). A vertex's bone ref indexes
  the surface's `bone_refs` list (global bone = `bone_refs[ref]`).

**Engine limits** (the ones that matter when a check finding fires —
full rule list in [validation.md](validation.md)): 32 bone refs/surface,
4 weights/vert, 64-byte names, `loopFrames` −1..127, `firstFrame`
< 65536.

## The Blender NLA mapping (the suite's contract)

- Actions are named **exactly** the cfg segment name (the jediacademy
  importer's convention; the engine fires saber/cfg references by that
  name).
- `g2_sequence_prop` = a PropertyGroup on the Action: `loop_frame` (bool)
  + `fps` (int). Import maps `loopFrames` → bool (true iff `!= -1`).
- The cfg **export** writes `loopFrames` as `0` (loop) or `-1` (no loop) —
  a loop point `N>0` is **not expressible** through Blender. The panel
  displays `N>0` read-only; edits are the loop bool + fps.
- Drift detection: per segment, compare the action's props against the
  cfg's expected props (a loop point `N>0` reads back as "loop", so `0`
  and `N>0` are indistinguishable after import — expected).
