# DESIGN.md

## 1. 目的（AI向けデザインシステム仕様）

このドキュメントは、**AIエージェントが実装時にUIの一貫性を守るための共通ルール**です。  
特に以下を保証します。

- ブランドトーン（明るいオレンジ系 + 水色系、親しみやすい雰囲気）
- コンポーネントの見た目と挙動の統一
- 既存 `index.html` / `src/app.js` / `src/ui/renderSongs.js` と整合する実装

---

## 2. ブランドトーン & デザイン原則

- テーマは「海・泡・歌」の軽快さ。
- 背景は暖色グラデーション、カードは淡い寒色で可読性を確保。
- 情報量は多いが、カード分割・余白・小さなアニメーションで圧迫感を抑える。
- モバイル操作を優先し、PCでは同一情報を広く読みやすく表示する。

---

## 3. デザイントークン（必須）

> 既存CSSカスタムプロパティを正として扱うこと。

### 3.1 Color

- `--surface: #F8FDFF`
- `--surface-2: #E8F5FB`
- `--text: #102033`
- `--muted: #486174`
- `--line: #74899A`
- `--primary: #145A86`
- `--primary-strong: #0F4D73`
- `--accent: #2F7AA8`
- `--danger: #DC2626`
- `--success: #059669`
- `--focus: #00C2FF`

### 3.2 Spacing / Radius / Size

- 余白: `--space-1: 4px`, `--space-2: 8px`, `--space-3: 12px`, `--space-4: 16px`
- 角丸: `--radius-sm: 8px`, `--radius-md: 12px`
- 入力系高さ: `--control-height: 36px`
- 入力系フォント: `--font-control: 16px`
- PC最大幅: `--pc-content-max-width: 860px`

### 3.3 Typography

- フォント: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans JP", sans-serif`
- 基本方針:
  - 本文は高コントラスト（`--text`）
  - 補助情報は `--muted`
  - 見出しは過度に大きくしない（密度重視）

---

## 4. レイアウト要件（現行HTML準拠）

ページは固定3層構造。

1. **Top Form（固定）**: フィルタカード / メモカードの横スワイプ
2. **Middle Form（固定）**: 楽曲カード一覧（内部スクロール）
3. **Bottom Form（固定）**: 検索カード / マイ弾幕カードの横スワイプ + 固定操作列

### 4.1 レスポンシブ

- `max-width: 860px` を中心にモバイルとPCを切替。
- モバイル: 余白を縮小し、カード展開はタップ時のみ。
- PC: 楽曲カード詳細は常時展開寄り（読みやすさ優先）。

### 4.2 Safe Area対応

- `env(safe-area-inset-top/bottom)` を前提に固定UIの重なりを調整。
- `--scroll-top-offset` などの動的変数で表示領域を補正。

---

## 5. コンポーネントスタイル要件

## 5.1 Card

- 背景 `--surface`
- 枠線 `1px solid --line`
- 角丸 `--radius-md` / 内部要素は `--radius-sm`

## 5.2 Input / Select / Button

- 高さは `--control-height` 以上
- 背景は `--surface-2`
- `button.primary` は `--primary` 系で強調
- フォーカスは白アウトライン + `--focus` グロー（視認性必須）

## 5.3 Song Card

- ヘッダ: タイトル + アーティスト + コピー操作
- 詳細: タグ / Latest日付 / 外部リンク / 動画プレビュー
- モバイルは `expanded` で開閉、PCは基本展開

## 5.4 Status Pill

- `loading / ok / error` の3状態
- 状態別で背景・ボーダー・ドット色・アニメーションを変更
- クリック/Enter/Space でインストール案内ポップオーバーを開閉

## 5.5 Toast

- 画面中央固定
- 短時間表示（コピー完了など）

## 5.6 装飾アニメーション

- 背景泡（`body::before/::after`）
- スクロール連動泡（`.scroll-bubble`）
- `prefers-reduced-motion` はアニメ停止
- デスクトップ（fine pointer）では一部モーション抑制

---

## 6. 現行機能要件（HTML起点）

> ここは「何が必要か」を機能単位で定義する。

### 6.1 絞り込み機能

- 種別チェック: 歌枠 / 歌ってみた / ショート
- 検索: 曲名 / アーティスト / メモを対象
- 並び替え: 項目（artist/title/date）×順序（asc/desc）
- 0件時はダミーカードと案内を表示

### 6.2 メモ機能

- テキストエリア入力
- コピー
- ペースト（Clipboard API失敗時は `prompt` フォールバック）

### 6.3 弾幕機能

- プリセット弾幕選択
- カスタム弾幕（絵文字1個を正規化し定型文字列化）
- 保存後は `my` オプションへ反映 + ラベル更新 + コピー

### 6.4 楽曲一覧機能

- データ取得後にカード描画
- タグ色分け（歌枠/歌ってみた/ショート）
- コピー（曲名/アーティスト）
- 動画リンクプレビュー開閉
- サムネイル失敗時はフォールバックURLを試行

### 6.5 PWA補助機能

- Service Worker登録
- install案内（Android prompt / iOS手動案内 / 既インストール判定）

### 6.6 エラー可視化

- 詳細ログをJSON整形で保持
- UI表示/コピー
- ステータス連動

---

## 7. CSS要件（機能別の詳細）

### 7.1 共通基盤

- `:root` のトークンを唯一の見た目ソースとする
- 直接色値の追加は最小限（既存意図がある場合のみ）

### 7.2 レイアウト

- `top-form`, `middle-form`, `bottom-form` は固定配置
- 実幅は共通計算（左右位置と幅の同期が前提）
- `song-cards` は内部スクロール領域

### 7.3 スワイプUI

- `*-swipe-track` は `width: 200%` の2面構成
- `transform: translateX(...)` で面切替
- `dragging` 時はトランジション無効
- ページドットで現在面を可視化

### 7.4 状態表現

- `.status-shell[data-state="..."]` で状態を切替
- `.song-card.expanded` / `.song-card.preview-visible` で表示分岐
- `.error-log-wrap.show` で障害情報を開示

### 7.5 アクセシビリティ

- `:focus-visible` スタイルを全入力/操作要素に適用
- reduced-motion 時は主要アニメーション停止

---

## 8. JS要件（機能別の詳細）

### 8.1 初期化順序（必須）

1. `bind()` でイベント束縛
2. `setupTopSwipe()`
3. `setupBottomSwipe()`
4. `initializeApp()`（SW登録 / PWA補助 / データ取得）

### 8.2 状態管理

- `state` を単一ソースとし、UIは state から再描画する
- フィルタ・ソート・検索変更時は `rerenderOrLoadSongs()` を通す

### 8.3 データ取得

- 候補URL配列を優先順で試行
- 取得後はキャッシュ保持（TTL管理）
- 失敗時は詳細ログ生成（headers/body/status等を保持）

### 8.4 レンダリング

- `renderSongs.render()` に依存注入で必要関数を渡す
- HTML生成時は `escapeHtml` を必ず経由
- 詳細リンクは `bestExternalUrl` で正規化

### 8.5 入力補助

- クリップボードは `navigator.clipboard` を優先
- 失敗時は `execCommand('copy')` / `prompt` フォールバック

### 8.6 モーション制御

- スクロール量・速度から泡エフェクト強度を計算
- 一定間隔未満の連続描画は抑制
- 表示中カード数の上限を設ける

### 8.7 モバイル挙動

- 上部メニューはスクロール量に応じ折りたたみ
- 画面外へ出た `expanded` / `preview-visible` カードは自動解除

---

## 9. AIエージェント実装ルール（厳守）

- 新規UIは**既存トークンのみ**で配色/余白/角丸を決める。
- 新規ボタンは既存の `button` / `button.primary` 仕様を流用する。
- 新規カードは `.song-card` と同等の密度で、情報階層（タイトル→補助情報→操作）を守る。
- JavaScript追加時は、
  - 既存の `state` 主導の再描画方針を壊さない
  - フォールバック手段を先に定義する
  - モバイル・PC双方の挙動差を明示する
- アニメーション追加時は `prefers-reduced-motion` の停止条件を必須で入れる。

---

## 10. 変更チェックリスト

- [ ] `:root` トークンを流用している
- [ ] fixed 3層レイアウト（top/middle/bottom）を崩していない
- [ ] モバイルでタップ操作・スワイプ操作が成立する
- [ ] キーボード操作（Enter/Space/Escape）を阻害しない
- [ ] コピー・貼り付け・リンク遷移のフォールバックがある
- [ ] エラー時に状態表示とログ確認が可能
- [ ] reduced-motionで過度なアニメーションが止まる
