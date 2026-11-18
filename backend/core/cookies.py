"""
Cookie helper functions for amanatyab.
Handles signed cookies for recently viewed items and standard cookies for user preferences like last city.
"""

import json
from typing import List
from urllib.parse import quote, unquote

from django.core.signing import BadSignature, SignatureExpired
from django.http import HttpRequest, HttpResponse

RECENT_ITEMS_COOKIE = "recent_items"
LAST_CITY_COOKIE = "last_city"

# 7 days in seconds
RECENT_ITEMS_MAX_AGE = 7 * 24 * 60 * 60
LAST_CITY_MAX_AGE = 7 * 24 * 60 * 60

RECENT_ITEMS_MAX_COUNT = 6
RECENT_ITEMS_SALT = "amanatyab.core.cookies.recent_items"


def get_recent_item_ids(request: HttpRequest) -> List[int]:
    """
    Retrieve recently viewed item IDs from the signed cookie.
    Returns a list of integer IDs (up to RECENT_ITEMS_MAX_COUNT).
    If the cookie is missing, tampered, expired, or malformed, gracefully returns an empty list.
    """
    if not request:
        return []

    try:
        raw_val = request.get_signed_cookie(
            RECENT_ITEMS_COOKIE,
            default=None,
            salt=RECENT_ITEMS_SALT,
            max_age=RECENT_ITEMS_MAX_AGE,
        )
    except (BadSignature, SignatureExpired, KeyError, Exception):
        return []

    if raw_val is None:
        return []

    parsed_items = []
    if isinstance(raw_val, (list, tuple)):
        parsed_items = raw_val
    elif isinstance(raw_val, str):
        raw_str = raw_val.strip()
        if not raw_str:
            return []
        try:
            loaded = json.loads(raw_str)
            if isinstance(loaded, (list, tuple)):
                parsed_items = loaded
            else:
                parsed_items = [loaded]
        except (json.JSONDecodeError, ValueError):
            parsed_items = [x.strip() for x in raw_str.split(",") if x.strip()]

    valid_ids: List[int] = []
    for item in parsed_items:
        try:
            item_id = int(item)
            if item_id > 0 and item_id not in valid_ids:
                valid_ids.append(item_id)
        except (ValueError, TypeError):
            continue

    return valid_ids[:RECENT_ITEMS_MAX_COUNT]


def add_recent_item_id(response: HttpResponse, request: HttpRequest, item_id: int) -> None:
    """
    Prepend a viewed item ID to the recent_items signed cookie on the response object.
    Maintains a maximum of 6 unique items (last viewed first).
    Sets max_age=7 days, httponly=True, and samesite='Lax'.
    """
    if not response:
        return

    try:
        item_id_int = int(item_id)
        if item_id_int <= 0:
            return
    except (ValueError, TypeError):
        return

    existing_ids = get_recent_item_ids(request)
    # Deduplicate: place the newly viewed item first
    updated_ids = [item_id_int] + [pk for pk in existing_ids if pk != item_id_int]
    updated_ids = updated_ids[:RECENT_ITEMS_MAX_COUNT]

    serialized = json.dumps(updated_ids, separators=(",", ":"))
    response.set_signed_cookie(
        RECENT_ITEMS_COOKIE,
        serialized,
        salt=RECENT_ITEMS_SALT,
        max_age=RECENT_ITEMS_MAX_AGE,
        httponly=True,
        samesite="Lax",
    )


def get_last_city(request: HttpRequest) -> str:
    """
    Retrieve the last selected/viewed city from cookies, unquoting URL encoding.
    """
    if not request:
        return ""
    raw_val = request.COOKIES.get(LAST_CITY_COOKIE, "").strip()
    if not raw_val:
        return ""
    return unquote(raw_val).strip()


def set_last_city(response: HttpResponse, city: str) -> None:
    """
    Set the last_city cookie on the response with a 7-day max_age.
    URL-encodes non-ASCII city names for RFC 6265 HTTP cookie compliance.
    """
    if not response:
        return

    city_cleaned = (city or "").strip()
    if city_cleaned:
        encoded_city = quote(city_cleaned)
        response.set_cookie(
            LAST_CITY_COOKIE,
            encoded_city,
            max_age=LAST_CITY_MAX_AGE,
            samesite="Lax",
        )
