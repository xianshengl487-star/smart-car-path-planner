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
        for (int r = 0; r < ROWS; r++) {
            for (int c = 0; c < COLS; c++) {
                char t = token(r, c);
                if (t == 'P') player = new Cell(r, c);
                else if (t >= '1' && t <= '4') {
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

    public static GridMap template(int levelId) {
        GridMap map = new GridMap();
        addMazeWalls(map);
        map.setToken(5, 1, 'P');
        map.setToken(3, 4, '1');
        map.setToken(3, 10, 'a');
        map.setToken(7, 11, '2');
        map.setToken(7, 5, 'b');
        if (levelId == 102 || levelId == 103) {
            map.requiresRecognition = true;
        }
        if (levelId == 103) {
            map.setToken(9, 6, '3');
            map.setToken(9, 12, 'c');
            map.setToken(3, 10, '.');
            map.setToken(3, 12, 'a');
            map.setToken(3, 8, 'X');
            map.setToken(2, 8, '#');
            map.setToken(3, 9, '#');
            map.setToken(4, 8, '#');
            map.scanBombs = false;
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
}
