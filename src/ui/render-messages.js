const MODE_MESSAGES = {
  video: {
    noResult: "条件に一致する動画はありません。",
    loading: "動画を読み込み中…",
    loadFailed: "動画データの読み込みに失敗しました。",
    fallback: "代替データを表示中です。",
  },
  talk: {
    noResult: "条件に一致するトークはありません。",
    loading: "トークを読み込み中…",
    loadFailed: "トークデータの読み込みに失敗しました。",
    fallback: "代替データを表示中です。",
  },
  favorites: {
    noResult: "条件に一致するお気に入りはありません。",
    loading: "お気に入りを読み込み中…",
    loadFailed: "お気に入りデータの読み込みに失敗しました。",
    fallback: "代替データを表示中です。",
  },
};

function normalizeMode(mode) {
  return mode === "talk" || mode === "favorites" ? mode : "video";
}

export function getModeMessage(mode, key) {
  const normalizedMode = normalizeMode(mode);
  return MODE_MESSAGES[normalizedMode]?.[key] || "";
}

export function getFavoritesMeta(status, readyText) {
  if (status === "ready") return readyText;
  if (status === "loading") return getModeMessage("favorites", "loading");
  if (status === "error") return getModeMessage("favorites", "loadFailed");
  return "未取得";
}
