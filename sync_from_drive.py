"""
sync_from_drive.py
──────────────────
Downloads new receipt files from Google Drive to the local Grocery bills folder,
then re-seeds the data CSVs.

SETUP (one-time):
  1. Go to https://console.cloud.google.com/
  2. Create a project → Enable "Google Drive API"
  3. Credentials → Create OAuth 2.0 Client ID (Desktop app)
  4. Download the JSON → save as credentials.json next to this file
  5. Run:  python sync_from_drive.py --setup
     (Opens browser once to authorize — creates token.json for future runs)
  6. Share your Google Drive receipt folders with the authorized account.
     Set GDRIVE_HIT_FOLDER_ID, GDRIVE_LIDL_FOLDER_ID, GDRIVE_RESTAURANT_FOLDER_ID below.

WEEKLY USE:
  python sync_from_drive.py          # sync + seed
  python sync_from_drive.py --sync-only   # just download, don't seed
"""

import os, io, argparse
from pathlib import Path

BASE_DIR  = Path(__file__).parent
CREDS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
LOG_FILE   = BASE_DIR / "data" / "update_log.txt"

# ── Configure your Google Drive folder IDs ────────────────────────────────────
# Get these from the URL when you open the folder in Google Drive:
#   https://drive.google.com/drive/folders/FOLDER_ID_HERE
GDRIVE_HIT_FOLDER_ID        = "1debrgin6k4yr0_nil3NcRyjrx2BqzLlR"
GDRIVE_LIDL_FOLDER_ID       = "1QFaAZ5Ml5INAhSpfbbw1prJuxpi0QdZv"
GDRIVE_RESTAURANT_FOLDER_ID = "1luZIK0Hsb9cCwirOGJAWL5PY7MyK5nLJ"

LOCAL_HIT_DIR        = BASE_DIR / "Grocery bills" / "Hit Bills"
LOCAL_LIDL_DIR       = BASE_DIR / "Grocery bills" / "Lidl bills"
LOCAL_RESTAURANT_DIR = BASE_DIR / "Grocery bills" / "Restaurant bills"

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# ── Auth ──────────────────────────────────────────────────────────────────────
def get_drive_service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CREDS_FILE.exists():
                print(f"ERROR: credentials.json not found at {CREDS_FILE}")
                print("Download it from Google Cloud Console → Credentials → OAuth 2.0 Client IDs")
                raise SystemExit(1)
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        TOKEN_FILE.write_text(creds.to_json())
        print("Authorization successful — token.json saved.")

    return build("drive", "v3", credentials=creds)


# ── Download helpers ──────────────────────────────────────────────────────────
def list_drive_files(service, folder_id: str) -> list[dict]:
    """Return all files in a Drive folder."""
    results = []
    page_token = None
    while True:
        resp = service.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
            pageToken=page_token,
        ).execute()
        results.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return results


def download_file(service, file_id: str, dest_path: Path):
    from googleapiclient.http import MediaIoBaseDownload
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    dest_path.write_bytes(buf.getvalue())


def sync_folder(service, folder_id: str, local_dir: Path, label: str) -> int:
    """Download files that don't exist locally yet. Returns count of new files."""
    if not folder_id:
        print(f"  SKIP {label}: folder ID not configured in sync_from_drive.py")
        return 0

    local_dir.mkdir(parents=True, exist_ok=True)
    existing = {f.name for f in local_dir.iterdir()}
    drive_files = list_drive_files(service, folder_id)

    new_count = 0
    for f in drive_files:
        safe_name = f["name"].replace(":", "_")
        if safe_name in existing or f["name"] in existing:
            continue  # Already downloaded — skip (no duplicates)
        dest = local_dir / safe_name
        print(f"  Downloading: {f['name']} -> {safe_name}")
        download_file(service, f["id"], dest)
        new_count += 1

    print(f"  {label}: {new_count} new file(s) downloaded ({len(drive_files)} total on Drive)")
    return new_count


# ── Main ──────────────────────────────────────────────────────────────────────
def run(sync_only=False):
    import subprocess, sys
    from datetime import datetime

    LOG_FILE.parent.mkdir(exist_ok=True)

    print("=== Syncing from Google Drive ===")
    service   = get_drive_service()
    hit_new        = sync_folder(service, GDRIVE_HIT_FOLDER_ID,        LOCAL_HIT_DIR,        "HIT Bills")
    lidl_new       = sync_folder(service, GDRIVE_LIDL_FOLDER_ID,       LOCAL_LIDL_DIR,       "Lidl Bills")
    restaurant_new = sync_folder(service, GDRIVE_RESTAURANT_FOLDER_ID, LOCAL_RESTAURANT_DIR, "Restaurant Bills")
    total_new = hit_new + lidl_new + restaurant_new

    msg = f"{datetime.now():%Y-%m-%d %H:%M} — Sync: {hit_new} HIT + {lidl_new} Lidl + {restaurant_new} Restaurant new files"
    print(msg)

    if not sync_only:
        if total_new > 0:
            print("\n=== Re-seeding data (new files found) ===")
            subprocess.run([sys.executable, "-X", "utf8",
                            str(BASE_DIR / "seed_data.py")], check=True)
            _git_push_data(msg)
        else:
            print("No new files — skipping seed.")

    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def _git_push_data(commit_msg: str):
    """Commit updated CSVs to GitHub so the cloud dashboard stays fresh."""
    import subprocess
    git = r"C:\Program Files\Git\cmd\git.exe"
    cwd = str(BASE_DIR)
    try:
        subprocess.run([git, "add", "data/receipts.csv", "data/items.csv"], cwd=cwd, check=True)
        result = subprocess.run([git, "diff", "--cached", "--quiet"], cwd=cwd)
        if result.returncode == 0:
            print("Git: no CSV changes to push.")
            return
        subprocess.run([git, "commit", "-m", f"data: {commit_msg}"], cwd=cwd, check=True)
        subprocess.run([git, "push"], cwd=cwd, check=True)
        print("Git: CSVs pushed to GitHub ✓")
    except Exception as e:
        print(f"Git push failed (dashboard may lag): {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--setup",     action="store_true",
                        help="Authorize Google Drive (run once)")
    parser.add_argument("--sync-only", action="store_true",
                        help="Download files but don't re-seed CSVs")
    args = parser.parse_args()

    if args.setup:
        print("Opening browser for Google authorization...")
        get_drive_service()
        print("Done! Run without --setup for weekly syncs.")
    else:
        run(sync_only=args.sync_only)
