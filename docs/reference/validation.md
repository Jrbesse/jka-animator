# The validation gate (`check`)

`jka_anim.check_run` (panel) runs **animkit's `check`** (`animkit/check.py`)
over a character or skeleton directory. It validates the files the way
the engine would parse them and reports exactly what the engine would
reject or warn about — engine-mirrored severity.

**Input:** `<base>/models/players/<character>` — a real character (with
`model.glm`) or a **skeleton-only dir** (a `.gla` + cfgs, no `model.glm`,
e.g. `_humanoid`; the engine never loads such a dir as a character, so its
GLA + cfgs are validated directly, with one informational warning).

**Output:** the Results collection —
1. a summary line: `check <name>: OK (N warnings)` or
   `check <name>: FAILED (N errors, M warnings)` (error icon when failed;
   N/M are the UN-condensed totals),
2. every error (`[file] message`, never condensed), then the warnings
   **condensed per warning type**: N findings of the same type in one
   file collapse to `[file] ×N <first message> (lines a-b, c)` — a group
   of one prints unchanged (no line suffix when the type carries no line
   numbers).

**Severity model:**
- **error** — the engine rejects the file or reads it corruptly. Must fix.
- **warning** — the engine *tolerates* it, and the tolerance is
  documented per finding (e.g. "the engine reads this OOB (no bounds
  check)"). Review; usually fix, sometimes accept.
- A **crash inside animkit's check** (unexpected exception) is reported as
  a tool bug (`check crashed on <dir>: ...`), never as a passing/failed
  check.

**Scope note:** a clean check is necessary but not sufficient — it proves
the file is engine-legal, not that the animation looks right. The final
gate is the in-engine play check ([testing.md](testing.md)).

---

## Directory

| Condition | Severity | Message |
|-----------|----------|---------|
| No `model.glm` and no `.gla` | error | `[<dir>] model.glm not found` |
| No `model.glm`, a `.gla` present | warning | `[<dir>] skeleton dir (no model.glm) — checking <first .gla> + cfgs only` |

## model.glm

| Condition | Severity | Message |
|-----------|----------|---------|
| Parse failure | error | `[model.glm] <GlError>` |
| `numBones <= 0` | error | `[model.glm] numBones=<n>` |
| `numLODs <= 0` | error | `[model.glm] numLODs=<n>` |
| Surface bone ref out of range | error | `[model.glm] surface '<s>' bone ref <r> out of range (numBones=<n>)` |
| Triangle index out of range | error | `[model.glm] surface '<s>' triangle indexes out of range` |
| Vertex bone ref ≥ surface's bone_ref count | **warning** | `[model.glm] surface '<s>': <bad>/<total> verts reference a bone index >= <n> but the surface lists only <n> bone_refs (first at vert <v>) — the engine reads this OOB (no bounds check, tr_ghoul2.cpp), so those verts skin to whatever the OOB bytes give` — the engine dereferences `piBoneReferences[ref]` as a raw pointer with no bounds check (tr_ghoul2.cpp:1981/2084/2945), so this is undefined-but-tolerated → warning, not error. |
| Surface with no geometry in any LOD | warning | `[model.glm] surface '<s>' has no geometry in any LOD` |
| Duplicate surface names | error | `[model.glm] duplicate surface names in hierarchy` |
| No surface at hierarchy index 0 | error | `[model.glm] no surface at hierarchy index 0 (engine expects one)` |
| Surface 0 has a parent | warning | `[model.glm] surface 0 '<s>' has parent <p> (engine expects root -1)` |
| GLM's `animName` GLA not found | error | `[model.glm] referenced animation '<name>.gla' not found (tried: <candidates>)` — candidates: character dir, parent dir, and the pak-relative path anchored at the `models/` root (the shared `_humanoid` skeleton fallback). |

## model.gla (the referenced GLA, or the skeleton dir's GLA)

| Condition | Severity | Message |
|-----------|----------|---------|
| Parse failure | error | `[model.gla] <GlaError>` |
| Bone 0 has a parent | error | `[model.gla] bone 0 '<b>' parent=<p> (engine expects root with parent -1)` |
| Non-zero bone has parent -1 | error | `[model.gla] bone <i> '<b>' has parent -1 (only bone 0 may be root)` |
| Parent index out of range | error | `[model.gla] bone <i> '<b>' parent <p> out of range` |
| Child index out of range | error | `[model.gla] bone <i> '<b>' child <c> out of range` |
| Hierarchy cycle (topo sort fails) | error | `[model.gla] <GlaError from the playback topo sort>` |
| GLM vs GLA bone count, the 53/72 pair | **warning** | `[model.gla] GLM has <n> bones, GLA has <m> — engine remaps between JK2(72)/JKA(53) humanoid skeletons` |
| GLM vs GLA bone count, anything else | error | `[model.gla] bone count mismatch: GLM <a> vs GLA <b>` |

## animation.cfg

Resolved from the **skeleton** dir the engine way (`<skeleton>.cfg` →
`animation.cfg` — see [formats.md](formats.md)).

| Condition | Severity | Message |
|-----------|----------|---------|
| Not found | error | `[animation.cfg] not found (tried: <candidates>) — the engine cannot play this model` |
| Parse failure | error | `[animation.cfg] <CfgError>` |
| Parse warnings (unknown tokens, etc.) | warning | `[animation.cfg] <warning>` |
| Duplicate segment name | warning | `[animation.cfg] line <n>: duplicate segment '<s>' (last one wins)` |
| Unknown engine anim name | warning | `[animation.cfg] line <n>: '<s>' is not a known engine anim name — the game will WARN and IGNORE this segment` — see [new anim names](#new-anim-names). |
| `firstFrame < 0` | error | `[animation.cfg] line <n>: '<s>' firstFrame <f> < 0` |
| `fps == 0` | warning | `[animation.cfg] line <n>: '<s>' fps=0 (engine clamps to 1)` |
| `loopFrames` outside −1..127 | error | `[animation.cfg] line <n>: '<s>' loopFrames=<l> outside engine range -1..127 (parser would assert)` |
| `loopFrames > numFrames` | warning | `[animation.cfg] line <n>: '<s>' loopFrames=<l> exceeds numFrames=<n> (loop extends past the segment)` |
| Segment runs past the GLA | error | `[animation.cfg] line <n>: '<s>' runs to frame <L> but GLA only has <F> frames (0..<F-1>)` |
| `firstFrame >=` GLA frame count | error | `[animation.cfg] line <n>: '<s>' firstFrame <f> >= <F>` |

## animevents.cfg

| Condition | Severity | Message |
|-----------|----------|---------|
| Parse failure | error | `[animevents.cfg] <CfgError>` |
| Parse warnings | warning | `[animevents.cfg] <warning>` |
| Event on an unknown segment | warning | `[animevents.cfg] line <n>: event on '<s>' — no matching segment in animation.cfg (event will never fire)` |
| Key frame outside the segment | error | `[animevents.cfg] line <n>: '<AEV_...>' keyFrame <k> outside segment '<s>' (0..<num-1>)` |
| `AEV_SOUND` range `lo..hi` unusual | warning | `[animevents.cfg] line <n>: sound range <lo>..<hi> unusual` (expected `0 < lo <= hi`) |
| `AEV_SOUND` chance outside 0..100 | warning | `[animevents.cfg] line <n>: chance <c> outside 0..100` |
| Unknown footstep type | warning | `[animevents.cfg] line <n>: unknown footstep '<t>' — the engine (case-insensitive) will treat it as an invalid type` |

## model_default.skin

| Condition | Severity | Message |
|-----------|----------|---------|
| Parse warnings | warning | `[model_default.skin] <warning>` |
| Surface entry not in the model | warning | `[model_default.skin] line <n>: surface '<s>' not in model (engine ignores it)` |
| Read failure | error | `[model_default.skin] <OSError>` |

(Absent skin file = no check; the engine handles missing skins on its own.)

---

## Engine limits (source-verified)

The constants the rules above encode, from the OpenJK source
(`code/rd-common/mdx_format.h`, `code/qcommon/q_shared.h`,
`code/game/NPC_stats.cpp`):

| Limit | Value | Source |
|-------|-------|--------|
| Bone refs per surface | **32** (5-bit packed refs, `1<<iG2_BITS_PER_BONEREF`) | `iMAX_G2_BONEREFS_PER_SURFACE` (mdx_format.h:84) |
| Bone weights per vertex | **4** | `iMAX_G2_BONEWEIGHTS_PER_VERT` (mdx_format.h:85) |
| Name field (GLM/GLA/surface/bone) | **64 bytes** | `MAX_QPATH` (q_shared.h:207) |
| `firstFrame` range | `0 <= firstFrame < 65536` | `G_ParseAnimationFile` assert (NPC_stats.cpp) |
| `loopFrames` range | `-1 .. 127` | `G_ParseAnimationFile` assert (NPC_stats.cpp) |
| `AEV_MOVE` push fields | `±32767` | NPC_stats assert |
| GLA quat quantization | grid 1/16383 over [−2, 2] | matcomp.cpp `MC_UnCompressQuat` |
| GLA translation quantization | grid 1/64 over [−512, 511] | matcomp.cpp |
| Vertex weight quantization | `val/1023` | `fG2_BONEWEIGHT_RECIPROCAL_MULT` |

## New anim names

A segment/event name outside the engine's enum (~1,589 names) is a
warning — the engine red-warns and **ignores** it. Registering a new
token is a two-line engine change:

1. `code/game/anims.h` — add the enum entry before `MAX_ANIMATIONS`
   (existing IDs stay stable; append, don't insert mid-table).
2. `code/cgame/animtable.h` — add `ENUM2STRING(<TOKEN>)` before the
   `{ NULL, -1 }` terminator (the table is a string→enum lookup list, not
   position-dependent).

That is exactly how `BOTH_WALK_MINIGUN` landed (PR #1 on the OpenJK
fork, in-engine verified: the token resolved to a real anim index at
boot on the live mod, and a bogus control token resolved to −1 — proof
the cfg was parsed and the resolution was real). Note the `codemp/`
tree (the optional MP build) is a diverged subset and does **not** need
the edit for an SP build.
