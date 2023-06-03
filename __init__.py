from .bl_info_module import bl_info
from . import properties
from . import ui
from . import esec_dxf_ifc_TI_helper
from . import esec_archiologic_importer



import bpy

#
# Add additional functions here
#

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

