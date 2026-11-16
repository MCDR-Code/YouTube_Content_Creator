"""Friday: upload approved videos. Plain code, no agent.

Fixed rules, enforced here no matter what any setting or agent says:
  1. The approval record is re-read from the database right before each upload (approval.require_approved).
  2. privacyStatus is always "private". There is no parameter to change it.
  3. The AI-disclosure field (containsSyntheticMedia) and made-for-kids field are always sent.
The professor makes a video public himself in YouTube Studio.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ycc import approval
from ycc.config import PROJECT_ROOT, Settings
from ycc.storage import OUTPUT, save_json

PRIVACY = "private"  # never changes
CATEGORY_EDUCATION = "27"


def build_body(v: dict) -> dict:
    variant = v["variants"][v["chosen_variant"]] if v.get("variants") and v.get("chosen_variant") is not None else {}
    return {
        "snippet": {"title": v["title"] or variant.get("title", ""), "description": v["description"],
                    "tags": v["tags"][:15], "categoryId": CATEGORY_EDUCATION},
        "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": bool(v["made_for_kids"]),
                   "containsSyntheticMedia": bool(v["ai_disclosure"])},
    }


class MockYouTube:
    """Writes what would be uploaded to output/mock_youtube/. Same body as the real API call."""

    def __init__(self, root: Path | None = None):
        self.root = root or OUTPUT / "mock_youtube"

    def insert(self, body: dict, media_path: str, thumbnail: str | None) -> str:
        assert body["status"]["privacyStatus"] == "private"
        vid = "mock_" + hashlib.sha1(f"{media_path}|{body['snippet']['title']}".encode()).hexdigest()[:11]
        save_json(self.root / f"{vid}.json", {"youtube_id": vid, "body": body, "media": media_path,
                                               "thumbnail": thumbnail})
        return vid


class RealYouTube:
    """YouTube Data API v3 upload (Prompt 14). Needs client_secret.json from Google Cloud.

    The sign-in token is saved in tokens/youtube_token.json (git-ignored). Uploads from an
    unverified Google Cloud project are locked to private by YouTube anyway.
    """
    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    def __init__(self):
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        token = PROJECT_ROOT / "tokens" / "youtube_token.json"
        secret = PROJECT_ROOT / "client_secret.json"
        creds = Credentials.from_authorized_user_file(str(token), self.SCOPES) if token.exists() else None
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not secret.exists():
                    raise FileNotFoundError("client_secret.json is missing. See docs/real_mode.md.")
                creds = InstalledAppFlow.from_client_secrets_file(str(secret), self.SCOPES).run_local_server(port=0)
            token.parent.mkdir(exist_ok=True)
            token.write_text(creds.to_json(), encoding="utf-8")
        self.api = build("youtube", "v3", credentials=creds)

    def insert(self, body: dict, media_path: str, thumbnail: str | None) -> str:
        from googleapiclient.http import MediaFileUpload
        assert body["status"]["privacyStatus"] == "private"
        req = self.api.videos().insert(part="snippet,status", body=body,
                                       media_body=MediaFileUpload(media_path, chunksize=-1, resumable=True))
        resp = None
        while resp is None:
            _, resp = req.next_chunk()
        return resp["id"]


def client(settings: Settings):
    return RealYouTube() if settings.youtube_mode == "real" else MockYouTube()


def upload(video_id: str, yt, db: Path | None = None) -> str:
    v = approval.require_approved(video_id, db)  # the gate
    body = build_body(v)
    if body["status"]["privacyStatus"] != "private":
        raise approval.NotApproved("Refusing: privacy must be private.")
    thumb = v["thumbnails"][v["chosen_variant"]] if v["thumbnails"] and v["chosen_variant"] is not None else None
    yt_id = yt.insert(body, str(PROJECT_ROOT / v["path"]), thumb)
    approval.mark_uploaded(video_id, yt_id, body["status"]["privacyStatus"], db)
    return yt_id


def upload_approved(week: int, yt, db: Path | None = None) -> list[dict]:
    """Upload every approved video of the week. Pending and rejected videos are skipped and reported."""
    results = []
    for v in approval.list_week(week, db):
        if v["status"] == "approved":
            results.append({"id": v["id"], "youtube_id": upload(v["id"], yt, db), "privacy": PRIVACY})
        else:
            results.append({"id": v["id"], "skipped": v["status"]})
    return results


if __name__ == "__main__":
    print(json.dumps(build_body({"title": "t", "description": "d", "tags": [], "variants": [],
                                 "chosen_variant": None, "made_for_kids": 0, "ai_disclosure": 1}), indent=2))
