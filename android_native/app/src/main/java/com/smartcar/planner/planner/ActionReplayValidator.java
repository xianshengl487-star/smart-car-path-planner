package com.smartcar.planner.planner;

/**
 * Replays a PlannerResult.action sequence on a GridMap and verifies that every
 * step is legal and that the final state has all boxes delivered to their goals.
 * This prevents the solver from reporting solved=true when the action sequence
 * is actually invalid.
 */
public final class ActionReplayValidator {

    private ActionReplayValidator() {}

    /**
     * Validate the given result against the map. Returns null if valid, or a
     * human-readable error message describing the first illegal step.
     */
    public static String validate(GridMap map, PlannerResult result) {
        if (result == null) return "result 为 null";
        if (!result.solved) return "result.solved=false，无需验证动作";
        if (result.actions.isEmpty()) return "动作序列为空";

        // Work on a copy so we don't mutate the original.
        GridMap work = map.copy();
        work.rebuildObjects();

        Cell player = work.player;
        char heading = work.startHeading;
        Cell[] boxes = new Cell[GridMap.MAX_BOXES + 1];
        Cell[] bombs = new Cell[GridMap.MAX_BOMBS];
        int bombCount = 0;
        // Parse objects from the working map.
        for (int r = 0; r < GridMap.ROWS; r++) {
            for (int c = 0; c < GridMap.COLS; c++) {
                char t = work.token(r, c);
                if (t == 'P') player = new Cell(r, c);
                else if (t >= '1' && t <= '4') boxes[t - '0'] = new Cell(r, c);
                else if (t == 'X' && bombCount < bombs.length) bombs[bombCount++] = new Cell(r, c);
            }
        }
        // Build wall map for quick checks.
        boolean[] wallMap = new boolean[GridMap.CELLS];
        for (int i = 0; i < GridMap.CELLS; i++) {
            wallMap[i] = work.token(i / GridMap.COLS, i % GridMap.COLS) == '#';
        }
        boolean[] destroyed = new boolean[GridMap.CELLS];

        for (int step = 0; step < result.actions.size(); step++) {
            String action = result.actions.get(step);

            if ("turn_left".equals(action)) {
                heading = leftHeading(heading);
                continue;
            }
            if ("turn_right".equals(action)) {
                heading = rightHeading(heading);
                continue;
            }
            if ("forward".equals(action)) {
                Cell next = move(player, heading);
                if (!inside(next)) return stepStr(step, action) + " 玩家移动出界";
                if (isWallAt(wallMap, destroyed, next)) return stepStr(step, action) + " 玩家撞墙";
                if (boxAt(boxes, next) >= 0) return stepStr(step, action) + " forward 不能推动箱子，需要 push";
                if (bombAt(bombs, next) >= 0) return stepStr(step, action) + " forward 不能推动炸弹";
                player = next;
                continue;
            }

            // Single-char uppercase: push box (L/U/D/R)
            if (action.length() == 1 && Character.isUpperCase(action.charAt(0))) {
                char pushDir = action.charAt(0);
                Cell front = move(player, pushDir);
                if (!inside(front)) return stepStr(step, action) + " 推箱位置出界";
                if (isWallAt(wallMap, destroyed, front)) return stepStr(step, action) + " 推箱目标是墙";
                int boxId = boxAt(boxes, front);
                if (boxId < 0) return stepStr(step, action) + " 前方没有箱子可推";
                Cell pushed = move(front, pushDir);
                if (!inside(pushed)) return stepStr(step, action) + " 箱子推出界";
                if (isWallAt(wallMap, destroyed, pushed)) return stepStr(step, action) + " 箱子推入墙";
                if (boxAt(boxes, pushed) >= 0) return stepStr(step, action) + " 目标位置有另一个箱子";
                if (bombAt(bombs, pushed) >= 0) return stepStr(step, action) + " 目标位置有炸弹";
                // Move player to the box's old position, box to pushed position.
                player = front;
                heading = pushDir;
                Cell goal = work.goals[boxId];
                if (goal != null && goal.equals(pushed)) {
                    // Box delivered -- it vanishes.
                    boxes[boxId] = null;
                } else {
                    boxes[boxId] = pushed;
                }
                continue;
            }

            // Two-char actions: xL/xU/xD/xR (bomb move) or XL/XU/XD/XR (bomb explode)
            if (action.length() == 2 && (action.charAt(0) == 'x' || action.charAt(0) == 'X')) {
                char pushDir = action.charAt(1);
                boolean explode = action.charAt(0) == 'X';
                Cell front = move(player, pushDir);
                if (!inside(front)) return stepStr(step, action) + " 炸弹操作位置出界";
                if (isWallAt(wallMap, destroyed, front)) return stepStr(step, action) + " 炸弹操作位置是墙";
                int bombIdx = bombAt(bombs, front);
                if (bombIdx < 0) return stepStr(step, action) + " 前方没有炸弹";
                Cell target = move(front, pushDir);
                if (!inside(target)) return stepStr(step, action) + " 炸弹推出界";
                if (boxAt(boxes, target) >= 0) return stepStr(step, action) + " 炸弹目标有箱子";
                if (bombAt(bombs, target) >= 0) return stepStr(step, action) + " 炸弹目标有另一个炸弹";

                player = front;
                heading = pushDir;

                if (explode) {
                    // Verify the target is actually a wall (the bomb explodes on impact).
                    if (!isWallAt(wallMap, destroyed, target)) {
                        return stepStr(step, action) + " 炸弹爆炸目标不是墙";
                    }
                    // Destroy non-boundary walls in 3x3 area.
                    for (int rr = target.row - 1; rr <= target.row + 1; rr++) {
                        for (int cc = target.col - 1; cc <= target.col + 1; cc++) {
                            if (!inside(rr, cc) || isBoundaryWall(rr, cc)) continue;
                            int idx = rr * GridMap.COLS + cc;
                            if (wallMap[idx] && !destroyed[idx]) {
                                destroyed[idx] = true;
                            }
                        }
                    }
                    bombs[bombIdx] = null;
                } else {
                    // Non-explosive bomb move.
                    bombs[bombIdx] = target;
                }
                continue;
            }

            return stepStr(step, action) + " 无法识别的动作格式";
        }

        // Final check: all boxes should be delivered (null).
        for (int id = 1; id <= GridMap.MAX_BOXES; id++) {
            if (boxes[id] != null) {
                return "验证完成但箱子 B" + id + " 未到达目标";
            }
        }
        return null; // valid
    }

    // --- helpers ---

    private static String stepStr(int step, String action) {
        return "步骤 " + (step + 1) + " [" + action + "]";
    }

    private static boolean inside(Cell c) {
        return c.row >= 0 && c.col >= 0 && c.row < GridMap.ROWS && c.col < GridMap.COLS;
    }

    private static boolean inside(int row, int col) {
        return row >= 0 && col >= 0 && row < GridMap.ROWS && col < GridMap.COLS;
    }

    private static boolean isBoundaryWall(int row, int col) {
        return row == 0 || col == 0 || row == GridMap.ROWS - 1 || col == GridMap.COLS - 1;
    }

    private static boolean isWallAt(boolean[] wallMap, boolean[] destroyed, Cell c) {
        int idx = c.index();
        return wallMap[idx] && !destroyed[idx];
    }

    private static Cell move(Cell from, char heading) {
        switch (Character.toUpperCase(heading)) {
            case 'L': return new Cell(from.row, from.col - 1);
            case 'R': return new Cell(from.row, from.col + 1);
            case 'U': return new Cell(from.row - 1, from.col);
            case 'D': return new Cell(from.row + 1, from.col);
            default: return from;
        }
    }

    private static int boxAt(Cell[] boxes, Cell cell) {
        for (int id = 1; id < boxes.length; id++) {
            if (boxes[id] != null && boxes[id].equals(cell)) return id;
        }
        return -1;
    }

    private static int bombAt(Cell[] bombs, Cell cell) {
        for (int i = 0; i < bombs.length; i++) {
            if (bombs[i] != null && bombs[i].equals(cell)) return i;
        }
        return -1;
    }

    private static char leftHeading(char h) {
        h = Character.toUpperCase(h);
        if (h == 'U') return 'L';
        if (h == 'L') return 'D';
        if (h == 'D') return 'R';
        return 'U';
    }

    private static char rightHeading(char h) {
        h = Character.toUpperCase(h);
        if (h == 'U') return 'R';
        if (h == 'R') return 'D';
        if (h == 'D') return 'L';
        return 'U';
    }
}
