# SPDX-License-Identifier: MIT
"""Plain-Python unit tests for jka_anim_tools.paths (no Blender needed).

Run:  python3 tests/test_paths.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jka_anim_tools.paths import (  # noqa: E402
    normalize_export_args, derive_basepath_from_file, derive_ref_gla,
    derive_export_paths, DEFAULT_REF_GLA)
from jka_anim_tools.common import JkaError  # noqa: E402

BASE = "/opt/mods/mychar"
G = "models/players/mychar/mychar.gla"
R = "models/players/_humanoid/_humanoid.gla"

passed = failed = 0


def check(name, fn):
    global passed, failed
    try:
        fn()
        passed += 1
        print(f"  ok  {name}")
    except AssertionError as e:
        failed += 1
        print(f" FAIL {name}: {e}")


def expect_error(name, fn):
    def run():
        try:
            fn()
        except JkaError:
            return
        raise AssertionError(f"expected JkaError, none raised ({name})")
    check(name, run)


# --- happy paths ---
def t_inside():
    out, base, gl, ref = normalize_export_args(
        BASE + "/" + G, BASE, G, R)
    assert out == BASE + "/" + G, out
    assert base == BASE
    assert gl == G and ref == R
check("abs paths pass through", t_inside)


def t_rel_input():
    # relative inputs are absolutized against CWD (old-script contract)
    out, base, gl, ref = normalize_export_args("x.gla", ".", G, R)
    assert os.path.isabs(out) and os.path.isabs(base)
    assert out == os.path.abspath("x.gla") and base == os.path.abspath(".")
check("relative in -> absolute out", t_rel_input)


def t_empty_basepath():
    # parity with the old contract: basepath is optional (not validated)
    out, base, gl, ref = normalize_export_args("/a/b.gla", "", G, R)
    assert base == "" and out == "/a/b.gla"
check("empty basepath tolerated (parity)", t_empty_basepath)


# --- errors the addon would only surface confusingly ---
def t_outside():
    try:
        normalize_export_args("/elsewhere/b.gla", BASE, G, R)
    except JkaError as e:
        assert "inside basepath" in str(e)
        return
    raise AssertionError("expected JkaError for output outside basepath")
check("output outside basepath rejected", t_outside)


def t_abs_glapath():
    try:
        normalize_export_args(BASE + "/" + G, BASE, "/abs/mychar.gla", R)
    except JkaError as e:
        assert "glapath" in str(e)
        return
    raise AssertionError("expected JkaError for absolute glapath")
check("absolute glapath rejected", t_abs_glapath)


def t_abs_ref():
    try:
        normalize_export_args(BASE + "/" + G, BASE, G, "/abs/_humanoid.gla")
    except JkaError as e:
        assert "reference" in str(e)
        return
    raise AssertionError("expected JkaError for absolute ref")
check("absolute ref rejected", t_abs_ref)


# --- one-base-path derivation (review item #4) ---
import shutil  # noqa: E402
import tempfile  # noqa: E402

TB = tempfile.mkdtemp(prefix="jka_paths_")


def _make_tree():
    """A fake mod folder: <TB>/models/players/{mychar,_humanoid} + ext_data."""
    for d in ("models/players/mychar", "models/players/_humanoid",
              "ext_data"):
        os.makedirs(os.path.join(TB, d), exist_ok=True)
    open(os.path.join(TB, "models/players/mychar/mychar.gla"), "w").close()
    open(os.path.join(TB, "models/players/_humanoid/_humanoid.gla"),
         "w").close()
    return TB


def t_derive_basepath():
    base = _make_tree()
    f = os.path.join(base, "models/players/mychar/mychar.gla")
    assert derive_basepath_from_file(f) == base
    # one level up from the character dir (a cfg in the dir itself)
    assert derive_basepath_from_file(
        os.path.join(base, "models/players/mychar")) == base
    # a file with no models/players above it (separate tree!)
    stray_root = tempfile.mkdtemp(prefix="jka_paths_stray_")
    try:
        stray = os.path.join(stray_root, "elsewhere", "x.gla")
        os.makedirs(os.path.dirname(stray), exist_ok=True)
        open(stray, "w").close()
        assert derive_basepath_from_file(stray) == ""
    finally:
        shutil.rmtree(stray_root, ignore_errors=True)
    assert derive_basepath_from_file("") == ""
check("derive_basepath_from_file walks up to models/players",
      t_derive_basepath)


def t_ref_gla_derived():
    base = _make_tree()
    # character's own GLA wins
    assert derive_ref_gla(base, "mychar") == \
        os.path.join(base, "models/players/mychar/mychar.gla")
    # no own GLA -> stock _humanoid
    assert derive_ref_gla(base, "ghost") == \
        os.path.join(base, "models/players/_humanoid/_humanoid.gla")
    # explicit absolute wins over the derivation
    own = os.path.join(base, "models/players/_humanoid/_humanoid.gla")
    assert derive_ref_gla(base, "mychar", explicit=own) == own
    # explicit relative resolves against base
    rel = "models/players/mychar/mychar.gla"
    assert derive_ref_gla(base, "mychar", explicit=rel) == \
        os.path.join(base, rel)
check("derive_ref_gla: own -> stock -> explicit", t_ref_gla_derived)


def t_ref_gla_errors():
    expect_error("ref gla: no basepath",
                 lambda: derive_ref_gla("", "mychar"))
    expect_error("ref gla: relative explicit w/o basepath",
                 lambda: derive_ref_gla("", "mychar", explicit="x/y.gla"))
    expect_error("ref gla: nothing exists under base",
                 lambda: derive_ref_gla(os.path.join(TB, "nomods"), "mychar"))
check("derive_ref_gla errors name the missing piece", t_ref_gla_errors)


def t_ref_gla_folder_pick():
    """Item 4 (Sheng 5.1.1 retest): the user picks the FOLDER, not the
    .gla — resolve it instead of failing in the importer."""
    base = _make_tree()
    # folder whose own-name .gla exists (mychar -> mychar.gla)
    d1 = os.path.join(base, "models/players/mychar")
    assert derive_ref_gla(base, "mychar", explicit=d1) == \
        os.path.join(d1, "mychar.gla")
    # Sheng's shape: a copy dir holding a single .gla under another name
    d2 = os.path.join(base, "models", "players", "_humanoid - Copy")
    os.makedirs(d2, exist_ok=True)
    open(os.path.join(d2, "_humanoid.gla"), "w").close()
    assert derive_ref_gla(base, "mychar", explicit=d2) == \
        os.path.join(d2, "_humanoid.gla")
    # model.gla convention (NPC folders)
    d3 = os.path.join(base, "models", "players", "npc_x")
    os.makedirs(d3, exist_ok=True)
    open(os.path.join(d3, "model.gla"), "w").close()
    assert derive_ref_gla(base, "mychar", explicit=d3) == \
        os.path.join(d3, "model.gla")
    # several .gla, no own-name: a clear error, not the importer's
    d4 = os.path.join(base, "models", "players", "two")
    os.makedirs(d4, exist_ok=True)
    open(os.path.join(d4, "a.gla"), "w").close()
    open(os.path.join(d4, "b.gla"), "w").close()
    expect_error("ref gla: folder with several .gla",
                 lambda: derive_ref_gla(base, "mychar", explicit=d4))
    # empty folder: a clear error
    d5 = os.path.join(base, "models", "players", "empty")
    os.makedirs(d5, exist_ok=True)
    expect_error("ref gla: empty folder",
                 lambda: derive_ref_gla(base, "mychar", explicit=d5))
check("derive_ref_gla: folder pick resolves the .gla", t_ref_gla_folder_pick)


def t_export_derived():
    base = _make_tree()
    out, b, gl, ref = derive_export_paths(base, "mychar")
    assert gl == "models/players/mychar/mychar.gla", gl
    assert out == os.path.join(base, "models/players/mychar/mychar.gla"), out
    assert ref == DEFAULT_REF_GLA
    # explicit glapath + ref pass through the same validation
    out, b, gl, ref = derive_export_paths(
        base, "mychar", glapath="models/players/mychar/alt.gla",
        ref="models/players/_humanoid/_humanoid.gla")
    assert gl == "models/players/mychar/alt.gla"
    assert out == os.path.join(base, "models/players/mychar/alt.gla")
check("derive_export_paths defaults (char dir + stock ref)",
      t_export_derived)


def t_export_errors():
    expect_error("export: no basepath",
                 lambda: derive_export_paths("", "mychar"))
    expect_error("export: no character, no glapath",
                 lambda: derive_export_paths(_make_tree(), ""))
check("derive_export_paths errors name the missing piece", t_export_errors)


shutil.rmtree(TB, ignore_errors=True)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
