package com.smartcar.planner.planner;

import java.util.Arrays;

public final class GridMap {
    public static final int ROWS = 12;
    public static final int COLS = 16;
    public static final int CELLS = ROWS * COLS;
    public static final int MAX_BOXES = 4;
    public static final int MAX_BOMBS = 4;

    public final char[] cells = new char[CELLS];
    public final Cell[] boxes = new Cell[MAX_BOXES + 1];
    public final Cell[] goals = new Cell[MAX_BOXES + 1];
    public final Cell[] bombs = new Cell[MAX_BOMBS];
    public int bombCount = 0;
    public int boxCount = 0;
    public Cell player = new Cell(5, 1);
    public char startHeading = 'R';
    public boolean requiresRecognition;
    public boolean scanBombs;
    public boolean allowBombPush;

    public GridMap() {
        Arrays.fill(cells, '.');
        for (int r = 0; r < ROWS; r++) {
            setToken(r, 0, '#');
            setToken(r, COLS - 1, '#');
        }
        for (int c = 0; c < COLS; c++) {
            setToken(0, c, '#');
            setToken(ROWS - 1, c, '#');
        }
        setToken(5, 1, 'P');
    }

    public GridMap copy() {
        GridMap out = new GridMap();
        System.arraycopy(cells, 0, out.cells, 0, cells.length);
        System.arraycopy(boxes, 0, out.boxes, 0, boxes.length);
        System.arraycopy(goals, 0, out.goals, 0, goals.length);
        System.arraycopy(bombs, 0, out.bombs, 0, bombs.length);
        out.bombCount = bombCount;
        out.boxCount = boxCount;
        out.player = player;
        out.startHeading = startHeading;
        out.requiresRecognition = requiresRecognition;
        out.scanBombs = scanBombs;
        out.allowBombPush = allowBombPush;
        return out;
    }

    public void rebuildObjects() {
        Arrays.fill(boxes, null);
        Arrays.fill(goals, null);
        Arrays.fill(bombs, null);
        boxCount = 0;
        bombCount = 0;
        // Reset player so a map without 'P' does not retain the old position.
        player = null;
        for (int r = 0; r < ROWS; r++) {
            for (int c = 0; c < COLS; c++) {
                char t = token(r, c);
                if (t == 'P') {
                    player = new Cell(r, c);
                } else if (t >= '1' && t <= '4') {
                    int id = t - '0';
                    boxes[id] = new Cell(r, c);
                    boxCount = Math.max(boxCount, id);
                } else if (t >= 'a' && t <= 'd') {
                    int id = t - 'a' + 1;
                    goals[id] = new Cell(r, c);
                } else if (t == 'X' && bombCount < MAX_BOMBS) {
                    bombs[bombCount++] = new Cell(r, c);
                }
            }
        }
        // Fallback: if no P token was found, keep a default so callers don't NPE,
        // but validate() will flag this as an error.
        if (player == null) player = new Cell(5, 1);
    }

    public char token(int row, int col) {
        return cells[row * COLS + col];
    }

    public void setToken(int row, int col, char token) {
        cells[row * COLS + col] = token;
    }

    public boolean isWall(int row, int col) {
        return row < 0 || col < 0 || row >= ROWS || col >= COLS || token(row, col) == '#';
    }

    /** Validate the map for correctness before solving. */
    public ValidationResult validate() {
        ValidationResult r = new ValidationResult();

        // Check boundary walls.
        for (int c = 0; c < COLS; c++) {
            if (token(0, c) != '#') { r.ok = false; r.message = "上边界墙被擦除 (0," + c + ")"; return r; }
            if (token(ROWS - 1, c) != '#') { r.ok = false; r.message = "下边界墙被擦除 (" + (ROWS - 1) + "," + c + ")"; return r; }
        }
        for (int rr = 0; rr < ROWS; rr++) {
            if (token(rr, 0) != '#') { r.ok = false; r.message = "左边界墙被擦除 (" + rr + ",0)"; return r; }
            if (token(rr, COLS - 1) != '#') { r.ok = false; r.message = "右边界墙被擦除 (" + rr + "," + (COLS - 1) + ")"; return r; }
        }

        // Check player count.
        int playerCount = 0;
        for (int i = 0; i < CELLS; i++) {
            if (cells[i] == 'P') playerCount++;
        }
        if (playerCount == 0) {
            r.ok = false;
            r.message = "地图缺少玩家起点 P";
            return r;
        }
        if (playerCount > 1) {
            r.ok = false;
            r.message = "地图有多个玩家起点 P (" + playerCount + " 个)，只能有 1 个";
            return r;
        }

        // Rebuild to get current box/goal counts.
        rebuildObjects();

        // Check box/goal pairing.
        if (boxCount == 0) {
            r.ok = false;
            r.message = "地图没有箱子 (B1/B2/B3/B4)";
            return r;
        }

        // Check that every box has a matching goal and vice versa.
        boolean hasUnmatchedBox = false;
        boolean hasUnmatchedGoal = false;
        int maxId = 0;
        for (int id = 1; id <= MAX_BOXES; id++) {
            if (boxes[id] != null) {
                maxId = Math.max(maxId, id);
                if (goals[id] == null) hasUnmatchedBox = true;
            }
        }
        for (int id = 1; id <= MAX_BOXES; id++) {
            if (goals[id] != null) {
                maxId = Math.max(maxId, id);
                if (boxes[id] == null) hasUnmatchedGoal = true;
            }
        }
        if (hasUnmatchedBox && !hasUnmatchedGoal) {
            r.ok = false;
            r.message = "有箱子但缺少对应编号的目标 (例如有 B1 但没有 T1)";
            return r;
        }
        if (hasUnmatchedGoal && !hasUnmatchedBox) {
            r.ok = false;
            r.message = "有目标但缺少对应编号的箱子 (例如有 T1 但没有 B1)";
            return r;
        }
        if (hasUnmatchedBox && hasUnmatchedGoal) {
            r.ok = false;
            r.message = "箱子和目标编号不匹配";
            return r;
        }

        // Check ID continuity: IDs must be 1..boxCount without gaps.
        for (int id = 1; id <= boxCount; id++) {
            if (boxes[id] == null) {
                r.ok = false;
                r.message = "箱子编号不连续: 缺少 B" + id;
                return r;
            }
            if (goals[id] == null) {
                r.ok = false;
                r.message = "目标编号不连续: 缺少 T" + id;
                return r;
            }
        }

        // Check bomb count.
        if (bombCount > MAX_BOMBS) {
            r.ok = false;
            r.message = "炸弹数量超限: " + bombCount + " > " + MAX_BOMBS;
            return r;
        }

        return r;
    }

    public static GridMap template(int levelId) {
        GridMap map = new GridMap();
        addMazeWalls(map);
        map.setToken(5, 1, 'P');
        // Base: B1(3,4) B2(7,11)  T1(3,10) T2(7,5) — overridden per level below.
        map.setToken(3, 4, '1');
        map.setToken(3, 10, 'a');
        map.setToken(7, 11, '2');
        map.setToken(7, 5, 'b');
        if (levelId == 102 || levelId == 103 || levelId == 106) {
            map.requiresRecognition = true;
        }
        if (levelId == 103) {
            // 103: 3 boxes + 1 bomb + recognition
            // T1 moves from (3,10) to (3,12), add B3/T3, add bomb at (3,8)
            map.setToken(3, 10, '.');
            map.setToken(3, 12, 'a');
            map.setToken(9, 6, '3');
            map.setToken(9, 12, 'c');
            map.setToken(3, 8, 'X');
            map.setToken(2, 8, '#');
            map.setToken(3, 9, '#');
            map.setToken(4, 8, '#');
            map.scanBombs = false;
            map.allowBombPush = true;
        }
        if (levelId == 104) {
            // 104: 4 boxes, no vision, no bombs
            // T1(3,12), T2(7,3), B3(5,5)→T3(5,11), B4(9,6)→T4(9,12)
            map.setToken(3, 10, '.');
            map.setToken(3, 12, 'a');
            map.setToken(7, 5, '.');
            map.setToken(7, 3, 'b');
            map.setToken(5, 5, '3');
            map.setToken(5, 11, 'c');
            map.setToken(9, 6, '4');
            map.setToken(9, 12, 'd');
        }
        if (levelId == 105) {
            // 105: 2 boxes + 2 bombs, no vision
            // T1(3,12), T2(7,3), X at (3,6) and (7,6)
            // Extra walls at col 8 rows 2-4 and 6-8
            map.setToken(3, 10, '.');
            map.setToken(3, 12, 'a');
            map.setToken(7, 5, '.');
            map.setToken(7, 3, 'b');
            map.setToken(3, 6, 'X');
            map.setToken(7, 6, 'X');
            map.setToken(2, 8, '#');
            map.setToken(3, 8, '#');
            map.setToken(4, 8, '#');
            map.setToken(6, 8, '#');
            map.setToken(7, 8, '#');
            map.setToken(8, 8, '#');
            map.allowBombPush = true;
        }
        if (levelId == 106) {
            // 106: 3 boxes + 1 bomb + recognition
            // T1(3,12), T2 stays at (7,5), B3(9,6)→T3(9,12), X at (3,6)
            map.setToken(3, 10, '.');
            map.setToken(3, 12, 'a');
            map.setToken(9, 6, '3');
            map.setToken(9, 12, 'c');
            map.setToken(3, 6, 'X');
            map.setToken(2, 8, '#');
            map.setToken(3, 8, '#');
            map.setToken(4, 8, '#');
            map.allowBombPush = true;
        }
        map.rebuildObjects();
        return map;
    }

    private static void addMazeWalls(GridMap map) {
        int[][] ranges = {
            {2, 2, 5}, {2, 10, 13},
            {4, 2, 3}, {4, 12, 13},
            {6, 4, 6}, {6, 9, 11},
            {8, 2, 3}, {8, 12, 13},
            {10, 2, 5}, {10, 10, 13},
        };
        for (int[] range : ranges) {
            for (int c = range[1]; c <= range[2]; c++) map.setToken(range[0], c, '#');
        }
    }

    public static final class ValidationResult {
        public boolean ok = true;
        public String message = "";
    }
}
