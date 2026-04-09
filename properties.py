
import bpy
from bpy.types import Scene


class ESECAddonProperties(bpy.types.PropertyGroup):
    show_settings: bpy.props.BoolProperty(
        name="Settings",
        description="Show or hide the settings",
        default=False,
    )

#
# Add additional functions or classes here
#

# This is where you assign any variables you need in your script. Note that they
# won't always be assigned to the Scene object but it's a good place to start.
def register():
    #Scene.my_property = BoolProperty(default=True)
    bpy.utils.register_class(ESECAddonProperties)
    bpy.types.Scene.esec_addon_props = bpy.props.PointerProperty(type=ESECAddonProperties)

def unregister():
    bpy.utils.unregister_class(ESECAddonProperties)
    del bpy.types.Scene.esec_addon_props
