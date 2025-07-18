bl_info = {
    "name": "ESEC DXF-IFC 3D Floorplan Tool",
    "author": "stefan.knaak@e-shelter.io",
    "version": (1, 9, 13),
    "blender": (3, 5, 0),
    "location": "View3D > Sidebar > ESEC Tab",
    "description": "Create furniture like tables and chairs from a DXF plan, exported from Archiologic.",
    "warning": "",
    "doc_url": "https://github.com/corgan2222/blender_addon_dxf-icf_furniture",
    "category": "3D View",
    "wiki_url": "https://github.com/corgan2222/blender_addon_dxf-icf_furniture",
    "tracker_url": "https://github.com/corgan2222/blender_addon_dxf-icf_furniture/issues",
    "support": "COMMUNITY"    
}

from importlib import reload
version_text = '.'.join(map(str, bl_info["version"]))

#for hot reload of the addon from within Blender
if "bpy" in locals():
    print("Reloading ESEC Addons - " + version_text)
    properties = reload(properties)
    preferences = reload(preferences)
    ui = reload(ui)
    esec_dxf_ifc_TI_helper = reload(esec_dxf_ifc_TI_helper)
    esec_archiologic_importer = reload(esec_archiologic_importer)
    esec_sensor_plan_pro = reload(esec_sensor_plan_pro)
else:
    print("Loading ESEC Addons - " + version_text)
    from . import properties
    from . import preferences
    from . import ui    
    from . import esec_archiologic_importer
    from . import esec_sensor_plan_pro
    from . import esec_dxf_ifc_TI_helper

def register():
    properties.register()
    preferences.register()
    ui.register()
    esec_archiologic_importer.register()
    esec_sensor_plan_pro.register()
    esec_dxf_ifc_TI_helper.register()

def unregister():
    properties.unregister()
    preferences.unregister()    
    esec_archiologic_importer.unregister()
    esec_sensor_plan_pro.unregister()
    esec_dxf_ifc_TI_helper.unregister()
    ui.unregister()

if __name__ == '__main__':
    register()

