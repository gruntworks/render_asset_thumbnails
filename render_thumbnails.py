import bpy
from typing import List
from bpy.types import AddonPreferences
from bpy.props import IntProperty, BoolProperty
import os

bl_info = {
    "name": "Render Asset Thumbnails",
    "author": "GruntWorks",
    "blender": (4, 5, 0),
    "version": (0, 2, 2),
    "location": "ASSETS",
    "description": "Renders selected asset thumbnails from asset browser to a folder with current collection name.",
    "category": "User Interface",
}


class RenderAssetThumbnails(bpy.types.Operator):
    bl_idname = "asset.render_thumbnails"
    bl_label = "Render Thumbnail(s)"

    thumb_dir = ''
    visible_objects = []
    _settings = {}  # This is to revert render settings after executing
    allowed_types = ["COLLECTION", "OBJECT"]



    @classmethod
    def poll(cls, context):
        return context.selected_assets



    def disable_visible_objects(self) -> None:
        self.visible_objects = [obj for obj in bpy.data.objects if obj.hide_render == False]
        for obj in self.visible_objects:
            obj.hide_render = True



    def enable_visible_objects(self) -> None:
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

    # 4.0+ Overridden context for loading assets
    def update_thumbnail(self, context, asset: bpy.types.FileSelectEntry, location: str) -> None:
        if bpy.app.version >= (4, 0, 0):
            with context.temp_override(id=asset.local_id):
                bpy.ops.ed.lib_id_load_custom_preview(
                    filepath=f"{location}/{asset.local_id.name}.png"
                )
        else:
            bpy.ops.ed.lib_id_load_custom_preview(
                {"id": asset.local_id},
                filepath=f"{location}/{asset.local_id.name}.png")



    def get_area_type(self, _type: str) -> bpy.types.Area or None:
        if not _type:
            return None
        return [area for area in bpy.context.window.screen.areas if area.type == _type][0]



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



    def render_thumbnail(self, context, assets: List[bpy.types.FileSelectEntry]) -> List:
        executed_objects = {}

        bpy.context.window_manager.progress_begin(0, len(assets))
        bpy.context.scene.frame_start = 1
        bpy.context.scene.frame_end = 1
        bpy.context.scene.frame_set(1)
        filename = bpy.path.basename(bpy.context.blend_data.filepath).replace(".blend", "")

        for idx, asset in enumerate(assets):
            bpy.context.scene.frame_set(idx)
            bpy.ops.object.select_all(action='DESELECT')

            # This operation supports only mesh objects and collections
            if asset.id_type in self.allowed_types:
                active_obj = self.enable_and_select(asset.local_id)
                if not active_obj:
                    executed_objects[active_obj.name] = 'ERROR'
                    return

                # Get collection to which object belongs to
                collection_dir = f"{self.thumb_dir}/{filename}_{''.join(self.get_collection_name(active_obj).split())}"
                os.makedirs(collection_dir, exist_ok=True)

                bpy.ops.view3d.camera_to_view_selected()
                bpy.context.scene.render.filepath = os.path.join(collection_dir, active_obj.name)
                bpy.context.scene.render.image_settings.file_format = 'PNG'
                area = self.get_area_type('VIEW_3D')
                override_context = bpy.context.copy()
                override_context['area'] = area
                override_context['region'] = area.regions[-1]
                with bpy.context.temp_override(**override_context):
                    bpy.ops.render.render(write_still=True)
                self.update_thumbnail(context, assets[idx], collection_dir)
                executed_objects[active_obj.name] = 'INFO'
                active_obj.hide_render = True
                bpy.context.window_manager.progress_update(idx)
            else:
                executed_objects[asset.local_id.name] = 'ERROR'
        bpy.context.window_manager.progress_end()
        return executed_objects



    def show_report(self, executed_objects):
        if bpy.context.preferences.addons[__name__].preferences.show_report:
            for obj in executed_objects:
                self.report({executed_objects[obj]},
                            f"{'Updated' if executed_objects[obj] == 'INFO' else 'Skipped'} thumbnail for asset '{obj}'")
            self.report({'OPERATOR'}, f"Asset Catalog updated")
            bpy.ops.screen.info_log_show()



    def setup_directory(self) -> None:
        self.thumb_dir = f"{os.path.dirname(bpy.data.filepath)}/thumbnails"



    def delete_object(self, name: str) -> None:
        bpy.ops.object.select_all(action='DESELECT')
        bpy.data.objects[name].select_set(True)
        bpy.ops.object.delete()



    def setup_camera(self, context) -> None:
        self._settings = {
            'resolution_x': context.scene.render.resolution_x,
            'resolution_y': context.scene.render.resolution_y,
            'film_transparent': context.scene.render.film_transparent,
            'use_nodes': context.scene.use_nodes,
            'file_format': context.scene.render.image_settings.file_format,
            'color_mode': context.scene.render.image_settings.color_mode,
            'cam_pos': context.scene.camera.location.copy(),
            'cam_rot': context.scene.camera.rotation_euler.copy(),
            'cam_lens':  context.scene.camera.data.lens
        }

        area = self.get_area_type('VIEW_3D')
        prefs = bpy.context.preferences.addons[__name__].preferences
        
        # Match the camera's focal length to that of the viewport if applicable
        if area.spaces.active.region_3d.view_perspective == 'PERSP':
            bpy.context.scene.camera.data.lens = area.spaces.active.lens
        else: 
            area.spaces[0].region_3d.view_perspective = 'PERSP'

        # Bring camera to view to capture viewport angle, needs context override
        override_context = bpy.context.copy()
        override_context['area'] = area
        override_context['region'] = area.regions[-1]
        with bpy.context.temp_override(**override_context):
            bpy.ops.view3d.camera_to_view()        

        # Setup temp settings
        context.scene.render.resolution_x = prefs.thumb_res
        context.scene.render.resolution_y = prefs.thumb_res
        context.scene.render.film_transparent = True
        context.scene.use_nodes = False
        context.scene.render.image_settings.file_format = 'PNG'
        context.scene.render.image_settings.color_mode = 'RGBA'



    def restore_render_settings(self, context):
        if self._settings:
            context.scene.render.resolution_x = self._settings['resolution_x']
            context.scene.render.resolution_y = self._settings['resolution_y']
            context.scene.render.film_transparent = self._settings['film_transparent']
            context.scene.use_nodes = self._settings['use_nodes']
            context.scene.render.image_settings.file_format = self._settings['file_format']
            context.scene.render.image_settings.color_mode = self._settings['color_mode']
            context.scene.camera.location = self._settings['cam_pos']
            context.scene.camera.rotation_euler = self._settings['cam_rot']
            context.scene.camera.data.lens = self._settings['cam_lens']



    def check_preconditions(self, context):
        if not bpy.data.is_saved:
            self.report({'ERROR'}, "Please save current .blend file")
            return 'err'
        if not context.selected_assets:
            self.report({'ERROR'}, "You must select at least one asset");
        if not context.scene.camera:
            self.report({'ERROR'}, "There is no active camera")
            return 'err'



    def execute(self, context):
        status = self.check_preconditions(context)
        if status == 'err':
            return {'CANCELLED'}

        if bpy.context.active_object and bpy.context.active_object.mode == 'EDIT':
            bpy.ops.object.editmode_toggle()

        self.setup_directory()
        self.setup_camera(context)
        if not os.path.exists(self.thumb_dir):
            os.mkdir(self.thumb_dir)

        self.disable_visible_objects()
        objs = self.render_thumbnail(context, context.selected_assets)

        # Only show the report if the user has more than one asset selected
        if context.preferences.addons[__name__].preferences.show_report and objs and len(context.selected_assets) > 1:
            self.show_report(objs)

        self.enable_visible_objects()
        self.restore_render_settings(context)
        return {"FINISHED"}



class RenderAssetThumbnails_Preferences(AddonPreferences):
    bl_idname = __name__

    thumb_res : IntProperty(
        name = "Resolution",
        default = 200,
        min = 64,
        max = 2048,
        description = "Pixel width and height of rendered thumbnails"
    )

    show_report : BoolProperty(
        name = "Show Report",
        default = True,
        description = "Displays a confirmation log when a batch of thumbnails has finished rendering"
    )

    def draw(self, context):
        layout = self.layout

        contents = layout.split(factor=0.6)
        resbox = contents.column()
        
        xrow = resbox.row()
        xrow.alignment = "RIGHT"
        xrow.label(text="Resolution")
        xrow.prop(self, "thumb_res", text="", expand=True)

        otherbox = contents.column()
        otherbox.prop(self, "show_report")


def draw_operator(self, context):
    self.layout.operator(RenderAssetThumbnails.bl_idname)

def register():
    bpy.utils.register_class(RenderAssetThumbnails)
    bpy.utils.register_class(RenderAssetThumbnails_Preferences)
    if hasattr(bpy.types, "ASSETBROWSER_MT_context_menu"):
        bpy.types.ASSETBROWSER_MT_context_menu.append(draw_operator)
    if hasattr(bpy.types, "ASSETBROWSER_MT_edit"):
        bpy.types.ASSETBROWSER_MT_edit.append(draw_operator)
    elif hasattr(bpy.types, "ASSETBROWSER_MT_asset"):
        bpy.types.ASSETBROWSER_MT_asset.append(draw_operator)


def unregister():
    if hasattr(bpy.types, "ASSETBROWSER_MT_context_menu"):
        bpy.types.ASSETBROWSER_MT_context_menu.remove(draw_operator)
    if hasattr(bpy.types, "ASSETBROWSER_MT_edit"):
        bpy.types.ASSETBROWSER_MT_edit.remove(draw_operator)
    elif hasattr(bpy.types, "ASSETBROWSER_MT_asset"):
        bpy.types.ASSETBROWSER_MT_asset.remove(draw_operator)
    bpy.utils.unregister_class(RenderAssetThumbnails)
    bpy.utils.unregister_class(RenderAssetThumbnails_Preferences)

if __name__ == "__main__":
    register()
