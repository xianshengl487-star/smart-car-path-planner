from __future__ import annotations

import unittest
from pathlib import Path

from planner.grid import parse_level
from planner.vision import recognize_contest_image


def _contest_pngs() -> list[Path]:
    for child in Path.cwd().iterdir():
        if child.is_dir() and child.name != "outputs":
            pngs = sorted(child.glob("*.png"))
            if pngs:
                return pngs
    return []


class ContestFolderRecognitionTests(unittest.TestCase):
    def test_contest_pngs_recognize_as_fixed_16x12_maps(self) -> None:
        pngs = _contest_pngs()
        if not pngs:
            self.skipTest("No contest PNG folder found")

        for image_path in pngs:
            with self.subTest(image=image_path.name):
                level = recognize_contest_image(image_path)
                board = parse_level(level)
                self.assertEqual((board.rows, board.cols), (12, 16))
                self.assertEqual(board.player, (5, 1))
                self.assertEqual(len(board.boxes), len(board.goals))
                self.assertGreaterEqual(len(board.boxes), 1)
                self.assertTrue(level.requires_approach_recognition)
                self.assertTrue(level.boxes_vanish_on_goal)
