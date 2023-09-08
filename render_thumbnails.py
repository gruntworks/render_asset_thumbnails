import bpy
from typing import List
import os

bl_info = {
    "name": "Render asset thumbnail",
    "author": "GruntWorks",
    "blender": (3, 2, 0),
    "version": (0, 2),
    "location": "ASSETS",
    "description": "Renders selected asset thumbnail from asset browser to folder with current collection name.",
    "category": "User Interface",
}


class RenderAssetsThumbnail(bpy.types.Operator):
    bl_idname = "asset.render_thumbnails"
    bl_label = "Render thumbnails"

    thumb_dir = ''
    visible_objects = []
    _settings = {}  # This is to revert render settings after executing
    allowed_types = [bpy.types.Object, bpy.types.Collection]

    @classmethod
    def poll(cls, context):
        return context.selected_asset_files

    def disable_visible_objects(self) -> None:
        self.visible_objects = [obj for obj in bpy.data.objects if obj.hide_render == False]
        for obj in self.visible_objects:
            obj.hide_render = True

    def enable_visible_objects(self) -> None:
        if self.visible_objects:
            for obj in self.visible_objects:
                obj.hide_render = False

    def enable_and_select(self, asset):
        if isinstance(asset, bpy.types.Object):
            asset.hide_render = False
            asset.select_set(True)
            bpy.context.view_layer.objects.active = asset
            return asset
        if isinstance(asset, bpy.types.Collection):
            collection = bpy.data.collections.get(asset.name)
            if collection:
                # Iterate through the objects in the collection and select them
                self.select_all_objects_in_collection(collection)
                return collection

    def update_thumbnail(self, asset: bpy.types.FileSelectEntry, location: str) -> None:
        bpy.ops.ed.lib_id_load_custom_preview(
            {"id": asset.local_id},
            filepath=f"{location}/{asset.local_id.name}.png")

    def get_area_type(self, _type: str) -> bpy.types.Area or None:
        if not _type:
            return None
        return [area for area in bpy.context.screen.areas if area.type == _type][0]

    def get_collection_name(self, asset):
        if type(asset) == bpy.types.Object:
            return asset.users_collection[0].name
        if type(asset) == bpy.types.Collection:
            return asset.name

    def select_all_objects_in_collection(self, collection: bpy.types.Collection) -> None:
        """
        Recursively select all objects in the given collection and its sub-collections.

        Args:
            collection: The Blender collection to start the selection from.
        """
        if not collection:
            return
        collection.hide_render = False
        for obj in collection.objects:
            obj.select_set(True)
            obj.hide_render = False

        for sub_collection in collection.children:
            self.select_all_objects_in_collection(sub_collection)

    def render_thumbnail(self, assets: List[bpy.types.FileSelectEntry]) -> None:
        executed_objects = {}
        bpy.context.window_manager.progress_begin(0, len(assets))
        for idx, asset in enumerate(assets):
            bpy.context.scene.frame_set(idx)
            bpy.ops.object.select_all(action='DESELECT')

            # This operation supports only mesh objects and collections
            if any(isinstance(asset.asset_data.id_data, allowed_type) for allowed_type in self.allowed_types):
                active_obj = self.enable_and_select(asset.asset_data.id_data)
                if not active_obj:
                    executed_objects[active_obj.name] = 'ERROR'
                    return

                # Get collection to which object belongs to
                collection_dir = f"{self.thumb_dir}/{''.join(self.get_collection_name(active_obj).split())}"

                bpy.ops.view3d.camera_to_view_selected()
                bpy.data.scenes[0].render.filepath = os.path.join(collection_dir, active_obj.name + '.png')
                bpy.ops.render.render(write_still=True)
                self.update_thumbnail(assets[idx], collection_dir)
                executed_objects[active_obj.name] = 'INFO'
                active_obj.hide_render = True
                bpy.context.window_manager.progress_update(idx)
            else:
                executed_objects[asset.asset_data.id_data.name] = 'ERROR'
        bpy.context.window_manager.progress_end()

        # Show report
        for obj in executed_objects:
            self.report({executed_objects[obj]},
                        f"{'Update' if executed_objects[obj] == 'INFO' else 'Skip'} thumbnail for: {obj}")
        self.report({'OPERATOR'}, f"Asset Catalog updated")
        bpy.ops.screen.info_log_show()

    def setup_directory(self) -> None:
        self.thumb_dir = f"{os.path.dirname(bpy.data.filepath)}/thumbnails"

    def delete_object(self, name: str) -> None:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.data.objects[name].select_set(True)
        bpy.ops.object.delete()

    def setup_camera(self) -> None:
        self._settings = {
            'resolution_x': bpy.data.scenes[0].render.resolution_x,
            'resolution_y': bpy.data.scenes[0].render.resolution_y,
            'film_transparent': bpy.context.scene.render.film_transparent,
            'color_mode': bpy.context.scene.render.image_settings.color_mode,
            'cam': bpy.context.scene.camera.copy()
        }

        area = self.get_area_type('VIEW_3D')
        # Bring camera to view to capture viewport angle, needs context override
        override_context = bpy.context.copy()
        override_context['area'] = area
        override_context['region'] = area.regions[-1]
        with bpy.context.temp_override(**override_context):
            bpy.ops.view3d.camera_to_view()
        # Setup temp settings
        bpy.data.scenes[0].render.resolution_x = 200
        bpy.data.scenes[0].render.resolution_y = 200
        bpy.context.scene.render.film_transparent = True
        bpy.context.scene.render.image_settings.color_mode = 'RGBA'

    def restore_render_settings(self):
        if self._settings:
            bpy.data.scenes[0].render.resolution_x = self._settings['resolution_x']
            bpy.data.scenes[0].render.resolution_y = self._settings['resolution_y']
            bpy.context.scene.render.film_transparent = self._settings['film_transparent']
            bpy.context.scene.render.image_settings.color_mode = self._settings['color_mode']
            bpy.context.scene.camera.rotation_euler = self._settings['cam'].rotation_euler
            bpy.context.scene.camera.location = self._settings['cam'].location

    def check_initial_conditions(self):
        if not bpy.data.is_saved:
            self.report({'ERROR'}, "Please save current .blend file")
            return 'err'

        if not bpy.context.scene.camera:
            self.report({'ERROR'}, "There is no active camera")
            return 'err'

        area = self.get_area_type('VIEW_3D')
        if area.spaces[0].region_3d.view_perspective == 'CAMERA':
            area.spaces[0].region_3d.view_perspective = 'PERSP'

    def execute(self, context):
        status = self.check_initial_conditions()
        if status == 'err':
            return {'CANCELLED'}

        if bpy.context.active_object and bpy.context.active_object.mode == 'EDIT':
            bpy.ops.object.editmode_toggle()

        self.setup_directory()
        self.setup_camera()
        if not os.path.exists(self.thumb_dir):
            os.mkdir(self.thumb_dir)

        self.disable_visible_objects()
        self.render_thumbnail([asset for asset in bpy.context.selected_asset_files])
        self.enable_visible_objects()

        self.restore_render_settings()
        return {"FINISHED"}


def display_button(self, context):
    self.layout.operator(RenderAssetsThumbnail.bl_idname)


def register():
    bpy.utils.register_class(RenderAssetsThumbnail)
    if hasattr(bpy.types, "ASSETBROWSER_MT_edit"):
        bpy.types.ASSETBROWSER_MT_edit.append(display_button)
    elif hasattr(bpy.types, "ASSETBROWSER_MT_asset"):
        bpy.types.ASSETBROWSER_MT_asset.append(display_button)


def unregister():
    if hasattr(bpy.types, "ASSETBROWSER_MT_edit"):
        bpy.types.ASSETBROWSER_MT_edit.remove(display_button)
    elif hasattr(bpy.types, "ASSETBROWSER_MT_asset"):
        bpy.types.ASSETBROWSER_MT_asset.remove(display_button)
    bpy.utils.unregister_class(RenderAssetsThumbnail)


if __name__ == "__main__":
    register()
