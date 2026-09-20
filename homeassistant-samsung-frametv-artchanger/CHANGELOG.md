# Changelog

## 1.1.0

- Add Google Arts & Culture color, museum, and style/period filters.
- Support exact museum plus style combinations.
- Use Google-provided dominant-color metadata for combined filtering.
- Preserve sent-art history across app updates and avoid repeat uploads.
- Publish the processed TV image atomically as `/media/frame/latest.jpg`.
- Add progressive catalog caching with bounded storage.
- Add filter tests, translated configuration labels, and dashboard documentation.
- Preserve the complete artwork and add black borders when its aspect ratio is not 16:9.
- Bound Google dimension selection by attempts and elapsed time, fall back from strict TV format to a preserved-aspect landscape work, and exit cleanly when no work matches.
