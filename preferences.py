import bpy

class ESECAddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    archiologic_token: bpy.props.StringProperty(
        name="Archiologic Token",
        description="Enter your Archiologic Token here",
        default="",
        subtype='PASSWORD',   # This will mask the input, use 'TEXT' if you want it visible
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "archiologic_token")


def register():
    bpy.utils.register_class(ESECAddonPreferences)


def unregister():
    bpy.utils.unregister_class(ESECAddonPreferences)