function unwrapFetchFailureMessage(message) {
  const normalized = String(message || "").trim();
  const wrapped = normalized.match(/^[^:]+ の取得に失敗しました:\s*(.+)$/);
  return wrapped ? String(wrapped[1] || "").trim() : normalized;
}

function isInvalidJsonShapeError(error, message) {
  if (error && typeof error === "object") {
    if (error.code === "INVALID_JSON_SHAPE") return true;
    if (error.name === "InvalidJsonShapeError") return true;
  }
  return (
    message === "JSON形式が不正です"
    || /形式が不正/.test(message)
    || /schema/i.test(message)
  );
}

export function normalizeFailureReason(error) {
  const rawMessage = error instanceof Error ? error.message : String(error || "");
  const message = unwrapFetchFailureMessage(rawMessage);
  const httpMatch = message.match(/HTTP\s+\d{3}/);
  if (httpMatch) return httpMatch[0];
  if (message === "ネットワークエラー") return message;
  if (message === "JSONの解析に失敗しました") return message;
  if (message === "JSON形式が不正です") return message;
  if (isInvalidJsonShapeError(error, message)) return "JSON形式が不正です";
  if (error instanceof SyntaxError) return "JSONの解析に失敗しました";
  if (error instanceof TypeError) return "ネットワークエラー";
  if (/Failed to fetch|NetworkError|network request/i.test(message)) return "ネットワークエラー";
  if (/Unexpected token|Unexpected end of JSON input|JSON\.parse/i.test(message)) return "JSONの解析に失敗しました";
  return "不明なエラー";
}

export function createTargetFetchError(targetName, error) {
  const reason = normalizeFailureReason(error);
  return new Error(`${targetName} の取得に失敗しました: ${reason}`);
}

export function createInvalidJsonShapeError(message = "JSON形式が不正です") {
  const error = new Error(message);
  error.name = "InvalidJsonShapeError";
  error.code = "INVALID_JSON_SHAPE";
  return error;
}

export async function fetchJson(url, options = {}) {
  let response;
  try {
    response = await fetch(url, { cache: "no-store", ...options });
  } catch {
    throw new Error("ネットワークエラー");
  }
  if (!response.ok) throw new Error(`HTTP ${response.status}`);

  try {
    return await response.json();
  } catch {
    throw new Error("JSONの解析に失敗しました");
  }
}

export async function fetchJsonFromCandidates(candidates, config = {}) {
  const { targetName = "JSON", fetchOptions = {} } = config || {};
  let lastReason = "不明なエラー";

  for (const candidate of (Array.isArray(candidates) ? candidates : [])) {
    try {
      return await fetchJson(candidate, fetchOptions);
    } catch (error) {
      lastReason = normalizeFailureReason(error);
    }
  }

  throw createTargetFetchError(targetName, lastReason);
}
