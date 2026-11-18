# SPDX-License-Identifier: MIT
"""GLA export orchestration over the addon's export_scene.gla operator.

Verified S1 (2026-11-17, Blender 5.3.0): skeleton export
byte-compatible with ``_humanoid`` (53/53 bones), 240-frame round-trip
reproduces a genuine Raven engine file within compression tolerance.

Caveat C2: a frame EXACTLY at rest encodes to an all-identity pool, which
the engine decodes as all bones at the root origin. Near-rest frames are
fine; authored action frames will not sit exactly at rest.
"""
import bpy

from .addon_bridge import ensure_addon
from .paths import normalize_export_args
from .rigprep import find_mirror, restore_legacy_scale
from .common import MIRROR, JkaError


def export_gla(out, basepath="", glapath="", ref="", frame_start=None,
               frame_end=None, addon_dir=None):
    """Export the scene's ``skeleton_root`` armature to a .gla via the
    addon operator. Returns the absolute output path.

    ``out``: output file (absolute, inside ``basepath``).
    ``basepath``: the mod folder that contains ``models/...``.
    ``glapath``: base-relative in-GLA path (e.g.
      ``models/players/mychar/mychar.gla``).
    ``ref``: base-relative reference GLA (e.g.
      ``models/players/_humanoid/_humanoid.gla``) — copies the bone
      indices so the export lines up with existing models.
    ``frame_start``/``frame_end``: override the scene frame range
      (None = use the scene's current range).
    ``addon_dir``: see addon_bridge.ensure_addon.
    """
    out_abs, base, glapath, ref = normalize_export_args(
        out, basepath, glapath, ref)

    scene = bpy.context.scene
    if frame_start is not None:
        scene.frame_start = int(frame_start)
    if frame_end is not None:
        scene.frame_end = int(frame_end)
    if scene.frame_end < scene.frame_start:
        raise JkaError(
            "frame range is empty — set a frame start/end")
    if scene.frame_end == scene.frame_start:
        raise JkaError(
            "refusing to export a 1-frame GLA — set a frame end (and note "
            "caveat C2: a frame exactly at rest encodes degenerate)")

    arm = find_mirror()

    def _do():
        # the legacy-scale restore must run AFTER any late addon
        # registration (register can materialize g2_prop at its default)
        restore_legacy_scale(arm)
        return bpy.ops.export_scene.gla(
            filepath=out_abs, basepath=base,
            glapath=glapath, glareference=ref)

    # hasattr() on bpy.ops proxies is unreliable (lazy generation): probe
    # by calling and recovering once. A failed call writes nothing, so the
    # retry is a clean single export.
    try:
        _do()
    except AttributeError:
        ensure_addon(addon_dir, "export_scene.gla")
        _do()

    print(f"jka_anim_tools: exported {out_abs} "
          f"({scene.frame_start}..{scene.frame_end})")
    print("jka_anim_tools: VALIDATE with the animkit gate, e.g.\n"
          "  python -m animkit check <character-dir>")
    return out_abs
