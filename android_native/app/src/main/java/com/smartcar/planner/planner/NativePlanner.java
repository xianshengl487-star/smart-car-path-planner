package com.smartcar.planner.planner;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.PriorityQueue;

public final class NativePlanner {
    private static final int[][] DIRS = {
        {0, -1, 'L'}, {-1, 0, 'U'}, {1, 0, 'D'}, {0, 1, 'R'},
    };
    private static final char[] HEADINGS = {'L', 'U', 'D', 'R'};
    private static final int[] LEFT_HEADING_INDEX = {2, 0, 3, 1};
    private static final int[] RIGHT_HEADING_INDEX = {1, 3, 0, 2};
    private final HashMap<String, int[][]> pushDistanceCache = new HashMap<>();
    private final ReachWorkspace reachWorkspace = new ReachWorkspace();
    // Cell cache: avoid thousands of small allocations per search.
    private static final Cell[][] CELL_CACHE = new Cell[GridMap.ROWS][GridMap.COLS];
    static {
        for (int r = 0; r < GridMap.ROWS; r++)
            for (int c = 0; c < GridMap.COLS; c++)
                CELL_CACHE[r][c] = new Cell(r, c);
    }
    private static Cell cell(int row, int col) { return CELL_CACHE[row][col]; }
    // Precomputed nearest-wall distance for each cell (Manhattan).
    private int[][] nearestWallDist = new int[GridMap.ROWS][GridMap.COLS];
    private int[] lastWallDistKey = new int[0];
    private static final int INF_DIST = 999;
    // Simple deadlock zone: positions from which no box can reach any goal.
    // Recomputed lazily when destroyedWalls changes (explosions destroy walls,
    // shrinking the zone).
    private boolean[] deadlockZone;
    private int[] lastDeadlockZoneKey = new int[0];

    // ======================================================================
    // solve() -- public entry point
    // ======================================================================
    public PlannerResult solve(GridMap input, PerformanceLimits limits) {
        pushDistanceCache.clear();
        GridMap map = input.copy();
        map.rebuildObjects();
        PlannerResult result = new PlannerResult();
        GridMap.ValidationResult validation = map.validate();
        if (!validation.ok) { result.message = validation.message; return result; }

        long startMillis = System.currentTimeMillis();
        Cell pushStart = map.player;
        char pushStartHeading = map.startHeading;
        if (map.requiresRecognition) {
            RecognitionPlan plan = planRecognition(map);
            if (!plan.ok) { result.message = plan.message; return result; }
            result.actions.addAll(plan.actions);
            result.playerPath.addAll(plan.path);
            result.recognitionOrder.addAll(plan.order);
            result.recognitionCost = plan.actions.size();
            pushStart = plan.path.get(plan.path.size() - 1);
            pushStartHeading = plan.headings.get(plan.headings.size() - 1);
        } else {
            result.playerPath.add(map.player);
        }

        SearchResult search = searchPushPlan(map, pushStart, pushStartHeading, limits, startMillis, result.actions.size());
        result.solved = search.solved;
        result.message = search.message;
        result.expanded = search.expanded;
        result.maxFrontierSeen = search.maxFrontierSeen;
        result.prunedByDeadlock = search.prunedByDeadlock;
        result.prunedByActionLimit = search.prunedByActionLimit;
        result.prunedByBestCost = search.prunedByBestCost;
        result.prunedByFrontierTrim = search.prunedByFrontierTrim;
        result.timeoutHit = search.timeoutHit;
        result.expandedLimitHit = search.expandedLimitHit;
        result.frontierLimitHit = search.frontierLimitHit;
        result.actionLimitHit = search.actionLimitHit;
        result.bombMovesGenerated = search.bombMovesGenerated;
        result.bombExplosionsGenerated = search.bombExplosionsGenerated;
        result.bombMovesPruned = search.bombMovesPruned;
        result.bombRelevantWallPruned = search.bombRelevantWallPruned;
        result.bombPriorityUsed = search.bombPriorityUsed;
        result.bombDepthPruned = search.bombDepthPruned;
        if (!search.solved) {
            // Recognition succeeded but push search failed. Still expose
            // recognition actions and cost so the UI can animate them.
            if (result.recognitionCost > 0) {
                result.totalCost = result.recognitionCost;
            }
            return result;
        }

        result.actions.addAll(search.actions);
        result.playerPath.addAll(search.pathWithoutFirst());
        result.pushes = search.pushes;
        result.totalCost = result.actions.size();
        if (limits.enforceActionLimitDuringSearch && result.actions.size() > limits.maxTotalActions) {
            result.solved = false;
            result.actionLimitHit = true;
            result.message = "动作数超过限制: " + result.actions.size() + " > " + limits.maxTotalActions;
        }
        return result;
    }

    // ======================================================================
    // searchPushPlan() -- main A* loop
    // ======================================================================
    private SearchResult searchPushPlan(GridMap map, Cell startPlayer, char startHeading,
        PerformanceLimits limits, long startMillis, int actionOffset) {

        SearchResult failed = new SearchResult();
        Cell[] startBoxes = orderedBoxes(map);
        Cell[] startBombs = orderedBombs(map);
        int[] startDestroyedWalls = new int[0];
        PriorityQueue<Node> open = new PriorityQueue<>(NativePlanner::compareNodes);
        HashMap<String, Integer> best = new HashMap<>();

        // Precompute wall relevance scores for bomb move scoring.
        int[] wallScore = precomputeWallScores(map, startBoxes);
        // Precompute nearest destructible wall distance per cell (avoids O(n²) scan per bomb move).
        precomputeNearestWallDist(map, startDestroyedWalls);
        // Precompute simple deadlock zone: positions unreachable from any goal.
        // Recomputed lazily when destroyedWalls changes (after explosions).
        lastDeadlockZoneKey = new int[0]; // force initial computation
        deadlockZone = computeSimpleDeadlockZone(map, startDestroyedWalls);
        lastDeadlockZoneKey = startDestroyedWalls;

        Node start = new Node(startPlayer, startHeading, startBoxes, startBombs, startDestroyedWalls,
            0, priority(map, limits, 0, startPlayer, startBoxes, startBombs, startDestroyedWalls),
            new ArrayList<>(), new ArrayList<>(), 0);
        start.path.add(startPlayer);
        open.add(start);
        best.put(stateKey(start.player, start.heading, start.boxes, start.bombs, start.destroyedWalls), 0);

        int expanded = 0;
        int maxFrontierSeen = 1;
        boolean hasBombs = map.allowBombPush && hasLiveBomb(startBombs);

        while (!open.isEmpty()) {
            if (Thread.currentThread().isInterrupted()) {
                failed.message = "求解已取消";
                failed.timeoutHit = true;
                failed.expanded = expanded;
                failed.maxFrontierSeen = maxFrontierSeen;
                return failed;
            }
            if (System.currentTimeMillis() - startMillis > limits.maxMillis) {
                failed.message = "达到时间限制 " + limits.maxMillis + "ms，搜索未完成";
                failed.timeoutHit = true;
                failed.expanded = expanded;
                failed.maxFrontierSeen = maxFrontierSeen;
                return failed;
            }
            if (expanded >= limits.maxExpanded) {
                failed.message = limits.enforceActionLimitDuringSearch
                    ? "达到扩展节点限制 " + limits.maxExpanded
                    : "达到搜索节点预算 " + limits.maxExpanded + "（严格模式下仍无法找到更优解）";
                failed.expandedLimitHit = true;
                failed.expanded = expanded;
                failed.maxFrontierSeen = maxFrontierSeen;
                return failed;
            }

            Node node = open.poll();
            String nodeKey = stateKey(node.player, node.heading, node.boxes, node.bombs, node.destroyedWalls);
            Integer known = best.get(nodeKey);
            if (known == null || known != node.g) continue;
            expanded++;

            if (isGoal(map, node.boxes)) {
                SearchResult ok = new SearchResult();
                ok.solved = true; ok.message = "Solved"; ok.actions = node.actions; ok.path = node.path;
                ok.pushes = countPushes(node.actions); ok.expanded = expanded; ok.maxFrontierSeen = maxFrontierSeen;
                ok.prunedByDeadlock = failed.prunedByDeadlock;
                ok.prunedByActionLimit = failed.prunedByActionLimit;
                ok.prunedByBestCost = failed.prunedByBestCost;
                ok.prunedByFrontierTrim = failed.prunedByFrontierTrim;
                ok.bombMovesGenerated = failed.bombMovesGenerated;
                ok.bombExplosionsGenerated = failed.bombExplosionsGenerated;
                ok.bombMovesPruned = failed.bombMovesPruned;
                ok.bombRelevantWallPruned = failed.bombRelevantWallPruned;
                ok.bombPriorityUsed = failed.bombPriorityUsed;
                ok.bombDepthPruned = failed.bombDepthPruned;
                return ok;
            }

            Occupancy occupancy = buildOccupancy(node.boxes, node.bombs);
            Reachability reach = computeReachability(map, node, occupancy);

            // --- Expansion order ---
            // When bombs are live, ALWAYS expand bomb moves first to seed the
            // open list with bomb-relevant states. This is an ENUMERATION
            // ORDER preference only. In strict mode no f-bias is applied, so
            // A* still explores in correct f-order; bomb states simply appear
            // earlier in the queue and get dequeued first when f is equal.
            // Box moves are always enumerated and never skipped.
            boolean bombFirst = hasBombs && hasLiveBomb(node.bombs);

            if (bombFirst) {
                expandBombMoves(map, limits, actionOffset, open, best, node,
                    occupancy, reach, failed, wallScore);
                maxFrontierSeen = Math.max(maxFrontierSeen, failed.maxFrontierSeen);
                if (failed.frontierLimitHit || failed.message.startsWith("达到")) {
                    failed.expanded = expanded; failed.maxFrontierSeen = maxFrontierSeen; return failed;
                }
            }

            expandBoxMoves(map, limits, actionOffset, open, best, node,
                occupancy, reach, failed, wallScore);
            maxFrontierSeen = Math.max(maxFrontierSeen, failed.maxFrontierSeen);
            if (failed.frontierLimitHit || failed.message.startsWith("达到")) {
                failed.expanded = expanded; failed.maxFrontierSeen = maxFrontierSeen; return failed;
            }

            if (!bombFirst) {
                expandBombMoves(map, limits, actionOffset, open, best, node,
                    occupancy, reach, failed, wallScore);
                maxFrontierSeen = Math.max(maxFrontierSeen, failed.maxFrontierSeen);
                if (failed.frontierLimitHit || failed.message.startsWith("达到")) {
                    failed.expanded = expanded; failed.maxFrontierSeen = maxFrontierSeen; return failed;
                }
            }
        }

        failed.message = failed.prunedByActionLimit > 0
            ? "搜索队列为空，所有候选状态均因动作数限制 (maxPushActions=" + limits.maxPushActions + ") 被剪枝"
            : "搜索队列为空，无法到达目标（真无解）";
        failed.expanded = expanded;
        failed.maxFrontierSeen = maxFrontierSeen;
        return failed;
    }

    // ======================================================================
    // expandBoxMoves() -- enumerate box pushes
    // ======================================================================
    private void expandBoxMoves(GridMap map, PerformanceLimits limits, int actionOffset,
        PriorityQueue<Node> open, HashMap<String, Integer> best, Node node,
        Occupancy occupancy, Reachability reach, SearchResult failed, int[] wallScore) {

        for (int boxIndex = 0; boxIndex < node.boxes.length; boxIndex++) {
            Cell box = node.boxes[boxIndex];
            if (box == null) continue;
            for (int[] dir : DIRS) {
                int dr = dir[0], dc = dir[1];
                char pushHeading = (char) dir[2];
                Cell stance = cell(box.row - dr, box.col - dc);
                if (!reach.canReach(stance, pushHeading)) continue;
                Cell pushed = cell(box.row + dr, box.col + dc);
                if (isWallDynamic(map, pushed.row, pushed.col, node.destroyedWalls)
                    || occupancy.hasBox(pushed) || occupancy.hasBomb(pushed)) continue;

                boolean delivered = pushed.equals(map.goals[boxIndex + 1]);
                // In-place mutation + restore avoids copyCells for the common
                // non-delivered case; appendTransition copies again internally.
                Cell saved = node.boxes[boxIndex];
                node.boxes[boxIndex] = delivered ? null : pushed;
                if (!delivered) {
                    // 1. Existing corner + 2x2 deadlock check.
                    if (isDeadlock(map, pushed, boxIndex + 1, node.boxes, node.destroyedWalls)) {
                        node.boxes[boxIndex] = saved;
                        failed.prunedByDeadlock++; continue;
                    }
                    // 2. Simple deadlock zone: position unreachable from any goal.
                    // Lazily recompute when destroyedWalls changes (after explosion).
                    if (node.destroyedWalls != lastDeadlockZoneKey) {
                        deadlockZone = computeSimpleDeadlockZone(map, node.destroyedWalls);
                        lastDeadlockZoneKey = node.destroyedWalls;
                    }
                    int pushIdx = pushed.index();
                    if (deadlockZone != null && pushIdx < deadlockZone.length
                        && deadlockZone[pushIdx]) {
                        node.boxes[boxIndex] = saved;
                        failed.prunedByDeadlock++; continue;
                    }
                }

                TransitionResult tr = appendTransition(map, limits, actionOffset, open, best, node,
                    node.boxes, node.bombs, node.destroyedWalls, box, pushHeading, reach, stance,
                    Character.toString(pushHeading), 0, node.bombDepthSinceExplosion);
                // Restore parent state.
                node.boxes[boxIndex] = saved;
                updateTransitionStats(failed, tr, maxFrontierSeen(open, tr));
                if (tr.frontierLimitHit) { failed.message = "达到 frontier 大小限制 " + limits.maxFrontier; failed.frontierLimitHit = true; return; }
            }
        }
    }

    // ======================================================================
    // expandBombMoves() -- enumerate bomb pushes / explosions
    // ======================================================================
    private void expandBombMoves(GridMap map, PerformanceLimits limits, int actionOffset,
        PriorityQueue<Node> open, HashMap<String, Integer> best, Node node,
        Occupancy occupancy, Reachability reach, SearchResult failed, int[] wallScore) {

        if (!map.allowBombPush) return;

        // Depth-since-explosion guard: non-strict only.
        if (!limits.strictShortest && limits.bombMoveDepthLimit > 0
            && node.bombDepthSinceExplosion >= limits.bombMoveDepthLimit) {
            failed.bombDepthPruned++; return;
        }

        // Explosion deduplication: track which (targetCell, destroyedWallsHash)
        // combinations have already been generated, so we don't re-generate
        // the same explosion from different stances.
        // Applied in ALL modes since the same explosion from the same position
        // with the same walls always produces the same result.
        HashMap<Long, Boolean> explosionSeen = limits.bombPriorityBias ? new HashMap<>() : null;

        for (int bombIndex = 0; bombIndex < node.bombs.length; bombIndex++) {
            Cell bomb = node.bombs[bombIndex];
            if (bomb == null) continue;
            for (int[] dir : DIRS) {
                int dr = dir[0], dc = dir[1];
                char pushHeading = (char) dir[2];
                Cell stance = cell(bomb.row - dr, bomb.col - dc);
                if (!reach.canReach(stance, pushHeading)) continue;
                Cell target = cell(bomb.row + dr, bomb.col + dc);
                if (occupancy.hasBox(target) || occupancy.hasBomb(target)) continue;

                int[] nextDestroyed = node.destroyedWalls;
                String action;
                int priorityBias = 0;
                boolean isExplosion = false;

                if (isWallDynamic(map, target.row, target.col, node.destroyedWalls)) {
                    // --- Explosion path ---
                    int[] destroyedByExplosion = explosionCells(map, target.row, target.col, node.destroyedWalls);
                    if (destroyedByExplosion.length == 0) continue;

                    // Explosion dedup: same bomb position + same walls = same result.
                    if (explosionSeen != null) {
                        long expKey = explosionKey(target, node.destroyedWalls);
                        if (explosionSeen.containsKey(expKey)) continue;
                        explosionSeen.put(expKey, Boolean.TRUE);
                    }

                    int expScore = bombExplosionScore(map, target, destroyedByExplosion, node.boxes, wallScore);

                    // Non-strict: prune low-value explosions.
                    if (!limits.strictShortest && limits.bombPriorityBias && expScore <= 0) {
                        failed.bombRelevantWallPruned++; continue;
                    }
                    // In-place mutation: set bomb to null (exploded), restore after appendTransition.
                    node.bombs[bombIndex] = null;
                    nextDestroyed = mergeDestroyedWalls(node.destroyedWalls, destroyedByExplosion);
                    action = "X" + (char) dir[2];
                    isExplosion = true;
                    if (limits.bombPriorityBias && !limits.strictShortest) {
                        priorityBias = -20 - Math.min(40, expScore * 5);
                    }
                } else {
                    // --- Non-explosion bomb move ---
                    int targetScore = bombRelevanceScore(map, target, node.boxes, nextDestroyed, wallScore);

                    if (!limits.strictShortest && limits.bombPriorityBias) {
                        if (targetScore <= 0) { failed.bombRelevantWallPruned++; continue; }
                        priorityBias = Math.max(-10, -targetScore);
                    } else if (limits.strictShortest) {
                        if (!hasAdjacentWall(map, target, nextDestroyed)
                            && !isBombMoveTowardAnyWall(map, bomb, target, nextDestroyed)) continue;
                    } else {
                        if (!isBombMoveTowardWall(map, bomb, target, nextDestroyed)) continue;
                    }
                    // In-place mutation: move bomb to target, restore after appendTransition.
                    node.bombs[bombIndex] = target;
                    action = "x" + (char) dir[2];
                }

                int newBombDepth = isExplosion ? 0 : node.bombDepthSinceExplosion + 1;
                TransitionResult tr = appendTransition(map, limits, actionOffset, open, best, node,
                    node.boxes, node.bombs, nextDestroyed, bomb, pushHeading, reach, stance,
                    action, priorityBias, newBombDepth);
                // Restore parent state.
                node.bombs[bombIndex] = bomb;
                // Count only actual insertions, not candidates.
                if (tr.prunedByBestCost == 0 && tr.prunedByActionLimit == 0) {
                    if (isExplosion) failed.bombExplosionsGenerated++;
                    else failed.bombMovesGenerated++;
                }
                updateTransitionStats(failed, tr, maxFrontierSeen(open, tr));
                if (tr.frontierLimitHit) { failed.message = "达到 frontier 大小限制 " + limits.maxFrontier; failed.frontierLimitHit = true; return; }
            }
        }
    }

    /**
     * Generate a dedup key for an explosion: (bombIndex, target cell index,
     * destroyedWallsHash). Same key = same explosion result.
     */
    private long explosionKey(Cell target, int[] destroyedWalls) {
        long key = (long) target.index() << 24;
        int h = 1;
        for (int w : destroyedWalls) h = 31 * h + w;
        return key | (h & 0xFFFFFF);
    }

    private int maxFrontierSeen(PriorityQueue<Node> open, TransitionResult tr) {
        return Math.max(open.size(), tr.maxFrontierSeen);
    }

    private void updateTransitionStats(SearchResult failed, TransitionResult tr, int frontier) {
        failed.prunedByActionLimit += tr.prunedByActionLimit;
        failed.prunedByBestCost += tr.prunedByBestCost;
        failed.prunedByFrontierTrim += tr.prunedByFrontierTrim;
        failed.maxFrontierSeen = Math.max(failed.maxFrontierSeen, frontier);
    }

    // ======================================================================
    // Bomb explosion scoring -- assesses the VALUE of an explosion.
    // ======================================================================

    /** Score how many walls an explosion would destroy. */
    private int explosionWallCount(GridMap map, Cell center, int[] destroyedWalls) {
        int count = 0;
        for (int r = center.row - 1; r <= center.row + 1; r++) {
            for (int c = center.col - 1; c <= center.col + 1; c++) {
                if (!inside(r, c) || isBoundaryWall(r, c)) continue;
                int idx = r * GridMap.COLS + c;
                if (map.token(r, c) == '#' && Arrays.binarySearch(destroyedWalls, idx) < 0) count++;
            }
        }
        return count;
    }

    /**
     * Score an explosion: how many useful walls it destroys.
     * High score = explosion opens paths between boxes and goals.
     * Used by non-strict mode to prune low-value explosions and to set
     * priorityBias. strict mode uses this for ordering but not pruning.
     */
    private int bombExplosionScore(GridMap map, Cell bombTarget, int[] destroyedByExplosion,
        Cell[] boxes, int[] wallScore) {
        int score = 0;
        for (int idx : destroyedByExplosion) {
            score += Math.max(1, wallScore[idx]);
        }
        // Bonus: count how many boxes gain a new open neighbor.
        for (Cell box : boxes) {
            if (box == null) continue;
            for (int[] d : DIRS) {
                int nr = box.row + d[0], nc = box.col + d[1];
                if (!inside(nr, nc)) continue;
                int nidx = nr * GridMap.COLS + nc;
                if (Arrays.binarySearch(destroyedByExplosion, nidx) >= 0) score += 2;
            }
        }
        return score;
    }

    /**
     * Precompute a relevance score for each destructible wall cell.
     * Walls on the bounding box between a box and its goal get higher scores.
     * Walls that separate a box from its goal (on the direct path) get bonus.
     * Walls near通道 (2+ open neighbors) get bonus.
     */
    private int[] precomputeWallScores(GridMap map, Cell[] boxes) {
        int[] scores = new int[GridMap.CELLS];
        for (int i = 0; i < boxes.length; i++) {
            Cell box = boxes[i];
            if (box == null) continue;
            Cell goal = map.goals[i + 1];
            if (goal == null) continue;
            // Bounding box between box and goal.
            int r0 = Math.min(box.row, goal.row), r1 = Math.max(box.row, goal.row);
            int c0 = Math.min(box.col, goal.col), c1 = Math.max(box.col, goal.col);
            for (int r = r0; r <= r1; r++) {
                for (int c = c0; c <= c1; c++) {
                    if (map.token(r, c) == '#' && !isBoundaryWall(r, c)) {
                        scores[r * GridMap.COLS + c] += 2;
                    }
                }
            }
            // Direct line-of-sight walls: walls that sit between box and goal
            // on the shortest path axis get extra bonus.
            if (box.row == goal.row) {
                for (int c = Math.min(box.col, goal.col); c <= Math.max(box.col, goal.col); c++) {
                    if (map.token(box.row, c) == '#' && !isBoundaryWall(box.row, c))
                        scores[box.row * GridMap.COLS + c] += 3;
                }
            }
            if (box.col == goal.col) {
                for (int r = Math.min(box.row, goal.row); r <= Math.max(box.row, goal.row); r++) {
                    if (map.token(r, box.col) == '#' && !isBoundaryWall(r, box.col))
                        scores[r * GridMap.COLS + box.col] += 3;
                }
            }
        }
        // Boost walls near通道 (open neighbors >= 2).
        for (int r = 1; r < GridMap.ROWS - 1; r++) {
            for (int c = 1; c < GridMap.COLS - 1; c++) {
                if (map.token(r, c) == '#' && !isBoundaryWall(r, c)) {
                    int openN = 0;
                    for (int[] d : DIRS) { int nr = r+d[0], nc = c+d[1]; if (inside(nr,nc) && map.token(nr,nc)!='#') openN++; }
                    if (openN >= 2) scores[r * GridMap.COLS + c] += 1;
                }
            }
        }
        return scores;
    }

    /**
     * Score a bomb target cell: sum of relevance of walls in the 3x3 area
     * around the target (walls that WOULD be destroyed if bomb later explodes
     * from this position).
     */
    private int bombRelevanceScore(GridMap map, Cell bombTarget, Cell[] boxes, int[] destroyedWalls, int[] wallScore) {
        int score = 0;
        for (int r = bombTarget.row - 1; r <= bombTarget.row + 1; r++) {
            for (int c = bombTarget.col - 1; c <= bombTarget.col + 1; c++) {
                if (!inside(r, c) || isBoundaryWall(r, c)) continue;
                int idx = r * GridMap.COLS + c;
                if (map.token(r, c) == '#' && Arrays.binarySearch(destroyedWalls, idx) < 0) {
                    score += wallScore[idx];
                }
            }
        }
        return score;
    }

    /**
     * Precompute Manhattan distance to the nearest destructible wall for every
     * cell. Uses BFS from all wall cells simultaneously — O(ROWS*COLS).
     * This replaces the per-call O(ROWS*COLS) scan in isBombMoveTowardAnyWall.
     */
    private void precomputeNearestWallDist(GridMap map, int[] destroyedWalls) {
        // Reset all cells to INF.
        for (int r = 0; r < GridMap.ROWS; r++)
            for (int c = 0; c < GridMap.COLS; c++)
                nearestWallDist[r][c] = INF_DIST;
        // Multi-source BFS from all live wall cells.
        int[] queue = new int[GridMap.CELLS];
        int head = 0, tail = 0;
        for (int r = 1; r < GridMap.ROWS - 1; r++) {
            for (int c = 1; c < GridMap.COLS - 1; c++) {
                if (map.token(r, c) == '#' && Arrays.binarySearch(destroyedWalls, r * GridMap.COLS + c) < 0) {
                    nearestWallDist[r][c] = 0;
                    queue[tail++] = r * GridMap.COLS + c;
                }
            }
        }
        while (head < tail) {
            int cell = queue[head++];
            int r = cell / GridMap.COLS, c = cell % GridMap.COLS;
            int nd = nearestWallDist[r][c] + 1;
            for (int[] d : DIRS) {
                int nr = r + d[0], nc = c + d[1];
                if (inside(nr, nc) && nearestWallDist[nr][nc] == INF_DIST) {
                    nearestWallDist[nr][nc] = nd;
                    queue[tail++] = nr * GridMap.COLS + nc;
                }
            }
        }
    }

    /** Check if target is closer to ANY destructible wall than bomb's current position. */
    private boolean isBombMoveTowardAnyWall(GridMap map, Cell bomb, Cell target, int[] destroyedWalls) {
        // Lazy recompute: rebuild when destroyedWalls reference changed (explosion occurred).
        // mergeDestroyedWalls always creates a new array, so reference != triggers rebuild.
        if (destroyedWalls != lastWallDistKey) {
            precomputeNearestWallDist(map, destroyedWalls);
            lastWallDistKey = destroyedWalls;
        }
        return nearestWallDist[target.row][target.col] < nearestWallDist[bomb.row][bomb.col];
    }

    /**
     * Quick check: is there any wall adjacent to the target cell?
     * This is a cheap O(1) check that catches most cases where the bomb
     * is about to be in explosion range.
     */
    private boolean hasAdjacentWall(GridMap map, Cell cell, int[] destroyedWalls) {
        for (int[] d : DIRS) {
            int nr = cell.row + d[0], nc = cell.col + d[1];
            if (!inside(nr, nc) || isBoundaryWall(nr, nc)) continue;
            if (map.token(nr, nc) == '#' && Arrays.binarySearch(destroyedWalls, nr * GridMap.COLS + nc) < 0) return true;
        }
        return false;
    }

    // ======================================================================
    // appendTransition() -- add a node to the open list
    // ======================================================================
    private TransitionResult appendTransition(GridMap map, PerformanceLimits limits, int actionOffset,
        PriorityQueue<Node> open, HashMap<String, Integer> best, Node node,
        Cell[] nextBoxes, Cell[] nextBombs, int[] nextDestroyedWalls,
        Cell nextPlayer, char nextHeading, Reachability reach, Cell stance,
        String pushAction, int priorityBias, int bombDepthSinceExplosion) {

        // Defer expensive allocations until after pruning checks.
        ArrayList<String> walkActions = reach.actionsTo(stance, nextHeading);
        int nextCost = node.g + walkActions.size() + 1;
        TransitionResult result = new TransitionResult(open.size());

        if (limits.enforceActionLimitDuringSearch && actionOffset + nextCost > limits.maxPushActions) {
            result.prunedByActionLimit = 1; return result;
        }
        String sk = stateKey(nextPlayer, nextHeading, nextBoxes, nextBombs, nextDestroyedWalls);
        if (nextCost >= best.getOrDefault(sk, Integer.MAX_VALUE)) {
            result.prunedByBestCost = 1; return result;
        }
        best.put(sk, nextCost);

        // Now that we know the candidate survives pruning, allocate the lists.
        ArrayList<String> actions = new ArrayList<>(node.actions.size() + walkActions.size() + 1);
        actions.addAll(node.actions);
        actions.addAll(walkActions);
        actions.add(pushAction);
        ArrayList<Cell> path = new ArrayList<>(node.path.size() + walkActions.size() + 1);
        path.addAll(node.path);
        path.addAll(reach.pathTo(stance, nextHeading));
        path.add(nextPlayer);

        int f = priority(map, limits, nextCost, nextPlayer, nextBoxes, nextBombs, nextDestroyedWalls);
        if (priorityBias != 0 && limits.bombPriorityBias && !limits.strictShortest) {
            f += priorityBias;
        }
        open.add(new Node(nextPlayer, nextHeading, copyCells(nextBoxes), copyCells(nextBombs),
            nextDestroyedWalls, nextCost, f, actions, path, bombDepthSinceExplosion));

        if (limits.enforceFrontierLimitDuringSearch && limits.trimFrontier) {
            int before = open.size();
            trimFrontier(open, limits.maxFrontier);
            result.prunedByFrontierTrim = before - open.size();
        }
        result.maxFrontierSeen = Math.max(result.maxFrontierSeen, open.size());
        result.frontierLimitHit = limits.enforceFrontierLimitDuringSearch
            && !limits.trimFrontier && open.size() > limits.maxFrontier;
        return result;
    }

    // ======================================================================
    // Recognition (unchanged)
    // ======================================================================
    private RecognitionPlan planRecognition(GridMap map) {
        ArrayList<RecognitionObject> objects = new ArrayList<>();
        for (int id = 1; id <= map.boxCount; id++) if (map.boxes[id] != null) objects.add(new RecognitionObject("B" + id, map.boxes[id]));
        for (int id = 1; id <= map.boxCount; id++) if (map.goals[id] != null) objects.add(new RecognitionObject("T" + id, map.goals[id]));
        if (map.scanBombs) for (int i = 0; i < map.bombCount; i++) objects.add(new RecognitionObject("X" + (i + 1), map.bombs[i]));
        int fullMask = (1 << objects.size()) - 1;
        int poseCount = GridMap.CELLS * 4;
        int stateCount = poseCount * (fullMask + 1);
        int[] frontMask = new int[poseCount], leftPose = new int[poseCount], rightPose = new int[poseCount], forwardPose = new int[poseCount];
        buildRecognitionTables(map, objects, frontMask, leftPose, rightPose, forwardPose);
        int[] parent = new int[stateCount]; byte[] action = new byte[stateCount];
        Arrays.fill(parent, -2);
        ArrayDeque<Integer> queue = new ArrayDeque<>();
        int startPose = poseIndex(map.player, map.startHeading);
        int startState = frontMask[startPose] * poseCount + startPose;
        parent[startState] = -1; queue.add(startState);
        while (!queue.isEmpty()) {
            int state = queue.removeFirst();
            int mask = state / poseCount, pose = state % poseCount;
            if (mask == fullMask) return reconstructRecognitionPlan(state, poseCount, parent, action, objects);
            addRecognitionTransition(queue, parent, action, frontMask, poseCount, mask, state, leftPose[pose], (byte) 1);
            addRecognitionTransition(queue, parent, action, frontMask, poseCount, mask, state, rightPose[pose], (byte) 2);
            addRecognitionTransition(queue, parent, action, frontMask, poseCount, mask, state, forwardPose[pose], (byte) 3);
        }
        RecognitionPlan failed = new RecognitionPlan(); failed.message = "无法正面识别所有对象"; return failed;
    }

    private void buildRecognitionTables(GridMap map, ArrayList<RecognitionObject> objects,
        int[] frontMask, int[] leftPose, int[] rightPose, int[] forwardPose) {
        Arrays.fill(forwardPose, -1);
        for (int cell = 0; cell < GridMap.CELLS; cell++) {
            Cell pos = new Cell(cell / GridMap.COLS, cell % GridMap.COLS);
            for (char heading : HEADINGS) {
                int pose = poseIndex(pos, heading);
                leftPose[pose] = poseIndex(pos, leftHeading(heading));
                rightPose[pose] = poseIndex(pos, rightHeading(heading));
                Cell front = new Cell(pos.row + dirDr(heading), pos.col + dirDc(heading));
                frontMask[pose] = objectMask(front, objects);
                if (!map.isWall(front.row, front.col) && !objectOccupied(map, front)) forwardPose[pose] = poseIndex(front, heading);
            }
        }
    }

    private int objectMask(Cell front, ArrayList<RecognitionObject> objects) {
        int mask = 0;
        for (int i = 0; i < objects.size(); i++) if (front.equals(objects.get(i).pos)) mask |= 1 << i;
        return mask;
    }

    private void addRecognitionTransition(ArrayDeque<Integer> queue, int[] parent, byte[] action,
        int[] frontMask, int poseCount, int mask, int state, int nextPose, byte actionKind) {
        if (nextPose < 0) return;
        int nextState = (mask | frontMask[nextPose]) * poseCount + nextPose;
        if (parent[nextState] != -2) return;
        parent[nextState] = state; action[nextState] = actionKind; queue.add(nextState);
    }

    private RecognitionPlan reconstructRecognitionPlan(int goalState, int poseCount, int[] parent, byte[] action, ArrayList<RecognitionObject> objects) {
        ArrayList<Integer> rPoses = new ArrayList<>(); ArrayList<String> rActions = new ArrayList<>();
        int cur = goalState;
        while (cur >= 0) { rPoses.add(cur % poseCount); if (action[cur] != 0) rActions.add(actionName(action[cur])); cur = parent[cur]; }
        RecognitionPlan plan = new RecognitionPlan(); plan.ok = true;
        for (int i = rPoses.size() - 1; i >= 0; i--) { plan.path.add(poseCell(rPoses.get(i))); plan.headings.add(poseHeading(rPoses.get(i))); }
        for (int i = rActions.size() - 1; i >= 0; i--) plan.actions.add(rActions.get(i));
        plan.order = recognitionOrder(plan.path, plan.headings, objects); return plan;
    }

    private static String actionName(byte k) { return k == 1 ? "turn_left" : k == 2 ? "turn_right" : "forward"; }

    private ArrayList<String> recognitionOrder(List<Cell> path, List<Character> headings, ArrayList<RecognitionObject> objects) {
        ArrayList<String> order = new ArrayList<>(); boolean[] seen = new boolean[objects.size()];
        for (int step = 0; step < path.size(); step++) {
            Cell front = new Cell(path.get(step).row + dirDr(headings.get(step)), path.get(step).col + dirDc(headings.get(step)));
            for (int i = 0; i < objects.size(); i++) { if (!seen[i] && front.equals(objects.get(i).pos)) { seen[i] = true; order.add(objects.get(i).label); } }
        }
        return order;
    }

    // ======================================================================
    // Reachability BFS
    // ======================================================================
    private Reachability computeReachability(GridMap map, Node node, Occupancy occupancy) {
        ReachWorkspace ws = reachWorkspace; ws.nextSearch();
        int remaining = markTargetPoses(map, node, occupancy, ws);
        int head = 0, startPose = poseIndex(node.player, node.heading);
        ws.seenStamp[startPose] = ws.searchGeneration; ws.prev[startPose] = -1; ws.action[startPose] = 0;
        if (ws.targetStamp[startPose] == ws.targetGeneration) remaining--;
        ws.queue[ws.tail++] = startPose;
        while (head < ws.tail && remaining > 0) {
            int cur = ws.queue[head++], cell = cur / 4, hi = cur & 3;
            int row = cell / GridMap.COLS, col = cell % GridMap.COLS;
            if (addPoseTransition(ws, cur, cell, LEFT_HEADING_INDEX[hi], (byte) 1)) remaining--;
            if (addPoseTransition(ws, cur, cell, RIGHT_HEADING_INDEX[hi], (byte) 2)) remaining--;
            int nr = row + DIRS[hi][0], nc = col + DIRS[hi][1];
            if (inside(nr, nc)) {
                int nextCell = nr * GridMap.COLS + nc;
                if (!isWallDynamic(map, nr, nc, node.destroyedWalls) && occupancy.boxAt[nextCell] < 0 && occupancy.bombAt[nextCell] < 0) {
                    if (addPoseTransition(ws, cur, nextCell, hi, (byte) 3)) remaining--;
                }
            }
        }
        return new Reachability(startPose, ws.searchGeneration, ws.seenStamp, ws.prev, ws.action);
    }

    private boolean addPoseTransition(ReachWorkspace ws, int cur, int nextCell, int nextHi, byte act) {
        int next = nextCell * 4 + nextHi;
        if (ws.seenStamp[next] == ws.searchGeneration) return false;
        ws.seenStamp[next] = ws.searchGeneration; ws.prev[next] = cur; ws.action[next] = act; ws.queue[ws.tail++] = next;
        return ws.targetStamp[next] == ws.targetGeneration;
    }

    private int markTargetPoses(GridMap map, Node node, Occupancy occupancy, ReachWorkspace ws) {
        int count = 0;
        for (Cell box : node.boxes) count += markMovableTargets(map, node, occupancy, ws, box);
        if (map.allowBombPush) for (Cell bomb : node.bombs) count += markMovableTargets(map, node, occupancy, ws, bomb);
        return count;
    }

    private int markMovableTargets(GridMap map, Node node, Occupancy occupancy, ReachWorkspace ws, Cell movable) {
        if (movable == null) return 0;
        int count = 0;
        for (int[] dir : DIRS) {
            int sr = movable.row - dir[0], sc = movable.col - dir[1];
            if (!inside(sr, sc) || isWallDynamic(map, sr, sc, node.destroyedWalls)) continue;
            int si = sr * GridMap.COLS + sc;
            if (occupancy.boxAt[si] >= 0 || occupancy.bombAt[si] >= 0) continue;
            int pose = si * 4 + headingIndex((char) dir[2]);
            if (ws.targetStamp[pose] != ws.targetGeneration) { ws.targetStamp[pose] = ws.targetGeneration; count++; }
        }
        return count;
    }

    // ======================================================================
    // Heuristic -- reverse push distances (admissible for numbered boxes).
    // For numbered boxes (B1→T1 fixed), simpleSum IS the correct admissible
    // heuristic. minAssignment would be weaker (allows B1→T2 reassignment).
    // ======================================================================
    private int heuristic(GridMap map, Cell[] boxes, Cell[] bombs, int[] destroyedWalls) {
        if (allBoxesDelivered(boxes)) return 0;
        int[][] pushDist = pushDistances(map, destroyedWalls);
        int value = 0;
        for (int i = 0; i < boxes.length; i++) {
            if (boxes[i] != null && map.goals[i + 1] != null) {
                int dist = (pushDist != null && i < pushDist.length) ? pushDist[i][boxes[i].index()] : -1;
                value += dist >= 0 ? dist : Math.abs(boxes[i].row - map.goals[i + 1].row) + Math.abs(boxes[i].col - map.goals[i + 1].col);
            }
        }
        return value;
    }

    private int priority(GridMap map, PerformanceLimits limits, int cost,
        Cell player, Cell[] boxes, Cell[] bombs, int[] destroyedWalls) {
        return cost + heuristic(map, boxes, bombs, destroyedWalls) * Math.max(1, limits.heuristicWeight);
    }

    private Cell[] orderedBoxes(GridMap map) { Cell[] o = new Cell[map.boxCount]; for (int id = 1; id <= map.boxCount; id++) o[id - 1] = map.boxes[id]; return o; }
    private Cell[] orderedBombs(GridMap map) { Cell[] o = new Cell[map.bombCount]; for (int i = 0; i < map.bombCount; i++) o[i] = map.bombs[i]; return o; }
    private boolean allBoxesDelivered(Cell[] boxes) { for (Cell b : boxes) if (b != null) return false; return true; }
    private boolean hasLiveBomb(Cell[] bombs) { for (Cell b : bombs) if (b != null) return true; return false; }

    private int[][] pushDistances(GridMap map, int[] destroyedWalls) {
        String key = destroyedWallsKey(destroyedWalls);
        int[][] cached = pushDistanceCache.get(key);
        if (cached != null) return cached;
        int[][] dist = new int[Math.max(0, map.boxCount)][GridMap.CELLS];
        for (int i = 0; i < dist.length; i++) { Arrays.fill(dist[i], -1); Cell g = map.goals[i + 1]; if (g != null) fillReversePushDistances(map, g, destroyedWalls, dist[i]); }
        pushDistanceCache.put(key, dist); return dist;
    }

    private String destroyedWallsKey(int[] w) { if (w.length == 0) return ""; StringBuilder sb = new StringBuilder(w.length * 4); for (int v : w) sb.append(v).append(','); return sb.toString(); }

    private void fillReversePushDistances(GridMap map, Cell goal, int[] destroyedWalls, int[] dist) {
        ArrayDeque<Integer> q = new ArrayDeque<>(); dist[goal.index()] = 0; q.add(goal.index());
        while (!q.isEmpty()) {
            int cell = q.removeFirst(), row = cell / GridMap.COLS, col = cell % GridMap.COLS, nd = dist[cell] + 1;
            for (int[] dir : DIRS) {
                int pr = row - dir[0], pc = col - dir[1], sr = pr - dir[0], sc = pc - dir[1];
                if (!inside(pr, pc) || !inside(sr, sc) || isWallDynamic(map, pr, pc, destroyedWalls) || isWallDynamic(map, sr, sc, destroyedWalls)) continue;
                int prev = pr * GridMap.COLS + pc;
                if (dist[prev] >= 0) continue; dist[prev] = nd; q.add(prev);
            }
        }
    }

    // ======================================================================
    // Utilities
    // ======================================================================
    private static int compareNodes(Node a, Node b) { return a.f != b.f ? Integer.compare(a.f, b.f) : Integer.compare(b.g, a.g); }

    private void trimFrontier(PriorityQueue<Node> open, int max) {
        if (max <= 0 || open.size() <= max) return;
        ArrayList<Node> nodes = new ArrayList<>(open); nodes.sort(NativePlanner::compareNodes);
        open.clear(); for (int i = 0; i < max && i < nodes.size(); i++) open.add(nodes.get(i));
    }

    private boolean isGoal(GridMap map, Cell[] boxes) { return allBoxesDelivered(boxes); }

    private boolean isDeadlock(GridMap map, Cell pos, int boxId, Cell[] boxes, int[] destroyedWalls) {
        Cell goal = map.goals[boxId]; if (goal != null && goal.equals(pos)) return false;
        boolean u = isWallDynamic(map, pos.row - 1, pos.col, destroyedWalls), d = isWallDynamic(map, pos.row + 1, pos.col, destroyedWalls);
        boolean l = isWallDynamic(map, pos.row, pos.col - 1, destroyedWalls), r = isWallDynamic(map, pos.row, pos.col + 1, destroyedWalls);
        if ((u && l) || (u && r) || (d && l) || (d && r)) return true;
        int bi = pos.index();
        for (int top = pos.row - 1; top <= pos.row; top++) {
            for (int lft = pos.col - 1; lft <= pos.col; lft++) {
                boolean cb = false, cg = false, blocked = true;
                for (int rr = top; rr <= top + 1; rr++) for (int cc = lft; cc <= lft + 1; cc++) {
                    if (!inside(rr, cc)) { blocked = false; continue; }
                    int idx = rr * GridMap.COLS + cc; if (idx == bi) cb = true;
                    for (int id = 1; id <= map.boxCount; id++) { Cell g = map.goals[id]; if (g != null && g.row == rr && g.col == cc) cg = true; }
                    if (!isWallDynamic(map, rr, cc, destroyedWalls) && !hasBoxAtIndex(boxes, idx)) blocked = false;
                }
                if (cb && !cg && blocked) return true;
            }
        }
        return false;
    }

    private boolean hasBoxAtIndex(Cell[] boxes, int idx) { for (Cell b : boxes) if (b != null && b.index() == idx) return true; return false; }

    private int countRemainingBoxes(Cell[] boxes) {
        int count = 0;
        for (Cell b : boxes) if (b != null) count++;
        return count;
    }

    private boolean isAdjacentToBox(Cell pos, Cell[] boxes) {
        for (Cell b : boxes) {
            if (b == null) continue;
            if (Math.abs(b.row - pos.row) + Math.abs(b.col - pos.col) == 1) return true;
        }
        return false;
    }

    // ======================================================================
    // Simple deadlock zone: reverse BFS from all goals.
    // Positions unreachable from any goal are dead for any box.
    // Only depends on wall layout — shrinks when walls are destroyed.
    // ======================================================================
    private boolean[] computeSimpleDeadlockZone(GridMap map, int[] destroyedWalls) {
        boolean[] reachable = new boolean[GridMap.CELLS];
        int[] queue = new int[GridMap.CELLS];
        int head = 0, tail = 0;
        // Seed: all goal positions are reachable.
        for (int id = 1; id <= map.boxCount; id++) {
            Cell g = map.goals[id];
            if (g != null) {
                int gi = g.index();
                reachable[gi] = true;
                queue[tail++] = gi;
            }
        }
        // Reverse BFS: from each reachable cell, check if a box could have been
        // pushed there from an adjacent cell (with a stance cell two steps back).
        while (head < tail) {
            int cell = queue[head++];
            int cr = cell / GridMap.COLS, cc = cell % GridMap.COLS;
            for (int[] d : DIRS) {
                int dr = d[0], dc = d[1];
                // previous = cell the box was pushed FROM to reach 'cell'
                int pr = cr - dr, pc = cc - dc;
                if (!inside(pr, pc)) continue;
                int pi = pr * GridMap.COLS + pc;
                if (reachable[pi]) continue;
                if (isWallDynamic(map, pr, pc, destroyedWalls)) continue;
                // stance = cell the car stood on to push from previous to cell
                int sr = pr - dr, sc = pc - dc;
                if (!inside(sr, sc)) continue;
                if (isWallDynamic(map, sr, sc, destroyedWalls)) continue;
                reachable[pi] = true;
                queue[tail++] = pi;
            }
        }
        // Deadlock zone: every non-wall, non-goal cell not reachable.
        boolean[] zone = new boolean[GridMap.CELLS];
        for (int r = 1; r < GridMap.ROWS - 1; r++) {
            for (int c = 1; c < GridMap.COLS - 1; c++) {
                int idx = r * GridMap.COLS + c;
                if (isWallDynamic(map, r, c, destroyedWalls)) continue;
                // Skip goal cells — boxes on goals are delivered.
                if (map.token(r, c) >= 'a' && map.token(r, c) <= 'd') continue;
                if (!reachable[idx]) zone[idx] = true;
            }
        }
        return zone;
    }

    // ======================================================================
    // Frozen group deadlock: fixed-point detection of mutually-blocking boxes.
    // A box is frozen when every push direction is blocked by a wall or
    // another frozen box. Any frozen box NOT on its goal = deadlock.
    // ======================================================================
    private boolean isFrozenGroupDeadlock(GridMap map, Cell[] boxes, int[] destroyedWalls) {
        // Collect non-delivered box indices.
        int count = 0;
        for (Cell b : boxes) if (b != null) count++;
        if (count == 0) return false;

        int[] boxIdx = new int[count]; // cell indices
        boolean[] onGoal = new boolean[count];
        int n = 0;
        for (int i = 0; i < boxes.length; i++) {
            if (boxes[i] == null) continue;
            boxIdx[n] = boxes[i].index();
            onGoal[n] = (map.goals[i + 1] != null && map.goals[i + 1].equals(boxes[i]));
            n++;
        }

        boolean[] frozen = new boolean[count];
        boolean changed = true;
        int maxIter = GridMap.CELLS;
        int iter = 0;
        while (changed && iter < maxIter) {
            changed = false;
            iter++;
            for (int i = 0; i < n; i++) {
                if (frozen[i] || onGoal[i]) continue;
                int r = boxIdx[i] / GridMap.COLS, c = boxIdx[i] % GridMap.COLS;
                boolean allBlocked = true;
                for (int[] d : DIRS) {
                    int dr = d[0], dc = d[1];
                    int tr = r + dr, tc = c + dc; // target
                    int sr = r - dr, sc = c - dc; // stance
                    if (!inside(tr, tc) || !inside(sr, sc)) continue;
                    if (isWallDynamic(map, tr, tc, destroyedWalls)) continue;
                    if (isWallDynamic(map, sr, sc, destroyedWalls)) continue;
                    // Check if target or stance is occupied by another box.
                    boolean targetBlocked = false, stanceBlocked = false;
                    for (int j = 0; j < n; j++) {
                        if (j == i) continue;
                        int bi = boxIdx[j];
                        if (bi == tr * GridMap.COLS + tc) {
                            if (!frozen[j]) { targetBlocked = false; allBlocked = false; break; }
                            targetBlocked = true;
                        }
                        if (bi == sr * GridMap.COLS + sc) {
                            if (!frozen[j]) { stanceBlocked = false; allBlocked = false; break; }
                            stanceBlocked = true;
                        }
                    }
                    if (!allBlocked) break;
                    if (!targetBlocked && !stanceBlocked) { allBlocked = false; break; }
                }
                if (allBlocked) {
                    frozen[i] = true;
                    changed = true;
                }
            }
        }
        // Any frozen box not on its goal = deadlock.
        for (int i = 0; i < n; i++) {
            if (frozen[i] && !onGoal[i]) return true;
        }
        return false;
    }

    // ======================================================================
    // Minimum assignment heuristic (brute-force for ≤4 boxes, tighter than
    // simple sum). Uses reverse push distances.
    // ======================================================================
    private int minAssignmentHeuristic(GridMap map, Cell[] boxes, int[] destroyedWalls) {
        int n = 0;
        for (Cell b : boxes) if (b != null) n++;
        if (n == 0) return 0;
        if (n == 1) {
            for (int i = 0; i < boxes.length; i++) {
                if (boxes[i] != null) return singleBoxPushDist(map, i, boxes[i], destroyedWalls);
            }
            return 0;
        }
        // Build cost matrix: boxes[i] → goals[i+1]
        int[][] pushDist = pushDistances(map, destroyedWalls);
        // For n ≤ 4, enumerate all permutations.
        if (n <= 4) return minAssignBrute(map, boxes, pushDist, n);
        // Fallback: simple sum (still admissible).
        int sum = 0;
        for (int i = 0; i < boxes.length; i++) {
            if (boxes[i] != null && map.goals[i + 1] != null) {
                int dist = (pushDist != null && i < pushDist.length) ? pushDist[i][boxes[i].index()] : -1;
                sum += dist >= 0 ? dist : Math.abs(boxes[i].row - map.goals[i + 1].row) + Math.abs(boxes[i].col - map.goals[i + 1].col);
            }
        }
        return sum;
    }

    private int minAssignBrute(GridMap map, Cell[] boxes, int[][] pushDist, int n) {
        // Collect non-null box indices and goal indices.
        int[] bi = new int[n]; // box index in boxes array
        int[] gi = new int[n]; // goal index in map.goals (1-based)
        int idx = 0;
        for (int i = 0; i < boxes.length; i++) {
            if (boxes[i] != null) { bi[idx] = i; gi[idx] = i + 1; idx++; }
        }
        // Enumerate all permutations of goal assignments.
        int[] perm = new int[n];
        for (int i = 0; i < n; i++) perm[i] = i;
        int best = Integer.MAX_VALUE;
        do {
            int cost = 0;
            for (int i = 0; i < n; i++) {
                int boxI = bi[i];
                int goalI = gi[perm[i]];
                Cell box = boxes[boxI];
                Cell goal = map.goals[goalI];
                if (box != null && goal != null) {
                    int dist = (pushDist != null && boxI < pushDist.length) ? pushDist[boxI][box.index()] : -1;
                    cost += dist >= 0 ? dist : Math.abs(box.row - goal.row) + Math.abs(box.col - goal.col);
                }
            }
            if (cost < best) best = cost;
        } while (nextPermutation(perm));
        return best;
    }

    private static boolean nextPermutation(int[] a) {
        int n = a.length;
        for (int i = n - 2; i >= 0; i--) {
            if (a[i] < a[i + 1]) {
                int j = n - 1;
                while (a[j] <= a[i]) j--;
                int tmp = a[i]; a[i] = a[j]; a[j] = tmp;
                for (int l = i + 1, r = n - 1; l < r; l++, r--) {
                    tmp = a[l]; a[l] = a[r]; a[r] = tmp;
                }
                return true;
            }
        }
        return false;
    }

    private int singleBoxPushDist(GridMap map, int boxIndex, Cell box, int[] destroyedWalls) {
        Cell goal = map.goals[boxIndex + 1];
        if (goal == null) return 0;
        int[][] pushDist = pushDistances(map, destroyedWalls);
        if (pushDist != null && boxIndex < pushDist.length) {
            int dist = pushDist[boxIndex][box.index()];
            if (dist >= 0) return dist;
        }
        return Math.abs(box.row - goal.row) + Math.abs(box.col - goal.col);
    }

    private boolean objectOccupied(GridMap map, Cell pos) {
        int idx = pos.index();
        for (int id = 1; id <= map.boxCount; id++) if (map.boxes[id] != null && map.boxes[id].index() == idx) return true;
        for (int i = 0; i < map.bombCount; i++) if (map.bombs[i] != null && map.bombs[i].index() == idx) return true;
        return false;
    }

    private Occupancy buildOccupancy(Cell[] boxes, Cell[] bombs) {
        Occupancy o = new Occupancy();
        for (int i = 0; i < boxes.length; i++) if (boxes[i] != null) o.boxAt[boxes[i].index()] = i;
        for (int i = 0; i < bombs.length; i++) if (bombs[i] != null) o.bombAt[bombs[i].index()] = i;
        return o;
    }

    private Cell[] copyCells(Cell[] c) { return Arrays.copyOf(c, c.length); }

    // Reusable char buffer for stateKey to avoid StringBuilder allocation on every call.
    // Must be large enough for worst case: ~96 destroyed walls * 4 chars + boxes/bombs/prefix.
    private char[] stateKeyBuf = new char[512];
    private int stateKeyLen;

    private String stateKey(Cell player, char heading, Cell[] boxes, Cell[] bombs, int[] destroyedWalls) {
        stateKeyLen = 0;
        appendInt(player.index());
        stateKeyBuf[stateKeyLen++] = '@';
        stateKeyBuf[stateKeyLen++] = heading;
        stateKeyBuf[stateKeyLen++] = '|';
        for (Cell box : boxes) { if (box != null) appendInt(box.index()); else stateKeyBuf[stateKeyLen++] = '-'; stateKeyBuf[stateKeyLen++] = ','; }
        stateKeyBuf[stateKeyLen++] = '|';
        // Sort bomb indices to make the key order-independent.
        int[] bi = new int[bombs.length];
        for (int i = 0; i < bombs.length; i++) bi[i] = bombs[i] == null ? -1 : bombs[i].index();
        Arrays.sort(bi);
        for (int v : bi) { if (v >= 0) appendInt(v); else stateKeyBuf[stateKeyLen++] = '-'; stateKeyBuf[stateKeyLen++] = ','; }
        stateKeyBuf[stateKeyLen++] = '|';
        for (int v : destroyedWalls) { appendInt(v); stateKeyBuf[stateKeyLen++] = ','; }
        return new String(stateKeyBuf, 0, stateKeyLen);
    }

    private void appendInt(int v) {
        if (v == 0) { stateKeyBuf[stateKeyLen++] = '0'; return; }
        int start = stateKeyLen;
        while (v > 0) { stateKeyBuf[stateKeyLen++] = (char) ('0' + v % 10); v /= 10; }
        // Reverse the digits.
        for (int i = start, j = stateKeyLen - 1; i < j; i++, j--) {
            char tmp = stateKeyBuf[i]; stateKeyBuf[i] = stateKeyBuf[j]; stateKeyBuf[j] = tmp;
        }
    }

    private int countPushes(ArrayList<String> actions) {
        int c = 0; for (String a : actions) { if (a.length() == 1 && Character.isUpperCase(a.charAt(0))) c++; else if (a.length() == 2 && a.charAt(0) == 'X') c++; } return c;
    }

    private static int headingIndex(char h) { h = Character.toUpperCase(h); return h == 'L' ? 0 : h == 'U' ? 1 : h == 'D' ? 2 : 3; }
    private static char leftHeading(char h) { h = Character.toUpperCase(h); return h == 'U' ? 'L' : h == 'L' ? 'D' : h == 'D' ? 'R' : 'U'; }
    private static char rightHeading(char h) { h = Character.toUpperCase(h); return h == 'U' ? 'R' : h == 'R' ? 'D' : h == 'D' ? 'L' : 'U'; }
    private static int dirDr(char h) { return DIRS[headingIndex(h)][0]; }
    private static int dirDc(char h) { return DIRS[headingIndex(h)][1]; }
    private static int poseIndex(Cell c, char h) { return c.index() * 4 + headingIndex(h); }
    private static Cell poseCell(int pi) { int c = pi / 4; return new Cell(c / GridMap.COLS, c % GridMap.COLS); }
    private static char poseHeading(int pi) { return HEADINGS[pi & 3]; }
    private boolean inside(int r, int c) { return r >= 0 && c >= 0 && r < GridMap.ROWS && c < GridMap.COLS; }

    private boolean isWallDynamic(GridMap map, int r, int c, int[] dw) {
        if (r < 0 || c < 0 || r >= GridMap.ROWS || c >= GridMap.COLS) return true;
        return map.token(r, c) == '#' && Arrays.binarySearch(dw, r * GridMap.COLS + c) < 0;
    }

    private boolean isBoundaryWall(int r, int c) { return r == 0 || c == 0 || r == GridMap.ROWS - 1 || c == GridMap.COLS - 1; }

    private int[] explosionCells(GridMap map, int row, int col, int[] dw) {
        int[] s = new int[9]; int n = 0;
        for (int r = row - 1; r <= row + 1; r++) for (int c = col - 1; c <= col + 1; c++) {
            if (!inside(r, c) || isBoundaryWall(r, c)) continue;
            int idx = r * GridMap.COLS + c;
            if (map.token(r, c) == '#' && Arrays.binarySearch(dw, idx) < 0) s[n++] = idx;
        }
        return Arrays.copyOf(s, n);
    }

    private boolean isBombMoveTowardWall(GridMap map, Cell from, Cell to, int[] dw) {
        return nearestWallDist(map, to, dw) < nearestWallDist(map, from, dw);
    }

    private int nearestWallDist(GridMap map, Cell cell, int[] dw) {
        int best = 9999;
        for (int r = 1; r < GridMap.ROWS - 1; r++) for (int c = 1; c < GridMap.COLS - 1; c++) {
            if (map.token(r, c) != '#' || Arrays.binarySearch(dw, r * GridMap.COLS + c) >= 0) continue;
            int d = Math.abs(cell.row - r) + Math.abs(cell.col - c); if (d < best) best = d;
        }
        return best;
    }

    private int[] mergeDestroyedWalls(int[] cur, int[] add) {
        if (add.length == 0) return cur;
        int[] m = Arrays.copyOf(cur, cur.length + add.length);
        System.arraycopy(add, 0, m, cur.length, add.length); Arrays.sort(m);
        int u = 0; for (int v : m) if (u == 0 || m[u - 1] != v) m[u++] = v;
        return Arrays.copyOf(m, u);
    }

    // ======================================================================
    // Inner classes
    // ======================================================================
    private static final class Node {
        final Cell player; final char heading; final Cell[] boxes; final Cell[] bombs;
        final int[] destroyedWalls; final int g, f;
        final ArrayList<String> actions; final ArrayList<Cell> path;
        final int bombDepthSinceExplosion;
        Node(Cell p, char h, Cell[] b, Cell[] bm, int[] dw, int g, int f, ArrayList<String> a, ArrayList<Cell> pa, int bd) {
            player = p; heading = h; boxes = b; bombs = bm; destroyedWalls = dw; this.g = g; this.f = f; actions = a; path = pa; bombDepthSinceExplosion = bd;
        }
    }

    static final class SearchResult {
        boolean solved; String message = ""; int expanded, maxFrontierSeen, pushes;
        ArrayList<String> actions = new ArrayList<>(); ArrayList<Cell> path = new ArrayList<>();
        int prunedByDeadlock, prunedByActionLimit, prunedByBestCost, prunedByFrontierTrim;
        boolean timeoutHit, expandedLimitHit, frontierLimitHit, actionLimitHit;
        int bombMovesGenerated, bombExplosionsGenerated, bombMovesPruned, bombRelevantWallPruned;
        boolean bombPriorityUsed; int bombDepthPruned;
        List<Cell> pathWithoutFirst() { return path.size() <= 1 ? new ArrayList<>() : path.subList(1, path.size()); }
    }

    static final class TransitionResult {
        boolean frontierLimitHit; int maxFrontierSeen, prunedByActionLimit, prunedByBestCost, prunedByFrontierTrim;
        TransitionResult(int mfs) { maxFrontierSeen = mfs; }
    }

    private static final class Occupancy {
        final int[] boxAt = new int[GridMap.CELLS], bombAt = new int[GridMap.CELLS];
        Occupancy() { Arrays.fill(boxAt, -1); Arrays.fill(bombAt, -1); }
        boolean hasBox(Cell c) { return c.row >= 0 && c.col >= 0 && c.row < GridMap.ROWS && c.col < GridMap.COLS && boxAt[c.index()] >= 0; }
        boolean hasBomb(Cell c) { return c.row >= 0 && c.col >= 0 && c.row < GridMap.ROWS && c.col < GridMap.COLS && bombAt[c.index()] >= 0; }
    }

    private static final class ReachWorkspace {
        final int[] seenStamp = new int[GridMap.CELLS * 4], targetStamp = new int[GridMap.CELLS * 4];
        final int[] prev = new int[GridMap.CELLS * 4]; final byte[] action = new byte[GridMap.CELLS * 4];
        final int[] queue = new int[GridMap.CELLS * 4];
        int searchGeneration = 0, targetGeneration = 0, tail = 0;
        void nextSearch() { searchGeneration++; targetGeneration++; tail = 0;
            if (searchGeneration == Integer.MAX_VALUE || targetGeneration == Integer.MAX_VALUE) { Arrays.fill(seenStamp, 0); Arrays.fill(targetStamp, 0); searchGeneration = 1; targetGeneration = 1; }
        }
    }

    private static final class Reachability {
        final int startPose, generation; final int[] seenStamp, prev; final byte[] action;
        Reachability(int s, int g, int[] seen, int[] prev, byte[] act) { startPose = s; generation = g; seenStamp = seen; this.prev = prev; action = act; }
        boolean canReach(Cell c, char h) { return c.row >= 0 && c.col >= 0 && c.row < GridMap.ROWS && c.col < GridMap.COLS && seenStamp[poseIndex(c, h)] == generation; }
        ArrayList<String> actionsTo(Cell t, char h) {
            ArrayList<String> r = new ArrayList<>(); int cur = poseIndex(t, h);
            while (cur != startPose) { if (cur < 0 || seenStamp[cur] != generation || prev[cur] < 0) return new ArrayList<>(); r.add(NativePlanner.actionName(action[cur])); cur = prev[cur]; }
            ArrayList<String> o = new ArrayList<>(); for (int i = r.size() - 1; i >= 0; i--) o.add(r.get(i)); return o;
        }
        ArrayList<Cell> pathTo(Cell t, char h) {
            ArrayList<Cell> r = new ArrayList<>(); int cur = poseIndex(t, h);
            while (cur != startPose) { if (cur < 0 || seenStamp[cur] != generation || prev[cur] < 0) return new ArrayList<>(); r.add(poseCell(cur)); cur = prev[cur]; }
            ArrayList<Cell> o = new ArrayList<>(); for (int i = r.size() - 1; i >= 0; i--) o.add(r.get(i)); return o;
        }
    }

    private static final class RecognitionObject { final String label; final Cell pos; RecognitionObject(String l, Cell p) { label = l; pos = p; } }
    private static final class RecognitionPlan {
        boolean ok; String message = ""; ArrayList<Cell> path = new ArrayList<>();
        ArrayList<Character> headings = new ArrayList<>(); ArrayList<String> actions = new ArrayList<>(), order = new ArrayList<>();
    }
}
