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


def _resolve_ifc_path():
    """Path of the currently loaded IFC, from whichever BIM addon is active."""
    import sys
    import types
    for key, mod in sys.modules.items():
        if isinstance(mod, types.ModuleType) and key.endswith('.bim.ifc') and hasattr(mod, 'IfcStore'):
            return getattr(mod.IfcStore, 'path', None)
    return None


def _save_blend_named_after_ifc():
    """Save the blend next to the loaded IFC, named after it. Synchronous.

    Called from Prepare IFC, where an IFC is already loaded, so no polling is
    needed (the import operator is modal and has no loaded IFC on return).
    """
    path = _resolve_ifc_path()
    if not path:
        print("[_save_blend_named_after_ifc] No IFC path available, blend not saved.")
        return
    blend_path = os.path.splitext(path)[0] + '.blend'
    print("[_save_blend_named_after_ifc] IFC path: %s" % path)
    try:
        bpy.ops.wm.save_as_mainfile(filepath=blend_path)
        print("[_save_blend_named_after_ifc] Saved blend project: " + blend_path)
    except Exception as exc:
        print("[_save_blend_named_after_ifc] Could not save blend: " + str(exc))


def rename_spaces_by_longname():
    print("[rename_spaces_by_longname] start")

    file = _resolve_ifc_file()
    if not file:
        print("[rename_spaces_by_longname] No IFC file loaded, skipping.")
        return

    counters = {}
    renamed = 0
    skipped = 0

    for obj in bpy.data.objects:
        if "IfcSpace" not in obj.name:
            continue

        bim_props = getattr(obj, 'BIMObjectProperties', None)
        ifc_id = getattr(bim_props, 'ifc_definition_id', 0)
        if not ifc_id:
            print("[rename_spaces_by_longname] skip %s: no ifc_definition_id" % obj.name)
            skipped += 1
            continue

        element = file.by_id(ifc_id)
        if not element:
            print("[rename_spaces_by_longname] skip %s: ifc id %s not found" % (obj.name, ifc_id))
            skipped += 1
            continue

        longname = getattr(element, 'LongName', None)
        print("[rename_spaces_by_longname] %s -> LongName=%s" % (obj.name, longname))
        if not longname:
            print("[rename_spaces_by_longname] skip %s: empty LongName" % obj.name)
            skipped += 1
            continue

        # Derive the object name straight from the IFC LongName, so new room
        # types work without maintaining a lookup table. Strip anything that is
        # not alphanumeric to keep the name a clean single token.
        type_name = re.sub(r'[^A-Za-z0-9]', '', longname)
        if not type_name:
            print("[rename_spaces_by_longname] skip %s: LongName has no alphanumerics" % obj.name)
            skipped += 1
            continue

        counters[type_name] = counters.get(type_name, 0) + 1
        new_name = '{}_{:03}'.format(type_name, counters[type_name])
        print("[rename_spaces_by_longname] rename %s -> %s" % (obj.name, new_name))
        # Persist into the IFC entity, otherwise Bonsai resyncs the object
        # name back to the original IFC Name on the next refresh.
        element.Name = new_name
        obj.name = new_name
        renamed += 1

    print("[rename_spaces_by_longname] done, renamed=%d skipped=%d" % (renamed, skipped))


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


def _space_sort_key(space, id_to_obj, alpha_first=False):
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

    if alpha_first:
        # After the DXF rename: order by the IFC Name alphabetically first
        # (A.East G.001, A.West C.002, ...), then fall back to the predefined
        # type order for spaces that share a name prefix.
        ifc_name = (space.Name or '').strip().lower()
        return (ifc_name, group, rank, number)

    return (group, rank, type_key, number, name)


def sort_spaces_for_export(alpha_first=False):
    print("[sort_spaces_for_export] start (alpha_first=%s)" % alpha_first)
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
    print("[sort_spaces_for_export] mapped %d IFC objects" % len(id_to_obj))

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

    print("[sort_spaces_for_export] %d storey(s) with space aggregations" % len(by_storey))
    for storey_id, rels in by_storey.items():
        spaces = []
        for rel in rels:
            spaces.extend(rel.RelatedObjects)
        if len(spaces) < 2:
            print("[sort_spaces_for_export] storey #%s has %d space(s), skip sort" % (storey_id, len(spaces)))
            continue

        spaces.sort(key=lambda s: _space_sort_key(s, id_to_obj, alpha_first))

        keep = rels[0]
        keep.RelatedObjects = tuple(spaces)
        for rel in rels[1:]:
            file.remove(rel)

        print("[sort_spaces_for_export] merged {} rels into 1, {} spaces under storey #{}".format(
            len(rels), len(spaces), storey_id))
        for order, s in enumerate(spaces, 1):
            print("[sort_spaces_for_export]   %02d. %s (%s)" % (order, s.Name, getattr(s, 'LongName', '')))
    print("[sort_spaces_for_export] done")


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
        print("[get_or_create_dxf_import_collection] created '%s'" % DXF_IMPORT_COLLECTION)
    else:
        print("[get_or_create_dxf_import_collection] reuse '%s'" % DXF_IMPORT_COLLECTION)
    return col


def set_active_collection(col):
    layer_col = find_layer_collection(bpy.context.view_layer.layer_collection, col.name)
    if layer_col:
        bpy.context.view_layer.active_layer_collection = layer_col
        print("[set_active_collection] active layer collection -> %s" % col.name)
    else:
        print("[set_active_collection] layer collection for '%s' not found" % col.name)


def move_objects_to_new_collection():
    print("[move_objects_to_new_collection] start")
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
    print("[move_objects_to_new_collection] %d object(s) in source '%s'" % (len(all_objects), source.name))

    text_count = 0
    building_count = 0
    for obj in all_objects:
        # Skip collection instances
        if obj.type == 'EMPTY' and obj.instance_collection:
            continue

        # Unlink from the source collection
        source.objects.unlink(obj)

        # Link to appropriate subcollection
        if obj.type == 'FONT':
            dxf_text.objects.link(obj)
            text_count += 1
        else:
            dxf_building.objects.link(obj)
            building_count += 1

    print("[move_objects_to_new_collection] done, %d text -> dxf_text, %d other -> dxf_building" % (text_count, building_count))

def delete_unwanted_text_objects_from_dxf():
    print("[delete_unwanted_text_objects_from_dxf] start")
    # Define the list of strings to look for
    strings_to_keep = bpy.context.scene.esec_strings_to_keep.split(', ')
    print("[delete_unwanted_text_objects_from_dxf] strings_to_keep=%s" % strings_to_keep)

    # Get the 'dxf_text' collection
    dxf_text_collection = bpy.data.collections.get('dxf_text')

    # If the collection doesn't exist, there's nothing to do
    if not dxf_text_collection:
        print("[delete_unwanted_text_objects_from_dxf] 'dxf_text' collection does not exist.")
        return

    # Collect text objects whose body contains none of the strings to keep.
    # bpy.data.objects.remove() is context-independent; bpy.ops.object.delete()
    # needs a correct operator context override that we cannot guarantee here.
    to_delete = [
        obj for obj in dxf_text_collection.objects
        if obj.type == 'FONT' and not any(s in obj.data.body for s in strings_to_keep)
    ]
    print("[delete_unwanted_text_objects_from_dxf] %d text object(s) to delete" % len(to_delete))
    for obj in to_delete:
        print("[delete_unwanted_text_objects_from_dxf] delete %s" % obj.name)
        bpy.data.objects.remove(obj, do_unlink=True)
    print("[delete_unwanted_text_objects_from_dxf] done")

    
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
    print("[print_spaces_and_texts] start")
    space_replacements = {}

    # Collect IfcSpace objects anywhere in the scene. Bonsai changed the
    # collection layout (no fixed 'IfcProject/None'); collect_spaces filters
    # on 'IfcSpace' in the object name, so the source name no longer matters.
    space_objects = []
    collect_spaces(bpy.context.scene.collection, space_objects)

    if not space_objects:
        print("[print_spaces_and_texts] No IfcSpace objects found in the scene.")
        return

    text_objects = []
    collect_text_objects(bpy.context.scene.collection, text_objects)
    print("[print_spaces_and_texts] %d space(s), %d text object(s)" % (len(space_objects), len(text_objects)))

    sorted_space_objects = sorted(space_objects, key=sort_spaces_numerically)

    #keywords = ['North', 'South', 'West', 'East', 'Central']
    keywords = bpy.context.scene.esec_strings_to_keep.split(', ')
    print("[print_spaces_and_texts] keywords=%s" % keywords)

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
            print("[print_spaces_and_texts] match %s -> %s" % (space.name, matching_text))
            total_texts_found += 1
            space_replacements[space.name] = matching_text

    print("[print_spaces_and_texts] Total IFC spaces: %d" % len(sorted_space_objects))
    print("[print_spaces_and_texts] Texts found in spaces: %d" % total_texts_found)

    if not bpy.context.scene.esec_dry_run:
        print("[print_spaces_and_texts] dry_run=OFF, applying %d rename(s)" % len(space_replacements))
        replace_space_names_in_ifc(space_replacements)
        sort_spaces_for_export(alpha_first=True)
    else:
        print("[print_spaces_and_texts] dry_run=ON, no changes applied")
            #replace_space_names_in_ifc(space_replacements)

    # Mark every space that got no DXF text match, so the user can see at a
    # glance which ones still need attention. Unmatched spaces are not in
    # space_replacements and therefore keep their object reference.
    unmatched = [s for s in sorted_space_objects if s.name not in space_replacements]
    for obj in list(bpy.context.selected_objects):
        obj.select_set(False)
    last = None
    for space in unmatched:
        try:
            space.select_set(True)
            last = space
        except RuntimeError:
            pass
    if last:
        bpy.context.view_layer.objects.active = last
    print("[print_spaces_and_texts] Spaces without DXF match (selected): %d" % len(unmatched))
    for space in unmatched:
        print("[print_spaces_and_texts]   not renamed: %s" % space.name)
    print("[print_spaces_and_texts] done")

    return space_replacements

def replace_space_names_in_ifc(space_replacements):
    # Keys are full Blender object names (e.g. "IfcSpace/focusRoom_001").
    print("[replace_space_names_in_ifc] start, %d rename(s)" % len(space_replacements))
    file = _resolve_ifc_file()
    if not file:
        print("[replace_space_names_in_ifc] No IFC file loaded, Blender names only.")
    renamed = 0
    for space_name, new_space_name in space_replacements.items():
        obj = bpy.data.objects.get(space_name)
        if obj is None:
            print("[replace_space_names_in_ifc] skip %s: object not found" % space_name)
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
        print("[replace_space_names_in_ifc] rename %s -> %s" % (obj.name, new_full))
        obj.name = new_full
        renamed += 1
    print("[replace_space_names_in_ifc] done, %d renamed" % renamed)
    

#########################################################

class ESEC_OT_ImportIFC(bpy.types.Operator):
    bl_idname = "esec.import_ifc"
    bl_label = "Import IFC"
    bl_description = "Import IFC file"

    def execute(self, context):
        print("[ESEC_OT_ImportIFC] execute")
        try:
            bpy.ops.bim.load_project('INVOKE_DEFAULT')
            print("[ESEC_OT_ImportIFC] bim.load_project dialog opened")
        except AttributeError:
            bpy.ops.import_ifc.bim('INVOKE_DEFAULT')
            print("[ESEC_OT_ImportIFC] import_ifc.bim dialog opened (legacy)")
        return {'FINISHED'}

class ESEC_OT_ImportDXF(bpy.types.Operator):
    bl_idname = "esec.import_dxf"
    bl_label = "Import DXF"
    bl_description = "Import DXF file"

    def execute(self, context):
        print("[ESEC_OT_ImportDXF] execute")
        col = get_or_create_dxf_import_collection()
        set_active_collection(col)
        try:
            bpy.ops.import_scene.dxf('INVOKE_DEFAULT')
            print("[ESEC_OT_ImportDXF] import_scene.dxf dialog opened")
        except (AttributeError, RuntimeError):
            self.report({'ERROR'}, "DXF import not available. Enable 'Import-Export: AutoCAD DXF' in Edit > Preferences > Add-ons.")
            return {'CANCELLED'}
        return {'FINISHED'}

class ESEC_OT_RenameSpacesByLongname(bpy.types.Operator):
    bl_idname = "esec.rename_spaces_by_longname"
    bl_label = "Prepare IFC"
    bl_description = "Rename spaces by long name"

    def execute(self, context):
        print("[ESEC_OT_RenameSpacesByLongname] execute")
        _save_blend_named_after_ifc()
        rename_spaces_by_longname()
        sort_spaces_for_export()
        print("[ESEC_OT_RenameSpacesByLongname] done")
        return {'FINISHED'}

class ESEC_OT_PrepareDXF(bpy.types.Operator):
    bl_idname = "esec.prepare_dxf"
    bl_label = "Prepare DXF"
    bl_description = "Prepare DXF file"

    def execute(self, context):
        print("[ESEC_OT_PrepareDXF] execute")
        move_objects_to_new_collection()
        delete_unwanted_text_objects_from_dxf()
        print("[ESEC_OT_PrepareDXF] done")
        return {'FINISHED'}

class ESEC_OT_RenameSpaces(bpy.types.Operator):
    bl_idname = "esec.rename_spaces"
    bl_label = "Rename Spaces by DXF Text"
    bl_description = "Rename spaces based on text objects"

    def execute(self, context):
        print("[ESEC_OT_RenameSpaces] execute")
        print_spaces_and_texts()
        print("[ESEC_OT_RenameSpaces] done")
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
        print("[ESEC_OT_SortIFCFile] execute, file=%s" % self.filepath)
        from . import sort_ifc_spaces
        path = self.filepath
        if not path or not path.lower().endswith(".ifc"):
            self.report({'ERROR'}, "Please select an .ifc file.")
            return {'CANCELLED'}
        try:
            out_path = sort_ifc_spaces.main(path)
        except Exception as e:
            print("[ESEC_OT_SortIFCFile] sort failed: %s" % e)
            self.report({'ERROR'}, "Sort failed: %s" % e)
            return {'CANCELLED'}
        print("[ESEC_OT_SortIFCFile] sorted IFC written: %s" % out_path)
        self.report({'INFO'}, "Sorted IFC written: %s" % os.path.basename(out_path))
        return {'FINISHED'}


def delete_spaces_by_name(keywords):
    print("[delete_spaces] start, keywords=%s" % keywords)
    if not keywords:
        print("[delete_spaces] no keywords given, nothing to do.")
        return 0

    lowered = [k.lower() for k in keywords]

    file = _resolve_ifc_file()
    if not file:
        print("[delete_spaces] No IFC file loaded, aborting.")
        return 0

    try:
        import ifcopenshell.api
    except ImportError:
        print("[delete_spaces] ifcopenshell.api not available, aborting.")
        return 0

    targets = []
    for obj in bpy.data.objects:
        if "IfcSpace" not in obj.name:
            continue
        bim_props = getattr(obj, 'BIMObjectProperties', None)
        ifc_id = getattr(bim_props, 'ifc_definition_id', 0)
        element = file.by_id(ifc_id) if ifc_id else None
        match_name = (getattr(element, 'Name', None) or obj.name)
        if any(k in match_name.lower() for k in lowered):
            targets.append((obj, element, match_name))

    if not targets:
        print("[delete_spaces] no IfcSpace matched %s" % keywords)
        return 0

    print("[delete_spaces] %d space(s) matched:" % len(targets))
    for _, _, name in targets:
        print("  - %s" % name)

    deleted = 0
    for obj, element, name in targets:
        # root.remove_product unlinks the space from its aggregation, containment,
        # space boundaries, property and type relations and cleans up its owned
        # placement/representation, so no dangling references remain in the IFC.
        try:
            if element is not None:
                ifcopenshell.api.run("root.remove_product", file, product=element)
                print("[delete_spaces] removed IFC entity for %s" % name)
        except Exception as e:
            print("[delete_spaces] FAILED to remove IFC entity for %s: %s" % (name, e))
            continue
        try:
            bpy.data.objects.remove(obj, do_unlink=True)
        except Exception as e:
            print("[delete_spaces] removed from IFC but failed to delete Blender object %s: %s" % (name, e))
        deleted += 1

    print("[delete_spaces] done, %d space(s) deleted." % deleted)
    return deleted


class ESEC_OT_DeleteSpaces(bpy.types.Operator):
    bl_idname = "esec.delete_spaces"
    bl_label = "Delete Spaces by Name"
    bl_description = "Safely delete every IfcSpace whose name matches the comma separated text field"
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        print("[ESEC_OT_DeleteSpaces] execute")
        raw = context.scene.esec_spaces_to_delete or ''
        keywords = [k.strip() for k in raw.split(',') if k.strip()]
        deleted = delete_spaces_by_name(keywords)
        if deleted:
            self.report({'INFO'}, "Deleted %d space(s). See system console." % deleted)
        else:
            self.report({'WARNING'}, "No spaces deleted. See system console.")
        return {'FINISHED'}


def _ifc_save_as_available():
    # Bonsai registers BIM_OT_save_project (idname bim.save_project), older
    # BlenderBIM EXPORT_IFC_OT_bim (idname export_ifc.bim).
    return (hasattr(bpy.types, 'BIM_OT_save_project')
            or hasattr(bpy.types, 'EXPORT_IFC_OT_bim'))


class ESEC_OT_SaveAsIFC(bpy.types.Operator):
    bl_idname = "esec.save_as_ifc"
    bl_label = "Save as IFC"
    bl_description = "Save the loaded IFC under a new name via the active BIM addon"

    @classmethod
    def poll(cls, context):
        return _ifc_save_as_available()

    def execute(self, context):
        print("[ESEC_OT_SaveAsIFC] execute")
        if hasattr(bpy.types, 'BIM_OT_save_project'):
            print("[ESEC_OT_SaveAsIFC] using bim.save_project (should_save_as=True)")
            bpy.ops.bim.save_project('INVOKE_DEFAULT', should_save_as=True)
        elif hasattr(bpy.types, 'EXPORT_IFC_OT_bim'):
            print("[ESEC_OT_SaveAsIFC] using export_ifc.bim (legacy)")
            bpy.ops.export_ifc.bim('INVOKE_DEFAULT')
        else:
            self.report({'ERROR'}, "No IFC save operator available. Is Bonsai/BlenderBIM enabled?")
            return {'CANCELLED'}
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
        layout.prop(context.scene, "esec_dry_run")
        layout.operator("esec.rename_spaces", icon="SNAP_VERTEX")
        
        layout.separator()
        layout.label(text="Delete spaces by name | comma separated")
        layout.prop(context.scene, "esec_spaces_to_delete")
        layout.operator("esec.delete_spaces", icon="TRASH")


        if _ifc_save_as_available():
            layout.separator()
            layout.operator("esec.save_as_ifc", icon="EXPORT")

        layout.separator()
        layout.label(text="After saved IFC File, select this File for sorting.")
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
    bpy.types.Scene.esec_spaces_to_delete = bpy.props.StringProperty(
        name="Spaces to delete",
        description="Comma separated names. Every IfcSpace whose name contains one of these is safely deleted.",
        default='Shaft',
    )

    bpy.utils.register_class(ESEC_OT_ImportIFC)
    bpy.utils.register_class(ESEC_OT_ImportDXF)
    bpy.utils.register_class(ESEC_OT_RenameSpacesByLongname)
    bpy.utils.register_class(ESEC_OT_PrepareDXF)
    bpy.utils.register_class(ESEC_OT_RenameSpaces)
    bpy.utils.register_class(ESEC_OT_SortIFCFile)
    bpy.utils.register_class(ESEC_OT_DeleteSpaces)
    bpy.utils.register_class(ESEC_OT_SaveAsIFC)
    bpy.utils.register_class(ESEC_PT_MainPanel)
    print("[register] ESEC IFC-TI Helper registered")


def unregister():
    print("[unregister] ESEC IFC-TI Helper unregistering")
    bpy.utils.unregister_class(ESEC_PT_MainPanel)
    bpy.utils.unregister_class(ESEC_OT_SaveAsIFC)
    bpy.utils.unregister_class(ESEC_OT_DeleteSpaces)
    bpy.utils.unregister_class(ESEC_OT_SortIFCFile)
    bpy.utils.unregister_class(ESEC_OT_RenameSpaces)
    bpy.utils.unregister_class(ESEC_OT_PrepareDXF)
    bpy.utils.unregister_class(ESEC_OT_RenameSpacesByLongname)
    bpy.utils.unregister_class(ESEC_OT_ImportDXF)
    bpy.utils.unregister_class(ESEC_OT_ImportIFC)

    del bpy.types.Scene.esec_spaces_to_delete
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