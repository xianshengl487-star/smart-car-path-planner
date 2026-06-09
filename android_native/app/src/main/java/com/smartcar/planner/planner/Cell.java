package com.smartcar.planner.planner;

public final class Cell {
    public final int row;
    public final int col;

    public Cell(int row, int col) {
        this.row = row;
        this.col = col;
    }

    public int index() {
        return row * GridMap.COLS + col;
    }

    @Override
    public boolean equals(Object other) {
        if (!(other instanceof Cell)) return false;
        Cell cell = (Cell) other;
        return row == cell.row && col == cell.col;
    }

    @Override
    public int hashCode() {
        return index();
    }
}
