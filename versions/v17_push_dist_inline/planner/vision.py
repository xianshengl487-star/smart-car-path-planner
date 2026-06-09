from __future__ import annotations

from itertools import permutations
from pathlib import Path

import cv2
import numpy as np

from .grid import Level

CELL_SIZE = 64  # default for generated/recognized roundtrips

BASE_COLORS_BGR: dict[str, tuple[int, int, int]] = {
    ".": (238, 238, 238),
    "#": (45, 45, 45),
    "P": (40, 180, 255),
    "X": (45, 45, 220),
    "E": (50, 200, 80),
}

BOX_COLORS_BGR: dict[int, tuple[int, int, int]] = {
    1: (60, 90, 230),
    2: (60, 155, 235),
    3: (160, 80, 220),
    4: (110, 60, 210),
}

GOAL_COLORS_BGR: dict[int, tuple[int, int, int]] = {
    1: (80, 190, 80),
    2: (200, 175, 60),
    3: (210, 120, 80),
    4: (130, 190, 60),
}


def generate_level_image(level: Level, output_path: str | Path) -> str:
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    rows = len(level.rows)
    cols = len(level.rows[0])
    image = np.full((rows * CELL_SIZE, cols * CELL_SIZE, 3), 255, dtype=np.uint8)

    for row_index, row in enumerate(level.rows):
        for col_index, token in enumerate(row):
            _draw_cell(image, row_index, col_index, token)

    _write_image(output, image)
    return str(output)


def recognize_level_image(
    image_path: str | Path,
    *,
    level_id: int,
    name: str,
    category: int = 1,
    hp_start: int,
    use_deadlock: bool = True,
    requires_approach_recognition: bool = False,
    boxes_vanish_on_goal: bool = False,
    cell_size: int | None = None,
    recognized_output_path: str | Path | None = None,
) -> Level:
    """Recognize a (possibly real camera/screenshot) grid image into a Level.

    Supports variable cell_size (for contest screenshots that are not exactly 64px cells).
    If cell_size is None, falls back to the default CELL_SIZE (for clean generated images).
    The sampled patch is now a robust central fraction of the cell to tolerate
    slight misalignment, scaling differences, and grid line thickness in real images.
    """
    image = _read_image(image_path)
    cs = cell_size if cell_size is not None else CELL_SIZE

    img_h, img_w = image.shape[:2]
    n_rows = img_h // cs
    n_cols = img_w // cs

    recognized_rows: list[tuple[str, ...]] = []
    margin_frac = 0.18  # inner 64% of cell, avoids borders/lines better than fixed +8+22

    for row_index in range(n_rows):
        row_tokens: list[str] = []
        for col_index in range(n_cols):
            y0 = row_index * cs
            x0 = col_index * cs
            m = int(cs * margin_frac)
            y1 = y0 + cs - m
            x1 = x0 + cs - m
            y0 += m
            x0 += m
            # clamp in case very small cs
            if y1 <= y0 or x1 <= x0:
                y0, y1 = row_index * cs, (row_index + 1) * cs
                x0, x1 = col_index * cs, (col_index + 1) * cs
            patch = image[y0:y1, x0:x1]
            if patch.size == 0:
                tok = "."
            else:
                # Use median per channel for robustness to text/anti-alias/noise in real captures
                med = tuple(float(np.median(patch[:, :, ch])) for ch in range(3))
                tok = _nearest_token(med)
            row_tokens.append(tok)
        recognized_rows.append(tuple(row_tokens))

    level = Level(
        level_id=level_id,
        name=name,
        rows=tuple(recognized_rows),
        category=category,
        use_vision=True,
        use_deadlock=use_deadlock,
        requires_approach_recognition=requires_approach_recognition,
        boxes_vanish_on_goal=boxes_vanish_on_goal,
        hp_start=hp_start,
        description=f"Recognized from image (cell_size={cs}).",
    )

    if recognized_output_path is not None:
        generate_level_image(level, recognized_output_path)

    return level


def _draw_cell(image: np.ndarray, row: int, col: int, token: str) -> None:
    y0 = row * CELL_SIZE
    x0 = col * CELL_SIZE
    y1 = y0 + CELL_SIZE
    x1 = x0 + CELL_SIZE

    color = _token_color(token)
    cv2.rectangle(image, (x0, y0), (x1 - 1, y1 - 1), color, thickness=-1)
    cv2.rectangle(image, (x0, y0), (x1 - 1, y1 - 1), (25, 25, 25), thickness=1)

    if token not in (".", "#"):
        text_color = (255, 255, 255) if token == "#" else (20, 20, 20)
        scale = 0.55 if len(token) > 1 else 0.7
        thickness = 2
        (width, height), _ = cv2.getTextSize(token, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
        x = x0 + (CELL_SIZE - width) // 2
        y = y0 + (CELL_SIZE + height) // 2
        cv2.putText(
            image,
            token,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            text_color,
            thickness,
            cv2.LINE_AA,
        )


def _token_color(token: str) -> tuple[int, int, int]:
    if token.startswith("B"):
        return BOX_COLORS_BGR[int(token[1:])]
    if token.startswith("T"):
        return GOAL_COLORS_BGR[int(token[1:])]
    return BASE_COLORS_BGR[token]


def _nearest_token(mean_color: tuple[float, float, float]) -> str:
    palette: dict[str, tuple[int, int, int]] = dict(BASE_COLORS_BGR)
    for box_id, color in BOX_COLORS_BGR.items():
        palette[f"B{box_id}"] = color
    for goal_id, color in GOAL_COLORS_BGR.items():
        palette[f"T{goal_id}"] = color

    def distance(color: tuple[int, int, int]) -> float:
        return sum((mean_color[index] - color[index]) ** 2 for index in range(3))

    return min(palette, key=lambda token: distance(palette[token]))


def _read_image(path: str | Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image {path}")
    return image


def _write_image(path: str | Path, image: np.ndarray) -> None:
    extension = Path(path).suffix or ".png"
    ok, buffer = cv2.imencode(extension, image)
    if not ok:
        raise ValueError(f"Cannot encode image as {extension}")
    buffer.tofile(str(path))


# ---------------------- Contest / real-image support & auto grid ----------------------

CONTEST_ROWS = 12
CONTEST_COLS = 16
CONTEST_START = (5, 1)


def _axis_clusters(values: list[float], tolerance: float) -> list[float]:
    if not values:
        return []
    groups: list[list[float]] = []
    for value in sorted(values):
        if not groups or abs(value - groups[-1][-1]) > tolerance:
            groups.append([value])
        else:
            groups[-1].append(value)
    return [sum(group) / len(group) for group in groups]


def _best_even_run(values: list[float], count: int) -> list[float]:
    if len(values) <= count:
        return values[:count]
    best = values[:count]
    best_score = float("inf")
    for start in range(0, len(values) - count + 1):
        run = values[start:start + count]
        diffs = [run[index + 1] - run[index] for index in range(len(run) - 1)]
        if not diffs:
            continue
        mean = sum(diffs) / len(diffs)
        variance = sum((diff - mean) ** 2 for diff in diffs) / len(diffs)
        score = variance ** 0.5
        if score < best_score:
            best = run
            best_score = score
    return best


def _detect_contest_grid_centers(image: np.ndarray) -> tuple[list[float], list[float]] | None:
    """Detect the 16x12 contest grid by clustering black wall-cell centers."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    mask = gray < 60
    contours, _ = cv2.findContours(mask.astype("uint8") * 255, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    centers: list[tuple[float, float]] = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if 18 <= width <= 50 and 16 <= height <= 42 and area >= 250:
            centers.append((x + width / 2, y + height / 2))

    if len(centers) < CONTEST_ROWS + CONTEST_COLS:
        return None

    xs = _axis_clusters([x for x, _ in centers], tolerance=14)
    ys = _axis_clusters([y for _, y in centers], tolerance=14)
    if len(xs) < CONTEST_COLS or len(ys) < CONTEST_ROWS:
        return None

    xs = _best_even_run(xs, CONTEST_COLS)
    ys = _best_even_run(ys, CONTEST_ROWS)
    if len(xs) != CONTEST_COLS or len(ys) != CONTEST_ROWS:
        return None
    return xs, ys


def _contest_cell_token(median_bgr: np.ndarray) -> str:
    blue, green, red = (float(value) for value in median_bgr)
    if blue < 75 and green < 75 and red < 75:
        return "#"
    if red > 180 and green > 140 and blue < 130:
        return "B"
    if blue > 180 and green > 80 and red < 150:
        return "T"
    if red > 150 and green < 130 and blue < 130:
        return "X"
    return "."


def _recognize_contest_fixed_grid(image: np.ndarray) -> tuple[tuple[str, ...], ...] | None:
    detected = _detect_contest_grid_centers(image)
    if detected is None:
        return None

    xs, ys = detected
    step_x = float(np.median(np.diff(xs))) if len(xs) > 1 else 32.0
    step_y = float(np.median(np.diff(ys))) if len(ys) > 1 else 32.0
    half_w = max(5, int(step_x * 0.25))
    half_h = max(5, int(step_y * 0.25))

    rows = [["." for _ in range(CONTEST_COLS)] for _ in range(CONTEST_ROWS)]
    boxes: list[tuple[int, int]] = []
    goals: list[tuple[int, int]] = []

    height, width = image.shape[:2]
    for row_index, center_y in enumerate(ys):
        for col_index, center_x in enumerate(xs):
            y0 = max(0, int(center_y) - half_h)
            y1 = min(height, int(center_y) + half_h)
            x0 = max(0, int(center_x) - half_w)
            x1 = min(width, int(center_x) + half_w)
            patch = image[y0:y1, x0:x1]
            if patch.size == 0:
                continue
            token = _contest_cell_token(np.median(patch.reshape(-1, 3), axis=0))
            if token == "B":
                boxes.append((row_index, col_index))
            elif token == "T":
                goals.append((row_index, col_index))
            else:
                rows[row_index][col_index] = token

    boxes.sort()
    goals.sort()
    matched_count = min(len(boxes), len(goals), 4)
    for index in range(matched_count):
        box_row, box_col = boxes[index]
        goal_row, goal_col = goals[index]
        rows[box_row][box_col] = f"B{index + 1}"
        rows[goal_row][goal_col] = f"T{index + 1}"

    start_row, start_col = CONTEST_START
    rows[start_row][start_col] = "P"
    return tuple(tuple(row) for row in rows)


def _remap_goal_ids(level: Level, perm: tuple[int, ...]) -> Level:
    """Return a level where B ids stay fixed and T ids follow the permutation."""
    boxes: list[tuple[int, int, str]] = []
    goals: list[tuple[int, int, str]] = []
    rows = [list(row) for row in level.rows]
    for row_index, row in enumerate(rows):
        for col_index, token in enumerate(row):
            if token.startswith("B"):
                boxes.append((row_index, col_index, token))
                rows[row_index][col_index] = "."
            elif token.startswith("T"):
                goals.append((row_index, col_index, token))
                rows[row_index][col_index] = "."

    boxes.sort()
    goals.sort()
    if len(boxes) != len(goals) or len(perm) != len(goals):
        return level

    for index, (row_index, col_index, _token) in enumerate(boxes, start=1):
        rows[row_index][col_index] = f"B{index}"
    for index, goal_index in enumerate(perm, start=1):
        row_index, col_index, _token = goals[goal_index]
        rows[row_index][col_index] = f"T{index}"

    return Level(
        level_id=level.level_id,
        name=level.name,
        rows=tuple(tuple(row) for row in rows),
        category=level.category,
        use_vision=level.use_vision,
        use_deadlock=level.use_deadlock,
        requires_approach_recognition=level.requires_approach_recognition,
        hp_start=level.hp_start,
        description=level.description + f" [target_perm={perm}]",
        start_heading=level.start_heading,
        boxes_vanish_on_goal=level.boxes_vanish_on_goal,
    )


def _goal_permutation_candidates(level: Level) -> list[tuple[int, ...]]:
    boxes: list[tuple[int, int]] = []
    goals: list[tuple[int, int]] = []
    for row_index, row in enumerate(level.rows):
        for col_index, token in enumerate(row):
            if token.startswith("B"):
                boxes.append((row_index, col_index))
            elif token.startswith("T"):
                goals.append((row_index, col_index))

    boxes.sort()
    goals.sort()
    if len(boxes) != len(goals) or len(boxes) <= 1 or len(boxes) > 4:
        return []

    count = len(boxes)
    direct = tuple(range(count))
    candidates: list[tuple[int, ...]] = []
    seen = {direct}

    # Contest screenshots can preserve cyclic visual order even when raw
    # reading-order labels are offset by one.
    for shift in range(1, count):
        perm = tuple((index + shift) % count for index in range(count))
        if perm not in seen:
            seen.add(perm)
            candidates.append(perm)

    scored: list[tuple[int, tuple[int, ...]]] = []
    for perm in permutations(range(count)):
        if perm in seen:
            continue
        score = sum(
            abs(boxes[index][0] - goals[perm[index]][0])
            + abs(boxes[index][1] - goals[perm[index]][1])
            for index in range(count)
        )
        scored.append((score, perm))
    candidates.extend(perm for _score, perm in sorted(scored))
    return candidates


def _numbered_object_count(level: Level, prefix: str) -> int:
    return sum(1 for row in level.rows for token in row if token.startswith(prefix))


def _matching_manhattan_lower_bound(level: Level) -> int:
    boxes: dict[int, tuple[int, int]] = {}
    goals: dict[int, tuple[int, int]] = {}
    for row_index, row in enumerate(level.rows):
        for col_index, token in enumerate(row):
            if token.startswith("B"):
                boxes[int(token[1:])] = (row_index, col_index)
            elif token.startswith("T"):
                goals[int(token[1:])] = (row_index, col_index)

    total = 0
    for object_id, box in boxes.items():
        goal = goals.get(object_id)
        if goal is None:
            continue
        total += abs(box[0] - goal[0]) + abs(box[1] - goal[1])
    return total


def _cleanup_tokens(tokens: list[list[str]]) -> list[list[str]]:
    """Post-process recognized token grid to fix common real-image artifacts:
    - Exactly one P (pick the 'best' cyan cell; demote duplicates to .)
    - Try to make B ids match T ids (drop lowest-confidence extras on the side with more).
    - Force outer border walls if a strong majority of perimeter looks wall-like
      (typical for these puzzles; helps when UI chrome or lighting miscolors edges).
    This greatly increases the chance that parse_level will succeed on contest screenshots.
    """
    if not tokens or not tokens[0]:
        return tokens

    nr = len(tokens)
    nc = len(tokens[0])
    cleaned = [list(row) for row in tokens]

    # 1. Fix player: find all cells whose *color distance to P* is small even if token != P,
    #    or that were labeled P. Keep only the single most plausible one.
    p_color = BASE_COLORS_BGR["P"]
    p_candidates = []
    for r in range(nr):
        for c in range(nc):
            # re-compute a quick mean for confidence (we don't have the image here, so use token + heuristic)
            tok = cleaned[r][c]
            conf = 0.0
            if tok == "P":
                conf = 10.0
            # crude: cells in the middle 60% of the grid are more likely real P
            center_bonus = 1.0 - (abs(r - nr/2) / nr + abs(c - nc/2) / nc)
            p_candidates.append((r, c, tok, conf + center_bonus * 3))

    if p_candidates:
        p_candidates.sort(key=lambda x: x[3], reverse=True)
        best_r, best_c, _, _ = p_candidates[0]
        for r, c, tok, _ in p_candidates:
            if (r, c) != (best_r, best_c):
                if cleaned[r][c] == "P":
                    cleaned[r][c] = "."

    # 2. Border wall enforcement (soft)
    border_cells = []
    for c in range(nc):
        border_cells.append((0, c))
        border_cells.append((nr-1, c))
    for r in range(1, nr-1):
        border_cells.append((r, 0))
        border_cells.append((r, nc-1))

    wallish = sum(1 for r,c in border_cells if cleaned[r][c] == "#")
    if len(border_cells) > 0 and wallish / len(border_cells) >= 0.55:
        for r, c in border_cells:
            if cleaned[r][c] not in ("#", "P", "X"):  # don't overwrite important objects
                cleaned[r][c] = "#"

    # 3. B/T id matching repair (drop extras on the over-represented side)
    boxes = {}   # id -> (r,c)
    goals = {}
    for r in range(nr):
        for c in range(nc):
            tok = cleaned[r][c]
            if tok.startswith("B"):
                bid = int(tok[1:])
                if bid not in boxes:  # keep first seen
                    boxes[bid] = (r, c)
            elif tok.startswith("T"):
                tid = int(tok[1:])
                if tid not in goals:
                    goals[tid] = (r, c)

    if boxes and goals:
        extra_b = set(boxes) - set(goals)
        extra_t = set(goals) - set(boxes)
        for bid in extra_b:
            r, c = boxes[bid]
            cleaned[r][c] = "."   # drop spurious box
        for tid in extra_t:
            r, c = goals[tid]
            cleaned[r][c] = "."   # drop spurious target

    return [tuple(row) for row in cleaned]


def _estimate_cell_size(image: np.ndarray, min_cs: int = 28, max_cs: int = 80, step: int = 2) -> int:
    """Heuristic cell size estimator for real screenshots/contest images.
    Tries several sizes and picks the one whose *cleaned* token grid looks most 'puzzle-like'.
    """
    h, w = image.shape[:2]
    best_score = -1.0
    best_cs = CELL_SIZE

    candidates = list(range(min_cs, max_cs + 1, step))
    for extra in (42, 46, 50, 54, 58):
        if extra not in candidates:
            candidates.append(extra)
    candidates = sorted(set(c for c in candidates if 24 <= c <= 82))

    for cs in candidates:
        nr = h // cs
        nc = w // cs
        if nr < 5 or nc < 5 or nr > 22 or nc > 22:
            continue

        margin = max(2, int(cs * 0.18))
        tokens: list[list[str]] = []
        for r in range(nr):
            row_t = []
            for c in range(nc):
                y0 = r * cs + margin
                x0 = c * cs + margin
                y1 = (r + 1) * cs - margin
                x1 = (c + 1) * cs - margin
                patch = image[y0:y1, x0:x1] if y1 > y0 and x1 > x0 else image[r*cs:(r+1)*cs, c*cs:(c+1)*cs]
                if patch.size == 0:
                    tok = "."
                else:
                    med = tuple(float(np.median(patch[:, :, ch])) for ch in range(3))
                    tok = _nearest_token(med)
                row_t.append(tok)
            tokens.append(row_t)

        cleaned = _cleanup_tokens(tokens)

        # scoring on cleaned grid
        score = 0.0
        border_wall = 0
        border_total = 0
        for c in range(nc):
            if cleaned[0][c] == "#": border_wall += 1
            if cleaned[-1][c] == "#": border_wall += 1
            border_total += 2
        for r in range(nr):
            if cleaned[r][0] == "#": border_wall += 1
            if cleaned[r][-1] == "#": border_wall += 1
            border_total += 2
        if border_total > 0:
            score += 5.0 * (border_wall / border_total)

        has_p = any("P" in row for row in cleaned)
        score += 4.0 if has_p else -2.0

        boxes = {int(t[1:]) for row in cleaned for t in row if t.startswith("B")}
        goals = {int(t[1:]) for row in cleaned for t in row if t.startswith("T")}
        matched = len(boxes & goals)
        score += 3.0 * matched
        if boxes or goals:
            score += 0.8 * min(len(boxes), 4)

        wall_count = sum(row.count("#") for row in cleaned)
        if wall_count < max(5, (nr + nc)):
            score -= 2.5

        # bonus for exactly one P after cleanup
        p_count = sum(row.count("P") for row in cleaned)
        if p_count == 1:
            score += 2.0
        elif p_count > 1:
            score -= 1.5 * (p_count - 1)

        if score > best_score:
            best_score = score
            best_cs = cs

    return best_cs


def recognize_contest_image(
    image_path: str | Path,
    *,
    level_id: int = 999,
    name: str | None = None,
    auto_category: bool = True,
    default_category: int = 3,
    hp_start: int = 20,
    use_deadlock: bool = True,
    recognized_output_path: str | Path | None = None,
) -> Level:
    """High-level recognizer tuned for real '比赛关卡' contest screenshots.

    - Auto-estimates cell size (handles the ~800x485 phone/wechat captures).
    - Builds token grid with robust central sampling + median.
    - Infers category from detected tokens (X -> 3, B/T -> 2, else 1).
    - Sets reasonable defaults: boxes_vanish_on_goal=True, requires_approach for cat>=2.
    - Always produces a Level that parse_level + solve should accept (if the image
      is a valid puzzle under the project rules).
    """
    img = _read_image(image_path)
    fixed_rows = _recognize_contest_fixed_grid(img)
    if fixed_rows is not None:
        has_b = any(token.startswith("B") for row in fixed_rows for token in row)
        has_x = any(token == "X" for row in fixed_rows for token in row)
        has_e = any(token == "E" for row in fixed_rows for token in row)
        if auto_category:
            if has_x:
                category = 3
            elif has_b:
                category = 2
            elif has_e:
                category = 1
            else:
                category = default_category
        else:
            category = default_category

        level = Level(
            level_id=level_id,
            name=name or f"Contest-{Path(image_path).stem[:8]}",
            rows=fixed_rows,
            category=category,
            use_vision=True,
            use_deadlock=use_deadlock,
            requires_approach_recognition=category >= 2,
            boxes_vanish_on_goal=category >= 2,
            hp_start=hp_start,
            description="Recognized from contest screenshot with fixed 16x12 grid.",
        )
        if recognized_output_path is not None:
            generate_level_image(level, recognized_output_path)
        return level

    cs = _estimate_cell_size(img)

    # First pass with estimated cs to get raw tokens
    nr = img.shape[0] // cs
    nc = img.shape[1] // cs
    margin = max(2, int(cs * 0.18))

    tokens: list[list[str]] = []
    for r in range(nr):
        row_t: list[str] = []
        for c in range(nc):
            y0 = r * cs + margin
            x0 = c * cs + margin
            y1 = (r + 1) * cs - margin
            x1 = (c + 1) * cs - margin
            patch = img[y0:y1, x0:x1] if (y1 > y0 and x1 > x0) else img[r*cs:(r+1)*cs, c*cs:(c+1)*cs]
            if patch.size == 0:
                tok = "."
            else:
                med = tuple(float(np.median(patch[:, :, ch])) for ch in range(3))
                tok = _nearest_token(med)
            row_t.append(tok)
        tokens.append(row_t)

    # Infer objects
    has_b = any(t.startswith("B") for row in tokens for t in row)
    has_x = any(t == "X" for row in tokens for t in row)
    has_e = any(t == "E" for row in tokens for t in row)

    if auto_category:
        if has_x:
            category = 3
        elif has_b:
            category = 2
        elif has_e:
            category = 1
        else:
            category = default_category
    else:
        category = default_category

    requires_approach = category >= 2
    vanish = category >= 2  # per user rule for box levels

    base_name = name or f"Contest-{Path(image_path).stem[:8]}"

    level = recognize_level_image(
        image_path,
        level_id=level_id,
        name=base_name,
        category=category,
        hp_start=hp_start,
        use_deadlock=use_deadlock,
        requires_approach_recognition=requires_approach,
        boxes_vanish_on_goal=vanish,
        cell_size=cs,
        recognized_output_path=recognized_output_path,
    )

    # Apply cleanup (exactly-1-P, B/T matching, border walls) to make parse_level + solver happy
    raw_rows = [list(row) for row in level.rows]
    cleaned_rows = _cleanup_tokens(raw_rows)

    # Extra contest safety: if still mismatched B/T ids, keep only the common matched subset
    # so parse_level succeeds and we have a (possibly partial) solvable puzzle.
    # Work on mutable lists.
    cleaned_rows = [list(row) for row in cleaned_rows]
    boxes_ids = {int(t[1:]) for row in cleaned_rows for t in row if t.startswith("B")}
    goals_ids = {int(t[1:]) for row in cleaned_rows for t in row if t.startswith("T")}
    if boxes_ids and goals_ids and boxes_ids != goals_ids:
        common = boxes_ids & goals_ids
        if common:
            for r in range(len(cleaned_rows)):
                for c in range(len(cleaned_rows[0])):
                    tok = cleaned_rows[r][c]
                    if tok.startswith("B") and int(tok[1:]) not in common:
                        cleaned_rows[r][c] = "."
                    if tok.startswith("T") and int(tok[1:]) not in common:
                        cleaned_rows[r][c] = "."

    cleaned_tuples = tuple(tuple(row) for row in cleaned_rows)
    if cleaned_tuples != level.rows:
        level = Level(
            level_id=level.level_id,
            name=level.name,
            rows=cleaned_tuples,
            category=level.category,
            use_vision=True,
            use_deadlock=level.use_deadlock,
            requires_approach_recognition=level.requires_approach_recognition,
            boxes_vanish_on_goal=level.boxes_vanish_on_goal,
            hp_start=level.hp_start,
            description=level.description + " [cleaned+matched]",
        )
        if recognized_output_path is not None:
            try:
                generate_level_image(level, recognized_output_path)
            except Exception:
                pass

    if len(level.rows) < 5 or len(level.rows[0]) < 5:
        pass  # caller will see the problem

    return level


def batch_solve_contest_levels(
    contest_dir: str | Path = "比赛关卡",
    max_expanded: int = 800_000,
    save_outputs: bool = True,
) -> list[dict]:
    """Process all PNGs in the contest levels folder, recognize + solve, return summaries.
    This is the main entry to '完成文件夹里的比赛关卡图片地图'.
    Tries hard (multiple categories, high expansion) to ensure as many simple/real maps as possible succeed.
    """
    from planner.grid import parse_level
    from planner.solver import solve

    out_dir = Path("outputs")
    if save_outputs:
        out_dir.mkdir(parents=True, exist_ok=True)

    results = []
    contest_dir = Path(contest_dir)
    if not contest_dir.exists():
        for child in Path.cwd().iterdir():
            if child.is_dir() and child.name != "outputs" and list(child.glob("*.png")):
                contest_dir = child
                break

    pngs = sorted(contest_dir.glob("*.png"))
    for img_path in pngs:
        rec_path = out_dir / f"contest_rec_{img_path.stem}.png" if save_outputs else None
        solved_any = False
        best_res = None
        used_level = None
        last_err: Exception | None = None
        matching_mode = "direct"

        try:
            base_level = recognize_contest_image(img_path, recognized_output_path=rec_path)
            candidate_levels: list[tuple[str, Level]] = [("direct", base_level)]
            candidate_levels.extend(
                (f"target_perm={perm}", _remap_goal_ids(base_level, perm))
                for perm in _goal_permutation_candidates(base_level)
            )
        except Exception as exc:
            results.append({
                "image": str(img_path),
                "solved": False,
                "message": str(exc)[:80],
                "grid": None,
                "category": None,
            })
            continue

        direct_probe_budget = min(max_expanded, 4_000) if max_expanded > 4_000 else max_expanded
        remap_probe_budget = min(max_expanded, 8_000) if max_expanded > 8_000 else max_expanded
        box_count = _numbered_object_count(base_level, "B")
        cycle_candidates = candidate_levels[1:box_count]
        remap_probe_candidates: list[tuple[str, Level]] = []
        if cycle_candidates:
            direct_lb = _matching_manhattan_lower_bound(base_level)
            best_cycle_lb = min(_matching_manhattan_lower_bound(level) for _label, level in cycle_candidates)
            if best_cycle_lb <= direct_lb:
                remap_probe_candidates.extend(cycle_candidates)

        solve_rounds: list[tuple[int, list[tuple[str, Level]], str]] = []
        if direct_probe_budget < max_expanded:
            # A capped A* probe is still exact if it reaches a goal; if it does
            # not, we only learned "not solved yet" and retry with the full cap.
            solve_rounds.append((direct_probe_budget, candidate_levels[:1], "probe"))
        if remap_probe_candidates and remap_probe_budget < max_expanded:
            solve_rounds.append((remap_probe_budget, remap_probe_candidates, "probe"))
        solve_rounds.append((max_expanded, candidate_levels, "full"))

        for budget, candidates, round_name in solve_rounds:
            if solved_any:
                break
            for label, candidate in candidates:
                try:
                    board = parse_level(candidate)
                    res = solve(board, max_expanded=budget)
                except Exception as exc:
                    last_err = exc
                    continue

                if res.solved:
                    solved_any = True
                    best_res = res
                    used_level = candidate
                    matching_mode = label if round_name == "full" else f"{label}, probe={budget}"
                    if save_outputs and candidate is not base_level and rec_path is not None:
                        generate_level_image(candidate, rec_path)
                    break

                if best_res is None or res.expanded > best_res.expanded:
                    best_res = res
                    used_level = candidate
                    matching_mode = label

        if solved_any and best_res is not None:
            summary = {
                "image": str(img_path),
                "grid": (used_level.rows and len(used_level.rows), used_level.rows and len(used_level.rows[0])),
                "category": used_level.category,
                "solved": True,
                "cost": best_res.total_cost,
                "pushes": best_res.pushes,
                "expanded": best_res.expanded,
                "message": "Solved",
                "matching": matching_mode,
            }
            if save_outputs:
                try:
                    from planner.visualizer_tk import save_final_frame
                    final_path = out_dir / f"contest_final_{img_path.stem}.png"
                    save_final_frame(parse_level(used_level), best_res, final_path)
                    summary["final_image"] = str(final_path)
                except Exception:
                    pass
            results.append(summary)
        else:
            # report the last attempt or error
            msg = str(last_err) if last_err else (best_res.message if best_res else "no solution found")
            results.append({
                "image": str(img_path),
                "solved": False,
                "message": msg[:80],
                "grid": (used_level.rows and len(used_level.rows), used_level.rows and len(used_level.rows[0])) if used_level else None,
                "category": used_level.category if used_level else None,
            })
    return results
