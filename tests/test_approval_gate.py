"""Nothing reaches YouTube without the professor's approval, and every upload is private."""
import pytest

from ycc import approval, uploader
from ycc.config import load_settings


def _video(vid="w01_long", kind="long"):
    return {"id": vid, "week": 1, "kind": kind, "path": "output/week_01/long_video.mp4",
            "thumbnails": ["output/week_01/thumbnail_1.png"],
            "variants": [{"title": "Title A", "thumbnail_text": "A"}], "title": "Title A",
            "description": "d", "tags": ["ai"], "ai_disclosure": True, "made_for_kids": False}


class SpyYouTube:
    def __init__(self):
        self.calls = []

    def insert(self, body, media_path, thumbnail):
        self.calls.append(body)
        return "yt123"


def test_upload_without_approval_is_refused(tmp_db):
    approval.register_video(_video(), tmp_db)
    yt = SpyYouTube()
    with pytest.raises(approval.NotApproved):
        uploader.upload("w01_long", yt, tmp_db)
    assert yt.calls == []


def test_rejected_video_is_refused(tmp_db):
    approval.register_video(_video(), tmp_db)
    approval.reject("w01_long", "Professor", "not yet", tmp_db)
    with pytest.raises(approval.NotApproved):
        uploader.upload("w01_long", SpyYouTube(), tmp_db)


def test_approved_video_uploads_private_with_ai_disclosure(tmp_db):
    approval.register_video(_video(), tmp_db)
    approval.approve("w01_long", "Professor", "Final title", "desc", 0, "", tmp_db)
    yt = SpyYouTube()
    assert uploader.upload("w01_long", yt, tmp_db) == "yt123"
    body = yt.calls[0]
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["containsSyntheticMedia"] is True
    assert body["status"]["selfDeclaredMadeForKids"] is False
    assert approval.get("w01_long", tmp_db)["status"] == "uploaded"
    actions = [e["action"] for e in approval.events("w01_long", tmp_db)]
    assert actions == ["registered", "approved", "uploaded"]


def test_withdrawn_approval_blocks_upload(tmp_db):
    approval.register_video(_video(), tmp_db)
    approval.approve("w01_long", "Professor", "t", "d", 0, "", tmp_db)
    approval.withdraw("w01_long", "Professor", tmp_db)
    with pytest.raises(approval.NotApproved):
        uploader.upload("w01_long", SpyYouTube(), tmp_db)


def test_cannot_withdraw_or_reapprove_after_upload(tmp_db):
    approval.register_video(_video(), tmp_db)
    approval.approve("w01_long", "Professor", "t", "d", 0, "", tmp_db)
    uploader.upload("w01_long", SpyYouTube(), tmp_db)
    with pytest.raises(approval.NotApproved):
        approval.withdraw("w01_long", "Professor", tmp_db)
    with pytest.raises(approval.NotApproved):
        approval.approve("w01_long", "Professor", "t", "d", 0, "", tmp_db)


def test_approval_needs_a_name(tmp_db):
    approval.register_video(_video(), tmp_db)
    with pytest.raises(ValueError):
        approval.approve("w01_long", "  ", "t", "d", 0, "", tmp_db)


def test_only_approved_videos_upload_in_a_batch(tmp_db):
    approval.register_video(_video("w01_long"), tmp_db)
    approval.register_video(_video("w01_short1", "short"), tmp_db)
    approval.approve("w01_long", "Professor", "t", "d", 0, "", tmp_db)
    yt = SpyYouTube()
    res = uploader.upload_approved(1, yt, tmp_db)
    assert len(yt.calls) == 1
    assert {"id": "w01_short1", "skipped": "pending"} in res


def test_privacy_cannot_be_set_to_public(tmp_path):
    assert uploader.PRIVACY == "private"
    cfg = (load_settings.__globals__["PROJECT_ROOT"] / "config.yaml").read_text(encoding="utf-8")
    bad = tmp_path / "config.yaml"
    bad.write_text(cfg.replace("privacy_status: private", "privacy_status: public"), encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(bad)


def test_review_page_requires_form_token(tmp_db):
    from ycc.webapp import app
    approval.register_video(_video(), tmp_db)
    c = app.test_client()
    r = c.post("/video/w01_long/decide", data={"action": "approve", "approver": "Someone", "title": "t",
                                              "description": "d", "variant": "0"})
    assert r.status_code == 403
    assert approval.get("w01_long", tmp_db)["status"] == "pending"
    r = c.post("/video/w01_long/decide", data={"action": "approve", "approver": "Professor", "title": "t",
                                              "description": "d", "variant": "0",
                                              "token": app.config["FORM_TOKEN"]})
    assert r.status_code == 302
    assert approval.get("w01_long", tmp_db)["approved_by"] == "Professor"
