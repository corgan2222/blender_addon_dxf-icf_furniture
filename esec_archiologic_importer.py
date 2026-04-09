bl_info = {
    "name": "ESEC Archilogic Importer",
    "author": "stefan.knaak@e-shelter.io",
    "version": (2, 1, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > ESEC Tab",
    "description": "Import floors directly from Archilogic into Blender (list, download, import).",
    "warning": "",
    "category": "3D View",
}

import json
import os
import re
import tempfile
import traceback
from pathlib import Path

import bpy

# --------------------------------------------------------------------------------------
# Globals / helpers
# --------------------------------------------------------------------------------------

ADDON_ID = __package__ if __package__ else __name__
FLOOR_CACHE = []
ASSETS_CACHE = {}  # guid -> properties dict, populated on IFC import
_panel_auto_refreshed = False
_repopulate_scheduled = False

def _debug_mode():
    """Return True if the addon's debug_mode preference is enabled."""
    prefs = _get_prefs()
    return prefs.debug_mode if prefs else False

def _repopulate_from_cache():
    """Repopulate scene floor list from FLOOR_CACHE. Called via timer (outside draw context)."""
    global _repopulate_scheduled
    _repopulate_scheduled = False
    if not FLOOR_CACHE:
        return None
    try:
        items = bpy.context.scene.floor_list_items
        if items:
            return None  # Already populated, nothing to do
        for f in FLOOR_CACHE:
            fid = f.get("id") or f.get("properties", {}).get("id")
            props = f.get("properties", {}) if isinstance(f, dict) else {}
            name = props.get("name") or "(unnamed)"
            floor_no = props.get("floorNumber")
            label = name if not floor_no else f"{name}  [#{floor_no}]"
            if fid:
                item = items.add()
                item.floor_id = fid
                item.floor_name = label
        _log(f"Repopulated floor list from cache ({len(FLOOR_CACHE)} floors).")
    except Exception as e:
        _log(f"Cache repopulate error: {e}")
    return None

def _log(msg: str):
    """Print a prefixed log message to the Blender console."""
    print(f"[ESEC Archilogic] {msg}")

def _get_prefs():
    """Return the addon's ESECAddonPreferences (contains archiologic_token, etc.)."""
    return bpy.context.preferences.addons[ADDON_ID].preferences

def _headers(token: str):
    """Build the Authorization + Accept headers dict for Archilogic API calls."""
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }

def _ensure_gltf_importer_enabled():
    """Enable the built-in glTF importer addon if not already active.
    UNUSED: not called anywhere in the current version. Kept as fallback utility.
    """
    try:
        if "io_scene_gltf2" not in bpy.context.preferences.addons:
            bpy.ops.preferences.addon_enable(module="io_scene_gltf2")
    except Exception:
        _log("Could not enable io_scene_gltf2; attempting to import anyway.")

def _ensure_ifc_importer_enabled():
    """Check that Bonsai (or BlenderBIM) is installed and print a warning if not.
    Called before bpy.ops.bim.load_project to give an early, readable error.
    """
    try:
        import bonsai
        return
    except ImportError:
        pass
    try:
        import blenderbim
        return
    except ImportError:
        pass
    _log("IFC import requires the Bonsai Add-on. Please install/enable it from Blender Extensions.")

# --------------------------------------------------------------------------------------
# API calls
# --------------------------------------------------------------------------------------

def _status(context, text: str):
    """Write `text` to the Blender status bar and force a redraw so progress is visible mid-operator."""
    _log(text)
    try:
        context.workspace.status_text_set(text)
        bpy.ops.wm.redraw_timer(type='DRAW_WIN_SWAP', iterations=1)
    except Exception:
        pass

def _import_requests():
    """Import and return the `requests` library, raising a clear RuntimeError if not installed.
    Deferred import so the addon loads even when requests is missing (shows error only on use).
    """
    try:
        import requests
        return requests
    except Exception as e:
        raise RuntimeError(
            "The 'requests' package is required. Install it into Blender's Python "
            "(e.g., in Blender's Python console: `import pip, sys; "
            "pip.main([\"install\", \"requests\"])`)") from e

def _download_bytes(url: str, requests_module, retries: int = 5, timeout: int = 300) -> bytes:
    """Download URL content with retry. Raises RuntimeError after all attempts fail."""
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests_module.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            last_err = e
            _log(f"  Download attempt {attempt}/{retries} failed: {e}")
    raise RuntimeError(f"Download failed after {retries} attempts: {last_err}")

def api_list_floors(token: str, include_archived=False, limit=100):
    """GET /v2/floor — returns all features across pages."""
    requests = _import_requests()
    url = "https://api.archilogic.com/v2/floor"
    offset = 0
    all_features = []
    while True:
        params = {
            "geometry": "false",
            "includeCustomAttributes": "false",
            "includeArchived": "true" if include_archived else "false",
            "limit": str(limit),
            "offset": str(offset),
        }
        resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"List floors failed ({resp.status_code}): {resp.text}")
        payload = resp.json() or {}
        features = payload.get("features", [])
        all_features.extend(features)
        if not features or len(features) < limit:
            break
        offset += limit
    return all_features

def api_export_image(token: str, floor_id: str, fmt: str, dest_folder: Path, filename: str) -> Path:
    """POST /v2/floor/{id}/2d-image — download jpg, png or svg to dest_folder.
    Response returns 'imageUrl' (not downloadUrl)."""
    requests = _import_requests()
    url = f"https://api.archilogic.com/v2/floor/{floor_id}/2d-image"
    headers = _headers(token)
    headers["Content-Type"] = "application/json"
    r = requests.post(url, headers=headers, json={"format": fmt}, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"2D image ({fmt}) failed ({r.status_code}): {r.text}")
    image_url = (r.json() or {}).get("imageUrl")
    if not image_url:
        raise RuntimeError("2D image response missing 'imageUrl'.")
    content = _download_bytes(image_url, requests)
    out = dest_folder / f"{filename}.{fmt}"
    out.write_bytes(content)
    _log(f"  Saved {fmt}: {out}")
    return out

def api_export_to_folder(token: str, floor_id: str, kind: str, ext: str, dest_folder: Path, filename: str) -> Path:
    """POST /v2/floor/{id}/{kind} -> downloadUrl -> save file to dest_folder."""
    requests = _import_requests()
    r = requests.post(
        f"https://api.archilogic.com/v2/floor/{floor_id}/{kind}",
        headers=_headers(token), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Export {kind.upper()} failed ({r.status_code}): {r.text}")
    dl = (r.json() or {}).get("downloadUrl")
    if not dl:
        raise RuntimeError(f"Export {kind.upper()} response missing 'downloadUrl'.")
    content = _download_bytes(dl, requests)
    out = dest_folder / f"{filename}.{ext}"
    out.write_bytes(content)
    _log(f"  Saved {kind}: {out}")
    return out

def api_get_assets(token: str, floor_id: str, limit: int = 100) -> list:
    """GET /v2/asset?floorId={id} — returns all asset features across pages."""
    requests = _import_requests()
    url = "https://api.archilogic.com/v2/asset"
    offset = 0
    all_features = []
    while True:
        params = {
            "floorId": floor_id,
            "geometry": "false",
            "includeCustomAttributes": "false",
            "limit": str(limit),
            "offset": str(offset),
        }
        resp = requests.get(url, headers=_headers(token), params=params, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(f"Get assets failed ({resp.status_code}): {resp.text}")
        payload = resp.json() or {}
        features = payload.get("features", [])
        all_features.extend(features)
        if not features or len(features) < limit:
            break
        offset += limit
    return all_features


def api_export_and_download_format(token: str, floor_id: str, kind: str, target_ext: str) -> Path:
    """POST /v2/floor/{id}/{kind} -> downloadUrl -> temp file. Handles ZIP."""
    requests = _import_requests()
    r = requests.post(
        f"https://api.archilogic.com/v2/floor/{floor_id}/{kind}",
        headers=_headers(token), timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Export {kind.upper()} failed ({r.status_code}): {r.text}")
    dl = (r.json() or {}).get("downloadUrl")
    if not dl:
        raise RuntimeError(f"Export {kind.upper()} response did not include 'downloadUrl'.")

    tmp_dir = Path(tempfile.gettempdir()) / "archilogic_blender"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    with requests.get(dl, stream=True, timeout=300) as resp:
        resp.raise_for_status()
        iter_chunks = resp.iter_content(chunk_size=8192)
        try:
            first_chunk = next(iter_chunks)
        except StopIteration:
            raise RuntimeError("Empty response while downloading exported file.")

        content_type = (resp.headers.get("Content-Type") or "").lower()
        is_zip = "zip" in content_type or first_chunk[:4] == b"PK\x03\x04"

        if is_zip:
            zip_path = tmp_dir / f"archilogic_{floor_id}_{kind}.zip"
            with open(zip_path, "wb") as f:
                f.write(first_chunk)
                for chunk in iter_chunks:
                    if chunk:
                        f.write(chunk)
            _log(f"Downloaded {kind.upper()} ZIP to: {zip_path}")
            import zipfile
            extract_dir = tmp_dir / f"archilogic_{floor_id}_{kind}"
            extract_dir.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(extract_dir)
            _log(f"Extracted to: {extract_dir}")
            matches = list(extract_dir.rglob(f"*.{target_ext.lstrip('.').lower()}"))
            if not matches:
                raise RuntimeError(f"No {target_ext} file found inside the downloaded ZIP.")
            _log(f"Using {kind.upper()} file: {matches[0]}")
            return matches[0]
        else:
            out = tmp_dir / f"archilogic_{floor_id}.{target_ext.lstrip('.')}"
            with open(out, "wb") as f:
                f.write(first_chunk)
                for chunk in iter_chunks:
                    if chunk:
                        f.write(chunk)
            _log(f"Downloaded {kind.upper()} to: {out}")
            return out

# --------------------------------------------------------------------------------------
# Assets overview helper
# --------------------------------------------------------------------------------------

def print_assets_overview(assets_data):
    """Print a quick overview of an assets GeoJSON FeatureCollection.

    assets_data: dict (parsed JSON) or list of feature dicts.
    """
    from collections import Counter, defaultdict

    if isinstance(assets_data, dict):
        features = assets_data.get("features", [])
    else:
        features = list(assets_data)

    total = len(features)
    _log(f"--- Assets Overview ---")
    _log(f"Total assets: {total}")

    cat_counter = Counter()
    subcat_by_cat = defaultdict(set)
    table_sizes = []

    for feat in features:
        props = feat.get("properties", {}) if isinstance(feat, dict) else {}
        cats = props.get("categories") or []
        subcats = props.get("subCategories") or []
        dims = props.get("dimensions") or {}

        for cat in cats:
            cat_counter[cat] += 1
            for sub in subcats:
                subcat_by_cat[cat].add(sub)

        if "table" in cats:
            w = dims.get("width")
            l = dims.get("length")
            if w is not None and l is not None:
                # round to cm to avoid float noise, format as table_WxL
                w_cm = round(w * 100)
                l_cm = round(l * 100)
                table_sizes.append(f"table_{w_cm}x{l_cm}")

    _log(f"Unique categories: {len(cat_counter)}")
    for cat in sorted(cat_counter):
        subs = sorted(subcat_by_cat.get(cat, []))
        sub_str = ", ".join(subs) if subs else "-"
        _log(f"  {cat}: {cat_counter[cat]} asset(s)  |  subCategories: {sub_str}")

    if table_sizes:
        size_counts = Counter(table_sizes)
        _log(f"Table sizes ({len(size_counts)} unique):")
        for size in sorted(size_counts):
            _log(f"  {size}: {size_counts[size]}x")

    _log(f"-----------------------")


# --------------------------------------------------------------------------------------
# Furnish rename from assets
# --------------------------------------------------------------------------------------

def _get_or_create_collection(name, parent):
    """Get an existing collection by name, or create it as a child of parent."""
    col = bpy.data.collections.get(name)
    if not col:
        col = bpy.data.collections.new(name)
        parent.children.link(col)
    elif col.name not in parent.children:
        # Reparent: unlink from wherever it currently lives, link under parent
        for scene_col in bpy.data.collections:
            if col.name in scene_col.children:
                scene_col.children.unlink(col)
                break
        if col.name not in bpy.context.scene.collection.children:
            pass  # already unlinked
        parent.children.link(col)
    return col


def rename_furnish_from_assets():
    """Rename IfcFurnishingElement objects in the Furnish collection using ASSETS_CACHE,
    then split them into Furnish_<category> sub-collections under Assets.

    IFC name:    IfcFurnishingElement/0b459b7a-bee6-4643-86cf-8bfafe516a25
    After step:  IfcFurnishingElement/0b459b7a-bee6-4643-86cf-8bfafe516a25_tables_desk
    Collection:  Assets/Furnish_tables
    """
    if not ASSETS_CACHE:
        _log("rename_furnish_from_assets: ASSETS_CACHE is empty — import a floor first.")
        return

    furnish_col = bpy.data.collections.get("Furnish")
    if not furnish_col:
        _log("rename_furnish_from_assets: 'Furnish' collection not found, skipping.")
        return

    # --- Step 1: Rename ---
    renamed = 0
    not_found = 0

    for obj in list(furnish_col.objects):
        if "/" not in obj.name:
            continue
        prefix, rest = obj.name.split("/", 1)
        guid = rest.split("_")[0]  # strip any existing suffix

        asset_props = ASSETS_CACHE.get(guid)
        if asset_props is None:
            not_found += 1
            if _debug_mode():
                _log(f"  Not in assets: {obj.name}")
            continue

        cats = asset_props.get("categories") or []
        subcats = asset_props.get("subCategories") or []
        cat_str = cats[0] if cats else "unknown"
        sub_str = subcats[0] if subcats else "unknown"
        obj.name = f"{prefix}/{guid}_{cat_str}_{sub_str}"
        renamed += 1

    _log(f"rename_furnish_from_assets: renamed {renamed}, not found in assets: {not_found}")

    # --- Step 2: Split into Furnish_<category> sub-collections under Assets ---

    # Find or create Assets collection
    assets_col = bpy.data.collections.get("Assets")
    if not assets_col:
        assets_col = bpy.data.collections.new("Assets")
        bpy.context.scene.collection.children.link(assets_col)

    moved = 0
    for obj in list(furnish_col.objects):
        if "/" not in obj.name:
            continue
        # Name format after rename: prefix/guid_category_sub  (or prefix/guid if not found)
        rest = obj.name.split("/", 1)[1]
        parts = rest.split("_")
        category = parts[1] if len(parts) >= 3 else "unknown"
        target_name = f"Furnish_{category}"

        target_col = _get_or_create_collection(target_name, assets_col)
        furnish_col.objects.unlink(obj)
        target_col.objects.link(obj)
        moved += 1

    _log(f"rename_furnish_from_assets: moved {moved} objects into Furnish_<category> collections")

    # Remove the now-empty Furnish collection
    if len(furnish_col.objects) == 0 and len(furnish_col.children) == 0:
        bpy.data.collections.remove(furnish_col)
        _log("rename_furnish_from_assets: removed empty 'Furnish' collection")



# --------------------------------------------------------------------------------------
# PropertyGroup for floor list
# --------------------------------------------------------------------------------------

class FloorListItem(bpy.types.PropertyGroup):
    floor_id: bpy.props.StringProperty(name="Floor ID")
    floor_name: bpy.props.StringProperty(name="Floor Name")
    selected: bpy.props.BoolProperty(name="", default=False)

# --------------------------------------------------------------------------------------
# UIList
# --------------------------------------------------------------------------------------

class ESEC_FLOOR_UL_list(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        row.prop(item, "selected", text="")
        row.label(text=item.floor_name or item.floor_id)
        op = row.operator("esec.open_floor_url", text="", icon='URL', emboss=False)
        op.floor_id = item.floor_id

# --------------------------------------------------------------------------------------
# --------------------------------------------------------------------------------------
# Operators
# --------------------------------------------------------------------------------------

class ESEC_ARCHIOLOGIC_OT_open_floor_url(bpy.types.Operator):
    bl_idname = "esec.open_floor_url"
    bl_label = "Open in Archilogic"
    bl_description = "Open this floor in the Archilogic web app"

    floor_id: bpy.props.StringProperty()

    def execute(self, context):
        bpy.ops.wm.url_open(url=f"https://app.archilogic.com/floors/{self.floor_id}")
        return {'FINISHED'}


class ESEC_ARCHIOLOGIC_OT_open_download_folder(bpy.types.Operator):
    bl_idname = "esec.open_download_folder"
    bl_label = "Open Download Folder"
    bl_description = "Open the Archilogic download folder in the file explorer"

    def execute(self, context):
        folder = Path.home() / "Downloads" / "archilogic_download"
        folder.mkdir(parents=True, exist_ok=True)
        import subprocess
        import sys
        if sys.platform == "win32":
            subprocess.Popen(["explorer", str(folder)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(folder)])
        else:
            subprocess.Popen(["xdg-open", str(folder)])
        return {'FINISHED'}


class ESEC_ARCHIOLOGIC_OT_refresh_floors(bpy.types.Operator):
    bl_idname = "esec.refresh_floors"
    bl_label = "Refresh floors"
    bl_description = "Fetch floor list from Archilogic"

    def execute(self, context):
        prefs = _get_prefs()
        token = prefs.archiologic_token
        if not token:
            self.report({'ERROR'}, "Set your Secret token in Add-on Preferences.")
            return {'CANCELLED'}
        try:
            features = api_list_floors(token, include_archived=prefs.include_archived)
            global FLOOR_CACHE
            FLOOR_CACHE = features

            items = context.scene.floor_list_items
            items.clear()
            for f in features:
                fid = f.get("id") or f.get("properties", {}).get("id")
                props = f.get("properties", {}) if isinstance(f, dict) else {}
                name = props.get("name") or "(unnamed)"
                floor_no = props.get("floorNumber")
                label = name if not floor_no else f"{name}  [#{floor_no}]"
                if fid:
                    item = items.add()
                    item.floor_id = fid
                    item.floor_name = label

            self.report({'INFO'}, f"Loaded {len(features)} floor(s) from Archiologic.")
            return {'FINISHED'}
        except Exception as e:
            _log(traceback.format_exc())
            self.report({'ERROR'}, f"Could not load floors: {e}")
            return {'CANCELLED'}


class ESEC_ARCHIOLOGIC_OT_download_all(bpy.types.Operator):
    bl_idname = "esec.download_all"
    bl_label = "Download All"
    bl_description = (
        "Download jpg, png, svg, ifc, imdf and assets.json for all checked floors "
        "into ~/Downloads/archilogic_download"
    )

    def execute(self, context):
        prefs = _get_prefs()
        token = prefs.archiologic_token
        if not token:
            self.report({'ERROR'}, "Set your Secret token in Add-on Preferences.")
            return {'CANCELLED'}

        selected = [item for item in context.scene.floor_list_items if item.selected]
        if not selected:
            self.report({'ERROR'}, "Check at least one floor in the list.")
            return {'CANCELLED'}

        base_dir = Path.home() / "Downloads" / "archilogic_download"
        base_dir.mkdir(parents=True, exist_ok=True)

        total_steps = len(selected) * 6  # jpg, png, svg, ifc, imdf, assets.json
        step = 0
        errors = []

        try:
            for floor_num, item in enumerate(selected, 1):
                safe_name = re.sub(r'[<>:"/\\|?*\s]+', '_', item.floor_name).strip('_') or item.floor_id
                floor_dir = base_dir / safe_name
                floor_dir.mkdir(parents=True, exist_ok=True)

                for fmt in ("jpg", "png", "svg"):
                    step += 1
                    _status(context, f"[{step}/{total_steps}] Floor {floor_num}/{len(selected)}: {item.floor_name} - {fmt.upper()}")
                    try:
                        api_export_image(token, item.floor_id, fmt, floor_dir, safe_name)
                    except Exception as e:
                        errors.append(f"{item.floor_name} | {fmt}: {e}")
                        _log(f"  ERROR {fmt}: {e}")

                for kind, ext in (("ifc", "ifc"), ("imdf", "imdf.zip")):
                    step += 1
                    _status(context, f"[{step}/{total_steps}] Floor {floor_num}/{len(selected)}: {item.floor_name} - {kind.upper()}")
                    try:
                        api_export_to_folder(token, item.floor_id, kind, ext, floor_dir, safe_name)
                    except Exception as e:
                        errors.append(f"{item.floor_name} | {kind}: {e}")
                        _log(f"  ERROR {kind}: {e}")

                # assets.json
                step += 1
                _status(context, f"[{step}/{total_steps}] Floor {floor_num}/{len(selected)}: {item.floor_name} - assets.json")
                try:
                    assets = api_get_assets(token, item.floor_id)
                    out = floor_dir / f"{safe_name}_assets.json"
                    out.write_text(json.dumps({"type": "FeatureCollection", "features": assets}, indent=2), encoding="utf-8")
                    _log(f"  Saved assets.json: {out} ({len(assets)} assets)")
                    print_assets_overview({"type": "FeatureCollection", "features": assets})
                except Exception as e:
                    errors.append(f"{item.floor_name} | assets.json: {e}")
                    _log(f"  ERROR assets.json: {e}")

        finally:
            context.workspace.status_text_set(None)  # clear status bar when done

        if errors:
            for err in errors:
                _log(f"FAILED: {err}")
            self.report({'WARNING'}, f"Done with {len(errors)} error(s) - check console.")
        else:
            self.report({'INFO'}, f"Downloaded {len(selected)} floor(s) to {base_dir}")
        return {'FINISHED'}


class ESEC_ARCHIOLOGIC_OT_import_ifc(bpy.types.Operator):
    bl_idname = "esec.import_ifc2"
    bl_label = "Import IFC"
    bl_description = "Download and import IFC for the single highlighted floor only (ignores checkboxes)"

    def execute(self, context):
        prefs = _get_prefs()
        token = prefs.archiologic_token
        if not token:
            self.report({'ERROR'}, "Set your Secret token in Add-on Preferences.")
            return {'CANCELLED'}

        items = context.scene.floor_list_items
        idx = context.scene.floor_list_index
        if not items or idx < 0 or idx >= len(items):
            self.report({'ERROR'}, "Select (highlight) a floor from the list first.")
            return {'CANCELLED'}
        floor_id = items[idx].floor_id

        try:
            ifc_path = api_export_and_download_format(token, floor_id, "ifc", ".ifc")
            _log(f"Temporary IFC stored at: {ifc_path}")
            self.report({'INFO'}, f"IFC temp: {str(ifc_path)}")

            # Download assets and keep in memory for rename step
            try:
                assets = api_get_assets(token, floor_id)
                global ASSETS_CACHE
                ASSETS_CACHE = {f["id"]: f.get("properties", {}) for f in assets if f.get("id")}
                _log(f"Assets loaded into cache: {len(ASSETS_CACHE)} entries")
                print_assets_overview({"type": "FeatureCollection", "features": assets})
            except Exception as ae:
                _log(f"WARNING: Could not download assets.json: {ae}")
                ASSETS_CACHE = {}

            _ensure_ifc_importer_enabled()
            res = bpy.ops.bim.load_project(filepath=str(ifc_path))
            if 'FINISHED' in res:
                self.report({'INFO'}, f"Imported IFC: {ifc_path.name}")
                return {'FINISHED'}
            else:
                self.report({'ERROR'}, f"IFC importer returned: {res}")
                return {'CANCELLED'}

        except Exception as e:
            _log(traceback.format_exc())
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}



# --------------------------------------------------------------------------------------
# Panel
# --------------------------------------------------------------------------------------

class ESEC_ARCHIOLOGIC_PT_main_panel(bpy.types.Panel):
    bl_label = "ESEC Archilogic import v" + ".".join(map(str, bl_info['version']))
    bl_idname = "ESEC_ARCHIOLOGIC_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'ESEC'

    def draw(self, context):
        global _panel_auto_refreshed, _repopulate_scheduled
        items = context.scene.floor_list_items

        # Repopulate from cache if the scene list was cleared (e.g. after IFC import).
        # Writing to CollectionProperty is not allowed in draw(), so schedule a timer instead.
        if not items and FLOOR_CACHE and not _repopulate_scheduled:
            _repopulate_scheduled = True
            if not bpy.app.timers.is_registered(_repopulate_from_cache):
                bpy.app.timers.register(_repopulate_from_cache, first_interval=0.0)

        # Auto-refresh once on first panel open if a token is set
        if not _panel_auto_refreshed:
            _panel_auto_refreshed = True
            try:
                if _get_prefs().archiologic_token:
                    bpy.app.timers.register(
                        lambda: bpy.ops.esec.refresh_floors() and None,
                        first_interval=0.1,
                    )
            except Exception:
                pass

        layout = self.layout

        try:
            has_token = bool(_get_prefs().archiologic_token)
        except Exception:
            has_token = False

        if not has_token:
            box = layout.box()
            col = box.column(align=True)
            col.label(text="To import floors, create an access token.", icon='INFO')
            col.separator()
            op = col.operator("wm.url_open", text="Open Archilogic Access Tokens URL", icon='URL')
            op.url = "https://app.archilogic.com/organization/settings/access-tokens"
            col.separator()
            op2 = col.operator("preferences.addon_show", text="Open Addon Preferences and enter the access token", icon='PREFERENCES')
            op2.module = ADDON_ID
            return

        box = layout.box()
        row = box.row(align=True)
        row.label(text="Floors")
        row.operator("esec.refresh_floors", icon='FILE_REFRESH', text="Refresh")

        box.template_list(
            "ESEC_FLOOR_UL_list", "",
            context.scene, "floor_list_items",
            context.scene, "floor_list_index",
            rows=5,
        )

        row = box.row(align=True)
        row.operator("esec.download_all", text="Download checked Floors", icon='IMPORT')
        row.operator("esec.open_download_folder", text="", icon='FILE_FOLDER')

        row = box.row(align=True)
        row.operator("esec.import_ifc2", text="Import selected Floor IFC", icon='IMPORT')

        layout.separator()
        

# --------------------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------------------

classes = (
    FloorListItem,
    ESEC_FLOOR_UL_list,
    ESEC_ARCHIOLOGIC_OT_open_floor_url,
    ESEC_ARCHIOLOGIC_OT_open_download_folder,
    ESEC_ARCHIOLOGIC_OT_refresh_floors,
    ESEC_ARCHIOLOGIC_OT_download_all,
    ESEC_ARCHIOLOGIC_OT_import_ifc,
    ESEC_ARCHIOLOGIC_PT_main_panel,
)

def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.floor_list_items = bpy.props.CollectionProperty(type=FloorListItem)
    bpy.types.Scene.floor_list_index = bpy.props.IntProperty(name="Active Floor", default=0)

    # Legacy properties kept for compatibility
    bpy.types.Scene.floorID = bpy.props.StringProperty(name="Floor ID", default="")
    bpy.types.Scene.create_rooms = bpy.props.BoolProperty(name="Create Rooms", default=False)
    bpy.types.Scene.create_walls = bpy.props.BoolProperty(name="Create Walls", default=False)
    bpy.types.Scene.create_windows_doors = bpy.props.BoolProperty(name="Create Windows/Doors", default=False)

def unregister():
    global _panel_auto_refreshed
    _panel_auto_refreshed = False
    for prop in ("floor_list_items", "floor_list_index", "floorID",
                 "create_rooms", "create_walls", "create_windows_doors"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()
