import sys
import logging
import os
import json
import argparse
from io import BytesIO
import random

sys.path.append('../')

from samsungtvws import SamsungTVWS
from sources import bing_wallpapers, google_art, media_folder
from utils.utils import Utils

# Add command line argument parsing
parser = argparse.ArgumentParser(description='Upload images to Samsung TV.')
parser.add_argument('--upload-all', action='store_true', help='Upload all images at once')
parser.add_argument('--debug', action='store_true', help='Enable debug mode to check if TV is reachable')
parser.add_argument('--tvip', help='Comma-separated IP addresses of Samsung Frame TVs')
parser.add_argument('--same-image', action='store_true', help='Use the same image for all TVs (default: different images)')
parser.add_argument('--google-art', action='store_true', help='Download and upload image from Google Arts & Culture')
parser.add_argument('--google-color', default='ANY', help='Google Arts & Culture color filter')
parser.add_argument('--google-color-entity', help='Home Assistant input_select entity containing the color filter')
parser.add_argument('--google-museum', default='ANY', help='Google Arts & Culture museum filter')
parser.add_argument('--google-museum-entity', help='Home Assistant input_select entity containing the museum filter')
parser.add_argument('--google-style', default='ANY', help='Google Arts & Culture style or period filter')
parser.add_argument('--google-style-entity', help='Home Assistant input_select entity containing the style filter')
parser.add_argument('--google-landscape-only', action='store_true', help='Skip portrait and square Google Arts & Culture works')
parser.add_argument('--google-tv-format-only', action='store_true', help='Use only landscape Google Art close enough to 16:9 for a small edge crop')
parser.add_argument('--download-high-res', action='store_true', help='Download high resolution image using dezoomify-rs')
parser.add_argument('--bing-wallpapers', action='store_true', help='Download and upload image from Bing Wallpapers')
parser.add_argument('--media-folder', action='store_true', help='Use images from the local media folder')
parser.add_argument('--preserve-aspect-ratio', action='store_true', help='Fit the complete image on a black 16:9 canvas instead of cropping it')
parser.add_argument('--debugimage', action='store_true', help='Save downloaded and resized images for inspection')

args = parser.parse_args()

# Set the path to the file that will store the list of uploaded filenames
upload_list_path = '/media/frame/uploaded_files.json'
legacy_upload_list_paths = ['/data/uploaded_files.json', 'uploaded_files.json']

# Load the list of uploaded filenames from the file
if os.path.isfile(upload_list_path):
    with open(upload_list_path, 'r') as f:
        uploaded_files = json.load(f)
elif any(os.path.isfile(path) for path in legacy_upload_list_paths):
    legacy_upload_list_path = next(
        path for path in legacy_upload_list_paths if os.path.isfile(path)
    )
    with open(legacy_upload_list_path, 'r') as f:
        uploaded_files = json.load(f)
    logging.warning('Migrating artwork history to the shared media folder')
else:
    uploaded_files = []

os.makedirs(os.path.dirname(upload_list_path), exist_ok=True)

# Increase debug level
logging.basicConfig(level=logging.INFO)

sources = []
if args.bing_wallpapers:
    sources.append(bing_wallpapers)
if args.google_art:
    sources.append(google_art)
if args.media_folder:
    sources.append(media_folder)

if not sources:
    logging.error('No image source specified. Please use --google-art, --bing-wallpapers, or --media-folder')
    sys.exit(1)

tvip = args.tvip.split(',') if args.tvip else []
use_same_image = args.same_image
preview_path = '/media/frame/latest.jpg'

utils = Utils(args.tvip, uploaded_files)

def process_tv(tv_ip: str, image_data: BytesIO, file_type: str, image_url: str, remote_filename: str, source_name: str):
    if not image_url or not source_name:
        logging.warning(f'No artwork was selected for TV at {tv_ip}; leaving the current image unchanged')
        return False
    if image_data is None and remote_filename is None:
        logging.warning(f'No image data is available for TV at {tv_ip}; leaving the current image unchanged')
        return False

    tv = SamsungTVWS(tv_ip)
    
    # Check if TV supports art mode
    if not tv.art().supported():
        logging.warning(f'TV at {tv_ip} does not support art mode.')
        return False

    if remote_filename is None:
        try:
            logging.info(f'Uploading image to TV at {tv_ip}')
            remote_filename = tv.art().upload(image_data.getvalue(), file_type=file_type, matte="none")
            if remote_filename is None:
                raise Exception('No remote filename returned')

            tv.art().select_image(remote_filename, show=True)
            save_preview_image(image_data)
            logging.info(f'Image uploaded and selected on TV at {tv_ip}')
            # Add the filename to the list of uploaded filenames
            uploaded_files.append({
                'file': image_url,
                'remote_filename': remote_filename,
                'tv_ip': tv_ip if len(tvip) > 1 else None,
                'source': source_name
            })
            # Save the list of uploaded filenames to the file
            with open(upload_list_path, 'w') as f:
                json.dump(uploaded_files, f)
            return True
        except Exception as e:
            logging.error(f'There was an error uploading the image to TV at {tv_ip}: ' + str(e))
            return False
    else:
        if not args.upload_all:
            # Select the image using the remote file name only if not in 'upload-all' mode
            logging.info(f'Setting existing image on TV at {tv_ip}, skipping upload')
            tv.art().select_image(remote_filename, show=True)
            save_preview_image(image_data)
            return True
    return False

def get_image_for_tv(tv_ip: str):
    selected_source = random.choice(sources)
    logging.info(f'Selected source: {selected_source.__name__}')

    previously_sent_urls = {
        item.get('file')
        for item in uploaded_files
        if isinstance(item, dict)
        and item.get('file')
        and item.get('source') == selected_source.__name__
    }
    image_url = selected_source.get_image_url(args, previously_sent_urls)

    if not image_url:
        logging.error('No unused image is available from the selected source')
        return None, None, None, None, None

    remote_filename = utils.get_remote_filename(image_url, selected_source.__name__, tv_ip)

    image_data, file_type = selected_source.get_image(args, image_url)
    if image_data is None:
        if remote_filename:
            logging.warning('Could not refresh preview; selecting the existing TV image without changing latest.jpg')
            return None, None, image_url, remote_filename, selected_source.__name__
        return None, None, None, None, None

    save_debug_image(image_data, f'debug_{selected_source.__name__}_original.jpg')

    if (
        selected_source is google_art
        and args.google_tv_format_only
        and not getattr(args, '_google_preserve_aspect_fallback', False)
    ):
        logging.info('Filling the 16:9 TV canvas with a dimension-filtered artwork...')
        resized_image_data = utils.resize_and_crop_image(image_data)
    elif args.preserve_aspect_ratio:
        logging.info('Fitting the complete image onto a black 16:9 canvas...')
        resized_image_data = utils.resize_and_pad_image(image_data)
    else:
        logging.info('Filling the 16:9 canvas and cropping the image...')
        resized_image_data = utils.resize_and_crop_image(image_data)

    save_debug_image(resized_image_data, f'debug_{selected_source.__name__}_resized.jpg')

    return resized_image_data, file_type, image_url, remote_filename, selected_source.__name__

def save_preview_image(image_data: BytesIO) -> None:
    """Publish exactly the processed TV image without exposing a partial file."""
    if image_data is None:
        return
    os.makedirs(os.path.dirname(preview_path), exist_ok=True)
    temporary_path = preview_path + '.tmp'
    try:
        with open(temporary_path, 'wb') as preview_file:
            preview_file.write(image_data.getvalue())
            preview_file.flush()
            os.fsync(preview_file.fileno())
        os.replace(temporary_path, preview_path)
        logging.info(f'Dashboard preview saved as {preview_path}')
    except OSError as error:
        logging.error(f'Could not save dashboard preview: {error}')
        try:
            os.remove(temporary_path)
        except FileNotFoundError:
            pass

def save_debug_image(image_data: BytesIO, filename: str) -> None:
    if args.debugimage:
        with open(filename, 'wb') as f:
            f.write(image_data.getvalue())
        logging.info(f'Debug image saved as {filename}')

changed_tv = False

if tvip:
    if len(tvip) > 1 and use_same_image:
        image_data, file_type, image_url, remote_filename, source_name = get_image_for_tv(None)
        if image_url:
            for tv_ip in tvip:
                changed_tv = process_tv(
                    tv_ip,
                    image_data,
                    file_type,
                    image_url,
                    remote_filename,
                    source_name,
                ) or changed_tv
    else:
        for tv_ip in tvip:
            image_data, file_type, image_url, remote_filename, source_name = get_image_for_tv(tv_ip)
            if image_url:
                changed_tv = process_tv(
                    tv_ip,
                    image_data,
                    file_type,
                    image_url,
                    remote_filename,
                    source_name,
                ) or changed_tv
    if not changed_tv:
        logging.warning('Finished without changing the TV because no usable artwork was available')
else:
    logging.error('No TV IP addresses specified. Please use --tvip')
    sys.exit(1)
