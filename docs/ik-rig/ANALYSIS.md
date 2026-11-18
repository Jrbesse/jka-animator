# JustJordyn JKA IK Rig — Full Analysis

**Fixture:** `Jedi_Academy_IK_Animation_Rig_v1.1.blend` (local: `fixtures/ik-rig/`, gitignored per sanitize policy)
**Analyzed:** 2026-11-17, Blender **5.3.0** headless (`dump_rig2.py` + `probe.py`, both committed under `docs/ik-rig/`)
**Evidence:** `docs/ik-rig/dump-5.3.0.txt` (447-line full dump: collections, bones, constraints, drivers, actions, images, materials)

## 1. What it is

A Blender IK animation rig for Jedi Academy `_humanoid` characters, by JustJordyn
(release 28/06/2024, "for Blender 2.93+"). Inspired by the CAT Rig for 3DS Max.
The `.blend` is **pure data** — no embedded Python, no addon scripts. All 13
textures (Kyle model + sabers + blasters) are **packed** into the file, so it is
self-contained and opens with zero external dependencies.

The author's guide (embedded TEXT datablock, reproduced in §5) documents the
full workflow: animate → bake → **export via an external .gla addon** →
**merge with an external GLAMerge tool** (both "not included").

## 2. File inventory

| Collection | Contents |
|---|---|
| `RIG - Use This to Animate` | `IK_Rig` armature — **64 bones** (the thing you animate) |
| `EXPORT - Do Not Delete` | `scene_root` (empty) + `skeleton_root` armature — **53 bones** (the engine skeleton) |
| `MODELS - Use These for Reference` | Kyle GLM (29 surface parts, all with ARMATURE modifiers → `skeleton_root`), SaberL/R/Dual, BlasterPistol/Rifle, Floor |
| (top-level dupes) | SABERS + BLASTERS collections duplicated from import; harmless |

- Scene: 24 fps, frame range **0..0** (artist must set range before bake), metric units.
- **No actions, no drivers, no shape keys** anywhere — the file is a clean rig,
  every animation is authored from scratch in-session.
- Kyle's 29 mesh parts are weighted to **`skeleton_root`** (not the IK rig):
  the model deforms off the *mirrored* skeleton, which is why the rig works
  without reweighting.

## 3. The two-armature architecture

```
IK_Rig (64)                          skeleton_root (53 = exact engine _humanoid)
  model_root (ctrl)      ──CopyLoc──►  model_root
  pelvis (ctrl)          ──CopyLoc+Rot► pelvis
  spine (ctrl, yellow)        │           Motion  ◄── NO CONSTRAINT (stays at bind pose!)
  Upper_Body_Pivot (ctrl)     │
  lower_lumbar (FK)      ──CopyRot──►  lower_lumbar
  upper_lumbar (IK c=1)  ──CopyRot──►  upper_lumbar      upper_spine (ctrl) ─IK→ upper_lumbar
  thoracic (CopyLoc←upper_lumbar) ─CopyRot► thoracic
  cervical (FK)          ──CopyLoc+Rot► cervical
  cranium (TrackTo→head_target, CopyRot via face) ─DampedTrack+CopyRot► cranium
  face, ceyebrow, jaw, 7 lip/eye bones ─CopyLoc+Rot► same
  r/lclavical (CopyRot only) ► r/lclavical
  r/lhumerus ─CopyLoc+Rot►; humerusX: none (follows parent)
  r/lradius (IK c=2) ─CopyRot►; radiusX ─CopyLoc+Rot►
  r/lhand (CopyLoc←radius) ─CopyLoc+Rot► r/lhand
  6 finger bones/hand ─CopyLoc+Rot► (engine: fingers parented under radius, not hand)
  rhang_tag_bone / lhang_tag_bone ─CopyLoc+Rot► same
  femurX, tails: no constraints (follow parents)
```

**64 = 52 real engine bones + 12 controls:**
`Upper_Body_Pivot`, `spine`, `upper_spine`, `rheel_IK`, `lheel_IK`, `rhand_IK`,
`lhand_IK`, `rknee_target`, `lknee_targeet` (sic), `relbow_target`, `lelbow_target`,
`head_target`.

**Critical gap: `Motion` (engine bone #2, child of pelvis) exists only in
`skeleton_root` with no constraints.** The rig has no control that drives it.
Every animation exported through this rig has a **static Motion bone** — no
root motion. (In-place loops are fine; anything the engine PM system expects to
drive via `Motion` is absent.)

## 4. IK map (verified from constraint data)

| Solver bone | IK target | Pole target | Chain | Angle |
|---|---|---|---|---|
| `ltibia` | `lheel_IK` | `lknee_targeet` | 2 | 180° |
| `rtibia` | `rheel_IK` | `rknee_target` | 2 | 180° |
| `lradius` | `lhand_IK` | `lelbow_target` | 2 | 180° |
| `rradius` | `rhand_IK` | `relbow_target` | 2 | 180° |
| `upper_lumbar` | `upper_spine` | — | 1 | — |

Plus: `cranium` TrackTo→`head_target` (rig) / DampedTrack (skeleton);
`rtalus`/`ltalus` CopyLoc←tibia (foot follows); `lhand`/`rhand` CopyLoc←radius
(hand follows after IK solve); spine duplicated as FK (`lower_lumbar`,
`upper_lumbar`) + IK control (`upper_spine`).

Controls are color-coded per the guide: **yellow** core (root/hips/spine),
**purple** hips tweaks (move spine without hands), **green** limb endpoints,
**red** pole/track targets. Everything else is FK fine-tuning (fingers,
shoulders, face).

All pose bones carry a `mmd_bone` custom property (MustardUI) and the
armature carries MustardUI setting blocks (Rig/Lattice/Physics/Armature
Settings). **MustardUI is not required** — the file loads and evaluates
cleanly on 5.3.0 without it (proven); the properties are inert without the
addon. It only powered the fancy custom UI.

## 5. Author's documented workflow (embedded guide, verbatim steps)

1. Animate on `IK_Rig` (RIG collection).
2. Exit pose mode, select `skeleton_root` (EXPORT collection).
3. Object → Animation → **Bake Action**: set start/end frame, untick
   "Only Selected Bones", tick **Visual Keying** + **Clear Constraints**,
   Bake Data = **Pose**, OK.
4. **Delete the RIG and MODELS collections** (destructive to the file!).
5. **Export as .gla** (external addon operator — "not included"): set Base
   Path to modding dir, `gla name`, and `gla reference` =
   `models/players/_humanoid/_humanoid.gla` (the exporter reads the reference
   GLA to build the bone table — same design as our GLA writer).
6. Merge the animation into a copy of `_humanoid.gla` with **GLAMerge**
   ("Not included"), rename to `_humanoid.gla`, preview in modview.

## 6. Compatibility verdict on current Blender

**The rig itself already works on current Blender.** The file is 2.93-era but
contains only stable, still-supported data: vanilla armatures, IK/Copy/Track
constraints, packed textures, one TEXT block. It **loads, evaluates, and
dumps completely cleanly on 5.3.0** — no API breakage in the data itself.
(Optionally spot-check 4.5 LTS; expected to pass for the same reason.)

What does NOT work on current Blender:
1. **The .gla export addon** — external, not included, era-unknown. Almost
   certainly Python-2 / pre-4.0 UI code. **Do not port it.**
2. **GLAMerge** — external, not included. **Already replaced** by
   `jka-animkit` merge (byte-exact, validated against the engine).

## 7. Gaps (why the author's two weak spots are weak, plus what we found)

1. **Animation matching — nonexistent.** No reference loading, no pose
   library, no way to load an existing `.gla` as a pose target and match a
   take against it. The workflow is pure from-scratch keyframing.
2. **Finger positioning — difficult.** The bones exist (6 per hand:
   `d1/d2/d4 × j1/j2`, no thumbs — matches the engine), but there are no
   finger FK controls, no grasp/curl control, no hand presets. Worse: in the
   engine skeleton **fingers are children of `radius`**, so finger keys are
   relative to the radius; when the arm is IK-driven the radius orientation
   shifts and hand-authored finger poses rotate in surprising ways. Direct
   keyframing of the finger bones against a moving IK hand is the root
   cause of the pain.
3. **No Motion control** (§3) — exported anims have static root motion.
4. **Destructive export workflow** (step 4 deletes collections from the
   working file; frame range must be set by hand) — fine for v1.0, bad for
   iteration.
5. **Export/merge tooling missing** from the package (§6) — the two tools
   that would actually produce an engine-ready file.

## 8. Work plan

**A. Blender side (authoring front-end stays as-is, retrofitted via script)**

- **A1 — Motion control:** add a `motion_ctrl` (or reuse `model_root`
  delta) → CopyLoc/CopyRot into `skeleton_root/Motion`. Scripted,
  reproducible, save as `…_v1.2.blend`. *Verifies: export a test anim,
  GLA-decode, Motion bone keys present.*
- **A2 — Finger FK controls:** add per-finger ctrl bones (6/hand) with
  Copy constraints overwriting the plain finger mirroring; optional single
  "grasp" slider via drivers. *Verifies: pose a grip in Blender, check
  mirrored skeleton fingers.*
- **A3 — Non-destructive bake bridge:** small standalone script (no addon
  needed) that reads the *baked* `skeleton_root` action and writes
  **JSON** (`bone, frame, quat[wxyz], trans[x,y,z]`) — replaces both the
  destructive delete step and the external .gla exporter. No coordinate
  conventions cross the boundary (Blender Y-up handled inside the writer).

**B. Workstation side (jka-animator, Godot 4 + C#)**

- **B1 — JSON→GLA writer (G2, already critical path):** takes the A3 JSON +
  reference `_humanoid.gla` (bone table) and writes an engine-exact animation
  GLA. This is the "Export as .gla" replacement — same design as the
  author's exporter (`gla reference` param), but validated against the
  engine's decoder.
- **B2 — Animation matching:** load any `.gla` as a reference overlay on the
  model; scrub + "copy this pose/frame into the take". This is the missing
  matching feature, and the workstation is the right home for it (we already
  parse GLAs byte-exact).
- **B3 — Finger editor + grasp presets** (direct radius-relative finger
  editing, which is what the engine actually stores — the workstation edits
  the same data the engine consumes, so no IK weirdness).
- **B4 — Merge:** already done (`jka-animkit` merge) — zero work.

**C. Sequencing recommendation**

A3+B1 first (completes the export path end-to-end and unblocks everything),
then B2 (matching), A1/A2 (rig upgrades — only if/when the Blender route is
kept as the primary authoring surface), B3 last.

## 9. Open questions

1. Is the original .gla export addon obtainable (JustJordyn's distribution,
   community mirrors)? Worth a look *only* to confirm our writer covers its
   behavior (e.g., scale_weight handling, subitem references) — not to port.
2. Which Blender will the artist actually run (4.5 LTS vs 5.x)? Both should
   work; A1/A2 scripts will target the artist's version.
3. Confirm the artist's intent: keep Blender+rig as the authoring surface
   with the workstation as export/inspection/matching, or move authoring
   fully into the workstation over time?
