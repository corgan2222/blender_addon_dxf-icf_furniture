bl_info = {
    "name": "ESEC ICF-TI Helper",
    "author": "stefan.knaak@e-shelter.io",
    "version": (2, 1),
    "blender": (5, 1, 0),
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
from bpy_extras.io_utils import ImportHelper


def _resolve_ifc_file():
    """Resolve the loaded IFC file via whichever BIM addon is active (Bonsai or BlenderBIM).
    Walks sys.modules instead of importing bonsai at addon-load time, which is fragile
    across addon load order and the bonsai/blenderbim rename. Returns None if no IFC loaded.
    """
    import sys
    import types
    for key, mod in sys.modules.items():
        if isinstance(mod, types.ModuleType) and key.endswith('.bim.ifc') and hasattr(mod, 'IfcStore'):
            return mod.IfcStore.get_file()
    return None


def rename_spaces_by_longname():
    print("rename_spaces_by_longname")

    file = _resolve_ifc_file()
    if not file:
        print("[rename_spaces_by_longname] No IFC file loaded, skipping.")
        return

    counters = {}

    for obj in bpy.data.objects:
        if "IfcSpace" not in obj.name:
            continue

        bim_props = getattr(obj, 'BIMObjectProperties', None)
        ifc_id = getattr(bim_props, 'ifc_definition_id', 0)
        if not ifc_id:
            continue

        element = file.by_id(ifc_id)
        if not element:
            continue

        longname = getattr(element, 'LongName', None)
        print(f"[longname] {longname} ")
        if not longname:
            continue

        # Derive the object name straight from the IFC LongName, so new room
        # types work without maintaining a lookup table. Strip anything that is
        # not alphanumeric to keep the name a clean single token.
        type_name = re.sub(r'[^A-Za-z0-9]', '', longname)
        if not type_name:
            continue

        counters[type_name] = counters.get(type_name, 0) + 1
        new_name = '{}_{:03}'.format(type_name, counters[type_name])
        print("rename " + obj.name + " to " + new_name)
        # Persist into the IFC entity, otherwise Bonsai resyncs the object
        # name back to the original IFC Name on the next refresh.
        element.Name = new_name
        obj.name = new_name


# Export order for Thing-IT. Thing-IT shows spaces in IFC file order (the
# RelatedObjects order of the storey aggregation), not alphabetically, so we
# sort that list here. Front types first, then any unlisted type, then back
# types. Compared lowercased against LongName.
SPACE_ORDER_FRONT = [
    'meetingroom',
    'privateoffice',
    'enclosedworkspace',
    'openworkspace',
    'focusroom',
]

SPACE_ORDER_BACK = [
    'generic',
    'restroom',
    'operationalroom',
    'cafe',
    'foyer',
    'printstation',
    'storage',
    'corridor',
    'elevator',
    'staircase',
]


def _space_sort_key(space, id_to_obj):
    type_key = (getattr(space, 'LongName', None) or '').strip().lower()

    if type_key in SPACE_ORDER_FRONT:
        group, rank = 0, SPACE_ORDER_FRONT.index(type_key)
    elif type_key in SPACE_ORDER_BACK:
        group, rank = 2, SPACE_ORDER_BACK.index(type_key)
    else:
        group, rank = 1, 0

    obj = id_to_obj.get(space.id())
    name = obj.name if obj else (space.Name or '')
    match = re.search(r'(\d+)', name)
    number = int(match.group(1)) if match else 0
    return (group, rank, type_key, number, name)


def sort_spaces_for_export():
    print("sort_spaces_for_export")
    file = _resolve_ifc_file()
    if not file:
        print("[sort_spaces_for_export] No IFC file loaded, skipping.")
        return

    id_to_obj = {}
    for obj in bpy.data.objects:
        bim_props = getattr(obj, 'BIMObjectProperties', None)
        ifc_id = getattr(bim_props, 'ifc_definition_id', 0)
        if ifc_id:
            id_to_obj[ifc_id] = obj

    # Bonsai exports one IfcRelAggregates per space, so a storey owns many
    # single-space relationships and Thing-IT renders them in that order.
    # Merge each storey's space aggregations into one relationship whose
    # RelatedObjects list is sorted, and drop the now redundant relationships.
    from collections import defaultdict
    by_storey = defaultdict(list)
    for rel in file.by_type('IfcRelAggregates'):
        relating = rel.RelatingObject
        if not relating or not relating.is_a('IfcBuildingStorey'):
            continue
        related = rel.RelatedObjects
        if related and all(o.is_a('IfcSpace') for o in related):
            by_storey[relating.id()].append(rel)

    for storey_id, rels in by_storey.items():
        spaces = []
        for rel in rels:
            spaces.extend(rel.RelatedObjects)
        if len(spaces) < 2:
            continue

        spaces.sort(key=lambda s: _space_sort_key(s, id_to_obj))

        keep = rels[0]
        keep.RelatedObjects = tuple(spaces)
        for rel in rels[1:]:
            file.remove(rel)

        print("[sort_spaces_for_export] merged {} rels into 1, {} spaces under storey #{}".format(
            len(rels), len(spaces), storey_id))


DXF_IMPORT_COLLECTION = 'dxf_import'


def find_layer_collection(layer_collection, name):
    if layer_collection.collection.name == name:
        return layer_collection
    for child in layer_collection.children:
        found = find_layer_collection(child, name)
        if found:
            return found
    return None


def get_or_create_dxf_import_collection():
    col = bpy.data.collections.get(DXF_IMPORT_COLLECTION)
    if not col:
        col = bpy.data.collections.new(DXF_IMPORT_COLLECTION)
        bpy.context.scene.collection.children.link(col)
    return col


def set_active_collection(col):
    layer_col = find_layer_collection(bpy.context.view_layer.layer_collection, col.name)
    if layer_col:
        bpy.context.view_layer.active_layer_collection = layer_col


def move_objects_to_new_collection():
    # Create or get the 'dxf' collection
    dxf_collection = bpy.data.collections.get('dxf')
    if not dxf_collection:
        dxf_collection = bpy.data.collections.new('dxf')
        bpy.context.scene.collection.children.link(dxf_collection)

    # Create subcollections 'dxf_text' and 'dxf_building'
    dxf_text = bpy.data.collections.get('dxf_text')
    if not dxf_text:
        dxf_text = bpy.data.collections.new('dxf_text')
        dxf_collection.children.link(dxf_text)

    dxf_building = bpy.data.collections.get('dxf_building')
    if not dxf_building:
        dxf_building = bpy.data.collections.new('dxf_building')
        dxf_collection.children.link(dxf_building)

    # Read the imported objects from the dedicated import collection.
    # Fall back to the scene root for files imported the old way.
    source = bpy.data.collections.get(DXF_IMPORT_COLLECTION) or bpy.context.scene.collection
    all_objects = list(source.objects)

    for obj in all_objects:
        # Skip collection instances
        if obj.type == 'EMPTY' and obj.instance_collection:
            continue

        # Unlink from the source collection
        source.objects.unlink(obj)

        # Link to appropriate subcollection
        if obj.type == 'FONT':
            dxf_text.objects.link(obj)
        else:
            dxf_building.objects.link(obj)

def delete_unwanted_text_objects_from_dxf():
    # Define the list of strings to look for
    strings_to_keep = bpy.context.scene.esec_strings_to_keep.split(', ')
    print(strings_to_keep)

    # Get the 'dxf_text' collection
    dxf_text_collection = bpy.data.collections.get('dxf_text')

    # If the collection doesn't exist, there's nothing to do
    if not dxf_text_collection:
        print("'dxf_text' collection does not exist.")
        return

    # Collect text objects whose body contains none of the strings to keep.
    # bpy.data.objects.remove() is context-independent; bpy.ops.object.delete()
    # needs a correct operator context override that we cannot guarantee here.
    to_delete = [
        obj for obj in dxf_text_collection.objects
        if obj.type == 'FONT' and not any(s in obj.data.body for s in strings_to_keep)
    ]
    for obj in to_delete:
        print("delete " + obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)

    
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

def space_world_center(obj):
    local_center = sum((mathutils.Vector(c) for c in obj.bound_box), mathutils.Vector()) / 8.0
    return obj.matrix_world @ local_center

def is_text_inside_space(text_obj, space_obj):
    text_pos = text_obj.matrix_world.translation
    bbox_corners = [mathutils.Vector(corner) for corner in space_obj.bound_box]
    bbox_world_corners = [space_obj.matrix_world @ corner for corner in bbox_corners]

    bbox_min = [min(corner[i] for corner in bbox_world_corners) for i in range(3)]
    bbox_max = [max(corner[i] for corner in bbox_world_corners) for i in range(3)]

    return bbox_min[0] <= text_pos[0] <= bbox_max[0] and bbox_min[1] <= text_pos[1] <= bbox_max[1]


def print_spaces_and_texts():
    space_replacements = {}

    # Collect IfcSpace objects anywhere in the scene. Bonsai changed the
    # collection layout (no fixed 'IfcProject/None'); collect_spaces filters
    # on 'IfcSpace' in the object name, so the source name no longer matters.
    space_objects = []
    collect_spaces(bpy.context.scene.collection, space_objects)

    if not space_objects:
        print("No IfcSpace objects found in the scene.")
        return

    text_objects = []
    collect_text_objects(bpy.context.scene.collection, text_objects)

    sorted_space_objects = sorted(space_objects, key=sort_spaces_numerically)
    
    #keywords = ['North', 'South', 'West', 'East', 'Central']
    keywords = bpy.context.scene.esec_strings_to_keep.split(', ')

    total_texts_found = 0

    for space in sorted_space_objects:
        space_center = space_world_center(space)

        # Collect every matching text inside the space, keep the one nearest
        # the space center. Rooms often hold several labels (number, area,
        # name); requiring exactly one missed most of them.
        candidates = []
        for text_obj in text_objects:
            cleaned_text = re.sub(r'[^A-Za-z0-9\s.]', '', text_obj.data.body.replace('\n', ' '))
            cleaned_text = re.sub(r'\s{2,}', ' ', cleaned_text).strip()

            if any(keyword in cleaned_text for keyword in keywords) and is_text_inside_space(text_obj, space):
                dist = (text_obj.matrix_world.translation - space_center).length
                candidates.append((dist, cleaned_text))

        if candidates:
            candidates.sort(key=lambda c: c[0])
            matching_text = candidates[0][1]
            print(f"{space.name} - {matching_text}")
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
    # Keys are full Blender object names (e.g. "IfcSpace/focusRoom_001").
    file = _resolve_ifc_file()
    for space_name, new_space_name in space_replacements.items():
        obj = bpy.data.objects.get(space_name)
        if obj is None:
            continue
        # Persist into the IFC entity so the name survives a Bonsai resync
        # and reaches the export.
        if file:
            bim_props = getattr(obj, 'BIMObjectProperties', None)
            ifc_id = getattr(bim_props, 'ifc_definition_id', 0)
            if ifc_id:
                element = file.by_id(ifc_id)
                if element:
                    element.Name = new_space_name
        prefix = obj.name.rsplit('/', 1)[0] + '/' if '/' in obj.name else ''
        new_full = prefix + new_space_name
        print("rename " + obj.name + " to " + new_full)
        obj.name = new_full
    

#########################################################

class ESEC_OT_ImportIFC(bpy.types.Operator):
    bl_idname = "esec.import_ifc"
    bl_label = "Import IFC"
    bl_description = "Import IFC file"

    def execute(self, context):
        try:
            bpy.ops.bim.load_project('INVOKE_DEFAULT')
        except AttributeError:
            bpy.ops.import_ifc.bim('INVOKE_DEFAULT')
        return {'FINISHED'}

class ESEC_OT_ImportDXF(bpy.types.Operator):
    bl_idname = "esec.import_dxf"
    bl_label = "Import DXF"
    bl_description = "Import DXF file"

    def execute(self, context):
        col = get_or_create_dxf_import_collection()
        set_active_collection(col)
        try:
            bpy.ops.import_scene.dxf('INVOKE_DEFAULT')
        except (AttributeError, RuntimeError):
            self.report({'ERROR'}, "DXF import not available. Enable 'Import-Export: AutoCAD DXF' in Edit > Preferences > Add-ons.")
            return {'CANCELLED'}
        return {'FINISHED'}

class ESEC_OT_RenameSpacesByLongname(bpy.types.Operator):
    bl_idname = "esec.rename_spaces_by_longname"
    bl_label = "Prepare IFC"
    bl_description = "Rename spaces by long name"

    def execute(self, context):
        rename_spaces_by_longname()
        sort_spaces_for_export()
        return {'FINISHED'}

class ESEC_OT_PrepareDXF(bpy.types.Operator):
    bl_idname = "esec.prepare_dxf"
    bl_label = "Prepare DXF"
    bl_description = "Prepare DXF file"

    def execute(self, context):
        print("Prepare DXF")
        move_objects_to_new_collection()
        print("delete_unwanted_text_objects_from_dxf")
        delete_unwanted_text_objects_from_dxf()
        return {'FINISHED'}

class ESEC_OT_RenameSpaces(bpy.types.Operator):
    bl_idname = "esec.rename_spaces"
    bl_label = "Rename Spaces by DXF Text"
    bl_description = "Rename spaces based on text objects"

    def execute(self, context):
        print_spaces_and_texts()
        return {'FINISHED'}


class ESEC_OT_SortIFCFile(bpy.types.Operator, ImportHelper):
    bl_idname = "esec.sort_ifc_file"
    bl_label = "Sort exported IFC"
    bl_description = (
        "Pick an exported IFC. Reorders the IfcSpace entities by type "
        "(meetingRoom first ... staircase last) and writes a copy as <name>_sorted.ifc"
    )
    filename_ext = ".ifc"
    filter_glob: bpy.props.StringProperty(default="*.ifc", options={'HIDDEN'})

    def execute(self, context):
        from . import sort_ifc_spaces
        path = self.filepath
        if not path or not path.lower().endswith(".ifc"):
            self.report({'ERROR'}, "Please select an .ifc file.")
            return {'CANCELLED'}
        try:
            out_path = sort_ifc_spaces.main(path)
        except Exception as e:
            self.report({'ERROR'}, "Sort failed: %s" % e)
            return {'CANCELLED'}
        self.report({'INFO'}, "Sorted IFC written: %s" % os.path.basename(out_path))
        return {'FINISHED'}


class ESEC_PT_MainPanel(bpy.types.Panel):
    bl_label = "ESEC IFC-TI Helper v" + ".".join(map(str, bl_info['version']))
    bl_idname = "ESEC_PT_MainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ESEC'

    def draw(self, context):
        layout = self.layout

        # Add your buttons here
        layout.operator("esec.import_ifc", icon="IMPORT")
        layout.operator("esec.rename_spaces_by_longname", icon="FILE_3D")
        layout.separator()
        layout.operator("esec.import_dxf", icon="IMPORT")  
        layout.label(text="Strings to keep in DXF | used as prefix wildcard")      
        layout.prop(context.scene, "esec_strings_to_keep")      
        layout.operator("esec.prepare_dxf", icon="FILE_VOLUME")
        layout.separator()
        layout.label(text="1. Use Autocad to open the DWG")      
        layout.label(text="2. Clean up layers. Command: laydel+N")              
        layout.label(text="4. Export as DXF")      
        layout.label(text="5. Prepare Archi IFC Export. ")      
        layout.label(text="6. Delete columns")      
        layout.label(text="7. Export as IFC")      
        layout.label(text="8. Blender: Move all room names inside spaces")              
        layout.label(text="9. Move only the DXF!!")      
        layout.separator()
        layout.operator("esec.rename_spaces", icon="SNAP_VERTEX")
        layout.prop(context.scene, "esec_dry_run")
        layout.separator()
        layout.label(text="Export with IFC Save as")
        layout.separator()
        layout.operator("esec.sort_ifc_file", icon="SORTALPHA")


def register():
    bpy.types.Scene.esec_dry_run = bpy.props.BoolProperty(
        name="Dry Run (check system console)",
        description="Enable Dry Run (check system console)",
        default=True,
    )
    bpy.types.Scene.esec_strings_to_keep = bpy.props.StringProperty(
        name="Strings to keep",
        description="Enter strings to keep, separated by commas",
        default='A., B., C., D., E., F., G.',
    )

    bpy.utils.register_class(ESEC_OT_ImportIFC)
    bpy.utils.register_class(ESEC_OT_ImportDXF)
    bpy.utils.register_class(ESEC_OT_RenameSpacesByLongname)
    bpy.utils.register_class(ESEC_OT_PrepareDXF)
    bpy.utils.register_class(ESEC_OT_RenameSpaces)
    bpy.utils.register_class(ESEC_OT_SortIFCFile)
    bpy.utils.register_class(ESEC_PT_MainPanel)


def unregister():
    bpy.utils.unregister_class(ESEC_PT_MainPanel)
    bpy.utils.unregister_class(ESEC_OT_SortIFCFile)
    bpy.utils.unregister_class(ESEC_OT_RenameSpaces)
    bpy.utils.unregister_class(ESEC_OT_PrepareDXF)
    bpy.utils.unregister_class(ESEC_OT_RenameSpacesByLongname)
    bpy.utils.unregister_class(ESEC_OT_ImportDXF)
    bpy.utils.unregister_class(ESEC_OT_ImportIFC)

    del bpy.types.Scene.esec_strings_to_keep
    del bpy.types.Scene.esec_dry_run

    

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