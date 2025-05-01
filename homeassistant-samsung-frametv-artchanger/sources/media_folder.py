import os
import logging
import random
from io import BytesIO
from typing import List, Tuple, Optional, Dict

folder_path = '/media/frame'

def get_media_folder_images() -> List[str]:
    """Get a list of JPG/PNG files in the folder, and search recursively if you want to use subdirectories"""
    return [os.path.join(root, f) for root, dirs, files in os.walk(folder_path) for f in files if f.endswith('.jpg') or f.endswith('.png')]

def get_image_url(args):
    files = get_media_folder_images()
    if not files:
        logging.info('No images found in the media folder.')
        return None
    selected_file = random.choice(files)
    return f"{os.path.basename(selected_file)}"

def get_image(args, image_url) -> Tuple[Optional[BytesIO], Optional[str]]:
    full_path = os.path.join(folder_path, image_url)
    if not os.path.exists(full_path):
        logging.error(f"File not found: {full_path}")
        return None, None
    
    file_type = 'JPEG' if full_path.endswith('.jpg') else 'PNG'
    with open(full_path, 'rb') as f:
        data = BytesIO(f.read())
    return data, file_type
