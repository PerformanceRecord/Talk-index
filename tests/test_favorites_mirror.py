from __future__ import annotations

import unittest
from datetime import UTC, datetime

from crawler.services.favorites import build_aggregates
from crawler.services.favorites_mirror import (
    FAVORITES_DAILY_SNAPSHOT_LATEST_KEY,
    build_daily_snapshot_upsert_key,
    build_sheet_rows_from_payload,
    compute_previous_week_key_jst,
    load_daily_snapshot_payloads,
)


class FavoritesMirrorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.talks_payload = {
            "talks": [
                {
                    "key": "heading-1",
                    "name": "heading-1",
                    "subsections": [
                        {"videoTitle": "元動画タイトルA"},
                        {"videoTitle": "元動画タイトルA"},
                    ],
                }
            ]
        }

    def test_build_sheet_rows_from_payload_resolves_source_video_title(self) -> None:
        payload = {
            "generatedAt": "2026-04-21T00:00:00Z",
            "items": [
                {
                    "headingId": "heading-1",
                    "headingTitle": "見出しA",
                    "videoId": "video-a",
                    "voteCount": 10,
                    "firstVotedAt": "2026-04-10T00:00:00Z",
                    "lastVotedAt": "2026-04-20T00:00:00Z",
                }
            ],
        }

        rows = build_sheet_rows_from_payload(
            payload,
            aggregate_type="current_ranking",
            source_json_url="https://example.com/current_ranking.json",
            talks_payload=self.talks_payload,
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sourceVideoTitle"], "元動画タイトルA")
        self.assertEqual(rows[0]["aggregateType"], "current_ranking")
        self.assertEqual(rows[0]["rank"], "1")

    def test_build_daily_snapshot_upsert_key_uses_snapshot_date_and_heading_id(self) -> None:
        row = {"snapshotDate": "2026-04-20", "headingId": "heading-9", "rank": "3"}
        self.assertEqual(build_daily_snapshot_upsert_key(row), ("2026-04-20", "heading-9"))

    def test_recent_recommendations_uses_previous_week_in_jst(self) -> None:
        votes = [
            {
                "headingId": "heading-1",
                "clientHash": "user-1",
                "videoId": "video-a",
                "headingTitle": "見出しA",
                "videoTitle": "元動画A",
                "firstVotedAt": "2026-04-13T03:00:00Z",
            },
            {
                "headingId": "heading-1",
                "clientHash": "user-2",
                "videoId": "video-a",
                "headingTitle": "見出しA",
                "videoTitle": "元動画A",
                "firstVotedAt": "2026-04-14T01:00:00Z",
            },
        ]
        now_utc = datetime(2026, 4, 21, 0, 0, tzinfo=UTC)

        aggregates = build_aggregates(votes, now_utc=now_utc)

        self.assertEqual(aggregates["recent_recommendations"]["weekKey"], "2026-04-13")
        self.assertEqual(compute_previous_week_key_jst(now_utc), "2026-04-13")
        self.assertEqual(len(aggregates["recent_recommendations"]["items"]), 1)

    def test_load_daily_snapshot_payloads_falls_back_to_latest_with_logging(self) -> None:
        messages: list[str] = []
        payload = {
            "generatedAt": "2026-04-21T00:00:00Z",
            "snapshotDate": "2026-04-21",
            "items": [],
        }

        result = load_daily_snapshot_payloads(
            list_keys=lambda: [],
            fetcher=lambda key: payload if key == FAVORITES_DAILY_SNAPSHOT_LATEST_KEY else {},
            logger=messages.append,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], FAVORITES_DAILY_SNAPSHOT_LATEST_KEY)
        self.assertTrue(any("fallback" in message for message in messages))

    def test_load_daily_snapshot_payloads_logs_missing_dated_file_and_continues(self) -> None:
        messages: list[str] = []
        payloads = {
            "favorites/exports/daily_snapshot/2026-04-19.json": {
                "generatedAt": "2026-04-19T00:00:00Z",
                "snapshotDate": "2026-04-19",
                "items": [],
            }
        }

        def fetcher(key: str):
            if key not in payloads:
                raise FileNotFoundError(key)
            return payloads[key]

        result = load_daily_snapshot_payloads(
            list_keys=lambda: [
                "favorites/exports/daily_snapshot/2026-04-18.json",
                "favorites/exports/daily_snapshot/2026-04-19.json",
            ],
            fetcher=fetcher,
            logger=messages.append,
        )

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "favorites/exports/daily_snapshot/2026-04-19.json")
        self.assertTrue(any("2026-04-18.json" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
