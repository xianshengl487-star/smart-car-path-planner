package com.smartcar.planner;

import android.content.Context;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.util.AttributeSet;
import android.view.MotionEvent;
import android.view.View;

import com.smartcar.planner.planner.Cell;
import com.smartcar.planner.planner.GridMap;
import com.smartcar.planner.planner.PlannerResult;

import java.util.HashSet;

public final class MapEditorView extends View {
    private GridMap map = GridMap.template(101);
    private char brush = '#';
    private PlannerResult result;
    private int animationStep;
    private char frameHeading = 'R';
    private EditListener editListener;
    private final char[] frameCells = new char[GridMap.CELLS];
    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final HashSet<Integer> pathCells = new HashSet<>();

    public MapEditorView(Context context) {
        super(context);
    }

    public MapEditorView(Context context, AttributeSet attrs) {
        super(context, attrs);
    }

    public void setMap(GridMap map) {
        this.map = map;
        this.result = null;
        this.animationStep = 0;
        rebuildPath();
        rebuildFrame();
        invalidate();
    }

    public GridMap getMap() {
        return map;
    }

    public void setBrush(char brush) {
        this.brush = brush;
    }

    public void setResult(PlannerResult result) {
        this.result = result;
        this.animationStep = 0;
        rebuildPath();
        rebuildFrame();
        invalidate();
    }

    public void setAnimationStep(int step) {
        int maxStep = getActionCount();
        int clamped = Math.max(0, Math.min(step, maxStep));
        if (animationStep == clamped) return;
        animationStep = clamped;
        rebuildPath();
        rebuildFrame();
        invalidate();
    }

    public int getAnimationStep() {
        return animationStep;
    }

    public int getActionCount() {
        return result == null ? 0 : result.actions.size();
    }

    public void setEditListener(EditListener editListener) {
        this.editListener = editListener;
    }

    private void rebuildPath() {
        pathCells.clear();
        if (result == null) return;
        int last = Math.min(animationStep, result.playerPath.size() - 1);
        for (int i = 0; i <= last; i++) pathCells.add(result.playerPath.get(i).index());
    }

    private void rebuildFrame() {
        System.arraycopy(map.cells, 0, frameCells, 0, GridMap.CELLS);
        frameHeading = map.startHeading;
        if (result == null) return;

        Cell player = map.player;
        Cell[] boxes = new Cell[GridMap.MAX_BOXES + 1];
        Cell[] bombs = new Cell[GridMap.MAX_BOMBS];
        int bombCount = 0;
        for (int i = 0; i < GridMap.CELLS; i++) {
            char token = frameCells[i];
            if (token == 'P') {
                frameCells[i] = '.';
            } else if (token >= '1' && token <= '4') {
                boxes[token - '0'] = new Cell(i / GridMap.COLS, i % GridMap.COLS);
                frameCells[i] = '.';
            } else if (token == 'X') {
                if (bombCount < bombs.length) bombs[bombCount++] = new Cell(i / GridMap.COLS, i % GridMap.COLS);
                frameCells[i] = '.';
            }
        }

        int steps = Math.min(animationStep, result.actions.size());
        for (int i = 0; i < steps; i++) {
            String action = result.actions.get(i);
            if ("turn_left".equals(action)) {
                frameHeading = leftHeading(frameHeading);
            } else if ("turn_right".equals(action)) {
                frameHeading = rightHeading(frameHeading);
            } else if ("forward".equals(action)) {
                player = new Cell(player.row + dirDr(frameHeading), player.col + dirDc(frameHeading));
            } else if (action.length() == 1) {
                char heading = action.charAt(0);
                Cell front = new Cell(player.row + dirDr(heading), player.col + dirDc(heading));
                int boxId = boxAt(boxes, front);
                if (boxId > 0) {
                    Cell pushed = new Cell(front.row + dirDr(heading), front.col + dirDc(heading));
                    boxes[boxId] = isGoalCell(boxId, pushed) ? null : pushed;
                }
                player = front;
                frameHeading = heading;
            } else if (action.length() == 2 && (action.charAt(0) == 'x' || action.charAt(0) == 'X')) {
                char heading = action.charAt(1);
                Cell front = new Cell(player.row + dirDr(heading), player.col + dirDc(heading));
                int bombIndex = bombAt(bombs, front);
                if (bombIndex >= 0) {
                    Cell target = new Cell(front.row + dirDr(heading), front.col + dirDc(heading));
                    if (action.charAt(0) == 'X') {
                        explodeAt(target);
                        bombs[bombIndex] = null;
                    } else {
                        bombs[bombIndex] = target;
                    }
                }
                player = front;
                frameHeading = heading;
            }
        }

        for (int id = 1; id < boxes.length; id++) {
            Cell box = boxes[id];
            if (box != null && inside(box.row, box.col)) frameCells[box.index()] = (char) ('0' + id);
        }
        for (Cell bomb : bombs) {
            if (bomb != null && inside(bomb.row, bomb.col)) frameCells[bomb.index()] = 'X';
        }
        if (inside(player.row, player.col)) frameCells[player.index()] = 'P';
    }

    @Override
    protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        float cell = Math.min(getWidth() / (float) GridMap.COLS, getHeight() / (float) GridMap.ROWS);
        float left = (getWidth() - cell * GridMap.COLS) / 2f;
        float top = 8f;
        paint.setTextAlign(Paint.Align.CENTER);
        paint.setTextSize(Math.max(16f, cell * 0.42f));
        for (int r = 0; r < GridMap.ROWS; r++) {
            for (int c = 0; c < GridMap.COLS; c++) {
                char token = result == null ? map.token(r, c) : frameCells[r * GridMap.COLS + c];
                float x = left + c * cell;
                float y = top + r * cell;
                paint.setStyle(Paint.Style.FILL);
                paint.setColor(colorFor(token));
                canvas.drawRect(x, y, x + cell, y + cell, paint);
                if (pathCells.contains(r * GridMap.COLS + c)) {
                    paint.setStyle(Paint.Style.STROKE);
                    paint.setStrokeWidth(4f);
                    paint.setColor(Color.rgb(45, 156, 111));
                    canvas.drawRect(x + 3, y + 3, x + cell - 3, y + cell - 3, paint);
                }
                paint.setStyle(Paint.Style.STROKE);
                paint.setStrokeWidth(1f);
                paint.setColor(Color.argb(80, 0, 0, 0));
                canvas.drawRect(x, y, x + cell, y + cell, paint);
                if (token != '.') {
                    paint.setStyle(Paint.Style.FILL);
                    paint.setColor(token == '#' ? Color.WHITE : Color.rgb(25, 30, 25));
                    canvas.drawText(labelFor(token), x + cell / 2f, y + cell * 0.65f, paint);
                }
            }
        }
    }

    @Override
    public boolean onTouchEvent(MotionEvent event) {
        if (event.getAction() != MotionEvent.ACTION_DOWN && event.getAction() != MotionEvent.ACTION_MOVE) return true;
        float cell = Math.min(getWidth() / (float) GridMap.COLS, getHeight() / (float) GridMap.ROWS);
        float left = (getWidth() - cell * GridMap.COLS) / 2f;
        float top = 8f;
        int c = (int) ((event.getX() - left) / cell);
        int r = (int) ((event.getY() - top) / cell);
        if (r <= 0 || c <= 0 || r >= GridMap.ROWS - 1 || c >= GridMap.COLS - 1) return true;
        if (brush == 'P') clearPlayer();
        map.setToken(r, c, brush);
        map.rebuildObjects();
        result = null;
        animationStep = 0;
        rebuildPath();
        rebuildFrame();
        invalidate();
        if (editListener != null) editListener.onMapEdited();
        return true;
    }

    private void clearPlayer() {
        for (int r = 1; r < GridMap.ROWS - 1; r++) {
            for (int c = 1; c < GridMap.COLS - 1; c++) {
                if (map.token(r, c) == 'P') map.setToken(r, c, '.');
            }
        }
    }

    private int colorFor(char token) {
        if (token == '#') return Color.rgb(41, 50, 41);
        if (token == 'P') return Color.rgb(77, 182, 255);
        if (token >= '1' && token <= '4') return Color.rgb(217, 93, 79);
        if (token >= 'a' && token <= 'd') return Color.rgb(101, 189, 97);
        if (token == 'X') return Color.rgb(243, 199, 74);
        return Color.rgb(238, 231, 214);
    }

    private String labelFor(char token) {
        if (token == 'P') return headingLabel(frameHeading);
        if (token >= '1' && token <= '4') return "B" + token;
        if (token >= 'a' && token <= 'd') return "T" + (token - 'a' + 1);
        return Character.toString(token);
    }

    private int boxAt(Cell[] boxes, Cell cell) {
        for (int id = 1; id < boxes.length; id++) {
            Cell box = boxes[id];
            if (box != null && box.equals(cell)) return id;
        }
        return -1;
    }

    private boolean isGoalCell(int boxId, Cell cell) {
        char goalToken = (char) ('a' + boxId - 1);
        return inside(cell.row, cell.col) && map.token(cell.row, cell.col) == goalToken;
    }

    private int bombAt(Cell[] bombs, Cell cell) {
        for (int i = 0; i < bombs.length; i++) {
            Cell bomb = bombs[i];
            if (bomb != null && bomb.equals(cell)) return i;
        }
        return -1;
    }

    private void explodeAt(Cell target) {
        for (int r = target.row - 1; r <= target.row + 1; r++) {
            for (int c = target.col - 1; c <= target.col + 1; c++) {
                if (!inside(r, c) || isBoundaryWall(r, c)) continue;
                int index = r * GridMap.COLS + c;
                if (frameCells[index] == '#') frameCells[index] = '.';
            }
        }
    }

    private static char leftHeading(char heading) {
        char h = Character.toUpperCase(heading);
        if (h == 'U') return 'L';
        if (h == 'L') return 'D';
        if (h == 'D') return 'R';
        return 'U';
    }

    private static char rightHeading(char heading) {
        char h = Character.toUpperCase(heading);
        if (h == 'U') return 'R';
        if (h == 'R') return 'D';
        if (h == 'D') return 'L';
        return 'U';
    }

    private static int dirDr(char heading) {
        char h = Character.toUpperCase(heading);
        if (h == 'U') return -1;
        if (h == 'D') return 1;
        return 0;
    }

    private static int dirDc(char heading) {
        char h = Character.toUpperCase(heading);
        if (h == 'L') return -1;
        if (h == 'R') return 1;
        return 0;
    }

    private static String headingLabel(char heading) {
        char h = Character.toUpperCase(heading);
        if (h == 'L') return "←";
        if (h == 'U') return "↑";
        if (h == 'D') return "↓";
        return "→";
    }

    private static boolean inside(int row, int col) {
        return row >= 0 && col >= 0 && row < GridMap.ROWS && col < GridMap.COLS;
    }

    private static boolean isBoundaryWall(int row, int col) {
        return row == 0 || col == 0 || row == GridMap.ROWS - 1 || col == GridMap.COLS - 1;
    }

    public interface EditListener {
        void onMapEdited();
    }
}
