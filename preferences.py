import bpy

class ESECAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    archiologic_token: bpy.props.StringProperty(
        name="Archiologic Token",
        description="Enter your Archiologic Token here",
        default="",
        subtype='PASSWORD',
    )

    include_archived: bpy.props.BoolProperty(
        name="Include archived floors",
        default=False,
    )

    repair_missing_walls: bpy.props.BoolProperty(
        name="Repair missing walls on IFC import",
        description="Repair missing walls on IFC import. Needs Bonsai > 0.8.5-alpha2604081058",
        default=False,
    )

    debug_mode: bpy.props.BoolProperty(
        name="Debug Mode",
        description="Print detailed information to the console",
        default=False,
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "archiologic_token")
        layout.prop(self, "include_archived")
        layout.label(text="Token must have scopes to list and export floors.", icon='INFO')
        layout.separator()
        layout.prop(self, "repair_missing_walls")
        layout.prop(self, "debug_mode")


def register():
    bpy.utils.register_class(ESECAddonPreferences)


def unregister():
    bpy.utils.unregister_class(ESECAddonPreferences)