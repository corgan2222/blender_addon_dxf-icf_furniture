
import bpy
from bpy.types import Scene


class ESECAddonProperties(bpy.types.PropertyGroup):
    table_height: bpy.props.FloatProperty(
        name="Table Height",
        description="Height for tables",
        default=0.8,
        min=0
    )

    chair_height: bpy.props.FloatProperty(
        name="Chair Height",
        description="Height for chairs",
        default=0.45,
        min=0
    )
    
    stool_scale: bpy.props.FloatProperty(
        name="Stool Scale",
        description="Adjust the X and Y scale of the stools",
        default=1.5,
        min=0.1,
        max=10.0
    )    

    storage_height: bpy.props.FloatProperty(
        name="Storage Scale Z",
        description="Height for storage",
        default=1.6,
        min=0.1,
        max=2
    )    

    sideboard_height: bpy.props.FloatProperty(
        name="Sideboard Scale Z",
        description="Height for Sideboard",
        default=0.2,
        min=0.1,
        max=2
    )    

    table_margin: bpy.props.FloatProperty(
        name="Margin between tables",
        description="Margin between tables",
        default=0.02,
        min=0,
        max=0.5
    )    

    sideboard_height2: bpy.props.FloatProperty(
        name="Sideboard Scale Z",
        description="Height for Sideboard",
        default=0.2,
        min=0.1,
        max=2
    )  

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
    bpy.types.Scene.use_high_poly_models = bpy.props.BoolProperty(name="Use high poly models", default=False)         

def unregister():
    #del Scene.my_property
    bpy.utils.unregister_class(ESECAddonProperties)
    del bpy.types.Scene.esec_addon_props
    del bpy.types.Scene.use_high_poly_models
