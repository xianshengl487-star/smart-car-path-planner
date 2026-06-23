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

    def test_no_duplicate_wall_layouts(self) -> None:
        """Wall-identical maps are poor benchmark coverage.

        Boxes still deliver to matching numbered targets; this check only keeps
        the external-map set varied enough to exercise different corridors.
        """
        files = _hard_map_files()
        if not files:
            self.skipTest("No .txt maps in hard_maps/")
        seen: dict[frozenset, str] = {}
        for path in files:
            level = load_text_map(path)
            board = parse_level(level)
            key = frozenset(board.walls)
            if key in seen:
                self.fail(
                    f"Duplicate wall layout: {path.name} matches {seen[key]}"
                )
            seen[key] = path.name

    def test_no_duplicate_box_configurations(self) -> None:
        """Two maps with the same walls and box starts are likely duplicates.

        Target numbering remains fixed (B1 -> T1), so this catches duplicate
        imports without weakening the numbered-box rule.
        """
        files = _hard_map_files()
        if not files:
            self.skipTest("No .txt maps in hard_maps/")
        seen: dict[tuple, str] = {}
        for path in files:
            level = load_text_map(path)
            board = parse_level(level)
            key = (frozenset(board.walls), frozenset(board.boxes.values()))
            if key in seen:
                self.fail(
                    f"Duplicate box config: {path.name} matches {seen[key]}"
                )
            seen[key] = path.name

    def test_all_hard_maps_are_nontrivial(self) -> None:
        """Flag maps solvable in <500 expanded as too easy for hard_maps/.
        This is a soft check — it warns but does not fail, since some
        easy maps may be useful as sanity-check anchors."""
        files = _hard_map_files()
        if not files:
            self.skipTest("No .txt maps in hard_maps/")
        easy_maps = []
        for path in files:
            level = load_text_map(path)
            board = parse_level(level)
            clear_heuristic_cache()
            result = solve(board, max_expanded=120_000)
            if result.solved and result.expanded < 500:
                easy_maps.append(
                    f"{path.name} (expanded={result.expanded})"
                )
        if easy_maps:
            # Soft warning — does not fail the test
            import sys
            print(
                f"\nWARNING: {len(easy_maps)} trivial map(s) in hard_maps/ "
                f"(expanded < 500): {easy_maps}",
                file=sys.stderr,
            )
