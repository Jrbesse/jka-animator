"""Rig analysis dump v2 — API-safe across Blender 4.5-5.3.
Run: blender --background RIG.blend --python dump_rig2.py OUT.txt
"""
import bpy, sys, os

out = []
def p(*a):
    out.append(" ".join(str(x) for x in a))

def props_of(id_like):
    try:
        return {k: id_like[k] for k in id_like.keys() if k != "rna_type"}
    except Exception:
        return {}

p("BLENDER_VERSION", bpy.app.version_string)
p("FILE", bpy.data.filepath)
sc = bpy.context.scene
p("SCENE", sc.name, "fps", sc.render.fps, "frames", sc.frame_start, sc.frame_end, "current", sc.frame_current)

p("\n=== COLLECTIONS ===")
def walk_coll(c, depth=0):
    p("  " * depth + "COLL", c.name)
    for o in c.objects:
        par = o.parent.name if o.parent else "-"
        p("  " * (depth + 1) + f"OBJ {o.name} type={o.type} parent={par} colls={[x.name for x in o.users_collection]}")
    for ch in c.children:
        walk_coll(ch, depth + 1)
for c in bpy.data.collections:
    walk_coll(c)

p("\n=== ARMATURES ===")
for ob in bpy.data.objects:
    if ob.type != "ARMATURE":
        continue
    arm = ob.data
    p(f"\nARMATURE '{ob.name}' (obj colls={[x.name for x in ob.users_collection]}) bones={len(arm.bones)} bone_collections={len(arm.collections)}")
    p("  armature props:", props_of(arm))
    for bc in arm.collections:
        names = [b.name for b in bc.bones]
        p(f"  BONE_COLL '{bc.name}' ({len(names)}): {', '.join(names)}")
    p("  --- bones ---")
    for b in arm.bones:
        extras = []
        if b.parent: extras.append(f"parent={b.parent.name}")
        if b.use_connect: extras.append("connect")
        bp = props_of(b)
        if bp: extras.append(f"props={bp}")
        p(f"  BONE {b.name} head=[{b.head[0]:.2f},{b.head[1]:.2f},{b.head[2]:.2f}] tail=[{b.tail[0]:.2f},{b.tail[1]:.2f},{b.tail[2]:.2f}] len={b.length:.3f} {' '.join(extras)}")
    p("  --- pose bones (constraints) ---")
    for pb in ob.pose.bones:
        cons = []
        for c in pb.constraints:
            extra = ""
            if c.type == "IK":
                extra = f"chain={c.chain_count} influence={c.influence}"
            elif hasattr(c, "influence"):
                extra = f"influence={c.influence}"
            tgt = ""
            t = getattr(c, "target", None)
            if t is not None:
                tgt = f" target={t.name}"
                st = getattr(c, "subtarget", "") or ""
                if st: tgt += f"/{st}"
            cons.append(f"{c.name}:{c.type}({extra}{tgt})")
        pp = props_of(pb)
        line = f"  PB {pb.bone}"
        if cons: line += " | " + " ; ".join(cons)
        if pp: line += f" | props={pp}"
        p(line)

p("\n=== DRIVERS (object level, incl. pose.bones paths) ===")
for idata in list(bpy.data.objects) + list(bpy.data.armatures):
    for drv in getattr(idata, "drivers", []):
        vars_ = ", ".join(
            f"{v.name}<-{(v.target.name if v.target else '?')}.{v.target_rna_property}[{v.array_index}]"
            for v in drv.variables)
        p(f"  DRV[{idata.name}] {drv.data_path} = '{drv.expression}' ({vars_})")

p("\n=== ACTIONS ===")
for act in bpy.data.actions:
    p(f"ACT '{act.name}' fcurves={len(act.fcurves)}")
    seen = {}
    for fc in act.fcurves:
        seen.setdefault(fc.data_path, []).append(fc)
    for key, fcs in sorted(seen.items()):
        frames = [kf.co[0] for fc in fcs for kf in fc.keyframe_points]
        if frames:
            p(f"  PATH {key} ({len(fcs)} ch) frames {min(frames):.0f}..{max(frames):.0f} keys={sum(len(fc.keyframe_points) for fc in fcs)}")

p("\n=== IMAGES ===")
for img in bpy.data.images:
    p(f"IMG '{img.name}' {img.size[0]}x{img.size[1]} src={img.source} filepath={img.filepath_raw} packed={bool(img.packed_file)}")

p("\n=== MATERIALS ===")
for mat in bpy.data.materials:
    nodes = len(mat.node_tree.nodes) if mat.node_tree else 0
    p(f"MAT '{mat.name}' nodes={nodes}")

p("\n=== TEXT DATABLOCKS ===")
for t in bpy.data.texts:
    s = t.as_string()
    p(f"TEXT '{t.name}' chars={len(s)} first='{s[:100]}'")

p("\n=== MESHES / OTHER ===")
for ob in bpy.data.objects:
    if ob.type == "MESH":
        p(f"MESH '{ob.name}' verts={len(ob.data.vertices)} mods={[m.type for m in ob.modifiers]} mats={[m.name for m in ob.data.materials]}")
    elif ob.type == "EMPTY":
        p(f"EMPTY '{ob.name}' display={ob.empty_display_type}")

blob = "\n".join(out)
target = sys.argv[-1] if len(sys.argv) > 1 and sys.argv[-1].endswith(".txt") else "rig_dump2.txt"
with open(target, "w") as f:
    f.write(blob)
print(f"DUMP-WROTE {target} chars={len(blob)}")
