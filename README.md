# Samsung Frame TV Art Changer add-on for Home Assistant

![TV with some art on it ](https://i.imgur.com/BunHdwb.jpeg)

This add-on is built on the awesome work of <https://github.com/ow/samsung-frame-art> and <https://github.com/gijsvdhoven/homeassistant-addons>. 
It adds the ability to push images from different sources to your Samsung Frame TV, currently supported are Google Art and Culture, Bing Wallpapers and Local Media folder. 

By starting the add-on it will randomly pick an image based on your configuration and put it on your frame; after the image is placed the add-on will automatically stop again. This for instance can be triggered via an automation to run on a daily basis. Please find an example below.

If multiple sources are enabled it will randomly choose a source on each run. 

# Google Art
By default the addon configuration has "Google Art" mode enabled which instead of taking images from the "media" folder takes random images from the Google Arts and Culture site and pushes it to the Samsung Frame TV. 

# Bing Wallpaper
The addon now also supports "Bing Wallpapers" mode, which allows you to display random high-quality wallpapers from Bing on your Samsung Frame TV.

# Local Media Folder
Looks for images in the /media/frame folder and randomly pushes an image to your Samsung Frame TV. When you start the addon for the first time it creates a specific directory in Media called "frame" where you can place your custom images.

Please note you must upload pictures with a lower-case extension and only .png and .jpg are supported.

If `/media/frame/selected_frame_art.jpg` exists, the add-on will upload that file instead of choosing a random image. This makes it possible for a Home Assistant dashboard, script, or shell command to stage one exact local artwork before starting the add-on. If that file is not present, the normal random local-media behavior is used.


## Installation

Install this addon by adding the repository:

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fvivalatech%2Fhomeassistant-addons)


## Configuration Options

1. **IP Address**: Set the IP address of your Samsung The Frame TV.
2. **Google Art**: Enable to use random images from Google Arts and Culture.
3. **Bing Wallpapers**: Enable to use random high-quality wallpapers from Bing.
4. **High Res**: (For Google Art only) Enable to get high-resolution images using dezoomify.


## Example Automation

Here's an example of how to set up an automation to change the image daily at 23:00:

```yaml
description: "Change Samsung Frame TV Art Daily"
mode: single
trigger:
  - platform: time
    at: "23:00:00"
condition: []
action:
  - service: hassio.addon_start
    data:
      addon: local_hass-frametv-artchanger
```

## TODO

Here's some ideas for stuff to implement
- [ ] Delete old N images on TV, e.g. configurable to keep last 100 uploaded images and delete an older image everytime a new one is uploaded
- [ ] More sources, especially something for high res contemporary art would be awesome or other curated sources
- [ ] Dashboard card that shows currently active art and maybe allows selection of other art
