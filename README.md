# jka-animator — JKA Ghoul2 animation suite (Blender-native)

A **Blender-native animation suite** for *Jedi Knight: Jedi Academy*
Ghoul2 characters: **display the model** (native skinned viewport + GLM
import) and **view, edit, and add animations** — with engine-exact
segment timing, in-Blender animation matching, `animevents.cfg`
authoring, and the animkit validation gate wired into the workflow.
Animation side only — modeling and weighting are v2 roadmap items of
the same suite.

**Product pivot (2026-11-17, decision #12):** the original standalone
C# Godot workstation (decisions #5–#7) was shelved — its skeleton is
archived in `godot-shelved/` (history preserved). The Blender suite
absorbs its scope; see the plan for rationale.

Spec and decision log: `Jrbesse/openjk-support` →
`plans/jka-anim-tool-plan.md` (read the latest `plans/handoff-*.md`
before working). Format ground truth (GLM/GLA v6, `animation.cfg`,
`animevents.cfg`, the `check`/`diff`/`merge` gate): `Jrbesse/jka-animkit`
(Python) — now a shared library the addon imports directly (same
language; the C# codec port is moot).

## Layout

| Path | What |
|------|------|
| `jka_anim_tools/` | The suite addon (our code, MIT): N-panel + authoring operators over the mrwonko addon. Install as a zip (B4) or point Blender's addons path at the repo. |
| `blender/` | Headless automation face: `prepare_rig.py`, `load_reference.py` — thin CLI wrappers over the addon's shared `core/` (single source of logic). Their `README.md` is the authoring procedure. |
| `godot-shelved/` | Archived G0 Godot skeleton (see `SHELVED.md`). |
| `docs/ik-rig/` | JustJordyn IK rig analysis + dump scripts (commit-safe). |
| `fixtures/` | Local-only pak-extracted fixtures (gitignored — sanitize policy). |

## Dependencies

- **Blender 4.1+** (everything verified on 5.3.0).
- **mrwonko/cagelight "Jedi Academy Import/Export Tools" v2.1.0** — the
  *installed base*: GLA import/export + Cfg-mode NLA. **GPL v2+: run it
  as an installed addon, never port its code into this repo** (decision
  #9). The zip lives in `fixtures/blender-addon/` (gitignored).
- **jka-animkit** — the validation gate (`python -m animkit check
  <character-dir>`); stays the format reference implementation.

## Milestones (suite v1, signed off 2026-11-17)

- [ ] **B1** — addon skeleton + authoring operators (load-reference /
      prep / export); headless E2E identical to the script flow
- [ ] **B2** — segments panel + `animevents.cfg` editor (engine-exact
      tokenizer shared with animkit, validated on write); saber scope
      folds in
- [ ] **B3** — animkit-check operator + results panel; finger presets
      (grasp/fist/open)
- [ ] **B4** — ship to Sheng (zip install on Windows), first real
      animation = decision #10 acceptance test, fixture sanitization,
      public-repo call
- **v2 roadmap** — GLM model work, saberanims.cfg validation + saber
      segment presets, engine-flavored preview

## Fixtures

Pak-extracted character fixtures live under `fixtures/` (gitignored —
Sheng's mod characters must not be committed; sanitize policy, plan
decision #3).
