# Samsung Frame TV Art Changer

This Home Assistant OS/Green app downloads artwork, sends it to a Samsung Frame
TV, and stops after one successful run. It supports:

- an atomic dashboard preview at `/media/frame/latest.jpg`;
- persistent duplicate prevention in `/media/frame/uploaded_files.json`;
- Google Arts & Culture filters for color, museum, and style/period;
- a landscape-only Google Art filter enabled by default;
- exact Google-side combinations for museum plus style;
- progressive, compact catalog caching in the app's private `/data` directory.

The app downloads and sends only one artwork per run. Its one-shot startup mode
is intentional: a Home Assistant script starts it whenever a new work is wanted.

By default, **Preserve complete artwork** is enabled. Images that are not 16:9
are centered on a black 16:9 canvas, so no part of the artwork is cropped. Turn
the option off only if you prefer the older edge-to-edge center crop.

By default, **Landscape artworks only** is also enabled for Google Art. The app
checks a small preview before the high-resolution download and skips portrait
and square works. Detected orientations are cached in `/data` without storing
the preview image. Disable the option if you want every orientation to remain
eligible.

Enable **Borderless TV format only** to accept only landscape Google Art close
enough to 16:9 that filling the screen removes no more than about 5% from each
affected edge. The accepted work is then fitted to exactly 3840x2160 without
black borders. If no such work is found within 30 new dimension checks or 60
seconds, the app falls back to a landscape work on a black 16:9 canvas when
both **Preserve complete artwork** and **Landscape artworks only** are enabled.
If even that fallback is unavailable, the app stops cleanly and leaves the
current TV image unchanged. The stricter option is disabled by default because
truly exact 16:9 museum works are rare.

## Installation

1. Add `https://github.com/vivalatech/homeassistant-addons` to the Home
   Assistant app store repositories.
2. Install **Samsung Frame TV Art Changer**.
3. Enter the TV IP address in the app configuration.
4. Start the app manually or from a Home Assistant script/automation whenever a
   new work is wanted.

No `configuration.yaml` change is needed. The dashboard resolves the preview
through Home Assistant's built-in media source.

## Filter helpers

Create three **Input select** helpers in the Home Assistant UI with these exact
entity IDs and options.

### `input_select.samsung_frame_farbe`

- Alle Farben
- Blau
- Grün
- Rot
- Orange
- Gelb
- Violett
- Rosa
- Türkis
- Grau

### `input_select.samsung_frame_museum`

- Alle Museen
- MoMA
- Musée d’Orsay
- Van Gogh Museum
- Metropolitan Museum
- Rijksmuseum
- National Gallery London
- Tate Britain

### `input_select.samsung_frame_stil`

- Alle Stile / Epochen
- Moderne Kunst
- Zeitgenössische Kunst
- Impressionismus
- Post-Impressionismus
- Expressionismus
- Abstrakter Expressionismus
- Surrealismus
- Pop Art
- Renaissance
- Barock
- Romantik
- Realismus

The corresponding app options are:

```yaml
google_color: ANY
google_color_entity: input_select.samsung_frame_farbe
google_museum: ANY
google_museum_entity: input_select.samsung_frame_museum
google_style: ANY
google_style_entity: input_select.samsung_frame_stil
google_landscape_only: true
google_tv_format_only: false
```

If a helper is unavailable, its `ANY` fallback means no restriction for that
dimension.

## How filtering works

With only a color selected, the app uses the Google Arts & Culture Color
Explorer. Museum and style are sent together to Google's artwork search, so a
combination such as MoMA plus Modern Art is exact. If color is added to a
museum/style query, the app groups Google's own dominant-color metadata into
the dashboard's color choices.

The first request caches up to 264 artwork records. If all matching unused
works have been sent, the app fetches the next batch, up to 2,400 records for
that filter combination. The cache contains URLs and color values, not image
files. Successfully sent artwork URLs remain excluded after app updates.

If a very narrow combination has no unused match, the app stops without
silently weakening the selected filters and without repeating an old work.

## Complete dashboard card

This card intentionally has no visual loading state. `button-card`'s supported
update timer plus three delayed media-source resolutions update the preview
without leaving the card stuck on “loading”.

```yaml
type: vertical-stack
cards:
  - type: entities
    title: Kunstfilter
    show_header_toggle: false
    entities:
      - entity: input_select.samsung_frame_farbe
        name: Farbe
      - entity: input_select.samsung_frame_museum
        name: Museum
      - entity: input_select.samsung_frame_stil
        name: Stil / Epoche

  - type: custom:button-card
    name: Neues Kunstwerk laden
    icon: mdi:palette
    show_name: true
    show_state: false
    show_icon: true
    size: 50px
    aspect_ratio: 16/9
    update_timer: 5s

    styles:
      card:
        - background-image: |
            [[[
              const mediaId =
                "media-source://media_source/local/frame/latest.jpg";

              if (!this._frameArtUrl && !this._frameArtResolving) {
                this._frameArtResolving = true;

                hass.callWS({
                  type: "media_source/resolve_media",
                  media_content_id: mediaId
                }).then((result) => {
                  this._frameArtUrl = result.url;
                }).catch(() => {
                  // Beim nächsten Update-Timer wird es erneut versucht.
                }).finally(() => {
                  this._frameArtResolving = false;
                });
              }

              if (this._frameArtUrl)
                return `url("${hass.hassUrl(this._frameArtUrl)}")`;

              return "linear-gradient(to bottom, #2c3e50, #000000)";
            ]]]
        - background-size: cover
        - background-position: center
        - border-radius: 16px
        - color: white
        - font-weight: bold
        - text-shadow: 0px 2px 5px rgba(0,0,0,0.9)
        - box-shadow: 0px 4px 15px rgba(0,0,0,0.3)

      grid:
        - grid-template-areas: '"i" "n"'
        - grid-template-rows: 1fr auto

      name:
        - justify-self: center
        - padding: 10px
        - width: 100%
        - font-size: 15px
        - background: rgba(0, 0, 0, 0.5)
        - backdrop-filter: blur(8px)
        - border-bottom-left-radius: 16px
        - border-bottom-right-radius: 16px

      icon:
        - color: rgba(255, 255, 255, 0.9)
        - filter: drop-shadow(0px 2px 5px rgba(0,0,0,0.5))

    tap_action:
      action: javascript
      javascript: |
        [[[
          void helpers.runAction({
            action: "perform-action",
            perform_action: "script.samsung_frame_neues_google_art"
          });

          const mediaId =
            "media-source://media_source/local/frame/latest.jpg";

          const refreshPreview = () => {
            hass.callWS({
              type: "media_source/resolve_media",
              media_content_id: mediaId
            }).then((result) => {
              this._frameArtUrl = result.url;
            }).catch(() => {
              // Eine spätere Aktualisierung darf weiterlaufen.
            });
          };

          window.setTimeout(refreshPreview, 12000);
          window.setTimeout(refreshPreview, 24000);
          window.setTimeout(refreshPreview, 42000);

          return;
        ]]]

    hold_action:
      action: none
```

## Upstream and licensing

License clarification and the contribution proposal are tracked in
[`vivalatech/homeassistant-addons#11`](https://github.com/vivalatech/homeassistant-addons/issues/11).
