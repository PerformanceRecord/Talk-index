# Talk-index

YouTube チャンネルの動画情報とコメント内タイムスタンプを収集し、
Google スプレッドシートに蓄積、JSON 化して Cloudflare R2 に配信するための設計メモです。

## 目的

- YouTube Data API v3 で動画情報を定期取得する
- コメントのタイムスタンプ（大見出し/小見出し）を構造化する
- スプレッドシートを JSON に変換し、R2 に公開する
- 静的 HTML/JavaScript で検索・閲覧できるようにする

## 全体アーキテクチャ

1. **Crawler (Python)**
   - チャンネル動画取得（差分）
   - コメント解析（タイムスタンプ抽出）
   - スプレッドシート更新
2. **Exporter (Python または GAS)**
   - スプレッドシートから JSON を生成
3. **Deployer (GitHub Actions)**
   - 日次で JSON を R2 にアップロード
4. **Frontend (Static HTML/JS)**
   - R2 上の JSON を読み込み、一覧・検索・詳細表示

## 推奨ディレクトリ構成

```text
/
├─ crawler/                      # Python: 収集・解析
├─ exporter/                     # Python: Sheet→JSON
├─ frontend/                     # 静的HTML/CSS/JS
├─ gas/                          # 補助用GAS（必要時のみ）
├─ .github/workflows/            # 定期実行
└─ docs/                         # 設計・運用メモ
```

## スプレッドシート設計

### 1) `title_list`（動画一覧）
新着検知と重複防止用。

- `video_id`（一意キー）
- `title`
- `url`
- `published_at`
- `thumbnail_url`
- `tags`
- `first_seen_at`
- `created_at`
- `updated_at`

### 2) `video_index`（詳細・解析結果）
動画ごとの解析状態と章情報を保存。

- `video_id`
- `timestamp_status`（`not_checked` / `found` / `not_found` / `error`）
- `last_checked_at`
- `parse_version`
- `error_message`
- `chapter_type`（`main` / `sub`）
- `parent_main_time`（sub の親）
- `timestamp`
- `chapter_title`
- `sort_order`
- `source_comment_id`
- `created_at`
- `updated_at`

### 3) `state`（実行状態）
再開可能にするための管理値。

- `last_success_at`（新着取得の基準時刻）
- `backfill_next_page_token`（遡及取得の次ページ）
- `backfill_done`（true/false）

## 差分更新方針（最適案）

### A. 新着追従
- `publishedAfter = last_success_at - 1日` で取得（取りこぼし防止）
- 未登録 `video_id` のみ `title_list` に追加
- 保険として最新30件も確認

### B. 未解析再試行
- `timestamp_status in (not_checked, error)` を優先
- `not_found` は毎回再解析せず、一定間隔（例: 7日）で再確認

### C. 遡及バックフィル（900件対応）
- uploads playlist を `pageToken` で古い順に巡回
- 1回の実行で 2〜5 ページ処理し、`backfill_next_page_token` を保存
- 次回は前回の続きから再開
- token が無くなれば完了

## タイムスタンプ抽出ルール

### 大見出し（main）
- 形式: `hh:mm:ss`（必須2桁）
- 例: `00:12:34 雑談パート`

### 小見出し（sub）
- 形式: `├h:mm:ss` / `└hh:mm:ss`（先頭記号付き）
- 例: `├1:23:45 話題A`

### 親子付け
- 直前の main を親にする
- 親のない sub は無効として破棄

### コメント選定（現実的実装）
- relevance順で上位コメントを取得
- 「投稿者本人」「like数」「main/sub行数」を点数化
- 最高スコアの1コメントを採用

> 注: 固定コメントは API で明確フラグ取得が難しいため要確認。

## JSON 出力仕様（初期）

初期は `videos.json` のみ。

```json
[
  {
    "video_id": "xxx",
    "title": "動画タイトル",
    "url": "https://www.youtube.com/watch?v=xxx",
    "published_at": "2026-04-01T12:34:56Z",
    "thumbnail_url": "https://...",
    "tags": ["tag1", "tag2"],
    "timestamps": [
      {
        "time": "00:12:34",
        "title": "雑談パート",
        "children": [
          { "time": "01:23:45", "title": "話題A" }
        ]
      }
    ]
  }
]
```

## フロントエンド方針

- 一覧カード: 投稿日 / タイトル / タグ
- 検索: 投稿日、タイトル、タグ、大見出しタイトル
- 詳細: サムネ、リンク、タグ、タイムスタンプ
- UI: main を表示し、クリックで sub を展開

## GitHub Actions / R2 方針

### 1) `crawl.yml`（必要なら1日複数回）
- 新着追従
- 未解析再試行
- バックフィル少量進行

### 2) `export-and-upload.yml`（1日1回）
- スプレッドシート読込
- JSON 生成
- R2 へアップロード（S3互換API）

### シークレット（必須）
- YouTube API key
- Google サービスアカウント情報
- R2 Access Key / Secret / Bucket / Account ID

## MVP（最初に作る範囲）

1. `title_list` / `video_index` / `state` 作成
2. 新着追従 + バックフィルの最小実装
3. タイムスタンプ解析（main/sub）
4. `videos.json` 生成
5. 日次アップロード
6. 静的フロントで一覧・検索・詳細

## 注意点

- API quota を超えないように件数制限を必ず入れる
- 再実行しても壊れない（冪等）更新にする
- エラー理由をシートに残す（追跡容易化）
- 取得不可データは「要確認」と明記して運用する
