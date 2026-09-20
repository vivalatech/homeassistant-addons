import os
import logging
import random
from io import BytesIO
from typing import List, Tuple, Optional, Set

folder_path = '/media/frame'

def get_media_folder_images() -> List[str]:
    """Get a list of JPG/PNG files in the folder, and search recursively if you want to use subdirectories"""
    return [
        os.path.join(root, filename)
        for root, dirs, files in os.walk(folder_path)
        for filename in files
        if filename.lower().endswith(('.jpg', '.png'))
        and filename.lower() != 'latest.jpg'
    ]

def get_image_url(args, excluded_urls: Optional[Set[str]] = None):
    files = get_media_folder_images()
    if not files:
        logging.info('No images found in the media folder.')
        return None

    excluded_urls = excluded_urls or set()
    candidates = [
        (
            selected_file,
            os.path.relpath(selected_file, folder_path).replace(os.sep, '/'),
        )
        for selected_file in files
    ]
    candidates = [candidate for candidate in candidates if candidate[1] not in excluded_urls]
    if not candidates:
        logging.info('No unused images found in the media folder.')
        return None

    _, relative_path = random.choice(candidates)
    return relative_path

def get_image(args, image_url) -> Tuple[Optional[BytesIO], Optional[str]]:
    full_path = os.path.join(folder_path, image_url)
    if not os.path.exists(full_path):
        logging.error(f"File not found: {full_path}")
        return None, None
    
    file_type = 'JPEG' if full_path.lower().endswith('.jpg') else 'PNG'
    with open(full_path, 'rb') as f:
        data = BytesIO(f.read())
    return data, file_type
