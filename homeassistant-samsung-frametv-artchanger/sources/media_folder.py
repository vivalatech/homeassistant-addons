import logging
import os
import random
from io import BytesIO
from typing import List, Optional, Tuple

FOLDER_PATH = '/media/frame'
PREFERRED_SELECTED_FILE = os.path.join(FOLDER_PATH, 'selected_frame_art.jpg')


def get_media_folder_images() -> List[str]:
    """Get a list of JPG/PNG files in the folder, and search recursively if you want to use subdirectories"""
    return [
        os.path.join(root, f)
        for root, dirs, files in os.walk(FOLDER_PATH)
        for f in files
        if f.endswith('.jpg') or f.endswith('.png')
    ]


def get_image_url(args):
    if os.path.exists(PREFERRED_SELECTED_FILE):
        return os.path.relpath(PREFERRED_SELECTED_FILE, FOLDER_PATH)
    files = get_media_folder_images()
    if not files:
        logging.info('No images found in the media folder.')
        return None
    selected_file = random.choice(files)
    return os.path.relpath(selected_file, FOLDER_PATH)


def get_image(args, image_url) -> Tuple[Optional[BytesIO], Optional[str]]:
    if not image_url:
        return None, None
    full_path = os.path.join(FOLDER_PATH, image_url)
    if not os.path.exists(full_path):
        logging.error(f"File not found: {full_path}")
        return None, None

    file_type = 'JPEG' if full_path.endswith('.jpg') else 'PNG'
    with open(full_path, 'rb') as f:
        data = BytesIO(f.read())
    return data, file_type
