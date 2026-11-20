#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the JKA animation tools distribution zip (workstream B4).

Ships ONE standard Blender add-on zip, installable with
Edit > Preferences > Add-ons > Install from Disk (one click):

    jka-anim-tools-<version>.zip
      jka_anim_tools/            <- the add-on package, at the zip root (MIT)
        __init__.py ...          <- bl_info add-on; N-panel + operators
        lib/
          animkit/               <- the cfg/GLA format library (MIT, bundled
                                    so no 'AnimKit Dir' setup is needed)
      README-install.md          <- install sheet (unzipped alongside)

The GPL jediacademy (mrwonko/cagelight) add-on is NOT shipped in this zip
(2026-11-20 review item #1): it is a separately installed dependency. The
README links the user to the upstream repo (mrwonko/Blender-Jedi-Academy-
Tools, tag v2.1.0) and this add-on invokes its operators after the user
installs it — the 'Add-on dir' field remains as a fallback for loading it
from a local folder.

Usage:
    python3 packaging/build_release.py [--version 0.2.2]
                                       [--animkit-src ~/work/jka-animkit]
                                       [--out dist]

--animkit-src: the jka-animkit checkout; the pinned ref is recorded in
packaging/animkit.lock and CI checks it out shallow at that SHA.
"""
import argparse
import os
import shutil
import subprocess
import sys
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UPSTREAM_JEDACADEMY = ("https://github.com/mrwonko/Blender-Jedi-Academy-Tools"
                       " (tag v2.1.0)")


def git(*args):
    try:
        return subprocess.check_output(
            ["git", "-C", REPO, *args], text=True,
            stderr=subprocess.DEVNULL).strip()
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
    ap.add_argument("--version", default="0.2.2")
    ap.add_argument("--animkit-src",
                    default=os.path.expanduser("~/work/jka-animkit"))
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

    base = os.path.join(a.out, f"jka-anim-tools-{a.version}")
    if os.path.isdir(base):
        shutil.rmtree(base)
    addon = os.path.join(base, "jka_anim_tools")
    os.makedirs(os.path.join(addon, "lib"))

    commit = git("rev-parse", "--short", "HEAD")
    print(f"jka-animator @ {commit}  jka-animkit @ {ak_commit}  "
          f"version {a.version}")

    # 1. the add-on core (package at the zip root — the standard install
    #    format: Blender installs every bl_info package it finds in the
    #    unzipped folder)
    copy_pkg(os.path.join(REPO, "jka_anim_tools"), addon)

    # 2. the animkit library, bundled INSIDE the add-on (jka_anim_tools/lib)
    #    so the 'AnimKit Dir' field is never needed — animkit_bridge
    #    resolves <add-on>/lib before the env var / dev clone.
    copy_pkg(ak_pkg, os.path.join(addon, "lib", "animkit"))

    # 3. install README (unzipped alongside the package; Blender's
    #    installer ignores non-add-on files at the zip root)
    readme = f"""# JKA Animation Tools — install (Blender 4.1+)

Version **{a.version}** · built from `jka-animator @ {commit}` +
`jka-animkit @ {ak_commit}`.

The Blender-addon side of the JKA (OpenJK / JKA: Enhanced) animation
pipeline: import reference GLA → author a segment → export GLA → validate
against your character dir.

## 1. Install THIS add-on (one click)

Blender → Edit → Preferences → Add-ons → **Install from Disk…** → pick
`jka-anim-tools-{a.version}.zip` (this zip). Then enable **JKA Animation
Tools** in the Add-ons list.

No paths to configure: the cfg/GLA format library (`animkit`) is bundled
inside the add-on (`jka_anim_tools/lib/`).

## 2. Install the separate dependency (GLA import/export)

This add-on calls the **Jedi Academy Import/Export Tools** add-on
(`jediacademy`, by mrwonko) for the actual .gla/.glm import/export. It is
**not** bundled with this zip — install it once, separately, from its own
repository:

    {UPSTREAM_JEDACADEMY}

Download the release/zip from that repo, then in Blender:
Edit → Preferences → Add-ons → **Install from Disk…** → pick that zip →
enable **Jedi Academy Import/Export Tools** (`jediacademy`).

If you keep the unzipped add-on folder somewhere and it is not installed
in Preferences, you can point this add-on's **Add-on Dir** field (bottom
of the JKA panel) at the folder that CONTAINS the `jediacademy` package —
it will be loaded on demand.

## 3. Use it

Open your mod's base tree (the folder that contains
`models/players/_humanoid/_humanoid.gla` + `animation.cfg`), press **N**
in the 3D view → **JKA** tab, and set the **one Base Path** field at the
top — everything (reference GLA, output, segments, check) derives from it.

- **Load reference**: `_humanoid/_humanoid.gla` + a frame range (Range mode
  is fast; do not import the whole file).
- **Author**: key a segment, use the finger presets (Grasp / Fist / Open)
  for hand poses.
- **Export GLA**: writes the authored segment into the base tree.
- **Check**: validates the character dir (GLA + cfgs + skin); a clean
  check is the gate before in-engine play.

Your panel settings are saved automatically and restored the next time
Blender starts.

## Licensing

- `jka_anim_tools/` — MIT (see the repo LICENSE).
- `jka_anim_tools/lib/animkit/` — MIT.
- `jediacademy` (separate install) — its own license, per its upstream
  repository; intentionally NOT redistributed here.
"""
    with open(os.path.join(base, "README-install.md"), "w") as f:
        f.write(readme)

    # 4. zip it (package at the zip root)
    os.makedirs(a.out, exist_ok=True)
    zpath = os.path.join(a.out, f"jka-anim-tools-{a.version}.zip")
    if os.path.isfile(zpath):
        os.remove(zpath)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        # zip relative to the STAGING dir so the add-on package sits at
        # the zip root (the standard install-from-disk layout)
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for f in files:
                if f.endswith(".pyc"):
                    continue
                full = os.path.join(root, f)
                z.write(full, os.path.relpath(full, base))

    size = os.path.getsize(zpath)
    print(f"\nOK: {zpath}  ({size/1024:.0f} KB)")
    # sanity: the zip must contain the add-on + bundled animkit + readme,
    # and must NOT contain any jediacademy file (the GPL dep ships
    # separately — review item #1)
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        checks = {
            "add-on core": "jka_anim_tools/__init__.py" in names,
            "bundled animkit": "jka_anim_tools/lib/animkit/__init__.py"
                               in names,
            "readme": "jka_anim_tools/../README-install.md" in names
                      or any(n == "README-install.md" for n in names),
        }
        for k, ok in checks.items():
            print(f"  [{'ok' if ok else 'MISSING'}] {k}")
        if not all(checks.values()):
            sys.exit("distribution incomplete")
        leaked = [n for n in names if "jediacademy" in n.lower()
                  or "wonko" in n.lower()]
        if leaked:
            sys.exit(f"GPL dependency leaked into the distribution: "
                     f"{leaked[:5]}")
        print("  [ok] no jediacademy/GPL content in the zip")


if __name__ == "__main__":
    main()
