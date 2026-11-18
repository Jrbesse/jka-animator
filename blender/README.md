# Blender export path for JKA animations (S1, signed off 2026-11-17)

The animation export path is the community **mrwonko/cagelight "Jedi Academy
Import/Export Tools" addon (v2.1.0)** — not a home-grown exporter. It was
validated against `jka-animkit` (engine-strict) on Blender 5.3.0: skeleton
export is byte-compatible with `_humanoid` (53/53 bones), and a 240-frame
round-trip reproduces a genuine Raven engine file within compression
tolerance. Evidence + the two caveats below: `plans/handoff-2026-11-17-v15.md`
in `Jrbesse/openjk-support`, and `docs/ik-rig/` in this repo.

## Licensing (read once)

The addon is **GPL v2+** (header in every file). Usage rule: **run it as an
installed Blender addon, never port its code into this repo or jka-animkit**
(copyleft would apply to those repos). The addon zip + manual are kept in
`fixtures/blender-addon/` (gitignored — do not commit).

## Install (once, per Blender)

Blender 4.1+ (5.3.0 verified). User Preferences > Add-ons > *Install from
File* > select `jediacademy.zip` > enable *Import-Export: Jedi Academy
Import/Export Tools*.

## Export workflow

1. **Open the rig** (or character scene) in Blender.
2. **Prep the rig** — the saved pose state of the JustJordyn rig is
   contaminated (stored pose offset + 82 IK constraints, no actions);
   exporting it raw writes a degenerate frame stream. Run
   `prepare_rig.py` (Text Editor > Run, or headless): it strips the IK
   constraints and zeroes the pose offsets **in memory only** — the .blend
   is never saved.
3. **Set the frame range** on the scene (the rig file ships 0..0; the range
   you export is the stream you get).
4. **Export** via File > Export > *JA Ghoul 2 Skeleton & Animation (.gla)*:
   - *Base Path*: your mod folder (the folder that contains `models/...`)
   - *gla name*: base-relative, e.g. `models/players/mychar/mychar.gla`
   - *gla reference*: **base-relative**, e.g.
     `models/players/_humanoid/_humanoid.gla` — this copies the bone
     INDICES from the reference so the export lines up with existing
     models. Absolute paths fail ("Could not find reference GLA").
5. **animkit gate (non-negotiable):**
   ```
   python -m animkit check <character-dir>     # engine-strict validation
   python -m animkit diff <new> <old>          # when replacing a skeleton
   ```
   plus the in-engine play check on the gdesk VM before anything ships.

One-shot headless equivalent of steps 2+4:

```
blender --background rig.blend --python blender/prepare_rig.py -- \
    --export out.gla --basepath /path/to/modfolder \
    --glapath models/players/mychar/mychar.gla \
    --ref models/players/_humanoid/_humanoid.gla \
    --frame-start 0 --frame-end 239
```

## Animation matching (S2, signed off 2026-11-17)

The adopted path: load the reference .gla **into the rig's scene** as a
second armature, scrub it, and pose the rig to match. Verified end-to-end
(2026-11-17, Blender 5.3.0): three armatures coexist (IK_Rig 64 bones,
rig_armature 53, reference_humanoid 53), the reference animates
independently, the rig stays untouched, and the export afterwards is
byte-identical to a non-matched export.

**The name trap (why `load_reference.py` exists):** the addon's importer
reuses ANY existing object OR armature data-block named `skeleton_root` —
naively importing into the rig scene would keyframe the reference onto the
rig's mirror armature. Worse, in the JustJordyn rig the IK_Rig armature's
*data-block* is also named `skeleton_root`. `load_reference.py` renames
both out of the way, imports (fresh armature), and renames the result to
`reference_humanoid`.

Interactive (the normal flow — matching is visual work):

1. Open the rig in Blender (addon installed).
2. Text Editor: run `load_reference.py` with the reference path
   (or just run it and edit the `_arg` defaults; see `--gla/--basepath`).
3. Scrub the timeline — `reference_humanoid` plays, `rig_armature` is
   yours. Pose the rig to match (select pose bones on `rig_armature`,
   insert keyframes into a new action for the take).
4. Run `prepare_rig.py` — it renames `rig_armature` back to
   `skeleton_root` automatically, strips, restores scale, exports.
5. animkit gate (below), then in-engine play check.

Headless notes:

- `blender --background rig.blend --python load_reference.py -- ...`
  and `--python prepare_rig.py -- ...` work as separate invocations, but
  **two `--python` blocks do NOT chain on one command line** (Blender CLI:
  everything after the first `--` is consumed as the first script's args).
  For one-process runs, drive both from a single script (each reads args
  after `--`).
- `--mode cfg` (NLA strip per animation.cfg segment) is the comfortable
  mode for scrubbing named sequences; it is slow on big skeletons
  (26K-frame `_humanoid` needs several minutes on a container CPU).
  `--mode range` is fast and fine for single-segment probes.

## Fingers (R3)

Key them directly — no controls needed in the addon: each hand has the six
engine finger bones (`l_d1_j1 … r_d4_j3`, four fingers × three joints, no
thumbs — the engine has none). The engine parents fingers under `radius`,
so they rotate in the hand's frame; key the joint pose bones directly
(relative to the hand as posed) and the exporter writes all 53 bones —
per-bone fidelity including finger joints is covered by the round-trip
validation. In a matched session, key them on `rig_armature` while
`reference_humanoid` shows the target hand pose.

## Caveats (reproducible — details in the v15 handoff)

- **C1 — never export the rig .blend as-is.** Run `prepare_rig.py` first
  (or follow the author's destructive "delete the RIG collection" step).
- **C2 — a frame exactly at rest encodes degenerate.** The addon writes
  frame entries as deltas from the Blender rest pose; an exactly-at-rest
  frame becomes an all-identity pool, which the engine decodes as all bones
  at the root origin. Near-rest frames are fine; authored action frames
  (saber moves, idles) will not sit exactly at rest. Check the first real
  export with `animkit` before trusting it.
- GLA decode gotcha: pool entries are band-space local matrices; the base
  pose is applied by the SmoothLow round trip. A "flat band" in a raw walk
  is NORMAL for a healthy file.

## Also in the addon (for reference)

GLA import (Cfg mode → one NLA strip per animation.cfg segment — this is
the in-Blender reference-overlay workflow for matching), GLM import/export
(LODs, tags, custom normals, skins), ASE + ROFF + Patch export. Out of the
animation-pipeline scope per plan decision #5, but available if model work
comes back.
