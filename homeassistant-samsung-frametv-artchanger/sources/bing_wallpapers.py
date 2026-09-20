import logging
import random
import requests
from io import BytesIO
from datetime import datetime, timedelta
from typing import Tuple, Optional, Set

def get_image_url(args, excluded_urls: Optional[Set[str]] = None):
    # wallpapers before 2021-08-28 are not available in 4k from https://bing.npanuhin.me/US/en/2021-08-28.jpg
    start_date: datetime = datetime(2021, 8, 28)
    end_date: datetime = datetime.now()
    excluded_urls = excluded_urls or set()
    available_dates = []
    for offset in range((end_date - start_date).days + 1):
        candidate_date = start_date + timedelta(days=offset)
        candidate_url = (
            'https://bing.npanuhin.me/US/en/'
            f"{candidate_date.strftime('%Y-%m-%d')}.jpg"
        )
        if candidate_url not in excluded_urls:
            available_dates.append(candidate_date)
    if not available_dates:
        logging.info('No unused Bing Wallpapers are available.')
        return None

    random_date: datetime = random.choice(available_dates)
    formatted_date: str = random_date.strftime("%Y-%m-%d")
    url: str = f"https://bing.npanuhin.me/US/en/{formatted_date}.jpg"
    return url

def get_image(args, url) -> Tuple[Optional[BytesIO], Optional[str]]:
    try:
        response: requests.Response = requests.get(url)
        response.raise_for_status()
        image_data: BytesIO = BytesIO(response.content)
        return image_data, "JPEG"
    except requests.RequestException as e:
        logging.error(f"Failed to fetch Bing Wallpaper: {str(e)}")
        return None, None
