# SPDX-License-Identifier: MIT
"""Runtime loader for the animkit package (Jrbesse/jka-animkit).

animkit is the format ground truth (spec decision #8) and a shared Python
library this addon imports (decision #12) — loaded at runtime as a separate
package, never ported into the addon (same boundary pattern as the
jediacademy bridge). bpy-free: importable from headless tests.

Search order for the directory that CONTAINS the ``animkit`` package:
1. an explicit dir (the panel's 'animkit dir' field / CLI flag),
2. the ``JKA_ANIMKIT_DIR`` environment variable,
3. ``~/work/jka-animkit`` (the dev-machine clone).
"""
import importlib
import os
import sys

from .common import JkaError

_LOADED_FROM = None  # the directory the current sys.modules['animkit'] came from

_DEV_DEFAULT = os.path.expanduser("~/work/jka-animkit")

_CANDIDATE_ORDER = ("explicit", "JKA_ANIMKIT_DIR", "dev clone")


def _is_animkit_dir(d):
    return bool(d) and os.path.isdir(os.path.join(d, "animkit"))


def resolve_dir(animkit_dir=""):
    """First usable directory (containing the 'animkit' package), or ''."""
    env = os.environ.get("JKA_ANIMKIT_DIR", "")
    for d in (animkit_dir, env, _DEV_DEFAULT):
        if _is_animkit_dir(d):
            return d
    return ""


def get_animkit(animkit_dir=""):
    """Import (idempotently) and return the animkit package module.

    Raises JkaError listing the searched locations when it cannot be found.
    """
    global _LOADED_FROM
    d = resolve_dir(animkit_dir)
    if not d:
        searched = [
            f"the 'animkit dir' field ({animkit_dir!r})",
            f"$JKA_ANIMKIT_DIR ({os.environ.get('JKA_ANIMKIT_DIR', '')!r})",
            f"the dev clone ({_DEV_DEFAULT})",
        ]
        raise JkaError(
            "animkit (the JKA cfg/GLA format library) was not found — set "
            "the 'animkit dir' field to the folder that CONTAINS the "
            f"'animkit' package. Searched: " + "; ".join(searched) + ".")
    if _LOADED_FROM == d and "animkit" in sys.modules:
        mod = sys.modules["animkit"]
    else:
        if _LOADED_FROM is not None and _LOADED_FROM != d:
            # a different dir was requested after a load — start clean
            for name in [n for n in sys.modules if n == "animkit" or n.startswith("animkit.")]:
                del sys.modules[name]
            if d in sys.path:
                sys.path.remove(d)
        if d not in sys.path:
            sys.path.insert(0, d)
        try:
            mod = importlib.import_module("animkit")
        except Exception as e:
            raise JkaError(f"failed to import animkit from {d}: {e}")
        _LOADED_FROM = d
    # animkit/__init__ does not import the submodules — the addon reaches
    # them as attributes, so pull them in explicitly (idempotent)
    for sub in ("animevents", "cfgwrite", "saberanims", "animtable", "check"):
        importlib.import_module(f"animkit.{sub}")
    return mod
