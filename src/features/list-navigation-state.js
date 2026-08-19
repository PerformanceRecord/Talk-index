function cloneOptionalSet(value) {
  return value instanceof Set ? new Set(value) : null;
}

export function captureVideoListState(state, scrollY = 0) {
  return {
    search: String(state?.search || ""),
    focusedVideoKeys: cloneOptionalSet(state?.focusedVideoKeys),
    openVideoKeys: cloneOptionalSet(state?.openVideoKeys) || new Set(),
    isVideoExpandLock: Boolean(state?.isVideoExpandLock),
    scrollY: Math.max(0, Number(scrollY) || 0),
  };
}

export function restoreVideoListState(state, snapshot) {
  if (!state || !snapshot) return 0;
  state.search = snapshot.search;
  state.focusedVideoKeys = cloneOptionalSet(snapshot.focusedVideoKeys);
  state.openVideoKeys = cloneOptionalSet(snapshot.openVideoKeys) || new Set();
  state.isVideoExpandLock = snapshot.isVideoExpandLock;
  // Restoring the previous auto-collapse anchor would make the programmatic
  // scroll trigger a render that changes the list height and causes a jump.
  state.videoAutoCollapseAnchor = null;
  return snapshot.scrollY;
}
