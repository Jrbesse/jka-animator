# jka-animator — JKA Ghoul2 animation workstation

Godot 4 + C# workstation for *Jedi Knight: Jedi Academy* Ghoul2 characters:
**display the model; view, edit, and add animations.** Animation side only —
modeling and weighting live in a separate program (Blender); the finished
GLM is input, not edited here.

Spec and decision log: `Jrbesse/openjk-support` → `plans/jka-anim-tool-plan.md`
(DRAFT v3, decisions #5–#7). Format ground truth (GLM/GLA v6,
`animation.cfg`, `animevents.cfg`): `Jrbesse/jka-animkit` (Python CLI) — the
C# parsers port that code and are validated byte-for-byte against it.

## Milestones

- [x] **G0** — repo + skeleton (Godot 4.7 + C#, headless + window boot)
- [ ] **G1** — Display + view: GLM/GLA/cfg loaders, skinned viewport,
      segment playback with engine-exact timing
- [ ] **G2** — GLA writer (exact inverse of `MC_UnCompressQuat`;
      decode→encode round-trip on all fixtures)
- [ ] **G3** — Edit: frame-level pose, timing, trim/copy/retarget, events
- [ ] **G4** — Add: new segments + cfg/animevents generation, Blender import
- [ ] **G5** — In-engine verification loop (gdesk VM)
- [ ] **G6** — Windows export for Sheng, fixture sanitization, public call

## Build & run (dev container / Linux)

```
dotnet build
godot --path . --headless --quit-after 3   # headless smoke
godot --path .                             # windowed
```

## Fixtures

Pak-extracted character fixtures live under `fixtures/` (gitignored — Sheng's
mod characters must not be committed; sanitize policy, plan decision #3).
