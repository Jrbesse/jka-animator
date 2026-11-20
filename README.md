# jka-animator — JKA Ghoul2 animation suite (Blender-native)

A Blender add-on for authoring character animations for *Jedi Knight: Jedi
Academy* (JKA) and OpenJK-based mods (JKA: Enhanced). It displays your
character model, imports reference animations you can pose and keyframe over
in Blender, exports engine-ready `.gla` files, and validates everything
against the real engine rules before you ship it.

If you have never touched JKA modding: think "Blender, but the file formats
and the rules are the game's — and the add-on checks your work against them
before export." The finished model (mesh + skin weights) is an **input**;
this suite is the animation side.

## What you get

One panel — 3D view → press **N** → **JKA** tab (the last tab) — 15
operators, each a button for one verified flow step:

- **Reference matching** — import any reference `.gla` into the scene and
  scrub it while you pose the rig to match, frame by frame.
- **Segments** — the game's `animation.cfg` table in the panel: load, jump
  to, fix (loop/fps), and add segments with engine-exact semantics.
- **Events** — `animevents.cfg` (footsteps, sounds, effects, pushes) with
  validate-on-write: a broken event set never touches the file.
- **Saber** — `saberanims.cfg` validation and one-click preset segments for
  saber attacks (guard + one attack per style).
- **Finger presets** — one-click **FIST** / **OPEN** / **GRASP** hand poses
  for the 12 engine finger bones, derived from real stock animations.
- **Check** — the animkit validation gate: your whole character directory
  (GLM + GLA + cfgs + skin) validated the way the engine parses it, with
  every finding listed in the panel.
- **GLA export** — through the separately-installed jediacademy add-on
  (its own license — see below), with legacy Ghoul2 scale restored and
  path validation.

## Install (one time)

Two add-ons, both via **Edit → Preferences → Add-ons → Install from
Disk…**:

1. **JKA Animation Tools** — the
   [latest release zip](https://github.com/Jrbesse/jka-animator/releases)
   (`jka-anim-tools-X.Y.Z.zip`, a standard add-on zip — the format
   library `animkit` is bundled inside it). Requires Blender **4.1+**
   (verified on 5.1 and 5.3.0).
2. **Jedi Academy Import/Export Tools** (`jediacademy`, by mrwonko) — the
   GLA/GLM import/export engine this add-on calls. It is **not bundled**
   (its own license); install it once, separately, from
   [mrwonko/Blender-Jedi-Academy-Tools](https://github.com/mrwonko/Blender-Jedi-Academy-Tools)
   (tag `v2.1.0`).

Then enable both in the Add-ons list, open your mod's folder tree and
press **N** → **JKA**, and set the **Base Path** at the top — everything
else derives from it.

The full end-to-end walkthrough — first animation, every panel field, the
check output explained, troubleshooting — is in
**[docs/guide.md](docs/guide.md)**.

## How it fits together

```
                 jka_anim_tools (this repo, MIT)
                 N-panel + 15 operators + shared core
                 ┌──────────────┴───────────────┐
                 │ calls its GLA import/export  │ imports at runtime
                 ▼ operators (installed addon)  ▼
   ┌────────────────────────────┐   ┌──────────────────────────────┐
   │ jediacademy                │   │ jka-animkit (MIT library)    │
   │ mrwonko "Jedi Academy      │   │ the GLM/GLA + cfg format     │
   │ Import/Export Tools" —     │   │ ground truth: parse, check,  │
   │ its own license, installed │   │ diff, merge — bundled in the │
   │ separately (not bundled)   │   │ add-on under lib/            │
   └────────────────────────────┘   └──────────────────────────────┘
```

The panel operators and the headless `blender/` scripts are two faces of the
**same core** — interactive and automated flows cannot drift
([architecture](docs/reference/architecture.md)).

**[Technical reference: `docs/reference/`](docs/reference/)** — architecture
and the MIT/MIT/GPL license boundary, complete operator + panel reference,
cfg/GLA format notes, every validation rule, the release pipeline, and the
test strategy.

## Releases

GitHub Releases, cut automatically from a `vX.Y.Z` tag: CI builds the zip
from **pinned sources** (the private `jka-animkit` at the locked SHA in
`packaging/animkit.lock` — the only non-local input; `jediacademy` is a
user-side install, never a CI input) and attaches it to the release.
Current release:
[v0.2.2](https://github.com/Jrbesse/jka-animator/releases/tag/v0.2.2)
(2026-11-20). [Release pipeline details](docs/reference/release.md).

## Repo layout

| Path | What |
|------|------|
| `jka_anim_tools/` | The suite add-on (MIT): N-panel, operators, and the shared core. |
| `blender/` | Headless automation face: thin CLI wrappers over the same core (`prepare_rig.py`, `load_reference.py`, check drivers). |
| `packaging/` | Release build (`build_release.py`), the animkit pin (`animkit.lock`), the shipped-zip register smoke. |
| `.github/workflows/` | Release CI: reusable build, CI on push, tag-driven releases. |
| `docs/` | User guide + technical reference + rig analysis (`ik-rig/`) + panel screenshots. |
| `godot-shelved/` | Archived skeleton of the original C# Godot workstation (scope absorbed by this suite; see `SHELVED.md`). |
| `fixtures/` | Local-only fixtures (gitignored — mod character content is never committed). |

## Roadmap

- **Shipped (v0.2.2):** B1 add-on core + export gate · B2 cfg editor
  (segments/events/saber) · B3 validation check + finger presets · B4
  standard add-on zip packaging (no bundled GPL code) + public release CI
  · the `.xsi` import pilot (`BOTH_WALK_MINIGUN`, in-engine verified) ·
  the 2026-11-20 review fixes (one base path, labeled panel, icon/
  operator compatibility on Blender 5.1/5.3, settings persistence,
  reference-GLA plane alignment).
- **Next (v0.3.0 candidate):** the 4 remaining `.xsi` segments + a panel
  import face for them; a segment-import progress indicator for Cfg-mode
  loads of big skeletons.
- **v2:** GLM model work, engine-flavored preview.

## License

- This add-on: **MIT** (see `LICENSE`).
- `jka-animkit` (the format library, bundled in the zip): **MIT**.
- `jediacademy` (the GLA importer/exporter the suite drives): its own
  license — it is installed **separately** by the user from its upstream
  repository and is never copied into this repo or bundled in the release
  zip ([the boundary, in detail](docs/reference/architecture.md)).
