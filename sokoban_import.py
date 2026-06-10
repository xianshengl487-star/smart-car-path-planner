"""Convert Sokoban standard format to our Level format and solve.

Handles standard Sokoban notation:
# wall, space floor, @ player, $ box, . goal, * box-on-goal, + player-on-goal
Also handles custom variants: & player, B box, X bomb
"""
from __future__ import annotations
import os, time
from itertools import permutations
from planner.grid import Level, parse_level
from planner.solver import solve, clear_heuristic_cache


SOKOBAN_LEVEL_CHARS = set('# @ $. *+&BX')


def _is_level_line(line: str) -> bool:
    """A valid level line contains ONLY Sokoban chars and has at least one #."""
    stripped = line.rstrip()
    if not stripped:
        return False
    for ch in stripped:
        if ch not in SOKOBAN_LEVEL_CHARS:
            return False
    return '#' in stripped


def _parse_single_level(text: str, level_id: int = 9999, name: str = "Imported") -> Level | None:
    """Parse a single Sokoban level from text. Returns Level or None."""
    lines = [line.rstrip() for line in text.split('\n') if _is_level_line(line)]
    if len(lines) < 3:
        return None

    max_w = max(len(l) for l in lines)
    if max_w < 3:
        return None

    padded = [l.ljust(max_w) for l in lines]
    rows = len(padded)
    cols = max_w

    # First pass: collect positions and determine grid structure
    boxes = []
    goals = []
    player_pos = None
    bombs = []
    wall_cells = set()

    for r in range(rows):
        for c in range(cols):
            ch = padded[r][c]
            if ch == '#':
                wall_cells.add((r, c))
            elif ch in ('@', '&'):
                player_pos = (r, c)
            elif ch in ('$', 'B'):
                boxes.append((r, c))
            elif ch == '.':
                goals.append((r, c))
            elif ch == '*':
                # Box on goal: box already delivered in vanish mode
                goals.append((r, c))
                # Don't add to boxes - it's pre-delivered
            elif ch == '+':
                player_pos = (r, c)
                goals.append((r, c))
            elif ch == 'X':
                bombs.append((r, c))

    if player_pos is None or not goals:
        return None

    # Flood fill from edges to find "outside" cells (cells reachable from border without crossing walls)
    outside = set()
    queue = []
    for c in range(cols):
        for r in [0, rows - 1]:
            if (r, c) not in wall_cells:
                queue.append((r, c))
                outside.add((r, c))
    for r in range(rows):
        for c in [0, cols - 1]:
            if (r, c) not in wall_cells:
                queue.append((r, c))
                outside.add((r, c))
    while queue:
        cr, cc = queue.pop()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = cr + dr, cc + dc
            if 0 <= nr < rows and 0 <= nc < cols and (nr, nc) not in outside and (nr, nc) not in wall_cells:
                outside.add((nr, nc))
                queue.append((nr, nc))

    # Remove outside cells from boxes and goals
    boxes = [(r, c) for r, c in boxes if (r, c) not in outside]
    goals = [(r, c) for r, c in goals if (r, c) not in outside]

    if not boxes or not goals:
        return None

    # Build grid
    grid = [['.' for _ in range(cols)] for _ in range(rows)]
    for r, c in wall_cells:
        grid[r][c] = '#'
    for r, c in outside:
        grid[r][c] = '#'
    pr, pc = player_pos
    grid[pr][pc] = 'P'
    for r, c in bombs:
        if (r, c) not in outside:
            grid[r][c] = 'X'

    # Place boxes and goals with matched IDs
    n = min(len(boxes), len(goals))
    if n == 0:
        return None

    for i in range(n):
        r, c = boxes[i]
        grid[r][c] = f'B{i + 1}'
    for i in range(n):
        r, c = goals[i]
        if grid[r][c] == '.':
            grid[r][c] = f'T{i + 1}'
        elif grid[r][c] == 'P':
            # Goal at player position - place T at nearest empty cell
            placed = False
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and grid[nr][nc] == '.':
                    grid[nr][nc] = f'T{i + 1}'
                    placed = True
                    break
            if not placed:
                # Can't place T - skip this goal and its matching box
                continue

    # Final recount
    b_count = sum(1 for row in grid for tok in row if str(tok).startswith('B'))
    t_count = sum(1 for row in grid for tok in row if str(tok).startswith('T'))
    n_final = min(b_count, t_count)
    if n_final == 0:
        return None

    # Re-number to ensure B1..Bn match T1..Tn
    final_grid = []
    b_idx = 0
    t_idx = 0
    for row in grid:
        new_row = []
        for tok in row:
            if isinstance(tok, str) and tok.startswith('B'):
                b_idx += 1
                new_row.append(f'B{b_idx}' if b_idx <= n_final else '.')
            elif isinstance(tok, str) and tok.startswith('T'):
                t_idx += 1
                new_row.append(f'T{t_idx}' if t_idx <= n_final else '.')
            else:
                new_row.append(tok if isinstance(tok, str) else '.')
        final_grid.append(tuple(new_row))

    bomb_count = sum(1 for row in final_grid for tok in row if tok == 'X')
    category = 3 if bomb_count > 0 else 2
    return Level(
        level_id=level_id,
        name=name,
        rows=tuple(final_grid),
        category=category,
        use_vision=False,
        use_deadlock=True,
        boxes_vanish_on_goal=True,
        requires_approach_recognition=False,
        hp_start=20,
        description=f"{rows}x{cols}, {n_final} boxes, {bomb_count} bombs",
    )


def parse_sok_file(text: str) -> list[tuple[str, Level]]:
    """Parse a .sok file with multiple levels."""
    levels = []
    blocks = []
    current_block = []
    consecutive_blanks = 0

    for line in text.split('\n'):
        line = line.rstrip('\r')
        stripped = line.rstrip()
        if line.startswith('::'):
            if current_block:
                blocks.append(current_block)
                current_block = []
            consecutive_blanks = 0
            continue
        if stripped and not _is_level_line(stripped):
            if current_block:
                blocks.append(current_block)
                current_block = []
            consecutive_blanks = 0
            continue
        if not stripped:
            consecutive_blanks += 1
            continue
        if consecutive_blanks >= 2 and current_block:
            blocks.append(current_block)
            current_block = []
        consecutive_blanks = 0
        current_block.append(stripped)

    if current_block:
        blocks.append(current_block)

    for idx, block in enumerate(blocks):
        if len(block) < 3:
            continue
        level = _parse_single_level('\n'.join(block), level_id=9000 + idx + 1, name=f"sok_{idx + 1}")
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
                level = Level(
                    level_id=8000 + idx, name=f"{fname}:{pname}",
                    rows=level.rows, category=level.category,
                    use_vision=False, use_deadlock=True, boxes_vanish_on_goal=True,
                    requires_approach_recognition=False, hp_start=20,
                    description=level.description,
                )
                levels.append((f"{fname}:{pname}", level))
        else:
            idx += 1
            level = _parse_single_level(text, level_id=8000 + idx, name=fname)
            if level is not None:
                levels.append((fname, level))
    return levels


def try_solve_with_permutations(level: Level, max_expanded: int = 200_000):
    """Try to solve with direct matching, then permutations for n<=3."""
    try:
        board = parse_level(level)
        clear_heuristic_cache()
        result = solve(board, max_expanded=max_expanded)
        if result.solved:
            return True, result, "direct"
    except Exception:
        pass

    box_ids = sorted(set(int(tok[1:]) for row in level.rows for tok in row if isinstance(tok, str) and tok.startswith('B')))
    goal_ids = sorted(set(int(tok[1:]) for row in level.rows for tok in row if isinstance(tok, str) and tok.startswith('T')))
    n = len(box_ids)
    if n != len(goal_ids) or n > 3:
        return False, "Cannot solve", "direct"

    for perm in permutations(range(n)):
        if perm == tuple(range(n)):
            continue
        goal_map = {goal_ids[i]: goal_ids[perm[i]] for i in range(n)}
        new_rows = []
        for row in level.rows:
            new_row = []
            for tok in row:
                if isinstance(tok, str) and tok.startswith('T'):
                    tid = int(tok[1:])
                    new_tid = goal_map.get(tid, tid)
                    new_row.append(f'T{new_tid}')
                else:
                    new_row.append(tok)
            new_rows.append(tuple(new_row))
        new_level = Level(
            level_id=level.level_id, name=level.name,
            rows=tuple(new_rows), category=level.category,
            use_vision=False, use_deadlock=True, boxes_vanish_on_goal=True,
            requires_approach_recognition=False, hp_start=20,
        )
        try:
            board = parse_level(new_level)
            clear_heuristic_cache()
            result = solve(board, max_expanded=max_expanded)
            if result.solved:
                return True, result, f"perm={perm}"
        except Exception:
            pass

    return False, "No solution", "all_perms"


def try_solve_with_matching(level: Level, max_expanded: int = 200_000):
    """Backward-compatible name used by older optimization loops."""
    return try_solve_with_permutations(level, max_expanded=max_expanded)


def try_solve(level: Level, max_expanded: int = 200_000):
    """Return the raw SolveResult for older scripts that expect direct solving."""
    board = parse_level(level)
    clear_heuristic_cache()
    return solve(board, max_expanded=max_expanded)
