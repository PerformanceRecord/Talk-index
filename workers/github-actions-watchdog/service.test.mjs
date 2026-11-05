import test from "node:test";
import assert from "node:assert/strict";

import {
  ensureWorkflowActive,
  loadWatchdogConfig,
  monitorGitHubActions,
} from "./service.mjs";

const CONFIG = {
  token: "secret-token",
  owner: "PerformanceRecord",
  repository: "Talk-index",
  workflowFiles: ["daily_crawl.yml"],
};

function jsonResponse(status, body) {
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

test("環境変数をtrimして監視対象を重複排除する", () => {
  const config = loadWatchdogConfig({
    GITHUB_TOKEN: " token ",
    GITHUB_OWNER: " PerformanceRecord ",
    GITHUB_REPOSITORY: " Talk-index ",
    GITHUB_WORKFLOWS: " daily_crawl.yml, upload_index_json_to_r2.yml, daily_crawl.yml ",
  });

  assert.equal(config.token, "token");
  assert.equal(config.owner, "PerformanceRecord");
  assert.deepEqual(config.workflowFiles, ["daily_crawl.yml", "upload_index_json_to_r2.yml"]);
});

test("必須Secretが空なら明確なエラーにする", () => {
  assert.throws(
    () => loadWatchdogConfig({
      GITHUB_TOKEN: "  ",
      GITHUB_OWNER: "PerformanceRecord",
      GITHUB_REPOSITORY: "Talk-index",
      GITHUB_WORKFLOWS: "daily_crawl.yml",
    }),
    /GITHUB_TOKEN が未設定です/,
  );
});

test("activeのワークフローは変更しない", async () => {
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return jsonResponse(200, { state: "active" });
  };

  const result = await ensureWorkflowActive(CONFIG, "daily_crawl.yml", fetchImpl);

  assert.equal(result.action, "none");
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.method, "GET");
  assert.equal(calls[0].options.headers.authorization, "Bearer secret-token");
});

test("disabled_inactivityだけを再有効化して状態を再確認する", async () => {
  const responses = [
    jsonResponse(200, { state: "disabled_inactivity" }),
    jsonResponse(204, null),
    jsonResponse(200, { state: "active" }),
  ];
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return responses.shift();
  };

  const result = await ensureWorkflowActive(CONFIG, "daily_crawl.yml", fetchImpl);

  assert.deepEqual(result, {
    workflowFile: "daily_crawl.yml",
    previousState: "disabled_inactivity",
    state: "active",
    action: "enabled",
  });
  assert.deepEqual(calls.map((call) => call.options.method), ["GET", "PUT", "GET"]);
  assert.match(calls[1].url, /daily_crawl\.yml\/enable$/);
});

test("手動無効化は自動で戻さない", async () => {
  const fetchImpl = async () => jsonResponse(200, { state: "disabled_manually" });

  await assert.rejects(
    ensureWorkflowActive(CONFIG, "daily_crawl.yml", fetchImpl),
    /手動で無効化されています/,
  );
});

test("一部の確認に失敗しても残りを確認し、原因をまとめて通知する", async () => {
  const env = {
    GITHUB_TOKEN: "token",
    GITHUB_OWNER: "PerformanceRecord",
    GITHUB_REPOSITORY: "Talk-index",
    GITHUB_WORKFLOWS: "daily_crawl.yml,upload_index_json_to_r2.yml",
  };
  const fetchImpl = async (url) => {
    if (url.includes("daily_crawl.yml")) {
      return jsonResponse(403, { message: "Resource not accessible by personal access token" });
    }
    return jsonResponse(200, { state: "active" });
  };

  await assert.rejects(
    monitorGitHubActions(env, fetchImpl),
    (error) => {
      assert.match(error.message, /HTTP 403/);
      assert.equal(error.results.length, 2);
      assert.equal(error.results[0].state, "error");
      assert.equal(error.results[1].state, "active");
      return true;
    },
  );
});
