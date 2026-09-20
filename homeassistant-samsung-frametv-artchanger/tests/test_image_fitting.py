from io import BytesIO
import os
import sys
import unittest

from PIL import Image


sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.utils import Utils


class ImageFittingTests(unittest.TestCase):
    @staticmethod
    def _encode_image(width, height, color):
        image_data = BytesIO()
        Image.new('RGB', (width, height), color).save(image_data, format='PNG')
        image_data.seek(0)
        return image_data

    def test_portrait_artwork_is_not_cropped(self):
        result = Utils.resize_and_pad_image(
            self._encode_image(100, 200, 'red'),
            target_width=160,
            target_height=90,
        )

        with Image.open(result) as image:
            self.assertEqual(image.size, (160, 90))
            self.assertLess(max(image.getpixel((0, 45))), 20)
            self.assertGreater(image.getpixel((80, 0))[0], 180)
            self.assertGreater(image.getpixel((80, 89))[0], 180)

    def test_wide_artwork_gets_black_borders_above_and_below(self):
        result = Utils.resize_and_pad_image(
            self._encode_image(200, 100, 'blue'),
            target_width=160,
            target_height=90,
        )

        with Image.open(result) as image:
            self.assertEqual(image.size, (160, 90))
            self.assertLess(max(image.getpixel((80, 0))), 20)
            self.assertGreater(image.getpixel((0, 45))[2], 180)
            self.assertGreater(image.getpixel((159, 45))[2], 180)


if __name__ == '__main__':
    unittest.main()
