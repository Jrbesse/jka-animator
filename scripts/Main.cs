using Godot;

namespace JkaAnimator;

/// <summary>
/// G0 skeleton: proves the project boots (window + headless) and the C#
/// toolchain compiles against Godot 4.7. G1 will replace the placeholder
/// box with the GLM/GLA loaders + skinned viewport.
/// </summary>
public partial class Main : Node3D
{
    public override void _Ready()
    {
        GD.Print("[jka-animator] G0 skeleton running — ", Engine.GetVersionInfo());
    }
}
