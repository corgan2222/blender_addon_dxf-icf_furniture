bl_info = {
    "name": "ESEC ICF-TI Helper",
    "author": "stefan.knaak@e-shelter.io",
    "version": (1, 3),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > ESEC Tab",
    "description": "Rename IFC Space based on DXF roomnames",
    "warning": "",
    "doc_url": "https://github.com/corgan2222/blender_addon_dxf-icf_furniture",
    "category": "3D View",
}

import bpy
import re
import mathutils
import os
import ifcopenshell
import blenderbim.tool as tool
from blenderbim.bim.ifc import IfcStore

def rename_spaces_by_longname():
    # Define the longnames to look for and their corresponding new names
    longname_dict = {
        'staircase': 'Staircase',
        'elevator': 'Elevator',
        'shaft': 'Shaft',
    }

    file = IfcStore.get_file()
    elements = file.by_type('IfcSpace')

    for e in elements:
        longname = e.LongName
        # Check if the space's LongName is one of the ones we're looking for
        if longname and longname.lower() in longname_dict:
                                
            # Extract the number part of the name
            number_part = e.Name.split('_')[-1]
            # Create the new name with the new name from the dictionary and the number part
            new_name = '{}_{}'.format(longname_dict[longname.lower()], number_part)
            # Assign the new name to the space
            old_space_name = e.Name
            
            for obj in bpy.data.objects:
                    # Make sure the object is an IfcSpace                    
                    old_name = obj.name.split('/')[-1]  # Get the last part of the name after '/'
                    # Check if the name follows the expected format
                    if old_name.startswith('Space_'):                                        
                        if old_name == old_space_name :            
                            print("rename " + old_name + " to " + new_name)
                            obj.name = obj.name.replace(old_name, new_name)
                                                                

def rename_spaces():
    for obj in bpy.data.objects:
        # Make sure the object is an IfcSpace
        if "IfcSpace" in obj.name:
            # Get the existing name
            old_name = obj.name.split('/')[-1]  # Get the last part of the name after '/'
            # Check if the name follows the expected format
            if old_name.startswith('Space_'):
                # Extract the number part of the name
                number_part = old_name.split('_')[1]
                # Create the new name with leading zeros
                new_name = 'Space_{:03}'.format(int(number_part))
                # Assign the new name to the space
                print("rename " + old_name + " to " + new_name)
                obj.name = obj.name.replace(old_name, new_name)
  

def move_objects_to_new_collection():
    # Create a new collection
    new_collection = bpy.data.collections.new('dxf')
    
    # Link the new collection to the current scene
    bpy.context.scene.collection.children.link(new_collection)
    
    # Get a list of all objects in the current scene
    all_objects = list(bpy.context.scene.collection.objects)
    
    # Move all objects to the new collection
    for obj in all_objects:
        # Check if the object is a collection
        if obj.type == 'EMPTY' and obj.instance_collection:
            continue
        # Unlink the object from its current collection
        bpy.context.scene.collection.objects.unlink(obj)
        # Link the object to the new collection
        new_collection.objects.link(obj)



def delete_unwanted_text_objects_from_dxf():
    # Define the list of strings to look for
    strings_to_keep = ['North', 'South', 'West', 'East', 'Central']

    # Get the 'dxf' collection
    dxf_collection = bpy.data.collections.get('dxf')

    # If the collection doesn't exist, there's nothing to do
    if not dxf_collection:
        print("'dxf' collection does not exist.")
        return

    # Deselect all objects
    bpy.ops.object.select_all(action='DESELECT')

    # Loop over all objects in the 'dxf' collection
    for obj in dxf_collection.objects:
        # Check if the object is a text object
        if obj.type == 'FONT':
            # If the object's text does not contain any of the specified strings, select it
            if not any(s in obj.data.body for s in strings_to_keep):
                obj.select_set(True)

    # Delete all selected objects at once
    bpy.ops.object.delete()
    
#######################################################

def collect_spaces(collection, space_objects):
    for obj in collection.objects:
        if 'IfcSpace' in obj.name:
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


def print_spaces_and_texts():
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
    
    keywords = ['North', 'South', 'West', 'East', 'Central']

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
        
    if not bpy.context.scene.esec_dry_run:
        print("not checked")
        replace_space_names_in_ifc(space_replacements)
    else:        
        print("checked")
            #replace_space_names_in_ifc(space_replacements)    
    
    
    
    return space_replacements

def replace_space_names_in_ifc(space_replacements):
    
    #space_replacements
    for space_name, new_space_name in space_replacements.items():
        space_name_without_prefix = space_name.replace("IfcSpace/", "")
        #print(f"found {space_name_without_prefix} - {new_space_name}")
        
        #ifc
        for obj in bpy.data.objects:
            # Make sure the object is an IfcSpace                    
            old_name = obj.name.split('/')[-1]  # Get the last part of the name after '/'
            # Check if the name follows the expected format
            if old_name.startswith('Space_'):                                        
                if old_name == space_name_without_prefix :            
                    print("rename " + old_name + " to " + new_space_name)
                    obj.name = obj.name.replace(old_name, new_space_name)    
    

#########################################################
bpy.types.Scene.esec_dry_run = bpy.props.BoolProperty(
    name="Dry Run (check system console)",
    description="Enable Dry Run (check system console)",
    default = True
)


class ESEC_OT_ImportIFC(bpy.types.Operator):
    bl_idname = "esec.import_ifc"
    bl_label = "Import IFC"
    bl_description = "Import IFC file"

    def execute(self, context):
        bpy.ops.import_ifc.bim('INVOKE_DEFAULT')
        return {'FINISHED'}

class ESEC_OT_ImportDXF(bpy.types.Operator):
    bl_idname = "esec.import_dxf"
    bl_label = "Import DXF"
    bl_description = "Import DXF file"

    def execute(self, context):
        bpy.ops.import_scene.dxf('INVOKE_DEFAULT')
        return {'FINISHED'}

class ESEC_OT_RenameSpacesByLongname(bpy.types.Operator):
    bl_idname = "esec.rename_spaces_by_longname"
    bl_label = "Prepare IFC"
    bl_description = "Rename spaces by long name"

    def execute(self, context):
        rename_spaces_by_longname()
        rename_spaces()
        return {'FINISHED'}

class ESEC_OT_PrepareDXF(bpy.types.Operator):
    bl_idname = "esec.prepare_dxf"
    bl_label = "Prepare DXF"
    bl_description = "Prepare DXF file"

    def execute(self, context):
        move_objects_to_new_collection()
        delete_unwanted_text_objects_from_dxf()
        return {'FINISHED'}

class ESEC_OT_RenameSpaces(bpy.types.Operator):
    bl_idname = "esec.rename_spaces"
    bl_label = "Rename Spaces by DXF Text"
    bl_description = "Rename spaces based on text objects"

    def execute(self, context):
        print_spaces_and_texts()
        return {'FINISHED'}


class ESEC_PT_MainPanel(bpy.types.Panel):
    bl_label = "ESEC IFC-TI Helper v"+ str(bl_info['version'])
    bl_idname = "ESEC_PT_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ESEC IFC Tab'

    def draw(self, context):
        layout = self.layout

        # Add your buttons here
        layout.operator("esec.import_ifc", icon="IMPORT")
        layout.operator("esec.rename_spaces_by_longname", icon="FILE_3D")
        layout.separator()
        layout.operator("esec.import_dxf", icon="IMPORT")        
        layout.operator("esec.prepare_dxf", icon="FILE_VOLUME")
        layout.separator()
        layout.label(text="Clean up and prepare the DXF ")      
        layout.label(text="Move the DXF over the IFC")      
        layout.label(text="Move all room names inside spaces")              
        layout.label(text="Move only the DXF!!")      
        layout.separator()
        layout.operator("esec.rename_spaces", icon="SNAP_VERTEX")
        layout.prop(context.scene, "esec_dry_run")
        layout.separator()
        layout.label(text="Export with IFC Save as")      


def register():
    bpy.utils.register_class(ESEC_OT_ImportIFC)
    bpy.utils.register_class(ESEC_OT_ImportDXF)
    bpy.utils.register_class(ESEC_OT_RenameSpacesByLongname)
    bpy.utils.register_class(ESEC_OT_PrepareDXF)
    bpy.utils.register_class(ESEC_OT_RenameSpaces)
    bpy.utils.register_class(ESEC_PT_MainPanel)


 

def unregister():
    bpy.utils.unregister_class(ESEC_PT_MainPanel)
    bpy.utils.unregister_class(ESEC_OT_RenameSpaces)
    bpy.utils.unregister_class(ESEC_OT_PrepareDXF)
    bpy.utils.unregister_class(ESEC_OT_RenameSpacesByLongname)
    bpy.utils.unregister_class(ESEC_OT_ImportDXF)
    bpy.utils.unregister_class(ESEC_OT_ImportIFC)

    

if __name__ == "__main__":
    register()




# def delete_specific_spaces():
#     to_be_deleted = []
#     collections_to_be_deleted = []
    
#     keywords = ['Shaft']

#     def search_collection(collection):
#         # Go through all objects in the collection
#         for obj in collection.objects:
#             # Check if the object is an IfcSpace and contains any of the specified strings in its name
#             if any(keyword in obj.name for keyword in keywords):
#                 print(obj.name)                
#                 to_be_deleted.append(obj)
#                 if collection not in collections_to_be_deleted:
#                     collections_to_be_deleted.append(collection)
                
#         # Recursively search in nested collections
#         for subcollection in collection.children:
#             search_collection(subcollection)

#     # Make sure the collection exists
#     if "IfcProject/None" in bpy.data.collections:
#         search_collection(bpy.data.collections["IfcProject/None"])

#     # Go through all objects to be deleted and delete them
#     for obj in to_be_deleted:
#         bpy.data.objects.remove(obj)

#     # Go through all collections to be deleted and delete them
#     for collection in collections_to_be_deleted:
#         bpy.data.collections.remove(collection)