bl_info = {
    "name": "ESEC SensorPlan Pro",
    "author": "stefan.knaak@e-shelter.io",
    "version": (1, 1),
    "blender": (3, 5, 0),
    "location": "View3D > Sidebar > ESEC Tab",
    "description": "Add to place Sensors or any other devices on a map.",
    "warning": "",
    "wiki_url": "",
    "category": "3D View",
}

import bpy
import os
import json
import bmesh
from bpy_extras.view3d_utils import region_2d_to_location_3d
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector
import math

keymap_items = []  # Track keymap items to remove them later

def update_sensor_type_color(self, context):
    # Find the material corresponding to this sensor type
    mat_name = f"{self.name}_Material"
    mat = bpy.data.materials.get(mat_name)

    if mat:
        # If the material exists, update its color
        mat.diffuse_color = self.color

# Mark the register_keymaps function as persistent so it isn't removed after file load
@persistent
def load_handler(dummy):
    bpy.app.timers.register(register_keymaps, first_interval=1.0)

def copy_sensor_counts_to_clipboard():
    # Check if the file is saved and get the filename, otherwise indicate it's unsaved
    file_path = bpy.data.filepath
    if file_path:
        filename = os.path.basename(file_path)
    else:
        filename = "Unsaved File"

    sensor_counts = count_sensors()
    sensor_info = [f"Filename: {filename}"]  # Start the info with the filename
    for sensor_type_name, count in sensor_counts.items():
        if count > 0:
            sensor_info.append(f"{sensor_type_name}: {count}")
    sensor_info_str = "\n".join(sensor_info)
    
    bpy.context.window_manager.clipboard = sensor_info_str
    print("Sensor counts (and filename) copied to clipboard.")


def count_sensors():
    sensor_counts = {}
    for sensor_type in bpy.context.scene.sensor_types:
        collection_name = sensor_type.name
        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]
            # Count only objects that are not children of another object in the same collection
            primary_sensors = [obj for obj in collection.objects if not obj.parent or obj.parent.name not in collection.objects]
            sensor_counts[collection_name] = len(primary_sensors)
    return sensor_counts

def create_device(x, y, sensor_type_name, color=(0.5, 0.0, 0.5, 1), shape='CIRCLE', device_number=1):

    # Retrieve the global scale factor
    scale_factor = bpy.context.scene.esec_sensor_plan_properties.scale_factor

    # Find the highest existing suffix for the given sensor type
    highest_suffix = 0
    for obj in bpy.data.objects:
        if obj.name.startswith(sensor_type_name + "_"):
            suffix = obj.name.replace(sensor_type_name + "_", "")
            if suffix.isdigit() and int(suffix) > highest_suffix:
                highest_suffix = int(suffix)


    # Determine the name for the new object, starting with .001 suffix
    new_suffix = str(highest_suffix + 1).zfill(3)
    device_name = f"{sensor_type_name}_{new_suffix}"

    mesh = bpy.data.meshes.new(name=device_name)
    obj = bpy.data.objects.new(name=device_name, object_data=mesh)

    bm = bmesh.new()
    print(shape)
    if shape == 'CIRCLE':
        bmesh.ops.create_circle(bm, cap_ends=True, radius=1.0, segments=32)
    elif shape == 'SQUARE':
        # Create a cube which by default has equal dimensions on all sides
        bmesh.ops.create_cube(bm, size=2.0)  # This creates a cube with a 'size' of 2.0 in all dimensions
        # After creation, we need to adjust the scale to match the desired "height" for consistency with the circle
    elif shape == 'DIAMOND':
        bmesh.ops.create_cube(bm, size=2.0)  # Start with a cube for simplicity
        # Rotate the cube 45 degrees around the Z-axis to create a diamond shape
        bmesh.ops.rotate(bm, verts=bm.verts, cent=(0.0, 0.0, 0.0), matrix=Matrix.Rotation(math.radians(45.0), 3, 'Z'))
    elif shape == 'HEXAGON':
        # Create a flat hexagon with 6 segments
        bmesh.ops.create_circle(bm, cap_ends=True, radius=1.0, segments=6)  # Hexagon shape

    # Common transformation for all polygonal shapes (SQUARE, DIAMOND, HEXAGON)
    if shape in {'SQUARE', 'DIAMOND', 'HEXAGON'}:
        for vert in bm.verts:
            vert.co.z *= 0.005  # Adjust the Z scale for flat shape

    bm.to_mesh(mesh)
    bm.free()

    # Check if the material already exists
    mat_name = f"{sensor_type_name}_Material"
    mat = bpy.data.materials.get(mat_name)

    if not mat:
        # If the material does not exist, create it
        mat = bpy.data.materials.new(name=mat_name)
        mat.diffuse_color = color

    # Assign the material to the object
    if len(obj.data.materials):
        # Replace the first material
        obj.data.materials[0] = mat
    else:
        # Add new material
        obj.data.materials.append(mat)

    obj.location = (x, y, 0.0001)
    obj.scale = (0.005 * scale_factor, 0.005 * scale_factor, 0.005 * scale_factor)

    if sensor_type_name not in bpy.data.collections:
        sensor_collection = bpy.data.collections.new(sensor_type_name)
        bpy.context.scene.collection.children.link(sensor_collection)
    else:
        sensor_collection = bpy.data.collections[sensor_type_name]

    sensor_collection.objects.link(obj)

    # Create a text object with the device number
    number = obj.name.split('_')[-1]  # Adjusted for your naming convention (underscore)

    # Create the text object at the same position as the shape
    bpy.ops.object.text_add(location=(0, 0, 0.009), scale=(0.005, 0.005, 0.005))
    text_obj = bpy.context.object

    # Parent the text object to the shape for organization
    text_obj.parent = obj
    text_obj.data.body = number  # Use the device number as the text

    # The text object's 'align_x' and 'align_y' properties control the text's alignment within its bounding box
    text_obj.data.align_x = 'CENTER'  # Center-align the text horizontally
    text_obj.data.align_y = 'CENTER'  # Center-align the text vertically

    # This can depend on the font size, the specific geometry of the shape, and other factors
    text_obj.location.z += 0.01  # Adjust the Z location slightly if necessary

    # Assign a white material to the text
    text_mat = bpy.data.materials.new(name="WhiteMaterial")
    text_mat.diffuse_color = (1, 1, 1, 1)  # RGBA for white
    text_obj.data.materials.append(text_mat)

    # Unlink the text object from the scene's active collection
    bpy.context.collection.objects.unlink(text_obj)

    # Instead, ensure the text object is linked to the same collection as the device
    sensor_collection.objects.link(text_obj)    


class CreateDeviceAtCursorOperator(bpy.types.Operator):
    """Place a device at the current mouse viewport position based on sensor type"""
    bl_idname = "view3d.device_create_at_cursor"
    bl_label = "Create Device at Cursor"
    bl_options = {'REGISTER', 'UNDO'}

    sensor_type_name: bpy.props.StringProperty()  # Directly use sensor type name

    def invoke(self, context, event):
        # Directly use the sensor_type_name to get color and shape
        sensor_types = context.scene.sensor_types
        sensor_type = next((st for st in sensor_types if st.name == self.sensor_type_name), None)

        # Convert mouse position to 3D space coordinates
        mouse_pos = (event.mouse_region_x, event.mouse_region_y)
        region = context.region
        rv3d = context.region_data
        location = region_2d_to_location_3d(region, rv3d, mouse_pos, (0, 0, 0.0001))        

        # from auto keymap
        if sensor_type is not None:            
            # Create the device with the properties of the chosen sensor type
            create_device(location[0], location[1], sensor_type.name, color=sensor_type.color, shape=sensor_type.shape)
        else:
            # from STRG+ALT+D
            scene = context.scene
            sensor_plan_props = scene.esec_sensor_plan_properties
            selected_sensor_type_name = sensor_plan_props.selected_sensor_type   

            self.report({'WARNING'}, f"{selected_sensor_type_name}")             

            # Find the sensor type properties
            for sensor_type in scene.sensor_types:
                if sensor_type.name == selected_sensor_type_name:
                    color = sensor_type.color
                    shape = sensor_type.shape
                    break

            else:
                self.report({'WARNING'}, "Selected sensor type not found.")
                return {'CANCELLED'}                
            
            # Create the device at this location with selected sensor type properties
            create_device(location[0], location[1], selected_sensor_type_name, color=color, shape=shape)
        
        return {'FINISHED'}
    
def load_sensor_types():
    file_path = bpy.path.abspath("//sensor_types.json")
    if not os.path.exists(file_path):
        return  # No saved data found
    
    with open(file_path, 'r') as infile:
        sensor_data = json.load(infile)
    
    sensor_types = bpy.context.scene.sensor_types
    sensor_types.clear()  # Clear existing items
    
    for sensor in sensor_data:
        new_type = sensor_types.add()
        new_type.name = sensor['name']
        new_type.color = sensor['color']
        new_type.shape = sensor['shape']



def sensor_type_items(self, context):
    items = [(sensor.name, sensor.name, "") for sensor in context.scene.sensor_types]
    if not items:
        items = [("NONE", "None available", "No sensors available")]
    return items

class ESEC_PG_SensorTypeItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Type Name", description="Unique type name for the sensor")
    color: bpy.props.FloatVectorProperty(
        name="Color",
        description="Color for the sensor type",
        subtype='COLOR',
        size=4,
        min=0.0,
        max=1.0,
        default=(0.5, 0.5, 0.5, 1.0),
        update=update_sensor_type_color
    )
    shape: bpy.props.EnumProperty(
        name="Shape",
        description="Shape of the sensor",
        items=[
            ('CIRCLE', "Circle", "Circular shape"),
            ('SQUARE', "Square", "Square shape"),
            ('DIAMOND', "Diamond", "Diamond shape"),
            ('HEXAGON', "Hexagon", "Hexagon shape"),
        ],
        default='CIRCLE'
    )

class ESEC_PG_SensorPlanProperties(bpy.types.PropertyGroup):
    selected_sensor_type: bpy.props.EnumProperty(
        name="Select Sensor Type",
        description="Choose a sensor type",
        items=sensor_type_items
    )
    show_sensor_types: bpy.props.BoolProperty(
        name="Show Sensor Types",
        description="Show or hide the sensor types management section",
        default=True  # Start expanded by default
    )

    scale_factor: bpy.props.FloatProperty(
        name="Scale Factor",
        description="Global scale factor for sensor shapes and text",
        default=1.0,
        min=0.1,
        max=100.0
    )

class ESEC_OT_add_sensor_type(bpy.types.Operator):
    """Add a new sensor type"""
    bl_idname = "esec.add_sensor_type"
    bl_label = "Add Sensor Type"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        sensor_types = context.scene.sensor_types
        new_type = sensor_types.add()
        new_type.name = "New Sensor Type"
        new_type.color = (1.0, 0.0, 0.0, 1.0)  # Default color, e.g., red
        new_type.shape = 'CIRCLE'  # Default shape
        return {'FINISHED'}

class ESEC_OT_remove_sensor_type(bpy.types.Operator):
    """Remove an existing sensor type"""
    bl_idname = "esec.remove_sensor_type"
    bl_label = "Remove Sensor Type"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()

    def execute(self, context):
        sensor_types = context.scene.sensor_types
        sensor_types.remove(self.index)
        return {'FINISHED'}

class ESEC_OT_save_sensor_types(bpy.types.Operator):
    """Save sensor types to a file"""
    bl_idname = "esec.save_sensor_types"
    bl_label = "Save Sensor Types"
    
    def execute(self, context):
        sensor_types = context.scene.sensor_types
        sensor_data = []
        for sensor in sensor_types:
            sensor_data.append({
                'name': sensor.name,
                'color': sensor.color[:],
                'shape': sensor.shape,
            })
        
        file_path = bpy.path.abspath("//sensor_types.json")
        with open(file_path, 'w') as outfile:
            json.dump(sensor_data, outfile, indent=4)
        
        self.report({'INFO'}, "Sensor types saved successfully.")
        return {'FINISHED'}

class ESEC_PT_SensorPlanMainPanel(bpy.types.Panel):
    bl_label = "ESEC SensorPlan Pro v"+ str(bl_info['version'])
    bl_idname = "ESEC_PT_SensorPlanMainPanel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ESEC'

    def draw(self, context):
        layout = self.layout

        sensor_counts = count_sensors()

        # Calculate total number of sensors
        total_sensors = sum(sensor_counts.values())

      # If there are any sensors, display the "Sensor Count" header and the counts for each sensor type
        if total_sensors > 0:
            layout.label(text="Sensor Count:")  # Display the header
            for sensor_type in context.scene.sensor_types:
                count = sensor_counts.get(sensor_type.name, 0)
                if count > 0:
                    # Create a row for each sensor type name and count
                    row = layout.row(align=True)
                    # Use a label for the sensor type name and count
                    row.label(text=f"{sensor_type.name}: {count}")
                    # Add a disabled property to display the color swatch
                    # We use a separate box to align the color swatch nicely next to the text
                    color_box = row.box()
                    color_box.ui_units_x = 0.8  # Adjust the size of the color swatch box as needed
                    color_box.prop(sensor_type, "color", text="")  # Display the color swatch
                    color_box.enabled = False  # Make it non-interactive

        scene = context.scene
        sensor_plan_props = scene.esec_sensor_plan_properties
        
        # Toggle button for showing/hiding the manage sensor types section
        layout.prop(sensor_plan_props, "show_sensor_types", icon="TRIA_DOWN" if sensor_plan_props.show_sensor_types else "TRIA_RIGHT", emboss=False, text="Manage Sensor Types")

        if sensor_plan_props.show_sensor_types:
            # Only draw the following UI elements if show_sensor_types is True
            box = layout.box()
            
            for i, sensor_type in enumerate(scene.sensor_types):
                row = box.row()
                row.prop(sensor_type, "name", text=f"{i + 1}")
                row.prop(sensor_type, "color", text="", icon_only=True, emboss=True)
                #row.label(text=f"{i + 1}")
                row.prop(sensor_type, "shape", text="")
                remove_op = row.operator("esec.remove_sensor_type", text="", icon='X')
                remove_op.index = i

            box.operator("esec.add_sensor_type", text="Add New Sensor Type", icon='ADD')
            box.operator("esec.save_sensor_types", text="Save Sensor Types", icon='FILE_TICK')
        
            layout.separator()
            # Input field for the global scale factor
            layout.prop(sensor_plan_props, 'scale_factor', text="Scale Factor")            

        layout.separator()
        # Button to update sensor naming
        layout.operator("esec.update_sensor_naming", text="Update Sensor Naming", icon='FILE_REFRESH')
        layout.operator(ESEC_OT_CopySensorCountsToClipboard.bl_idname, text="Copy Sensor Counts", icon='COPYDOWN')
        layout.separator()
        # Dropdown to select a sensor type
        layout.prop(scene.esec_sensor_plan_properties, 'selected_sensor_type', text="Sensor Type")
        layout.label(text="PRESS STRG+ALT+D to add a Sensor of the selected type")  
        layout.separator()
        layout.label(text="OR PRESS STRG+ALT+SHIFT+Number to add a Sensor directly")  

def register_keymaps():
    global keymap_items
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if not kc:
        return

    km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')

    # Number keys from 1 to 9
    number_keys = ['ONE', 'TWO', 'THREE', 'FOUR', 'FIVE', 'SIX', 'SEVEN', 'EIGHT', 'NINE']

    # Clear previously registered keymaps
    for item in keymap_items:
        km.keymap_items.remove(item)
    keymap_items.clear()

    # Register new keymaps for the first 9 sensor types
    sensor_types = bpy.context.scene.sensor_types
    for i, key in enumerate(number_keys):
        if i < len(sensor_types):  # Ensure there is a sensor type for the key
            sensor_type_name = sensor_types[i].name  # Get sensor type name by index
            # Register keymap with CTRL+ALT+SHIFT modifiers
            kmi = km.keymap_items.new(
                CreateDeviceAtCursorOperator.bl_idname,
                type=key, value='PRESS', ctrl=True, alt=True, shift=True)
            kmi.properties.sensor_type_name = sensor_type_name
            keymap_items.append(kmi)

    #single key for selected type: 
    kmi = km.keymap_items.new(CreateDeviceAtCursorOperator.bl_idname, type='D', value='PRESS', ctrl=True, alt=True)
       


def unregister_keymaps():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc:
        km = kc.keymaps.get('3D View')
        if km:
            for kmi in km.keymap_items:
                if kmi.idname == CreateDeviceAtCursorOperator.bl_idname:
                    km.keymap_items.remove(kmi)
                    break

def update_sensor_naming():
    for sensor_type in bpy.context.scene.sensor_types:
        collection_name = sensor_type.name
        if collection_name in bpy.data.collections:
            collection = bpy.data.collections[collection_name]

            # Filter objects that follow the expected "{Sensortypename}_###" format
            valid_objs = [obj for obj in collection.objects if obj.name.startswith(collection_name + "_") and obj.name[len(collection_name)+1:].isdigit()]

            # Sort these objects based on the numeric part of their names
            sorted_objs = sorted(valid_objs, key=lambda obj: int(obj.name[len(collection_name)+1:]))

            for i, obj in enumerate(sorted_objs, start=1):
                new_name_base = f"{collection_name}_{str(i).zfill(3)}"
                obj.name = new_name_base
                
                # Update the text object if it exists as the first child
                if obj.children:
                    text_obj = obj.children[0]  # Assuming the text object is the first child
                    # Ensure the text object's data is correctly targeted and exists
                    if hasattr(text_obj, "data") and hasattr(text_obj.data, "body"):
                        text_obj.data.body = str(i).zfill(3)  # Update the text to reflect the new number  
    count_sensors()                                         


class ESEC_OT_UpdateSensorNaming(bpy.types.Operator):
    """Update sensor naming to ensure sequential numbering"""
    bl_idname = "esec.update_sensor_naming"
    bl_label = "Update Sensor Naming"

    def execute(self, context):
        update_sensor_naming()
        count_sensors() 
        self.report({'INFO'}, "Sensor naming updated.")
        return {'FINISHED'}

class ESEC_OT_CopySensorCountsToClipboard(bpy.types.Operator):
    """Copy sensor counts to clipboard"""
    bl_idname = "esec.copy_sensor_counts_to_clipboard"
    bl_label = "Copy Sensor Counts"

    def execute(self, context):
        copy_sensor_counts_to_clipboard()
        self.report({'INFO'}, "Sensor counts copied to clipboard.")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(ESEC_PG_SensorTypeItem)
    bpy.utils.register_class(ESEC_PG_SensorPlanProperties)
    bpy.utils.register_class(ESEC_OT_add_sensor_type)
    bpy.utils.register_class(ESEC_OT_remove_sensor_type)
    bpy.utils.register_class(ESEC_OT_save_sensor_types)
    bpy.utils.register_class(ESEC_PT_SensorPlanMainPanel)
    bpy.utils.register_class(CreateDeviceAtCursorOperator)
    bpy.utils.register_class(ESEC_OT_UpdateSensorNaming)
    bpy.utils.register_class(ESEC_OT_CopySensorCountsToClipboard)
    
    bpy.types.Scene.sensor_types = bpy.props.CollectionProperty(type=ESEC_PG_SensorTypeItem)
    bpy.types.Scene.esec_sensor_plan_properties = bpy.props.PointerProperty(type=ESEC_PG_SensorPlanProperties)

    # Load sensor types from file
    bpy.app.timers.register(load_sensor_types) 
    bpy.app.handlers.load_post.append(load_handler)
   

def unregister():
    del bpy.types.Scene.sensor_types
    del bpy.types.Scene.esec_sensor_plan_properties
    
    bpy.utils.unregister_class(ESEC_PT_SensorPlanMainPanel)
    bpy.utils.unregister_class(ESEC_OT_save_sensor_types)
    bpy.utils.unregister_class(ESEC_OT_remove_sensor_type)
    bpy.utils.unregister_class(ESEC_OT_add_sensor_type)
    bpy.utils.unregister_class(ESEC_PG_SensorPlanProperties)
    bpy.utils.unregister_class(ESEC_PG_SensorTypeItem)
    bpy.utils.unregister_class(CreateDeviceAtCursorOperator)
    bpy.utils.unregister_class(ESEC_OT_UpdateSensorNaming)
    bpy.utils.unregister_class(ESEC_OT_CopySensorCountsToClipboard)

    if load_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_handler)
    unregister_keymaps()

if __name__ == "__main__":
    register()

