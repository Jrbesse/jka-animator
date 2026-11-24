# SPDX-License-Identifier: MIT
"""Settings persistence across Blender restarts (review item #10).

The panel's scene properties are session-scene by design (the .blend is
never saved by this add-on), so Sheng was re-typing everything on every
Blender start. The top-level fields are therefore mirrored to a small
JSON in the user config dir:

    Windows: %APPDATA%/jka_anim_tools/settings.json
    others:  ~/.config/jka_anim_tools/settings.json

Saved whenever a persisted field changes (RNA update callback); restored
on register (startup scene), on every scene load (load_post) and lazily
on first panel draw (covers File > New across versions). Collections
(segments/events/results), the segment filter and transient selections
stay session-only.
"""
import json
import os
import sys

import bpy

# The persisted field names (all on the scene's jka_anim prop group).
PERSISTED = (
    "basepath", "character",
    "ref_gla", "ref_mode", "ref_start", "ref_frames",
    "exp_ref", "exp_custom_frames", "exp_frame_start", "exp_frame_end",
    "addon_dir", "animkit_dir", "saber_cfg", "evt_block",
)

# None = auto: enabled only in interactive sessions. Headless/background
# runs (the blender/ drivers, CI, e2e) set scene properties freely and
# must never write or restore the user's settings file; tests can flip
# this explicitly.
ENABLED = None
_RESTORING = False
# Guard so per-frame panel draws don't pile up deferred-restore timers.
_SCHEDULED = False

# The "already restored" marker: a custom property ON the scene (gone when
# the scene is gone). Deliberately NOT id(scene): a deleted scene's id
# would sit in a module set forever, and a fresh scene reusing that
# address would be skipped as already-restored — the restore silently
# lost (the old _RESTORED_SCENES set had exactly this hole).
_MARKER = "jka_anim_restored"


def _mark(scene):
    try:
        scene[_MARKER] = True
    except (TypeError, KeyError):
        pass


def _enabled():
    if ENABLED is None:
        return not bpy.app.background
    return bool(ENABLED)


def settings_path():
    """Where settings.json lives (the user config dir, not the project)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "jka_anim_tools")
    else:
        d = os.path.join(os.path.expanduser("~"), ".config", "jka_anim_tools")
    return os.path.join(d, "settings.json")


def save(p):
    """Write p's persisted fields to settings.json (atomic replace).

    Skipped while a restore is in flight (the restore's own writes would
    not be a change), in headless/background runs (ENABLED=None defaults
    to "interactive only" — a driver setting scene properties must never
    clobber the user's real settings file; the 5.1 repro run did exactly
    that until this gate), or when the file cannot be written
    (read-only home — the panel keeps working, settings just don't stick).
    """
    if not _enabled():
        return
    if _RESTORING:
        return
    data = {k: getattr(p, k) for k in PERSISTED if hasattr(p, k)}
    try:
        path = settings_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=1)
        os.replace(tmp, path)
    except OSError as e:
        print(f"jka_anim_tools: could not save settings: {e}")


def restore(p):
    """Fill p's fields from settings.json. No file = no-op -> False;
    file read and applied -> True. Never raises (a corrupt file is
    reported and ignored — the panel must not fail to draw)."""
    global _RESTORING
    path = settings_path()
    if not os.path.isfile(path):
        return False
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return False
    except (OSError, ValueError) as e:
        print(f"jka_anim_tools: ignoring unreadable settings file: {e}")
        return False
    _RESTORING = True
    try:
        for k, v in data.items():
            if hasattr(p, k) and v not in (None, ""):
                try:
                    setattr(p, k, v)
                except (TypeError, ValueError):
                    pass  # a type mismatch after an add-on update — skip
    finally:
        _RESTORING = False
    return True


def _do_restore():
    """Deferred-restore timer body — runs in the MAIN LOOP, a context where
    writing Scene ID data IS allowed. Marks the current scene restored and
    fills its persisted fields from settings.json. Idempotent: a no-op if the
    scene is already marked. Returns None (one-shot timer)."""
    global _SCHEDULED
    _SCHEDULED = False
    try:
        scene = bpy.context.scene
        if scene is None or scene.get(_MARKER):
            return None
        _mark(scene)
        p = getattr(scene, "jka_anim", None)
        if p is not None:
            restore(p)
        try:
            bpy.context.window.tag_redraw()
        except Exception:
            pass
    except Exception as e:
        print(f"jka_anim_tools: deferred settings restore failed: {e}")
    return None


def maybe_schedule_restore(scene):
    """First-draw safety net that is SAFE to call from panel.draw().

    A panel draw runs in a UI context where writing ID data (the scene's
    ``jka_anim`` group, or a custom marker property on the scene) raises
    ``AttributeError: Writing to ID classes in this context is not allowed``
    — and an exception in draw() blanks the ENTIRE panel body. So this does
    ONLY a read here: if the scene is not yet marked restored, it schedules a
    one-shot timer that performs the actual restore in the main loop (where
    such writes are permitted). Deduplicated via ``_SCHEDULED`` so per-frame
    draws don't pile up timers. ``scene=None`` defers the check to the timer
    (used from register(), where the context scene may not be ready yet).
    """
    global _SCHEDULED
    if not _enabled():
        return
    if scene is not None:
        try:
            if scene.get(_MARKER):
                return
        except Exception:
            pass
    if _SCHEDULED:
        return
    _SCHEDULED = True
    try:
        bpy.app.timers.register(_do_restore, first_interval=0.0)
    except Exception as e:
        _SCHEDULED = False
        print(f"jka_anim_tools: could not schedule settings restore: {e}")


def ensure_restored(scene):
    """SYNCHRONOUS restore — for NON-draw contexts only (load_post, an
    operator, a test). Do NOT call from panel.draw(): it writes Scene ID
    data, which the draw context forbids (see maybe_schedule_restore)."""
    if not _enabled():
        return
    if scene.get(_MARKER):
        return
    _mark(scene)
    p = getattr(scene, "jka_anim", None)
    if p is not None:
        restore(p)


def _on_load_post(dummy=None):
    """Restore EVERY restored-able scene, not just the context one.

    In some Blender builds the load_post context still points at the OLD
    scene (or none), so ``bpy.context.scene`` alone can miss the scene
    that was just opened (Sheng item 3: settings not loading on 5.1 —
    the mechanism verified on 5.1.1, so the missing piece was context/
    version state, not the file format). Iterating bpy.data.scenes is
    cheap (a handful) and context-independent; the marker keeps it
    idempotent.
    """
    try:
        for scene in bpy.data.scenes:
            if scene.get(_MARKER):
                continue
            p = getattr(scene, "jka_anim", None)
            if p is None:
                continue
            restore(p)
            _mark(scene)
    except Exception as e:  # a settings failure must not block a file open
        print(f"jka_anim_tools: settings restore failed: {e}")


def on_change(self, context):
    """The update callback for every persisted field (attached at PROPERTY
    DEFINITION time — panel.py passes it to each bpy.props definition).

    5.x gotcha (root cause of Sheng retest #8): in Blender 5.0 the RNA
    property objects no longer expose a settable ``.update`` after
    registration (and ``bpy.types.Scene.jka_anim`` is a non-subscriptable
    ``_PropertyDeferred``), so the old post-registration attach loop
    silently attached NOTHING — settings never saved, nothing restored.
    Definition-time ``update=`` is the documented path on both 4.x and
    5.x. ``self`` is the owning JkaAnim_PropGroup instance.

    May run in a threaded context (Blender docs); save() is a small
    atomic write and never raises.
    """
    save(self)


def register():
    """Attach the load_post handler + restore the startup scene.

    Must run AFTER the panel register (the jka_anim property must exist).
    No-op in headless/background mode (see ENABLED).

    The per-field update callbacks are attached at PROPERTY DEFINITION
    time (panel.py passes ``persist.on_change`` to each bpy.props
    definition) — Blender 5.x does not allow attaching ``.update`` after
    registration, and the old post-registration loop silently attached
    nothing (Sheng retest #8).
    """
    if not _enabled():
        return
    if _on_load_post not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load_post)
    # Restore the startup scene. Registration can run before the startup
    # scene is ready (the write then silently fails and the scene is left
    # unmarked), so ALSO schedule the deferred restore as a safety net — it
    # is a no-op if the scene is already marked restored.
    try:
        scene = bpy.context.scene
        p = getattr(scene, "jka_anim", None)
        if p is not None:
            restore(p)
            _mark(scene)
    except Exception:
        pass
    maybe_schedule_restore(None)


def unregister():
    if not _enabled():
        return
    try:
        if _on_load_post in bpy.app.handlers.load_post:
            bpy.app.handlers.load_post.remove(_on_load_post)
    except Exception:
        pass
