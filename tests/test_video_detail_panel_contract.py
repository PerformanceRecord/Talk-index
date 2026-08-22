import unittest
from pathlib import Path


class VideoDetailPanelContractTests(unittest.TestCase):
    def test_video_detail_uses_separate_player_and_heading_panes(self):
        html = Path('index.html').read_text(encoding='utf-8')
        styles = Path('styles.css').read_text(encoding='utf-8')
        app_js = Path('app.js').read_text(encoding='utf-8')

        self.assertIn('id="video-detail-panel"', html)
        self.assertIn('id="video-detail-player"', html)
        self.assertIn('id="video-detail-content"', html)
        self.assertIn('grid-template-columns: minmax(360px, 1fr) minmax(380px, 0.9fr);', styles)
        self.assertIn('.video-detail-content {', styles)
        self.assertIn('height: auto;', styles)
        self.assertIn('overflow: visible;', styles)
        self.assertIn('body.has-mobile-video-detail', styles)
        self.assertIn('refs.videoDetailContent.appendChild(detail);', app_js)
        self.assertIn('card.append(summary);', app_js)
        self.assertNotIn('card.append(summary, detail);', app_js)

    def test_video_selection_keeps_only_one_detail_open(self):
        app_js = Path('app.js').read_text(encoding='utf-8')

        self.assertIn('state.openVideoKeys = new Set([video.key]);', app_js)
        self.assertIn('refs.toggleAll.textContent = "詳細を閉じる";', app_js)


if __name__ == '__main__':
    unittest.main()
