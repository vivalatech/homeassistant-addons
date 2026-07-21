import logging
import random
import requests
from io import BytesIO
from typing import Tuple, Optional, List, Dict

API_URL = "https://api.openverse.org/v1/images/"

# Search terms chosen to bias results toward bold-colour, non-representational
# work rather than photography or muted/traditional imagery.
SEARCH_TERMS: List[str] = [
    "abstract art",
    "abstract painting",
    "geometric abstract",
    "color field painting",
    "contemporary abstract art",
    "vibrant abstract",
    "modern abstract art",
    "bold color abstract",
]

# Excluding "photograph" keeps results to illustration / digitized artwork,
# i.e. no real-life imagery.
CATEGORIES = "illustration,digitized_artwork"
LICENSES = "cc0,by,by-sa"
MIN_WIDTH = 1600  # avoid low-res thumbnails that would look poor on a 4K panel


def get_image_url(args):
    query = random.choice(SEARCH_TERMS)
    logging.info(f"Fetching image list from Openverse for query '{query}'...")

    params: Dict[str, str] = {
        "q": query,
        "category": CATEGORIES,
        "license": LICENSES,
        "page_size": "40",
        "mature": "false",
    }

    try:
        response = requests.get(API_URL, params=params, timeout=15)
        response.raise_for_status()
        results: List[Dict] = response.json().get("results", [])

        # Filter out anything without a usable, reasonably sized source image
        candidates = [
            r for r in results
            if r.get("url") and r.get("width") and r["width"] >= MIN_WIDTH
        ]

        if not candidates:
            # Fall back to any result with a URL if nothing meets the size bar
            candidates = [r for r in results if r.get("url")]

        if not candidates:
            raise ValueError("No usable Openverse results for query")

        selected = random.choice(candidates)
        return selected["url"]
    except (requests.RequestException, ValueError, KeyError) as e:
        logging.error(f"Error getting image url from Openverse: {str(e)}")
        return None


def get_image(args, image_url) -> Tuple[Optional[BytesIO], Optional[str]]:
    try:
        logging.info(f"Downloading image from {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image_data: BytesIO = BytesIO(response.content)

        content_type = response.headers.get("Content-Type", "")
        file_type = "PNG" if "png" in content_type.lower() else "JPEG"

        return image_data, file_type
    except requests.RequestException as e:
        logging.error(f"Failed to fetch Openverse image: {str(e)}")
        return None, None
