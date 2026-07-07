"""Import smoke tests for the project skeleton."""

import unittest


class ImportTests(unittest.TestCase):
    def test_core_modules_import(self) -> None:
        import mvr_player
        from mvr_player import app
        from mvr_player import converter
        from mvr_player import ffmpeg_utils
        from mvr_player import main
        from mvr_player import player
        from mvr_player import settings
        from mvr_player import ui
        from mvr_player import utils

        self.assertTrue(mvr_player.__version__)
        self.assertEqual(settings.APP_NAME, "MVR Player")
        self.assertTrue(app)
        self.assertTrue(converter)
        self.assertTrue(ffmpeg_utils)
        self.assertTrue(main)
        self.assertTrue(player)
        self.assertTrue(ui)
        self.assertTrue(utils)


if __name__ == "__main__":
    unittest.main()
