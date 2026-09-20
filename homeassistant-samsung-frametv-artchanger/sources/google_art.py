import json
import logging
import os
import random
import re
import subprocess
import tempfile
import time
import colorsys
from html.parser import HTMLParser
from io import BytesIO
from typing import Dict, List, Optional, Set, Tuple, Union

import requests
from PIL import Image, UnidentifiedImageError


COLOR_PAGE_URL = "https://artsandculture.google.com/color"
SEARCH_PAGE_URL = "https://artsandculture.google.com/search/asset"
SEARCH_API_URL = "https://artsandculture.google.com/api/assets/images"
DEFAULT_FEED_URL = "https://www.gstatic.com/culturalinstitute/tabext/imax_2_2.json"
COLOR_CACHE_PATH = "/data/google_art_color_catalog.json"
FILTER_CACHE_PATH = "/data/google_art_filter_catalog.json"
ORIENTATION_CACHE_PATH = "/data/google_art_orientation_cache.json"
COLOR_CACHE_TTL_SECONDS = 24 * 60 * 60
FILTER_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
FILTER_PAGE_SIZE = 24
FILTER_PAGES_PER_BATCH = 10
FILTER_MAX_ASSETS = 2400
ORIENTATION_MAX_PROBES = 30
TV_FORMAT_MAX_PROBES = 30
DIMENSION_SELECTION_TIMEOUT_SECONDS = 60
DIMENSION_REQUEST_TIMEOUT_SECONDS = 10
TV_ASPECT_RATIO = 16 / 9
TV_ASPECT_RELATIVE_TOLERANCE = 0.10
ORIENTATION_CACHE_MAX_ENTRIES = 5000
REQUEST_HEADERS = {"User-Agent": "Mozilla/5.0 (Home Assistant Frame Art Changer)"}
_RESOLVED_IMAGE_URLS: Dict[str, str] = {}
SUPPORTED_COLORS = {
    "BLUE",
    "GREEN",
    "RED",
    "ORANGE",
    "YELLOW",
    "PURPLE",
    "PINK",
    "TEAL",
    "GRAY",
}
COLOR_ALIASES = {
    "ALLE": "ANY",
    "ALLE FARBEN": "ANY",
    "ANY": "ANY",
    "BLAU": "BLUE",
    "BLUE": "BLUE",
    "GRÜN": "GREEN",
    "GRUEN": "GREEN",
    "GREEN": "GREEN",
    "ROT": "RED",
    "RED": "RED",
    "ORANGE": "ORANGE",
    "GELB": "YELLOW",
    "YELLOW": "YELLOW",
    "VIOLETT": "PURPLE",
    "LILA": "PURPLE",
    "PURPLE": "PURPLE",
    "ROSA": "PINK",
    "PINK": "PINK",
    "TÜRKIS": "TEAL",
    "TUERKIS": "TEAL",
    "TEAL": "TEAL",
    "GRAU": "GRAY",
    "GRAY": "GRAY",
    "GREY": "GRAY",
}

MUSEUMS = {
    "ANY": None,
    "MOMA": "moma-the-museum-of-modern-art",
    "ORSAY": "musee-dorsay-paris",
    "VAN_GOGH": "van-gogh-museum",
    "MET": "the-metropolitan-museum-of-art",
    "RIJKSMUSEUM": "rijksmuseum",
    "NATIONAL_GALLERY": "the-national-gallery-london",
    "TATE_BRITAIN": "tate-britain",
}
MUSEUM_ALIASES = {
    "ALLE": "ANY",
    "ALLE MUSEEN": "ANY",
    "ANY": "ANY",
    "MOMA": "MOMA",
    "MOMA THE MUSEUM OF MODERN ART": "MOMA",
    "MUSÉE D’ORSAY": "ORSAY",
    "MUSÉE D'ORSAY": "ORSAY",
    "MUSEE D'ORSAY": "ORSAY",
    "ORSAY": "ORSAY",
    "VAN GOGH MUSEUM": "VAN_GOGH",
    "THE METROPOLITAN MUSEUM OF ART": "MET",
    "METROPOLITAN MUSEUM": "MET",
    "MET": "MET",
    "RIJKSMUSEUM": "RIJKSMUSEUM",
    "THE NATIONAL GALLERY, LONDON": "NATIONAL_GALLERY",
    "NATIONAL GALLERY LONDON": "NATIONAL_GALLERY",
    "NATIONAL GALLERY": "NATIONAL_GALLERY",
    "TATE BRITAIN": "TATE_BRITAIN",
}

ART_MOVEMENTS = {
    "ANY": None,
    "MODERN": "m015r61",
    "CONTEMPORARY": "m0h0vk",
    "IMPRESSIONISM": "m03xj1",
    "POST_IMPRESSIONISM": "m015xrq",
    "EXPRESSIONISM": "m0pybl",
    "ABSTRACT_EXPRESSIONISM": "m012yb9",
    "SURREALISM": "m073_6",
    "POP_ART": "m0q4mn",
    "RENAISSANCE": "m06cvx",
    "BAROQUE": "m0194x",
    "ROMANTICISM": "m06hsk",
    "REALISM": "m010vqr6v",
}
STYLE_ALIASES = {
    "ALLE": "ANY",
    "ALLE STILE": "ANY",
    "ALLE STILE / EPOCHEN": "ANY",
    "ANY": "ANY",
    "MODERNE KUNST": "MODERN",
    "MODERN ART": "MODERN",
    "MODERN": "MODERN",
    "ZEITGENÖSSISCHE KUNST": "CONTEMPORARY",
    "ZEITGENOESSISCHE KUNST": "CONTEMPORARY",
    "CONTEMPORARY ART": "CONTEMPORARY",
    "CONTEMPORARY": "CONTEMPORARY",
    "IMPRESSIONISMUS": "IMPRESSIONISM",
    "IMPRESSIONISM": "IMPRESSIONISM",
    "POST-IMPRESSIONISMUS": "POST_IMPRESSIONISM",
    "POST-IMPRESSIONISM": "POST_IMPRESSIONISM",
    "EXPRESSIONISMUS": "EXPRESSIONISM",
    "EXPRESSIONISM": "EXPRESSIONISM",
    "ABSTRAKTER EXPRESSIONISMUS": "ABSTRACT_EXPRESSIONISM",
    "ABSTRACT EXPRESSIONISM": "ABSTRACT_EXPRESSIONISM",
    "SURREALISMUS": "SURREALISM",
    "SURREALISM": "SURREALISM",
    "POP ART": "POP_ART",
    "RENAISSANCE": "RENAISSANCE",
    "BAROCK": "BAROQUE",
    "BAROQUE": "BAROQUE",
    "ROMANTIK": "ROMANTICISM",
    "ROMANTICISM": "ROMANTICISM",
    "REALISMUS": "REALISM",
    "REALISM": "REALISM",
}

COLOR_HUE_CENTERS = {
    "RED": 0.0,
    "ORANGE": 30.0,
    "YELLOW": 58.0,
    "GREEN": 120.0,
    "TEAL": 180.0,
    "BLUE": 220.0,
    "PURPLE": 280.0,
    "PINK": 330.0,
}


class GoogleColorAssetParser(HTMLParser):
    """Collect asset links only from the selected color result container."""

    def __init__(self, color: str):
        super().__init__(convert_charrefs=True)
        self.color = color
        self.container_depth = 0
        self.links: List[str] = []
        self._seen: Set[str] = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "div":
            if self.container_depth:
                self.container_depth += 1
            elif attributes.get("data-color", "").upper() == self.color:
                self.container_depth = 1

        if self.container_depth and tag == "a":
            href = attributes.get("href", "")
            if href.startswith("/asset/") and href not in self._seen:
                self._seen.add(href)
                self.links.append(href)

    def handle_endtag(self, tag):
        if tag == "div" and self.container_depth:
            self.container_depth -= 1


class GoogleAssetImageParser(HTMLParser):
    """Read the original-aspect image URL from a Google Arts asset page."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.image_url: Optional[str] = None

    def handle_starttag(self, tag, attrs):
        if tag != "meta" or self.image_url:
            return
        attributes = dict(attrs)
        if attributes.get("property") == "og:image":
            self.image_url = attributes.get("content")


def _normalize_color(value: Optional[str]) -> str:
    normalized = (value or "ANY").strip().upper()
    color = COLOR_ALIASES.get(normalized, normalized)
    if color == "ANY" or color in SUPPORTED_COLORS:
        return color
    logging.warning("Unsupported Google Art color '%s'; using all colors", value)
    return "ANY"


def _normalize_museum(value: Optional[str]) -> str:
    normalized = (value or "ANY").strip().upper()
    museum = MUSEUM_ALIASES.get(normalized, normalized)
    if museum in MUSEUMS:
        return museum
    logging.warning("Unsupported Google Art museum '%s'; using all museums", value)
    return "ANY"


def _normalize_style(value: Optional[str]) -> str:
    normalized = (value or "ANY").strip().upper()
    style = STYLE_ALIASES.get(normalized, normalized)
    if style in ART_MOVEMENTS:
        return style
    logging.warning("Unsupported Google Art style '%s'; using all styles", value)
    return "ANY"


def _read_helper(entity_id: Optional[str], label: str) -> Optional[str]:
    if not entity_id:
        return None

    supervisor_token = os.environ.get("SUPERVISOR_TOKEN")
    if not supervisor_token:
        logging.warning("No Supervisor token available; ignoring %s helper %s", label, entity_id)
        return None

    try:
        response = requests.get(
            f"http://supervisor/core/api/states/{entity_id}",
            headers={"Authorization": f"Bearer {supervisor_token}"},
            timeout=10,
        )
        response.raise_for_status()
        state = response.json().get("state")
        logging.info("%s helper %s selected '%s'", label.capitalize(), entity_id, state)
        return state
    except (requests.RequestException, ValueError, AttributeError) as error:
        logging.warning("Could not read %s helper %s: %s", label, entity_id, error)
        return None


def _load_cache() -> Dict:
    try:
        with open(COLOR_CACHE_PATH, "r", encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
            return cache if isinstance(cache, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_cache(cache: Dict) -> None:
    temporary_path = COLOR_CACHE_PATH + ".tmp"
    try:
        os.makedirs(os.path.dirname(COLOR_CACHE_PATH), exist_ok=True)
        with open(temporary_path, "w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file, ensure_ascii=False)
            cache_file.flush()
            os.fsync(cache_file.fileno())
        os.replace(temporary_path, COLOR_CACHE_PATH)
    except OSError as error:
        logging.warning("Could not save Google Art color cache: %s", error)
        try:
            os.remove(temporary_path)
        except FileNotFoundError:
            pass


def _fetch_color_links(color: str) -> List[str]:
    logging.info("Fetching Google Arts & Culture color list for %s...", color)
    response = requests.get(
        COLOR_PAGE_URL,
        params={"col": color, "hl": "en"},
        headers=REQUEST_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    parser = GoogleColorAssetParser(color)
    parser.feed(response.text)
    if not parser.links:
        raise ValueError(f"No artwork links found for color {color}")
    return parser.links


def _get_color_links(color: str) -> List[str]:
    cache = _load_cache()
    color_cache = cache.get("colors", {}).get(color, {})
    cached_links = color_cache.get("assets", [])
    cached_at = color_cache.get("updated_at", 0)

    if cached_links and time.time() - cached_at < COLOR_CACHE_TTL_SECONDS:
        logging.info("Using %d cached Google Art links for %s", len(cached_links), color)
        return cached_links

    try:
        links = _fetch_color_links(color)
        cache.setdefault("colors", {})[color] = {
            "updated_at": int(time.time()),
            "assets": links,
        }
        _save_cache(cache)
        logging.info("Cached %d Google Art links for %s", len(links), color)
        return links
    except (requests.RequestException, ValueError) as error:
        if cached_links:
            logging.warning(
                "Could not refresh Google Art color list (%s); using %d cached links",
                error,
                len(cached_links),
            )
            return cached_links
        raise


def _get_unfiltered_links() -> List[str]:
    logging.info("Fetching unfiltered image list from Google Arts & Culture...")
    response = requests.get(DEFAULT_FEED_URL, timeout=30)
    response.raise_for_status()
    image_list: List[Dict[str, Union[str, Dict]]] = response.json()
    links = [item.get("link") for item in image_list]
    valid_links = [link for link in links if isinstance(link, str)]
    if not valid_links:
        raise ValueError("Empty image list received")
    return valid_links


def _to_absolute_url(link: str) -> str:
    if link.startswith("https://"):
        return link
    if not link.startswith("/"):
        link = "/" + link
    return f"https://artsandculture.google.com{link}"


def _load_filter_cache() -> Dict:
    try:
        with open(FILTER_CACHE_PATH, "r", encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
            return cache if isinstance(cache, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_filter_cache(cache: Dict) -> None:
    temporary_path = FILTER_CACHE_PATH + ".tmp"
    try:
        os.makedirs(os.path.dirname(FILTER_CACHE_PATH), exist_ok=True)
        with open(temporary_path, "w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file, ensure_ascii=False)
            cache_file.flush()
            os.fsync(cache_file.fileno())
        os.replace(temporary_path, FILTER_CACHE_PATH)
    except OSError as error:
        logging.warning("Could not save Google Art filter cache: %s", error)
        try:
            os.remove(temporary_path)
        except FileNotFoundError:
            pass


def _load_orientation_cache() -> Dict:
    try:
        with open(ORIENTATION_CACHE_PATH, "r", encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
            return cache if isinstance(cache, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_orientation_cache(cache: Dict) -> None:
    if len(cache) > ORIENTATION_CACHE_MAX_ENTRIES:
        newest = sorted(
            cache.items(),
            key=lambda item: (
                item[1].get("checked_at", 0) if isinstance(item[1], dict) else 0
            ),
            reverse=True,
        )[:ORIENTATION_CACHE_MAX_ENTRIES]
        cache = dict(newest)

    temporary_path = ORIENTATION_CACHE_PATH + ".tmp"
    try:
        os.makedirs(os.path.dirname(ORIENTATION_CACHE_PATH), exist_ok=True)
        with open(temporary_path, "w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file, ensure_ascii=False)
            cache_file.flush()
            os.fsync(cache_file.fileno())
        os.replace(temporary_path, ORIENTATION_CACHE_PATH)
    except OSError as error:
        logging.warning("Could not save Google Art orientation cache: %s", error)
        try:
            os.remove(temporary_path)
        except FileNotFoundError:
            pass


def _parse_assets_query(query) -> Tuple[List[Dict[str, Optional[str]]], int, Optional[str]]:
    if not isinstance(query, list) or len(query) < 5:
        raise ValueError("Invalid Google Art AssetsQuery")

    assets = []
    for row in query[2] or []:
        if not isinstance(row, list) or len(row) < 9 or not isinstance(row[4], str):
            continue
        assets.append({"url": _to_absolute_url(row[4]), "color": row[8]})

    total = query[4] if isinstance(query[4], int) else len(assets)
    next_page_token = query[8] if len(query) > 8 and isinstance(query[8], str) else None
    return assets, total, next_page_token


def _parse_search_page(html: str) -> Tuple[List[Dict[str, Optional[str]]], int, Optional[str]]:
    match = re.search(
        r"window\.INIT_data\['SearchFilter:[^']+'\]\s*=\s*(\[.*?\]);</script>",
        html,
        re.DOTALL,
    )
    if not match:
        raise ValueError("Google Art search data was not found")
    payload = json.loads(match.group(1))
    return _parse_assets_query(payload[3])


def _parse_search_api(body: str) -> Tuple[List[Dict[str, Optional[str]]], int, Optional[str]]:
    if body.startswith(")]}'"):
        body = body.split("\n", 1)[1]
    payload = json.loads(body)
    return _parse_assets_query(payload[0][0])


def _catalog_key(museum: str, style: str) -> str:
    return f"{museum}:{style}"


def _query_params(museum: str, style: str) -> Dict[str, str]:
    params = {"hl": "en"}
    partner = MUSEUMS[museum]
    movement = ART_MOVEMENTS[style]
    if partner:
        params["p"] = partner
    if movement:
        params["em"] = movement
    return params


def _merge_assets(existing: List[Dict], additions: List[Dict]) -> List[Dict]:
    merged = []
    seen = set()
    for asset in existing + additions:
        url = asset.get("url") if isinstance(asset, dict) else None
        if not isinstance(url, str) or url in seen:
            continue
        seen.add(url)
        merged.append({"url": url, "color": asset.get("color")})
    return merged


def _fetch_initial_catalog(museum: str, style: str) -> Dict:
    params = _query_params(museum, style)
    logging.info("Fetching Google Art catalog for museum=%s style=%s", museum, style)
    response = requests.get(
        SEARCH_PAGE_URL,
        params=params,
        headers=REQUEST_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    assets, total, next_page_token = _parse_search_page(response.text)
    return {
        "updated_at": int(time.time()),
        "total": total,
        "next_page_token": next_page_token,
        "complete": not next_page_token or len(assets) >= total,
        "assets": assets,
    }


def _expand_catalog(catalog: Dict, museum: str, style: str) -> Dict:
    params = _query_params(museum, style)
    assets = catalog.get("assets", [])
    next_page_token = catalog.get("next_page_token")
    pages = 0

    while (
        next_page_token
        and pages < FILTER_PAGES_PER_BATCH
        and len(assets) < FILTER_MAX_ASSETS
    ):
        api_params = dict(params)
        api_params.update(
            {
                "s": str(FILTER_PAGE_SIZE),
                "pt": next_page_token,
                "rt": "j",
            }
        )
        response = requests.get(
            SEARCH_API_URL,
            params=api_params,
            headers=REQUEST_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        additions, total, next_page_token = _parse_search_api(response.text)
        before = len(assets)
        assets = _merge_assets(assets, additions)
        pages += 1
        if len(assets) == before:
            logging.warning("Google Art catalog pagination returned no new works")
            next_page_token = None
            break

    catalog.update(
        {
            "updated_at": int(time.time()),
            "total": catalog.get("total") or total,
            "next_page_token": next_page_token,
            "complete": not next_page_token or len(assets) >= catalog.get("total", len(assets)),
            "assets": assets,
        }
    )
    logging.info(
        "Cached %d of %d Google Art works for museum=%s style=%s",
        len(assets),
        catalog.get("total", len(assets)),
        museum,
        style,
    )
    return catalog


def _get_filter_catalog(museum: str, style: str, expand: bool = False) -> Dict:
    cache = _load_filter_cache()
    key = _catalog_key(museum, style)
    catalog = cache.get("catalogs", {}).get(key)
    cache_age = time.time() - catalog.get("updated_at", 0) if isinstance(catalog, dict) else None

    if not isinstance(catalog, dict) or not catalog.get("assets") or cache_age > FILTER_CACHE_TTL_SECONDS:
        catalog = _fetch_initial_catalog(museum, style)
        expand = True

    if expand and not catalog.get("complete"):
        catalog = _expand_catalog(catalog, museum, style)

    cache.setdefault("catalogs", {})[key] = catalog
    _save_filter_cache(cache)
    return catalog


def _dominant_color_group(hex_color: Optional[str]) -> Optional[str]:
    if not isinstance(hex_color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", hex_color):
        return None
    red = int(hex_color[1:3], 16) / 255.0
    green = int(hex_color[3:5], 16) / 255.0
    blue = int(hex_color[5:7], 16) / 255.0
    hue, saturation, _ = colorsys.rgb_to_hsv(red, green, blue)
    if saturation < 0.18:
        return "GRAY"
    hue_degrees = hue * 360.0
    return min(
        COLOR_HUE_CENTERS,
        key=lambda name: min(
            abs(hue_degrees - COLOR_HUE_CENTERS[name]),
            360.0 - abs(hue_degrees - COLOR_HUE_CENTERS[name]),
        ),
    )


def _filter_catalog_candidates(catalog: Dict, color: str, excluded: Set[str]) -> List[str]:
    return [
        asset["url"]
        for asset in catalog.get("assets", [])
        if isinstance(asset, dict)
        and isinstance(asset.get("url"), str)
        and asset["url"] not in excluded
        and (color == "ANY" or _dominant_color_group(asset.get("color")) == color)
    ]


def _remaining_request_timeout(deadline: Optional[float]) -> float:
    """Keep each dimension request inside the selection's wall-clock budget."""
    if deadline is None:
        return DIMENSION_REQUEST_TIMEOUT_SECONDS
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("Google Art dimension-selection deadline reached")
    return max(0.5, min(DIMENSION_REQUEST_TIMEOUT_SECONDS, remaining))


def _resolve_download_base_url(
    image_url: str,
    deadline: Optional[float] = None,
) -> str:
    cached_url = _RESOLVED_IMAGE_URLS.get(image_url)
    if cached_url:
        return cached_url

    if "artsandculture.google.com/asset/" not in image_url:
        return image_url

    page_response = requests.get(
        image_url,
        headers=REQUEST_HEADERS,
        timeout=_remaining_request_timeout(deadline) if deadline is not None else 60,
    )
    page_response.raise_for_status()
    parser = GoogleAssetImageParser()
    parser.feed(page_response.text)
    if not parser.image_url:
        raise ValueError("Google Arts asset page has no og:image URL")
    _RESOLVED_IMAGE_URLS[image_url] = parser.image_url
    return parser.image_url


def _probe_asset_dimensions(
    image_url: str,
    deadline: Optional[float] = None,
) -> Tuple[int, int]:
    """Read a small Google preview to determine the original orientation."""
    download_base_url = _resolve_download_base_url(image_url, deadline=deadline)
    response = requests.get(
        download_base_url + "=w320",
        headers=REQUEST_HEADERS,
        timeout=_remaining_request_timeout(deadline) if deadline is not None else 30,
    )
    response.raise_for_status()
    try:
        with Image.open(BytesIO(response.content)) as image:
            return image.width, image.height
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("Google Art preview is not a readable image") from error


def _matches_tv_format(width: int, height: int) -> bool:
    """Accept landscape art requiring at most a small crop to fill 16:9."""
    if width <= height or height <= 0:
        return False
    aspect_ratio = width / height
    relative_difference = abs(aspect_ratio - TV_ASPECT_RATIO) / TV_ASPECT_RATIO
    return relative_difference <= TV_ASPECT_RELATIVE_TOLERANCE


def _cached_dimensions(entry) -> Optional[Tuple[int, int]]:
    if not isinstance(entry, dict):
        return None
    width = entry.get("width")
    height = entry.get("height")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        return width, height
    return None


def _select_dimension_candidate(
    candidates: List[str],
    tv_format_only: bool = False,
    probe_budget: Optional[Dict[str, int]] = None,
    deadline: Optional[float] = None,
) -> Optional[str]:
    """Choose a dimension match, caching metadata without caching images."""
    randomized_candidates = list(candidates)
    random.shuffle(randomized_candidates)
    cache = _load_orientation_cache()
    changed = False
    probes = 0
    max_probes = TV_FORMAT_MAX_PROBES if tv_format_only else ORIENTATION_MAX_PROBES

    for image_url in randomized_candidates:
        cached = cache.get(image_url)
        dimensions = _cached_dimensions(cached)
        if dimensions:
            width, height = dimensions
            matches = _matches_tv_format(width, height) if tv_format_only else width > height
            if matches:
                if changed:
                    _save_orientation_cache(cache)
                return image_url
            continue
        if not tv_format_only and isinstance(cached, dict):
            if cached.get("orientation") == "landscape":
                if changed:
                    _save_orientation_cache(cache)
                return image_url
            if cached.get("orientation") == "portrait_or_square":
                continue

        if probes >= max_probes:
            continue
        if probe_budget is not None and probe_budget.get("remaining", 0) <= 0:
            continue
        if deadline is not None and time.monotonic() >= deadline:
            continue
        probes += 1
        if probe_budget is not None:
            probe_budget["remaining"] -= 1

        try:
            width, height = _probe_asset_dimensions(image_url, deadline=deadline)
        except (requests.RequestException, ValueError, TimeoutError) as error:
            logging.warning("Could not determine artwork orientation for %s: %s", image_url, error)
            continue

        orientation = "landscape" if width > height else "portrait_or_square"
        cache[image_url] = {
            "orientation": orientation,
            "width": width,
            "height": height,
            "checked_at": int(time.time()),
        }
        changed = True
        logging.info(
            "Google Art orientation for %s: %s (%dx%d)",
            image_url,
            orientation,
            width,
            height,
        )
        matches = _matches_tv_format(width, height) if tv_format_only else width > height
        if matches:
            _save_orientation_cache(cache)
            return image_url

    if changed:
        _save_orientation_cache(cache)
    return None


def _select_candidate_for_dimensions(candidates: List[str], args) -> Optional[str]:
    """Apply the strict format filter with a bounded landscape fallback."""
    setattr(args, "_google_preserve_aspect_fallback", False)
    tv_format_only = getattr(args, "google_tv_format_only", False)
    landscape_only = getattr(args, "google_landscape_only", False)
    if not tv_format_only and not landscape_only:
        return random.choice(candidates)

    deadline = time.monotonic() + DIMENSION_SELECTION_TIMEOUT_SECONDS
    probe_budget = {"remaining": TV_FORMAT_MAX_PROBES}

    if tv_format_only:
        selected = _select_dimension_candidate(
            candidates,
            tv_format_only=True,
            probe_budget=probe_budget,
            deadline=deadline,
        )
        if selected:
            return selected

        checked = TV_FORMAT_MAX_PROBES - probe_budget["remaining"]
        if getattr(args, "preserve_aspect_ratio", False) and landscape_only:
            logging.warning(
                "No TV-format Google Art work was found after checking %d new candidates; "
                "falling back to landscape with preserved aspect ratio",
                checked,
            )
            selected = _select_dimension_candidate(
                candidates,
                tv_format_only=False,
                probe_budget=probe_budget,
                deadline=deadline,
            )
            if selected:
                setattr(args, "_google_preserve_aspect_fallback", True)
                logging.info("Selected a landscape Google Art fallback with preserved aspect ratio")
                return selected

        logging.error(
            "No unused Google Art work matched the TV format or permitted fallback "
            "after checking %d new candidates",
            checked,
        )
        return None

    selected = _select_dimension_candidate(
        candidates,
        tv_format_only=False,
        probe_budget=probe_budget,
        deadline=deadline,
    )
    if not selected:
        checked = TV_FORMAT_MAX_PROBES - probe_budget["remaining"]
        logging.error(
            "No unused landscape Google Art work was found after checking %d new candidates",
            checked,
        )
    return selected


def get_image_url(args, excluded_urls=None):
    helper_color = _read_helper(getattr(args, "google_color_entity", None), "color")
    helper_museum = _read_helper(getattr(args, "google_museum_entity", None), "museum")
    helper_style = _read_helper(getattr(args, "google_style_entity", None), "style")
    color = _normalize_color(helper_color or getattr(args, "google_color", "ANY"))
    museum = _normalize_museum(helper_museum or getattr(args, "google_museum", "ANY"))
    style = _normalize_style(helper_style or getattr(args, "google_style", "ANY"))
    excluded = set(excluded_urls or [])

    try:
        if museum == "ANY" and style == "ANY":
            links = _get_unfiltered_links() if color == "ANY" else _get_color_links(color)
            candidates = [
                _to_absolute_url(link)
                for link in links
                if _to_absolute_url(link) not in excluded
            ]
            total = len(links)
        else:
            catalog = _get_filter_catalog(museum, style)
            candidates = _filter_catalog_candidates(catalog, color, excluded)
            if not candidates and not catalog.get("complete"):
                catalog = _get_filter_catalog(museum, style, expand=True)
                candidates = _filter_catalog_candidates(catalog, color, excluded)
            total = len(catalog.get("assets", []))

        if not candidates:
            logging.error(
                "No unused Google Art works remain for color=%s museum=%s style=%s (%d already sent)",
                color,
                museum,
                style,
                len(excluded),
            )
            return None
        logging.info(
            "Selected Google Art color=%s museum=%s style=%s from %d unused works (%d cached)",
            color,
            museum,
            style,
            len(candidates),
            total,
        )
        return _select_candidate_for_dimensions(candidates, args)
    except (requests.RequestException, ValueError, KeyError, IndexError, json.JSONDecodeError) as error:
        logging.error("Error getting image URL: %s", error)
        return None


def get_image(args, image_url) -> Tuple[Optional[BytesIO], Optional[str]]:
    if not image_url:
        return None, None

    if args.download_high_res:
        logging.info("Downloading high-res image from %s", image_url)
        descriptor, output_file = tempfile.mkstemp(
            prefix="frame-art-",
            suffix=".jpg",
            dir="/tmp",
        )
        os.close(descriptor)
        os.remove(output_file)
        try:
            subprocess.run(
                ["dezoomify-rs", "--max-width", "5001", "--compression", "0", image_url, output_file],
                check=True,
            )
            with open(output_file, "rb") as image_file:
                image_data = BytesIO(image_file.read())
            return image_data, "JPEG"
        except subprocess.CalledProcessError as error:
            logging.error("Failed to download high-res image: %s", error)
            return None, None
        except OSError as error:
            logging.error("Failed to read temporary image: %s", error)
            return None, None
        finally:
            try:
                os.remove(output_file)
            except FileNotFoundError:
                pass
            except OSError as error:
                logging.warning("Could not remove temporary image %s: %s", output_file, error)

    try:
        download_base_url = _resolve_download_base_url(image_url)
        if getattr(args, "preserve_aspect_ratio", False):
            download_url = download_base_url + "=w3840"
        else:
            download_url = download_base_url + "=w3840-h2160-c"
        logging.info("Downloading image from %s", download_url)
        image_response = requests.get(download_url, timeout=60)
        image_response.raise_for_status()
        return BytesIO(image_response.content), "JPEG"
    except requests.RequestException as error:
        logging.error("Error getting image: %s", error)
        return None, None
