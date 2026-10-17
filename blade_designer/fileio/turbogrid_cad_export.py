"""TurboGrid boundary-CAD instructions; STEP is an intermediate, not Parasolid."""
TURBOGRID_CAD_INSTRUCTIONS="""# TurboGrid CAD import (NOT_TESTED)

`turbogrid_cad.step` is a validated fluid passage CAD boundary model. It is not the mechanical disk solid.
The STEP uses millimetres and rotation axis Z. Root fillet faces come from the same native BREP generation as the mechanical geometry.

The documented CAD-source workflow in TurboGrid 2025 R2 uses Parasolid and other release-specific supported inputs. A direct STEP reader is not assumed.
1. Confirm supported CAD formats and licenses in your target release.
2. Open the STEP in a CAD converter such as licensed SpaceClaim and export genuine Parasolid if required.
3. Never rename a STEP extension to `.x_t` or `.x_b`.
4. Compare units, volume/bounds, HUB/SHROUD/BLADE_PS/BLADE_SS/BLADE_LE/BLADE_TE/HUB_FILLET/INLET/OUTLET and periodic faces with cad_validation.json.
5. Start TurboGrid stand-alone, select CAD input and assign the required geometry entities.
6. Check Complex Blade End / fillet recognition; generate and inspect the mesh.

STEP Named Selections are not guaranteed. Semantic roles are listed in the validation report and must be assigned/confirmed in ANSYS.
Parasolid conversion, TurboGrid import, mesh generation and mesh quality are NOT_TESTED/UNAVAILABLE in this Python environment.

Official documentation:
https://ansyshelp.ansys.com/public/Views/Secured/corp/v252/en/tg_user/i4566510856516542556.html
"""

def blade_blend_instructions(radius_mm=8.,enabled=True):
    state='enabled' if enabled else 'disabled'
    return f"""# Profile points and ANSYS Blade Blend

Profile points are the original unfilleted design. They do not contain a Python-generated root fillet.
For TurboGrid CAD From Profile Points, confirm stand-alone execution and a BladeModeler/BladeBuilder license for the chosen CAD tool.
Requested Hub Blend: {state}. Saved Rolling Ball Radius: {radius_mm:g} mm. Shroud Blend: disabled.
When Hub Blend is enabled, use that radius with True Blend, then Apply And Generate CAD. A saved radius is not applied when Hub Blend is disabled.
ANSYS Blade Blend is a separate operation; equality with the Python BREP fillet is not guaranteed.
No ANSYS operation has been executed by this app. Import/mesh/quality: NOT_TESTED.
https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/tg_user/i132455554122894.html
"""

BLADE_BLEND_INSTRUCTIONS=blade_blend_instructions()
