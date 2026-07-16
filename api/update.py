import json
import os
import shutil
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spotify_batch_adder import (  # noqa: E402
    DEFAULT_PLAYLIST_ID,
    build_spotify_client,
    run_hourly_update,
)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        secret = os.getenv("CRON_SECRET")
        if secret:
            expected = f"Bearer {secret}"
            if self.headers.get("Authorization") != expected:
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Unauthorized")
                return

        output_dir = Path(os.getenv("SPOTIFY_OUTPUT_DIR", "/tmp/spotify_batch_output"))
        output_dir.mkdir(parents=True, exist_ok=True)

        learned_queries = ROOT / "spotify_batch_output" / "liked_style_queries.json"
        if learned_queries.exists():
            shutil.copy2(learned_queries, output_dir / "liked_style_queries.json")

        try:
            sp = build_spotify_client()
            run_hourly_update(
                sp=sp,
                playlist_id=os.getenv("SPOTIFY_PLAYLIST_ID", DEFAULT_PLAYLIST_ID),
                market=os.getenv("SPOTIFY_MARKET", "US"),
                output_dir=output_dir,
                update_count=int(os.getenv("SPOTIFY_UPDATE_COUNT", "25")),
                request_delay=float(os.getenv("SPOTIFY_REQUEST_DELAY", "1.0")),
                max_query_variants=int(os.getenv("SPOTIFY_MAX_QUERY_VARIANTS", "1")),
                search_without_market=env_bool("SPOTIFY_SEARCH_WITHOUT_MARKET", False),
                skip_existing_check=env_bool("SPOTIFY_SKIP_EXISTING_CHECK", False),
                debug_search=env_bool("SPOTIFY_DEBUG_SEARCH", False),
            )
            payload = {"ok": True}
            status = 200
        except Exception as exc:
            payload = {"ok": False, "error": str(exc)}
            status = 500

        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
