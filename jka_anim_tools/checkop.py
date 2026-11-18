# SPDX-License-Identifier: MIT
"""B3: animkit-check core (bpy-free).

Runs animkit's `check` (parse + structural validation — the C1 gate's
library, engine-mirrored severity) over a character or skeleton dir and
returns findings shaped for the Results collection: one `(text, is_error)`
line per finding. Order: summary line first (is_error = failed), then
errors, then warnings — mirroring `animkit.check.format_report`.

The N-panel operator (B3) and any future CLI face call this; no format
logic lives in the bpy face (one source of logic — the standing rule).
"""
import os

from .common import JkaError


class CheckResult:
    """Structured output of one check run (bpy-free)."""

    def __init__(self, directory, ok, errors, warnings):
        self.directory = directory
        self.ok = ok
        self.errors = list(errors)      # "[file] msg" strings
        self.warnings = list(warnings)

    @property
    def name(self):
        return os.path.basename(os.path.normpath(self.directory))

    def summary(self):
        if self.ok:
            s = f"check {self.name}: OK"
            if self.warnings:
                n = len(self.warnings)
                s += f" ({n} warning{'s' if n != 1 else ''})"
        else:
            s = (f"check {self.name}: FAILED "
                 f"({len(self.errors)} errors, {len(self.warnings)} warnings)")
        return s

    def lines(self):
        """`[(text, is_error), ...]` for the Results collection."""
        out = [(self.summary(), not self.ok)]
        out += [(e, True) for e in self.errors]
        out += [(w, False) for w in self.warnings]
        return out


def resolve_char_dir(basepath, character):
    """`<base>/models/players/<character>` — JkaError when it cannot exist.

    `character` may be a real character (assassin_droid, …) or a skeleton
    dir name (`_humanoid`) — check accepts both (skeleton-only dirs validate
    GLA + cfgs, the engine never loads them as a character).
    """
    if not basepath:
        raise JkaError("check: no basepath set (the mod folder)")
    if not character:
        raise JkaError("check: no character set")
    d = os.path.join(os.path.abspath(basepath), "models", "players", character)
    if not os.path.isdir(d):
        raise JkaError(
            f"check: no such directory: {d} — expected a character or "
            "skeleton dir under models/players/ in the basepath")
    return d


def check_dir(ak, directory):
    """Run animkit's check over `directory`. `ak` = animkit module from
    `animkit_bridge.get_animkit` (needs the `check` submodule).

    Returns CheckResult. Raises JkaError for a missing dir or a crash in
    check itself (a crash is a tool bug, not a finding — never reported as
    a passing/failed check).
    """
    if not os.path.isdir(directory):
        raise JkaError(f"check: no such directory: {directory}")
    chk = getattr(ak, "check", None)
    if chk is None:
        raise JkaError("animkit's 'check' submodule did not load")
    rep = chk.Report()
    try:
        chk.check_character_dir(directory, rep)
    except Exception as e:
        raise JkaError(f"check crashed on {directory}: {type(e).__name__}: {e}")
    return CheckResult(directory, rep.ok, rep.errors, rep.warnings)
