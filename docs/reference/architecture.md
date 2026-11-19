# Architecture

The suite is a Blender add-on (`jka_anim_tools`) that coordinates two
external components — the GPL GLA importer/exporter and the MIT format
library — with one strict rule: **one source of logic**.

## The three components

| Component | Repo / home | License | Role |
|-----------|-------------|---------|------|
| **jka_anim_tools** | this repo (`Jrbesse/jka-animator`) | MIT | The N-panel UI, the 15 operators, and the shared core both faces delegate to. |
| **jka-animkit** | `Jrbesse/jka-animkit` (private; shipped in the release zip under `lib/`) | MIT | The **format ground truth**: GLM/GLA v6 parsers, `animation.cfg`/`animevents.cfg`/`saberanims.cfg` parsers + writers, the `check` gate, `diff`/`merge`, dotXSI parsing/grafting. Pure Python stdlib (no numpy/scipy/pillow). |
| **jediacademy** | `mrwonko/Blender-Jedi-Academy-Tools` (public; the successor of the cagelight fork) | GPL v2+ | GLA/GLM import/export, Cfg-mode NLA import. The suite's *installed base* for file I/O. |

## The license boundary (decision #9)

`jka_anim_tools` is MIT; `jediacademy` is GPL. The boundary is structural,
not aspirational:

- The suite **calls the GPL add-on's operators** as an installed Blender
  add-on — `addon_bridge.ensure_addon()` only puts the jediacademy
  directory on `sys.path` and calls its `register()`. It never imports its
  modules into the suite's own code paths and never copies its code.
- The GPL add-on is **never vendored into this repo**. It is a separate
  plugin: kept as a gitignored dev fixture locally, and in release builds
  it is checked out from its pinned public tag and built with upstream's
  own Makefile ([release reference](release.md)).
- `jka-animkit` (MIT) is a **shared library the add-on imports at runtime**
  (`animkit_bridge.get_animkit(dir)`) — same language, no port. Its search
  order for the directory that *contains* the `animkit` package:
  1. the panel's **AnimKit Dir** field (explicit),
  2. the `JKA_ANIMKIT_DIR` environment variable,
  3. `~/work/jka-animkit` (the dev-machine clone; absent on a shipped
     install — so the zip's `lib` folder is what you set).

What each side is allowed to call:

```
jka_anim_tools (MIT)  ──calls──▶  jediacademy (GPL)      via bpy.ops / installed add-on only
jka_anim_tools (MIT)  ──imports─▶  jka-animkit (MIT)     as a normal Python package
jediacademy           ──never calls──▶ jka_anim_tools    (no back-coupling)
```

## One source of logic

Two faces, one core — they **cannot drift**:

| Face | Entry point | What it does |
|------|-------------|--------------|
| **Interactive** | N-panel operators (`jka_anim_tools/operators.py`, `cfgops.py`, `fingerops.py`) | Thin delegates: read scene properties → call the core → report via `self.report()` + the Results collection. |
| **Headless** | `blender/` CLI scripts (`prepare_rig.py`, `load_reference.py`, `b2_cfg_check.py`, `b3_check_check.py`, `b3_finger_apply_check.py`) | Drive the *same* core functions (and, for check, the same `bpy.ops`), no UI. |

Rule for contributors: **never put logic in a face.** Operators never parse
cfg text themselves (all format logic is animkit, via the bpy-free core);
headless scripts never re-derive what the core already does.

## Module map (`jka_anim_tools/`)

| Module | bpy? | Responsibility |
|--------|------|----------------|
| `common.py` | no | Names, modes, `JkaError`. |
| `paths.py` | no | Export path shaping/validation. |
| `animkit_bridge.py` | no | Runtime loader for the animkit package. |
| `anims.py` | no | cfg authoring core: segments load/add/save, events load/add/remove/save (validate-on-write), saber validation/presets — over animkit's cfg layer. |
| `checkop.py` | no | animkit-check core: `resolve_char_dir`, `check_dir` → `CheckResult(lines())`. A crash inside animkit's check is a `JkaError` (tool bug), never a finding. |
| `fingers.py` | no | The finger preset tables (hand-relative joint matrices) + the grasp slerp. |
| `nla.py` | yes | Armature / NLA track / strip glue; the `g2_sequence_prop` (loop bool + fps) read/write. |
| `addon_bridge.py` | yes | jediacademy registration (sys.path + `register()` only — the GPL boundary). |
| `rigprep.py` | yes | Mirror-armature prep: strip IK constraints, zero stored pose offsets, legacy g2 scale. |
| `refimport.py` | yes | Reference GLA import around the `skeleton_root` name trap. |
| `exportop.py` | yes | GLA export orchestration (paths, frames, scale restore) via jediacademy. |
| `operators.py` | yes | B1 operators: `load_reference`, `prep_rig`, `export_gla`. |
| `cfgops.py` | yes | B2/B3 operators: segments, events, saber, `check_run`. |
| `fingerops.py` | yes | The `finger_preset` operator (follows the rig mirror to its driver armature). |
| `panel.py` | yes | N-panel UI + the scene properties the operators read. |

## The two rig armatures (why prep and fingerops are non-trivial)

The JustJordyn IK rig carries **two** armatures: the working **IK rig**
(64 bones, chained finger hierarchy `j1→hand/j2→j1`) and the
**export/bind skeleton** (the object named `skeleton_root`, 53 bones, flat
finger hierarchy) — a *passive mirror* whose bones carry
`COPY_ROTATION`/`COPY_LOCATION` constraints onto the IK rig. Posing the
mirror does nothing; `fingerops` follows a finger bone's copy constraint to
its **target** armature and poses the driver instead. The preset tables are
**hand-relative** joint matrices (absolute armature-space tables embed the
authoring segment's hand placement and teleport fingers on a posed rig).

## History note

The suite began as a standalone C# Godot 4 workstation; that pivot was
shelved on 2026-11-17 (decision #12) when the Blender-native approach
absorbed its scope. The G0 skeleton is preserved, unmodified, in
`godot-shelved/` (`SHELVED.md` there).

The project's spec, decision log, and handoffs live in the private
companion repo `Jrbesse/openjk-support` (`plans/jka-anim-tool-plan.md` +
the latest `plans/handoff-*.md`). This documentation is the public front
door and is checked against the code for accuracy.
