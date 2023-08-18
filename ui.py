import bpy
import os
import math
import os
import re
import inspect
import bmesh
import mathutils
from mathutils import Vector
from bpy.types import Panel
from . import config

def get_version_from_init():
    # Get the directory containing the current script
    current_dir = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))

    # Construct the full path to the __init__.py file
    init_file_path = os.path.join(current_dir, "__init__.py")

    with open(init_file_path, "r") as file:
        for line in file:
            if match := re.search(r'"version": \((\d+), (\d+), (\d+)\)', line):
                return '.'.join(match.groups())
    return None

# Panel class
class ESEC_PT_panel(bpy.types.Panel):
    bl_label = "ESEC 3D Floorplan Creator " + get_version_from_init()
    bl_idname = "ESEC_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ESEC'

    def draw(self, context):
        layout = self.layout
        props = context.scene.esec_addon_props

        layout.label(text="Import")
        row_01 = layout.row(align=True)  # align=True puts operators side by side
        row_01.operator("import_scene.dxf_esec", icon="IMPORT") 
        row_01.operator("import_ifc.bim_esec", icon="IMPORT") 
        layout.separator()

        layout.label(text="Process")
        layout.operator("esec.function_1", icon="FILE_VOLUME")
        layout.operator("esec.function_2", icon="FILE_3D")
        layout.operator("esec.function_3", icon="SNAP_VERTEX")
        layout.operator("esec.create_3d_chairs", icon="OUTLINER_OB_POINTCLOUD")        
        #layout.operator("esec.create_storage", icon="SNAP_FACE")
        #layout.operator("esec.create_sideboard", icon="SNAP_EDGE")
        layout.operator("esec.assign_materials", icon="IMAGE_RGB_ALPHA")
        layout.separator()
        layout.operator("esec.function_5", icon="HAND")
        layout.separator()   
        layout.label(text="Close holes")        
        row_02 = layout.row(align=True)  # align=True puts operators side by side
        row_02.operator("esec.close_holes_prepare", icon="TRACKING_FORWARDS")        
        row_02.operator("esec.close_holes_finish", icon='CHECKMARK')
        layout.separator()        
        layout.label(text="Save/Export")
        row_03 = layout.row(align=True)  # align=True puts operators side by side
        row_03.operator("wm.save_as_esec", icon="FILE_TICK")        
        row_03.operator("wm.export_obj_esec", icon='EXPORT')
        layout.operator("esec.export_keyshot_esec", icon='EXPORT')
        layout.separator()
        layout.label(text="Render")
        row_04 = layout.row(align=True)  # align=True puts operators side by side
        row_04.operator("esec.setup_renderer", icon='SHADING_RENDERED')
        row_04.operator("esec.render", icon='RENDERLAYERS')
        layout.separator()        
        layout.menu(EsecSubmenu.bl_idname)
        layout.separator()   
        box = layout.box()
        row = box.row()
        row.prop(props, "show_settings", icon="TRIA_DOWN" if props.show_settings else "TRIA_RIGHT", emboss=False)
        if props.show_settings:
            box.prop(context.scene, "use_high_poly_models")
            box.prop(props, "table_height", text="Table Height")
            box.prop(props, "chair_height", text="Chair Height")
            box.prop(props, "stool_scale", text="Chairs Scale")
            box.prop(props, "storage_height", text="Storage Height")
            box.prop(props, "sideboard_height", text="Sideboard Height")
            box.prop(props, "desk_table_margin", text="Desk Table margin")   
            box.prop(props, "meeting_table_margin", text="Meeting Table margin")          
        layout.label(text="  stefan.knaak@e-shelter.io")            


class OBJECT_OT_DeleteIfcCollection(bpy.types.Operator):
    bl_idname = "object.delete_ifc_collection"
    bl_label = "Delete 'Structur' Collection"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Deletes all structure Collections"

    def execute(self, context):

        collections = ['ifc', 'Floors', 'Doors', 'Windows', 'Bar_Stools', 'floors_intersect', 'Structure']

        for collection_name in collections:
            if collection := bpy.data.collections.get(collection_name):
                bpy.data.collections.remove(collection)
                print(f"Deleted '{collection_name}' collection.")
            else:
                print(f"Collection '{collection_name}' not found.")

        return {'FINISHED'}

class OBJECT_OT_DeleteDxfCollection(bpy.types.Operator):
    bl_idname = "object.delete_dxf_collection"
    bl_label = "Delete 'dxf' Collection"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Deletes the DXF Collections"

    def execute(self, context):

        collections = ['dxf', 'dxf_orphan', 'DXF']

        for collection_name in collections:
            if collection := bpy.data.collections.get(collection_name):
                bpy.data.collections.remove(collection)
                print(f"Deleted '{collection_name}' collection.")
            else:
                print(f"Collection '{collection_name}' not found.")

        return {'FINISHED'}

class OBJECT_OT_DeleteFurnitureCollection(bpy.types.Operator):
    bl_idname = "object.delete_furniture_collection"
    bl_label = "Delete Furniture Collection"
    bl_description = "Deletes all furniture Collections"

    def execute(self, context):

        collections = ['tables', 'Office_chairs', 'Dining_chairs', 'Arm_chairs', 'Bar_Stools', 'printer', 'Sofas', 'outdoor_bench', 'outdoor_chair', 'Storage', 'Sideboard', 'Bathroom', 'closets' , 'Assets']

        for collection_name in collections:
            if collection := bpy.data.collections.get(collection_name):
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

    @classmethod
    def poll(cls, context):
        # This operator is available only if the 'dxf' collection exists
        return 'dxf' in bpy.data.collections

    def execute(self, context):
        #function_1(self, context)
        print("Step 1 - prepare DXF")
        move_to_closets_collection()
        convert_splines_to_meshes_in_closets()
        create_faces_in_closets_meshes()
        move_objects_to_dxf()
        move_unwanted_objects("dxf")
        rename_objects_dxf("dxf")
        print("Step 1 done")        
        return {'FINISHED'}

class ESEC_OT_function_2(bpy.types.Operator):
    bl_idname = "esec.function_2"
    bl_label = "Step 2 - Prepare IFC"
    bl_description = "Prepares the IFC file. Move all objects to the 'ifc' collection, remove the 'IfcProject' collection and move the windows to the 'Windows' collection."

    @classmethod
    def poll(cls, context):
        # This operator is available only if the 'IfcProject/None' collection exists
        return 'IfcProject/None' in bpy.data.collections

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

    @classmethod
    def poll(cls, context):
        # This operator is available only if the 'dxf' collection exists
        return 'dxf' in bpy.data.collections

    def execute(self, context):
        print("Step 3 - create tables")
        #create_tabletops_from_dxf_collection()   
        create_tabletops_from_dxf_collection()
        print("Step 3 done")
        return {'FINISHED'}

class ESEC_OT_create_simple_chairs(bpy.types.Operator):
    bl_idname = "esec.create_simple_chairs"
    bl_label = "Step 4 - Create simple chairs"
    bl_description = "Create simple chairs (just circles) from the DXF collection."

    @classmethod
    def poll(cls, context):
        # This operator is available only if the 'dxf' collection exists
        return 'dxf' in bpy.data.collections

    def execute(self, context):
        print("Step 4 - create stools")
        create_stools_from_dxf_collection()
        print("Step 4 done")
        return {'FINISHED'}
    
class ESEC_OT_create_3d_chairs(bpy.types.Operator):
    bl_idname = "esec.create_3d_chairs"
    bl_label = "Step 4 - Create 3D Objects"
    bl_description = "Create chairs, stools and sofas from the DXF collection."

    @classmethod
    def poll(cls, context):
        # This operator is available only if the 'dxf' collection exists
        return 'dxf' in bpy.data.collections

    def execute(self, context):
        print("Create 3D Objects")
        create3D_Objects()
        print("Create 3D Objects done")
        print("Create Storage")
        create_squares_from_dxf_collection('Storage', bpy.context.scene.esec_addon_props.storage_height)    
        print("Create Storage done")
        print("Create sideboards")
        create_squares_from_dxf_collection('Sideboard', bpy.context.scene.esec_addon_props.sideboard_height)    
        print("Create sideboards done")
        return {'FINISHED'}

class ESEC_OT_function_5(bpy.types.Operator):
    bl_idname = "esec.function_5"
    bl_label = "Step 1-5 at once"
    bl_description = "Execute all steps at once"

    @classmethod
    def poll(cls, context):
        # This operator is available only if the 'dxf' collection exists
        # and there is any collection with 'ifc' in its name.
        return 'dxf' in bpy.data.collections and any('ifc' in coll.name.lower() for coll in bpy.data.collections)
 

    def execute(self, context):
        print("Rock'n'Roll")  

        move_to_closets_collection()
        convert_splines_to_meshes_in_closets()
        create_faces_in_closets_meshes()
        move_objects_to_dxf()
        move_unwanted_objects("dxf")
        rename_objects_dxf("dxf")
        rename_parking_floors()
        move_objects_to_ifc()
        remove_collection("IfcProject/None")
        move_objects_to_new_collection("IfcSlab/Floor", "ifc", "Floors")  
        move_objects_to_new_collection("IfcDoor/Door", "ifc", "Doors")
        move_objects_to_new_collection("IfcWindow/Window", "ifc", "Windows")
        move_objects_to_new_collection("IfcSlab/Parking", "ifc", "Parking")                
        create_tabletops_from_dxf_collection()
        create3D_Objects()
        create_squares_from_dxf_collection('Storage', bpy.context.scene.esec_addon_props.storage_height)    
        create_squares_from_dxf_collection('Sideboard', bpy.context.scene.esec_addon_props.sideboard_height) 
        assign_collection_materials()
        organize_collections() 
        print("all done")        
        return {'FINISHED'}

class ESEC_OT_close_holes_prepare(bpy.types.Operator):
    bl_idname = "esec.close_holes_prepare"
    bl_label = "Prepare"
    bl_description = "Creates an intersection of the floors and the walls. You have to move the Floors_Intersect object exactly on top of Floors_combined."

    @classmethod
    def poll(cls, context):
        # This operator is available only if the 'dxf' collection exists
        return 'Floors' in bpy.data.collections

    def execute(self, context):
        print("Prepare closing holes")
        close_holes_process_floors()
        close_holes_extrude_top_face()
        close_holes_apply_boolean_difference()
        close_holes_deactivate_rendering()
        print("done prepare closing holes")
        return {'FINISHED'}

class ESEC_OT_close_holes_finish(bpy.types.Operator):
    bl_idname = "esec.close_holes_finish"
    bl_label = "Finish"
    bl_description = "Move the Floors_Intersect object exactly on top of Floors_combined before clicking this button! "

    @classmethod
    def poll(cls, context):
        return 'floors_intersect' in bpy.data.collections

    def execute(self, context):
        print("Finish closing holes")
        close_holes_finish()   
        print("done closing holes")
        return {'FINISHED'}


class IMPORT_OT_dxf(bpy.types.Operator):
    bl_idname = "import_scene.dxf_esec"
    bl_label = "DXF"
    bl_description = "Import the DXF file exported from Archiologic. Official Blender DXF importer addon required."

    @classmethod
    def poll(cls, context):        
        try:
            return bpy.ops.import_scene.dxf.poll() is not None
        except AttributeError:
            return False

    def execute(self, context):
        global last_imported_dxf_directory, last_imported_dxf_filename
        bpy.ops.import_scene.dxf('INVOKE_DEFAULT')

        if 'dxf' not in bpy.data.collections:
            dxf_collection = bpy.data.collections.new('dxf')
            bpy.context.scene.collection.children.link(dxf_collection)

        return {'FINISHED'}

class IMPORT_OT_ifc(bpy.types.Operator):
    bl_idname = "import_ifc.bim_esec"
    bl_label = "IFC"
    bl_description = "Import the IFC file exported from Archiologic. Blenderbim Addon required. Download from https://blenderbim.org/download.html."
    
    @classmethod
    def poll(cls, context):        
        try:
            return bpy.ops.import_ifc.bim.poll() is not None
        except AttributeError:
            return False

    def execute(self, context):
        bpy.ops.import_ifc.bim('INVOKE_DEFAULT')
        return {'FINISHED'}

class EsecSaveAsOperator(bpy.types.Operator):
    bl_idname = "wm.save_as_esec"
    bl_label = "Blender"
    bl_description = "Save the current file with a new name"

    def execute(self, context):
        bpy.ops.wm.save_as_mainfile('INVOKE_DEFAULT')
        return {'FINISHED'}

class EsecExportObjOperator(bpy.types.Operator):
    bl_idname = "wm.export_obj_esec"
    bl_label = "OBJ"
    bl_description = "Export the current scene as an OBJ file"

    def execute(self, context):
        bpy.ops.wm.obj_export('INVOKE_DEFAULT')
        return {'FINISHED'}

class EsecExportKeyShotOperator(bpy.types.Operator):
    bl_idname = "esec.export_keyshot_esec"
    bl_label = "send to Keyshot"
    bl_description = "Export the current scene to Keyshot. Keyshot Plugin required. (https://www.keyshot.com/resources/downloads/plugins)"    

    @classmethod
    def poll(cls, context):
        # Check if the 'send_to_keyshot' operator is available
        try:
            return bpy.ops.keyshot.send_to_keyshot.poll() is not None
        except AttributeError:
            return False

    def execute(self, context):
        bpy.ops.keyshot.send_to_keyshot()
        return {'FINISHED'}

class EsecSubmenu(bpy.types.Menu):
    bl_label = "Tools"
    bl_idname = "OBJECT_MT_esec_submenu"

    def draw(self, context):
        layout = self.layout
        layout.operator(OBJECT_OT_DeleteIfcCollection.bl_idname, icon="CANCEL")
        layout.operator(OBJECT_OT_DeleteDxfCollection.bl_idname, icon="CANCEL")
        layout.operator(OBJECT_OT_DeleteFurnitureCollection.bl_idname, icon="CANCEL")
        layout.operator("esec.create_simple_chairs", icon="OUTLINER_OB_POINTCLOUD")
        layout.operator("esec.organize_collections", icon="GRAPH")        
        layout.operator("esec.select_parking", icon="LATTICE_DATA")
        layout.operator("esec.prep_parking", icon="REMOVE")

class ESEC_OT_select_parking(bpy.types.Operator):
    bl_idname = "esec.select_parking"
    bl_label = "Select Parking"
    bl_description = "Select all Parking lots"

    def execute(self, context):
        select_objects_from_collection("Parking", "Structure")  
        return {'FINISHED'}
    
class ESEC_OT_prep_parking(bpy.types.Operator):
    bl_idname = "esec.prep_parking"
    bl_label = "Reduce selected by 0.05"
    bl_description = "Reduce all selected objects by 0.05"

    def execute(self, context):
        reduce_scale()
        return {'FINISHED'}
    
class ESEC_OT_organize_collections(bpy.types.Operator):
    bl_idname = "esec.organize_collections"
    bl_label = "Organize Collections"
    bl_description = "Organize Collections"

    def execute(self, context):
        organize_collections()    
        return {'FINISHED'}


class ESEC_OT_create_storage(bpy.types.Operator):
    bl_idname = "esec.create_storage"
    bl_label = "Step 5 - Create Storage"
    bl_description = "Create storage from the DXF collection."

    @classmethod
    def poll(cls, context):
        # This operator is available only if the 'dxf' collection exists
        return 'dxf' in bpy.data.collections

    def execute(self, context):
        print("Create Storage")
        create_squares_from_dxf_collection('Storage', bpy.context.scene.esec_addon_props.storage_height)    
        print("Create Storage done")
        return {'FINISHED'}

class ESEC_OT_create_sideboard(bpy.types.Operator):
    bl_idname = "esec.create_sideboard"
    bl_label = "Step 6 - Create Sideboard"
    bl_description = "Create sideboard from the DXF collection."

    @classmethod
    def poll(cls, context):
        # This operator is available only if the 'dxf' collection exists
        return 'dxf' in bpy.data.collections

    def execute(self, context):
        print("Create sideboards")
        create_squares_from_dxf_collection('Sideboard', bpy.context.scene.esec_addon_props.sideboard_height)    
        print("Create sideboards done")
        return {'FINISHED'}


class ESEC_OT_assign_materials(bpy.types.Operator):
    bl_idname = "esec.assign_materials"
    bl_label = "Step 5 - Assign Materials"
    bl_description = "Assign materials to all objects."

    def execute(self, context):
        assign_collection_materials()
        return {'FINISHED'}         

class ESEC_OT_setup_renderer(bpy.types.Operator):
    bl_idname = "esec.setup_renderer"
    bl_label = "Setup"
    bl_description = "Setup the GPU cycles renderer. Create a hdri enviroment, set a transparent background and create a camera."

    def execute(self, context):
        setup_render()
        setup_hdri()
        set_transparent_background()
        setup_camera()
        return {'FINISHED'}

class ESEC_OT_render(bpy.types.Operator):
    bl_idname = "esec.render"
    bl_label = "Render"
    bl_description = "Renders the scene with the current settings. Dont forget to create the render enviroment first."

    def execute(self, context):
        render_scene(3400, 1923)
        return {'FINISHED'}

addon_keymaps = []

def register():  # sourcery skip: extract-method
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
    bpy.utils.register_class(ESEC_OT_organize_collections)
    bpy.utils.register_class(ESEC_OT_close_holes_prepare)
    bpy.utils.register_class(ESEC_OT_close_holes_finish)
    bpy.utils.register_class(ESEC_OT_select_parking)
    bpy.utils.register_class(ESEC_OT_prep_parking)


    wm = bpy.context.window_manager
    if kc := wm.keyconfigs.addon:
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
    bpy.utils.unregister_class(ESEC_OT_organize_collections)
    bpy.utils.unregister_class(ESEC_OT_close_holes_prepare)
    bpy.utils.unregister_class(ESEC_OT_close_holes_finish)
    bpy.utils.unregister_class(ESEC_OT_select_parking)
    bpy.utils.unregister_class(ESEC_OT_prep_parking)    

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()    
        
#######################################################################################

def detect_shape(ob):
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
        print("Created new collection: 'dxf_orphan'")

    allowed_keywords = ['desk', 'chair', 'sofa', 'table', 'storage', 'sideboard', 'bed', 'stool', 'printer', 'bench', 'toilet', 'urinal', 'sink', 'stair', 'ottoman', 'bank', 'parking']
    objects_to_move = [
        obj
        for obj in source_collection.objects
        if all(keyword not in obj.name.lower() for keyword in allowed_keywords)
    ]
    # Move objects
    for obj in objects_to_move:
        # Unlink from the source collection
        source_collection.objects.unlink(obj)
        # Link to the target collection
        orphan_collection.objects.link(obj)
        print(f"Moved object: {obj.name}")

    # Hide the orphan collection
    orphan_collection.hide_viewport = True
    print("Collection 'dxf_orphan' is now hidden.")

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
    objects_to_move = [
        obj.name
        for obj in source_collection.objects
        if any(keyword in obj.name for keyword in keywords)
    ]
    # Move objects
    for obj_name in objects_to_move:
        if obj := bpy.data.objects.get(obj_name):
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

    objects_to_move = [
        obj.name for obj in source_collection.objects if keyword in obj.name
    ]
    # Move objects
    for obj_name in objects_to_move:
        if obj := bpy.data.objects.get(obj_name):
            source_collection.objects.unlink(obj)
            target_collection.objects.link(obj)
            print(f"Moved object: {obj_name} to collection: {new_collection_name}") 


def remove_window_objects(collection_name):
    collection = bpy.data.collections.get(collection_name)
    if not collection:
        print(f"Collection '{collection_name}' not found.")
        return

    keywords = ['Window', 'window']
    objects_to_remove = [
        obj.name
        for obj in collection.objects
        if any(keyword in obj.name for keyword in keywords)
    ]
    # Remove objects
    for obj_name in objects_to_remove:
        if obj := bpy.data.objects.get(obj_name):
            bpy.data.objects.remove(obj, do_unlink=True)
            print(f"Removed object: {obj_name}")

def create_tabletop_square_from_object(obj,table_type):
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
    #bbox_dimensions = Vector((max(coord[i] for coord in local_coords) - min(coord[i] for coord in local_coords) for i in range(3)))

    # Calculate the dimensions directly from the transformed vertices
    width = max(v.x for v in local_coords) - min(v.x for v in local_coords)
    depth = max(v.y for v in local_coords) - min(v.y for v in local_coords)
    
    height = bpy.context.scene.esec_addon_props.table_height
    bpy.ops.mesh.primitive_cube_add(size=1)
    table_top = bpy.context.active_object
    print(f"Create Table for {obj.name}")
    table_top.name = obj.name + "_TableTop"

    # Set the scale of the table_top based on the directly calculated dimensions
    match table_type:
        case "desk":
            table_top.scale.x = width - bpy.context.scene.esec_addon_props.desk_table_margin
            table_top.scale.y = depth - bpy.context.scene.esec_addon_props.desk_table_margin
            table_top.scale.z = 0.025
        case "table":
            table_top.scale.x = width - bpy.context.scene.esec_addon_props.meeting_table_margin
            table_top.scale.y = depth - bpy.context.scene.esec_addon_props.meeting_table_margin
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
    print("create_tabletops_from_dxf_collection_2")
    if dxf_collection := bpy.data.collections.get("dxf"):
        for obj in dxf_collection.objects:
            obj_name = obj.name.lower()

            if "desk" in obj_name:
                create_table(obj,"desk")
            if "table" in obj_name:
                create_table(obj,"table")
            else:
                print("no desk or table in obj.name")
    else:
        print("Collection 'dxf' not found.")

def create_table(dxf_object,table_type):
    if dxf_object.type == 'CURVE':
        shape, num_points = detect_shape(dxf_object)
        if shape == 'square':
            #print(f"square: {obj.name} - Shape: {shape} - Points: {num_points}")
            create_tabletop_square_from_object(dxf_object,table_type)
        else:
            #print(f"circle: {obj.name} - Shape: {shape} - Points: {num_points}")    
            create_tabletop_rounds_from_object(dxf_object)    

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
    if dxf_collection := bpy.data.collections.get("dxf"):
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
    if dxf_collection := bpy.data.collections.get("dxf"):
        for obj in dxf_collection.objects:
            if needle in obj.name:
                create_squares_from_dxf_object(obj, needle, scaleZ)
    else:
        print("Collection 'dxf' not found.")

#################################################################################################################

def create_3Dobject_from_dxf_collection(needles, model_name, new_collection_name, ignoreKeyword=None):
    
    # Convert single string needle to list for compatibility
    if isinstance(needles, str):
        needles = [needles]

    if bpy.context.scene.use_high_poly_models:
        strDirectory = os.path.join(os.path.dirname(__file__), config.MODELS_HIGH_DIRECTORY)        
    else:
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

    if dxf_collection := bpy.data.collections.get("dxf"):
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
        if match := re.match(r"([^.]*)(\.\d+)?", obj.name):
            base_name = match[1]
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
    
    print(f"Created material: {material_name}")
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
    return (
        srgb_color_component / 12.92
        if srgb_color_component <= 0.04045
        else math.pow((srgb_color_component + 0.055) / 1.055, 2.4)
    )

def assign_collection_materials():
    # Remove all materials
    print("Remove all materials")
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
        "Doors": create_material("Doors", (0.65, 0.65, 0.65, 1), 0.8, 0.1),
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
    if collection := bpy.data.collections.get(collection_name):
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
    create_3Dobject_from_dxf_collection('Sink','sink', 'Bathroom')
    create_3Dobject_from_dxf_collection('Toilet','toilet', 'Bathroom')
    create_3Dobject_from_dxf_collection('Urinal','urinal', 'Bathroom')
    create_3Dobject_from_dxf_collection('BumperSmallOttoman','pouf', 'Sofas')
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




def move_to_closets_collection():
    # Ensure the 'closets' collection exists
    closets_collection = bpy.data.collections.get("closets")
    if not closets_collection:
        closets_collection = bpy.data.collections.new("closets")
        bpy.context.scene.collection.children.link(closets_collection)

    # Find spline objects with 'closets' in their name and move them to the 'closets' collection
    for obj in bpy.data.objects:
        if 'closets' in obj.name and obj.type == 'CURVE':
            # Unlink object from all its current collections
            for coll in obj.users_collection:
                coll.objects.unlink(obj)
            # Link object to the 'closets' collection
            closets_collection.objects.link(obj)

def convert_splines_to_meshes_in_closets():
    # Get the 'closets' collection
    closets_collection = bpy.data.collections.get("closets")
    if closets_collection is None:
        print("No 'closets' collection found.")
        return

    # Deselect all objects
    bpy.ops.object.select_all(action='DESELECT')

    # Loop through objects in the 'closets' collection
    for obj in closets_collection.objects:
        if obj.type == 'CURVE':
            # Select the object
            obj.select_set(True)

            # Set the active object (required for the conversion operation)
            bpy.context.view_layer.objects.active = obj

            # Convert the spline object to a mesh
            bpy.ops.object.convert(target='MESH')

            # Deselect the object
            obj.select_set(False)
            
            
def create_faces_in_closets_meshes():
    # Get the 'closets' collection
    closets_collection = bpy.data.collections.get("closets")
    if closets_collection is None:
        print("No 'closets' collection found.")
        return

    # Save the original context
    original_area = bpy.context.area.type
    bpy.context.area.type = 'VIEW_3D'

    # Deselect all objects
    bpy.ops.object.select_all(action='DESELECT')

    # Loop through objects in the 'closets' collection
    for obj in closets_collection.objects:
        if obj.type == 'MESH':
            # Select the object
            obj.select_set(True)

            # Set the active object (required for the edit mode operations)
            bpy.context.view_layer.objects.active = obj

            # Switch to edit mode
            bpy.ops.object.mode_set(mode='EDIT')

            # Select all vertices
            bpy.ops.mesh.select_all(action='SELECT')

            # Create a new edge/face from vertices
            bpy.ops.mesh.edge_face_add()

            # Extrude on Z axis by 1.8 units
            bpy.ops.transform.translate(value=(0, 0, 0))

            # Switch back to object mode
            bpy.ops.object.mode_set(mode='OBJECT')

            # Deselect the object
            obj.select_set(False)

    # Restore the original context
    bpy.context.area.type = original_area


def organize_collections():

    # Remove any empty collections
    for collection in list(bpy.data.collections):  # Make a copy of the list because we're modifying it
        if len(collection.objects) == 0 and len(collection.children) == 0:
            bpy.data.collections.remove(collection)

    # Create 'Structure', 'DXF', and 'Assets' collections if they don't exist
    structure_collection = bpy.data.collections.get('Structure')
    if not structure_collection:
        structure_collection = bpy.data.collections.new('Structure')
        bpy.context.scene.collection.children.link(structure_collection)

    dxf_collection = bpy.data.collections.get('DXF')
    if not dxf_collection:
        dxf_collection = bpy.data.collections.new('DXF')
        bpy.context.scene.collection.children.link(dxf_collection)

    assets_collection = bpy.data.collections.get('Assets')
    if not assets_collection:
        assets_collection = bpy.data.collections.new('Assets')
        bpy.context.scene.collection.children.link(assets_collection)

    # List of collections to move to 'Structure'
    structure_collections = ['ifc', 'Floors', 'Doors', 'Windows', 'floors_intersect', 'Parking']

    # List of collections to move to 'DXF'
    dxf_collections = ['dxf', 'dxf_orphan']

    # List of collections to move to 'Assets'
    asset_collections = ['tables', 'Office_chairs', 'Dining_chairs', 'Arm_chairs', 'Bar_Stools', 'printer', 'Sofas', 'outdoor_bench', 'outdoor_chair', 'Storage', 'Sideboard', 'Bathroom', 'closets' ]

    # Move collections to 'Structure'
    for col_name in structure_collections:
        if collection := bpy.data.collections.get(col_name):
            if collection.name in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.unlink(collection)
            if collection.name not in structure_collection.children:
                structure_collection.children.link(collection)

    # Move collections to 'DXF'
    for col_name in dxf_collections:
        if collection := bpy.data.collections.get(col_name):
            if collection.name in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.unlink(collection)
            if collection.name not in dxf_collection.children:
                dxf_collection.children.link(collection)

    # Move collections to 'Assets'
    for col_name in asset_collections:
        if collection := bpy.data.collections.get(col_name):
            if collection.name in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.unlink(collection)
            if collection.name not in assets_collection:
                assets_collection.children.link(collection)



###

def close_holes_process_floors():
    # Create a new collection
    new_collection = bpy.data.collections.new("floors_intersect")
    bpy.context.scene.collection.children.link(new_collection)
    
    # Get reference to the existing 'Floors' collection
    floors_collection = bpy.data.collections.get("Floors")
    
    # Check if 'Floors' collection exists
    if floors_collection is None:
        print("Collection 'Floors' not found.")
        return

    # Copy each object from 'Floors' collection to the new collection
    for obj in floors_collection.objects:
        new_obj = obj.copy()
        new_obj.data = obj.data.copy()
        new_collection.objects.link(new_obj)
        
    # Combine all objects in the new collection into one mesh
    bpy.context.view_layer.active_layer_collection = bpy.context.view_layer.layer_collection.children['floors_intersect']
    bpy.ops.object.select_all(action='DESELECT')

    for obj in new_collection.objects:
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj

    bpy.ops.object.join()
    
    # Set the name of the joined object
    bpy.context.object.name = "Floors_combined"

    # Set the origin of 'floors_intersect' object to geometry
    #bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS', center='BOUNDS')

    # Create a new plane with the same settings as floors_intersect
    bpy.ops.mesh.primitive_plane_add(size=1)
    plane = bpy.context.object
    plane.name = "Floors_Intersect"

    # Set the plane's settings to match floors_combined
    floors_intersect = bpy.data.objects.get("Floors_combined")
    if floors_intersect is not None:
        plane.location = floors_intersect.location
        plane.scale = floors_intersect.scale
        plane.dimensions = floors_intersect.dimensions
    else:
        print("Object 'Floors_combined' not found.")

#process_floors()

def close_holes_extrude_top_face():
    # Get the object named "Plan" from the "floors_intersect" collection
    floors_intersect_collection = bpy.data.collections.get("floors_intersect")
    if floors_intersect_collection is None:
        print("Collection 'floors_intersect' not found.")
        return

    plan_object = floors_intersect_collection.objects.get("Floors_Intersect")
    if plan_object is None:
        print("Object 'Plane' not found.")
        return
    
    # Set the "Floors_Intersect" object as the active object
    bpy.context.view_layer.objects.active = plan_object
    plan_object.select_set(True)
    
    # Switch to edit mode
    bpy.ops.object.mode_set(mode='EDIT')

    # Deselect all
    bpy.ops.mesh.select_all(action='DESELECT')

    # Switch to face select mode
    bpy.context.tool_settings.mesh_select_mode = (False, False, True)
    
    # Select all faces
    bpy.ops.mesh.select_all(action='SELECT')

    # Extrude the faces on the Z axis by 0.197681 m
    bpy.ops.mesh.extrude_region_move(
        TRANSFORM_OT_translate={"value": (0, 0, 0.19)}
    )
    
    # Switch back to object mode
    bpy.ops.object.mode_set(mode='OBJECT')

def close_holes_apply_boolean_difference():
    # Get the collection
    floors_intersect_collection = bpy.data.collections.get("floors_intersect")
    if floors_intersect_collection is None:
        print("Collection 'floors_intersect' not found.")
        return

    # Get the Plane object
    plane_object = floors_intersect_collection.objects.get("Floors_Intersect")
    if plane_object is None:
        print("Object 'Floors_Intersect' not found.")
        return

    # Get the floors_intersect object
    floors_combined_object = floors_intersect_collection.objects.get("Floors_combined")
    if floors_combined_object is None:
        print("Object 'Floors_combined' not found.")
        return

    # Add a boolean modifier to the Plane object
    bool_mod = plane_object.modifiers.new(name="BooleanMod", type='BOOLEAN')
    bool_mod.operation = 'DIFFERENCE'
    bool_mod.object = floors_combined_object
    bool_mod.solver = 'EXACT'
    bool_mod.use_self = True

    # Apply the modifier
    bpy.context.view_layer.objects.active = plane_object
    #bpy.ops.object.modifier_apply(modifier=bool_mod.name)

def close_holes_deactivate_rendering():
    # List of collections to deactivate for rendering
    collections_to_deactivate = ["ifc", "Floors", "Doors", "Windows"]
    
    # Deactivate each collection for rendering
    for collection_name in collections_to_deactivate:
        collection = bpy.data.collections.get(collection_name)
        if collection is not None:
            collection.hide_viewport = True
        else:
            print(f"Collection '{collection_name}' not found.")

    # Deactivate boolean modifiers for viewport rendering in 'Floors_Intersect'
    object_name = "Floors_Intersect"
    obj = bpy.data.objects.get(object_name)
    if obj is not None:
        for mod in obj.modifiers:
            if mod.type == 'BOOLEAN':
                mod.show_viewport = False
    else:
        print(f"Object '{object_name}' not found.")


def close_holes_finish():
    # List of collections to activate for rendering
    collections_to_activate = ["ifc", "Floors", "Doors", "Windows"]
    
    # Activate each collection for rendering
    for collection_name in collections_to_activate:
        collection = bpy.data.collections.get(collection_name)
        if collection is not None:
            collection.hide_viewport = False
        else:
            print(f"Collection '{collection_name}' not found.")

    # Object to hide in the viewport
    object_name = "Floors_combined"
    obj = bpy.data.objects.get(object_name)
    if obj is not None:
        obj.hide_viewport = True
    else:
        print(f"Object '{object_name}' not found.")

    # Activate and apply boolean modifiers for viewport rendering in 'Floors_Intersect'
    object_name = "Floors_Intersect"
    obj = bpy.data.objects.get(object_name)
    if obj is not None:
        bpy.context.view_layer.objects.active = obj
        for mod in obj.modifiers:
            if mod.type == 'BOOLEAN':
                mod.show_viewport = True
                bpy.ops.object.modifier_apply({"object": obj}, modifier=mod.name)
    else:
        print(f"Object '{object_name}' not found.")

    # Assign material "floors" to 'Floors_Intersect'
    floors_material = bpy.data.materials.get("Floors")
    if floors_material is not None:
        if obj is not None:
            if len(obj.data.materials) > 0:
                # assign to material slot 0
                obj.data.materials[0] = floors_material
            else:
                # no slots
                obj.data.materials.append(floors_material)
    else:
        print("Material 'Floors' not found.")

##############################
# parking lots
# rename parking lots floors
##############################

def collect_spaces(collection, space_objects):
    for obj in collection.objects:
        if 'IfcSlab' in obj.name:
            space_objects.append(obj)

    for child_collection in collection.children:
        collect_spaces(child_collection, space_objects)

def collect_text_objects(collection, text_objects):
    for obj in collection.objects:
        if obj.type == 'FONT':
            text_objects.append(obj)

    for child_collection in collection.children:
        collect_text_objects(child_collection, text_objects)

def sort_spaces_numerically(space_object):
    number = re.search(r'\d+', space_object.name)
    return int(number.group(0)) if number else 0

def get_bounding_box(obj):
    bbox_min = [min(obj.bound_box[i][j] for i in range(8)) for j in range(3)]
    bbox_max = [max(obj.bound_box[i][j] for i in range(8)) for j in range(3)]
    return bbox_min, bbox_max

def is_text_inside_space(text_obj, space_obj):
    text_pos = text_obj.matrix_world.translation
    bbox_corners = [mathutils.Vector(corner) for corner in space_obj.bound_box]
    bbox_world_corners = [space_obj.matrix_world @ corner for corner in bbox_corners]

    bbox_min = [min(corner[i] for corner in bbox_world_corners) for i in range(3)]
    bbox_max = [max(corner[i] for corner in bbox_world_corners) for i in range(3)]

    return bbox_min[0] <= text_pos[0] <= bbox_max[0] and bbox_min[1] <= text_pos[1] <= bbox_max[1]


def rename_parking_floors():
    space_replacements = {}
    ifc_project_none = bpy.data.collections.get('IfcProject/None')

    if ifc_project_none is None:
        print("IfcProject/None collection not found.")
        return

    space_objects = []
    collect_spaces(ifc_project_none, space_objects)

    text_objects = []
    collect_text_objects(bpy.context.scene.collection, text_objects)

    sorted_space_objects = sorted(space_objects, key=sort_spaces_numerically)
    
    keywords = ['Parking']
    #keywords = bpy.context.scene.esec_strings_to_keep.split(', ')

    total_texts_found = 0

    for space in sorted_space_objects:
        bbox_min, bbox_max = get_bounding_box(space)
        x_length = bbox_max[0] - bbox_min[0]
        y_length = bbox_max[1] - bbox_min[1]
        size = x_length * y_length

        #space_output = f"{space.name} - X length: {x_length:.2f}, Y length: {y_length:.2f}, Size: {size:.2f}"
        space_output = f"{space.name} - "

        texts_found = 0
        matching_text = ""

        for text_obj in text_objects:
            cleaned_text = re.sub(r'[^A-Za-z0-9\s.]', '', text_obj.data.body.replace('\n', ' '))
            cleaned_text = re.sub(r'\s{2,}', ' ', cleaned_text)  # Remove multiple consecutive whitespaces

            if any(keyword in cleaned_text for keyword in keywords) and is_text_inside_space(text_obj, space):
                texts_found += 1
                matching_text = cleaned_text

        if texts_found == 1:
            space_output += f"{matching_text}"
            print(space_output)
            total_texts_found += 1
            space_replacements[space.name] = matching_text

    print(f"Total number of IFC spaces: {len(sorted_space_objects)}")
    print(f"Total number of texts found in spaces: {total_texts_found}")

    replace_space_names_in_ifc(space_replacements)
          
            
    return space_replacements

def replace_space_names_in_ifc(space_replacements):
    
    #space_replacements
    for space_name, new_space_name in space_replacements.items():
        space_name_without_prefix = space_name.replace("IfcSlab/", "")
        print(f"found {space_name_without_prefix} - {new_space_name}")
        
        #ifc
        for obj in bpy.data.objects:
            # Make sure the object is an IfcSpace                    
            old_name = obj.name.split('/')[-1]  # Get the last part of the name after '/'
            # Check if the name follows the expected format
            if old_name.startswith('Floor_'):                                        
                if old_name == space_name_without_prefix :            
                    print("rename " + old_name + " to " + new_space_name)
                    obj.name = obj.name.replace(old_name, new_space_name)    
   

def select_objects_from_collection(collection_name, parent_name=None):
    """Select all objects from a specified collection. 
    Optionally, specify a parent collection."""
    
    # If parent_name is given, find the parent collection
    if parent_name:
        parent_col = bpy.data.collections.get(parent_name)
        if not parent_col:
            print(f"No collection found with the name {parent_name}.")
            return
        # Get the nested collection from the parent collection
        target_col = parent_col.children.get(collection_name)
    else:
        # Otherwise, just get the collection by name from bpy.data.collections
        target_col = bpy.data.collections.get(collection_name)
    
    # If the target collection was found, select its objects
    if target_col:
        for obj in target_col.objects:
            obj.select_set(True)
    else:
        print(f"No collection found with the name {collection_name}.")




def reduce_scale():
    # Iterate through selected objects in the scene
    for obj in bpy.context.selected_objects:
        # Check if the object is of type 'MESH'
        if obj.type == 'MESH':
            # Reduce the x and y scale by 0.05
            obj.scale[0] *= (1 - 0.05)
            obj.scale[1] *= (1 - 0.05)
         