#!/usr/bin/env python3
"""
Spotify batch playlist builder

What it does:
1. Searches Spotify with 20 style batches.
2. Collects up to 100 unique tracks per batch.
3. Saves a review file: spotify_batches.csv and spotify_batches.json.
4. Adds each batch to your playlist, 100 tracks at a time.

Safety:
- Your Spotify password is never used here.
- Login happens through Spotify OAuth in your browser.
- Your Client ID/Secret stay on your computer.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

import requests
import spotipy
from spotipy.oauth2 import SpotifyOAuth


DEFAULT_PLAYLIST_ID = "6hFjAjRHW88LUKau2rIDHC"
REDIRECT_URI = "http://127.0.0.1:8888/callback"

# Spotify Development Mode now allows max 10 search results per request.
# The script paginates with offset instead of asking for 50.
API_PAGE_LIMIT = 10
SEARCH_LIMIT = 10
DEFAULT_PAGES_PER_QUERY = 2
DEFAULT_REQUEST_DELAY = 0.35
DEFAULT_MAX_QUERY_VARIANTS = 2
DEFAULT_HOURLY_UPDATE_COUNT = 25
DEFAULT_LIKED_LIMIT = 200
DEFAULT_ARTIST_GENRE_LIMIT = 100

HOURLY_STYLE_QUERIES = [
    "G-Eazy style rap",
    "bay area rap",
    "west coast party rap",
    "night drive rap",
    "dark melodic rap",
    "smooth trap rap",
    "late night hip hop",
    "moody rap",
    "club rap explicit",
    "party hip hop",
    "rap banger",
    "west coast club rap",
    "melodic trap",
    "autotune rap",
    "sad trap banger",
    "new school rap",
    "trap hits",
    "viral rap",
    "hip hop hits explicit",
    "latin trap",
    "malianteo",
    "reggaeton rap",
    "rkt argentina",
    "cumbia 420",
    "persian rap",
    "persian trap",
    "turkish rap",
    "french rap",
    "german rap",
    "uk drill",
    "afro trap",
    "phonk rap",
    "gym trap rap",
    "smoke rap",
    "toxic rap",
    "drift phonk rap",
]

BATCH_PLAN = [
    {
        "name": "01_g_eazy_core_english",
        "target_count": 100,
        "min_popularity": 0,
        "queries": [
            "artist:\"G-Eazy\"",
            "\"G-Eazy\" remix",
            "\"G-Eazy\" feat",
            "\"G-Eazy\" type rap",
            "\"Me Myself & I\" rap",
            "\"No Limit\" rap",
            "\"I Mean It\" rap",
            "g eazy style",
            "bay area rap club",
            "west coast party rap"
        ]
    },
    {
        "name": "02_english_night_drive_rap",
        "target_count": 100,
        "min_popularity": 20,
        "queries": [
            "night drive rap",
            "dark melodic rap",
            "smooth trap rap",
            "late night hip hop",
            "melodic hip hop",
            "moody rap",
            "rap for driving",
            "club rap night",
            "trap night drive",
            "toxic rap"
        ]
    },
    {
        "name": "03_english_club_rap",
        "target_count": 100,
        "min_popularity": 20,
        "queries": [
            "club rap explicit",
            "party hip hop",
            "rap banger",
            "hip hop club",
            "rap remix club",
            "west coast club rap",
            "strip club rap",
            "new school rap banger",
            "turn up rap",
            "trap party"
        ]
    },
    {
        "name": "04_english_trap_melodic",
        "target_count": 100,
        "min_popularity": 20,
        "queries": [
            "melodic trap",
            "trap rap melodic",
            "rap melodic explicit",
            "autotune rap",
            "sad trap banger",
            "Don Toliver type",
            "Tory Lanez type",
            "A Boogie type",
            "NAV type rap",
            "Post Malone type rap"
        ]
    },
    {
        "name": "05_english_new_school_mix",
        "target_count": 100,
        "min_popularity": 20,
        "queries": [
            "new school rap",
            "trap hits",
            "hip hop hits explicit",
            "rap 2024",
            "rap 2025",
            "rap 2026",
            "viral rap",
            "drill rap club",
            "trap remix",
            "hip hop remix"
        ]
    },
    {
        "name": "06_spanish_malianteo_boricua",
        "target_count": 100,
        "min_popularity": 10,
        "queries": [
            "malianteo",
            "malianteo boricua",
            "trap boricua",
            "reggaeton maleanteo",
            "calle reggaeton",
            "reggaeton calle",
            "Ñengo Flow",
            "Anuel AA malianteo",
            "Bryant Myers",
            "Arcangel malianteo"
        ]
    },
    {
        "name": "07_spanish_latin_trap",
        "target_count": 100,
        "min_popularity": 15,
        "queries": [
            "latin trap",
            "trap latino",
            "trap latino explicit",
            "Bad Bunny trap",
            "Myke Towers trap",
            "Eladio Carrion",
            "Mora trap",
            "Jhayco trap",
            "Duki trap",
            "Khea trap"
        ]
    },
    {
        "name": "08_spanish_reggaeton_dark",
        "target_count": 100,
        "min_popularity": 15,
        "queries": [
            "reggaeton oscuro",
            "reggaeton dark",
            "reggaeton de calle",
            "perreo oscuro",
            "perreo intenso",
            "reggaeton lento dark",
            "reggaeton remix",
            "latin club reggaeton",
            "underground reggaeton",
            "old school reggaeton"
        ]
    },
    {
        "name": "09_spanish_perreo_party",
        "target_count": 100,
        "min_popularity": 20,
        "queries": [
            "perreo",
            "perreo intenso",
            "reggaeton party",
            "perreo remix",
            "reggaeton banger",
            "dembow reggaeton",
            "neoperreo",
            "Ryan Castro",
            "Blessd",
            "Cris Mj"
        ]
    },
    {
        "name": "10_argentina_trap_turreo",
        "target_count": 100,
        "min_popularity": 10,
        "queries": [
            "trap argentino",
            "turreo",
            "turreo argentino",
            "rap argentino trap",
            "Duki",
            "YSY A",
            "Neo Pistea",
            "Cazzu",
            "Lit Killah",
            "Tiago PZK"
        ]
    },
    {
        "name": "11_rkt_cumbia_420",
        "target_count": 100,
        "min_popularity": 5,
        "queries": [
            "RKT",
            "rkt remix",
            "cumbia 420",
            "cumbia 420 remix",
            "turreo rkt",
            "Kaleb Di Masi",
            "L-Gante",
            "La Joaqui",
            "Ecko rkt",
            "Alan Gomez rkt"
        ]
    },
    {
        "name": "12_supermerk2_cumbia_villera",
        "target_count": 100,
        "min_popularity": 0,
        "queries": [
            "Supermerk2",
            "Supermerk2 remix",
            "cumbia villera",
            "cumbia villera argentina",
            "Damas Gratis",
            "Pablito Lescano",
            "Yerba Brava",
            "Los Pibes Chorros",
            "Flor de Piedra",
            "Mala Fama"
        ]
    },
    {
        "name": "13_migrantes_cumbia_pop_rkt",
        "target_count": 100,
        "min_popularity": 5,
        "queries": [
            "Migrantes",
            "Migrantes remix",
            "cumbia pop argentina",
            "cumbia argentina moderna",
            "rkt pop",
            "cumbia rkt",
            "Ke Personajes",
            "Q Lokura",
            "La Konga",
            "Rafaga remix"
        ]
    },
    {
        "name": "14_cumbia_remix_turreo_mix",
        "target_count": 100,
        "min_popularity": 5,
        "queries": [
            "cumbia remix",
            "cumbia callejera",
            "cumbia argentina remix",
            "cumbia villera remix",
            "rkt cumbia remix",
            "turreo remix",
            "cachengue",
            "cachengue remix",
            "cumbia cheta",
            "cumbia sonidera remix"
        ]
    },
    {
        "name": "15_persian_rap_legends",
        "target_count": 100,
        "min_popularity": 0,
        "queries": [
            "Persian rap",
            "Iranian rap",
            "rap farsi",
            "رپ فارسی",
            "رپ ایرانی",
            "Hichkas",
            "Reza Pishro",
            "Yas rap",
            "Zedbazi",
            "Bahram rap"
        ]
    },
    {
        "name": "16_persian_trap_melodic",
        "target_count": 100,
        "min_popularity": 0,
        "queries": [
            "Persian trap",
            "trap farsi",
            "ترپ فارسی",
            "Iranian trap",
            "rap farsi trap",
            "Behzad Leito",
            "Sepehr Khalse",
            "Koorosh",
            "Arta",
            "Catchybeatz"
        ]
    },
    {
        "name": "17_persian_party_club_rap",
        "target_count": 100,
        "min_popularity": 0,
        "queries": [
            "Persian party rap",
            "Iranian hip hop club",
            "rap farsi party",
            "Persian hip hop",
            "hip hop farsi",
            "Zedbazi party",
            "Sijal",
            "Sohrab MJ",
            "Mehrad Hidden",
            "Alireza JJ"
        ]
    },
    {
        "name": "18_persian_dark_drill",
        "target_count": 100,
        "min_popularity": 0,
        "queries": [
            "Persian drill",
            "Iranian drill",
            "dark Persian rap",
            "rap farsi dark",
            "Persian underground rap",
            "Putak",
            "021G",
            "Shayea",
            "Ho3ein",
            "Gdaal"
        ]
    },
    {
        "name": "19_mixed_english_spanish_remix",
        "target_count": 100,
        "min_popularity": 10,
        "queries": [
            "latin hip hop remix",
            "spanish english rap remix",
            "reggaeton hip hop remix",
            "latin trap remix",
            "malianteo remix",
            "rap latino remix",
            "perreo hip hop remix",
            "G-Eazy latin remix",
            "trap latino english remix",
            "club latin rap"
        ]
    },
    {
        "name": "20_global_filler_all_styles",
        "target_count": 100,
        "min_popularity": 5,
        "queries": [
            "global trap",
            "latin rap",
            "international hip hop",
            "trap remix 2025",
            "rap remix 2025",
            "reggaeton remix 2025",
            "cumbia remix 2025",
            "Persian rap remix",
            "malianteo 2025",
            "RKT 2025"
        ]
    }
]


def build_spotify_client() -> spotipy.Spotify:
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    token_info_json = os.getenv("SPOTIFY_TOKEN_INFO_JSON")
    cache_path = os.getenv("SPOTIFY_CACHE_PATH", ".cache")

    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing env vars. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET first."
        )

    if token_info_json:
        cache_file = Path(cache_path)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(token_info_json, encoding="utf-8")

    scope = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative user-read-email user-library-read"

    return spotipy.Spotify(
        auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=REDIRECT_URI,
            scope=scope,
            open_browser=True,
            cache_path=cache_path,
        ),
        requests_timeout=30,
        retries=0,
        status_retries=0,
        backoff_factor=0.7,
    )


def get_access_token(sp: spotipy.Spotify) -> str:
    token_info = sp.auth_manager.get_access_token(as_dict=True)
    if isinstance(token_info, dict):
        return token_info["access_token"]
    return token_info


def format_retry_after(value: str | None) -> str:
    if not value:
        return "unknown"
    try:
        seconds = int(value)
    except ValueError:
        return value

    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{seconds} seconds ({hours}h {minutes}m {secs}s)"
    if minutes:
        return f"{seconds} seconds ({minutes}m {secs}s)"
    return f"{seconds} seconds"


def raise_for_spotify_response(response: requests.Response, method: str, url: str) -> None:
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        raise RuntimeError(
            f"{method} {url} rate limited: retry after {format_retry_after(retry_after)}. "
            "Stop now, wait, then rerun with lower --pages-per-query and higher --request-delay."
        )
    if response.status_code >= 400:
        raise RuntimeError(f"{method} {url} failed: {response.status_code} {response.text}")


def is_rate_limit_error(exc: Exception) -> bool:
    status = getattr(exc, "http_status", None)
    if status == 429:
        return True
    return "429" in str(exc) or "rate/request limit" in str(exc).lower()


def spotify_get(sp: spotipy.Spotify, path: str, params: Dict | None = None) -> Dict:
    token = get_access_token(sp)
    url = f"https://api.spotify.com/v1/{path.lstrip('/')}"
    response = requests.get(url, headers={"Authorization": f"Bearer {token}"}, params=params or {}, timeout=30)
    raise_for_spotify_response(response, "GET", url)
    return response.json()


def spotify_post(sp: spotipy.Spotify, path: str, payload: Dict | None = None) -> Dict:
    token = get_access_token(sp)
    url = f"https://api.spotify.com/v1/{path.lstrip('/')}"
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload or {},
        timeout=30,
    )
    raise_for_spotify_response(response, "POST", url)
    if response.text.strip():
        return response.json()
    return {}


def spotify_search(sp: spotipy.Spotify, params: Dict) -> Dict:
    return spotify_get(sp, "search", params=params)


def normalize_style_term(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s-]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def load_learned_style_queries(output_dir: Path) -> List[str]:
    path = output_dir / "liked_style_queries.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    queries = data.get("queries", []) if isinstance(data, dict) else data
    if not isinstance(queries, list):
        return []
    return [q for q in queries if isinstance(q, str) and q.strip()]


def save_learned_style_queries(output_dir: Path, queries: List[str], genre_counts: Counter, artist_counts: Counter) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "liked_style_queries.json"
    payload = {
        "queries": queries,
        "top_genres": genre_counts.most_common(100),
        "top_artists": artist_counts.most_common(100),
        "updated_at": int(time.time()),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved learned style queries: {path}")


def get_liked_tracks(
    sp: spotipy.Spotify,
    market: str,
    limit: int,
    request_delay: float,
) -> List[Dict]:
    tracks: List[Dict] = []
    offset = 0

    while True:
        page_limit = 50 if limit <= 0 else min(50, limit - len(tracks))
        if page_limit <= 0:
            break

        page = spotify_get(
            sp,
            "me/tracks",
            params={
                "limit": page_limit,
                "offset": offset,
                "market": market,
            },
        )
        items = page.get("items", [])
        if not items:
            break

        for entry in items:
            track = entry.get("track") or {}
            if track.get("uri"):
                tracks.append(track)

        if not page.get("next"):
            break
        offset += page_limit
        time.sleep(request_delay)

    return tracks


def get_artist_genres(
    sp: spotipy.Spotify,
    artist_ids: List[str],
    request_delay: float,
) -> Dict[str, List[str]]:
    genres_by_artist: Dict[str, List[str]] = {}

    for artist_id in artist_ids:
        try:
            artist = spotify_get(sp, f"artists/{artist_id}")
        except Exception as exc:
            if is_rate_limit_error(exc):
                raise
            print(f"Artist genre read failed: {artist_id} | {exc}")
            continue

        genres_by_artist[artist_id] = artist.get("genres") or []
        time.sleep(request_delay)

    return genres_by_artist


def learn_liked_styles(
    sp: spotipy.Spotify,
    market: str,
    output_dir: Path,
    liked_limit: int,
    artist_genre_limit: int,
    request_delay: float,
) -> List[str]:
    tracks = get_liked_tracks(sp, market, liked_limit, request_delay)
    if not tracks:
        print("No liked tracks found.")
        return []

    artist_counts: Counter = Counter()
    artist_ids: List[str] = []
    artist_id_seen: Set[str] = set()

    for track in tracks:
        for artist in track.get("artists", []):
            artist_name = artist.get("name")
            artist_id = artist.get("id")
            if artist_name:
                artist_counts[artist_name] += 1
            if artist_id and artist_id not in artist_id_seen:
                artist_id_seen.add(artist_id)
                artist_ids.append(artist_id)

    genre_counts: Counter = Counter()
    artist_ids_to_scan = artist_ids if artist_genre_limit <= 0 else artist_ids[:artist_genre_limit]
    genres_by_artist = get_artist_genres(sp, artist_ids_to_scan, request_delay)
    for genres in genres_by_artist.values():
        for genre in genres:
            genre = normalize_style_term(genre)
            if genre:
                genre_counts[genre] += 1

    queries: List[str] = []

    def add_query(query: str) -> None:
        query = normalize_style_term(query)
        if query and query not in queries:
            queries.append(query)

    for genre, _count in genre_counts.most_common(60):
        add_query(genre)

    for genre, _count in genre_counts.most_common(30):
        if "rap" not in genre and "trap" not in genre and "hip hop" not in genre:
            add_query(f"{genre} rap")
            add_query(f"{genre} trap")

    for artist_name, _count in artist_counts.most_common(30):
        add_query(f"{artist_name} style")

    save_learned_style_queries(output_dir, queries[:120], genre_counts, artist_counts)
    print(f"Liked tracks read: {len(tracks)}")
    print(f"Artists analyzed: {len(genres_by_artist)}")
    print(f"Learned queries: {len(queries[:120])}")
    return queries[:120]


def create_playlist(
    sp: spotipy.Spotify,
    name: str,
    public: bool,
    description: str,
) -> str:
    playlist = spotify_post(
        sp,
        "me/playlists",
        {
            "name": name,
            "public": public,
            "description": description,
        },
    )
    playlist_id = playlist.get("id")
    if not playlist_id:
        raise RuntimeError(f"Spotify did not return a playlist id: {playlist}")

    print(f"Created playlist: {playlist.get('name', name)} | id={playlist_id}")
    return playlist_id


def get_existing_uris(sp: spotipy.Spotify, playlist_id: str, market: str) -> Set[str]:
    """Read playlist tracks through the new /playlists/{id}/items endpoint."""
    existing = set()
    offset = 0

    while True:
        page = spotify_get(
            sp,
            f"playlists/{playlist_id}/items",
            params={
                "fields": "items(item(uri)),next",
                "limit": API_PAGE_LIMIT,
                "offset": offset,
                "market": market,
            },
        )

        for entry in page.get("items", []):
            item = entry.get("item")
            if item and item.get("uri") and item.get("uri", "").startswith("spotify:track:"):
                existing.add(item["uri"])

        if not page.get("next"):
            break

        offset += API_PAGE_LIMIT

    return existing

def normalize_query_variants(query: str) -> List[str]:
    """Create Spotify-search-friendly fallbacks for brittle quoted/field queries."""
    variants: List[str] = []

    def add(value: str) -> None:
        value = re.sub(r"\s+", " ", value).strip()
        if value and value not in variants:
            variants.append(value)

    add(query)

    # artist:"G-Eazy" -> G-Eazy and G Eazy
    artist_match = re.search(r'artist:\"?([^\"]+)\"?', query, flags=re.IGNORECASE)
    if artist_match:
        artist = artist_match.group(1).strip()
        add(artist)
        add(artist.replace("-", " "))
        add(f"artist:{artist}")
        add(f"artist:{artist.replace('-', ' ')}")

    # Remove quotes because Spotify search can be too strict with exact phrases.
    unquoted = query.replace('"', '')
    add(unquoted)
    add(unquoted.replace("-", " "))

    return variants


def search_artist_catalog(
    sp: spotipy.Spotify,
    artist_name: str,
    market: str,
    min_popularity: int,
    request_delay: float,
) -> List[Dict]:
    """Find tracks by an artist using allowed endpoints only.

    Notes for Spotify Development Mode:
    - /artists/{id}/top-tracks is removed, so this function does not call it.
    - Bulk /tracks?ids=... is removed, so album-track results are used directly.
    - Popularity may be missing, so missing popularity never blocks a track.
    """
    results: List[Dict] = []
    seen_uris: Set[str] = set()

    try:
        artist_response = spotify_search(
            sp,
            {
                "q": artist_name,
                "type": "artist",
                "market": market,
                "limit": API_PAGE_LIMIT,
            },
        )
    except Exception as exc:
        if is_rate_limit_error(exc):
            raise
        print(f"Artist search failed: {artist_name} | {exc}")
        return results

    artists = artist_response.get("artists", {}).get("items", [])
    if not artists:
        return results

    wanted = artist_name.lower().replace("-", " ").strip()
    selected = artists[0]
    for artist in artists:
        candidate = (artist.get("name") or "").lower().replace("-", " ").strip()
        if candidate == wanted:
            selected = artist
            break

    artist_id = selected.get("id")
    selected_artist_name = selected.get("name", artist_name)
    if not artist_id:
        return results

    try:
        offset = 0
        albums = []
        while offset < 200:
            page = spotify_get(
                sp,
                f"artists/{artist_id}/albums",
                params={
                    "include_groups": "album,single,appears_on,compilation",
                    "market": market,
                    "limit": API_PAGE_LIMIT,
                    "offset": offset,
                },
            )
            items = page.get("items", [])
            albums.extend(items)
            if not page.get("next") or not items:
                break
            offset += API_PAGE_LIMIT
            time.sleep(request_delay)

        album_ids_seen: Set[str] = set()
        for album in albums:
            album_id = album.get("id")
            album_name = album.get("name", "")
            if not album_id or album_id in album_ids_seen:
                continue
            album_ids_seen.add(album_id)

            track_offset = 0
            while track_offset < 100:
                try:
                    tracks_page = spotify_get(
                        sp,
                        f"albums/{album_id}/tracks",
                        params={
                            "limit": API_PAGE_LIMIT,
                            "offset": track_offset,
                            "market": market,
                        },
                    )
                except Exception as exc:
                    if is_rate_limit_error(exc):
                        raise
                    break

                items = tracks_page.get("items", [])
                if not items:
                    break

                for item in items:
                    uri = item.get("uri")
                    if not uri or uri in seen_uris:
                        continue

                    artist_names = [a.get("name", "") for a in item.get("artists", [])]
                    if not any(a.lower() == selected_artist_name.lower() for a in artist_names):
                        continue

                    popularity = item.get("popularity")
                    if popularity is not None and popularity < min_popularity:
                        continue

                    results.append(
                        {
                            "uri": uri,
                            "track": item.get("name", ""),
                            "artists": ", ".join(artist_names),
                            "album": album_name,
                            "popularity": popularity if popularity is not None else "",
                            "explicit": bool(item.get("explicit")),
                            "query": f"artist_catalog:{selected_artist_name}",
                        }
                    )
                    seen_uris.add(uri)

                if not tracks_page.get("next"):
                    break
                track_offset += API_PAGE_LIMIT
                time.sleep(request_delay)

    except Exception as exc:
        if is_rate_limit_error(exc):
            raise
        print(f"Artist catalog failed: {artist_name} | {exc}")

    return results

def search_tracks(
    sp: spotipy.Spotify,
    query: str,
    market: str,
    max_pages: int,
    min_popularity: int,
    request_delay: float,
    include_artist_catalog: bool,
    search_without_market: bool,
    max_query_variants: int,
    debug: bool = False,
) -> List[Dict]:
    results: List[Dict] = []
    seen_uris: Set[str] = set()

    artist_match = re.search(r'artist:\"?([^\"]+)\"?', query, flags=re.IGNORECASE)
    if artist_match and include_artist_catalog:
        artist_name = artist_match.group(1).strip()
        for track in search_artist_catalog(sp, artist_name, market, min_popularity, request_delay):
            uri = track["uri"]
            if uri not in seen_uris:
                seen_uris.add(uri)
                results.append(track)

    variants = normalize_query_variants(query)[:max(1, max_query_variants)]
    market_modes = (True, False) if search_without_market else (True,)

    for variant in variants:
        for use_market in market_modes:
            if len(results) >= SEARCH_LIMIT * max_pages:
                break

            for page_index in range(max_pages):
                offset = page_index * SEARCH_LIMIT

                try:
                    kwargs = {
                        "q": variant,
                        "type": "track",
                        "limit": SEARCH_LIMIT,
                        "offset": offset,
                    }
                    if use_market:
                        kwargs["market"] = market
                    response = spotify_search(sp, kwargs)
                except Exception as exc:
                    if is_rate_limit_error(exc):
                        raise RuntimeError(
                            "Spotify rate limit hit during search. "
                            "Wait for Spotify's retry window, then rerun with "
                            "--pages-per-query 1 --request-delay 1.0"
                        ) from exc
                    print(f"Search failed: {variant} | {exc}")
                    time.sleep(2)
                    continue

                items = response.get("tracks", {}).get("items", [])
                if debug and page_index == 0:
                    market_label = market if use_market else "no-market"
                    print(f"    debug search {market_label}: {variant!r} -> raw {len(items)}")

                if not items:
                    break

                for item in items:
                    uri = item.get("uri")
                    if not uri or uri in seen_uris:
                        continue

                    popularity = item.get("popularity")
                    # Spotify Development Mode may omit popularity. If omitted, do not filter it out.
                    if popularity is not None and popularity < min_popularity:
                        continue

                    artists = ", ".join(a.get("name", "") for a in item.get("artists", []))

                    results.append(
                        {
                            "uri": uri,
                            "track": item.get("name", ""),
                            "artists": artists,
                            "album": item.get("album", {}).get("name", ""),
                            "popularity": popularity if popularity is not None else "",
                            "explicit": bool(item.get("explicit")),
                            "query": variant,
                        }
                    )
                    seen_uris.add(uri)

                time.sleep(request_delay)

    return results

def collect_batches(
    sp: spotipy.Spotify,
    playlist_id: str,
    market: str,
    pages_per_query: int,
    request_delay: float,
    include_artist_catalog: bool,
    search_without_market: bool,
    max_query_variants: int,
    skip_existing_check: bool = False,
    debug_search: bool = False,
) -> Dict[str, List[Dict]]:
    if skip_existing_check:
        print("Skipping current-playlist read. Duplicate prevention will only apply inside this run.")
        global_seen = set()
    else:
        print("Reading current playlist to avoid duplicates...")
        try:
            global_seen = get_existing_uris(sp, playlist_id, market)
            print(f"Existing playlist tracks: {len(global_seen)}")
        except Exception as exc:
            print("Warning: could not read current playlist tracks.")
            print("This usually means the Spotify account you approved is not the playlist owner/collaborator, the app user is not allowlisted, or the cached token has old scopes.")
            print(f"Spotify error: {exc}")
            print("Continuing without existing-playlist duplicate check. If adding also fails with 403, fix account ownership/allowlist/scopes first.")
            global_seen = set()

    collected_batches = {}

    for batch in BATCH_PLAN:
        batch_name = batch["name"]
        target = batch["target_count"]
        min_popularity = batch["min_popularity"]
        batch_tracks = []

        print(f"\nCollecting {batch_name} | target {target}")

        for query in batch["queries"]:
            if len(batch_tracks) >= target:
                break

            found = search_tracks(
                sp=sp,
                query=query,
                market=market,
                max_pages=pages_per_query,
                min_popularity=min_popularity,
                request_delay=request_delay,
                include_artist_catalog=include_artist_catalog,
                search_without_market=search_without_market,
                max_query_variants=max_query_variants,
                debug=debug_search,
            )

            for track in found:
                uri = track["uri"]
                if uri in global_seen:
                    continue

                track["batch"] = batch_name
                batch_tracks.append(track)
                global_seen.add(uri)

                if len(batch_tracks) >= target:
                    break

            print(f"  {len(batch_tracks):03d}/{target} | {query}")

        collected_batches[batch_name] = batch_tracks

        if len(batch_tracks) < target:
            print(f"  Warning: only found {len(batch_tracks)} tracks for {batch_name}")

    return collected_batches


def save_outputs(collected_batches: Dict[str, List[Dict]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "spotify_batches.json"
    csv_path = output_dir / "spotify_batches.csv"

    with json_path.open("w", encoding="utf-8") as f:
        json.dump(collected_batches, f, ensure_ascii=False, indent=2)

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "batch",
                "track",
                "artists",
                "album",
                "popularity",
                "explicit",
                "uri",
                "query",
            ],
        )
        writer.writeheader()

        for tracks in collected_batches.values():
            for track in tracks:
                writer.writerow(track)

    print(f"\nSaved review files:")
    print(f"  {json_path}")
    print(f"  {csv_path}")


def add_batch(
    sp: spotipy.Spotify,
    playlist_id: str,
    batch_name: str,
    tracks: List[Dict],
) -> None:
    uris = [track["uri"] for track in tracks]

    if not uris:
        print(f"Skipping empty batch: {batch_name}")
        return

    print(f"Adding {batch_name}: {len(uris)} tracks")

    for start in range(0, len(uris), 100):
        chunk = uris[start : start + 100]
        # Use the new Development Mode playlist endpoint. Spotipy versions may still call /tracks.
        spotify_post(sp, f"playlists/{playlist_id}/items", {"uris": chunk})
        print(f"  Added {start + len(chunk)}/{len(uris)}")
        time.sleep(1.2)


def load_state(state_path: Path) -> Dict:
    if not state_path.exists():
        return {"query_index": 0, "seen_uris": []}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return {"query_index": 0, "seen_uris": []}
    if not isinstance(state, dict):
        return {"query_index": 0, "seen_uris": []}
    state.setdefault("query_index", 0)
    state.setdefault("seen_uris", [])
    return state


def save_state(state_path: Path, state: Dict) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def collect_hourly_tracks(
    sp: spotipy.Spotify,
    playlist_id: str,
    market: str,
    update_count: int,
    request_delay: float,
    max_query_variants: int,
    search_without_market: bool,
    state_path: Path,
    skip_existing_check: bool,
    debug_search: bool,
    persist_state: bool = True,
) -> List[Dict]:
    state = load_state(state_path)
    state_seen = set(state.get("seen_uris", []))

    if skip_existing_check:
        global_seen = set(state_seen)
    else:
        print("Reading current playlist to avoid duplicates...")
        try:
            global_seen = get_existing_uris(sp, playlist_id, market) | state_seen
            print(f"Known tracks: {len(global_seen)}")
        except Exception as exc:
            if is_rate_limit_error(exc):
                raise
            print(f"Warning: playlist read failed, using state file only: {exc}")
            global_seen = set(state_seen)

    collected: List[Dict] = []
    style_queries: List[str] = []
    for query in load_learned_style_queries(state_path.parent) + HOURLY_STYLE_QUERIES:
        if query not in style_queries:
            style_queries.append(query)

    if not style_queries:
        raise RuntimeError("No hourly style queries available.")

    start_index = int(state.get("query_index", 0)) % len(style_queries)
    query_index = start_index
    attempts = 0
    max_attempts = len(style_queries)

    while len(collected) < update_count and attempts < max_attempts:
        query = style_queries[query_index]
        found = search_tracks(
            sp=sp,
            query=query,
            market=market,
            max_pages=1,
            min_popularity=0,
            request_delay=request_delay,
            include_artist_catalog=False,
            search_without_market=search_without_market,
            max_query_variants=max_query_variants,
            debug=debug_search,
        )

        for track in found:
            uri = track["uri"]
            if uri in global_seen:
                continue
            track["batch"] = "hourly_update"
            collected.append(track)
            global_seen.add(uri)
            state_seen.add(uri)
            if len(collected) >= update_count:
                break

        print(f"  {len(collected):03d}/{update_count} | {query}")
        query_index = (query_index + 1) % len(style_queries)
        attempts += 1

    if persist_state:
        state["query_index"] = query_index
        state["seen_uris"] = sorted(state_seen)[-10000:]
        save_state(state_path, state)
    return collected


def run_hourly_update(
    sp: spotipy.Spotify,
    playlist_id: str,
    market: str,
    output_dir: Path,
    update_count: int,
    request_delay: float,
    max_query_variants: int,
    search_without_market: bool,
    skip_existing_check: bool,
    debug_search: bool,
) -> None:
    state_path = output_dir / "hourly_state.json"
    tracks = collect_hourly_tracks(
        sp=sp,
        playlist_id=playlist_id,
        market=market,
        update_count=update_count,
        request_delay=request_delay,
        max_query_variants=max_query_variants,
        search_without_market=search_without_market,
        state_path=state_path,
        skip_existing_check=skip_existing_check,
        debug_search=debug_search,
    )

    if not tracks:
        print("No new hourly tracks found.")
        return

    save_outputs({"hourly_update": tracks}, output_dir)
    add_batch(sp, playlist_id, "hourly_update", tracks)


def add_batches_interactive(
    sp: spotipy.Spotify,
    playlist_id: str,
    collected_batches: Dict[str, List[Dict]],
    add_all: bool,
) -> None:
    for batch_name, tracks in collected_batches.items():
        if not tracks:
            continue

        if not add_all:
            answer = input(f"\nAdd {batch_name} with {len(tracks)} tracks? [y/N]: ").strip().lower()
            if answer != "y":
                print(f"Skipped {batch_name}")
                continue

        add_batch(sp, playlist_id, batch_name, tracks)

    print("\nDone.")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--playlist-id", default=DEFAULT_PLAYLIST_ID)
    parser.add_argument("--market", default="US")
    parser.add_argument("--pages-per-query", type=int, default=DEFAULT_PAGES_PER_QUERY)
    parser.add_argument("--request-delay", type=float, default=DEFAULT_REQUEST_DELAY, help="Seconds to sleep between Spotify search/catalog requests.")
    parser.add_argument("--max-query-variants", type=int, default=DEFAULT_MAX_QUERY_VARIANTS, help="Maximum fallback query variants to try per query.")
    parser.add_argument("--search-without-market", action="store_true", help="Also retry searches without market. Uses more API requests.")
    parser.add_argument("--include-artist-catalog", action="store_true", help="Also scan artist albums for artist: queries. This uses many API requests and can trigger rate limits.")
    parser.add_argument("--output-dir", default="spotify_batch_output")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--add-all", action="store_true")
    parser.add_argument("--learn-liked-styles", action="store_true", help="Read liked songs and save learned genre/style search queries.")
    parser.add_argument("--liked-limit", type=int, default=DEFAULT_LIKED_LIMIT, help="Number of liked songs to inspect. Use 0 for all liked songs.")
    parser.add_argument("--artist-genre-limit", type=int, default=DEFAULT_ARTIST_GENRE_LIMIT, help="Maximum unique liked-song artists to inspect for genres. Use 0 for all artists.")
    parser.add_argument("--hourly-update", action="store_true", help="Add a small rotating set of new tracks and exit. Designed for Task Scheduler.")
    parser.add_argument("--update-count", type=int, default=DEFAULT_HOURLY_UPDATE_COUNT, help="Number of tracks to add in hourly-update mode.")
    parser.add_argument("--create-playlist", help="Create a new playlist with this name, then add batches to it.")
    parser.add_argument("--playlist-public", action="store_true", help="Create the new playlist as public. Default is private.")
    parser.add_argument("--playlist-description", default="Generated by spotify_batch_adder.py")
    parser.add_argument("--skip-existing-check", action="store_true", help="Do not read current playlist before collecting tracks. Useful when Spotify returns 403 on playlist item reads.")
    parser.add_argument("--debug-search", action="store_true", help="Print raw Spotify search result counts for troubleshooting.")
    args = parser.parse_args()

    try:
        sp = build_spotify_client()
        try:
            me = sp.current_user()
            print(f"Authorized Spotify user: {me.get('display_name') or me.get('id')} | id={me.get('id')} | email={me.get('email', 'not available')}")
        except Exception as exc:
            print(f"Warning: could not read current Spotify user: {exc}")

        playlist_id = args.playlist_id
        if args.create_playlist:
            if args.generate_only:
                print("Generate-only mode. New playlist will not be created.")
            else:
                playlist_id = create_playlist(
                    sp=sp,
                    name=args.create_playlist,
                    public=args.playlist_public,
                    description=args.playlist_description,
                )

        output_dir = Path(args.output_dir)

        if args.learn_liked_styles:
            learn_liked_styles(
                sp=sp,
                market=args.market,
                output_dir=output_dir,
                liked_limit=args.liked_limit,
                artist_genre_limit=args.artist_genre_limit,
                request_delay=args.request_delay,
            )
            return 0

        if args.hourly_update:
            if args.generate_only:
                print("Generate-only mode. Hourly update will not add to Spotify.")
                tracks = collect_hourly_tracks(
                    sp=sp,
                    playlist_id=playlist_id,
                    market=args.market,
                    update_count=args.update_count,
                    request_delay=args.request_delay,
                    max_query_variants=args.max_query_variants,
                    search_without_market=args.search_without_market,
                    state_path=output_dir / "hourly_state.json",
                    skip_existing_check=args.skip_existing_check,
                    debug_search=args.debug_search,
                    persist_state=False,
                )
                save_outputs({"hourly_update": tracks}, output_dir)
                return 0

            run_hourly_update(
                sp=sp,
                playlist_id=playlist_id,
                market=args.market,
                output_dir=output_dir,
                update_count=args.update_count,
                request_delay=args.request_delay,
                max_query_variants=args.max_query_variants,
                search_without_market=args.search_without_market,
                skip_existing_check=args.skip_existing_check,
                debug_search=args.debug_search,
            )
            return 0

        batches = collect_batches(
            sp=sp,
            playlist_id=playlist_id,
            market=args.market,
            pages_per_query=args.pages_per_query,
            request_delay=args.request_delay,
            include_artist_catalog=args.include_artist_catalog,
            search_without_market=args.search_without_market,
            max_query_variants=args.max_query_variants,
            skip_existing_check=args.skip_existing_check,
            debug_search=args.debug_search,
        )

        save_outputs(batches, output_dir)

        total = sum(len(tracks) for tracks in batches.values())
        print(f"\nTotal collected: {total}")

        if args.generate_only:
            print("Generate-only mode. Nothing was added to Spotify.")
            return 0

        add_batches_interactive(
            sp=sp,
            playlist_id=playlist_id,
            collected_batches=batches,
            add_all=args.add_all,
        )

        return 0

    except KeyboardInterrupt:
        print("\nStopped by user.")
        return 130
    except Exception as exc:
        print(f"\nError: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
