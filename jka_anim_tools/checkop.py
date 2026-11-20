# SPDX-License-Identifier: MIT
"""B3: animkit-check core (bpy-free).

Runs animkit's `check` (parse + structural validation — the C1 gate's
library, engine-mirrored severity) over a character or skeleton dir and
returns findings shaped for the Results collection: one `(text, is_error)`
line per finding. Order: summary line first (is_error = failed), then
errors, then warnings — mirroring `animkit.check.format_report`.

The N-panel operator (B3) and any future CLI face call this; no format
logic lives in the bpy face (one source of logic — the standing rule).

Display condensing (Sheng retest #5, 2026-11-20): warnings collapse per
(file, warning TYPE) — the stock _humanoid check dumps 215 identical
"unknown anim name" lines, one per cfg segment; the Results box shows
one line with the count + the line range instead.
"""
import os
import re

from .common import JkaError

# animkit's warning shape: "[file] line N: msg" or "[file] msg"
_WARN_RE = re.compile(
    r"^\[(?P<file>[^\]]+)\]\s+(?:line\s+(?P<line>\d+)\s*:\s*)?(?P<msg>.*)$")


def _warning_type(msg):
    """Grouping key for a warning TYPE: quoted tokens and bare numbers
    collapse, so per-instance variants of one warning (one "unknown anim
    name" line per segment, `speed=5` vs `speed=99`) group together while
    genuinely different messages stay separate."""
    msg = re.sub(r"'[^']*'", "", msg)
    msg = re.sub(r"\b\d+\b", "", msg)
    return msg


def _fmt_run(start, end):
    return f"{start}-{end}" if end > start else str(start)


def _compact_ranges(nums):
    """[12, 13, 14, 18, 20, 21] -> '12-14, 18, 20-21' (sorted)."""
    out = []
    run = None  # [start, end] of the current consecutive run
    for n in sorted(nums):
        if run is not None and n == run[1] + 1:
            run[1] = n
        else:
            if run is not None:
                out.append(_fmt_run(run[0], run[1]))
            run = [n, n]
    if run is not None:
        out.append(_fmt_run(run[0], run[1]))
    return ", ".join(out)


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
        """`[(text, is_error), ...]` for the Results collection: summary
        line first, then errors (never condensed — each needs attention),
        then warnings collapsed per warning TYPE
        (``condensed_warnings``)."""
        out = [(self.summary(), not self.ok)]
        out += [(e, True) for e in self.errors]
        out += [(w, False) for w in self.condensed_warnings()]
        return out

    def condensed_warnings(self):
        """Warnings collapsed per (file, warning TYPE) — the display
        condensing, Sheng retest #5. A group of one line passes through
        unchanged; a group of N lines becomes

            [file] ×N <first message> (lines 1453-1667)

        with the line suffix dropped when the group carries no line
        numbers. Group order follows first appearance."""
        groups = {}
        order = []
        for w in self.warnings:
            m = _WARN_RE.match(w)
            if m is None:  # non-standard shape: own group, verbatim
                key = ("raw", w)
                gfile, gmsg, line = w, w, None
            else:
                key = (m.group("file"), _warning_type(m.group("msg")))
                gfile, gmsg = m.group("file"), m.group("msg")
                line = int(m.group("line")) if m.group("line") else None
            g = groups.get(key)
            if g is None:
                g = groups[key] = {"file": gfile, "msg": gmsg,
                                   "lines": [], "count": 0, "raw": w}
                order.append(key)
            g["count"] += 1
            if line is not None:
                g["lines"].append(line)
        out = []
        for key in order:
            g = groups[key]
            if g["count"] == 1:
                out.append(g["raw"])
            else:
                text = f"[{g['file']}] ×{g['count']} {g['msg']}"
                if g["lines"]:
                    text += f" (lines {_compact_ranges(g['lines'])})"
                out.append(text)
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
