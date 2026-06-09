"""Convert Sokoban standard format to our Level format and solve.

Handles:
- Standard .sok files (multiple levels separated by blank lines)
- Single-level .txt files with blank lines between rows
- Undirected matching: tries all box-goal permutations for standard Sokoban
"""
from __future__ import annotations
import os, re, time
from itertools import permutations
from planner.grid import Level, parse_level
from planner.solver import solve, clear_heuristic_cache

SOKOBAN_LEVEL_CHARS = set('# @ $. *+&B')


def _is_level_line(line: str) -> bool:
    """Check if a line looks like part of a Sokoban level.

    A level line must contain ONLY Sokoban characters (#, space, @, $, ., *, +, &, B).
    No other alphanumeric or punctuation characters are allowed.
    """
    stripped = line.rstrip()
    if not stripped:
        return False
    # Every character must be a valid Sokoban character
    for ch in stripped:
        if ch not in SOKOBAN_LEVEL_CHARS:
            return False
    # Must contain at least one definitive char (# @ $ . * + & B)
    return any(ch in '@$.*+&B' for ch in stripped) or '#' in stripped


def _parse_single_level(text: str, level_id: int = 9999, name: str = "Imported") -> Level | None:
    """Parse a single Sokoban level from text into a Level."""
    raw_lines = text.split('\n')
    # Filter to only level-like lines (skip blanks and comments)
    lines = []
    for line in raw_lines:
        line = line.rstrip('\r')
        if _is_level_line(line):
            lines.append(line)
    if not lines:
        return None

    # Strip leading/trailing whitespace-only lines
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    if len(lines) < 3:
        return None

    max_width = max(len(line) for line in lines)
    if max_width < 3:
        return None

    padded = [line.ljust(max_width) for line in lines]
    rows = len(padded)
    cols = max_width

    grid = []
    box_positions = []
    goal_positions = []
    bomb_count = 0
    has_player = False

    for r in range(rows):
        row_tokens = []
        for c in range(cols):
            ch = padded[r][c]
            if ch == '#':
                row_tokens.append('#')
            elif ch in ('@', '&'):
                row_tokens.append('P')
                has_player = True
            elif ch == '$':
                box_positions.append((r, c))
                row_tokens.append(f'B{len(box_positions)}')
            elif ch == '.':
                goal_positions.append((r, c))
                row_tokens.append(f'T{len(goal_positions)}')
            elif ch == '*':
                # Box on goal
                box_positions.append((r, c))
                goal_positions.append((r, c))
                row_tokens.append(f'B{len(box_positions)}')
            elif ch == '+':
                # Player on goal
                row_tokens.append('P')
                has_player = True
                goal_positions.append((r, c))
            elif ch == 'X':
                bomb_count += 1
                row_tokens.append('X')
            elif ch == 'B':
                # Alternate box notation (used in some level files)
                box_positions.append((r, c))
                row_tokens.append(f'B{len(box_positions)}')
            else:
                row_tokens.append('.')
        grid.append(tuple(row_tokens))

    if not has_player or not box_positions or not goal_positions:
        return None
    if len(box_positions) != len(goal_positions):
        return None

    category = 3 if bomb_count > 0 else 2
    return Level(
        level_id=level_id,
        name=name,
        rows=tuple(grid),
        category=category,
        use_vision=False,
        use_deadlock=True,
        boxes_vanish_on_goal=True,
        requires_approach_recognition=False,
        hp_start=20,
        description=f"{rows}x{cols}, {len(box_positions)} boxes, {bomb_count} bombs",
    )


def parse_sok_file(text: str) -> list[tuple[str, Level]]:
    """Parse a .sok file which may contain multiple levels.

    .sok format uses different conventions:
    - '::' prefix = metadata/comment
    - Level rows contain only Sokoban chars (# @ $ . * + & space)
    - Level rows within a level may be separated by single blank lines
    - Different levels are separated by 2+ blank lines or title lines
    """
    levels = []
    blocks = []
    current_block = []
    consecutive_blanks = 0

    for line in text.split('\n'):
        line = line.rstrip('\r')
        # Skip :: comment lines
        if line.startswith('::'):
            if current_block:
                blocks.append(current_block)
                current_block = []
            consecutive_blanks = 0
            continue
        # Skip title lines (contain quotes, commas, or alphanumeric beyond level chars)
        stripped = line.rstrip()
        if stripped and not _is_level_line(stripped):
            # This is a non-level, non-blank line (title, description, etc.)
            if current_block:
                blocks.append(current_block)
                current_block = []
            consecutive_blanks = 0
            continue
        # Blank line
        if not stripped:
            consecutive_blanks += 1
            continue
        # Level line
        if consecutive_blanks >= 2 and current_block:
            # 2+ blank lines = level separator
            blocks.append(current_block)
            current_block = []
        consecutive_blanks = 0
        current_block.append(stripped)

    if current_block:
        blocks.append(current_block)

    for idx, block in enumerate(blocks):
        if len(block) < 3:
            continue
        text_block = '\n'.join(block)
        level = _parse_single_level(text_block, level_id=9000 + idx + 1, name=f"SokImport-{idx + 1}")
        if level is not None:
            levels.append((f"sok_{idx + 1}", level))
    return levels


def load_sokoban_dir(directory: str) -> list[tuple[str, Level]]:
    """Load all Sokoban level files from a directory."""
    levels = []
    idx = 0
    for fname in sorted(os.listdir(directory)):
        fpath = os.path.join(directory, fname)
        if not os.path.isfile(fpath):
            continue
        with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()

        if fname.endswith('.sok'):
            parsed = parse_sok_file(text)
            for pname, level in parsed:
                idx += 1
                real_level = Level(
                    level_id=8000 + idx,
                    name=f"{fname}:{level.name}",
                    rows=level.rows,
                    category=level.category,
                    use_vision=False,
                    use_deadlock=True,
                    boxes_vanish_on_goal=True,
                    requires_approach_recognition=False,
                    hp_start=20,
                    description=level.description,
                )
                levels.append((f"{fname}:{pname}", real_level))
        else:
            idx += 1
            level = _parse_single_level(text, level_id=8000 + idx, name=fname)
            if level is not None:
                levels.append((fname, level))
    return levels


def try_solve_with_matching(level: Level, max_expanded: int = 500_000):
    """Try to solve a level, trying different box-goal matchings.

    In standard Sokoban, any box can go to any goal. Our solver requires
    B_i matched to T_i. We try the direct matching first, then permutations.
    """
    # First try direct matching
    try:
        board = parse_level(level)
        clear_heuristic_cache()
        result = solve(board, max_expanded=max_expanded)
        if result.solved:
            return True, result, "direct"
    except Exception:
        pass

    # Collect box and goal positions
    box_positions = []
    goal_positions = []
    for r in range(len(level.rows)):
        for c in range(len(level.rows[r])):
            tok = level.rows[r][c]
            if tok.startswith('B'):
                box_positions.append((r, c, int(tok[1:])))
            elif tok.startswith('T'):
                goal_positions.append((r, c, int(tok[1:])))

    n = len(box_positions)
    if n != len(goal_positions) or n > 4:
        return False, "Too many boxes for permutation matching", "failed"

    # Try permutations of goal assignments
    best_result = None
    for perm in permutations(range(n)):
        if perm == tuple(range(n)):
            continue  # already tried direct

        # Build new rows with remapped goal IDs
        new_rows = []
        goal_map = {i + 1: perm[i] + 1 for i in range(n)}
        for row in level.rows:
            new_row = []
            for tok in row:
                if tok.startswith('T'):
                    old_id = int(tok[1:])
                    new_id = goal_map.get(old_id, old_id)
                    new_row.append(f'T{new_id}')
                else:
                    new_row.append(tok)
            new_rows.append(tuple(new_row))

        new_level = Level(
            level_id=level.level_id,
            name=level.name,
            rows=tuple(new_rows),
            category=level.category,
            use_vision=False,
            use_deadlock=True,
            boxes_vanish_on_goal=True,
            requires_approach_recognition=False,
            hp_start=20,
            description=level.description,
        )

        try:
            board = parse_level(new_level)
            clear_heuristic_cache()
            result = solve(board, max_expanded=max_expanded)
            if result.solved:
                return True, result, f"perm={perm}"
            if best_result is None or (hasattr(result, 'expanded') and result.expanded > getattr(best_result, 'expanded', 0)):
                best_result = result
        except Exception:
            pass

    return False, best_result or "No solution", "all_perms"
