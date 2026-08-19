import assert from "node:assert/strict";
import test from "node:test";

import {
  captureVideoListState,
  restoreVideoListState,
} from "../src/features/list-navigation-state.js";

test("動画一覧の表示状態とスクロール位置を復元できる", () => {
  const state = {
    search: "雑談",
    focusedVideoKeys: null,
    openVideoKeys: new Set(["video-a", "video-b"]),
    isVideoExpandLock: true,
    videoAutoCollapseAnchor: { key: "video-b", index: 4 },
  };
  const snapshot = captureVideoListState(state, 1840);

  state.search = "";
  state.focusedVideoKeys = new Set(["video-a"]);
  state.openVideoKeys.clear();
  state.isVideoExpandLock = false;
  state.videoAutoCollapseAnchor = null;

  assert.equal(restoreVideoListState(state, snapshot), 1840);
  assert.equal(state.search, "雑談");
  assert.equal(state.focusedVideoKeys, null);
  assert.deepEqual([...state.openVideoKeys], ["video-a", "video-b"]);
  assert.equal(state.isVideoExpandLock, true);
  assert.equal(state.videoAutoCollapseAnchor, null);
});

test("保存後に元のSetを変更してもスナップショットへ影響しない", () => {
  const state = {
    search: "",
    focusedVideoKeys: new Set(["video-a"]),
    openVideoKeys: new Set(["video-a"]),
  };
  const snapshot = captureVideoListState(state, -20);
  state.focusedVideoKeys.add("video-b");
  state.openVideoKeys.clear();

  assert.deepEqual([...snapshot.focusedVideoKeys], ["video-a"]);
  assert.deepEqual([...snapshot.openVideoKeys], ["video-a"]);
  assert.equal(snapshot.scrollY, 0);
});
