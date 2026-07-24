import unittest
from pathlib import Path


class FavoritesFrontendContractTests(unittest.TestCase):
    def test_theme_exploration_replaces_random_and_aggregate_shelves(self):
        html = Path('index.html').read_text(encoding='utf-8')
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('テーマ探索', html)
        self.assertIn('テーマを探す', html)
        self.assertNotIn('ランダムおすすめ', html)
        self.assertIn('function renderExplorationHub', app_js)
        self.assertIn('function openTalkForExploration', app_js)
        self.assertIn('function createExplorationTrail', app_js)
        self.assertNotIn('function createFavoritePanel', app_js)
        self.assertNotIn('function pickRandomSection', app_js)

    def test_related_theme_keeps_talk_context(self):
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('openTalkForExploration(item.id, sourceTalkKey);', app_js)
        self.assertIn('state.viewMode = "talk";', app_js)
        self.assertIn('state.focusedTalkKeys = new Set([talk.key]);', app_js)
        self.assertIn('title.textContent = "次に掘るテーマ";', app_js)

    def test_video_and_talk_views_have_cross_navigation(self):
        html = Path('index.html').read_text(encoding='utf-8')
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('動画から探す', html)
        self.assertIn('function openTalkScreenForVideo', app_js)
        self.assertIn('function openVideoScreenForTalk', app_js)
        self.assertIn('収録トークを見る', app_js)
        self.assertIn('関連動画を見る', app_js)
        self.assertIn('動画へ戻る', app_js)
        self.assertIn('トークへ戻る', app_js)

    def test_search_is_cross_mode(self):
        html = Path('index.html').read_text(encoding='utf-8')
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('動画タイトル・トークテーマを横断検索', html)
        self.assertIn('function renderSearchOverview', app_js)
        self.assertIn('動画タイトル・トークテーマから検索', app_js)
        self.assertIn('if (includesKeyword(video.title, search.keyword)) return true;', app_js)
        self.assertIn('const titleMatched = includesKeyword(getTalkVideoTitle(talk), search.keyword);', app_js)
        self.assertIn('loadSearchIndexIfNeeded()', app_js)
        self.assertIn('loadTalksIfNeeded()', app_js)

    def test_html_does_not_render_recent_recommendations_feed(self):
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('fetchFavoritesAggregate("recentUpload")', app_js)
        self.assertNotIn('fetchFavoritesAggregate("recent")', app_js)

    def test_video_vote_payload_uses_video_context_metadata(self):
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('function resolveVideoFavoriteContext', app_js)
        self.assertIn('sec?.headingTitle || sec?.heading_title || sec?.name || sec?.title', app_js)
        self.assertIn('headingId: canonicalHeadingId', app_js)
        self.assertIn('videoId,', app_js)
        self.assertIn('videoTitle,', app_js)
        self.assertIn('sourceVideoUrl,', app_js)
        self.assertIn('sourceVideoTitle,', app_js)
        self.assertIn('publishedAt: canonicalPublishedAt', app_js)
        self.assertIn('videoDate: canonicalVideoDate', app_js)
        self.assertIn('headingStart,', app_js)
        self.assertIn('sourceMode: isVideoMode ? "video" : state.viewMode', app_js)

    def test_video_vote_fail_closed_guard_exists(self):
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('video mode vote skipped due to missing metadata', app_js)
        self.assertIn('missing.push("videoId")', app_js)
        self.assertIn('missing.push("headingTitle")', app_js)
        self.assertIn('missing.push("sourceVideoUrl_or_publishedAt")', app_js)
        self.assertIn('state.unsyncedFavoriteHeadingIds.add(normalized);', app_js)

    def test_vote_marked_only_on_success(self):
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('await sendFavoriteVote({', app_js)
        self.assertIn('state.alreadyVotedHeadingIds.add(normalized);', app_js)
        self.assertIn('if (state.alreadyVotedHeadingIds.has(normalized) && !state.unsyncedFavoriteHeadingIds.has(normalized)) {', app_js)

    def test_toggle_off_preserves_already_voted_when_sent_before(self):
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('const hasSuccessfulVote = state.alreadyVotedHeadingIds.has(normalized);', app_js)
        self.assertIn('if (!hasSuccessfulVote) {', app_js)
        self.assertIn('state.alreadyVotedHeadingIds.delete(normalized);', app_js)

    def test_toggle_off_on_for_already_voted_does_not_resend(self):
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('if (state.alreadyVotedHeadingIds.has(normalized)) {', app_js)
        self.assertIn('state.unsyncedFavoriteHeadingIds.delete(normalized);', app_js)
        self.assertIn('await syncFavoriteVote(normalized, sourceTalk);', app_js)

    def test_toggle_off_for_unsent_heading_clears_unsynced_and_already_voted(self):
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('state.unsyncedFavoriteHeadingIds.delete(normalized);', app_js)
        self.assertIn('if (!hasSuccessfulVote) {', app_js)
        self.assertIn('state.alreadyVotedHeadingIds.delete(normalized);', app_js)

    def test_fail_closed_failure_keeps_unsynced_without_already_voted(self):
        app_js = Path('app.js').read_text(encoding='utf-8')
        self.assertIn('state.unsyncedFavoriteHeadingIds.add(normalized);', app_js)
        self.assertIn('state.alreadyVotedHeadingIds.add(normalized);', app_js)
        self.assertIn('} catch (error) {', app_js)


if __name__ == '__main__':
    unittest.main()
