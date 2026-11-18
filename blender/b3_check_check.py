# SPDX-License-Identifier: MIT
"""b3_check_check.py — B3 headless functional driver (the check op).

Exercises the NEW bpy face — registers the addon and drives
jka_anim.check_run via bpy.ops exactly like the N-panel would — on a
SCRATCH copy of a real mod tree (the given --base is never modified).
Runs in `--background` Blender 5.3.

  blender --background RIG.blend --python blender/b3_check_check.py -- \
      --base /path/to/mod-folder --character assassin_droid \
      [--skeleton _humanoid] [--animkit-dir DIR]

--base must stage models/players/<character> AND the skeleton dir
(models/players/_humanoid — the check resolves the cfgs through it,
the engine-mirrored behavior). RIG.blend supplies the armature (any
armature works — the check op is data-only and never touches the scene).

Checks (each via bpy.ops; exit 0 + 'B3 CHECK PASSED' when all hold):
  1. skeleton clean     check _humanoid -> OK, no error lines, the live
                        cfg's warnings present (warning lines)
  2. character clean    check assassin_droid -> OK, the force_shield
                        skin warning present, no error lines
  3. corrupt gla        header numBones 53->60 -> FAILED with >=1 error
                        line; the op still FINISHED (a finding, never a
                        crash)
  4. seeded cfg error   BOTH_FAKE_XYZ appended to animation.cfg ->
                        FAILED summary (marked as an error line), error
                        line names BOTH_FAKE_XYZ
  5. missing char       no_such_char -> CANCELLED, the report names it
  6. no basepath        empty base path -> CANCELLED
  7. base untouched     every file of the given --base is byte-identical
"""
import os
import shutil
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def _arg(args, name, default):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args):
            return args[i + 1]
    return default


def _snapshot(root):
    out = {}
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            fp = os.path.join(dirpath, f)
            out[os.path.relpath(fp, root)] = open(fp, "rb").read()
    return out


def main():
    import bpy
    import jka_anim_tools

    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    base = _arg(args, "--base", "")
    character = _arg(args, "--character", "assassin_droid")
    skeleton = _arg(args, "--skeleton", "_humanoid")
    animkit_dir = _arg(args, "--animkit-dir", os.environ.get("JKA_ANIMKIT_DIR", ""))
    if not base:
        raise SystemExit("b3_check_check: pass --base <mod folder>")
    char_src = os.path.join(base, "models", "players", character)
    skel_src = os.path.join(base, "models", "players", skeleton)
    if not os.path.isdir(char_src):
        raise SystemExit(f"b3_check_check: no such character: {char_src}")
    if not os.path.isdir(skel_src):
        raise SystemExit(f"b3_check_check: no such skeleton: {skel_src}")

    # scratch copy — the given base is never modified
    work_root = tempfile.mkdtemp(prefix="jka_b3_check_")
    before = _snapshot(base)
    dst_root = os.path.join(work_root, "models", "players")
    os.makedirs(dst_root)
    shutil.copytree(char_src, os.path.join(dst_root, character))
    shutil.copytree(skel_src, os.path.join(dst_root, skeleton))

    jka_anim_tools.register()
    p = bpy.context.scene.jka_anim
    p.cfg_basepath = work_root
    p.cfg_character = character
    p.animkit_dir = animkit_dir

    failures = []

    def check(num, what, cond, detail=""):
        status = "ok " if cond else "FAIL"
        print(f"  [{status}] {num}. {what}" + (f" — {detail}" if detail and not cond else ""),
              flush=True)
        if not cond:
            failures.append(what)

    def run_check(char):
        p.cfg_character = char
        try:
            ret = bpy.ops.jka_anim.check_run()
            return set(ret), ""
        except RuntimeError as e:
            return {"CANCELLED"}, str(e)

    def results():
        return [(r.text, r.is_error) for r in p.results]

    # 1. skeleton clean
    ret, _msg = run_check(skeleton)
    lines = results()
    summary = lines[0][0] if lines else ""
    err_lines = [t for t, e in lines if e]
    warn_lines = [t for t, e in lines[1:] if not e]
    check(1, "check _humanoid clean",
          "FINISHED" in ret and lines and "OK" in summary and not lines[0][1]
          and not err_lines and len(warn_lines) > 0,
          f"ret={ret} summary={summary!r} errs={err_lines} n_warn={len(warn_lines)}")

    # 2. character clean (the force_shield skin warning is the fixture's known one)
    ret, _msg = run_check(character)
    lines = results()
    summary = lines[0][0] if lines else ""
    err_lines = [t for t, e in lines if e]
    warn_lines = [t for t, e in lines[1:] if not e]
    check(2, f"check {character} clean",
          "FINISHED" in ret and lines and "OK" in summary and not lines[0][1]
          and not err_lines and any("force_shield" in t for t in warn_lines),
          f"ret={ret} summary={summary!r} errs={err_lines} warns={warn_lines}")

    # 3. corrupt gla (GLA header <ii64sf6i>: numBones @ offset 84, 53 -> 60)
    gla = os.path.join(dst_root, skeleton, f"{skeleton}.gla")
    with open(gla, "r+b") as f:
        f.seek(84)
        f.write(struct.pack("<i", 60))
    ret, _msg = run_check(skeleton)
    lines = results()
    summary = lines[0][0] if lines else ""
    err_lines = [t for t, e in lines if e]
    check(3, "corrupt gla -> finding, not a crash",
          "FINISHED" in ret and "FAILED" in summary and lines[0][1]
          and len(err_lines) >= 1,
          f"ret={ret} summary={summary!r} errs={err_lines}")

    # 4. seeded cfg error (after the GLA repair — re-stage, then seed only)
    os.remove(gla)
    shutil.copy2(os.path.join(skel_src, f"{skeleton}.gla"), gla)
    cfg = os.path.join(dst_root, skeleton, "animation.cfg")
    with open(cfg, "a") as f:
        f.write("\nBOTH_FAKE_XYZ 999999 10 0 20\n")
    ret, _msg = run_check(skeleton)
    lines = results()
    summary = lines[0][0] if lines else ""
    err_lines = [t for t, e in lines if e]
    check(4, "seeded cfg error -> FAILED naming it",
          "FINISHED" in ret and "FAILED" in summary and lines[0][1]
          and any("BOTH_FAKE_XYZ" in t for t in err_lines),
          f"ret={ret} summary={summary!r} errs={err_lines}")

    # 5. missing char -> CANCELLED
    ret, msg = run_check("no_such_char")
    check(5, "missing char -> CANCELLED naming it",
          "CANCELLED" in ret and "no_such_char" in msg,
          f"ret={ret} msg={msg!r}")

    # 6. no basepath -> CANCELLED
    saved = p.cfg_basepath
    p.cfg_basepath = ""
    ret, msg = run_check(skeleton)
    p.cfg_basepath = saved
    check(6, "no basepath -> CANCELLED",
          "CANCELLED" in ret and "Base Path" in msg,
          f"ret={ret} msg={msg!r}")

    # 7. the given base is byte-identical
    after = _snapshot(base)
    diff = [k for k in before if before[k] != after.get(k)]
    check(7, "given base untouched", diff == [] and set(before) == set(after),
          f"changed={diff} only_before={set(before) - set(after)} "
          f"only_after={set(after) - set(before)}")

    shutil.rmtree(work_root, ignore_errors=True)

    if failures:
        print(f"B3 CHECK FAILED: {len(failures)} check(s): {failures}")
        raise SystemExit(1)
    print("B3 CHECK PASSED (7/7)")


if __name__ == "__main__":
    main()
