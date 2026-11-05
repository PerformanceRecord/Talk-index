const GITHUB_API_ROOT = "https://api.github.com";
const GITHUB_API_VERSION = "2026-03-10";

function requiredText(env, name) {
  const value = String(env?.[name] || "").trim();
  if (!value) {
    throw new Error(`${name} が未設定です。Cloudflare Worker の環境変数または Secret を確認してください。`);
  }
  return value;
}

function parseWorkflowFiles(rawValue) {
  const workflowFiles = rawValue
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  if (workflowFiles.length === 0) {
    throw new Error("GITHUB_WORKFLOWS に監視対象のワークフローファイルを1件以上指定してください。");
  }

  const invalid = workflowFiles.find((value) => !/^[A-Za-z0-9._-]+\.ya?ml$/.test(value));
  if (invalid) {
    throw new Error(`GITHUB_WORKFLOWS に不正なファイル名があります: ${invalid}`);
  }

  return [...new Set(workflowFiles)];
}

export function loadWatchdogConfig(env) {
  return {
    token: requiredText(env, "GITHUB_TOKEN"),
    owner: requiredText(env, "GITHUB_OWNER"),
    repository: requiredText(env, "GITHUB_REPOSITORY"),
    workflowFiles: parseWorkflowFiles(requiredText(env, "GITHUB_WORKFLOWS")),
  };
}

function buildWorkflowUrl(config, workflowFile, suffix = "") {
  const owner = encodeURIComponent(config.owner);
  const repository = encodeURIComponent(config.repository);
  const workflow = encodeURIComponent(workflowFile);
  return `${GITHUB_API_ROOT}/repos/${owner}/${repository}/actions/workflows/${workflow}${suffix}`;
}

async function githubRequest(config, workflowFile, fetchImpl, { method = "GET", suffix = "", expectedStatus }) {
  const url = buildWorkflowUrl(config, workflowFile, suffix);
  let response;
  try {
    response = await fetchImpl(url, {
      method,
      headers: {
        accept: "application/vnd.github+json",
        authorization: `Bearer ${config.token}`,
        "x-github-api-version": GITHUB_API_VERSION,
        "user-agent": "talk-index-actions-watchdog",
      },
    });
  } catch (error) {
    throw new Error(`${workflowFile}: GitHub APIへの接続に失敗しました: ${error?.message || error}`, { cause: error });
  }

  const bodyText = await response.text();
  if (response.status !== expectedStatus) {
    const detail = bodyText.trim().slice(0, 500) || "response body is empty";
    throw new Error(`${workflowFile}: GitHub API ${method} が失敗しました（HTTP ${response.status}）: ${detail}`);
  }

  if (!bodyText.trim()) return null;
  try {
    return JSON.parse(bodyText);
  } catch (error) {
    throw new Error(`${workflowFile}: GitHub APIの応答JSONを解析できませんでした: ${error?.message || error}`, { cause: error });
  }
}

async function readWorkflow(config, workflowFile, fetchImpl) {
  const payload = await githubRequest(config, workflowFile, fetchImpl, {
    expectedStatus: 200,
  });
  const state = String(payload?.state || "").trim();
  if (!state) {
    throw new Error(`${workflowFile}: GitHub APIの応答にstateがありません。`);
  }
  return state;
}

export async function ensureWorkflowActive(config, workflowFile, fetchImpl = fetch) {
  const previousState = await readWorkflow(config, workflowFile, fetchImpl);
  if (previousState === "active") {
    return { workflowFile, previousState, state: "active", action: "none" };
  }

  if (previousState === "disabled_manually") {
    throw new Error(`${workflowFile}: 手動で無効化されています。意図した停止を保護するため自動再有効化しません。`);
  }

  if (previousState !== "disabled_inactivity") {
    throw new Error(`${workflowFile}: 未対応のワークフロー状態です: ${previousState}`);
  }

  await githubRequest(config, workflowFile, fetchImpl, {
    method: "PUT",
    suffix: "/enable",
    expectedStatus: 204,
  });

  const state = await readWorkflow(config, workflowFile, fetchImpl);
  if (state !== "active") {
    throw new Error(`${workflowFile}: 再有効化後の状態確認に失敗しました: ${state}`);
  }

  return { workflowFile, previousState, state, action: "enabled" };
}

export async function monitorGitHubActions(env, fetchImpl = fetch) {
  const config = loadWatchdogConfig(env);
  const results = [];
  const errors = [];

  for (const workflowFile of config.workflowFiles) {
    try {
      results.push(await ensureWorkflowActive(config, workflowFile, fetchImpl));
    } catch (error) {
      const message = error?.message || String(error);
      results.push({ workflowFile, state: "error", action: "none", error: message });
      errors.push(message);
    }
  }

  if (errors.length > 0) {
    const error = new Error(`GitHub Actions監視で${errors.length}件のエラーが発生しました: ${errors.join(" | ")}`);
    error.results = results;
    throw error;
  }

  return results;
}
