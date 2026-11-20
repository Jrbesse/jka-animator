# SPDX-License-Identifier: MIT
"""Export path shaping/validation. bpy-free (unit-testable in plain Python).

Rules verified against the jediacademy addon v2.1.0 (S1, 2026-11-17):
* ``basepath`` must be ABSOLUTE — the addon resolves the output by
  string-prefix match (RelPath); a relative basepath never matches the
  absolute output path and the operator dies with "Invalid Base Path".
* the export ``filepath`` must be absolute AND inside ``basepath`` (the
  addon derives the relative name from the prefix match).
* ``glapath`` (the in-GLA path) and ``glareference`` are BASEPATH-RELATIVE;
  absolute values fail ("Could not find reference GLA").

The derive_* helpers (2026-11-20 review item #4) let the user set the base
path ONCE: everything else — the reference GLA, the export output and the
in-GLA path — is derived from ``<base>/models/players/<character>/`` and a
clear JkaError is raised when it cannot be derived ("base path should be
in the same path, just back a few steps, and if not it can throw an
error").
"""
import os

from .common import JkaError

# The stock reference skeleton GLA (base-relative) — the export's bone
# index template and the default matching reference.
DEFAULT_REF_GLA = "models/players/_humanoid/_humanoid.gla"


def normalize_export_args(out, basepath, glapath, ref):
    """Shape + validate the addon's export_scene.gla path arguments.

    Returns ``(out_abs, base_abs, glapath, ref)``. Mirrors the old
    prepare_rig.py contract (basepath optional, both paths absolutized) and
    adds early, clear errors for inputs the addon would reject with a
    confusing message.
    """
    out_abs = os.path.abspath(out)
    base = os.path.abspath(basepath) if basepath else ""
    if base and not (out_abs == base or out_abs.startswith(base + os.sep)):
        raise JkaError(
            f"export: output {out_abs!r} must be inside basepath {base!r} — "
            "the addon derives the GLA path from the basepath prefix")
    if glapath and os.path.isabs(glapath):
        raise JkaError(
            f"export: glapath must be base-relative, got absolute {glapath!r}")
    if ref and os.path.isabs(ref):
        raise JkaError(
            f"export: ref (gla reference) must be base-relative, got "
            f"absolute {ref!r} — it is resolved against the basepath")
    return out_abs, base, glapath, ref


# ---------------------------------------------------------------------------
# one-base-path derivation (review item #4)
# ---------------------------------------------------------------------------

def _clean_character(character):
    """The character folder name (a real character or ``_humanoid``)."""
    return (character or "").strip().strip(os.sep).strip("/")


def derive_basepath_from_file(file):
    """The mod folder (the directory that CONTAINS ``models/players``) at or
    above ``file``, walking up — '' when none exists.

    In-mod files always live a few steps below the base path
    (``<base>/models/players/<character>/<file>.gla``), so a typed file
    path carries its base path with it.
    """
    if not file:
        return ""
    d = os.path.dirname(os.path.abspath(file))
    while True:
        if os.path.isdir(os.path.join(d, "models", "players")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return ""
        d = parent


def derive_ref_gla(basepath, character, explicit=""):
    """The reference GLA (absolute path) for the matching import.

    An explicit value wins — a relative one is resolved against
    ``basepath``. Otherwise ``<base>/models/players/<character>/
    <character>.gla`` when that file exists, else the NPC convention
    ``<base>/models/players/<character>/model.gla`` (NPC folders ship
    their GLA under that name), else the stock ``_humanoid`` GLA.
    JkaError when nothing can be derived.
    """
    if explicit:
        if os.path.isabs(explicit):
            return os.path.abspath(explicit)
        if not basepath:
            raise JkaError(
                f"the reference GLA {explicit!r} is relative — set the "
                "Base Path (top of the panel) first")
        return os.path.abspath(os.path.join(os.path.abspath(basepath),
                                            explicit))
    if not basepath:
        raise JkaError(
            "no reference GLA — set the Base Path (top of the panel, the "
            "mod folder that contains models/players) or type the "
            "reference GLA path")
    base = os.path.abspath(basepath)
    char = _clean_character(character) or "_humanoid"
    own = os.path.join(base, "models", "players", char, f"{char}.gla")
    if os.path.isfile(own):
        return own
    npc = os.path.join(base, "models", "players", char, "model.gla")
    if os.path.isfile(npc):
        return npc
    stock = os.path.join(base, *DEFAULT_REF_GLA.split("/"))
    if os.path.isfile(stock):
        return stock
    raise JkaError(
        f"no reference GLA under {base} — tried {own}, {npc} and "
        f"{stock}; set the Reference GLA field to the file you want")


def derive_export_paths(basepath, character, glapath="", ref=""):
    """``(out_abs, base_abs, glapath, ref)`` for the GLA export, derived
    from the ONE base path + character:

    * glapath (in-GLA, base-relative) defaults to
      ``models/players/<character>/<character>.gla``;
    * the output file is ``<basepath>/<glapath>``;
    * ref defaults to the stock ``_humanoid`` GLA (bone indices).

    JkaError with the exact missing piece named (review item #4/#8).
    """
    if not basepath:
        raise JkaError(
            "no Base Path set — set it at the top of the panel (the mod "
            "folder that contains models/players)")
    char = _clean_character(character)
    if not glapath:
        if not char:
            raise JkaError(
                "set the Character (the folder under models/players, e.g. "
                "assassin_droid) so the output path can be derived")
        glapath = f"models/players/{char}/{char}.gla"
    if not ref:
        ref = DEFAULT_REF_GLA
    out = os.path.abspath(os.path.join(os.path.abspath(basepath),
                                       glapath.replace("/", os.sep)))
    return normalize_export_args(out, basepath, glapath, ref)
