# Shelved: Godot 4 + C# workstation (decision #12, 2026-11-17)

The original product form — a standalone Godot 4 + C# workstation that
displays the model and views/edits/adds animations — was shelved by
plan decision #12 in favour of a **Blender-native animation suite**
(the `jka_anim_tools` addon at the repo root).

What is here:

- `project.godot`, `jka-animator.csproj`, `scenes/`, `scripts/` — the G0
  skeleton (commit `018aac6`: Godot.NET.Sdk 4.7.2, net8.0, headless boot
  verified). It is a 4-file placeholder; nothing of value was built on it.

Why it is archived, not deleted:

- The history stays intact and the skeleton is the restore point if the
  decision #10 reopen trigger ever fires AND the Blender suite proves it
  cannot absorb the missing features (per the decision log, a miss means
  the *suite* grows first — a new app only if it cannot).

To restore (only if a future decision reopens this): `git mv godot-shelved/* .`
and put the Godot entries back in the root `.gitignore` (they remain in
history if you need to fish them out).

Milestones G1–G4 are void; G5's function (in-engine verification loop)
lives in the suite's validation-gate integration + the standing gdesk
in-engine play check. See `plans/jka-anim-tool-plan.md` in
`Jrbesse/openjk-support` (decisions #5–#7, #12) and the latest handoff.
