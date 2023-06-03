bl_info = {
    "name": "ESEC DXF-IFC 3D Floorplan Tool",
    "author": "stefan.knaak@e-shelter.io",
    "version": (1, 8, 6),
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

def get_version_string():
    version_tuple = bl_info['version']  # This will give you the version tuple, e.g. (1, 8, 6)
    version_string = '.'.join(str(number) for number in version_tuple)  # Convert to a string in the required format.
    return version_string

bl_info_version = get_version_string()
