bl_info = {
    "name": "ESEC DXF-IFC 3D Floorplan Tool",
    "author": "stefan.knaak@e-shelter.io",
    "version": (1, 4),
    "blender": (3, 5, 0),
    "location": "View3D > Sidebar > ESEC Tab",
    "description": "Create furniture like tables and chairs from a DXF plan, exported from Archiologic.",
    "warning": "",
    "doc_url": "https://github.com/corgan2222/blender_addon_dxf-icf_furniture",
    "category": "3D View",
}

import bpy
import os
import math
from mathutils import Vector

def detect_shape(ob):

    #Objectname: TaskChair.159 - Shape: circle - Points: 72
    #Objectname: ConferenceChair.001 - Shape: circle - Points: 30
    #Objectname: OutdoorChair.002 - Shape: circle - Points: 20

    # Get the curve data from the object
    curve = ob.data
    
    # Count the number of points in the first spline of the curve
    num_points = len(curve.splines[0].bezier_points) if curve.splines[0].type == 'BEZIER' else len(curve.splines[0].points)
    
    # Basic shape detection based on point count
    if num_points == 4:
        return 'square', num_points
    elif num_points > 4:
        # Further refine the detection to check if it's a circle
        # Calculate the distance from each point to the object's center
        # If the distances are approximately equal, it's a circle
        center = ob.location
        if curve.splines[0].type == 'BEZIER':
            distances = [((p.co.x - center.x)**2 + (p.co.y - center.y)**2)**0.5 for p in curve.splines[0].bezier_points]
        else:
            distances = [((p.co.x - center.x)**2 + (p.co.y - center.y)**2)**0.5 for p in curve.splines[0].points]
        average_distance = sum(distances) / len(distances)
        if all(math.isclose(d, average_distance, rel_tol=0.1) for d in distances):
            return 'circle', num_points
    return 'unknown', num_points

def move_objects_to_dxf():
    # Create the 'dxf' collection if it doesn't exist
    if 'dxf' not in bpy.data.collections:
        dxf_collection = bpy.data.collections.new('dxf')
        bpy.context.scene.collection.children.link(dxf_collection)
    else:
        dxf_collection = bpy.data.collections['dxf']

    root_collection = bpy.context.scene.collection

    # Move all objects that are not collections from the root level to the 'dxf' collection
    for obj in root_collection.objects:
        if obj.type != 'EMPTY':  # Assuming collections are Empty objects with children
            root_collection.objects.unlink(obj)
            dxf_collection.objects.link(obj)
            print(f"Moved '{obj.name}' to the 'dxf' collection.")


def delete_unwanted_objects(collection_name):
    collection = bpy.data.collections.get(collection_name)
    if not collection:
        print(f"Collection '{collection_name}' not found.")
        return

    allowed_keywords = ['Desk', 'Chair', 'chair', 'Sofa', 'Table', 'Storage', 'Sideboard', 'Bed', 'Stool', 'Printer']
    objects_to_delete = []

    # Find objects to delete
    for obj in collection.objects:
        if not any(keyword in obj.name for keyword in allowed_keywords):
            objects_to_delete.append(obj.name)

    # Delete objects
    for obj_name in objects_to_delete:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
            print(f"Deleted object: {obj_name}")

def rename_objects_dxf(collection_name):
    collection = bpy.data.collections.get(collection_name)
    if not collection:
        print(f"Collection '{collection_name}' not found.")
        return

    for obj in collection.objects:
        new_name = obj.name.split("|")[-1].split("_")[0]
        obj.name = new_name
        print(f"Renamed object to: {obj.name}")

def move_objects_to_ifc():
    # Create the 'ifc' collection if it doesn't exist
    if 'ifc' not in bpy.data.collections:
        ifc_collection = bpy.data.collections.new('ifc')
        bpy.context.scene.collection.children.link(ifc_collection)
    else:
        ifc_collection = bpy.data.collections['ifc']

    # Define the nested collections structure
    nested_collections = ["IfcProject/None", "IfcSite/None", "IfcBuilding/None", "IfcBuildingStorey/Storey_0"]

    current_collection = bpy.context.scene.collection
    for collection_name in nested_collections:
        if collection_name in current_collection.children:
            current_collection = current_collection.children[collection_name]
        else:
            print(f"Collection '{collection_name}' not found.")
            return

    # Move all objects from the nested collection to the 'ifc' collection
    for obj in current_collection.objects:
        current_collection.objects.unlink(obj)
        ifc_collection.objects.link(obj)
        print(f"Moved '{obj.name}' to the 'ifc' collection.")

def remove_collection(collection_name):
    collection = bpy.data.collections.get(collection_name)
    if not collection:
        print(f"Collection '{collection_name}' not found.")
        return

    bpy.data.collections.remove(collection)
    print(f"Removed collection: {collection_name}")


def remove_window_objects(collection_name):
    collection = bpy.data.collections.get(collection_name)
    if not collection:
        print(f"Collection '{collection_name}' not found.")
        return

    keywords = ['Window', 'window']
    objects_to_remove = []

    # Find objects to remove
    for obj in collection.objects:
        if any(keyword in obj.name for keyword in keywords):
            objects_to_remove.append(obj.name)

    # Remove objects
    for obj_name in objects_to_remove:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            bpy.data.objects.remove(obj, do_unlink=True)
            print(f"Removed object: {obj_name}")

def create_tabletop_square_from_object(obj):
    # Calculate the bounding box dimensions for the object
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    bbox_dimensions = Vector((max(corner[i] for corner in bbox_corners) - min(corner[i] for corner in bbox_corners) for i in range(3)))
    
    width, depth, _ = bbox_dimensions
    #height = 0.8
    height = bpy.context.scene.esec_addon_props.table_height
    bpy.ops.mesh.primitive_cube_add(size=1)
    table_top = bpy.context.active_object
    table_top.name = obj.name + "_TableTop"
    
    # Set the scale of the table_top based on the bounding box dimensions
    table_top.scale.x = width 
    table_top.scale.y = depth 
    table_top.scale.z = 0.025
    
    table_top.location = obj.location
    table_top.location.z = height - 0.025 / 2

    # Rotate the new object to match the source object
    # 1.5708 = 90 degrees
    # 0.1553 = 8.9 degrees
    # 4.7124 = 270 degrees
    # 3.142 = 180 degrees

    rotation_euler = round(obj.rotation_euler[2], 3)
    if rotation_euler != 1.571 and rotation_euler != -1.571 \
        and rotation_euler != 4.712 and rotation_euler != 0.0 \
        and rotation_euler != 3.142 : 
        print(rotation_euler)
        print(round(obj.rotation_euler[2], 4))
        table_top.rotation_euler = obj.rotation_euler  
        
    
    # Ensure the 'furniture' collection exists
    furniture_collection = bpy.data.collections.get("furniture")
    if not furniture_collection:
        furniture_collection = bpy.data.collections.new("furniture")
        bpy.context.scene.collection.children.link(furniture_collection)

    # Link the new table object to the 'furniture' collection and unlink it from the current collection
    current_collection = table_top.users_collection[0]
    current_collection.objects.unlink(table_top)
    furniture_collection.objects.link(table_top)    




def create_tabletops_from_dxf_collection():
    dxf_collection = bpy.data.collections.get("dxf")
    if dxf_collection:
        for obj in dxf_collection.objects:
            if "Desk" in obj.name or "desk" in obj.name or "Table" in obj.name or "table" in obj.name:
                if obj.type == 'CURVE':
                    shape, num_points = detect_shape(obj)
                    if shape == 'square':
                        print(f"square: {obj.name} - Shape: {shape} - Points: {num_points}")
                        create_tabletop_square_from_object(obj)
                    else:
                        print(f"circle: {obj.name} - Shape: {shape} - Points: {num_points}")    
    else:
        print("Collection 'dxf' not found.")


def create_stool_from_object(obj, furniture_collection):
    width, depth, _ = obj.dimensions
    height = bpy.context.scene.esec_addon_props.chair_height
    #height = 0.45
    stool_scale = bpy.context.scene.esec_addon_props.stool_scale
    bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=(width/4) * stool_scale, depth=0.05, location=(0, 0, 0))
    stool_top = bpy.context.active_object
    stool_top.name = obj.name + "_StoolTop"
    stool_top.location = obj.location
    stool_top.location.z = height - 0.05/2    
    
    
    # Ensure the 'furniture' collection exists
    furniture_collection = bpy.data.collections.get("furniture")
    if not furniture_collection:
        furniture_collection = bpy.data.collections.new("furniture")
        bpy.context.scene.collection.children.link(furniture_collection)

    # Link the new stool object to the 'furniture' collection and unlink it from the current collection
    current_collection = stool_top.users_collection[0]
    current_collection.objects.unlink(stool_top)
    furniture_collection.objects.link(stool_top)    


def create_stools_from_dxf_collection():
    dxf_collection = bpy.data.collections.get("dxf")
    if dxf_collection:
        # Create a new collection called "furniture" if it doesn't exist
        furniture_collection = bpy.data.collections.get("furniture")
        if not furniture_collection:
            furniture_collection = bpy.data.collections.new("furniture")
            bpy.context.scene.collection.children.link(furniture_collection)
        
        for obj in dxf_collection.objects:
            if "chair" in obj.name or "Chair" in obj.name:
                create_stool_from_object(obj, furniture_collection)
    else:
        print("Collection 'dxf' not found.")

#########################################

def create_squares_from_dxf_object(obj, needle, scaleZ):
    # Calculate the bounding box dimensions for the object
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    bbox_dimensions = Vector((max(corner[i] for corner in bbox_corners) - min(corner[i] for corner in bbox_corners) for i in range(3)))
    
    width, depth, _ = bbox_dimensions
    #height = 0.8
    height = bpy.context.scene.esec_addon_props.table_height
    bpy.ops.mesh.primitive_cube_add(size=1)
    table_top = bpy.context.active_object
    table_top.name = obj.name + "_" + needle
    
    # Set the scale of the table_top based on the bounding box dimensions
    table_top.scale.x = width 
    table_top.scale.y = depth 
    table_top.scale.z = scaleZ    

    table_top.location = obj.location
    table_top.location.z = height - 0.025 / 2
    
    # Ensure the 'furniture' collection exists
    furniture_collection = bpy.data.collections.get(needle)
    if not furniture_collection:
        furniture_collection = bpy.data.collections.new(needle)
        bpy.context.scene.collection.children.link(furniture_collection)

    # Link the new table object to the 'furniture' collection and unlink it from the current collection
    current_collection = table_top.users_collection[0]
    current_collection.objects.unlink(table_top)
    furniture_collection.objects.link(table_top)    


def create_squares_from_dxf_collection(needle, scaleZ):
    dxf_collection = bpy.data.collections.get("dxf")
    if dxf_collection:
        for obj in dxf_collection.objects:
            if needle in obj.name:
                create_squares_from_dxf_object(obj, needle, scaleZ)
    else:
        print("Collection 'dxf' not found.")



######################################################################################################
# Function definitions
def function_1(self, context):
    print("Step 1 - prepare DXF")
    move_objects_to_dxf()
    delete_unwanted_objects("dxf")
    rename_objects_dxf("dxf")
    print("Step 1 done")

def function_2(self, context):
    print("Step 2 - prepare IFC")
    move_objects_to_ifc()
    remove_collection("IfcProject/None")
    remove_window_objects("ifc")        
    print("Step 2 done")

def function_3(self, context):
    print("Step 3 - create tables")
    create_tabletops_from_dxf_collection()    
    print("Step 3 done")

def function_4(self, context):
    print("Step 4 - create stools")
    create_stools_from_dxf_collection()
    print("Step 4 done")

def function_5(self, context):
    print("Rock'n'Roll")
    move_objects_to_dxf()
    delete_unwanted_objects("dxf")
    rename_objects_dxf("dxf")
    move_objects_to_ifc()
    remove_collection("IfcProject/None")
    remove_window_objects("ifc")
    create_tabletops_from_dxf_collection()    
    create_stools_from_dxf_collection()
    print("Step 5 done")

class OBJECT_OT_DeleteIfcCollection(bpy.types.Operator):
    bl_idname = "object.delete_ifc_collection"
    bl_label = "Delete 'ifc' Collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if "ifc" in bpy.data.collections:
            bpy.data.collections.remove(bpy.data.collections["ifc"])
            self.report({'INFO'}, "Deleted 'ifc' Collection")
        else:
            self.report({'WARNING'}, "Collection 'ifc' not found")
        return {'FINISHED'}

class OBJECT_OT_DeleteDxfCollection(bpy.types.Operator):
    bl_idname = "object.delete_dxf_collection"
    bl_label = "Delete 'dxf' Collection"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if "dxf" in bpy.data.collections:
            bpy.data.collections.remove(bpy.data.collections["dxf"])
            self.report({'INFO'}, "Deleted 'dxf' Collection")
        else:
            self.report({'WARNING'}, "Collection 'dxf' not found")
        return {'FINISHED'}

class OBJECT_OT_DeleteFurnitureCollection(bpy.types.Operator):
    bl_idname = "object.delete_furniture_collection"
    bl_label = "Delete Furniture Collection"
    bl_description = "Deletes the 'furniture' collection if it exists"

    def execute(self, context):
        furniture_collection = bpy.data.collections.get("furniture")
        if furniture_collection:
            bpy.data.collections.remove(furniture_collection)
            print("Deleted 'furniture' collection.")
        else:
            print("Collection 'furniture' not found.")                
        return {'FINISHED'}

# Operator classes
class ESEC_OT_function_1(bpy.types.Operator):
    bl_idname = "esec.function_1"
    bl_label = "Step 1 - Prepare DXF"

    def execute(self, context):
        function_1(self, context)
        return {'FINISHED'}

class ESEC_OT_function_2(bpy.types.Operator):
    bl_idname = "esec.function_2"
    bl_label = "Step 2 - Prepare IFC"

    def execute(self, context):
        function_2(self, context)
        return {'FINISHED'}

class ESEC_OT_function_3(bpy.types.Operator):
    bl_idname = "esec.function_3"
    bl_label = "Step 3 - Create tables"

    def execute(self, context):
        function_3(self, context)
        return {'FINISHED'}

class ESEC_OT_function_4(bpy.types.Operator):
    bl_idname = "esec.function_4"
    bl_label = "Step 4 - Create chairs"

    def execute(self, context):
        function_4(self, context)
        return {'FINISHED'}

class ESEC_OT_function_5(bpy.types.Operator):
    bl_idname = "esec.function_5"
    bl_label = "Step 1-4 at once"

    def execute(self, context):
        function_5(self, context)
        return {'FINISHED'}

class IMPORT_OT_dxf(bpy.types.Operator):
    bl_idname = "import_scene.dxf_esec"
    bl_label = "Import DXF"
    
    def execute(self, context):
        bpy.ops.import_scene.dxf('INVOKE_DEFAULT')
        return {'FINISHED'}

class IMPORT_OT_ifc(bpy.types.Operator):
    bl_idname = "import_ifc.bim_esec"
    bl_label = "Import IFC"
    
    def execute(self, context):
        bpy.ops.import_ifc.bim('INVOKE_DEFAULT')
        return {'FINISHED'}

class EsecSaveAsOperator(bpy.types.Operator):
    bl_idname = "wm.save_as_esec"
    bl_label = "Save As Blender"
    bl_description = "Save the current file with a new name"

    def execute(self, context):
        bpy.ops.wm.save_as_mainfile('INVOKE_DEFAULT')
        return {'FINISHED'}

class EsecExportObjOperator(bpy.types.Operator):
    bl_idname = "wm.export_obj_esec"
    bl_label = "Export OBJ"
    bl_description = "Export the current scene as an OBJ file"

    def execute(self, context):
        bpy.ops.export_scene.obj('INVOKE_DEFAULT')
        return {'FINISHED'}

class EsecSubmenu(bpy.types.Menu):
    bl_label = "Tools"
    bl_idname = "OBJECT_MT_esec_submenu"

    def draw(self, context):
        layout = self.layout
        layout.operator(OBJECT_OT_DeleteIfcCollection.bl_idname)
        layout.operator(OBJECT_OT_DeleteDxfCollection.bl_idname)
        layout.operator(OBJECT_OT_DeleteFurnitureCollection.bl_idname)


class ESEC_OT_create_storage(bpy.types.Operator):
    bl_idname = "esec.create_storage"
    bl_label = "Create Storage"

    def execute(self, context):
        print("Create Storage")
        create_squares_from_dxf_collection('Storage', bpy.context.scene.esec_addon_props.storage_height)    
        print("Create Storage done")
        return {'FINISHED'}

class ESEC_OT_create_sideboard(bpy.types.Operator):
    bl_idname = "esec.create_sideboard"
    bl_label = "Create Sideboard"

    def execute(self, context):
        print("Create sideboards")
        create_squares_from_dxf_collection('Sideboard', bpy.context.scene.esec_addon_props.sideboard_height)    
        print("Create sideboards done")
        return {'FINISHED'}

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


# Panel class
class ESEC_PT_panel(bpy.types.Panel):
    bl_label = "ESEC 3D Floorplan Creator v" + str(bl_info['version'])
    bl_idname = "ESEC_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ESEC 3D Floorplan'

    def draw(self, context):
        layout = self.layout
        props = context.scene.esec_addon_props

        layout.operator("import_scene.dxf_esec", icon="IMPORT") 
        layout.operator("import_ifc.bim_esec", icon="IMPORT") 
        layout.separator()
        layout.operator("esec.function_1", icon="FILE_VOLUME")
        layout.operator("esec.function_2", icon="FILE_3D")
        layout.operator("esec.function_3", icon="SNAP_VERTEX")
        layout.operator("esec.function_4", icon="OUTLINER_OB_POINTCLOUD")
        layout.separator()
        layout.operator("esec.function_5", icon="HAND")
        layout.separator()        
        layout.operator("wm.save_as_esec", icon="FILE_TICK")
        layout.operator("wm.export_obj_esec", icon='EXPORT')
        layout.separator()        
        layout.menu(EsecSubmenu.bl_idname)
        layout.separator()      
        layout.prop(props, "table_height", text="Table Height")
        layout.prop(props, "chair_height", text="Chair Height")  
        layout.prop(props, "stool_scale", text="Chairs Scale")        
        layout.prop(props, "storage_height", text="Storage Height")        
        layout.prop(props, "sideboard_height", text="Sideboard Height")        
        layout.separator()
        layout.separator()
        layout.operator("esec.create_storage", icon="FILE_3D")
        layout.operator("esec.create_sideboard", icon="FILE_3D")



addon_keymaps = []

def register():
    bpy.utils.register_class(ESECAddonProperties)
    bpy.types.Scene.esec_addon_props = bpy.props.PointerProperty(type=ESECAddonProperties)        
    bpy.utils.register_class(ESEC_OT_function_1)
    bpy.utils.register_class(ESEC_OT_function_2)
    bpy.utils.register_class(ESEC_OT_function_3)
    bpy.utils.register_class(ESEC_OT_function_4)
    bpy.utils.register_class(ESEC_OT_function_5)
    bpy.utils.register_class(ESEC_PT_panel)
    bpy.utils.register_class(EsecSubmenu)
    bpy.utils.register_class(IMPORT_OT_dxf)
    bpy.utils.register_class(IMPORT_OT_ifc)
    bpy.utils.register_class(EsecExportObjOperator)
    bpy.utils.register_class(EsecSaveAsOperator)
    bpy.utils.register_class(OBJECT_OT_DeleteIfcCollection)
    bpy.utils.register_class(OBJECT_OT_DeleteDxfCollection)
    bpy.utils.register_class(OBJECT_OT_DeleteFurnitureCollection)
    bpy.utils.register_class(ESEC_OT_create_storage)
    bpy.utils.register_class(ESEC_OT_create_sideboard)

    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(ESEC_OT_function_1.bl_idname, type='A', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(ESEC_OT_function_2.bl_idname, type='B', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(ESEC_OT_function_3.bl_idname, type='C', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(ESEC_OT_function_4.bl_idname, type='D', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(ESEC_OT_function_5.bl_idname, type='E', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(IMPORT_OT_dxf.bl_idname, 'D', 'PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(IMPORT_OT_ifc.bl_idname, 'I', 'PRESS', alt=True, shift=True)
        addon_keymaps.append((km, kmi))


def unregister():
    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()
    bpy.utils.unregister_class(ESECAddonProperties)
    del bpy.types.Scene.esec_addon_props
    bpy.utils.unregister_class(ESEC_OT_function_1)
    bpy.utils.unregister_class(ESEC_OT_function_2)
    bpy.utils.unregister_class(ESEC_OT_function_3)
    bpy.utils.unregister_class(ESEC_OT_function_4)
    bpy.utils.unregister_class(ESEC_OT_function_5)
    bpy.utils.unregister_class(IMPORT_OT_dxf)
    bpy.utils.unregister_class(IMPORT_OT_ifc)
    bpy.utils.unregister_class(EsecSaveAsOperator)
    bpy.utils.unregister_class(EsecExportObjOperator)
    bpy.utils.unregister_class(ESEC_PT_panel)
    bpy.utils.unregister_class(EsecSubmenu)
    bpy.utils.unregister_class(OBJECT_OT_DeleteIfcCollection)
    bpy.utils.unregister_class(OBJECT_OT_DeleteDxfCollection)
    bpy.utils.unregister_class(OBJECT_OT_DeleteFurnitureCollection)
    bpy.utils.unregister_class(ESEC_OT_create_storage)
    bpy.utils.unregister_class(ESEC_OT_create_sideboard)

if __name__ == "__main__":
    register()




# Squarae 
#   Storage 