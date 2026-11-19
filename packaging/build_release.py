#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the Sheng-facing JKA animation suite distribution zip (workstream B4).

Assembles ONE folder Sheng can drop into his Windows Blender:

    jka-anim-suite-<version>/
      README-install.md        <- Windows Blender install instructions
      addons/
        jka_anim_tools/        <- our addon core (MIT)
        jediacademy/           <- mrwonko/cagelight GPL dep (unzipped from fixture)
      lib/
        animkit/               <- the cfg/GLA format library (MIT, pure stdlib)

Usage:
    python3 packaging/build_release.py [--version 0.1.0]
                                       [--animkit-src ~/work/jka-animkit]
                                       [--out dist]

The 'animkit dir' the addon searches must be the folder that CONTAINS the
'animkit' package — here that is <install>/lib. See the generated README.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def git(*args):
    try:
        return subprocess.check_output(
            ["git", "-C", REPO, *args], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def copy_pkg(src, dst, skip=("__pycache__", ".pyc")):
    for root, dirs, files in os.walk(src):
        dirs[:] = [d for d in dirs if d not in skip]
        rel = os.path.relpath(root, src)
        outd = dst if rel == "." else os.path.join(dst, rel)
        os.makedirs(outd, exist_ok=True)
        for f in files:
            if f.endswith(skip):
                continue
            shutil.copy2(os.path.join(root, f), os.path.join(outd, f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="0.1.0")
    ap.add_argument("--animkit-src", default=os.path.expanduser("~/work/jka-animkit"))
    ap.add_argument("--out", default=os.path.join(REPO, "dist"))
    a = ap.parse_args()

    animkit_src = os.path.abspath(a.animkit_src)
    ak_pkg = os.path.join(animkit_src, "animkit")
    if not os.path.isdir(ak_pkg):
        sys.exit(f"animkit package not found at {ak_pkg} (use --animkit-src)")

    ak_commit = ""
    try:
        ak_commit = subprocess.check_output(
            ["git", "-C", animkit_src, "rev-parse", "--short", "HEAD"],
            text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        pass

    base = os.path.join(a.out, f"jka-anim-suite-{a.version}")
    if os.path.isdir(base):
        shutil.rmtree(base)
    addons = os.path.join(base, "addons")
    lib = os.path.join(base, "lib")
    os.makedirs(addons)
    os.makedirs(lib)

    commit = git("rev-parse", "--short", "HEAD")
    print(f"jka-animator @ {commit}  jka-animkit @ {ak_commit}  version {a.version}")

    # 1. the addon core
    copy_pkg(os.path.join(REPO, "jka_anim_tools"), os.path.join(addons, "jka_anim_tools"))

    # 2. the GPL jediacademy dep (unzip, skip __MACOSX)
    jz = os.path.join(REPO, "fixtures", "blender-addon", "jediacademy.zip")
    if not os.path.isfile(jz):
        sys.exit(f"jediacademy fixture missing: {jz}")
    with zipfile.ZipFile(jz) as z:
        for info in z.infolist():
            name = info.filename
            if name.startswith("__MACOSX") or name.endswith("/"):
                continue
            parts = name.split("/")
            if parts[0] != "jediacademy":
                continue
            target = os.path.join(addons, name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)

    # 3. the animkit library
    copy_pkg(ak_pkg, os.path.join(lib, "animkit"))

    # 4. install README
    readme = f"""# JKA Animation Suite — install (Windows Blender)

Version **{a.version}** · built from `jka-animator @ {commit}` + `jka-animkit @ {ak_commit}`.
The Blender-addon side of the JKA (OpenJK / JKA: Enhanced) animation pipeline:
import reference GLA → author a segment (incl. `.xsi` clips) → export GLA →
validate against your character dir.

## What's in this folder

- `addons/jka_anim_tools/` — the addon (N-panel, operators). **MIT.**
- `addons/jediacademy/` — the mrwonko/cagelight "Jedi Academy Import/Export
  Tools" addon, a **hard dependency** (this addon calls its GLA
  import/export operators — GPL, kept as a separate plugin, not vendored).
- `lib/animkit/` — the JKA cfg/GLA format library the check/cfg layer imports
  at runtime. **MIT, pure Python stdlib** (no numpy/scipy/pillow needed).

## Install (Windows Blender 5.x)

1. **Copy the two addons** into your Blender addons folder:
   - Blender default: `<Blender>/scripts/addons/`
   - or your user addons dir (Blender → Edit → Preferences → Add-ons →
     "Install..." reveals it).
   - Copy BOTH `addons/jka_anim_tools` and `addons/jediacademy`.

2. **Point the addon at animkit.** Set the "animkit dir" field (in the
   addon's Quick Setup prefs, N-panel → JKA tab) to:

       <this folder>\\lib

   ...the folder that *contains* `animkit\\`. (Alternatively set the
   environment variable `JKA_ANIMKIT_DIR` to that same `lib` folder.)

3. **Enable both add-ons** in Blender → Edit → Preferences → Add-ons:
   - `Jedi Academy Import/Export Tools` (`jediacademy`)
   - `JKA Animation Tools` (`jka_anim_tools`)
   The JKA addon requires jediacademy to be enabled (it loads it on demand).

4. **Open your mod's base tree** (a folder containing
   `models/players/_humanoid/_humanoid.gla` + `animation.cfg`) and use the
   N-panel (press **N** in the 3D view → **JKA** tab, the last tab).

## Quick start (the workflow)

- **Load reference**: pick `_humanoid/_humanoid.gla` + a frame range.
- **Author**: key a segment (or import an `.xsi` clip), use the finger
  presets (FIST / OPEN / GRASP) for hand poses.
- **Export GLA**: writes the re-authored segment into the base tree.
- **Check**: validates the character dir (GLA + cfg) and prints errors /
  warnings; a clean check is the gate before in-engine play.

## Notes

- Blender 5.3 is the tested target; the panel handles the 4.x→5.3 enum/icon
  API differences.
- This is animation-side only: the finished GLM is input; modeling/weighting
  are out of scope.

## Licensing

- `jka_anim_tools/` — MIT (see the repo LICENSE).
- `lib/animkit/` — MIT.
- `addons/jediacademy/` — GPL (mrwonko/cagelight). It is a separate plugin
  this addon invokes; per the GPL/MIT boundary we never copy its code.
"""
    with open(os.path.join(base, "README-install.md"), "w") as f:
        f.write(readme)

    # 5. zip it
    os.makedirs(a.out, exist_ok=True)
    zpath = os.path.join(a.out, f"jka-anim-suite-{a.version}.zip")
    if os.path.isfile(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, a.out))

    size = os.path.getsize(zpath)
    print(f"\nOK: {zpath}  ({size/1024:.0f} KB)")
    # sanity: verify the zip contains the 3 components + readme
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        checks = {
            "add-on core": any(n.endswith("jka_anim_tools/__init__.py") for n in names),
            "jediacademy dep": any(n.endswith("jediacademy/__init__.py") for n in names),
            "animkit lib": any(n.endswith("lib/animkit/__init__.py") for n in names),
            "readme": any(n.endswith("README-install.md") for n in names),
        }
        for k, ok in checks.items():
            print(f"  [{'ok' if ok else 'MISSING'}] {k}")
        if not all(checks.values()):
            sys.exit("distribution incomplete")


if __name__ == "__main__":
    main()
