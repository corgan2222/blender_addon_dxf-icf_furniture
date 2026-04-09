import inspect
import math
import os
import re

import bmesh
import bpy
import mathutils
from bpy.types import Panel
from mathutils import Vector

from . import config, esec_archiologic_importer


def _get_prefs():
    """Return the addon's ESECAddonPreferences, or None if not yet registered."""
    try:
        return bpy.context.preferences.addons[__package__].preferences
    except Exception:
        return None

def _debug_mode():
    """Return True if the addon's debug_mode preference is enabled."""
    prefs = _get_prefs()
    return prefs.debug_mode if prefs else False

class ESEC_OT_OpenAddonPreferences_DXF(bpy.types.Operator):
    """Show instructions for enabling DXF Import"""
    bl_idname = "esec.open_addon_preferences_dxf"
    bl_label = "Enable DXF Import"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Show instructions in a Blender pop-up
        self.report({'INFO'}, "Go to Edit > Preferences > Add-ons and search for 'DXF'. Enable the 'Import-Export: AutoCAD DXF' addon.")
        return {'FINISHED'}

class ESEC_OT_OpenAddonPreferences_BIM(bpy.types.Operator):
    """Show instructions for installing Blender BIM Plugin"""
    bl_idname = "esec.open_addon_preferences_bim"
    bl_label = "Then install Bonsai Plugin"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Show instructions in a Blender pop-up
        self.report({'INFO'}, "Go to Edit > Preferences > Add-ons and then click on install. Select the downloaded ZIP File. Then enable the Plugin.")
        return {'FINISHED'}

def get_version_from_init():
    """Read the addon version tuple from __init__.py and return it as 'X.Y.Z' string.
    Used to display the version in the panel header without importing __init__ directly.
    """
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
    bl_label = "ESEC 3D Floorplan Creator v" + get_version_from_init()
    bl_idname = "ESEC_PT_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ESEC'

    def draw(self, context):
        layout = self.layout
        props = context.scene.esec_addon_props

        bim_import_available = self.check_ifc_import_availability()

        if not bim_import_available:
            layout.operator(ESEC_OT_OpenAddonPreferences_DXF.bl_idname, icon='PREFERENCES')
            layout.separator()

        if not bim_import_available:
            # Display an error message if DXF import is not available
            layout.label(text="IFC Import (Bonsai) not available!", icon='ERROR')
            # Button to show instructions
            layout.operator("wm.url_open", text="Download Bonsai").url = "https://github.com/IfcOpenShell/IfcOpenShell/releases"
            layout.operator(ESEC_OT_OpenAddonPreferences_BIM.bl_idname, icon='PREFERENCES')
            layout.separator()

        if bim_import_available:
            layout.label(text="Import")
            layout.operator("esec.import_ifc_manual", icon="IMPORT")
            layout.separator()
            layout.label(text="Process")
            layout.operator("esec.process_ifc", icon="HAND")
            layout.separator()   
            layout.separator()
            layout.label(text="Save/Export")
            row_03 = layout.row(align=True)  # align=True puts operators side by side
            row_03.operator("esec.save_as", icon="FILE_TICK")        
            row_03.operator("esec.export_obj", icon='EXPORT')
            layout.operator("esec.export_keyshot", icon='EXPORT')
            layout.separator()
            layout.label(text="Render")
            layout.operator("esec.setup_renderer", icon='SHADING_RENDERED')
            row_04 = layout.row(align=True)
            row_04.operator("esec.render", icon='RENDERLAYERS')
            if _last_render_path and os.path.isfile(_last_render_path):
                row_04.operator("esec.open_render_folder", text="", icon='FILE_FOLDER')
                row_04.operator("esec.open_render_image", text="", icon='IMAGE_DATA')
            layout.separator()        
            layout.menu(ESEC_MT_Tools.bl_idname)
            layout.separator()   
            box = layout.box()
            row = box.row()
            row.prop(props, "show_settings", icon="TRIA_DOWN" if props.show_settings else "TRIA_RIGHT", emboss=False)
            if props.show_settings:
                prefs = _get_prefs()
                if prefs:
                    box.prop(prefs, "repair_missing_walls", text="Repair missing walls on IFC import")
                    box.prop(prefs, "debug_mode", text="Debug Mode")

        layout.label(text="  stefan.knaak@e-shelter.io")            


    @staticmethod
    def check_ifc_import_availability():
        """Check if the IFC import operator is available (Bonsai or BlenderBIM)."""
        try:
            return bpy.ops.bim.load_project.poll() is not None
        except AttributeError:
            try:
                return bpy.ops.import_ifc.bim.poll() is not None
            except AttributeError:
                return False


class ESEC_OT_DeleteIfcCollection(bpy.types.Operator):
    """Remove the Structure collections (ifc, Floors, Doors, Windows, etc.) from the scene.
    Used in the Tools menu to reset the IFC side before re-running Process IFC.
    """
    bl_idname = "esec.delete_ifc_collection"
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


class ESEC_OT_DeleteFurnitureCollection(bpy.types.Operator):
    """Remove all Assets/furniture collections (tables, chairs, sofas, etc.) from the scene.
    Used in the Tools menu to reset the furniture side before re-running Step 4.
    """
    bl_idname = "esec.delete_furniture_collection"
    bl_label = "Delete Furniture Collection"
    bl_description = "Deletes all furniture Collections"

    def execute(self, context):

        collections = ['tables', 'Office_chairs', 'Dining_chairs', 'Arm_chairs', 'Bar_Stools', 'printer', 'Sofas', 'outdoor_bench', 'outdoor_chair', 'Storage', 'Sideboard', 'Bathroom', 'closets' , 'Assets', 'RollingContainer']

        for collection_name in collections:
            if collection := bpy.data.collections.get(collection_name):
                bpy.data.collections.remove(collection)
                print(f"Deleted '{collection_name}' collection.")
            else:
                print(f"Collection '{collection_name}' not found.")

        return {'FINISHED'}

# Operator classes


class ESEC_OT_process_ifc(bpy.types.Operator):
    bl_idname = "esec.process_ifc"
    bl_label = "Process IFC"
    bl_description = "Execute all steps at once"

    @classmethod
    def poll(cls, context):
        return any(
            coll.name.startswith("IfcProject/") or coll.name == "ifc"
            for coll in bpy.data.collections
        )

    def _build_steps(self, context):
        steps = []
        prefs = _get_prefs()
        if prefs and prefs.repair_missing_walls:
            steps.append(("Repairing walls...", lambda: bpy.ops.esec.repair_missing_walls()))
        steps.append(("Moving objects to IFC...", move_objects_to_ifc))
        steps.append(("Sorting IFC types...", self._sort_ifc_types))
        steps.append(("Renaming spaces...", rename_spaces_with_long_name))
        steps.append(("Splitting Floors / Ceiling...", lambda: move_slabs_separate_ceiling("ifc", "Floors", "Ceiling")))
        steps.append(("Renaming floors...", rename_floors_with_space_type))
        steps.append(("Hiding Space & Ceiling...", self._hide_collections))        
        steps.append(("Organizing collections...", organize_collections))
        steps.append(("Cleanup...", remove_ifc_project_collection))
        steps.append(("Renaming furnish from assets...", esec_archiologic_importer.rename_furnish_from_assets))
        steps.append(("Assigning materials...", assign_collection_materials))
        return steps

    def invoke(self, context, _event):
        print("Beginn IFC processing")
        self._steps = self._build_steps(context)
        self._step = 0
        context.window_manager.progress_begin(0, len(self._steps))
        self._timer = context.window_manager.event_timer_add(0.01, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        if self._step < len(self._steps):
            label, fn = self._steps[self._step]
            text = f"Step 1-5  [{self._step + 1}/{len(self._steps)}]  {label}"
            if _debug_mode():
                print(f"[process_ifc] {text}")
            context.workspace.status_text_set(text)
            context.window_manager.progress_update(self._step)
            try:
                fn()
            except Exception as e:
                print(f"[process_ifc] ERROR in '{label}': {e}")
                self._finish(context)
                self.report({'ERROR'}, str(e))
                return {'CANCELLED'}
            self._step += 1
            return {'RUNNING_MODAL'}

        self._finish(context)
        print("all done")
        self.report({'INFO'}, "IFC processing complete.")
        return {'FINISHED'}

    def _finish(self, context):
        context.window_manager.event_timer_remove(self._timer)
        context.window_manager.progress_end()
        context.workspace.status_text_set(None)

    def _sort_ifc_types(self):
        move_objects_to_new_collection("IfcColumn/", "ifc", "Column")
        move_objects_to_new_collection("IfcElementAssembly/", "ifc", "IfcElementAssembly")
        move_objects_to_new_collection("IfcStairFlight/", "ifc", "Stair")
        move_objects_to_new_collection("IfcWall/", "ifc", "Walls")
        move_objects_to_new_collection("IfcWallStandardCase/", "ifc", "Walls")
        move_objects_to_new_collection("IfcDoor/", "ifc", "Doors")
        move_objects_to_new_collection("IfcWindow/", "ifc", "Windows")
        move_objects_to_new_collection("IfcFurnishingElement/", "ifc", "Furnish")
        move_objects_to_new_collection("IfcSpace/", "ifc", "Space")
        move_objects_to_new_collection("IfcStair/", "ifc", "Stair")
        move_objects_to_new_collection("IfcRailing/", "ifc", "Railing")
        move_objects_to_new_collection("IfcSpace/", "IfcSpace", "Spaces")

    def _hide_collections(self):
        space = bpy.data.collections.get('Space')
        if space:
            space.hide_viewport = True
            print("Collection 'Space' is now hidden.")
        ceiling = bpy.data.collections.get('Ceiling')
        if ceiling:
            ceiling.hide_viewport = True
            print("Collection 'Ceiling' is now hidden.")
    



class ESEC_OT_ImportIfc(bpy.types.Operator):
    bl_idname = "esec.import_ifc_manual"
    bl_label = "IFC"
    bl_description = "Import the IFC file exported from Archiologic. Bonsai Addon required. Download from https://github.com/IfcOpenShell/IfcOpenShell/releases."

    @classmethod
    def poll(cls, context):
        try:
            return bpy.ops.bim.load_project.poll() is not None
        except AttributeError:
            try:
                return bpy.ops.import_ifc.bim.poll() is not None
            except AttributeError:
                return False

    def execute(self, context):
        try:
            bpy.ops.bim.load_project('INVOKE_DEFAULT')
        except AttributeError:
            bpy.ops.import_ifc.bim('INVOKE_DEFAULT')
        return {'FINISHED'}

class ESEC_OT_SaveAs(bpy.types.Operator):
    bl_idname = "esec.save_as"
    bl_label = "Blender"
    bl_description = "Save the current file with a new name"

    def execute(self, context):
        bpy.ops.wm.save_as_mainfile('INVOKE_DEFAULT')
        return {'FINISHED'}

class ESEC_OT_ExportObj(bpy.types.Operator):
    bl_idname = "esec.export_obj"
    bl_label = "OBJ"
    bl_description = "Export the current scene as an OBJ file"

    def execute(self, context):
        bpy.ops.wm.obj_export('INVOKE_DEFAULT')
        return {'FINISHED'}

class ESEC_OT_ExportKeyShot(bpy.types.Operator):
    bl_idname = "esec.export_keyshot"
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
        # The KeyShot plugin iterates over collections and calls
        # bpy.ops.object.mode_set(mode="OBJECT") for each one. That operator's
        # poll() requires context.active_object to be set — even during nested calls.
        # Setting active_object once before the call isn't enough because KeyShot
        # clears selection during its traversal.
        #
        # Fix: use context.temp_override() which propagates a stable active_object
        # into ALL nested operator calls made by the KeyShot plugin.

        # Find any non-hidden mesh in the current view layer to use as the anchor
        anchor = next(
            (o for o in context.view_layer.objects
             if o.type == 'MESH' and not o.hide_viewport and not o.hide_get()),
            None
        )
        if anchor is None:
            self.report({'ERROR'}, "No visible mesh found — select any object before exporting to KeyShot.")
            return {'CANCELLED'}

        # Ensure Object mode on the anchor before overriding
        prev_active = context.view_layer.objects.active
        context.view_layer.objects.active = anchor
        if anchor.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        try:
            with context.temp_override(
                active_object=anchor,
                object=anchor,
                selected_objects=[anchor],
                selected_editable_objects=[anchor],
            ):
                bpy.ops.keyshot.send_to_keyshot()
        except RuntimeError as e:
            self.report({'ERROR'}, f"KeyShot export failed: {e}")
            return {'CANCELLED'}
        finally:
            context.view_layer.objects.active = prev_active

        return {'FINISHED'}

class ESEC_OT_repair_missing_walls(bpy.types.Operator):
    bl_idname = "esec.repair_missing_walls"
    bl_label = "Repair Missing Walls"
    bl_description = (
        "Select all IFC objects with a Curve2D representation and switch them to their "
        "Body (3D) representation. Requires Bonsai > 0.8.5-alpha2604081058"
    )

    @classmethod
    def poll(cls, context):
        return (
            hasattr(bpy.ops.bim, 'select_by_representation_type') and
            hasattr(bpy.ops.bim, 'switch_representation')
        )

    def execute(self, context):
        if not hasattr(bpy.ops.bim, 'select_by_representation_type'):
            msg = "bpy.ops.bim.select_by_representation_type not available. Requires Bonsai > 0.8.5-alpha2604081058"
            self.report({'ERROR'}, msg); print(f"[repair_walls] ERROR: {msg}")
            return {'CANCELLED'}

        # Step 1: select all objects currently displaying a Curve2D representation
        print("[repair_walls] Calling select_by_representation_type(Curve2D)...")
        bpy.ops.bim.select_by_representation_type(representation_type="Curve2D")

        selected = list(bpy.context.selected_objects)
        print(f"[repair_walls] Objects selected: {len(selected)}")
        if not selected:
            msg = "No objects with Curve2D representation found."
            self.report({'INFO'}, msg); print(f"[repair_walls] {msg}")
            return {'FINISHED'}

        # Step 2: resolve Bonsai modules via sys.modules
        import sys
        import types

        _ifc_mod = None
        for key, mod in sys.modules.items():
            if isinstance(mod, types.ModuleType) and key.endswith('.bim.ifc') and hasattr(mod, 'IfcStore'):
                _ifc_mod = mod
                break

        # *.tool  — implementation module with Ifc + Geometry tool classes
        _tool_impl = None
        for key, mod in sys.modules.items():
            if (isinstance(mod, types.ModuleType)
                    and not key.endswith('.core.tool')
                    and key.endswith('.tool')
                    and hasattr(mod, 'Ifc')
                    and hasattr(mod, 'Geometry')):
                _tool_impl = mod
                break

        # *.core.geometry — has switch_representation()
        _core_geo = None
        for key, mod in sys.modules.items():
            if (isinstance(mod, types.ModuleType)
                    and key.endswith('.core.geometry')
                    and hasattr(mod, 'switch_representation')):
                _core_geo = mod
                break

        if not _ifc_mod:
            msg = "*.bim.ifc (IfcStore) not found. Is Bonsai active?"
            self.report({'ERROR'}, msg); print(f"[repair_walls] ERROR: {msg}")
            return {'CANCELLED'}

        IfcStore = _ifc_mod.IfcStore
        ifc_file = IfcStore.get_file()
        if not ifc_file:
            msg = "No IFC file loaded."
            self.report({'ERROR'}, msg); print(f"[repair_walls] ERROR: {msg}")
            return {'CANCELLED'}

        # Decide whether to use the fast direct core path or fall back to the operator
        use_core = (_tool_impl is not None and _core_geo is not None)
        print(f"[repair_walls] fast path (core.geometry): {use_core}")

        # Step 3: switch each object from Curve2D to its Body representation
        switched = 0
        for obj in selected:
            bim_props = getattr(obj, 'BIMObjectProperties', None)
            ifc_id = getattr(bim_props, 'ifc_definition_id', 0)
            element = ifc_file.by_id(ifc_id) if ifc_id else None
            if not element:
                print(f"[repair_walls] {obj.name}: no IFC entity, skipping.")
                continue

            body_rep = None
            if element.Representation:
                for rep in element.Representation.Representations:
                    if getattr(rep, 'RepresentationIdentifier', '') == "Body":
                        body_rep = rep
                        break
                if not body_rep:
                    for rep in element.Representation.Representations:
                        rtype = getattr(rep, 'RepresentationType', '')
                        if rtype not in ("Curve2D", "Curve3D", "GeometricCurveSet", "Annotation2D"):
                            body_rep = rep
                            break
            if not body_rep:
                print(f"[repair_walls] {obj.name}: no usable 3D representation, skipping.")
                continue

            if use_core:
                # Fast path: call core function directly — no undo push, no operator overhead
                try:
                    _core_geo.switch_representation(
                        _tool_impl.Ifc,
                        _tool_impl.Geometry,
                        obj=obj,
                        representation=body_rep,
                        apply_openings=True,
                    )
                    switched += 1
                    continue
                except Exception as e:
                    print(f"[repair_walls] core path failed for {obj.name}: {e}, falling back to operator")

            # Fallback: operator (slow but always available)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.bim.switch_representation(
                ifc_definition_id=body_rep.id(),
                disable_opening_subtractions=False,
            )
            switched += 1

        msg = f"Repaired {switched} of {len(selected)} wall(s)."
        self.report({'INFO'}, msg); print(f"[repair_walls] {msg}")
        return {'FINISHED'}


class ESEC_MT_Tools(bpy.types.Menu):
    bl_label = "Tools"
    bl_idname = "ESEC_MT_tools"

    def draw(self, context):
        layout = self.layout
        layout.operator(ESEC_OT_DeleteIfcCollection.bl_idname, icon="CANCEL")
        layout.operator(ESEC_OT_DeleteFurnitureCollection.bl_idname, icon="CANCEL")
        #layout.operator("esec.organize_collections", icon="GRAPH")
        layout.separator()
        layout.operator("esec.prep_parking", icon="REMOVE")
        #layout.separator()
        #layout.operator("esec.repair_missing_walls", icon="MOD_BUILD")

        # Dynamic "Select all - <type> (N)" entries built from renamed objects in scene
        from collections import Counter
        suffix_counts = Counter(
            obj.name.rsplit(" - ", 1)[1]
            for obj in bpy.data.objects
            if obj.name.startswith("IfcSlab/") and " - " in obj.name
        )
        if suffix_counts:
            layout.separator()
            layout.label(text="Select by space type:")
            for suffix in sorted(suffix_counts):
                count = suffix_counts[suffix]
                op = layout.operator("esec.select_by_suffix", text=f"Select all  {suffix}  ({count})", icon="LATTICE_DATA")
                op.suffix = suffix

        layout.separator()
        layout.operator("esec.create_material_by_selection", icon="COLLECTION_NEW")

class ESEC_OT_create_material_by_selection(bpy.types.Operator):
    bl_idname = "esec.create_material_by_selection"
    bl_label = "Create Material by Selection"
    bl_description = "Move selected floor slabs into Structure/Floors_<type> sub-collections"

    @classmethod
    def poll(cls, context):
        return any(
            obj.name.startswith("IfcSlab/") and " - " in obj.name
            for obj in context.selected_objects
        )

    def execute(self, context):
        # Find the Structure collection (parent of Floors)
        structure_coll = bpy.data.collections.get("Structure")

        selected_slabs = [
            obj for obj in context.selected_objects
            if obj.name.startswith("IfcSlab/") and " - " in obj.name
        ]

        moved_by_type = {}
        for obj in selected_slabs:
            suffix = obj.name.rsplit(" - ", 1)[1]
            target_name = f"Floors_{suffix}"

            # Get or create the Floors_<type> collection
            target_coll = bpy.data.collections.get(target_name)
            if not target_coll:
                target_coll = bpy.data.collections.new(target_name)
                # Place it as sibling of Floors under Structure; fall back to scene root
                parent = structure_coll or bpy.context.scene.collection
                parent.children.link(target_coll)
                print(f"[mat_by_sel] Created collection '{target_name}' under '{parent.name}'")

            # Unlink from all current collections, link to target
            for src in list(obj.users_collection):
                try:
                    src.objects.unlink(obj)
                except Exception:
                    pass
            target_coll.objects.link(obj)
            moved_by_type.setdefault(suffix, 0)
            moved_by_type[suffix] += 1

        summary = ", ".join(f"{v}x {k}" for k, v in sorted(moved_by_type.items()))
        print(f"[mat_by_sel] Done: {summary}")

        assign_collection_materials()

        self.report({'INFO'}, f"Moved: {summary} - materials reassigned")
        return {'FINISHED'}

class ESEC_OT_select_by_suffix(bpy.types.Operator):
    bl_idname = "esec.select_by_suffix"
    bl_label = "Select by Space Type"
    bl_description = "Select all objects whose name ends with this space type suffix"

    suffix: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        count = 0
        for obj in bpy.data.objects:
            if obj.name.startswith("IfcSlab/") and obj.name.endswith(f" - {self.suffix}"):
                obj.select_set(True)
                count += 1
        self.report({'INFO'}, f"Selected {count} slab(s): '{self.suffix}'")

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




class ESEC_OT_assign_materials(bpy.types.Operator):
    bl_idname = "esec.assign_materials"
    bl_label = "Step 5 - Assign Materials"
    bl_description = "Assign materials to all objects."

    def execute(self, context):
        assign_collection_materials()
        return {'FINISHED'}         

class ESEC_OT_setup_renderer(bpy.types.Operator):
    bl_idname = "esec.setup_renderer"
    bl_label = "Setup Render (KeyShot style)"
    bl_description = (
        "Configure Cycles to match KeyShot output: "
        "3840x2004 PNG+alpha, 512 samples, Gaussian filter 1.5, "
        "50 mm top-down camera, startup.hdr environment."
    )

    def execute(self, context):
        setup_render()     # engine, resolution, samples, filter, format, transparent bg
        setup_hdri()       # startup.hdr world environment
        setup_camera()     # 50 mm top-down camera, azimuth -90°
        self.report({'INFO'}, "Render setup complete: 3840x2004, 512 samples, 50 mm top-down camera")
        return {'FINISHED'}

class ESEC_OT_render(bpy.types.Operator):
    bl_idname = "esec.render"
    bl_label = "Render"
    bl_description = "Render the scene at 3840x2004 and save as PNG with alpha."

    def execute(self, context):
        render_scene(3840, 2004)
        return {'FINISHED'}


class ESEC_OT_open_render_folder(bpy.types.Operator):
    """Open the folder containing the last rendered image in the OS file explorer."""
    bl_idname = "esec.open_render_folder"
    bl_label = "Open Render Folder"
    bl_description = "Open the folder containing the last rendered image"

    def execute(self, context):
        import subprocess, sys
        path = _last_render_path
        if not path:
            self.report({'WARNING'}, "No render path recorded yet.")
            return {'CANCELLED'}
        folder = os.path.dirname(path)
        if sys.platform == "win32":
            subprocess.Popen(["explorer", folder])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        else:
            subprocess.Popen(["xdg-open", folder])
        return {'FINISHED'}


class ESEC_OT_open_render_image(bpy.types.Operator):
    """Open the last rendered image with the OS default image viewer."""
    bl_idname = "esec.open_render_image"
    bl_label = "Open Render Image"
    bl_description = "Open the last rendered image in the default viewer"

    def execute(self, context):
        import subprocess, sys
        path = _last_render_path
        if not path or not os.path.isfile(path):
            self.report({'WARNING'}, "Rendered file not found.")
            return {'CANCELLED'}
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return {'FINISHED'}

addon_keymaps = []
_last_render_path = None  # set by render_scene() after a successful render

def register():  # sourcery skip: extract-method
    #bpy.utils.register_class(MyPanel)         
    bpy.utils.register_class(ESEC_OT_process_ifc)
    bpy.utils.register_class(ESEC_PT_panel)
    bpy.utils.register_class(ESEC_MT_Tools)
    bpy.utils.register_class(ESEC_OT_ImportIfc)
    bpy.utils.register_class(ESEC_OT_ExportObj)
    bpy.utils.register_class(ESEC_OT_SaveAs)
    bpy.utils.register_class(ESEC_OT_DeleteIfcCollection)
    bpy.utils.register_class(ESEC_OT_DeleteFurnitureCollection)
    bpy.utils.register_class(ESEC_OT_assign_materials)
    bpy.utils.register_class(ESEC_OT_setup_renderer)
    bpy.utils.register_class(ESEC_OT_render)
    bpy.utils.register_class(ESEC_OT_open_render_folder)
    bpy.utils.register_class(ESEC_OT_open_render_image)
    bpy.utils.register_class(ESEC_OT_ExportKeyShot)
    bpy.utils.register_class(ESEC_OT_organize_collections)
    bpy.utils.register_class(ESEC_OT_create_material_by_selection)
    bpy.utils.register_class(ESEC_OT_select_by_suffix)
    bpy.utils.register_class(ESEC_OT_prep_parking)
    bpy.utils.register_class(ESEC_OT_repair_missing_walls)
    bpy.utils.register_class(ESEC_OT_OpenAddonPreferences_DXF)
    bpy.utils.register_class(ESEC_OT_OpenAddonPreferences_BIM)


    wm = bpy.context.window_manager
    if kc := wm.keyconfigs.addon:
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        kmi = km.keymap_items.new(ESEC_OT_ImportIfc.bl_idname, 'I', 'PRESS', alt=True, shift=True)
        addon_keymaps.append((km, kmi))    
    

def unregister():
    bpy.utils.unregister_class(ESEC_OT_process_ifc)
    bpy.utils.unregister_class(ESEC_OT_ImportIfc)
    bpy.utils.unregister_class(ESEC_OT_SaveAs)
    bpy.utils.unregister_class(ESEC_OT_ExportObj)
    bpy.utils.unregister_class(ESEC_PT_panel)
    bpy.utils.unregister_class(ESEC_MT_Tools)
    bpy.utils.unregister_class(ESEC_OT_DeleteIfcCollection)
    bpy.utils.unregister_class(ESEC_OT_DeleteFurnitureCollection)
    bpy.utils.unregister_class(ESEC_OT_assign_materials)
    bpy.utils.unregister_class(ESEC_OT_setup_renderer)
    bpy.utils.unregister_class(ESEC_OT_render)
    bpy.utils.unregister_class(ESEC_OT_open_render_folder)
    bpy.utils.unregister_class(ESEC_OT_open_render_image)
    bpy.utils.unregister_class(ESEC_OT_ExportKeyShot)
    bpy.utils.unregister_class(ESEC_OT_organize_collections)
    bpy.utils.unregister_class(ESEC_OT_create_material_by_selection)
    bpy.utils.unregister_class(ESEC_OT_select_by_suffix)
    bpy.utils.unregister_class(ESEC_OT_prep_parking)
    bpy.utils.unregister_class(ESEC_OT_repair_missing_walls)
    bpy.utils.unregister_class(ESEC_OT_OpenAddonPreferences_DXF)
    bpy.utils.unregister_class(ESEC_OT_OpenAddonPreferences_BIM)        

    for km, kmi in addon_keymaps:
        km.keymap_items.remove(kmi)
    addon_keymaps.clear()    
        
#######################################################################################


def move_objects_to_ifc():
    """Move all objects from any IfcBuildingStorey/Storey* collection(s) into a flat 'ifc' collection.

    Works with both old BlenderBIM (IfcProject/None > IfcSite/None > IfcBuilding/None > ...)
    and new Bonsai (IfcProject/Unnamed > random > IfcBuildingStorey/Storey_<guid>) hierarchies
    by searching the entire collection tree instead of hardcoded paths.
    """
    # Ensure target 'ifc' collection exists
    ifc_collection = bpy.data.collections.get('ifc')
    if not ifc_collection:
        ifc_collection = bpy.data.collections.new('ifc')
        bpy.context.scene.collection.children.link(ifc_collection)

    # Find the IfcProject/... root collection anywhere in the scene tree
    def _find_by_prefix(prefix, parent):
        for coll in parent.children:
            if coll.name.startswith(prefix):
                return coll
            found = _find_by_prefix(prefix, coll)
            if found:
                return found
        return None

    proj = _find_by_prefix("IfcProject/", bpy.context.scene.collection)
    if not proj:
        print("[move_objects_to_ifc] No 'IfcProject/*' collection found in scene.")
        return
    print(f"[move_objects_to_ifc] Found project root: '{proj.name}'")

    # Collect ALL IfcBuildingStorey/Storey* collections anywhere under the project root
    storeys = []
    def _collect_storeys(root):
        for ch in root.children:
            if ch.name.startswith("IfcBuildingStorey/Storey"):
                storeys.append(ch)
            _collect_storeys(ch)
    _collect_storeys(proj)

    if not storeys:
        print(f"[move_objects_to_ifc] No 'IfcBuildingStorey/Storey*' collections found under '{proj.name}'.")
        return
    print(f"[move_objects_to_ifc] Found {len(storeys)} storey(s): {[s.name for s in storeys]}")

    # Recursively move every object from storey (and sub-collections) into 'ifc'
    def _move_recursive(src_coll):
        for obj in list(src_coll.objects):
            try:
                src_coll.objects.unlink(obj)
            except RuntimeError:
                pass
            if ifc_collection not in obj.users_collection:
                ifc_collection.objects.link(obj)
            
            if _debug_mode():
                print(f"  Moved '{obj.name}' → 'ifc'")
        for child in list(src_coll.children):
            _move_recursive(child)

    for s in storeys:
        _move_recursive(s)


def remove_ifc_project_collection():
    """Remove whichever IfcProject/* collection exists (name varies between Bonsai versions)."""
    for coll in list(bpy.data.collections):
        if coll.name.startswith("IfcProject/"):
            bpy.data.collections.remove(coll)
            #print(f"Removed collection: {coll.name}")
            return
    print("No 'IfcProject/*' collection found to remove.")



def rename_spaces_with_long_name():
    """Rename all IfcSpace Blender objects by appending the IFC LongName.
    Searches all bpy.data.objects for IfcSpace/* names — does not rely on
    the Space collection being populated.
    E.g. 'IfcSpace/0be1ab65-...' → 'IfcSpace/0be1ab65-... - parkingSpot'
    """
    import sys
    import types

    debug = _debug_mode()

    # Resolve IfcStore
    ifc_file = None
    for key, mod in sys.modules.items():
        if isinstance(mod, types.ModuleType) and key.endswith('.bim.ifc') and hasattr(mod, 'IfcStore'):
            ifc_file = mod.IfcStore.get_file()
            break

    if not ifc_file:
        print("[rename_spaces] No IFC file loaded, skipping.")
        return

    space_objects = [obj for obj in bpy.data.objects if "IfcSpace" in obj.name]
    print(f"[rename_spaces] IfcSpace objects found in scene: {len(space_objects)}")

    renamed = 0
    for obj in space_objects:
        bim_props = getattr(obj, 'BIMObjectProperties', None)
        ifc_id = getattr(bim_props, 'ifc_definition_id', 0)
        if not ifc_id:
            if debug:
                print(f"[rename_spaces]  '{obj.name}': no ifc_definition_id, skipping.")
            continue

        element = ifc_file.by_id(ifc_id)
        if not element:
            if debug:
                print(f"[rename_spaces]  '{obj.name}': element id={ifc_id} not found.")
            continue

        label = getattr(element, 'LongName', None) or getattr(element, 'ObjectType', None)
        if not label:
            if debug:
                print(f"[rename_spaces]  '{obj.name}': no LongName or ObjectType, skipping.")
            continue

        if not obj.name.endswith(f" - {label}"):
            old_name = obj.name
            obj.name = f"{obj.name} - {label}"
            if debug:
                print(f"[rename_spaces]  '{old_name}' → '{obj.name}'")
            renamed += 1

    print(f"[rename_spaces] Renamed {renamed} of {len(space_objects)} IfcSpace object(s).")


def _mesh_centroid_xy(obj):
    """Return (cx, cy) of object mesh vertices in world space, or None if no mesh."""
    mesh = getattr(obj, 'data', None)
    if not mesh or not hasattr(mesh, 'vertices') or not mesh.vertices:
        return None
    mat = obj.matrix_world
    total_x = total_y = 0.0
    count = len(mesh.vertices)
    for v in mesh.vertices:
        wco = mat @ v.co
        total_x += wco.x
        total_y += wco.y
    return total_x / count, total_y / count


def rename_floors_with_space_type():
    """Rename objects in the Floors collection by matching each slab to its nearest
    IfcSpace Blender object using the mesh vertex centroid in world space.
    All IFC placements are at origin (0,0,0); real geometry is in mesh vertices.
    Relies on rename_spaces_with_long_name() having run first.
    E.g. 'IfcSlab/Floor_001' → 'IfcSlab/Floor_001 - parkingSpot'
    """
    debug = _debug_mode()

    floors_coll = bpy.data.collections.get("Floors")
    if not floors_coll:
        print("[rename_floors] 'Floors' collection not found, skipping.")
        return

    # Collect renamed IfcSpace objects with their mesh centroid XY
    space_positions = []
    for obj in bpy.data.objects:
        if "IfcSpace" not in obj.name or " - " not in obj.name:
            continue
        label = obj.name.rsplit(" - ", 1)[1]
        centroid = _mesh_centroid_xy(obj)
        if centroid:
            space_positions.append((centroid[0], centroid[1], label))

    print(f"[rename_floors] Objects in 'Floors' collection: {len(floors_coll.objects)}")
    print(f"[rename_floors] IfcSpace objects with mesh centroid: {len(space_positions)}")

    if not space_positions:
        print("[rename_floors] No space centroids found — run 'Renaming spaces' step first.")
        return

    renamed = 0
    for obj in floors_coll.objects:
        slab_centroid = _mesh_centroid_xy(obj)
        if not slab_centroid:
            continue
        sx, sy = slab_centroid

        best_label = None
        min_dist_sq = float('inf')
        for (px, py, label) in space_positions:
            d = (sx - px) ** 2 + (sy - py) ** 2
            if d < min_dist_sq:
                min_dist_sq = d
                best_label = label

        if not best_label:
            continue

        if debug:
            print(f"[rename_floors]  '{obj.name}' → '{best_label}' (dist={min_dist_sq**0.5:.3f}m)")

        if not obj.name.endswith(f" - {best_label}"):
            obj.name = f"{obj.name} - {best_label}"
            renamed += 1

    print(f"[rename_floors] Renamed {renamed} of {len(floors_coll.objects)} floor object(s).")


def unhide_ifc_spaces():
    """Unhide all IfcSpace objects that Bonsai imports hidden by default.
    UNUSED: not called anywhere in the active pipeline. Kept as utility.
    Original intent: Bonsai imports IfcSpace with hide_viewport=True by default.
    Unhide them so they can be selected and interacted with.
    The Space collection itself stays visible; individual object hide flags are cleared.
    """
    count = 0
    for obj in bpy.data.objects:
        if "IfcSpace" in obj.name and (obj.hide_viewport or obj.hide_get()):
            obj.hide_viewport = False
            obj.hide_set(False)
            count += 1
    print(f"[spaces] Unhid {count} IfcSpace object(s)")


def move_objects_to_new_collection(keyword, collection_name, new_collection_name):
    """Move objects whose name contains `keyword` from `collection_name` into `new_collection_name`.
    Creates the target collection if it doesn't exist. Used in Step 2 to sort IFC types
    (e.g. 'IfcDoor/' from 'ifc' into 'Doors').
    """
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
            if _debug_mode():
                print(f"Moved object: {obj_name} to collection: {new_collection_name}") 


def move_slabs_separate_ceiling(source_collection_name="ifc", floor_collection_name="Floors", ceiling_collection_name="Ceiling"):
    """
    Sort IfcSlab objects in source_collection into two groups by Z-height:
      - Lower Z cluster  → floor_collection_name   (Floors)
      - Upper Z cluster  → ceiling_collection_name  (Ceiling)

    Detection: all IfcSlab objects are grouped into Z-level clusters (world space,
    30 cm tolerance). The topmost cluster is ceiling, everything else is floor.
    """
    source = bpy.data.collections.get(source_collection_name)
    if not source:
        print(f"[ceiling] Collection '{source_collection_name}' not found.")
        return

    slab_objs = [obj for obj in source.objects if "IfcSlab" in obj.name]
    if not slab_objs:
        print("[ceiling] No IfcSlab objects found in ifc collection.")
        return

    # World-space Z centre of each slab's bounding box
    def _z_center(obj):
        corners = [obj.matrix_world @ mathutils.Vector(c) for c in obj.bound_box]
        zs = [c.z for c in corners]
        return (min(zs) + max(zs)) / 2.0

    z_by_name = {obj.name: _z_center(obj) for obj in slab_objs}

    # Cluster Z values: sort, then group values within 0.3 m of each other
    sorted_z = sorted(set(z_by_name.values()))
    clusters = []
    current = [sorted_z[0]]
    for z in sorted_z[1:]:
        if z - current[-1] <= 0.3:
            current.append(z)
        else:
            clusters.append(current)
            current = [z]
    clusters.append(current)

    # Topmost cluster → ceiling; everything below → floor
    ceiling_z_min = min(clusters[-1])
    if _debug_mode():
        print(f"[ceiling] Z clusters: {[round(c[0],2) for c in clusters]}  |  ceiling threshold ≥ {ceiling_z_min:.2f} m")

    floors = bpy.data.collections.get(floor_collection_name)
    if not floors:
        floors = bpy.data.collections.new(floor_collection_name)
        bpy.context.scene.collection.children.link(floors)

    ceiling = bpy.data.collections.get(ceiling_collection_name)
    if not ceiling:
        ceiling = bpy.data.collections.new(ceiling_collection_name)
        bpy.context.scene.collection.children.link(ceiling)

    moved_floor, moved_ceiling = 0, 0
    for obj in slab_objs:
        z = z_by_name[obj.name]
        source.objects.unlink(obj)
        if z >= ceiling_z_min - 0.01:
            if not any(o is obj for o in ceiling.objects):
                ceiling.objects.link(obj)
            if _debug_mode():
                print(f"  [ceiling] → Ceiling: {obj.name}  (Z={z:.2f})")
            moved_ceiling += 1
        else:
            if not any(o is obj for o in floors.objects):
                floors.objects.link(obj)
            if _debug_mode():    
                print(f"  [floor]   → Floors:  {obj.name}  (Z={z:.2f})")
            moved_floor += 1

    print(f"[ceiling] Done — {moved_floor} → '{floor_collection_name}', {moved_ceiling} → '{ceiling_collection_name}'")



######################################################################################################


def create_glass_material():
    """Create a Principled BSDF glass material named 'Windows' with transmission=1, roughness=0.
    Always creates a new material (does not check for existing). Called by assign_collection_materials.
    """
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
    """Create a new Principled BSDF material with the given name, RGBA base_color, and roughness.
    Always creates a new datablock — does not reuse an existing material with the same name.
    Use assign_collection_materials._get_or_create() when idempotency is needed.
    """
    material = bpy.data.materials.new(name=material_name)
    material.use_nodes = True

    # Get the Principled BSDF node
    principled_bsdf = material.node_tree.nodes["Principled BSDF"]

    # Set the base color (RGB)
    principled_bsdf.inputs['Base Color'].default_value = base_color

    # Set specular
    #principled_bsdf.inputs['Specular'].default_value = specular

    # Set roughness
    principled_bsdf.inputs['Roughness'].default_value = roughness

    if _debug_mode():
        print(f"Created material: {material_name}")
    return material

#color helper
# credtis to https://gist.github.com/CGArtPython

def hex_color_to_rgba(hex_color):
    """Convert a 6-digit hex color string (e.g. 'E0E9F2') to a linear-RGB (R, G, B, 1.0) tuple.
    Applies sRGB→linear conversion so colors appear correct in Cycles.
    """
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
    """Convert a single sRGB channel value [0..1] to linear RGB using the IEC 61966-2-1 formula.
    Used by hex_color_to_rgba to produce physically-correct material colors.
    """
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
    print("Remove all old materials and create a material per folder")

    # All material names that are explicitly defined below — these are never deleted
    HARDCODED_NAMES = {
        "Floor_pale_dark_blue", "Floor_pale_red", "Floor_pale_orange",
        "Floor_pale_light_green", "Floor_pale_light_blue", "Floors_parkingSpot",
        "ifc", "Floor", "Doors", "Windows", "printer", "Storage", "Locker",
        "Bathroom", "Furnish_tables",
    }

    # Remove only auto-generated materials (not the hardcoded ones)
    for mat in list(bpy.data.materials):
        if mat.name not in HARDCODED_NAMES:
            bpy.data.materials.remove(mat, do_unlink=True)

    def _get_or_create(name, create_fn):
        """Return existing material if already present, otherwise create it."""
        existing = bpy.data.materials.get(name)
        return existing if existing else create_fn()

    # Custom floor zone materials
    _get_or_create("Floor_pale_dark_blue",  lambda: create_material("Floor_pale_dark_blue",  hex_color_to_rgba("E0E9F2"), 0, 0.1))
    _get_or_create("Floor_pale_red",        lambda: create_material("Floor_pale_red",        hex_color_to_rgba("F8E0E4"), 0, 0.1))
    _get_or_create("Floor_pale_orange",     lambda: create_material("Floor_pale_orange",     hex_color_to_rgba("FDEFD9"), 0, 0.1))
    _get_or_create("Floor_pale_light_green",lambda: create_material("Floor_pale_light_green",hex_color_to_rgba("E0EED2"), 0, 0.1))
    _get_or_create("Floor_pale_light_blue", lambda: create_material("Floor_pale_light_blue", hex_color_to_rgba("E0F2F9"), 0, 0.1))
    _get_or_create("Floors_parkingSpot",    lambda: create_material("Floors_parkingSpot",    hex_color_to_rgba("C7C6C6"), 0, 0.1))

    # Per-collection materials
    materials = {
        "ifc":           _get_or_create("ifc",           lambda: create_material("ifc",           (0.8, 0.8, 0.8, 1), 0, 0.1)),
        "Floor":         _get_or_create("Floor",         lambda: create_material("Floor",         (1, 1, 1, 1),       0, 0.0)),
        "Doors":         _get_or_create("Doors",         lambda: create_material("Doors",         (0.65, 0.65, 0.65, 1), 0.8, 0.1)),
        "Windows":       _get_or_create("Windows",       lambda: create_glass_material()),
        "printer":       _get_or_create("printer",       lambda: create_material("printer",       (0.75, 0.75, 0.75, 1), 0.8, 0.1)),
        "Storage":       _get_or_create("Storage",       lambda: create_material("Storage",       (0.75, 0.75, 0.75, 1), 0.8, 0.1)),
        "Locker":        _get_or_create("Locker",        lambda: create_material("Locker",        (0.75, 0.75, 0.75, 1), 0.8, 0.1)),
        "Bathroom":      _get_or_create("Bathroom",      lambda: create_material("Bathroom",      (0.75, 0.75, 0.75, 1), 0.8, 0.1)),
        "Furnish_tables":_get_or_create("Furnish_tables",lambda: create_material("Furnish_tables",(1, 1, 1, 1),       0, 0.0)),
    }

    # Assign materials to collections
    for coll in bpy.data.collections:
        if coll.name in materials:
            material = materials[coll.name]
        else:
            material = bpy.data.materials.new(name=coll.name)
            material.diffuse_color = (0.8, 0.8, 0.8, 1.0)
            if _debug_mode():
                print(f"Created material: {coll.name}")

        for obj in coll.objects:
            if obj.type == 'MESH':
                obj.data.materials.clear()
                obj.data.materials.append(material)
        

def hide_collection(collection_name):
    """Hide a collection from both viewport and render by name. Silently skips if not found."""
    if collection := bpy.data.collections.get(collection_name):
        collection.hide_viewport = True
        collection.hide_render = True
    else:
        print(f"Collection '{collection_name}' not found.")

def setup_hdri():
    """Set up the world HDRI lighting using startup.hdr from the addon's hdri/ folder.
    Builds a TexCoord → Mapping → EnvironmentTexture → Background → WorldOutput node chain.
    Called by ESEC_OT_setup_renderer.
    """
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

def setup_camera():
    """Create / replace the top-down camera matching the KeyShot camera spec:
    - Perspective, 50 mm focal length  → FOV ≈ 39.6° (matches KeyShot 39.598°)
    - Top-down (elevation 90°), azimuth -90° (Z rotation)
    - Height auto-calculated so the entire ifc/Structure collection fits in frame.
    Camera is placed inside the '_Studio' collection (created if missing).
    """
    scene = bpy.context.scene

    # --- Get or create the _Studio collection at the scene root ---
    studio = bpy.data.collections.get("_Studio")
    if not studio:
        studio = bpy.data.collections.new("_Studio")
        scene.collection.children.link(studio)
        print("[camera] Created '_Studio' collection")

    # Remove any existing Camera objects (from any collection)
    for obj in list(bpy.data.objects):
        if obj.type == 'CAMERA':
            bpy.data.objects.remove(obj, do_unlink=True)

    # Create camera with 50 mm lens (= 39.6° horizontal FOV on a 36 mm sensor)
    camera_data = bpy.data.cameras.new(name="Camera")
    camera_data.lens = 50          # focal length in mm
    camera_data.sensor_width = 36  # full-frame sensor
    camera_data.type = 'PERSP'

    camera = bpy.data.objects.new('Camera', camera_data)
    studio.objects.link(camera)    # place camera inside _Studio
    scene.camera = camera

    # --- Collect all mesh objects from the ifc / Structure collection ---
    source_collections = ['ifc', 'Walls', 'Floors', 'Structure']
    mesh_objects = []
    for coll_name in source_collections:
        coll = bpy.data.collections.get(coll_name)
        if coll:
            for obj in coll.objects:
                if obj.type == 'MESH':
                    mesh_objects.append(obj)

    # Fallback: use all mesh objects in the scene
    if not mesh_objects:
        mesh_objects = [o for o in scene.objects if o.type == 'MESH']

    if not mesh_objects:
        print("[camera] No mesh objects found — camera placed at (0, 0, 20)")
        camera.location = (0, 0, 20)
        camera.rotation_euler = (0, 0, math.radians(-90))
        return

    # Calculate world-space bounding box of all collected objects
    bm = bmesh.new()
    for obj in mesh_objects:
        for corner in obj.bound_box:
            bm.verts.new(obj.matrix_world @ Vector(corner))
    bm.verts.ensure_lookup_table()

    xs = [v.co.x for v in bm.verts]
    ys = [v.co.y for v in bm.verts]
    zs = [v.co.z for v in bm.verts]
    bm.free()

    center_x = (min(xs) + max(xs)) / 2
    center_y = (min(ys) + max(ys)) / 2
    scene_w   = max(xs) - min(xs)
    scene_h   = max(ys) - min(ys)
    scene_top = max(zs)

    # Camera height: fit the wider scene dimension inside the FOV
    # Use a 10 % margin so geometry isn't clipped at frame edges
    half_fov = camera_data.angle / 2   # horizontal FOV in radians
    # For top-down, the longer ground dimension must fit horizontally
    # aspect ratio correction: vertical FOV = 2*atan(tan(hFOV/2) / aspect)
    aspect = scene.render.resolution_x / scene.render.resolution_y
    half_fov_v = math.atan(math.tan(half_fov / 2) / aspect)
    dist_from_w = (scene_w / 2 * 1.10) / math.tan(half_fov / 2)
    dist_from_h = (scene_h / 2 * 1.10) / math.tan(half_fov_v)
    camera_distance = max(dist_from_w, dist_from_h)

    # Top-down: camera above center, rotation (0,0) = looks straight down.
    # Z rotation = azimuth -90° as specified in the KeyShot camera settings.
    camera.location = (center_x, center_y, scene_top + camera_distance)
    camera.rotation_euler = (0.0, 0.0, math.radians(-90))

    print(f"[camera] Positioned at Z={camera.location.z:.1f} m, covering {scene_w:.1f} x {scene_h:.1f} m scene")



def setup_render():
    """Configure Cycles render settings to match the KeyShot reference output:
    3840x2004 @ 300 dpi, PNG+alpha, 512 samples, Gaussian filter 1.5 px, GPU.
    """
    scene = bpy.context.scene

    # Engine + device
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'GPU'

    # Resolution  (3840 x 2004, 300 dpi)
    scene.render.resolution_x = 3840
    scene.render.resolution_y = 2004
    scene.render.resolution_percentage = 100

    # Output format — PNG with alpha channel
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGBA'
    scene.render.image_settings.compression = 15   # light lossless compression

    # Samples
    scene.cycles.samples = 512
    scene.cycles.use_adaptive_sampling = False

    # Pixel filter (Gaussian 1.5 px — matches KeyShot pixel filter size 1.5)
    scene.cycles.pixel_filter_type = 'GAUSSIAN'
    scene.cycles.filter_width = 1.5

    # Transparent background so the PNG alpha channel is meaningful
    scene.render.film_transparent = True
    scene.cycles.film_transparent_glass = True

    # Switch the viewport shading to Rendered
    for area in bpy.context.screen.areas:
        if area.type == 'VIEW_3D':
            for space in area.spaces:
                if space.type == 'VIEW_3D':
                    space.shading.type = 'RENDERED'


    print("[render] Cycles render settings applied: 3840x2004, 512 samples, Gaussian 1.5")
    

def render_scene(resolution_x, resolution_y):
    """Render the scene to a PNG file.

    Output path priority:
      1. Next to the saved .blend file (bpy.data.filepath)
      2. Next to the currently loaded Bonsai IFC file (BIMProperties.ifc_file)
      3. ~/Downloads/  (cross-platform fallback when nothing is saved)

    Output filename: <source_stem>_3D-render_<W>x<H>.png
    Called by ESEC_OT_render with 3840x2004.
    """
    import sys
    from pathlib import Path

    scene = bpy.context.scene

    # --- Render settings ---
    scene.render.engine = 'CYCLES'
    scene.render.image_settings.file_format = 'PNG'
    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.resolution_percentage = 100

    # --- Resolve output directory and base filename ---
    directory = None
    stem = "render"

    # 1. Try saved .blend file location
    blend_path = bpy.data.filepath
    if blend_path:
        directory = os.path.dirname(blend_path)
        stem = os.path.splitext(os.path.basename(blend_path))[0]
        print(f"[render] Using .blend path: {directory}")

    # 2. Fall back to Bonsai IFC file location
    if not directory:
        try:
            ifc_path = scene.BIMProperties.ifc_file
            if ifc_path and os.path.isfile(ifc_path):
                directory = os.path.dirname(ifc_path)
                stem = os.path.splitext(os.path.basename(ifc_path))[0]
                print(f"[render] Using IFC path: {directory}")
        except Exception:
            pass

    # 3. Fall back to ~/Downloads (cross-platform)
    if not directory:
        if sys.platform == "win32":
            downloads = Path.home() / "Downloads"
        elif sys.platform == "darwin":
            downloads = Path.home() / "Downloads"
        else:
            # XDG or plain ~/Downloads on Linux
            xdg = os.environ.get("XDG_DOWNLOAD_DIR")
            downloads = Path(xdg) if xdg else Path.home() / "Downloads"
        downloads.mkdir(parents=True, exist_ok=True)
        directory = str(downloads)
        print(f"[render] No saved file found — using Downloads folder: {directory}")

    filename = f"{stem}_3D-render_{resolution_x}x{resolution_y}"
    scene.render.filepath = os.path.join(directory, filename)

    # --- Camera ---
    if 'Camera' in bpy.data.objects:
        scene.camera = bpy.data.objects['Camera']
    else:
        print("[render] No camera found in scene.")
        return

    print(f"[render] Rendering to: {scene.render.filepath}")
    bpy.ops.render.render(write_still=True)

    global _last_render_path
    _last_render_path = scene.render.filepath + ".png"
    print(f"[render] Done: {_last_render_path}")




def organize_collections():
    """Group all scene collections into the two top-level parents: Structure and Assets.
    - Removes empty collections first.
    - Creates Structure/Assets parents if missing.
    - Moves known IFC collections (Floors, Doors, Walls, etc.) under Structure.
    - Moves furniture/asset collections (tables, chairs, Furnish_* etc.) under Assets.
    Called as a processing step and via ESEC_OT_organize_collections button.
    """
    # Remove empty collections — but never touch _Studio (may be empty before setup_renderer runs)
    for collection in list(bpy.data.collections):
        if collection.name == "_Studio":
            continue
        if len(collection.objects) == 0 and len(collection.children) == 0:
            bpy.data.collections.remove(collection)

    # Create 'Structure', and 'Assets' collections if they don't exist
    structure_collection = bpy.data.collections.get('Structure')
    if not structure_collection:
        structure_collection = bpy.data.collections.new('Structure')
        bpy.context.scene.collection.children.link(structure_collection)


    assets_collection = bpy.data.collections.get('Assets')
    if not assets_collection:
        assets_collection = bpy.data.collections.new('Assets')
        bpy.context.scene.collection.children.link(assets_collection)

    # List of collections to move to 'Structure'
    structure_collections = [
        'ifc', 'Floors', 'Ceiling', 'Doors', 'Windows', 'floors_intersect', 'Parking',
        'Space', 'Stair', 'Railing', 'Walls', 'Column', 'IfcElementAssembly', 'Spaces',
    ]


    # List of collections to move to 'Assets'
    asset_collections = ['tables', 'Office_chairs', 'Dining_chairs', 'Arm_chairs', 'Bar_Stools', 'printer', 
                         'Sofas', 'outdoor_bench', 'outdoor_chair', 'Storage', 'Sideboard', 'Bathroom', 
                         'closets', 'Genericsideboard', 'Locker', 'RollingContainer', 'Furnish' 
                         ]

    # Move collections to 'Structure'
    for col_name in structure_collections:
        if collection := bpy.data.collections.get(col_name):
            if collection.name in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.unlink(collection)
            if collection.name not in structure_collection.children:
                structure_collection.children.link(collection)


    # Move collections to 'Assets' (static list + any dynamic Furnish_* collections)
    dynamic_furnish = [c.name for c in bpy.data.collections if c.name.startswith("Furnish_")]
    for col_name in asset_collections + dynamic_furnish:
        if collection := bpy.data.collections.get(col_name):
            if collection.name in bpy.context.scene.collection.children:
                bpy.context.scene.collection.children.unlink(collection)
            if collection.name not in assets_collection.children:
                assets_collection.children.link(collection)


   

def reduce_scale():
    # Store names — Bonsai may rebuild mesh objects after origin_set,
    # making Python references stale. Look objects up fresh by name in loop 2.
    selected_names = [obj.name for obj in bpy.context.selected_objects if obj.type == 'MESH']
    prev_active = bpy.context.view_layer.objects.active
    print(f"[reduce_scale] {len(selected_names)} mesh object(s) selected")

    # Loop 1: fix origins where needed
    origins_fixed = set()
    for name in selected_names:
        obj = bpy.data.objects.get(name)
        if not obj or not obj.data or not getattr(obj.data, 'vertices', None):
            continue
        local_centroid = sum((v.co for v in obj.data.vertices), Vector()) / len(obj.data.vertices)
        centroid_dist = local_centroid.length
        if _debug_mode():
            print(f"[reduce_scale] L1  '{name}'  centroid dist={centroid_dist:.4f}")
        if centroid_dist > 0.001:
            bpy.ops.object.select_all(action='DESELECT')
            obj.select_set(True)
            bpy.context.view_layer.objects.active = obj
            bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
            origins_fixed.add(name)
            if _debug_mode():
                print(f"[reduce_scale] L1  '{name}'  → origin_set applied")

    # Loop 2: shrink vertex positions directly — avoids Bonsai's scale→IFC sync
    # which fails for parametric slabs and reverts on KeyShot export.
    for name in selected_names:
        obj = bpy.data.objects.get(name)
        if not obj or not obj.data or not getattr(obj.data, 'vertices', None):
            if _debug_mode():
                print(f"[reduce_scale] L2  '{name}': object not found or no mesh")
            continue
        vert_count = len(obj.data.vertices)
        for v in obj.data.vertices:
            v.co.x *= 0.90
            v.co.y *= 0.90
        obj.data.update()
        obj.location.z = -1
        if _debug_mode():
            print(f"[reduce_scale] L2  '{name}'  scaled {vert_count} vertices by 0.95 XY, Z set to -0.5  (origin_fixed={name in origins_fixed})")

    # Restore selection
    bpy.ops.object.select_all(action='DESELECT')
    for name in selected_names:
        obj = bpy.data.objects.get(name)
        if obj:
            obj.select_set(True)
    if prev_active:
        bpy.context.view_layer.objects.active = prev_active
         