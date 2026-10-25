"""Mauszeiger-Ausblenden (CURSOR_HIDE_SECONDS): Parsing + Injektion ins HTML.

Der Samsung-TV-Browser zeigt seinen Zeiger dauerhaft mitten im Plan. Die Seite
startet daher mit `cursor-hidden` auf <html> (sonst blitzt der Zeiger bei jedem
60-s-Reload auf); das JS blendet ihn bei Bewegung ein, nach N s wieder aus.
"""
import unittest

from scripts.fetch_untis import parse_cursor_hide_seconds
from tests.test_generate_html_golden import _FROZEN, _fixture, fu


class TestParseCursorHideSeconds(unittest.TestCase):
    def test_default_wenn_leer(self):
        self.assertEqual(parse_cursor_hide_seconds({}), 2)
        self.assertEqual(parse_cursor_hide_seconds({"CURSOR_HIDE_SECONDS": ""}), 2)

    def test_gueltiger_wert(self):
        self.assertEqual(parse_cursor_hide_seconds({"CURSOR_HIDE_SECONDS": "5"}), 5)

    def test_null_heisst_aus(self):
        self.assertEqual(parse_cursor_hide_seconds({"CURSOR_HIDE_SECONDS": "0"}), 0)

    def test_muell_und_negativ_fallen_auf_default(self):
        self.assertEqual(parse_cursor_hide_seconds({"CURSOR_HIDE_SECONDS": "abc"}), 2)
        self.assertEqual(parse_cursor_hide_seconds({"CURSOR_HIDE_SECONDS": "-3"}), 2)
        self.assertEqual(parse_cursor_hide_seconds({"CURSOR_HIDE_SECONDS": "1.5"}), 2)

    def test_inline_kommentar_wird_ignoriert(self):
        self.assertEqual(
            parse_cursor_hide_seconds({"CURSOR_HIDE_SECONDS": "3   # sekunden"}), 3)


class TestCursorHideInjection(unittest.TestCase):
    def setUp(self):
        self._orig_now = fu.now_local
        fu.now_local = lambda: _FROZEN

    def tearDown(self):
        fu.now_local = self._orig_now

    def _render(self, config):
        fx = _fixture()
        settings = fu.DisplaySettings.from_config(config)
        return fu.generate_html(
            fx["groups_today"], fx["groups_tomorrow"],
            fx["today_date"], fx["tomorrow_date"],
            fx["teacher_lookup"], fx["indicator"],
            import_time=fx["import_time"], settings=settings,
        )

    def test_startet_ausgeblendet(self):
        html = self._render({"CURSOR_HIDE_SECONDS": "2"})
        self.assertIn('<html lang="de" data-theme="dark" class="cursor-hidden">', html)
        self.assertIn("<script>window.CURSOR_HIDE_SECONDS = 2;</script>", html)

    def test_null_ohne_klasse(self):
        html = self._render({"CURSOR_HIDE_SECONDS": "0"})
        self.assertNotIn("cursor-hidden", html)
        self.assertIn("<script>window.CURSOR_HIDE_SECONDS = 0;</script>", html)


if __name__ == "__main__":
    unittest.main()
