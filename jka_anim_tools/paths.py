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
"""
import os

from .common import JkaError


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
