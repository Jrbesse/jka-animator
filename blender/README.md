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
