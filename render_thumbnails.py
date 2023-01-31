import bpy
from typing import List
import os

bl_info = {
    "name": "Render asset thumbnail",
    "author": "GruntWorks",
    "blender": (3, 2, 0),
    "version": (0, 1),
    "location": "ASSETS",
    "description": "Renders selected asset thumbnail from asset browser to folder with current collection name.",
    "category": "User Interface",
}


class RenderAssetsThumbnail(bpy.types.Operator):
    bl_idname = "asset.render_thumbnails"
    bl_label = "Render thumbnails"

    _camera_name = '_temp_camera'
    thumb_dir = ''
    visible_objects = []
    _settings = {}  # This is to revert render settings after executing

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

    def enable_and_select(self, asset: bpy.types.Object) -> bpy.types.Object:
        if asset:
            asset.hide_render = False
            asset.select_set(True)
            bpy.context.view_layer.objects.active = asset
            return asset

    def update_thumbnail(self, asset: bpy.types.FileSelectEntry, location: str) -> None:
        bpy.ops.ed.lib_id_load_custom_preview(
            {"id": asset.local_id},
            filepath=f"{location}/{asset.local_id.name}.png")

    def render_thumbnail(self, assets: List[bpy.types.FileSelectEntry]) -> None:
        executed_objects = {}
        bpy.context.window_manager.progress_begin(0, len(assets))
        for idx, asset in enumerate(assets):
            bpy.context.scene.frame_set(idx)
            bpy.ops.object.select_all(action='DESELECT')

            # This operation supports only mesh objects, not materials or poses yet
            if type(asset.asset_data.id_data) == bpy.types.Object:
                active_obj = self.enable_and_select(asset.asset_data.id_data)

                if not active_obj:
                    executed_objects[active_obj.name] = 'ERROR'
                    return

                # Get collection to which object belongs to
                collection_dir = f"{self.thumb_dir}/{''.join(active_obj.users_collection[0].name.split())}"

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

    def setup_directory(self):
        self.thumb_dir = f"{os.path.dirname(bpy.data.filepath)}/thumbnails"

    def setup_camera(self):
        self._settings = {
            'resolution_x': bpy.data.scenes[0].render.resolution_x,
            'resolution_y': bpy.data.scenes[0].render.resolution_y,
            'film_transparent': bpy.context.scene.render.film_transparent,
            'color_mode': bpy.context.scene.render.image_settings.color_mode,
            'active_camera': bpy.context.scene.camera or None
        }
        area = [area for area in bpy.context.screen.areas if area.type == "VIEW_3D"][0]
        bpy.ops.object.camera_add({'area': area}, enter_editmode=False, align='VIEW', location=(0, 0, 0), rotation=(0, 0, 0),
                                  scale=(1, 1, 1))
        bpy.context.active_object.name = self._camera_name
        bpy.context.scene.camera = bpy.data.objects[self._camera_name]
        # Bring camera to view to capture viewport angle, needs context override
        bpy.ops.view3d.camera_to_view({'area': area})
        # Setup _temp_camera settings
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
            if self._settings['active_camera']:
                bpy.context.scene.camera = self._settings['active_camera']
        bpy.ops.object.select_all(action='DESELECT')
        bpy.data.objects[self._camera_name].select_set(True)
        bpy.ops.object.delete()

    def execute(self, context):

        if not bpy.data.is_saved:
            self.report({'ERROR'}, "Please save current .blend file")
            return {"CANCELLED"}
            
        if bpy.context.active_object.mode == 'EDIT':
            bpy.ops.object.editmode_toggle()

        self.setup_directory()
        self.setup_camera()
        current_library_name = context.area.spaces.active.params.asset_library_ref

        if not os.path.exists(self.thumb_dir):
            os.mkdir(self.thumb_dir)

        if current_library_name == "LOCAL":  # Is Current file
            self.disable_visible_objects()
            self.render_thumbnail([asset for asset in bpy.context.selected_asset_files])
            self.enable_visible_objects()

        self.restore_render_settings()
        return {"FINISHED"}


def display_button(self, context):
    self.layout.operator(RenderAssetsThumbnail.bl_idname)


def register():
    bpy.utils.register_class(RenderAssetsThumbnail)
    bpy.types.ASSETBROWSER_MT_edit.append(display_button)


def unregister():
    bpy.types.ASSETBROWSER_MT_edit.remove(display_button)
    bpy.utils.unregister_class(RenderAssetsThumbnail)


if __name__ == "__main__":
    register()
