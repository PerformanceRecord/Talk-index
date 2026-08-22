import unittest
from pathlib import Path


class LayoutFrontendContractTests(unittest.TestCase):
    def test_search_toolbar_is_above_scrollable_results(self):
        html = Path('index.html').read_text(encoding='utf-8')
        styles = Path('styles.css').read_text(encoding='utf-8')

        self.assertLess(html.index('class="left-toolbar"'), html.index('id="results"'))
        self.assertIn('.left-pane > .results {', styles)
        self.assertIn('overflow-y: auto;', styles)
        self.assertNotIn('bottom: 12px;', styles)


if __name__ == '__main__':
    unittest.main()
