bl_info = {
    "name": "ESEC Archiologic Importer",
    "author": "stefan.knaak@e-shelter.io",
    "version": (1, 2),
    "blender": (2, 93, 0),
    "location": "View3D > Sidebar > ESEC Tab",
    "description": "Addon to import your Archiologic Data directly into Blender.",
    "warning": "",
    "wiki_url": "",
    "category": "3D View",
}

import bpy
import requests
import os
import json
import math
from statistics import mean

global spaces_json_data

def get_floor_data(floor_id):

    preferences = bpy.context.preferences.addons[__package__].preferences
    token = preferences.archiologic_token
    
    global spaces_json_data
    headers = {
        "Authorization": f"AL-Secret-Token {token}"
    }

    response = requests.get(f"https://api.archilogic.com/v2/floor/{floor_id}", headers=headers)

    if response.status_code == 200:
        data = response.json()
        space_ids = data["resourceRelations"]["spaces"]
        spaces_data = []

        for space_id in space_ids:
            params = {
                "includeCustomFields": "true",
                "includeCustomAttributes": "true"
            }

            response = requests.get(f"https://api.archilogic.com/v2/space/{space_id}/geo-json", headers=headers, params=params)

            if response.status_code == 200:
                space_data = response.json()
                spaces_data.append(space_data)
            else:
                print(f"Failed to get data for space {space_id}")
                return None

        spaces_json = json.dumps(spaces_data, indent=4)
        print(spaces_json)
        spaces_json_data = spaces_json  # Save the data to the global variable
        return spaces_json

    else:
        print("Failed to get floor data")
        return None
    
def create_3d():
    # parse json data
    spaces = json.loads(spaces_json_data)

    # Create or get the collections
    space_collection_name = "spaces"
    text_collection_name = "space_names"


    if space_collection_name in bpy.data.collections:
        space_collection = bpy.data.collections[space_collection_name]
    else:
        space_collection = bpy.data.collections.new(space_collection_name)
        bpy.context.scene.collection.children.link(space_collection)

    if text_collection_name in bpy.data.collections:
        text_collection = bpy.data.collections[text_collection_name]
    else:
        text_collection = bpy.data.collections.new(text_collection_name)
        bpy.context.scene.collection.children.link(text_collection)


    # iterate over the spaces in the JSON
    for space in spaces:
        # get the name from the properties if it exists, otherwise get the id
        name = space["properties"].get("name", space["id"])

        # get the coordinates from the geometry
        coordinates = space["geometry"]["coordinates"][0]

        # convert to tuples and swap (lat, lon) to (x, y)
        # convert lat/lon to meters using a local tangent plane approximation
        coordinates = [(lon * 111.32 * 1000 * math.cos(math.radians(lat)), lat * 111.32 * 1000, 0) for lon, lat in coordinates]

        # create a new mesh and a new object
        mesh = bpy.data.meshes.new(name=name)
        obj = bpy.data.objects.new(name, mesh)

        # link the object to the space collection
        space_collection.objects.link(obj)

        # create the mesh from python data
        mesh.from_pydata(coordinates, [], [list(range(len(coordinates)))])

        # update the mesh with the new data
        mesh.update()

        # calculate left centered position of the text
        x_min = min(coordinates, key=lambda x: x[0])[0]
        y_center = mean(coord[1] for coord in coordinates)
        x_margin = x_min + (0.10 * (max(coordinates, key=lambda x: x[0])[0] - x_min))

        # create a new text object
        font_curve = bpy.data.curves.new(type="FONT", name=f"{name}_text")
        text_obj = bpy.data.objects.new(f"{name}_text", font_curve)
        text_obj.data.body = name
        text_obj.location = (x_margin, y_center, 0)
        text_obj.scale = (0.5, 0.5, 0.5)  # make the text half the size

        # link the text object to the text collection
        text_collection.objects.link(text_obj)

class ESEC_ARCHIOLOGIC_PT_main_panel(bpy.types.Panel):
    bl_label = "ESEC Archiologic import v"+ str(bl_info['version'])
    bl_idname = "ESEC_ARCHIOLOGIC_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ESEC'

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "floorID")
        layout.operator("esec.get_floor_data")
        layout.separator()
        layout.prop(context.scene, "create_rooms")
        layout.prop(context.scene, "create_walls")
        layout.prop(context.scene, "create_windows_doors")
        layout.operator("esec.create")
        layout.separator()        
        layout.operator("esec.delete_all")

class ESEC_ARCHIOLOGIC_OT_get_floor_data(bpy.types.Operator):
    bl_label = "Get Floor Data"
    bl_idname = "esec.get_floor_data"

    def execute(self, context):
        print("Get Floor Data")
        
        # Get floorID from the input fields
        floor_id = context.scene.floorID

        # Call the separate function to get floor data
        get_floor_data(floor_id)  
              
        return {'FINISHED'}

class ESEC_ARCHIOLOGIC_OT_delete_all(bpy.types.Operator):
    bl_label = "Delete All"
    bl_idname = "esec.delete_all"

    def execute(self, context):
        print("Delete All")        
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False, confirm=False)
        
        return {'FINISHED'}

class ESEC_ARCHIOLOGIC_OT_create(bpy.types.Operator):
    bl_label = "Create"
    bl_idname = "esec.create"

    def execute(self, context):
        print("Create")        
        create_3d()
        return {'FINISHED'}


def register():
    bpy.utils.register_class(ESEC_ARCHIOLOGIC_PT_main_panel)
    bpy.utils.register_class(ESEC_ARCHIOLOGIC_OT_get_floor_data)
    bpy.utils.register_class(ESEC_ARCHIOLOGIC_OT_delete_all)
    bpy.utils.register_class(ESEC_ARCHIOLOGIC_OT_create)        
    bpy.types.Scene.floorID = bpy.props.StringProperty(name="Floor ID", default="", description="Floor from Archiologic")
    bpy.types.Scene.create_rooms = bpy.props.BoolProperty(name="Create Rooms")
    bpy.types.Scene.create_walls = bpy.props.BoolProperty(name="Create Walls")
    bpy.types.Scene.create_windows_doors = bpy.props.BoolProperty(name="Create Windows/Doors")


def unregister():
    bpy.utils.unregister_class(ESEC_ARCHIOLOGIC_PT_main_panel)
    bpy.utils.unregister_class(ESEC_ARCHIOLOGIC_OT_get_floor_data)
    bpy.utils.unregister_class(ESEC_ARCHIOLOGIC_OT_delete_all)
    bpy.utils.unregister_class(ESEC_ARCHIOLOGIC_OT_create)
    del bpy.types.Scene.floorID
    del bpy.types.Scene.create_rooms
    del bpy.types.Scene.create_walls
    del bpy.types.Scene.create_windows_doors
    #bpy.utils.unregister_class(ESEC_ARCHIOLOGIC_OT_set_defaults)

if __name__ == "__main__":
    register()
