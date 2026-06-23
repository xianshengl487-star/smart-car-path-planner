"""Tests for external hard maps in the hard_maps/ directory.

Discovers all *.txt files in hard_maps/, loads them via load_text_map(),
validates dimensions, and optionally solves each with a generous budget.
Skips gracefully if no maps are present.
"""
from __future__ import annotations

import unittest
from pathlib import Path

from planner.grid import Level, load_text_map, parse_level
from planner.solver import clear_heuristic_cache, solve

ROOT = Path(__file__).resolve().parents[1]
HARD_MAPS_DIR = ROOT / "hard_maps"


def _hard_map_files() -> list[Path]:
    if not HARD_MAPS_DIR.is_dir():
        return []
    return sorted(HARD_MAPS_DIR.glob("*.txt"))


class HardMapLoadTests(unittest.TestCase):
    """Validate that every .txt in hard_maps/ parses into a valid Level."""

    def test_hard_maps_directory_exists(self) -> None:
        self.assertTrue(HARD_MAPS_DIR.is_dir(), f"Directory missing: {HARD_MAPS_DIR}")

    def test_all_hard_maps_parse(self) -> None:
        files = _hard_map_files()
        if not files:
            self.skipTest("No .txt maps in hard_maps/")
        for path in files:
            with self.subTest(file=path.name):
                level = load_text_map(path)
                self.assertIsInstance(level, Level)
                self.assertGreaterEqual(level.level_id, 101)

    def test_all_hard_maps_have_12x16_grid(self) -> None:
        files = _hard_map_files()
        if not files:
            self.skipTest("No .txt maps in hard_maps/")
        for path in files:
            with self.subTest(file=path.name):
                level = load_text_map(path)
                board = parse_level(level)
                self.assertEqual(board.rows, 12)
                self.assertEqual(board.cols, 16)

    def test_all_hard_maps_have_player(self) -> None:
        files = _hard_map_files()
        if not files:
            self.skipTest("No .txt maps in hard_maps/")
        for path in files:
            with self.subTest(file=path.name):
                level = load_text_map(path)
                board = parse_level(level)
                self.assertIsNotNone(board.player)

    def test_all_hard_maps_have_boxes_and_goals(self) -> None:
        files = _hard_map_files()
        if not files:
            self.skipTest("No .txt maps in hard_maps/")
        for path in files:
            with self.subTest(file=path.name):
                level = load_text_map(path)
                board = parse_level(level)
                self.assertGreater(len(board.boxes), 0, f"{path.name}: no boxes")
                self.assertEqual(set(board.boxes), set(board.goals),
                                 f"{path.name}: box/goal id mismatch")

    def test_all_hard_maps_solve_with_generous_budget(self) -> None:
        files = _hard_map_files()
        if not files:
            self.skipTest("No .txt maps in hard_maps/")
        for path in files:
            with self.subTest(file=path.name):
                level = load_text_map(path)
                board = parse_level(level)
                clear_heuristic_cache()
                result = solve(board, max_expanded=120_000)
                self.assertTrue(result.solved, f"{path.name}: {result.message}")
