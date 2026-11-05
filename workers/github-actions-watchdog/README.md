# GitHub Actions watchdog Worker

公開リポジトリの無操作期間によってGitHub Actionsの予約実行が停止した場合に、Cloudflareから検知して再有効化するWorkerです。

## 動作

- 毎日 03:55 / 15:55 JST に監視します。
- `active` は変更しません。
- GitHubによる無操作停止の `disabled_inactivity` だけを再有効化します。
- `disabled_manually` は意図した停止として保護し、再有効化せずエラーを記録します。
- 4ワークフローをすべて確認し、一部が失敗しても残りの状態確認を継続します。

## GitHubトークン

`Talk-index` は別ユーザー所有の公開リポジトリで、共同編集者のfine-grained personal access tokenでは書き込み対象に選べません。そのため、現在はclassic personal access tokenを次の構成で使用します。

- Expiration: `No expiration`
- Scope: `public_repo` のみ
- `repo` / `workflow` など、privateリポジトリへ届く権限は付けない

classic tokenの仕様上、対象を1リポジトリだけに限定することはできません。トークンはソースや `wrangler.toml` に記載せず、Cloudflare Secret `GITHUB_TOKEN` に保存します。GitHub APIの再有効化リクエストでHTTP 204を確認してから登録してください。

## デプロイ

```powershell
npx wrangler deploy --config workers/github-actions-watchdog/wrangler.toml
npx wrangler secret put GITHUB_TOKEN --config workers/github-actions-watchdog/wrangler.toml
npx wrangler deploy --config workers/github-actions-watchdog/wrangler.toml
```

初回デプロイ後、Cloudflare DashboardのWorker設定でCron Triggersが2件登録されていることと、`GITHUB_TOKEN` がSecretとして登録されていることを確認します。

## テスト

```powershell
node --test workers/github-actions-watchdog/service.test.mjs
```
