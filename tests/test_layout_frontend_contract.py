import unittest
from pathlib import Path


class LayoutFrontendContractTests(unittest.TestCase):
    def test_page_reserves_space_for_fixed_control_menu(self):
        styles = Path('styles.css').read_text(encoding='utf-8')

        self.assertIn('--control-menu-reserved-space: 156px;', styles)
        self.assertIn(
            'padding: 12px 12px calc(var(--control-menu-reserved-space) + env(safe-area-inset-bottom));',
            styles,
        )


if __name__ == '__main__':
    unittest.main()
