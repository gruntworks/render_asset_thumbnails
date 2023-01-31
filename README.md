## Render Assets Thumbnail

### 1. About
This is Blender addon that lets you render asset thumbnails by selecting them  
in Asset Browser.
Uses scene camera which renders 200x200 thumbnails depending on viewport angle.

### 2. Installation
- Download this repository or just `render_thumbnails.py` file
- In Blender go to `Edit -> Preferences -> Add-on` and click `install`
- Navigate to `render_thumbnails.py` file and click install.
- Addon should be visible in the list, enable it.

Alternative to installing the addon is copy/paste script content into Blender  
script editor, however it will be available only for the current session.

### 3. Usage
For addon to work Camera needs to be available and **.blend file needs to be saved somewhere** so that  
images can be saved somewhere...
Eevee is recommended with low sampling and HDRI setup for rendering.

1. Go to Asset browser and click on assets which you would like to render.
2. Click `Edit -> Render Thumbnails`

After it is finished rendering, all images should be in `/thumbnails/{collection_name}/`  
Script will update asset thumbnails automatically after rendering.