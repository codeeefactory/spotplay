import json
import os
import shutil
import sys
from http.server import BaseHTTPRequestHandler
from html import escape
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from spotify_batch_adder import (  # noqa: E402
    DEFAULT_PLAYLIST_ID,
    build_spotify_client,
    get_or_create_playlist_by_name,
    list_current_user_playlists,
    run_hourly_update,
    spotify_get,
)


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def html_page(
    message: str = "",
    result: dict | None = None,
    status: int = 200,
    token: str = "",
    playlists: list[dict] | None = None,
) -> tuple[int, bytes, str]:
    result_html = ""
    if result:
        result_html = f"<pre>{escape(json.dumps(result, indent=2, ensure_ascii=False))}</pre>"
    elif message:
        result_html = f"<p>{escape(message)}</p>"

    token_input = (
        f'<input id="token" name="token" type="hidden" value="{escape(token, quote=True)}">'
        if token
        else '<label for="token">Secret token</label><input id="token" name="token" type="password" required>'
    )

    playlist_options = ""
    if playlists:
        options = ['<option value="">Create new playlist...</option>']
        for playlist in playlists:
            playlist_id = escape(playlist.get("id", ""), quote=True)
            playlist_name = escape(playlist.get("name", "Untitled"), quote=True)
            options.append(f'<option value="{playlist_id}">{playlist_name}</option>')
        playlist_options = f"""
    <label for="playlist_id">Choose existing playlist</label>
    <select id="playlist_id" name="playlist_id">
      {''.join(options)}
    </select>
"""

    body = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Spotify Playlist Update</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 16px; background: #111; color: #f5f5f5; }}
    label {{ display: block; margin: 14px 0 6px; }}
    input, select {{ width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #444; background: #1c1c1c; color: #fff; }}
    button {{ margin-top: 18px; padding: 10px 16px; border: 0; border-radius: 6px; background: #1db954; color: #041207; font-weight: 700; cursor: pointer; }}
    button[disabled] {{ opacity: .6; cursor: wait; }}
    pre {{ white-space: pre-wrap; background: #1c1c1c; border: 1px solid #333; border-radius: 6px; padding: 12px; }}
    small {{ color: #aaa; }}
  </style>
</head>
<body>
  <h1>Spotify Playlist Update</h1>
  <p><small>Open with <code>?token=YOUR_SECRET</code> to load your playlists.</small></p>
  <form method="post" action="/api/update">
    {token_input}
    {playlist_options}
    <label for="new_playlist_name">New playlist name</label>
    <input id="new_playlist_name" name="new_playlist_name" placeholder="Only used when no existing playlist is selected">
    <label for="update_count">Tracks to add</label>
    <input id="update_count" name="update_count" type="number" min="0" value="25">
    <small>Use 0 for continuous batches until no more tracks found. Browser keeps sending safe chunks.</small>
    <input id="batch_size" name="batch_size" type="hidden" value="100">
    <input id="manual_page" name="manual_page" type="hidden" value="1">
    <small>If playlist does not exist, app creates it as private.</small>
    <br>
    <button type="submit">Run update</button>
  </form>
  <div id="server-result">{result_html}</div>
  <pre id="progress"></pre>
  <script>
    const form = document.querySelector("form");
    const button = document.querySelector("button");
    const progress = document.querySelector("#progress");
    const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
    const params = new URLSearchParams(window.location.search);
    const tokenFromUrl = params.get("token");
    if (tokenFromUrl) localStorage.setItem("spotify_update_token", tokenFromUrl);

    function getToken(forcePrompt = false) {{
      const input = form.querySelector("[name=token]");
      let token = "";
      if (!forcePrompt) {{
        token = input?.value || localStorage.getItem("spotify_update_token") || "";
      }}
      if (!token) token = window.prompt("Enter secret token") || "";
      if (token) localStorage.setItem("spotify_update_token", token);
      if (input) input.value = token;
      return token;
    }}

    async function submitBatch(data) {{
      const response = await fetch("/api/update", {{ method: "POST", body: data }});
      const text = await response.text();
      const jsonText = text.match(/<pre>([\\s\\S]*?)<\\/pre>/)?.[1]
        ?.replace(/&quot;/g, '"')
        ?.replace(/&amp;/g, '&')
        ?.replace(/&lt;/g, '<')
        ?.replace(/&gt;/g, '>');
      return JSON.parse(jsonText || text);
    }}

    form.addEventListener("submit", async (event) => {{
      event.preventDefault();
      button.disabled = true;
      progress.textContent = "";

      const original = new FormData(form);
      let token = getToken();
      if (!token) {{
        progress.textContent = "Missing secret token.\\n";
        button.disabled = false;
        return;
      }}
      const requested = Number(original.get("update_count") || "0");
      let remaining = requested;
      let totalAdded = 0;
      let batch = 0;

      while (requested === 0 || remaining > 0) {{
        const data = new FormData(form);
        const chunk = requested === 0 ? 100 : Math.min(100, remaining);
        data.set("update_count", String(chunk));
        data.set("batch_size", "100");
        data.set("token", token);
        batch += 1;

        progress.textContent += `Batch ${{batch}}: requesting ${{chunk}} tracks...\\n`;
        let result = await submitBatch(data);
        if (result.error === "Unauthorized") {{
          localStorage.removeItem("spotify_update_token");
          progress.textContent += "Token rejected. Enter correct token to retry this batch.\\n";
          token = getToken(true);
          if (!token) break;
          data.set("token", token);
          result = await submitBatch(data);
        }}

        progress.textContent += JSON.stringify(result, null, 2) + "\\n\\n";
        if (result.error === "Unauthorized") {{
          localStorage.removeItem("spotify_update_token");
          progress.textContent += "Token rejected again. Open page with correct ?token=... value.\\n";
        }}
        if (!result.ok) break;

        const added = Number(result.added_count || 0);
        totalAdded += added;
        if (requested !== 0) remaining -= added;
        if (added === 0) break;
        if (requested !== 0 && remaining <= 0) break;

        await sleep(1500);
      }}

      progress.textContent += `Done. Total added: ${{totalAdded}}\\n`;
      button.disabled = false;
    }});
  </script>
</body>
</html>"""
    return status, body.encode("utf-8"), "text/html; charset=utf-8"


class handler(BaseHTTPRequestHandler):
    def is_authorized(self, params: dict) -> bool:
        secret = os.getenv("CRON_SECRET")
        if secret:
            expected = f"Bearer {secret}"
            query_token = params.get("token", [""])[0]
            return self.headers.get("Authorization") == expected or query_token == secret
        return True

    def send_body(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def run_update(self, params: dict) -> tuple[int, dict]:
        if not self.is_authorized(params):
            return 401, {"ok": False, "error": "Unauthorized"}

        output_dir = Path(os.getenv("SPOTIFY_OUTPUT_DIR", "/tmp/spotify_batch_output"))
        output_dir.mkdir(parents=True, exist_ok=True)

        learned_queries = ROOT / "spotify_batch_output" / "liked_style_queries.json"
        if learned_queries.exists():
            shutil.copy2(learned_queries, output_dir / "liked_style_queries.json")

        try:
            sp = build_spotify_client()
            playlist_id = os.getenv("SPOTIFY_PLAYLIST_ID", DEFAULT_PLAYLIST_ID)
            playlist_id_from_form = (params.get("playlist_id", [""])[0] or "").strip()
            playlist_name = (
                (params.get("new_playlist_name", [""])[0] or "").strip()
                or (params.get("playlist_name", [""])[0] or "").strip()
            )
            playlist_created = False
            resolved_playlist_name = ""
            if playlist_id_from_form:
                playlist_id = playlist_id_from_form
                playlist_meta = spotify_get(sp, f"playlists/{playlist_id}", {"fields": "name"})
                resolved_playlist_name = playlist_meta.get("name", "(selected)")
            elif playlist_name:
                playlist = get_or_create_playlist_by_name(
                    sp=sp,
                    name=playlist_name,
                    public=False,
                    description="Generated by spotify_batch_adder.py",
                )
                playlist_id = playlist["id"]
                playlist_created = playlist["created"]
                resolved_playlist_name = playlist["name"]

            requested_count = int(params.get("update_count", [os.getenv("SPOTIFY_UPDATE_COUNT", "25")])[0])
            batch_size = int(params.get("batch_size", ["100"])[0])
            batch_size = max(1, min(batch_size, 100))
            update_count = max(1, min(requested_count, batch_size))
            result = run_hourly_update(
                sp=sp,
                playlist_id=playlist_id,
                market=os.getenv("SPOTIFY_MARKET", "US"),
                output_dir=output_dir,
                update_count=update_count,
                request_delay=float(os.getenv("SPOTIFY_REQUEST_DELAY", "1.0")),
                max_query_variants=int(os.getenv("SPOTIFY_MAX_QUERY_VARIANTS", "1")),
                search_without_market=env_bool("SPOTIFY_SEARCH_WITHOUT_MARKET", False),
                skip_existing_check=env_bool("SPOTIFY_SKIP_EXISTING_CHECK", False),
                debug_search=env_bool("SPOTIFY_DEBUG_SEARCH", False),
                stateless_rotation=env_bool("SPOTIFY_STATELESS_ROTATION", True),
                fail_on_existing_check_error=True,
            )
            payload = {
                "ok": True,
                "playlist_name": resolved_playlist_name or playlist_name or "(default)",
                "playlist_created": playlist_created,
                "requested_count": requested_count,
                "processed_count": update_count,
                "remaining_count": max(0, requested_count - result.get("added_count", 0)) if requested_count > 0 else None,
                **result,
            }
            return 200, payload
        except Exception as exc:
            return 500, {"ok": False, "error": str(exc)}

    def do_GET(self):
        params = parse_qs(urlparse(self.path).query)
        wants_run = (
            params.get("run", [""])[0] == "1"
            or bool(self.headers.get("Authorization"))
            or "playlist_id" in params
            or "playlist_name" in params
            or "new_playlist_name" in params
        )
        if not wants_run:
            token = params.get("token", [""])[0]
            playlists = None
            message = ""
            if token:
                if self.is_authorized(params):
                    try:
                        playlists = list_current_user_playlists(build_spotify_client())
                    except Exception as exc:
                        message = f"Could not load playlists: {exc}"
                else:
                    message = "Bad token."
            status, body, content_type = html_page(message=message, token=token, playlists=playlists)
            self.send_body(status, body, content_type)
            return

        status, payload = self.run_update(params)
        body = json.dumps(payload).encode("utf-8")
        self.send_body(status, body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        params = parse_qs(self.rfile.read(length).decode("utf-8")) if length else {}
        status, payload = self.run_update(params)
        page_status, body, content_type = html_page(result=payload, status=status)
        self.send_body(page_status, body, content_type)
