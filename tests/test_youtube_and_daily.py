import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from googleapiclient.errors import HttpError
from httplib2 import Response

from crawler.jobs.daily_crawl import _select_recheck_ids
from crawler.models import VideoItem
from crawler.services.youtube import (
    YouTubeQuotaExceededError,
    _execute_request,
    fetch_channel_videos,
    fetch_timestamp_sources,
)


class _Exec:
    def __init__(self, payload=None, error=None):
        self.payload = payload
        self.error = error
        self.execute_kwargs = []

    def execute(self, **kwargs):
        self.execute_kwargs.append(kwargs)
        if self.error:
            raise self.error
        return self.payload


class _CommentThreadsAPI:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def list(self, **kwargs):
        token = kwargs.get("pageToken")
        self.calls.append(kwargs)
        payload = self.pages.get(token, {"items": []})
        if isinstance(payload, Exception):
            return _Exec(error=payload)
        return _Exec(payload)


class _RepliesAPI:
    def __init__(self, pages_by_parent):
        self.pages_by_parent = pages_by_parent
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        parent = kwargs.get("parentId")
        token = kwargs.get("pageToken")
        payload = self.pages_by_parent.get(parent, {}).get(token, {"items": []})
        return _Exec(payload)


class _YoutubeMock:
    def __init__(self, pages, reply_pages=None):
        self._threads = _CommentThreadsAPI(pages)
        self._replies = _RepliesAPI(reply_pages or {})

    def commentThreads(self):
        return self._threads

    def comments(self):
        return self._replies


class _ListAPI:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        payload = self.payloads.pop(0) if self.payloads else {"items": []}
        return _Exec(payload)


class _DiscoveryYoutubeMock:
    def __init__(self, playlist_payloads, video_payloads):
        self._channels = _ListAPI([{"items": [{"contentDetails": {"relatedPlaylists": {"uploads": "UU-test"}}}]}])
        self._playlist = _ListAPI(playlist_payloads)
        self._videos = _ListAPI(video_payloads)

    def channels(self):
        return self._channels

    def playlistItems(self):
        return self._playlist

    def videos(self):
        return self._videos


class YoutubeAndDailyTests(unittest.TestCase):
    def test_select_recheck_prioritizes_missing_timestamp_archives(self):
        ordered = ["old-complete", "old-missing", "recent"]
        now = datetime.now(timezone.utc)
        videos_by_id = {
            "old-complete": VideoItem("old-complete", "old", "", "2020-01-01T00:00:00Z", ""),
            "old-missing": VideoItem("old-missing", "missing", "", "2020-01-02T00:00:00Z", ""),
            "recent": VideoItem("recent", "recent", "", now.isoformat(), ""),
        }

        selected, _ = _select_recheck_ids(
            ordered_video_ids=ordered,
            current_cursor=0,
            limit=2,
            recent_hours=72,
            videos_by_id=videos_by_id,
            priority_video_ids={"old-missing"},
        )

        self.assertEqual(selected, ["old-missing", "recent"])

    def test_reply_budget_prioritizes_threads_with_timestamp_evidence(self):
        def thread(comment_id, embedded_reply=None):
            item = {
                "id": f"thread-{comment_id}",
                "snippet": {
                    "topLevelComment": {
                        "id": comment_id,
                        "snippet": {"textOriginal": "通常コメント"},
                    },
                    "totalReplyCount": 2,
                },
            }
            if embedded_reply:
                item["replies"] = {"comments": [embedded_reply]}
            return item

        target_embedded = {"id": "embedded", "snippet": {"textOriginal": "0:00 開始"}}
        pages = {None: {"items": [thread("decoy"), thread("target", target_embedded)]}}
        reply_pages = {
            "decoy": {None: {"items": [{"id": "waste", "snippet": {"textOriginal": "雑談"}}]}},
            "target": {None: {"items": [{"id": "timeline", "snippet": {"textOriginal": "10:00 本編"}}]}},
        }
        youtube = _YoutubeMock(pages, reply_pages=reply_pages)

        with patch.dict(
            "os.environ",
            {"TIMESTAMP_COMMENT_REQUEST_BUDGET": "2", "TIMESTAMP_TOP_COMMENT_MAX_PAGES": "1"},
            clear=False,
        ):
            sources = fetch_timestamp_sources(youtube, "abc123def45")

        self.assertEqual([call["parentId"] for call in youtube._replies.calls], ["target"])
        self.assertIn("timeline", [source.source_id for source in sources])

    def test_old_archive_scans_late_comment_pages(self):
        def thread(comment_id, text):
            return {
                "id": f"thread-{comment_id}",
                "snippet": {
                    "topLevelComment": {
                        "id": comment_id,
                        "snippet": {"textOriginal": text},
                    },
                    "totalReplyCount": 0,
                },
            }

        pages = {
            None: {"items": [thread("c1", "通常コメント")], "nextPageToken": "p2"},
            "p2": {"items": [thread("c2", "通常コメント")], "nextPageToken": "p3"},
            "p3": {"items": [thread("c3", "通常コメント")], "nextPageToken": "p4"},
            "p4": {"items": [thread("c4", "通常コメント")], "nextPageToken": "p5"},
            "p5": {"items": [thread("timeline", "0:00 開始\n10:00 本編")]},
        }
        youtube = _YoutubeMock(pages)

        sources = fetch_timestamp_sources(youtube, "abc123def45")

        self.assertIn("timeline", [source.source_id for source in sources])
        self.assertGreaterEqual(len(youtube._threads.calls), 6)

    def test_fullwidth_description_is_kept_as_timestamp_source(self):
        youtube = _YoutubeMock({None: {"items": []}})

        sources = fetch_timestamp_sources(
            youtube,
            "abc123def45",
            description="０：００ オープニング\n１２：３４ 本編",
        )

        descriptions = [source for source in sources if source.source_type == "description"]
        self.assertEqual(len(descriptions), 1)
        self.assertEqual(descriptions[0].timestamp_count, 2)

    def test_comment_threads_multi_page_with_order_time(self):
        pages = {
            None: {
                "items": [
                    {
                        "id": "t1",
                        "snippet": {
                            "topLevelComment": {
                                "id": "c1",
                                "snippet": {
                                    "textOriginal": "00:10:00 foo",
                                    "likeCount": 1,
                                    "publishedAt": "2026-01-01T00:00:00Z",
                                },
                            },
                            "totalReplyCount": 0,
                        },
                    }
                ],
                "nextPageToken": "p2",
            },
            "p2": {
                "items": [
                    {
                        "id": "t2",
                        "snippet": {
                            "topLevelComment": {
                                "id": "c2",
                                "snippet": {
                                    "textOriginal": "00:20:00 bar",
                                    "likeCount": 1,
                                    "publishedAt": "2026-01-01T00:01:00Z",
                                },
                            },
                            "totalReplyCount": 0,
                        },
                    }
                ]
            },
        }
        youtube = _YoutubeMock(pages)

        sources = fetch_timestamp_sources(youtube, "abc123def45", description="")

        tops = [s for s in sources if s.source_type == "top"]
        self.assertEqual(len(tops), 2)
        self.assertEqual(len(youtube._threads.calls), 3)
        self.assertEqual(
            [call["order"] for call in youtube._threads.calls],
            ["relevance", "time", "time"],
        )

    def test_reply_fetch_has_page_cap(self):
        pages = {
            None: {
                "items": [
                    {
                        "id": "t1",
                        "snippet": {
                            "topLevelComment": {
                                "id": "c1",
                                "snippet": {
                                    "textOriginal": "00:00:10 top",
                                    "publishedAt": "2026-01-01T00:00:00Z",
                                },
                            },
                            "totalReplyCount": 5,
                        },
                    }
                ]
            }
        }
        reply_pages = {
            "c1": {
                None: {"items": [{"id": "r1", "snippet": {"textOriginal": "00:00:20 r1", "publishedAt": "2026-01-01T00:00:01Z"}}], "nextPageToken": "p2"},
                "p2": {"items": [{"id": "r2", "snippet": {"textOriginal": "00:00:30 r2", "publishedAt": "2026-01-01T00:00:02Z"}}], "nextPageToken": "p3"},
                "p3": {"items": [{"id": "r3", "snippet": {"textOriginal": "00:00:40 r3", "publishedAt": "2026-01-01T00:00:03Z"}}], "nextPageToken": "p4"},
                "p4": {"items": [{"id": "r4", "snippet": {"textOriginal": "00:00:50 r4", "publishedAt": "2026-01-01T00:00:04Z"}}]},
            }
        }
        youtube = _YoutubeMock(pages, reply_pages=reply_pages)

        sources = fetch_timestamp_sources(youtube, "abc123def45", description="")
        replies = [s for s in sources if s.source_type == "reply"]

        self.assertEqual(len(replies), 3)
        self.assertEqual(len(youtube._replies.calls), 3)

    def test_comment_request_budget_caps_reply_pages(self):
        pages = {
            None: {
                "items": [
                    {
                        "id": "t1",
                        "snippet": {
                            "topLevelComment": {
                                "id": "c1",
                                "snippet": {"textOriginal": "0:10 top"},
                            },
                            "totalReplyCount": 10,
                        },
                    }
                ]
            }
        }
        reply_pages = {
            "c1": {
                None: {"items": [{"id": "r1", "snippet": {"textOriginal": "0:20 reply"}}], "nextPageToken": "p2"},
                "p2": {"items": [{"id": "r2", "snippet": {"textOriginal": "0:30 reply"}}]},
            }
        }
        youtube = _YoutubeMock(pages, reply_pages=reply_pages)

        with patch.dict(
            "os.environ",
            {"TIMESTAMP_COMMENT_REQUEST_BUDGET": "2", "TIMESTAMP_TOP_COMMENT_MAX_PAGES": "1"},
            clear=False,
        ):
            sources = fetch_timestamp_sources(youtube, "abc123def45")

        self.assertEqual(len(youtube._threads.calls), 1)
        self.assertEqual(len(youtube._replies.calls), 1)
        self.assertEqual([source.source_id for source in sources], ["c1", "r1"])

    def test_comments_disabled_keeps_description_source(self):
        error = HttpError(
            Response({"status": "403", "reason": "Forbidden"}),
            b'{"error":{"errors":[{"reason":"commentsDisabled"}]}}',
        )
        youtube = _YoutubeMock({None: error})

        sources = fetch_timestamp_sources(
            youtube,
            "abc123def45",
            description="0:00 opening\n1:20 topic",
        )

        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0].source_type, "description")

    def test_quota_error_is_not_hidden(self):
        error = HttpError(
            Response({"status": "403", "reason": "Forbidden"}),
            b'{"error":{"errors":[{"reason":"quotaExceeded"}]}}',
        )

        with self.assertRaises(YouTubeQuotaExceededError):
            _execute_request(_Exec(error=error), "commentThreads.list")

    def test_upload_playlist_scan_stops_at_page_limit(self):
        playlist_payloads = [
            {"items": [{"contentDetails": {"videoId": "known000001"}}], "nextPageToken": "p2"},
            {"items": [{"contentDetails": {"videoId": "known000002"}}], "nextPageToken": "p3"},
            {"items": [{"contentDetails": {"videoId": "new00000003"}}]},
        ]
        video_payloads = [
            {"items": [{"id": "known000001", "snippet": {}, "liveStreamingDetails": {}}]},
            {"items": [{"id": "known000002", "snippet": {}, "liveStreamingDetails": {}}]},
        ]
        youtube = _DiscoveryYoutubeMock(playlist_payloads, video_payloads)

        videos = fetch_channel_videos(
            youtube,
            "UC-test",
            max_results=1,
            exclude_video_ids={"known000001", "known000002"},
            max_pages=2,
        )

        self.assertEqual(videos, [])
        self.assertEqual(len(youtube._playlist.calls), 2)

    def test_pinned_flag_missing_does_not_crash(self):
        pages = {
            None: {
                "items": [
                    {
                        "id": "t1",
                        "snippet": {
                            "topLevelComment": {
                                "id": "c1",
                                "snippet": {
                                    "textOriginal": "00:10:00 foo",
                                    "publishedAt": "2026-01-01T00:00:00Z",
                                },
                            },
                            "totalReplyCount": 0,
                        },
                    }
                ]
            }
        }
        youtube = _YoutubeMock(pages)

        sources = fetch_timestamp_sources(youtube, "abc123def45", description="")
        self.assertEqual(len(sources), 1)
        self.assertIsNone(sources[0].is_pinned)

    def test_select_recheck_recent_first_and_cursor_fill(self):
        now = datetime.now(timezone.utc)
        ordered = ["old1", "old2", "new1", "new2"]

        def make_video(vid: str, hours_ago: int) -> VideoItem:
            return VideoItem(
                video_id=vid,
                title=vid,
                url=f"https://www.youtube.com/watch?v={vid}",
                published_at=(now - timedelta(hours=hours_ago)).isoformat().replace("+00:00", "Z"),
                thumbnail_url="",
            )

        videos_by_id = {
            "old1": make_video("old1", 200),
            "old2": make_video("old2", 150),
            "new1": make_video("new1", 10),
            "new2": make_video("new2", 5),
        }

        selected, next_cursor = _select_recheck_ids(
            ordered_video_ids=ordered,
            current_cursor=0,
            limit=3,
            recent_hours=72,
            videos_by_id=videos_by_id,
        )

        self.assertEqual(selected[:2], ["new2", "new1"])
        self.assertEqual(len(selected), 3)
        self.assertEqual(next_cursor, 1)

    def test_select_recheck_fills_past_recent_cursor_overlap(self):
        now = datetime.now(timezone.utc)
        ordered = ["new1", "new2", "old1"]
        videos_by_id = {
            "new1": VideoItem("new1", "new1", "", now.isoformat(), ""),
            "new2": VideoItem("new2", "new2", "", now.isoformat(), ""),
            "old1": VideoItem(
                "old1",
                "old1",
                "",
                (now - timedelta(hours=200)).isoformat(),
                "",
            ),
        }

        selected, next_cursor = _select_recheck_ids(
            ordered_video_ids=ordered,
            current_cursor=0,
            limit=3,
            recent_hours=72,
            videos_by_id=videos_by_id,
        )

        self.assertEqual(selected[:2], ["new1", "new2"])
        self.assertEqual(selected[2], "old1")
        self.assertEqual(next_cursor, 0)

    def test_select_recheck_excludes_videos_fetched_in_same_run(self):
        now = datetime.now(timezone.utc)
        ordered = ["new1", "old1", "old2"]
        videos_by_id = {
            video_id: VideoItem(video_id, video_id, "", now.isoformat(), "")
            for video_id in ordered
        }

        selected, _ = _select_recheck_ids(
            ordered_video_ids=ordered,
            current_cursor=0,
            limit=2,
            recent_hours=72,
            videos_by_id=videos_by_id,
            exclude_video_ids={"new1"},
        )

        self.assertEqual(selected, ["old1", "old2"])


if __name__ == "__main__":
    unittest.main()
