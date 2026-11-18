"""Probe: IK pole targets, armature modifier targets, shape keys, custom props."""
import bpy

out = []
def p(*a): out.append(" ".join(str(x) for x in a))

for ob in bpy.data.objects:
    if ob.type != "ARMATURE":
        continue
    for pb in ob.pose.bones:
        for c in pb.constraints:
            if c.type == "IK":
                pole = c.pole_target
                p(f"IK[{ob.name}/{pb.bone}] target={c.target.name if c.target else None}"
                  f" pole={pole.name if pole else None}/{getattr(c,'pole_subtarget','') or ''}"
                  f" pole_angle={c.pole_angle:.3f} chain={c.chain_count}")
    if ob.name == "IK_Rig":
        arm = ob.data
        for k in arm.keys():
            if k == "rna_type":
                continue
            v = arm[k]
            s = repr(v)
            if len(s) > 300:
                s = s[:300] + "..."
            p(f"ARMPROP {ob.name} {k} = {s}")

p("\n--- armature modifiers ---")
for ob in bpy.data.objects:
    if ob.type == "MESH":
        for m in ob.modifiers:
            if m.type == "ARMATURE":
                p(f"ARMMOD mesh='{ob.name}' -> {m.object.name if m.object else None}")
    if ob.type == "MESH" and ob.data.shape_keys and ob.data.shape_keys.key_blocks:
        ks = [kb.name for kb in ob.data.shape_keys.key_blocks]
        p(f"SHAPEKEYS '{ob.name}': {ks}")

p("\n--- scene ---")
sc = bpy.context.scene
p("fps", sc.render.fps, "range", sc.frame_start, sc.frame_end,
  "interp", sc.render.fps_base, "units", sc.unit_settings.system)

print("\n".join(out))
