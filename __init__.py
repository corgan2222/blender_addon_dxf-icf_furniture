from . import properties
from . import ui
from . import esec_dxf_ifc_TI_helper
from . import esec_archiologic_importer

bl_info = {
    "name": "ESEC DXF-IFC 3D Floorplan Tool",
    "author": "stefan.knaak@e-shelter.io",
    "version": (1, 8, 9),
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

def register():
    properties.register()
    ui.register()
    esec_dxf_ifc_TI_helper.register()
    esec_archiologic_importer.register()

def unregister():
    properties.unregister()
    ui.unregister()
    esec_dxf_ifc_TI_helper.unregister()
    esec_archiologic_importer.unregister()

if __name__ == '__main__':
    register()

