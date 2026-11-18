# SPDX-License-Identifier: MIT
"""Shared names, modes and the error type. bpy-free (importable anywhere)."""

# The addon's GLA exporter hard-requires an armature OBJECT named exactly
# "skeleton_root" (decision #9 evidence). "rig_armature" is where we move it
# while a reference GLA is loaded (the importer would otherwise reuse it).
MIRROR = "skeleton_root"
RIG_NAME = "rig_armature"
REF_NAME = "reference_humanoid"

# Reference-import modes -> the addon's import_scene.gla loadAnimations values
VALID_MODES = ("none", "cfg", "all", "range")
MODE_TO_OP = {"none": "NONE", "cfg": "CFG", "all": "ALL", "range": "RANGE"}


class JkaError(Exception):
    """User-facing failure with a complete message (raise, never print).

    The CLI wrappers convert it to SystemExit; the operators report it.
    """
