Spotify batch playlist tool v4

Why this version exists:
Spotify changed Development Mode API behavior in 2026. Search limit is now max 10, artist top tracks is removed, playlist /tracks endpoints were replaced by /items, and some response fields like popularity may be missing. This version avoids the removed endpoints and uses 10-result pagination.

Setup:
1. Create a Spotify Developer app.
2. Add this Redirect URI exactly:
   http://127.0.0.1:8888/callback
3. Add your Spotify user in Users Management.
4. Make sure the app owner has Spotify Premium if your app is in Development Mode.
5. Set environment variables:

Windows PowerShell:
setx SPOTIFY_CLIENT_ID "your_client_id"
setx SPOTIFY_CLIENT_SECRET "your_client_secret"

Then close PowerShell and open it again.

Install:
py -m pip install -r requirements.txt

First test:
Remove-Item .cache* -Force
py .\spotify_batch_adder.py --skip-existing-check --generate-only --debug-search --pages-per-query 1 --request-delay 1.0 --max-query-variants 1

Learn genres/styles from your liked songs:
Remove-Item .cache* -Force
py .\spotify_batch_adder.py --learn-liked-styles --liked-limit 200 --artist-genre-limit 100 --request-delay 1.0

One-time full liked-songs style scan:
Remove-Item .cache* -Force
py .\spotify_batch_adder.py --learn-liked-styles --liked-limit 0 --artist-genre-limit 0 --request-delay 1.0

Create a new private playlist and add to it:
py .\spotify_batch_adder.py --create-playlist "My Spotify Batch Playlist" --skip-existing-check --add-all --pages-per-query 1 --request-delay 1.0 --max-query-variants 1

Hourly update mode:
py .\spotify_batch_adder.py --hourly-update --skip-existing-check --update-count 25 --request-delay 1.0 --max-query-variants 1

Windows Task Scheduler, run once from PowerShell:
schtasks /Create /TN "Spotify Hourly Playlist Update" /SC HOURLY /MO 1 /TR "powershell -NoProfile -ExecutionPolicy Bypass -Command cd 'C:\Users\Sadjad Rgz\Downloads\Compressed\spotify_batches_tool_v4'; py .\spotify_batch_adder.py --hourly-update --skip-existing-check --update-count 25 --request-delay 1.0 --max-query-variants 1" /F

Linux cron, daily at 03:00:
1. Copy this project to a Linux path, for example:
   /home/YOUR_USER/spotify_batches_tool_v4
2. Make sure SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET are available to cron.
3. Edit cron:
   crontab -e
4. Add this line, replacing paths and env values:
   0 3 * * * cd /home/YOUR_USER/spotify_batches_tool_v4 && SPOTIFY_CLIENT_ID="your_client_id" SPOTIFY_CLIENT_SECRET="your_client_secret" /usr/bin/python3 spotify_batch_adder.py --hourly-update --skip-existing-check --update-count 25 --request-delay 1.0 --max-query-variants 1 >> /home/YOUR_USER/spotify_batches_tool_v4/cron.log 2>&1

Vercel deploy, daily at 03:00 UTC:
1. Refresh local Spotify token after the user-library-read scope change:
   Remove-Item .cache* -Force
   py .\spotify_batch_adder.py --learn-liked-styles --liked-limit 0 --artist-genre-limit 0 --request-delay 1.0
2. Install and login:
   npm i -g vercel
   vercel login
3. Create/link project from this folder:
   vercel
4. Add production env vars:
   vercel env add SPOTIFY_CLIENT_ID production
   vercel env add SPOTIFY_CLIENT_SECRET production
   vercel env add SPOTIFY_TOKEN_INFO_JSON production
   vercel env add SPOTIFY_CACHE_PATH production
   vercel env add SPOTIFY_PLAYLIST_ID production
   vercel env add CRON_SECRET production
5. Env values:
   SPOTIFY_TOKEN_INFO_JSON = full one-line contents of .cache
   SPOTIFY_CACHE_PATH = /tmp/.cache
   SPOTIFY_PLAYLIST_ID = 6hFjAjRHW88LUKau2rIDHC or your playlist ID
   CRON_SECRET = any long random password
6. Deploy:
   vercel --prod
7. Cron endpoint:
   /api/update
   Schedule lives in vercel.json: 0 3 * * *

Add to the existing hardcoded playlist:
py .\spotify_batch_adder.py --skip-existing-check --add-all --pages-per-query 1 --request-delay 1.0 --max-query-variants 1

If Spotify prints a rate/request limit warning:
- Stop the script.
- Wait for the Retry-After time.
- Rerun with --pages-per-query 1 --request-delay 1.0 --max-query-variants 1.
- Do not use --include-artist-catalog unless you accept many album-track API requests.

If adding gives 403:
- You logged in with the wrong Spotify account.
- The playlist is not owned by/collaborative with that account.
- Your Spotify user is not added to the Developer Dashboard Users Management list.
- Your cached token is old. Run: Remove-Item .cache* -Force

Playlist ID already set for existing-playlist mode:
6hFjAjRHW88LUKau2rIDHC
