import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sources import google_art


class GoogleArtFilterTests(unittest.TestCase):
    def test_german_helper_values_are_normalized(self):
        self.assertEqual(google_art._normalize_museum("Musée d’Orsay"), "ORSAY")
        self.assertEqual(google_art._normalize_museum("MoMA"), "MOMA")
        self.assertEqual(google_art._normalize_style("Moderne Kunst"), "MODERN")
        self.assertEqual(
            google_art._normalize_style("Abstrakter Expressionismus"),
            "ABSTRACT_EXPRESSIONISM",
        )

    def test_google_dominant_colors_map_to_dashboard_groups(self):
        self.assertEqual(google_art._dominant_color_group("#607995"), "BLUE")
        self.assertEqual(google_art._dominant_color_group("#ff2020"), "RED")
        self.assertEqual(google_art._dominant_color_group("#f080b0"), "PINK")
        self.assertEqual(google_art._dominant_color_group("#777777"), "GRAY")

    def test_final_api_page_without_continuation_token_is_supported(self):
        query = [
            "stella.pr",
            "AssetsQuery:test",
            [
                [
                    "stella.common.cobject",
                    "The Starry Night",
                    "Vincent van Gogh",
                    "//lh3.googleusercontent.com/example",
                    "/asset/the-starry-night/test",
                    8,
                    None,
                    None,
                    "#607995",
                ]
            ],
            None,
            1,
        ]
        body = ")]}'\n" + json.dumps([[[*query], ["e", 2]]])
        assets, total, token = google_art._parse_search_api(body)
        self.assertEqual(total, 1)
        self.assertIsNone(token)
        self.assertEqual(assets[0]["color"], "#607995")
        self.assertTrue(assets[0]["url"].startswith("https://artsandculture.google.com/asset/"))

    def test_sent_urls_and_color_are_both_applied(self):
        catalog = {
            "assets": [
                {"url": "https://example/red-sent", "color": "#ff2020"},
                {"url": "https://example/red-new", "color": "#c03020"},
                {"url": "https://example/blue-new", "color": "#2040d0"},
            ]
        }
        candidates = google_art._filter_catalog_candidates(
            catalog,
            "RED",
            {"https://example/red-sent"},
        )
        self.assertEqual(candidates, ["https://example/red-new"])

    def test_asset_page_parser_keeps_original_image_url(self):
        parser = google_art.GoogleAssetImageParser()
        parser.feed(
            '<html><head><meta property="og:image" '
            'content="https://lh3.googleusercontent.com/example"></head></html>'
        )
        self.assertEqual(
            parser.image_url,
            "https://lh3.googleusercontent.com/example",
        )

    @mock.patch.object(google_art, "_save_orientation_cache")
    @mock.patch.object(google_art, "_load_orientation_cache", return_value={})
    @mock.patch.object(google_art.random, "shuffle")
    @mock.patch.object(
        google_art,
        "_probe_asset_dimensions",
        side_effect=[(600, 900), (1600, 900)],
    )
    def test_landscape_selector_skips_portrait_before_high_res_download(
        self,
        probe_dimensions,
        _shuffle,
        _load_cache,
        save_cache,
    ):
        selected = google_art._select_dimension_candidate(
            ["https://example/portrait", "https://example/landscape"]
        )

        self.assertEqual(selected, "https://example/landscape")
        self.assertEqual(probe_dimensions.call_count, 2)
        saved_cache = save_cache.call_args.args[0]
        self.assertEqual(
            saved_cache["https://example/portrait"]["orientation"],
            "portrait_or_square",
        )
        self.assertEqual(
            saved_cache["https://example/landscape"]["orientation"],
            "landscape",
        )

    @mock.patch.object(google_art, "_save_orientation_cache")
    @mock.patch.object(
        google_art,
        "_load_orientation_cache",
        return_value={
            "https://example/portrait": {"orientation": "portrait_or_square"},
            "https://example/landscape": {"orientation": "landscape"},
        },
    )
    @mock.patch.object(google_art.random, "shuffle")
    @mock.patch.object(google_art, "_probe_asset_dimensions")
    def test_landscape_selector_reuses_cached_orientation(
        self,
        probe_dimensions,
        _shuffle,
        _load_cache,
        save_cache,
    ):
        selected = google_art._select_dimension_candidate(
            ["https://example/portrait", "https://example/landscape"]
        )

        self.assertEqual(selected, "https://example/landscape")
        probe_dimensions.assert_not_called()
        save_cache.assert_not_called()

    def test_tv_format_accepts_only_near_16_by_9_landscape(self):
        self.assertTrue(google_art._matches_tv_format(1920, 1080))
        self.assertTrue(google_art._matches_tv_format(1680, 1050))
        self.assertFalse(google_art._matches_tv_format(1600, 1200))
        self.assertFalse(google_art._matches_tv_format(1080, 1920))

    @mock.patch.object(google_art, "_save_orientation_cache")
    @mock.patch.object(google_art, "_load_orientation_cache", return_value={})
    @mock.patch.object(google_art.random, "shuffle")
    @mock.patch.object(
        google_art,
        "_probe_asset_dimensions",
        side_effect=[(600, 900), (1600, 1200), (1920, 1080)],
    )
    def test_tv_format_selector_skips_portrait_and_four_by_three(
        self,
        probe_dimensions,
        _shuffle,
        _load_cache,
        _save_cache,
    ):
        selected = google_art._select_dimension_candidate(
            [
                "https://example/portrait",
                "https://example/four-by-three",
                "https://example/sixteen-by-nine",
            ],
            tv_format_only=True,
        )

        self.assertEqual(selected, "https://example/sixteen-by-nine")
        self.assertEqual(probe_dimensions.call_count, 3)

    @mock.patch.object(
        google_art,
        "_select_dimension_candidate",
        side_effect=[None, "https://example/landscape-fallback"],
    )
    def test_tv_format_falls_back_to_landscape_when_aspect_is_preserved(self, select):
        args = SimpleNamespace(
            google_tv_format_only=True,
            google_landscape_only=True,
            preserve_aspect_ratio=True,
        )
        selected = google_art._select_candidate_for_dimensions(
            ["https://example/artwork"],
            args,
        )

        self.assertEqual(selected, "https://example/landscape-fallback")
        self.assertTrue(args._google_preserve_aspect_fallback)
        self.assertEqual(select.call_count, 2)
        self.assertTrue(select.call_args_list[0].kwargs["tv_format_only"])
        self.assertFalse(select.call_args_list[1].kwargs["tv_format_only"])
        self.assertIs(
            select.call_args_list[0].kwargs["probe_budget"],
            select.call_args_list[1].kwargs["probe_budget"],
        )
        self.assertEqual(
            select.call_args_list[0].kwargs["deadline"],
            select.call_args_list[1].kwargs["deadline"],
        )

    @mock.patch.object(
        google_art,
        "_select_dimension_candidate",
        return_value=None,
    )
    def test_tv_format_without_permitted_fallback_ends_cleanly(self, select):
        selected = google_art._select_candidate_for_dimensions(
            ["https://example/artwork"],
            SimpleNamespace(
                google_tv_format_only=True,
                google_landscape_only=True,
                preserve_aspect_ratio=False,
            ),
        )

        self.assertIsNone(selected)
        select.assert_called_once()

    def test_failed_high_res_download_removes_temporary_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory, "frame-art-test.jpg")

            def fail_download(_command, check):
                self.assertTrue(check)
                output_path.write_bytes(b"partial")
                raise google_art.subprocess.CalledProcessError(1, "dezoomify-rs")

            with mock.patch.object(
                google_art.tempfile,
                "mkstemp",
                return_value=(os.open(output_path, os.O_CREAT | os.O_RDWR), str(output_path)),
            ), mock.patch.object(google_art.subprocess, "run", side_effect=fail_download):
                image_data, file_type = google_art.get_image(
                    SimpleNamespace(download_high_res=True),
                    "https://example/artwork",
                )

            self.assertIsNone(image_data)
            self.assertIsNone(file_type)
            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
