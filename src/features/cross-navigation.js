function text(value) {
  return String(value ?? "").trim();
}

function normalizeTitle(value) {
  return text(value)
    .normalize("NFKC")
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function normalizeUrl(value) {
  const raw = text(value);
  if (!raw) return "";
  try {
    const url = new URL(raw);
    url.hash = "";
    return url.toString();
  } catch {
    return "";
  }
}

function extractYoutubeId(value) {
  const raw = text(value);
  if (!raw) return "";
  if (/^[A-Za-z0-9_-]{6,}$/.test(raw) && !raw.includes("/")) return raw;
  try {
    const url = new URL(raw);
    if (url.hostname.includes("youtu.be")) return url.pathname.split("/").filter(Boolean)[0] || "";
    if (url.searchParams.get("v")) return url.searchParams.get("v") || "";
    if (url.pathname.startsWith("/shorts/")) return url.pathname.split("/")[2] || "";
  } catch {
    return "";
  }
  return "";
}

function createIdentity() {
  return {
    strong: new Set(),
    titles: new Set(),
  };
}

function addUrlIdentity(identity, value) {
  const normalizedUrl = normalizeUrl(value);
  if (normalizedUrl) identity.strong.add(`url:${normalizedUrl}`);
  const youtubeId = extractYoutubeId(value);
  if (youtubeId) identity.strong.add(`youtube:${youtubeId}`);
}

function addIdIdentity(identity, value) {
  const raw = text(value);
  if (!raw) return;
  identity.strong.add(`id:${raw}`);
  const youtubeId = extractYoutubeId(raw);
  if (youtubeId) identity.strong.add(`youtube:${youtubeId}`);
  addUrlIdentity(identity, raw);
}

function addTitleIdentity(identity, value) {
  const title = normalizeTitle(value);
  if (title) identity.titles.add(title);
}

function buildVideoIdentity(video) {
  const identity = createIdentity();
  addIdIdentity(identity, video?.id);
  addIdIdentity(identity, video?.key);
  addUrlIdentity(identity, video?.url);
  addTitleIdentity(identity, video?.title);
  return identity;
}

function buildTalkIdentity(talk) {
  const identity = createIdentity();
  addIdIdentity(identity, talk?.videoId);
  addUrlIdentity(identity, talk?.videoUrl);
  addTitleIdentity(identity, talk?.videoTitle);

  const subsections = Array.isArray(talk?.subsections) ? talk.subsections : [];
  subsections.forEach((subsection) => {
    addIdIdentity(identity, subsection?.videoId);
    addUrlIdentity(identity, subsection?.videoUrl);
    addTitleIdentity(identity, subsection?.videoTitle);
  });
  return identity;
}

function hasIntersection(left, right) {
  for (const value of left) {
    if (right.has(value)) return true;
  }
  return false;
}

export function scoreTalkVideoMatch(talk, video) {
  const talkIdentity = buildTalkIdentity(talk);
  const videoIdentity = buildVideoIdentity(video);
  if (hasIntersection(talkIdentity.strong, videoIdentity.strong)) return 2;
  if (hasIntersection(talkIdentity.titles, videoIdentity.titles)) return 1;
  return 0;
}

export function findTalksForVideo(video, talks) {
  if (!video || !Array.isArray(talks)) return [];
  return talks.filter((talk) => scoreTalkVideoMatch(talk, video) > 0);
}

export function findVideosForTalk(talk, videos) {
  if (!talk || !Array.isArray(videos)) return [];
  return videos
    .map((video) => ({ video, score: scoreTalkVideoMatch(talk, video) }))
    .filter((item) => item.score > 0)
    .sort((left, right) => right.score - left.score)
    .map((item) => item.video);
}
