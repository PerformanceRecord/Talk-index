from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable
from urllib.parse import parse_qs, urlparse

import gspread

from crawler.models import VideoItem


class SpreadsheetServiceError(RuntimeError):
    pass


TIMESTAMP_WITH_LABEL_PATTERN = re.compile(
    r"(?P<ts>(?:\d{1,2}:)?\d{1,2}:\d{2})\s*(?P<label>[^\n\r]*)"
)


def build_gspread_client(service_account_json: str) -> gspread.Client:
    if not service_account_json.strip():
        raise SpreadsheetServiceError("GOOGLE_SERVICE_ACCOUNT_JSON が未設定です。")

    try:
        account_info = json.loads(service_account_json)
    except json.JSONDecodeError as exc:
        raise SpreadsheetServiceError("GOOGLE_SERVICE_ACCOUNT_JSON のJSON形式が不正です。") from exc

    return gspread.service_account_from_dict(account_info)


def extract_video_id_from_url(url: str) -> str:
    value = (url or "").strip()
    if not value:
        return ""

    if "youtu.be/" in value:
        path = urlparse(value).path.strip("/")
        return path.split("/")[0] if path else ""

    parsed = urlparse(value)
    query_video_id = parse_qs(parsed.query).get("v", [""])[0]
    if query_video_id:
        return query_video_id

    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) >= 2 and path_parts[0] in {"shorts", "live"}:
        return path_parts[1]

    return ""


def _get_or_create_sheet(book: gspread.Spreadsheet, worksheet_name: str) -> gspread.Worksheet:
    try:
        return book.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        return book.add_worksheet(title=worksheet_name, rows=1000, cols=12)


def read_video_ids_from_url_column(
    client: gspread.Client,
    spreadsheet_id: str,
    worksheet_name: str,
    start_row: int = 2,
    column_index: int = 1,
) -> set[str]:
    if not spreadsheet_id.strip():
        raise SpreadsheetServiceError("SPREADSHEET_ID が未設定です。")

    book = client.open_by_key(spreadsheet_id)
    sheet = _get_or_create_sheet(book, worksheet_name)

    values = sheet.col_values(column_index)
    if len(values) < start_row:
        return set()

    video_ids: set[str] = set()
    for raw in values[start_row - 1 :]:
        video_id = extract_video_id_from_url(raw)
        if video_id:
            video_ids.add(video_id)

    return video_ids


def read_existing_video_ids(
    client: gspread.Client,
    spreadsheet_id: str,
    worksheet_name: str,
) -> set[str]:
    if not spreadsheet_id.strip():
        raise SpreadsheetServiceError("SPREADSHEET_ID が未設定です。")

    book = client.open_by_key(spreadsheet_id)
    sheet = _get_or_create_sheet(book, worksheet_name)

    values = sheet.get_all_values()
    if len(values) <= 1:
        return set()

    header = values[0]
    rows = values[1:]

    normalized_header = [h.strip().lower() for h in header]
    video_id_idx = normalized_header.index("video_id") if "video_id" in normalized_header else None

    url_candidates = ["url", "動画url", "youtube_url", "大見出しurl"]
    url_idx = next((normalized_header.index(c) for c in url_candidates if c in normalized_header), None)

    existing_ids: set[str] = set()
    for row in rows:
        video_id = ""
        if video_id_idx is not None and len(row) > video_id_idx:
            video_id = row[video_id_idx].strip()

        if not video_id and url_idx is not None and len(row) > url_idx:
            video_id = extract_video_id_from_url(row[url_idx])

        if video_id:
            existing_ids.add(video_id)

    return existing_ids


def append_videos(
    client: gspread.Client,
    spreadsheet_id: str,
    worksheet_name: str,
    channel_id: str,
    videos: Iterable[VideoItem],
) -> int:
    if not spreadsheet_id.strip():
        raise SpreadsheetServiceError("SPREADSHEET_ID が未設定です。")

    book = client.open_by_key(spreadsheet_id)
    sheet = _get_or_create_sheet(book, worksheet_name)

    header = [
        "タイトル",
        "日付",
        "URL",
        "大見出し",
        "大見出しURL",
        "小見出し",
        "小見出しURL",
        "自動検出タグ",
    ]

    if not sheet.get_all_values():
        sheet.append_row(header, value_input_option="RAW")

    rows: list[list[str]] = []
    for video in videos:
        major, major_url, minor, minor_url = _extract_timestamp_fields(video.url, video.timestamp_comment)
        rows.append(
            [
                video.title,
                _to_jst_date(video.published_at),
                video.url,
                major,
                major_url,
                minor,
                minor_url,
                "|".join(video.tags),
            ]
        )

    if rows:
        sheet.append_rows(rows, value_input_option="RAW")

    return len(rows)


def _extract_timestamp_fields(video_url: str, timestamp_comment: str) -> tuple[str, str, str, str]:
    if not timestamp_comment.strip():
        return "", "", "", ""

    items: list[tuple[str, str]] = []
    for match in TIMESTAMP_WITH_LABEL_PATTERN.finditer(timestamp_comment):
        ts = (match.group("ts") or "").strip()
        label = (match.group("label") or "").strip()
        if not ts:
            continue
        items.append((ts, label))
        if len(items) >= 2:
            break

    if not items:
        return "", "", "", ""

    major_ts, major_label = items[0]
    major_text = f"{major_ts} {major_label}".strip()
    major_url = _build_timestamp_url(video_url, major_ts)

    minor_text = ""
    minor_url = ""
    if len(items) >= 2:
        minor_ts, minor_label = items[1]
        minor_text = f"{minor_ts} {minor_label}".strip()
        minor_url = _build_timestamp_url(video_url, minor_ts)

    return major_text, major_url, minor_text, minor_url


def _build_timestamp_url(video_url: str, timestamp: str) -> str:
    seconds = _timestamp_to_seconds(timestamp)
    if seconds <= 0:
        return video_url
    separator = "&" if "?" in video_url else "?"
    return f"{video_url}{separator}t={seconds}s"


def _timestamp_to_seconds(timestamp: str) -> int:
    raw = timestamp.strip()
    if not raw:
        return 0
    parts = raw.split(":")
    try:
        nums = [int(p) for p in parts]
    except ValueError:
        return 0
    if len(nums) == 2:
        return nums[0] * 60 + nums[1]
    if len(nums) == 3:
        return nums[0] * 3600 + nums[1] * 60 + nums[2]
    return 0


def _to_jst_date(published_at: str) -> str:
    value = (published_at or "").strip()
    if not value:
        return ""
    normalized = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        return value
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    jst = timezone(timedelta(hours=9))
    return dt.astimezone(jst).date().isoformat()
