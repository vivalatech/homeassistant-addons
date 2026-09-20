#!/usr/bin/with-contenv bashio

TVIP=$(bashio::config 'tv')

mkdir -p /media/frame
echo "Using ${TVIP} as the IP's of the Samsung Frame"

PARAMS=""

if bashio::config.true 'google_art'; then
    PARAMS="${PARAMS} --google-art"
fi
if bashio::config.has_value 'google_color'; then
    GOOGLE_COLOR=$(bashio::config 'google_color')
    PARAMS="${PARAMS} --google-color ${GOOGLE_COLOR}"
fi
if bashio::config.has_value 'google_color_entity'; then
    GOOGLE_COLOR_ENTITY=$(bashio::config 'google_color_entity')
    PARAMS="${PARAMS} --google-color-entity ${GOOGLE_COLOR_ENTITY}"
fi
if bashio::config.has_value 'google_museum'; then
    GOOGLE_MUSEUM=$(bashio::config 'google_museum')
    PARAMS="${PARAMS} --google-museum ${GOOGLE_MUSEUM}"
fi
if bashio::config.has_value 'google_museum_entity'; then
    GOOGLE_MUSEUM_ENTITY=$(bashio::config 'google_museum_entity')
    PARAMS="${PARAMS} --google-museum-entity ${GOOGLE_MUSEUM_ENTITY}"
fi
if bashio::config.has_value 'google_style'; then
    GOOGLE_STYLE=$(bashio::config 'google_style')
    PARAMS="${PARAMS} --google-style ${GOOGLE_STYLE}"
fi
if bashio::config.has_value 'google_style_entity'; then
    GOOGLE_STYLE_ENTITY=$(bashio::config 'google_style_entity')
    PARAMS="${PARAMS} --google-style-entity ${GOOGLE_STYLE_ENTITY}"
fi
if bashio::config.true 'google_landscape_only'; then
    PARAMS="${PARAMS} --google-landscape-only"
fi
if bashio::config.true 'google_tv_format_only'; then
    PARAMS="${PARAMS} --google-tv-format-only"
fi
if bashio::config.true 'bing_wallpapers'; then
    PARAMS="${PARAMS} --bing-wallpapers"
fi
if bashio::config.true 'media_folder'; then
    PARAMS="${PARAMS} --media-folder"
fi
if bashio::config.true 'preserve_aspect_ratio'; then
    PARAMS="${PARAMS} --preserve-aspect-ratio"
fi
if bashio::config.true 'download_high_res'; then
    PARAMS="${PARAMS} --download-high-res"
fi
if bashio::config.true 'same_image'; then
    PARAMS="${PARAMS} --same-image"
fi

python3 art.py --tvip ${TVIP} ${PARAMS}

echo "done, closing now!"
kill -s SIGHUP 1
