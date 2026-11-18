# SPDX-License-Identifier: MIT
"""Plain-Python unit tests for jka_anim_tools.paths (no Blender needed).

Run:  python3 tests/test_paths.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jka_anim_tools.paths import normalize_export_args  # noqa: E402
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


print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
