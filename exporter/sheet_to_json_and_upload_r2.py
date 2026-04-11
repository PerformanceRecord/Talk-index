from __future__ import annotations

import json
import os
import re
from hashlib import sha1
from collections import defaultdict
from datetime import datetime, timezone

import boto3

from crawler.services.spreadsheet import build_gspread_client, normalize_spreadsheet_id

TOKEN_STOP_WORDS = {
    "の",
    "こと",
    "です",
    "ます",
    "する",
    "した",
    "いる",
    "ある",
    "なる",
    "よう",
    "ため",
    "話",
    "の話",
    "配信の話",
    "雑談の話",
    "について",
    "そして",
}
TOKEN_PATTERN = re.compile(r"[一-龠ぁ-んァ-ヶーa-zA-Z0-9]+")
OPENING_ENDING_SECTIONS = {"【オープニングトーク】", "【エンディングトーク】", "【開場】"}


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} が未設定です。GitHub Secrets を確認してください。")
    return value


def _text(value: str | None) -> str:
    return (value or "").strip()


def _split_tags(raw: str) -> list[str]:
    tags: list[str] = []
    for item in _text(raw).split(","):
        tag = _text(item).lstrip("#")
        if tag:
            tags.append(tag)
    return tags


def _normalize_token(raw_token: str) -> str:
    token = _text(raw_token).lower()
    if not token:
        return ""
    if token in TOKEN_STOP_WORDS:
        return ""
    if token.endswith("の話"):
        return _normalize_token(token[:-2])
    if len(token) <= 1 and not token.isdigit():
        return ""
    return token


def _tokenize_text(raw: str) -> list[str]:
    words = TOKEN_PATTERN.findall(_text(raw))
    seen: set[str] = set()
    for word in words:
        token = _normalize_token(word)
        if token:
            seen.add(token)
    return sorted(seen)


def _finalize_store(source: dict[str, dict[str, object]]) -> dict[str, object]:
    entries: list[dict[str, object]] = []
    postings: defaultdict[str, list[str]] = defaultdict(list)

    for entry in source.values():
        tokens = sorted(entry["tokens"])
        record = {
            "id": entry["id"],
            "title": entry["title"],
            "subtitle": entry["subtitle"],
            "date": entry["date"],
            "tokens": tokens[:16],
        }
        entries.append(record)
        for token in record["tokens"]:
            postings[token].append(record["id"])

    entries.sort(key=lambda x: str(x["id"]))
    return {
        "entries": entries,
        "inverted_index": {token: sorted(ids) for token, ids in sorted(postings.items())},
    }


def _build_search_entries(items: list[dict[str, object]]) -> dict[str, object]:
    by_video: dict[str, dict[str, object]] = {}
    by_talk: dict[str, dict[str, object]] = {}

    for item in items:
        title = _text(item.get("title") if isinstance(item.get("title"), str) else "")
        date = _text(item.get("date") if isinstance(item.get("date"), str) else "")
        url = _text(item.get("url") if isinstance(item.get("url"), str) else "")
        section = _text(item.get("section") if isinstance(item.get("section"), str) else "")
        subsection = _text(item.get("subsection") if isinstance(item.get("subsection"), str) else "")
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []

        video_id = _text(item.get("id") if isinstance(item.get("id"), str) else "")
        if video_id and video_id not in by_video:
            by_video[video_id] = {
                "id": video_id,
                "title": title or "タイトルなし",
                "subtitle": date or "日付なし",
                "date": date,
                "tokens": set(),
            }
        if video_id:
            video = by_video[video_id]
            for src in [title, section, subsection, *[str(tag) for tag in tags]]:
                for token in _tokenize_text(src):
                    video["tokens"].add(token)

        if not section:
            continue
        if section in OPENING_ENDING_SECTIONS:
            continue

        if section not in by_talk:
            by_talk[section] = {
                "id": section,
                "title": subsection or section,
                "subtitle": section,
                "date": "",
                "tokens": set(),
            }
        talk = by_talk[section]
        for src in [section, subsection, title]:
            for token in _tokenize_text(src):
                talk["tokens"].add(token)

    return {
        "video": _finalize_store(by_video),
        "talk": _finalize_store(by_talk),
    }


def _extract_youtube_video_id(url: str) -> str:
    src = _text(url)
    if not src:
        return ""
    patterns = [
        r"youtu\.be/([A-Za-z0-9_-]{6,})",
        r"[?&]v=([A-Za-z0-9_-]{6,})",
        r"/shorts/([A-Za-z0-9_-]{6,})",
    ]
    for pattern in patterns:
        matched = re.search(pattern, src)
        if matched:
            return matched.group(1)
    return ""


def _thumbnail_url(url: str) -> str:
    video_id = _extract_youtube_video_id(url)
    return f"https://i.ytimg.com/vi/{video_id}/mqdefault.jpg" if video_id else ""


def _is_singing_item(item: dict[str, object]) -> bool:
    title = _text(item.get("title") if isinstance(item.get("title"), str) else "")
    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
    return "#歌枠" in title or any(_text(str(tag)) in {"歌枠", "#歌枠"} for tag in tags)


def _parse_date_sort_key(value: str) -> tuple[int, str]:
    raw = _text(value)
    if not raw:
        return (0, "")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return (1, parsed.date().isoformat())
    except ValueError:
        return (0, raw)


def _build_staged_payloads(items: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict[str, dict[str, object]], list[dict[str, object]]]:
    videos_by_key: dict[str, dict[str, object]] = {}
    talks_by_section: dict[str, dict[str, object]] = {}

    for item in items:
        title = _text(item.get("title") if isinstance(item.get("title"), str) else "")
        date = _text(item.get("date") if isinstance(item.get("date"), str) else "")
        url = _text(item.get("url") if isinstance(item.get("url"), str) else "")
        section = _text(item.get("section") if isinstance(item.get("section"), str) else "")
        section_url = _text(item.get("section_url") if isinstance(item.get("section_url"), str) else "")
        subsection = _text(item.get("subsection") if isinstance(item.get("subsection"), str) else "")
        tags = [_text(str(tag)) for tag in (item.get("tags") if isinstance(item.get("tags"), list) else []) if _text(str(tag))]

        if not title or not section:
            continue

        video_key = url or f"{title}::{date}"
        video = videos_by_key.get(video_key)
        if video is None:
            preferred_id = _extract_youtube_video_id(url)
            if not preferred_id:
                fallback_src = f"{video_key}|{title}|{date}"
                preferred_id = f"v-{sha1(fallback_src.encode('utf-8')).hexdigest()[:16]}"
            video = {
                "id": preferred_id,
                "title": title or "タイトルなし",
                "date": date,
                "url": url,
                "thumb": _thumbnail_url(url),
                "tags": set(),
                "sections": {},
                "sort_key": _parse_date_sort_key(date),
            }
            videos_by_key[video_key] = video
        video["tags"].update(tags)

        sections = video["sections"]
        if section not in sections:
            sections[section] = {"name": section, "sectionUrl": section_url, "subsections": []}
        if subsection:
            sections[section]["subsections"].append({"name": subsection})

        if section in OPENING_ENDING_SECTIONS:
            continue
        talk = talks_by_section.get(section)
        if talk is None:
            talk = {
                "key": section,
                "name": section,
                "sectionUrl": section_url,
                "date": "",
                "thumb": "",
                "hasSingingVideo": False,
                "subsections": [],
                "sort_key": (0, ""),
            }
            talks_by_section[section] = talk
        if _parse_date_sort_key(date) > talk["sort_key"]:
            talk["sort_key"] = _parse_date_sort_key(date)
            talk["date"] = date
        if not talk["thumb"] and url:
            talk["thumb"] = _thumbnail_url(url)
        if _is_singing_item(item):
            talk["hasSingingVideo"] = True
        if subsection:
            talk["subsections"].append(
                {
                    "name": subsection,
                    "videoTitle": title or "タイトルなし",
                    "videoUrl": url,
                }
            )

    video_details: dict[str, dict[str, object]] = {}
    video_summaries: list[dict[str, object]] = []
    for video in videos_by_key.values():
        detail_id = str(video["id"])
        section_list = list(video["sections"].values())
        video_details[detail_id] = {"id": detail_id, "sections": section_list}
        video_summaries.append(
            {
                "id": detail_id,
                "key": detail_id,
                "title": video["title"],
                "date": video["date"],
                "url": video["url"],
                "tags": sorted(video["tags"]),
                "section_count": len(section_list),
                "thumb": video["thumb"],
                "detail_id": detail_id,
            }
        )

    video_summaries.sort(
        key=lambda v: (_parse_date_sort_key(str(v.get("date"))), str(v.get("id"))),
        reverse=True,
    )

    talks: list[dict[str, object]] = []
    for talk in talks_by_section.values():
        talks.append(
            {
                "key": talk["key"],
                "name": talk["name"],
                "sectionUrl": talk["sectionUrl"],
                "date": talk["date"],
                "thumb": talk["thumb"],
                "hasSingingVideo": talk["hasSingingVideo"],
                "subsections": talk["subsections"],
            }
        )
    talks.sort(key=lambda t: (_parse_date_sort_key(str(t.get("date"))), str(t.get("key"))), reverse=True)

    return video_summaries, video_details, talks


def main() -> None:
    spreadsheet_id = normalize_spreadsheet_id(_require_env("SPREADSHEET_ID"))
    worksheet_name = os.getenv("SPREADSHEET_WORKSHEET_NAME", "索引").strip() or "索引"
    service_account_json = _require_env("GOOGLE_SERVICE_ACCOUNT_JSON")

    r2_account_id = _require_env("R2_ACCOUNT_ID")
    r2_access_key_id = _require_env("R2_ACCESS_KEY_ID")
    r2_secret_access_key = _require_env("R2_SECRET_ACCESS_KEY")
    r2_bucket_name = _require_env("R2_BUCKET_NAME")

    endpoint_url = f"https://{r2_account_id}.r2.cloudflarestorage.com"

    try:
        gspread_client = build_gspread_client(service_account_json)
        sheet = gspread_client.open_by_key(spreadsheet_id).worksheet(worksheet_name)
        values = sheet.get_all_values()
    except Exception as exc:
        raise RuntimeError("Googleスプレッドシートの読み取りに失敗しました。設定値と権限を確認してください。") from exc

    items: list[dict[str, object]] = []
    if values:
        headers = [_text(h) for h in values[0]]
        for row_index, raw in enumerate(values[1:], start=2):
            if not any(_text(cell) for cell in raw):
                continue

            row: dict[str, str] = {}
            for i, header in enumerate(headers):
                if not header:
                    continue
                row[header] = raw[i] if i < len(raw) else ""

            title = _text(row.get("タイトル"))
            section = _text(row.get("大見出し"))
            if not title or not section:
                continue

            date = _text(row.get("日付"))
            url = _text(row.get("URL"))
            item_id = url or f"row-{row_index}"
            items.append(
                {
                    "id": item_id,
                    "title": title,
                    "date": date,
                    "url": url,
                    "section": section,
                    "section_url": _text(row.get("大見出しURL")),
                    "subsection": _text(row.get("小見出し")),
                    "tags": _split_tags(row.get("自動検出タグ", "")),
                }
            )

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    video_summaries, video_details_map, talks = _build_staged_payloads(items)

    latest_payload = {
        "version": 1,
        "generated_at": generated_at,
        "videos": video_summaries,
    }
    talks_payload = {
        "version": 1,
        "generated_at": generated_at,
        "talks": talks,
    }

    search_store = _build_search_entries(items)
    search_payload = {
        "version": 1,
        "generated_at": generated_at,
        "video": search_store["video"],
        "talk": search_store["talk"],
    }

    try:
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=r2_access_key_id,
            aws_secret_access_key=r2_secret_access_key,
            region_name="auto",
        )

        s3.put_object(
            Bucket=r2_bucket_name,
            Key="index/latest.json",
            Body=json.dumps(latest_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        s3.put_object(
            Bucket=r2_bucket_name,
            Key="index/search_index.json",
            Body=json.dumps(search_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        s3.put_object(
            Bucket=r2_bucket_name,
            Key="index/talks.json",
            Body=json.dumps(talks_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            ContentType="application/json; charset=utf-8",
        )
        for detail_id, detail_payload in sorted(video_details_map.items()):
            s3.put_object(
                Bucket=r2_bucket_name,
                Key=f"index/video-details/{detail_id}.json",
                Body=json.dumps(detail_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
                ContentType="application/json; charset=utf-8",
            )
    except Exception as exc:
        raise RuntimeError("R2 へのアップロードに失敗しました。認証情報・バケット名・権限を確認してください。") from exc

    print(
        "done: "
        f"worksheet={worksheet_name}, "
        f"items={len(items)}, "
        f"videos={len(video_summaries)}, "
        f"video_details={len(video_details_map)}, "
        f"talks={len(talks)}, "
        f"search_video_entries={len(search_store['video']['entries'])}, "
        f"search_talk_entries={len(search_store['talk']['entries'])}, "
        f"bucket={r2_bucket_name}, "
        "keys=index/latest.json,index/talks.json,index/video-details/*.json,index/search_index.json"
    )


if __name__ == "__main__":
    main()
