import logging
import random
import requests
from io import BytesIO
from typing import Tuple, Optional, List, Dict

SEARCH_URL = "https://api.artic.edu/api/v1/artworks/search"
IIIF_BASE = "https://www.artic.edu/iiif/2"
IMAGE_WIDTH = 4096  # upscaled request; IIIF caps to the largest native size

# Non-objective / bold-colour movements only, so results skew abstract
# rather than portraiture, landscape, or other representational work.
SEARCH_TERMS: List[str] = [
    "abstract",
    "geometric abstraction",
    "suprematism",
    "constructivism",
    "de stijl",
    "orphism",
    "color field",
    "abstract expressionism",
]


def get_image_url(args):
    query = random.choice(SEARCH_TERMS)
    logging.info(f"Fetching image list from Art Institute of Chicago for query '{query}'...")

    params = {
        "q": query,
        "query[term][is_public_domain]": "true",
        "fields": "id,image_id",
        "limit": "100",
    }

    try:
        response = requests.get(SEARCH_URL, params=params, timeout=15)
        response.raise_for_status()
        results: List[Dict] = response.json().get("data", [])

        candidates = [r for r in results if r.get("image_id")]
        if not candidates:
            raise ValueError("No public-domain artworks with images for query")

        selected = random.choice(candidates)
        image_id = selected["image_id"]
        return f"{IIIF_BASE}/{image_id}/full/{IMAGE_WIDTH},/0/default.jpg"
    except (requests.RequestException, ValueError, KeyError) as e:
        logging.error(f"Error getting image url from Art Institute of Chicago: {str(e)}")
        return None


def get_image(args, image_url) -> Tuple[Optional[BytesIO], Optional[str]]:
    try:
        logging.info(f"Downloading image from {image_url}")
        response = requests.get(image_url, timeout=30)
        response.raise_for_status()
        image_data: BytesIO = BytesIO(response.content)
        return image_data, "JPEG"
    except requests.RequestException as e:
        logging.error(f"Failed to fetch Art Institute of Chicago image: {str(e)}")
        return None, None
