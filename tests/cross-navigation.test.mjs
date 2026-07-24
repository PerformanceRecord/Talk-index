import assert from "node:assert/strict";
import test from "node:test";

import {
  findTalksForVideo,
  findVideosForTalk,
  scoreTalkVideoMatch,
} from "../src/features/cross-navigation.js";

const videos = [
  {
    key: "AAAAAAAAAAA",
    id: "AAAAAAAAAAA",
    title: "夏の旅行を振り返る雑談",
    url: "https://www.youtube.com/watch?v=AAAAAAAAAAA",
  },
  {
    key: "BBBBBBBBBBB",
    id: "BBBBBBBBBBB",
    title: "配信機材について",
    url: "https://youtu.be/BBBBBBBBBBB",
  },
];

test("URL形式が違ってもYouTube IDで動画とトークを対応付ける", () => {
  const talk = {
    key: "北海道旅行",
    subsections: [{
      name: "食べたもの",
      videoTitle: "夏の旅行を振り返る雑談",
      videoUrl: "https://youtu.be/AAAAAAAAAAA?t=120",
    }],
  };

  assert.equal(scoreTalkVideoMatch(talk, videos[0]), 2);
  assert.deepEqual(findVideosForTalk(talk, videos).map((video) => video.key), ["AAAAAAAAAAA"]);
});

test("動画に含まれる複数のトークテーマを返す", () => {
  const talks = [
    {
      key: "北海道旅行",
      subsections: [{ videoUrl: "https://youtu.be/AAAAAAAAAAA" }],
    },
    {
      key: "旅行の食事",
      subsections: [{ videoUrl: "https://www.youtube.com/watch?v=AAAAAAAAAAA&t=300" }],
    },
    {
      key: "配信機材",
      subsections: [{ videoUrl: "https://youtu.be/BBBBBBBBBBB" }],
    },
  ];

  assert.deepEqual(
    findTalksForVideo(videos[0], talks).map((talk) => talk.key),
    ["北海道旅行", "旅行の食事"],
  );
});

test("URLがない旧データは正規化した動画タイトルで対応付ける", () => {
  const talk = {
    key: "機材",
    subsections: [{ videoTitle: "  配信機材について " }],
  };

  assert.equal(scoreTalkVideoMatch(talk, videos[1]), 1);
});
