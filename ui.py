import bpy
import os
import math
import os
import re
import bmesh
from mathutils import Vector
from bpy.types import Panel

from . import config

# Panel class
class ESEC_PT_panel(bpy.types.Panel):
    bl_label = "ESEC 3D Floorplan Creator v 1.8.3" #+ str(bl_info['version'])
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
        layout.operator("esec.create_3d_chairs", icon="OUTLINER_OB_POINTCLOUD")
        layout.prop(context.scene, "use_high_poly_models")
        layout.operator("esec.create_storage", icon="SNAP_FACE")
        layout.operator("esec.create_sideboard", icon="SNAP_EDGE")
        layout.operator("esec.assign_materials", icon="IMAGE_RGB_ALPHA")
        layout.separator()
        layout.operator("esec.function_5", icon="HAND")
        layout.separator()        
        layout.operator("wm.save_as_esec", icon="FILE_TICK")        
        layout.operator("wm.export_obj_esec", icon='EXPORT')
        layout.operator("esec.export_keyshot_esec", icon='EXPORT')
        layout.separator()
        layout.operator("esec.setup_renderer", icon='SHADING_RENDERED')
        layout.operator("esec.render", icon='RENDERLAYERS')
        layout.separator()        
        layout.menu(EsecSubmenu.bl_idname)
        layout.separator()   
        layout.label(text="Settings")        
        layout.prop(props, "table_height", text="Table Height")
        layout.prop(props, "chair_height", text="Chair Height")  
        layout.prop(props, "stool_scale", text="Chairs Scale")        
        layout.prop(props, "storage_height", text="Storage Height")        
        layout.prop(props, "sideboard_height", text="Sideboard Height")                
        layout.prop(props, "table_margin", text="Table margin")    

class OBJECT_OT_DeleteIfcCollection(bpy.types.Operator):
    bl_idname = "object.delete_ifc_collection"
    bl_label = "Delete 'ifc' Collection"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Deletes the IFC Collection"

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
    bl_description = "Deletes the DXF Collection"

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
    bl_description = "Deletes all furniture Collections"

    def execute(self, context):

        collections = ['tables', 'Office_chairs', 'Dining_chairs', 'Arm_chairs', 'Bar_Stools', 'printer', 'Sofas', 'outdoor_bench', 'outdoor_chair', 'Storage', 'Sideboard', 'bathroom' ]

        for collection_name in collections:
            collection = bpy.data.collections.get(collection_name)
            if collection:
                bpy.data.collections.remove(collection)
                print(f"Deleted '{collection_name}' collection.")
            else:
                print(f"Collection '{collection_name}' not found.")

        return {'FINISHED'}

# Operator classes
class ESEC_OT_function_1(bpy.types.Operator):
    bl_idname = "esec.function_1"
    bl_label = "Step 1 - Prepare DXF"
    bl_description = "Prepares the DXF. Move all objects to the 'dxf' collection, delete unwanted objects and rename the objects."

    def execute(self, context):
        #function_1(self, context)
        print("Step 1 - prepare DXF")
        move_objects_to_dxf()
        move_unwanted_objects("dxf")
        rename_objects_dxf("dxf")
        print("Step 1 done")        
        return {'FINISHED'}

class ESEC_OT_function_2(bpy.types.Operator):
    bl_idname = "esec.function_2"
    bl_label = "Step 2 - Prepare IFC"
    bl_description = "Prepares the IFC file. Move all objects to the 'ifc' collection, remove the 'IfcProject' collection and move the windows to the 'Windows' collection."

    def execute(self, context):
        print("Step 2 - prepare IFC")
        move_objects_to_ifc()
        remove_collection("IfcProject/None")
        move_objects_to_new_collection("IfcSlab/Floor", "ifc", "Floors")  
        move_objects_to_new_collection("IfcDoor/Door", "ifc", "Doors")
        move_objects_to_new_collection("IfcWindow/Window", "ifc", "Windows")  
        print("Step 2 done")        
        return {'FINISHED'}

class ESEC_OT_function_3(bpy.types.Operator):
    bl_idname = "esec.function_3"
    bl_label = "Step 3 - Create tables"
    bl_description = "Create tables from the DXF collection."

    def execute(self, context):
        print("Step 3 - create tables")
        create_tabletops_from_dxf_collection()    
        print("Step 3 done")
        return {'FINISHED'}

class ESEC_OT_create_simple_chairs(bpy.types.Operator):
    bl_idname = "esec.create_simple_chairs"
    bl_label = "Step 4 - Create simple chairs"
    bl_description = "Create simple chairs (just circles) from the DXF collection."

    def execute(self, context):
        print("Step 4 - create stools")
        create_stools_from_dxf_collection()
        print("Step 4 done")
        return {'FINISHED'}
    
class ESEC_OT_create_3d_chairs(bpy.types.Operator):
    bl_idname = "esec.create_3d_chairs"
    bl_label = "Step 4 - Create 3D Objects"
    bl_description = "Create chairs, stools and sofas from the DXF collection."

    def execute(self, context):
        create3D_Objects()
        return {'FINISHED'}

class ESEC_OT_function_5(bpy.types.Operator):
    bl_idname = "esec.function_5"
    bl_label = "Step 1-7 at once"
    bl_description = "Execute all steps at once"

    def execute(self, context):
        print("Rock'n'Roll")
        move_objects_to_dxf()
        move_unwanted_objects("dxf")
        rename_objects_dxf("dxf")
        move_objects_to_ifc()
        remove_collection("IfcProject/None")
        move_objects_to_new_collection("IfcSlab/Floor", "ifc", "Floors")  
        move_objects_to_new_collection("IfcDoor/Door", "ifc", "Doors")
        move_objects_to_new_collection("IfcWindow/Window", "ifc", "Windows") 
        create_tabletops_from_dxf_collection()    
        create3D_Objects()
        create_squares_from_dxf_collection('Storage', bpy.context.scene.esec_addon_props.storage_height)    
        create_squares_from_dxf_collection('Sideboard', bpy.context.scene.esec_addon_props.sideboard_height) 
        assign_collection_materials()
        print("all done")        
        return {'FINISHED'}

class IMPORT_OT_dxf(bpy.types.Operator):
    bl_idname = "import_scene.dxf_esec"
    bl_label = "Import DXF"
    bl_description = "Import the DXF file exported from Archiologic"
    
    def execute(self, context):
        global last_imported_dxf_directory, last_imported_dxf_filename
        bpy.ops.import_scene.dxf('INVOKE_DEFAULT')
        return {'FINISHED'}

class IMPORT_OT_ifc(bpy.types.Operator):
    bl_idname = "import_ifc.bim_esec"
    bl_label = "Import IFC"
    bl_description = "Import the IFC file exported from Archiologic"
    
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
        bpy.ops.wm.obj_export('INVOKE_DEFAULT')
        return {'FINISHED'}

class EsecExportKeyShotOperator(bpy.types.Operator):
    bl_idname = "esec.export_keyshot_esec"
    bl_label = "Export to Keyshot"
    bl_description = "Export the current scene to Keyshot. Keyshot Plugin required."

    def execute(self, context):
        bpy.ops.keyshot.send_to_keyshot()
        return {'FINISHED'}

class EsecSubmenu(bpy.types.Menu):
    bl_label = "Tools"
    bl_idname = "OBJECT_MT_esec_submenu"

    def draw(self, context):
        layout = self.layout
        layout.operator(OBJECT_OT_DeleteIfcCollection.bl_idname)
        layout.operator(OBJECT_OT_DeleteDxfCollection.bl_idname)
        layout.operator(OBJECT_OT_DeleteFurnitureCollection.bl_idname)
        layout.operator("esec.create_simple_chairs", icon="OUTLINER_OB_POINTCLOUD")


class ESEC_OT_create_storage(bpy.types.Operator):
    bl_idname = "esec.create_storage"
    bl_label = "Step 5 - Create Storage"
    bl_description = "Create storage from the DXF collection."

    def execute(self, context):
        print("Create Storage")
        create_squares_from_dxf_collection('Storage', bpy.context.scene.esec_addon_props.storage_height)    
        print("Create Storage done")
        return {'FINISHED'}

class ESEC_OT_create_sideboard(bpy.types.Operator):
    bl_idname = "esec.create_sideboard"
    bl_label = "Step 6 - Create Sideboard"
    bl_description = "Create sideboard from the DXF collection."

    def execute(self, context):
        print("Create sideboards")
        create_squares_from_dxf_collection('Sideboard', bpy.context.scene.esec_addon_props.sideboard_height)    
        print("Create sideboards done")
        return {'FINISHED'}


class ESEC_OT_assign_materials(bpy.types.Operator):
    bl_idname = "esec.assign_materials"
    bl_label = "Step 7 - Assign Materials"
    bl_description = "Assign materials to all objects."

    def execute(self, context):
        assign_collection_materials()
        return {'FINISHED'}         

class ESEC_OT_setup_renderer(bpy.types.Operator):
    bl_idname = "esec.setup_renderer"
    bl_label = "Setup Renderer"
    bl_description = "Setup the GPU cycles renderer. Create a hdri enviroment, set a transparent background and create a camera."

    def execute(self, context):
        setup_render()
        setup_hdri()
        set_transparent_background()
        setup_camera()
        return {'FINISHED'}

class ESEC_OT_render(bpy.types.Operator):
    bl_idname = "esec.render"
    bl_label = "Render Scene"
    bl_description = "Renders the scene with the current settings. Dont forget to create the render enviroment first."

    def execute(self, context):
        render_scene(3400, 1923)
        return {'FINISHED'}

addon_keymaps = []

def register():
    #bpy.utils.register_class(MyPanel)         
    bpy.utils.register_class(ESEC_OT_function_1)
    bpy.utils.register_class(ESEC_OT_function_2)
    bpy.utils.register_class(ESEC_OT_function_3)
    bpy.utils.register_class(ESEC_OT_create_simple_chairs)
    bpy.utils.register_class(ESEC_OT_create_3d_chairs)
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
    bpy.utils.register_class(ESEC_OT_assign_materials)
    bpy.utils.register_class(ESEC_OT_setup_renderer)
    bpy.utils.register_class(ESEC_OT_render)
    bpy.utils.register_class(EsecExportKeyShotOperator)


    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:        
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(ESEC_OT_function_1.bl_idname, type='A', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(ESEC_OT_function_2.bl_idname, type='B', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(ESEC_OT_function_3.bl_idname, type='C', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(ESEC_OT_create_simple_chairs.bl_idname, type='D', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(ESEC_OT_function_5.bl_idname, type='E', value='PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(IMPORT_OT_dxf.bl_idname, 'D', 'PRESS', alt=True, shift=True)
        kmi = km.keymap_items.new(IMPORT_OT_ifc.bl_idname, 'I', 'PRESS', alt=True, shift=True)
        addon_keymaps.append((km, kmi))    
    

def unregister():
    #bpy.utils.unregister_class(MyPanel)
    
    bpy.utils.unregister_class(ESEC_OT_function_1)
    bpy.utils.unregister_class(ESEC_OT_function_2)
    bpy.utils.unregister_class(ESEC_OT_function_3)
    bpy.utils.unregister_class(ESEC_OT_create_simple_chairs)
    bpy.utils.unregister_class(ESEC_OT_create_3d_chairs)
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
    bpy.utils.unregister_class(ESEC_OT_assign_materials)
    bpy.utils.unregister_class(ESEC_OT_setup_renderer)
    bpy.utils.unregister_class(ESEC_OT_render)
    bpy.utils.unregister_class(EsecExportKeyShotOperator)

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()    
        
#######################################################################################

def detect_shape(ob):

    #Objectname: TaskChair.159 - Shape: circle - Points: 72
    #Objectname: ConferenceChair.001 - Shape: circle - Points: 30
    #Objectname: OutdoorChair.002 - Shape: circle - Points: 20

    # Get the curve data from the object
    curve = ob.data
    
    # Count the number of points in the first spline of the curve
    num_points = len(curve.splines[0].bezier_points) if curve.splines[0].type == 'BEZIER' else len(curve.splines[0].points)
    
    # Basic shape detection based on point count
    if num_points < 11:
        return 'square', num_points
    elif num_points > 10:
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


def move_unwanted_objects(collection_name):
    source_collection = bpy.data.collections.get(collection_name)
    if not source_collection:
        print(f"Collection '{collection_name}' not found.")
        return

    # Create the target collection if it doesn't exist
    orphan_collection = bpy.data.collections.get('dxf_orphan')
    if not orphan_collection:
        orphan_collection = bpy.data.collections.new(name='dxf_orphan')
        bpy.context.scene.collection.children.link(orphan_collection)
        print(f"Created new collection: 'dxf_orphan'")

    allowed_keywords = ['Desk', 'Chair', 'chair', 'Sofa', 'Table', 'Storage', 'Sideboard', 'Bed', 'Stool', 'Printer', 'Bench', 'Toilet', 'Urinal', 'Sink']
    objects_to_move = []

    # Find objects to move
    for obj in source_collection.objects:
        if not any(keyword in obj.name for keyword in allowed_keywords):
            objects_to_move.append(obj)

    # Move objects
    for obj in objects_to_move:
        # Unlink from the source collection
        source_collection.objects.unlink(obj)
        # Link to the target collection
        orphan_collection.objects.link(obj)
        print(f"Moved object: {obj.name}")

    # Hide the orphan collection
    orphan_collection.hide_viewport = True
    print(f"Collection 'dxf_orphan' is now hidden.")

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


def move_window_objects_to_collection(collection_name, new_collection_name):
    source_collection = bpy.data.collections.get(collection_name)
    if not source_collection:
        print(f"Collection '{collection_name}' not found.")
        return

    # Get or create the target collection
    target_collection = bpy.data.collections.get(new_collection_name)
    if not target_collection:
        target_collection = bpy.data.collections.new(new_collection_name)
        bpy.context.scene.collection.children.link(target_collection)
    
    keywords = ['Window', 'window']
    objects_to_move = []

    # Find objects to move
    for obj in source_collection.objects:
        if any(keyword in obj.name for keyword in keywords):
            objects_to_move.append(obj.name)

    # Move objects
    for obj_name in objects_to_move:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            source_collection.objects.unlink(obj)
            target_collection.objects.link(obj)
            print(f"Moved object: {obj_name} to collection: {new_collection_name}")


def move_objects_to_new_collection(keyword, collection_name, new_collection_name):
    source_collection = bpy.data.collections.get(collection_name)
    if not source_collection:
        print(f"Collection '{collection_name}' not found.")
        return

    # Get or create the target collection
    target_collection = bpy.data.collections.get(new_collection_name)
    if not target_collection:
        target_collection = bpy.data.collections.new(new_collection_name)
        bpy.context.scene.collection.children.link(target_collection)
    
    #keywords = ['IfcSlab/Floor']
    objects_to_move = []

    # Find objects to move
    for obj in source_collection.objects:
        if keyword in obj.name :
            objects_to_move.append(obj.name)

    # Move objects
    for obj_name in objects_to_move:
        obj = bpy.data.objects.get(obj_name)
        if obj:
            source_collection.objects.unlink(obj)
            target_collection.objects.link(obj)
            print(f"Moved object: {obj_name} to collection: {new_collection_name}") 


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
    # Apply the inverse rotation to each point of the object to align it with the world axes
    inv_rot = obj.rotation_euler.to_matrix().inverted()

    local_coords = []
    for spline in obj.data.splines:
        if spline.type == 'BEZIER':
            local_coords.extend(obj.matrix_world @ (inv_rot @ Vector(point.co[:3])) for point in spline.bezier_points)
        elif spline.type == 'POLY':
            local_coords.extend(obj.matrix_world @ (inv_rot @ Vector(point.co[:3])) for point in spline.points)

    if not local_coords:
        print(f"No points found in object {obj.name}")
        return

    # Calculate the bounding box dimensions in local space
    bbox_dimensions = Vector((max(coord[i] for coord in local_coords) - min(coord[i] for coord in local_coords) for i in range(3)))

    # Calculate the dimensions directly from the transformed vertices
    width = max(v.x for v in local_coords) - min(v.x for v in local_coords)
    depth = max(v.y for v in local_coords) - min(v.y for v in local_coords)
    
    height = bpy.context.scene.esec_addon_props.table_height
    bpy.ops.mesh.primitive_cube_add(size=1)
    table_top = bpy.context.active_object
    table_top.name = obj.name + "_TableTop"

    # Set the scale of the table_top based on the directly calculated dimensions
    table_top.scale.x = width - bpy.context.scene.esec_addon_props.table_margin
    table_top.scale.y = depth - bpy.context.scene.esec_addon_props.table_margin
    table_top.scale.z = 0.025

    table_top.location = obj.location
    table_top.location.z = height - 0.025 / 2

    # Now you can apply the original rotation of the object to the table_top
    table_top.rotation_euler = obj.rotation_euler     
    
    # Ensure the 'furniture' collection exists
    furniture_collection = bpy.data.collections.get("tables")
    if not furniture_collection:
        furniture_collection = bpy.data.collections.new("tables")
        bpy.context.scene.collection.children.link(furniture_collection)

    # Link the new table object to the 'furniture' collection and unlink it from the current collection
    current_collection = table_top.users_collection[0]
    current_collection.objects.unlink(table_top)
    furniture_collection.objects.link(table_top)    

def create_tabletop_rounds_from_object(obj):
    # Calculate the bounding box dimensions for the object
    bbox_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    bbox_dimensions = Vector((max(corner[i] for corner in bbox_corners) - min(corner[i] for corner in bbox_corners) for i in range(3)))

    width, depth, _ = bbox_dimensions
    radius = max(width, depth) / 2  # Use the longer dimension as diameter
    height = bpy.context.scene.esec_addon_props.table_height
    bpy.ops.mesh.primitive_cylinder_add(radius=radius, depth=0.025)
    table_top = bpy.context.active_object
    table_top.name = obj.name + "_TableTop"

    table_top.location = obj.location
    table_top.location.z = height - 0.025 / 2

    # Ensure the 'furniture' collection exists
    furniture_collection = bpy.data.collections.get("tables")
    if not furniture_collection:
        furniture_collection = bpy.data.collections.new("tables")
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
                        #print(f"square: {obj.name} - Shape: {shape} - Points: {num_points}")
                        create_tabletop_square_from_object(obj)
                    else:
                        #print(f"circle: {obj.name} - Shape: {shape} - Points: {num_points}")    
                        create_tabletop_rounds_from_object(obj)
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
    furniture_collection = bpy.data.collections.get("chairs")
    if not furniture_collection:
        furniture_collection = bpy.data.collections.new("chairs")
        bpy.context.scene.collection.children.link(furniture_collection)

    # Link the new stool object to the 'furniture' collection and unlink it from the current collection
    current_collection = stool_top.users_collection[0]
    current_collection.objects.unlink(stool_top)
    furniture_collection.objects.link(stool_top)    


def create_stools_from_dxf_collection():
    dxf_collection = bpy.data.collections.get("dxf")
    if dxf_collection:
        # Create a new collection called "furniture" if it doesn't exist
        furniture_collection = bpy.data.collections.get("chairs")
        if not furniture_collection:
            furniture_collection = bpy.data.collections.new("chairs")
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

#################################################################################################################
#################################################################################################################

def create_3Dobject_from_dxf_collection(needles, model_name, new_collection_name, ignoreKeyword=None):
    
    # Convert single string needle to list for compatibility
    if isinstance(needles, str):
        needles = [needles]
    
    if bpy.context.scene.use_high_poly_models:
        #file_loc = bpy.path.abspath("//models_high\\"+model_name+".obj")
        strDirectory = os.path.join(os.path.dirname(__file__), config.MODELS_HIGH_DIRECTORY)        
    else:
        #file_loc = bpy.path.abspath("//models_low\\"+model_name+".obj")
        strDirectory = os.path.join(os.path.dirname(__file__), config.MODELS_LOW_DIRECTORY)        

    file_loc = os.path.join(strDirectory, model_name + ".obj")

    # Check if the file exists
    if not os.path.isfile(file_loc):
        print(f"Error: {file_loc} does not exist.")
        print(f"strDirectory: {strDirectory} does not exist.")
        return

    imported_object = bpy.ops.import_scene.obj(filepath=file_loc)
    selected_obj = bpy.context.selected_objects[0]
            
    collection_to_write = bpy.data.collections.get(new_collection_name)
    if not collection_to_write:
        collection_to_write = bpy.data.collections.new(new_collection_name)
        bpy.context.scene.collection.children.link(collection_to_write)       

    dxf_collection = bpy.data.collections.get("dxf")
    if dxf_collection:
        for obj in dxf_collection.objects:
            for needle in needles:
                if needle.lower() in obj.name.lower():  
                    if ignoreKeyword and ignoreKeyword.lower() in obj.name.lower():
                        continue  # skip this object and go to the next
                    create_3d_object_from_dxf_object(obj,selected_obj.copy(),collection_to_write)
    else:
        print("Collection 'dxf' not found.")

    #cleanup first imported model from 0 0 0 position
    bpy.data.objects.remove(selected_obj, do_unlink=True)



def create_3d_object_from_dxf_object(dxf_obj,obj_model, collection_to_add_to):

    print('create_chair_from_dxf_object: dxf_obj.location: ', dxf_obj.location)
    obj_model.location = dxf_obj.location
    obj_model.rotation_euler[2] = dxf_obj.rotation_euler[2]
    collection_to_add_to.objects.link(obj_model)
    

######################################################################################################

def count_objects_in_collection(collection_name):
    #count_objects_in_collection('dxf')

    collection = bpy.data.collections.get(collection_name)
    
    if not collection:
        print(f"No collection named {collection_name}")
        return

    # We'll use a dictionary to count the objects
    object_count = {}

    for obj in collection.objects:
        # We'll use regex to extract the base name of the object (name without trailing .###)
        match = re.match(r"([^.]*)(\.\d+)?", obj.name)
        if match:
            base_name = match.group(1)
            # If this base name is not in the dictionary yet, add it with a count of 1
            if base_name not in object_count:
                object_count[base_name] = 1
            # If it's already in the dictionary, increment the count
            else:
                object_count[base_name] += 1
    
    for name, count in object_count.items():
        print(f"{count}x {name}")


def create_glass_material():
    # Create a glass material
    glass_material = bpy.data.materials.new(name="Windows")
    glass_material.use_nodes = True

    # Get the material node tree
    nodes = glass_material.node_tree.nodes

    # Clear all nodes
    for node in nodes:
        nodes.remove(node)

    # Create a new Glass BSDF node
    glass_node = nodes.new(type='ShaderNodeBsdfGlass')

    # Set the Glass BSDF properties
    glass_node.inputs['Roughness'].default_value = 0
    glass_node.inputs['IOR'].default_value = 1.450

    # Create a Material Output node and connect the Glass node to its Surface input
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    links = glass_material.node_tree.links
    link = links.new(glass_node.outputs[0], output_node.inputs[0])
    
    return glass_material



def create_material(material_name, base_color, specular, roughness):
    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True

    # Get the Principled BSDF node
    principled_bsdf = material.node_tree.nodes["Principled BSDF"]

    # Set the base color (RGB)
    principled_bsdf.inputs['Base Color'].default_value = base_color

    # Set specular
    principled_bsdf.inputs['Specular'].default_value = specular

    # Set roughness
    principled_bsdf.inputs['Roughness'].default_value = roughness
    
    return material

#color helper
# credtis to https://gist.github.com/CGArtPython

def hex_color_to_rgba(hex_color):
    # remove the leading '#' symbol if it is set
    if hex_color[1] == "#":
        hex_color = hex_color[1:]

    # extracting the Red color component - RRxxxx
    red = int(hex_color[:2], 16)
    # dividing by 255 to get a number between 0.0 and 1.0
    srgb_red = red / 255
    linear_red = convert_srgb_to_linear_rgb(srgb_red)

    # extracting the Green color component - xxGGxx
    green = int(hex_color[2:4], 16)
    # dividing by 255 to get a number between 0.0 and 1.0
    srgb_green = green / 255
    linear_green = convert_srgb_to_linear_rgb(srgb_green)

    # extracting the Blue color component - xxxxBB
    blue = int(hex_color[4:6], 16)
    # dividing by 255 to get a number between 0.0 and 1.0
    srgb_blue = blue / 255
    linear_blue = convert_srgb_to_linear_rgb(srgb_blue)

    return tuple([linear_red, linear_green, linear_blue, 1.0])


def convert_srgb_to_linear_rgb(srgb_color_component: float) -> float:
    """
    Converting from sRGB to Linear RGB
    based on https://en.wikipedia.org/wiki/SRGB#From_sRGB_to_CIE_XYZ
    """
    if srgb_color_component <= 0.04045:
        linear_color_component = srgb_color_component / 12.92
    else:
        linear_color_component = math.pow((srgb_color_component + 0.055) / 1.055, 2.4)

    return linear_color_component

def assign_collection_materials():
    # Remove all materials
    for material in bpy.data.materials:
        bpy.data.materials.remove(material)

    #custom materials
    create_material("Floor_pale_dark_blue", hex_color_to_rgba("E0E9F2"), 0, 0.1)
    create_material("Floor_pale_red", hex_color_to_rgba("F8E0E4"), 0, 0.1)
    create_material("Floor_pale_orange", hex_color_to_rgba("FDEFD9"), 0, 0.1)
    create_material("Floor_pale_light_green", hex_color_to_rgba("E0EED2"), 0, 0.1)
    create_material("Floor_pale_light_blue", hex_color_to_rgba("E0F2F9"), 0, 0.1)

    # Create materials
    materials = {
        "ifc": create_material("ifc", (0.8, 0.8, 0.8, 1), 0, 0.1),
        "Floor": create_material("Floor", (1, 1, 1, 1), 0, 0.1),
        "Doors": create_material("Doors", (0.75, 0.75, 0.75, 1), 0.8, 0.1),
        "Windows": create_glass_material(),
        "tables": create_material("Table", (0.9, 0.9, 0.9, 1), 0.8, 0.1),
        "Office_chairs": create_material("Office_chairs", (0.75, 0.75, 0.75, 1), 0.8, 0.1),
        "Dining_chairs": create_material("Dining_chairs", (0.75, 0.75, 0.75, 1), 0.8, 0.1),
        "Arm_chairs": create_material("Arm_chairs", (0.75, 0.75, 0.75, 1), 0.8, 0.1),
        "Bar_Stools": create_material("Bar_Stools", (0.75, 0.75, 0.75, 1), 0.8, 0.1),
        "printer": create_material("printer", (0.75, 0.75, 0.75, 1), 0.8, 0.1),
        "Sofas": create_material("Sofas", (0.75, 0.75, 0.75, 1), 0.8, 0.1),
        "outdoor_bench": create_material("outdoor_bench", (0.75, 0.75, 0.75, 1), 0.15, 0.15),
        "outdoor_chair": create_material("outdoor_chair", (0.75, 0.75, 0.75, 1), 0.15, 0.15),
        "Storage": create_material("Storage", (0.75, 0.75, 0.75, 1), 0.8, 0.1),
        "Sideboard": create_material("Sideboard", (0.75, 0.75, 0.75, 1), 0.8, 0.1),
        "Bathroom": create_material("Bathroon", (0.75, 0.75, 0.75, 1), 0.8, 0.1)
    }

    # Assign materials to collections
    for coll in bpy.data.collections:
        if coll.name in materials:
            material = materials[coll.name]
        else:
            material = bpy.data.materials.new(name=coll.name)
            material.diffuse_color = (0.8, 0.8, 0.8, 1.0)  # Light gray color
        
        # Assign material to each object in the collection
        for obj in coll.objects:
            if obj.type == 'MESH':
                obj.data.materials.clear()
                obj.data.materials.append(material)

def hide_collection(collection_name):
    collection = bpy.data.collections.get(collection_name)
    if collection:
        collection.hide_viewport = True
        collection.hide_render = True
    else:
        print(f"Collection '{collection_name}' not found.")

def setup_hdri():
    # Path to your HDRI image
    strDirectory = os.path.join(os.path.dirname(__file__), config.HDRI_DIRECTORY)        
    hdri_path = os.path.join(strDirectory, "startup.hdr")


    # Create a new world if there is none
    if not bpy.data.worlds:
        bpy.context.scene.world = bpy.data.worlds.new("World")
        
    # Set the world to use nodes
    bpy.context.scene.world.use_nodes = True

    # Get the tree
    tree = bpy.context.scene.world.node_tree

    # Clear all nodes to start clean
    tree.nodes.clear()

    # Add the needed nodes
    links = tree.links
    tex_coord = tree.nodes.new(type='ShaderNodeTexCoord')
    mapping = tree.nodes.new(type='ShaderNodeMapping')
    texture = tree.nodes.new(type='ShaderNodeTexEnvironment')
    bg = tree.nodes.new(type='ShaderNodeBackground')
    output = tree.nodes.new(type='ShaderNodeOutputWorld')

    # Set the HDRI image
    texture.image = bpy.data.images.load(hdri_path)

    # Connect the nodes
    links.new(tex_coord.outputs['Generated'], mapping.inputs['Vector'])
    links.new(mapping.outputs['Vector'], texture.inputs['Vector'])
    links.new(texture.outputs['Color'], bg.inputs['Color'])
    links.new(bg.outputs['Background'], output.inputs['Surface'])

    # Set the world strength
    bg.inputs['Strength'].default_value = 1.0  # Set to desired strength

    # Update the scene, if necessary
    bpy.context.view_layer.update()

def set_transparent_background():
    # Set the film to transparent
    bpy.context.scene.render.film_transparent = True
    
    # Set transparent glass
    bpy.context.scene.cycles.film_transparent_glass = True

def setup_camera():
    # Define scene and camera
    scene = bpy.context.scene

    # Remove camera if it already exists
    if "Camera" in bpy.data.objects:
        bpy.data.objects.remove(bpy.data.objects["Camera"], do_unlink=True)

    # Add new camera
    camera_data = bpy.data.cameras.new(name="Camera")
    camera = bpy.data.objects.new('Camera', camera_data)
    bpy.context.collection.objects.link(camera)

    # Define camera parameters
    camera.rotation_euler = (math.radians(90), 0, math.radians(180))

    # Check if the 'ifc' collection exists in the scene
    if 'ifc' in bpy.data.collections:
        ifc_collection = bpy.data.collections['ifc']
    else:
        print("Collection 'ifc' does not exist in the scene.")
        return

    # Create empty mesh and object
    mesh = bpy.data.meshes.new(name="EmptyMesh")
    empty_object = bpy.data.objects.new("EmptyObject", mesh)
    bpy.context.collection.objects.link(empty_object)

    # Create bmesh object and link it to the mesh
    bm = bmesh.new()
    bm.from_mesh(mesh)

    # Add all mesh object's vertices in the 'ifc' collection to the bmesh
    for obj in ifc_collection.objects:
        if obj.type == 'MESH':
            transformed = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
            for vert in transformed:
                bm.verts.new(vert)

    # Update the bmesh to the mesh
    bm.to_mesh(mesh)
    bm.free()

    # Calculate center and dimensions of the bounding box
    bbox_center = 0.125 * sum((Vector(b) for b in empty_object.bound_box), Vector())
    bbox_dim = empty_object.dimensions

    # Calculate camera distance
    camera_distance = max(bbox_dim.x, bbox_dim.y) / (2 * math.tan(camera_data.angle / 2))

    # Position camera
    camera.location = bbox_center
    camera.location.z += camera_distance + 10
    camera.rotation_euler = (0.0, 0.0, 0.0)  # Rotate the camera 180 degrees around the z axis


    # Delete the temporary object
    bpy.data.objects.remove(empty_object, do_unlink=True)



def setup_render():
    # Switch the render engine to Cycles
    bpy.context.scene.render.engine = 'CYCLES'
    
    # Switch the viewport shading to Rendered
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'RENDERED'    

    # Hide the 'dxf' collection
    hide_collection('dxf')  

    # Set the render device to GPU if available
    bpy.context.scene.cycles.device = 'GPU'
    

def create3D_Objects():
    print("Create 3d objects")
    create_3Dobject_from_dxf_collection(['TaskChair', 'ConferenceChair', 'Genericofficechair'],'office_chair', 'Office_chairs')       
    create_3Dobject_from_dxf_collection(['DiningChair', 'GenericChair'],'dining_chair', 'Dining_chairs')        
    create_3Dobject_from_dxf_collection(['LoungeChair', 'Armchair'],'arm_chair', 'Arm_chairs', ignoreKeyword='Outdoor')
    create_3Dobject_from_dxf_collection('BarStool','bar_stool', 'Bar_Stools')
    create_3Dobject_from_dxf_collection('Printer','printer', 'printer')
    create_3Dobject_from_dxf_collection('Sofa','couch_76x76x45_round', 'Sofas', ignoreKeyword='Corner')
    create_3Dobject_from_dxf_collection('CornerSofa','couch_76x76x45_round_corner', 'Sofas')
    create_3Dobject_from_dxf_collection('OutdoorBench','outdoor_bench', 'outdoor_bench')
    create_3Dobject_from_dxf_collection(['OutdoorChair', 'OutdoorArmchair'],'outdoor_chair', 'outdoor_chair')
    create_3Dobject_from_dxf_collection('Sink','sink', 'bathroom')
    create_3Dobject_from_dxf_collection('Toilet','toilet', 'bathroom')
    create_3Dobject_from_dxf_collection('Urinal','urinal', 'bathroom')
    print("Create 3d objects done")

def render_scene(resolution_x, resolution_y):
    global last_imported_dxf_directory, last_imported_dxf_filename
    # Set up rendering properties
    bpy.context.scene.render.engine = 'CYCLES'
    bpy.context.scene.render.image_settings.file_format = 'PNG'
    bpy.context.scene.render.resolution_x = resolution_x
    bpy.context.scene.render.resolution_y = resolution_y
    bpy.context.scene.render.resolution_percentage = 100
   
    # Get the absolute path and filename from the BIMProperties
    abs_path = bpy.data.scenes["Scene"].BIMProperties.ifc_file
    directory = os.path.dirname(abs_path)
    filename = os.path.splitext(os.path.basename(abs_path))[0]  # Remove the extension    

    # Remove the .dxf extension
    filename = os.path.splitext(filename)[0]+"_3D-render_"+str(resolution_x)+"x"+str(resolution_y)

    # Set the filepath for the rendered image
    bpy.context.scene.render.filepath = os.path.join(directory, filename)

    # Set the active camera
    if 'Camera' in bpy.data.objects:
        bpy.context.scene.camera = bpy.data.objects['Camera']
    else:
        print("No camera found in the scene.")
        return

    print("Start rendering to" + str(bpy.context.scene.render.filepath))
    # Render the scene
    bpy.ops.render.render(write_still=True)
    print("Finish renderer")
