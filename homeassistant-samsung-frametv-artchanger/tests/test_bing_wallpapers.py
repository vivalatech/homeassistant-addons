from datetime import datetime
import os
import sys
import unittest
from unittest.mock import patch


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sources import bing_wallpapers


class BingWallpaperTests(unittest.TestCase):
    def test_previously_sent_wallpapers_are_not_selected(self):
        class FrozenDateTime(datetime):
            @classmethod
            def now(cls):
                return cls(2021, 8, 29)

        excluded = {'https://bing.npanuhin.me/US/en/2021-08-28.jpg'}

        with patch('sources.bing_wallpapers.datetime', FrozenDateTime):
            self.assertEqual(
                bing_wallpapers.get_image_url(None, excluded),
                'https://bing.npanuhin.me/US/en/2021-08-29.jpg',
            )

    def test_returns_none_when_every_wallpaper_was_sent(self):
        class FrozenDateTime(datetime):
            @classmethod
            def now(cls):
                return cls(2021, 8, 28)

        with patch('sources.bing_wallpapers.datetime', FrozenDateTime):
            self.assertIsNone(
                bing_wallpapers.get_image_url(
                    None,
                    {'https://bing.npanuhin.me/US/en/2021-08-28.jpg'},
                )
            )


if __name__ == '__main__':
    unittest.main()
