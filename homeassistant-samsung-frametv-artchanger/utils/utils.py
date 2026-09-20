from io import BytesIO
from PIL import Image, ImageOps
from typing import List, Dict, Optional

class Utils:
    def __init__(self, tvips: str, uploaded_files: List[Dict[str, str]]):
        self.tvips = tvips
        self.uploaded_files = uploaded_files
        self.check_tv_ip = len(tvips.split(',')) > 1 if tvips else False #only check the tv_ip if there is more than one tv_ip

    @staticmethod
    def resize_and_pad_image(image_data, target_width=3840, target_height=2160):
        """Fit the complete image onto a black 16:9 canvas without cropping it."""
        with Image.open(image_data) as source_image:
            img = ImageOps.exif_transpose(source_image)
            scale = min(target_width / img.width, target_height / img.height)
            new_width = max(1, round(img.width * scale))
            new_height = max(1, round(img.height * scale))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            canvas = Image.new('RGB', (target_width, target_height), 'black')
            left = (target_width - new_width) // 2
            top = (target_height - new_height) // 2

            if img.mode in ('RGBA', 'LA') or (
                img.mode == 'P' and 'transparency' in img.info
            ):
                img = img.convert('RGBA')
                canvas.paste(img, (left, top), img)
            else:
                canvas.paste(img.convert('RGB'), (left, top))

            output = BytesIO()
            canvas.save(output, format='JPEG', quality=90)
            output.seek(0)
            return output

    @staticmethod
    def resize_and_crop_image(image_data, target_width=3840, target_height=2160):
        """Fill the 16:9 canvas and crop only when the user opts into it."""
        with Image.open(image_data) as source_image:
            img = ImageOps.exif_transpose(source_image).convert('RGB')
            scale = max(target_width / img.width, target_height / img.height)
            new_width = max(1, round(img.width * scale))
            new_height = max(1, round(img.height * scale))
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            left = (new_width - target_width) // 2
            top = (new_height - target_height) // 2
            img = img.crop((left, top, left + target_width, top + target_height))

            output = BytesIO()
            img.save(output, format='JPEG', quality=90)
            output.seek(0)
            return output

    def get_remote_filename(self, file_name: str, source_name: str, tv_ip: str) -> Optional[str]:
        for uploaded_file in self.uploaded_files:
            if uploaded_file['file'] == file_name and uploaded_file['source'] == source_name:
                if self.check_tv_ip:
                    if uploaded_file['tv_ip'] == tv_ip:
                        return uploaded_file['remote_filename']
                else:
                    return uploaded_file['remote_filename']
        return None
