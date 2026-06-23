"""Import a small verified subset of DeepMind Boxoban hard maps.

The source format is classic Sokoban 10x10 (`#`, `$`, `.`, `@`). This project
uses fixed-number 12x16 maps, so the importer pads maps to 12x16 and assigns
box/target IDs by reading order. Because fixed IDs are stricter than classic
Sokoban's "any box to any target" rule, the importer solves each converted map
and writes only maps that pass the project solver.
"""
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from planner.grid import load_text_map, parse_level
from planner.solver import clear_heuristic_cache, solve

SOURCE_URL = "https://raw.githubusercontent.com/google-deepmind/boxoban-levels/master/hard/000.txt"


def parse_boxoban_levels(text: str) -> list[tuple[int, list[str]]]:
    levels: list[tuple[int, list[str]]] = []
    current: list[str] = []
    level_id = 0
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith(";"):
            if current:
                levels.append((level_id, current))
                current = []
            level_id = int(line[1:].strip())
        elif line.strip():
            current.append(line)
    if current:
        levels.append((level_id, current))
    return levels


def convert_level(level_id: int, rows: list[str]) -> str | None:
    boxes: list[tuple[int, int]] = []
    goals: list[tuple[int, int]] = []
    player: tuple[int, int] | None = None

    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "$":
                boxes.append((r, c))
            elif ch == ".":
                goals.append((r, c))
            elif ch == "@":
                player = (r, c)
            elif ch == "*":
                boxes.append((r, c))
                goals.append((r, c))
            elif ch == "+":
                player = (r, c)
                goals.append((r, c))

    if player is None or not boxes or len(boxes) != len(goals) or len(boxes) > 4:
        return None
    if len(rows) > 10 or max(len(row) for row in rows) > 14:
        return None

    grid = [["#"] * 16 for _ in range(12)]
    for r in range(1, 11):
        for c in range(1, 15):
            grid[r][c] = "."

    offset_r, offset_c = 1, 3
    for r, row in enumerate(rows):
        for c, ch in enumerate(row):
            if ch == "#":
                grid[r + offset_r][c + offset_c] = "#"

    pr, pc = player
    grid[pr + offset_r][pc + offset_c] = "P"
    for i, (r, c) in enumerate(sorted(boxes), 1):
        grid[r + offset_r][c + offset_c] = f"B{i}"
    for i, (r, c) in enumerate(sorted(goals), 1):
        rr, cc = r + offset_r, c + offset_c
        if grid[rr][cc] != ".":
            return None
        grid[rr][cc] = f"T{i}"

    lines = [
        f"// Source: DeepMind Boxoban hard/000.txt ; {level_id}",
        "// Converted to fixed-number 12x16 format; verified solved by project solver.",
        f"rows=12 cols=16 level={5000 + level_id} heading=R recognition=false scanBombs=false allowBombPush=false",
    ]
    lines.extend(" ".join(row) for row in grid)
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5, help="number of solved maps to write")
    parser.add_argument("--scan", type=int, default=120, help="number of source maps to scan")
    parser.add_argument("--max-expanded", type=int, default=80000)
    parser.add_argument(
        "--min-expanded",
        type=int,
        default=0,
        help="only write solved maps whose search expanded at least this many states",
    )
    parser.add_argument("--out", default="hard_maps")
    args = parser.parse_args()

    text = urllib.request.urlopen(SOURCE_URL, timeout=30).read().decode("utf-8")
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    tmp = out_dir / ".candidate.tmp"
    for level_id, rows in parse_boxoban_levels(text)[: args.scan]:
        converted = convert_level(level_id, rows)
        if converted is None:
            continue
        tmp.write_text(converted, encoding="utf-8")
        level = load_text_map(tmp)
        board = parse_level(level)
        clear_heuristic_cache()
        result = solve(board, max_expanded=args.max_expanded)
        if not result.solved:
            continue
        if result.expanded < args.min_expanded:
            continue
        target = out_dir / f"boxoban_hard_000_{level_id:03d}.txt"
        target.write_text(converted, encoding="utf-8")
        print(f"wrote {target} cost={result.total_cost} expanded={result.expanded}")
        written += 1
        if written >= args.limit:
            break

    tmp.unlink(missing_ok=True)
    print(f"written={written}")
    return 0 if written else 1


if __name__ == "__main__":
    raise SystemExit(main())
