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
- **GLA export** — through the community jediacademy add-on (GPL, a hard
  dependency), with legacy Ghoul2 scale restored and path validation.

## Install (one time)

Download the [latest release zip](https://github.com/Jrbesse/jka-animator/releases)
(`jka-anim-suite-X.Y.Z.zip`). Requires Blender **4.1+** (everything is
verified on 5.3.0).

1. Copy the two add-on folders — `addons/jka_anim_tools` and
   `addons/jediacademy` — into your Blender add-ons directory. Edit →
   Preferences → Add-ons reveals it; the Windows default is
   `%APPDATA%\Blender Foundation\Blender\<version>\scripts\addons`.
2. Enable **both** add-ons in Preferences: *Jedi Academy Import/Export
   Tools* (`jediacademy`) and *JKA Animation Tools* (`jka_anim_tools`).
3. Open the JKA N-panel and set the **AnimKit Dir** field (in the
   *Segments (animation.cfg)* box) to the `lib` folder of the zip you
   downloaded — the folder that *contains* `animkit\`.
4. Done. Open your mod's folder tree and press **N** → **JKA**.

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
   │ jediacademy (GPL)          │   │ jka-animkit (MIT library)    │
   │ mrwonko "Jedi Academy      │   │ the GLM/GLA + cfg format     │
   │ Import/Export Tools" —     │   │ ground truth: parse, check,  │
   │ installed as an add-on,    │   │ diff, merge — shipped in the │
   │ never copied into this repo│   │ release zip under lib/       │
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
`packaging/animkit.lock`; the GPL dependency from its pinned upstream tag
`v2.1.0`) and attaches it to the release. Current release:
[v0.1.0](https://github.com/Jrbesse/jka-animator/releases/tag/v0.1.0)
(2026-11-19). [Release pipeline details](docs/reference/release.md).

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

- **Shipped (v0.1.0):** B1 add-on core + export gate · B2 cfg editor
  (segments/events/saber) · B3 validation check + finger presets · B4
  packaging + public release CI · the `.xsi` import pilot
  (`BOTH_WALK_MINIGUN`, in-engine verified).
- **Next (v0.2.0 candidate):** the 4 remaining `.xsi` segments + a panel
  import face for them; the public documentation shipped here.
- **v2:** GLM model work, engine-flavored preview.

## License

- This add-on: **MIT** (see `LICENSE`).
- `jka-animkit` (the format library, shipped in the zip): **MIT**.
- `jediacademy` (the GLA importer/exporter the suite drives): **GPL** — it
  runs as an installed add-on and its code is never copied into this repo
  ([the boundary, in detail](docs/reference/architecture.md)).
