# SPDX-License-Identifier: MIT
"""B2 core: animation.cfg / animevents.cfg / saberanims.cfg authoring.

bpy-free (importable from headless tests) — the Blender operators and the
``blender/`` CLI scripts call these same functions (one source of logic,
B1 pattern). All functions take the animkit module (``ak``) as their first
argument: animkit is loaded at runtime by ``animkit_bridge`` (decision #12,
shared Python library, never ported).

Session state: the edited document (animkit cfgwrite Doc) is cached per
cfg-file path at module level — the Blender process is the editing session.
"""
import os

from .common import JkaError

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

def cfg_path(basepath, character, kind):
    """basepath/models/players/<character>/<kind>.cfg (kind: animation|animevents)."""
    return os.path.join(basepath, "models", "players", character, kind + ".cfg")


def saber_cfg_path(basepath, explicit=""):
    """The saberanims.cfg: an explicit path, else basepath/ext_data/saberanims.cfg."""
    if explicit:
        return explicit
    return os.path.join(basepath, "ext_data", "saberanims.cfg")


def _read(path, what):
    try:
        with open(path, "r", errors="replace") as f:
            return f.read()
    except OSError as e:
        raise JkaError(f"cannot read {what} {path!r}: {e}")


# ---------------------------------------------------------------------------
# Segments (animation.cfg)
# ---------------------------------------------------------------------------

class SegmentInfo:
    __slots__ = ("name", "first_frame", "num_frames", "loop_frames", "fps", "line")

    def __init__(self, seg):
        self.name = seg.name
        self.first_frame = seg.first_frame
        self.num_frames = seg.num_frames
        self.loop_frames = seg.loop_frames
        self.fps = seg.fps
        self.line = seg.line

    @property
    def range_str(self):
        return f"{self.first_frame}..{self.first_frame + self.num_frames - 1}"

    @property
    def loop_str(self):
        if self.loop_frames == -1:
            return "no loop"
        if self.loop_frames == 0:
            return "loop@0"
        return f"loop@{self.loop_frames}"

    def expected_props(self):
        """What the jediacademy NLA g2_sequence_prop should hold for this
        segment (import maps loopFrames -> bool loop = (loopFrames != -1);
        its cfg export writes 0 for loop / -1 for no-loop — the addon can
        only express those two, a loop point N>0 is lost through Blender)."""
        return bool(self.loop_frames != -1), int(self.fps)


class _SessionState:
    """Per-(basepath, character) editing session (the Blender process is
    the session). The docs are the live edit targets; segments is the
    parsed view (kept in sync by the ops below)."""
    __slots__ = ("segments", "seg_doc", "evt_doc", "evt_text")

    def __init__(self):
        self.segments = None
        self.seg_doc = None
        self.evt_doc = None
        self.evt_text = None


_state = {}  # (abs_basepath, character) -> _SessionState


def _key(basepath, character):
    return (os.path.abspath(basepath), character)


def _ensure_state(ak, basepath, character):
    key = _key(basepath, character)
    st = _state.get(key)
    if st is None:
        st = _SessionState()
        _state[key] = st
    return st


def load_segments(ak, basepath, character):
    """Parse animation.cfg -> (list[SegmentInfo], warnings)."""
    st = _ensure_state(ak, basepath, character)
    path = cfg_path(basepath, character, "animation")
    if not os.path.isfile(path):
        raise JkaError(f"no animation.cfg at {path!r} — set the base path and "
                       "character (or create the cfg first)")
    segs, warns = ak.animevents.parse_animation_cfg(_read(path, "animation.cfg"))
    st.segments = [SegmentInfo(s) for s in segs]
    st.seg_doc = ak.cfgwrite.AnimCfgDoc(_read(path, "animation.cfg"))
    return st.segments, warns


def load_segment_doc(ak, basepath, character):
    st = _ensure_state(ak, basepath, character)
    if st.seg_doc is None:
        load_segments(ak, basepath, character)
    return st.seg_doc


def add_segment(ak, basepath, character, name, first_frame, num_frames,
                loop_frames, fps):
    """Append a segment line via the line-preserving writer (new lines are
    formatted in the file's detected style). Returns (SegmentInfo, text)."""
    st = _ensure_state(ak, basepath, character)
    doc = load_segment_doc(ak, basepath, character)
    seg = doc.add(name, first_frame, num_frames, loop_frames, fps)
    info = SegmentInfo(seg)
    if st.segments is not None:
        st.segments.append(info)
    return info, doc.text()


def next_free_frame(ak, basepath, character):
    """The first frame at/after the end of every loaded segment (0 if the
    cfg is empty) — where a preset segment should start."""
    st = _ensure_state(ak, basepath, character)
    if not st.segments:
        return 0
    return max(s.first_frame + s.num_frames for s in st.segments)


def save_segment_doc(ak, basepath, character):
    """Write animation.cfg (after load_segments or add_segment)."""
    st = _ensure_state(ak, basepath, character)
    if st.seg_doc is None:
        raise JkaError("no animation.cfg loaded (load the segments first)")
    path = cfg_path(basepath, character, "animation")
    try:
        with open(path, "w", newline="") as f:
            f.write(st.seg_doc.text())
    except OSError as e:
        raise JkaError(f"cannot write {path!r}: {e}")
    return path


# ---------------------------------------------------------------------------
# Events (animevents.cfg)
# ---------------------------------------------------------------------------

def _norm_block(block):
    """Engine block names (LOWER/UPPER, NPC_stats.cpp) -> file headers
    (LOWEREVENTS/UPPEREVENTS). Case-insensitive, both forms accepted."""
    b = block.upper()
    if not b.endswith("EVENTS"):
        b += "EVENTS"
    if b not in ("LOWEREVENTS", "UPPEREVENTS"):
        raise JkaError(f"unknown event block {block!r} (LOWER or UPPER)")
    return b

# The AEV types the engine stores from a file (NPC_stats.cpp switch).
# AEV_SABER_SWING/AEV_SABER_SPIN are valid table names with NO switch case
# — the engine silently discards those lines — so they are NOT editable.
EDITABLE_ETYPES = (
    "AEV_SOUND", "AEV_SOUNDCHAN", "AEV_FOOTSTEP", "AEV_EFFECT",
    "AEV_FIRE", "AEV_MOVE",
)

# UI data string -> the data tuple cfgwrite expects, per type
# (field order = the engine's read order, NPC_stats.cpp).
_DATA_SPECS = {
    "AEV_SOUND": ("sound", 4, "sound lo hi chance"),
    "AEV_SOUNDCHAN": ("soundchan", 5, "chan sound lo hi chance"),
    "AEV_FOOTSTEP": ("footstep", 2, "footstepType probability"),
    "AEV_EFFECT": ("effect", 3, "effectPath boltName probability"),
    "AEV_FIRE": ("fire", 2, "altfire probability"),
    "AEV_MOVE": ("move", 3, "forwardPush rightPush upPush"),
}


def data_help(etype):
    kind, n, help_ = _DATA_SPECS[etype]
    return help_


def parse_event_data(ak, etype, data_str):
    """Parse the UI's space-separated data string into the writer's data
    tuple (validates the token count and integer fields; raises JkaError)."""
    if etype not in _DATA_SPECS:
        raise JkaError(f"{etype!r} is not an editable event type "
                       f"({' '.join(EDITABLE_ETYPES)})")
    kind, n, help_ = _DATA_SPECS[etype]
    toks = data_str.split()
    if len(toks) != n:
        raise JkaError(f"{etype} needs {n} data fields — {help_} "
                       f"(got {len(toks)}: {data_str!r})")
    if kind == "sound":
        sound, lo, hi, chance = toks
        return ("sound", sound, _int(ak, "AEV_SOUND", lo, "lo"),
                _int(ak, "AEV_SOUND", hi, "hi"),
                _int(ak, "AEV_SOUND", chance, "chance"), "CHAN_AUTO")
    if kind == "soundchan":
        chan, sound, lo, hi, chance = toks
        if chan not in ak.animevents.CHAN_TYPES:
            raise JkaError(f"unknown channel {chan!r} (engine falls back to "
                           f"CHAN_AUTO; expected one of "
                           f"{', '.join(sorted(ak.animevents.CHAN_TYPES))})")
        return ("soundchan", chan, sound,
                _int(ak, "AEV_SOUNDCHAN", lo, "lo"),
                _int(ak, "AEV_SOUNDCHAN", hi, "hi"),
                _int(ak, "AEV_SOUNDCHAN", chance, "chance"))
    if kind == "footstep":
        ft, prob = toks
        return ("footstep", ft, _int(ak, "AEV_FOOTSTEP", prob, "probability"))
    if kind == "effect":
        path, bolt, prob = toks
        return ("effect", path, bolt, _int(ak, "AEV_EFFECT", prob, "probability"))
    if kind == "fire":
        altfire, prob = toks
        return ("fire", _int(ak, "AEV_FIRE", altfire, "altfire"),
                _int(ak, "AEV_FIRE", prob, "probability"))
    if kind == "move":
        f, r, u = toks
        return ("move", _int(ak, "AEV_MOVE", f, "forward"),
                _int(ak, "AEV_MOVE", r, "right"),
                _int(ak, "AEV_MOVE", u, "up"))
    raise JkaError(f"unhandled data kind {kind!r}")  # pragma: no cover


def _int(ak, etype, tok, what):
    try:
        return int(tok)
    except ValueError:
        raise JkaError(f"{etype} {what} {tok!r} is not an integer")


class EventInfo:
    __slots__ = ("block", "anim", "etype", "key_frame", "data_str", "line")

    def __init__(self, ev, block_header):
        self.block = block_header or ""
        self.anim = ev.anim
        self.etype = ev.etype
        self.key_frame = ev.key_frame
        self.data_str = " ".join(str(t) for t in ev.data[1:])
        self.line = ev.line

    def label(self):
        return f"{self.etype} @ {self.key_frame}: {self.data_str}"


def load_events(ak, basepath, character):
    """Parse animevents.cfg -> (blocks, list[EventInfo], warnings)."""
    st = _ensure_state(ak, basepath, character)
    path = cfg_path(basepath, character, "animevents")
    if not os.path.isfile(path):
        raise JkaError(f"no animevents.cfg at {path!r}")
    st.evt_text = _read(path, "animevents.cfg")
    st.evt_doc = ak.cfgwrite.AnimEventsDoc(st.evt_text)
    infos = [EventInfo(ev, b.header) for b in st.evt_doc.blocks for ev in b.events]
    return st.evt_doc.blocks, infos, st.evt_doc.parse_warnings


def events_for(ak, basepath, character, block, anim):
    """The event infos for one block+segment pair (file order)."""
    st = _ensure_state(ak, basepath, character)
    if st.evt_doc is None:
        load_events(ak, basepath, character)
    block = _norm_block(block)
    out = []
    for b in st.evt_doc.blocks:
        if (b.header or "").upper() != block:
            continue
        for i, ev in enumerate(b.events):
            if ev.anim == anim:
                out.append((i, EventInfo(ev, b.header)))
    return out


def add_event(ak, basepath, character, block, anim, etype, key_frame, data_str):
    """Append an event to the block (created if the file has no such
    block yet). Returns EventInfo."""
    st = _ensure_state(ak, basepath, character)
    if st.evt_doc is None:
        load_events(ak, basepath, character)
    doc = st.evt_doc
    block = _norm_block(block)
    b = next((x for x in doc.blocks if (x.header or "").upper() == block), None)
    if b is None:
        b = doc.add_block(block)
    data = parse_event_data(ak, etype, data_str)
    ev = doc.add_event(b, anim, etype, key_frame, data)
    return EventInfo(ev, b.header)


def remove_event(ak, basepath, character, block, index):
    """Remove event ``index`` from the block's event list."""
    st = _ensure_state(ak, basepath, character)
    if st.evt_doc is None:
        load_events(ak, basepath, character)
    doc = st.evt_doc
    block = _norm_block(block)
    b = next((x for x in doc.blocks if (x.header or "").upper() == block), None)
    if b is None or not (0 <= index < len(b.events)):
        raise JkaError(f"no such event in {block} (index {index})")
    doc.remove_event(b, index)


def save_events(ak, basepath, character):
    """VALIDATE-ON-WRITE: reparse the doc text (structure), validate the
    events against the segment table, then write. Returns (warnings,
    path). Raises JkaError when validation finds ERRORS (the file is not
    touched)."""
    st = _ensure_state(ak, basepath, character)
    if st.evt_doc is None:
        load_events(ak, basepath, character)
    doc = st.evt_doc
    text = doc.text()
    try:
        _blocks, events, pwarns = ak.animevents.parse_animevents_cfg_structured(text)
    except ak.animevents.CfgError as e:
        raise JkaError(f"write blocked — the edited text no longer parses: {e}")
    # validate against the IN-MEMORY segments when the session has them
    # (a preset may have appended a segment that is not saved yet)
    if st.seg_doc is not None:
        try:
            segs, _swarns = ak.animevents.parse_animation_cfg(st.seg_doc.text())
        except ak.animevents.CfgError:
            segs = []
    else:
        seg_path = cfg_path(basepath, character, "animation")
        segs, _swarns = (ak.animevents.parse_animation_cfg(_read(seg_path, "animation.cfg"))
                         if os.path.isfile(seg_path) else ([], []))
    errors, warnings = ak.animevents.validate_events(events, segs)
    warnings = list(pwarns) + warnings
    if errors:
        raise JkaError("write blocked — validation errors:\n"
                       + "\n".join(f"  {e}" for e in errors))
    path = cfg_path(basepath, character, "animevents")
    try:
        with open(path, "w", newline="") as f:
            f.write(text)
    except OSError as e:
        raise JkaError(f"cannot write {path!r}: {e}")
    st.evt_text = text
    return warnings, path


# ---------------------------------------------------------------------------
# Saber (saberanims.cfg validation + segment presets)
# ---------------------------------------------------------------------------

# Built-in fallback = the engine's s_defaultStyleSheet (wp_saber.c) —
# verified against the live mod's ext_data/saberanims.cfg (identical values).
_BUILTIN_STYLES = (
    ("fast", "BOTH_H1_S1_TR"), ("medium", "BOTH_H1_S1_T_"),
    ("strong", "BOTH_H1_S1_BL"), ("desann", "BOTH_H1_S1_BR"),
    ("tavion", "BOTH_H1_S1_TL"), ("dual", "BOTH_H6_S6_T_"),
    ("staff", "BOTH_H7_S7_T_"),
)
_NEUTRAL_ANIM = "BOTH_STAND1"  # every style's neutralAnim


def validate_saberanims(ak, basepath, explicit=""):
    """Parse + validate saberanims.cfg -> (styles, errors, warnings, path).
    A missing file is NOT an error (the engine falls back to its built-in
    style sheet) — it yields the built-in styles and an empty result."""
    path = saber_cfg_path(basepath, explicit)
    if not os.path.isfile(path):
        styles, errors, warnings = [], [], []
        return styles, errors, warnings, path
    styles, errors, warnings = ak.saberanims.parse_saberanims(_read(path, "saberanims.cfg"))
    return styles, errors, warnings, path


class SaberPreset:
    __slots__ = ("label", "name", "loop_frames", "num_frames", "fps")

    def __init__(self, label, name, num_frames=20, fps=20):
        self.label = label
        self.name = name
        self.loop_frames = -1  # swings do not loop
        self.num_frames = num_frames
        self.fps = fps


def saber_presets(ak, basepath, explicit=""):
    """Guard + one attack preset per saber style. The attack names come from
    the (validated) saberanims.cfg openAnim values — the engine's
    per-style entry swings — falling back to the built-in sheet when the
    file is absent. Returns list[SaberPreset]."""
    styles, _errors, _warnings, _path = validate_saberanims(ak, basepath, explicit)
    openanim = {st.name: (st.values.get("openanim") or "") for st in styles}
    presets = [SaberPreset("guard (stand)", _NEUTRAL_ANIM)]
    for name, built_in in _BUILTIN_STYLES:
        anim = openanim.get(name) or built_in
        presets.append(SaberPreset(f"attack: {name} ({anim})", anim))
    return presets
