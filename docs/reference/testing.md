# Test strategy

Five layers, from cheapest to most authoritative. The running order for a
change depends on what it touches — the "when to run what" table is at
the end.

## 1. Unit tests (pure Python, no Blender)

`tests/` — run in CI on every push and release:

```
python -m unittest tests.test_anims tests.test_checkop tests.test_fingers
python tests/test_paths.py        # standalone script (sys.exit style), NOT a unittest module
```

| Suite | Tests | Covers |
|-------|-------|--------|
| `test_anims.py` | 17 | the cfg core: segment load/add/save, event add/remove/save (validate-on-write), saber validation/presets — over the animkit fixtures (`JKA_ANIMKIT_DIR`). |
| `test_checkop.py` | 13 | the check core: `resolve_char_dir` (character OR skeleton dir), `CheckResult.lines()` ordering (summary first, then errors, then warnings), crash-is-a-tool-bug (a corrupt-GLA test mutates the header `numBones` @ offset 84). |
| `test_fingers.py` | 13 | the preset tables: hand-relative form, the FIST left-side mirror law (exact), the GRASP slerp midpoint, apply-matrix composition. |
| `test_paths.py` | 16 | export path shaping/validation (the in-base-path rule, base-relative naming) + the `derive_*` helpers (basepath derivation walking up to `models/players`, reference-GLA + export-path derivation, errors naming the missing piece). |

**Never run `python -m unittest discover tests`** — `test_paths.py` is a
standalone script with a module-level `sys.exit`, and discover dies on it.
Run it directly, and the rest by module name.

Test hygiene: ops that SAVE write into scratch fixture copies, so each
test gets a **fresh scratch dir** (`setUp`, not `setUpClass`) — a shared
class dir leaks edits between tests and the counts drift mysteriously.

## 2. The B1 byte-identical E2E gate (the export path)

The export/prep path must stay **byte-identical** to the verified
baseline on Blender 5.3.0:

```
G=~/.hermes/profiles/dev/cache/scratch/jka_blender/gabase
A=~/.hermes/profiles/dev/cache/scratch/jka_blender/jediacademy
B=~/work/blender/blender-5.3.0-linux-x64/blender
cd ~/work/jka-animator
# matched flow (one Blender process drives both scripts):
$B --background fixtures/ik-rig/doc_9f2fca7e0a77_Jedi_Academy_IK_Animation_Rig_v1.1.blend \
  --python tests/e2e_match_driver.py -- --base "$G" --out "$G/verify_match.gla" --addon-dir "$A"
# plain flow:
$B --background <same .blend> --python blender/prepare_rig.py -- \
  --export "$G/verify_plain.gla" --basepath "$G" \
  --glapath models/players/humanoid/humanoid.gla \
  --ref models/players/_humanoid/_humanoid.gla \
  --frame-start 0 --frame-end 239 --addon-dir "$A"
sha256sum "$G/verify_match.gla" "$G/verify_plain.gla"
```

Both must hash to
`6b0e2cecc28af4f703b268a2e095dd31897386c4452672a859d521b941326cd0`
(frames 0..239 of the `doc_9f2fca7e` JustJordyn rig, gabase staging).
The gate has caught a real silent regression (an identity-quaternion
typo → 102 vs 2 bone-pool entries) — "it compiles" / "it runs" is not
"it matches".

## 3. The registered-zip smoke

`packaging/b4_register_smoke.py` verifies the **shipped zip**, not the
dev clone: it extracts the zip (arg after `--`, else the newest
`dist/jka-anim-tools-*.zip`) into a clean temp dir, scrubs the dev clone
from `sys.path` + the env, registers the shipped package, and verifies:

* all **15** `jka_anim.*` operators + `JKA_PT_Main` registered
  (`hasattr(bpy.ops.jka_anim, <name>)` per idname — `dir(bpy.types)`
  misses dynamically registered operator classes),
* **animkit resolves to the bundled copy** (`jka_anim_tools/lib/animkit`)
  with no env var / field set,
* the one-base-path scene props exist and the old multi-path props are
  gone,
* unregisters clean.

```
blender --background --factory-startup \
  --python <repo>/packaging/b4_register_smoke.py
# expect: REGISTER SMOKE: PASS (with "bundled animkit: ok",
#         "one-base-path props: ok | old multi-path props removed: ok")
```

The smoke also proves registration works with **jediacademy absent** —
the operators only need it at call time (review item #1).

## 4. Headless flow drivers (bpy, `blender/`)

| Driver | Checks |
|--------|--------|
| `blender/b2_cfg_check.py` | 7 checks over the cfg ops via `bpy.ops`: segment load/jump/apply/add, events load/add/remove/save (validate-on-write), drift detection. |
| `blender/b3_check_check.py` | 7 checks over `check_run`: the result ordering, error vs warning severity, the tool-bug-crash path. |
| `blender/b3_finger_apply_check.py` | The 3 presets: read back the posed matrices (0.0000° diff), hands untouched, then a render vision-judged (clenched fist / relaxed open). |

Pitfalls baked in: `bpy.ops` raises `RuntimeError` when an op returns
CANCELLED with an error report (the exception text **is** the report) —
drivers catch it. Two `--python` blocks don't chain on one CLI line
(everything after the first `--` goes to the first script) — the matched
driver runpy's both scripts in one process. Headless stdout is buffered —
check the output file, not the pipe.

## 5. Windowed + in-engine gates (the VM)

- **Windowed VM runs** (gdesk VM, 1920×1080 Xorg): N-panel click-through
  and panel screenshots (`docs/screenshots/`) — windowed is the only
  place that executes `draw()`, so it polices the icon names (Blender 5.3
  renamed several: `REFRESH`→`FILE_REFRESH`, `BACKWARDS`→`BACK`,
  `SAVE`→`FILE_TICK`); an invalid icon silently cuts the panel off at
  that row. The recipe (main-loop timers, in-process screenshots, the
  JKA tab as the 5th N-panel tab) is in the dev skill `jka-animator-dev`
  → "Windowed VM runs".
- **The in-engine gate** (the final authority for shipped work): boot the
  mod in the engine build (OpenJK + the mod's pk3, `+map academy1`) on
  the gdesk VM and verify. For *new animation tokens*, absence of a
  `WARNING: Unknown token` is **not** sufficient — `FINAL_BUILD`
  compiles that warning out of Release builds. The definitive proof is a
  per-token resolution check (a temporary unconditional log at the
  `GetIDForString` call, reverted after): the real token must resolve to
  a valid anim index and a bogus control token to −1. That is how
  `BOTH_WALK_MINIGUN` was proven (decision #19). `cg_debugAnim` is a
  0–4 warning-filter selector, **not** a force-play tool — don't rely on
  it to play a specific segment.

## When to run what

| Change touches | Must stay green |
|----------------|-----------------|
| Anything in the export/prep path (`exportop`, `rigprep`, `refimport`, `paths`, `export_gla`) | Unit + **B1 byte-identical E2E gate** (both flows) |
| The cfg layer (`anims.py`; animkit's animevents/cfgwrite/saberanims) | Unit + the animkit cfg round-trip suite (byte-identical modulo comments on all fixture cfgs) + `b2_cfg_check.py` |
| The check core (`checkop.py`) | Unit + `b3_check_check.py` |
| The finger tables (`fingers.py`) | Unit + `b3_finger_apply_check.py` + a render vision-judge |
| Panel / operators / registration | Registered-zip smoke (3) + a windowed run (5) |
| Packaging (`build_release.py`, lock, workflows) | CI green on the push + registered-zip smoke on the built zip + release-asset byte-compare |
| Shipped work (before handing to a user) | Everything above + the in-engine gate (5) |
