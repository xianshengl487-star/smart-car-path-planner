package com.smartcar.planner.planner;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.PriorityQueue;

public final class NativePlanner {
    private static final int[][] DIRS = {
        {0, -1, 'L'},
        {-1, 0, 'U'},
        {1, 0, 'D'},
        {0, 1, 'R'},
    };

    private static final char[] HEADINGS = {'L', 'U', 'D', 'R'};
    private static final int[] LEFT_HEADING_INDEX = {2, 0, 3, 1};
    private static final int[] RIGHT_HEADING_INDEX = {1, 3, 0, 2};
    private final HashMap<String, int[][]> pushDistanceCache = new HashMap<>();
    private final ReachWorkspace reachWorkspace = new ReachWorkspace();

    public PlannerResult solve(GridMap input, PerformanceLimits limits) {
        pushDistanceCache.clear();
        GridMap map = input.copy();
        map.rebuildObjects();
        PlannerResult result = new PlannerResult();

        GridMap.ValidationResult validation = map.validate();
        if (!validation.ok) {
            result.message = validation.message;
            return result;
        }

        long startMillis = System.currentTimeMillis();

        Cell pushStart = map.player;
        char pushStartHeading = map.startHeading;
        if (map.requiresRecognition) {
            RecognitionPlan plan = planRecognition(map);
            if (!plan.ok) {
                result.message = plan.message;
                return result;
            }
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
        if (!search.solved) return result;

        result.actions.addAll(search.actions);
        result.playerPath.addAll(search.pathWithoutFirst());
        result.pushes = search.pushes;
        result.totalCost = result.actions.size();
        if (limits.enforceActionLimitDuringSearch && result.actions.size() > limits.maxActions) {
            result.solved = false;
            result.actionLimitHit = true;
            result.message = "动作数超过限制: " + result.actions.size() + " > " + limits.maxActions;
        }
        return result;
    }

    private SearchResult searchPushPlan(
        GridMap map,
        Cell startPlayer,
        char startHeading,
        PerformanceLimits limits,
        long startMillis,
        int actionOffset
    ) {
        SearchResult failed = new SearchResult();
        Cell[] startBoxes = orderedBoxes(map);
        Cell[] startBombs = orderedBombs(map);
        int[] startDestroyedWalls = new int[0];
        PriorityQueue<Node> open = new PriorityQueue<>(NativePlanner::compareNodes);
        HashMap<String, Integer> best = new HashMap<>();

        // Precompute a heuristic score for each destructible wall so that bomb
        // moves can be scored by the relevance of the wall they will eventually
        // destroy (see bombRelevanceScore).
        int[] wallScore = precomputeWallScores(map, startBoxes);

        Node start = new Node(
            startPlayer, startHeading, startBoxes, startBombs, startDestroyedWalls,
            0, priority(map, limits, 0, startPlayer, startBoxes, startBombs, startDestroyedWalls, wallScore),
            new ArrayList<>(), new ArrayList<>(), 0
        );
        start.path.add(startPlayer);
        open.add(start);
        best.put(stateKey(start.player, start.heading, start.boxes, start.bombs, start.destroyedWalls), 0);

        int expanded = 0;
        int maxFrontierSeen = 1;
        while (!open.isEmpty()) {
            // Cancellation support: if the calling thread was interrupted (e.g.
            // Activity destroyed or a future cancel button), return immediately.
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
                if (limits.enforceActionLimitDuringSearch) {
                    failed.message = "达到扩展节点限制 " + limits.maxExpanded;
                } else {
                    failed.message = "达到搜索节点预算 " + limits.maxExpanded + "（严格模式下仍无法找到更优解）";
                }
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
                ok.solved = true;
                ok.message = "Solved";
                ok.actions = node.actions;
                ok.path = node.path;
                ok.pushes = countPushes(node.actions);
                ok.expanded = expanded;
                ok.maxFrontierSeen = maxFrontierSeen;
                // Carry over accumulated diagnostic counters from the search state.
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

            // --- Determine search mode ---
            // preferBombs: in non-strict mode when bombs are live and no wall
            // has been destroyed yet, we expand bomb moves FIRST so that the
            // open list is seeded with bomb-relevant states before box moves.
            // This is an ENUMERATION ORDER preference, NOT a hard constraint.
            // Box pushes are always enumerated; they are simply inserted into
            // the open list after bomb pushes, so A* naturally explores
            // bomb-first paths earlier.
            boolean preferBombs = !limits.strictShortest
                && map.allowBombPush
                && node.destroyedWalls.length == 0
                && hasLiveBomb(node.bombs);

            Occupancy occupancy = buildOccupancy(node.boxes, node.bombs);
            Reachability reach = computeReachability(map, node, occupancy);

            // Bomb moves go first when preferBombs is true.
            if (preferBombs) {
                expandBombMoves(map, limits, actionOffset, open, best, node,
                    occupancy, reach, failed, wallScore, maxFrontierSeen);
                maxFrontierSeen = Math.max(maxFrontierSeen, failed.maxFrontierSeen);
                if (failed.frontierLimitHit || failed.message.startsWith("达到")) return failed;
            }

            expandBoxMoves(map, limits, actionOffset, open, best, node,
                occupancy, reach, failed, wallScore, maxFrontierSeen);
            maxFrontierSeen = Math.max(maxFrontierSeen, failed.maxFrontierSeen);
            if (failed.frontierLimitHit || failed.message.startsWith("达到")) return failed;

            // Box moves go first when preferBombs is false (normal order).
            if (!preferBombs) {
                expandBombMoves(map, limits, actionOffset, open, best, node,
                    occupancy, reach, failed, wallScore, maxFrontierSeen);
                maxFrontierSeen = Math.max(maxFrontierSeen, failed.maxFrontierSeen);
                if (failed.frontierLimitHit || failed.message.startsWith("达到")) return failed;
            }
        }

        if (failed.prunedByActionLimit > 0) {
            failed.message = "搜索队列为空，所有候选状态均因动作数限制 (maxActions=" + limits.maxActions + ") 被剪枝";
        } else {
            failed.message = "搜索队列为空，无法到达目标（真无解）";
        }
        failed.expanded = expanded;
        failed.maxFrontierSeen = maxFrontierSeen;
        return failed;
    }

    // ------------------------------------------------------------------
    // Box move expansion: enumerate all valid box pushes for the current node.
    // ------------------------------------------------------------------
    private void expandBoxMoves(
        GridMap map, PerformanceLimits limits, int actionOffset,
        PriorityQueue<Node> open, HashMap<String, Integer> best,
        Node node, Occupancy occupancy, Reachability reach,
        SearchResult failed, int[] wallScore, int maxFrontierSeen
    ) {
        for (int boxIndex = 0; boxIndex < node.boxes.length; boxIndex++) {
            Cell box = node.boxes[boxIndex];
            if (box == null) continue;
            for (int[] dir : DIRS) {
                int dr = dir[0];
                int dc = dir[1];
                char pushHeading = (char) dir[2];
                Cell stance = new Cell(box.row - dr, box.col - dc);
                if (!reach.canReach(stance, pushHeading)) continue;

                Cell pushed = new Cell(box.row + dr, box.col + dc);
                if (isWallDynamic(map, pushed.row, pushed.col, node.destroyedWalls)
                    || occupancy.hasBox(pushed) || occupancy.hasBomb(pushed)) continue;

                Cell[] nextBoxes = copyCells(node.boxes);
                boolean delivered = pushed.equals(map.goals[boxIndex + 1]);
                nextBoxes[boxIndex] = delivered ? null : pushed;
                if (!delivered && isDeadlock(map, pushed, boxIndex + 1, nextBoxes, node.destroyedWalls)) {
                    failed.prunedByDeadlock++;
                    continue;
                }

                TransitionResult transition = appendBoxTransition(
                    map, limits, actionOffset, open, best, node,
                    nextBoxes, node.bombs, node.destroyedWalls,
                    box, pushHeading, reach, stance,
                    Character.toString(pushHeading), 0
                );
                maxFrontierSeen = Math.max(maxFrontierSeen, transition.maxFrontierSeen);
                failed.prunedByActionLimit += transition.prunedByActionLimit;
                failed.prunedByBestCost += transition.prunedByBestCost;
                failed.prunedByFrontierTrim += transition.prunedByFrontierTrim;
                if (transition.frontierLimitHit) {
                    failed.message = "达到 frontier 大小限制 " + limits.maxFrontier;
                    failed.frontierLimitHit = true;
                    failed.maxFrontierSeen = maxFrontierSeen;
                    return;
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Bomb move expansion: enumerate all valid bomb pushes / explosions.
    // Includes bomb relevance scoring and depth-since-explosion pruning.
    // ------------------------------------------------------------------
    private void expandBombMoves(
        GridMap map, PerformanceLimits limits, int actionOffset,
        PriorityQueue<Node> open, HashMap<String, Integer> best,
        Node node, Occupancy occupancy, Reachability reach,
        SearchResult failed, int[] wallScore, int maxFrontierSeen
    ) {
        if (!map.allowBombPush) return;

        // Depth-since-explosion guard: in non-strict mode, if the node has
        // accumulated too many consecutive bomb moves without any new wall
        // destruction, prune it. This prevents the search from spiralling
        // through infinite bomb shuffles. strict mode ignores this.
        if (!limits.strictShortest && limits.bombMoveDepthLimit > 0
            && node.bombDepthSinceExplosion >= limits.bombMoveDepthLimit) {
            failed.bombDepthPruned++;
            return;
        }

        for (int bombIndex = 0; bombIndex < node.bombs.length; bombIndex++) {
            Cell bomb = node.bombs[bombIndex];
            if (bomb == null) continue;
            for (int[] dir : DIRS) {
                int dr = dir[0];
                int dc = dir[1];
                char pushHeading = (char) dir[2];
                Cell stance = new Cell(bomb.row - dr, bomb.col - dc);
                if (!reach.canReach(stance, pushHeading)) continue;

                Cell target = new Cell(bomb.row + dr, bomb.col + dc);
                if (occupancy.hasBox(target) || occupancy.hasBomb(target)) continue;

                Cell[] nextBombs = copyCells(node.bombs);
                int[] nextDestroyed = node.destroyedWalls;
                String action;
                int priorityBias = 0;
                boolean isExplosion = false;

                if (isWallDynamic(map, target.row, target.col, node.destroyedWalls)) {
                    // Bomb pushes into a wall -> explosion.
                    int[] destroyedByExplosion = explosionCells(map, target.row, target.col, node.destroyedWalls);
                    if (destroyedByExplosion.length == 0) continue;
                    nextBombs[bombIndex] = null;
                    nextDestroyed = mergeDestroyedWalls(node.destroyedWalls, destroyedByExplosion);
                    action = "X" + (char) dir[2];
                    isExplosion = true;
                    failed.bombExplosionsGenerated++;
                    // Explosions always get a strong negative bias in non-strict mode.
                    if (limits.bombPriorityBias && !limits.strictShortest) {
                        priorityBias = -20;
                    }
                } else {
                    // Bomb pushes into empty cell -> must move toward a relevant wall.
                    // In non-strict mode, score the target wall's relevance and
                    // only allow the move if the wall is useful. In strict mode
                    // the move is always allowed (no pruning).
                    int targetScore = bombRelevanceScore(map, target, node.boxes, nextDestroyed, wallScore);
                    if (!limits.strictShortest && limits.bombPriorityBias) {
                        // Non-strict: prune moves that don't approach any useful wall.
                        if (targetScore <= 0) {
                            failed.bombRelevantWallPruned++;
                            continue;
                        }
                        // Bias scales with relevance: more useful wall = stronger pull.
                        priorityBias = Math.max(-8, -targetScore);
                    } else if (limits.strictShortest) {
                        // Strict: never prune bomb moves by relevance; only by
                        // the existing "toward wall" check to avoid infinite loops.
                        if (!isBombMoveTowardAnyWall(map, target, nextDestroyed)) {
                            continue;
                        }
                    } else {
                        // Other non-strict modes without priority bias: original check.
                        if (!isBombMoveTowardWall(map, bomb, target, nextDestroyed)) continue;
                    }
                    nextBombs[bombIndex] = target;
                    action = "x" + (char) dir[2];
                    failed.bombMovesGenerated++;
                }

                TransitionResult transition = appendBombTransition(
                    map, limits, actionOffset, open, best, node,
                    node.boxes, nextBombs, nextDestroyed,
                    bomb, pushHeading, reach, stance,
                    action, priorityBias, isExplosion, node.bombDepthSinceExplosion
                );
                maxFrontierSeen = Math.max(maxFrontierSeen, transition.maxFrontierSeen);
                failed.prunedByActionLimit += transition.prunedByActionLimit;
                failed.prunedByBestCost += transition.prunedByBestCost;
                failed.prunedByFrontierTrim += transition.prunedByFrontierTrim;
                if (transition.frontierLimitHit) {
                    failed.message = "达到 frontier 大小限制 " + limits.maxFrontier;
                    failed.frontierLimitHit = true;
                    failed.maxFrontierSeen = maxFrontierSeen;
                    return;
                }
            }
        }
    }

    // ------------------------------------------------------------------
    // Wall relevance scoring for bomb moves.
    // ------------------------------------------------------------------

    /** Precompute a relevance score for every destructible wall cell. */
    private int[] precomputeWallScores(GridMap map, Cell[] boxes) {
        int[] scores = new int[GridMap.CELLS];
        // Score = number of boxes whose path to goal is blocked by this wall.
        for (int i = 0; i < boxes.length; i++) {
            Cell box = boxes[i];
            if (box == null) continue;
            Cell goal = map.goals[i + 1];
            if (goal == null) continue;
            int dr = Integer.signum(goal.row - box.row);
            int dc = Integer.signum(goal.col - box.col);
            // Mark walls in the bounding box between box and goal.
            int r0 = Math.min(box.row, goal.row);
            int r1 = Math.max(box.row, goal.row);
            int c0 = Math.min(box.col, goal.col);
            int c1 = Math.max(box.col, goal.col);
            for (int r = r0; r <= r1; r++) {
                for (int c = c0; c <= c1; c++) {
                    if (map.token(r, c) == '#' && !isBoundaryWall(r, c)) {
                        scores[r * GridMap.COLS + c] += 2;
                    }
                }
            }
        }
        // Also boost walls near the player start (通道 opens).
        for (int r = 1; r < GridMap.ROWS - 1; r++) {
            for (int c = 1; c < GridMap.COLS - 1; c++) {
                if (map.token(r, c) == '#' && !isBoundaryWall(r, c)) {
                    // Count open neighbors (non-wall) as a通道 bonus.
                    int openNeighbors = 0;
                    for (int[] d : DIRS) {
                        int nr = r + d[0], nc = c + d[1];
                        if (inside(nr, nc) && map.token(nr, nc) != '#') openNeighbors++;
                    }
                    if (openNeighbors >= 2) scores[r * GridMap.COLS + c] += 1;
                }
            }
        }
        return scores;
    }

    /**
     * Score a bomb target cell: sum of relevance scores of walls that would be
     * destroyed if the bomb were later pushed into an adjacent wall from this
     * position. Higher = more useful bomb placement.
     */
    private int bombRelevanceScore(GridMap map, Cell bombTarget, Cell[] boxes, int[] destroyedWalls, int[] wallScore) {
        int score = 0;
        // Check walls in the 3x3 area centered on bombTarget.
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

    /** Check if the bomb is moving closer to ANY destructible wall. */
    private boolean isBombMoveTowardAnyWall(GridMap map, Cell to, int[] destroyedWalls) {
        int after = nearestDestructibleWallDistance(map, to, destroyedWalls);
        return after < 9999;
    }

    // ------------------------------------------------------------------
    // Transition appenders with optional bomb priority bias.
    // ------------------------------------------------------------------

    /** Append a box push transition (no priority bias). */
    private TransitionResult appendBoxTransition(
        GridMap map, PerformanceLimits limits, int actionOffset,
        PriorityQueue<Node> open, HashMap<String, Integer> best,
        Node node, Cell[] nextBoxes, Cell[] nextBombs, int[] nextDestroyedWalls,
        Cell nextPlayer, char nextHeading, Reachability reach, Cell stance,
        String pushAction, int priorityBias
    ) {
        return appendTransitionCore(map, limits, actionOffset, open, best, node,
            nextBoxes, nextBombs, nextDestroyedWalls, nextPlayer, nextHeading,
            reach, stance, pushAction, priorityBias, node.bombDepthSinceExplosion);
    }

    /** Append a bomb move/explosion transition with priority bias and depth tracking. */
    private TransitionResult appendBombTransition(
        GridMap map, PerformanceLimits limits, int actionOffset,
        PriorityQueue<Node> open, HashMap<String, Integer> best,
        Node node, Cell[] nextBoxes, Cell[] nextBombs, int[] nextDestroyedWalls,
        Cell nextPlayer, char nextHeading, Reachability reach, Cell stance,
        String pushAction, int priorityBias, boolean isExplosion, int prevBombDepth
    ) {
        int newBombDepth = isExplosion ? 0 : prevBombDepth + 1;
        return appendTransitionCore(map, limits, actionOffset, open, best, node,
            nextBoxes, nextBombs, nextDestroyedWalls, nextPlayer, nextHeading,
            reach, stance, pushAction, priorityBias, newBombDepth);
    }

    /** Core transition append logic shared by box and bomb moves. */
    private TransitionResult appendTransitionCore(
        GridMap map, PerformanceLimits limits, int actionOffset,
        PriorityQueue<Node> open, HashMap<String, Integer> best,
        Node node, Cell[] nextBoxes, Cell[] nextBombs, int[] nextDestroyedWalls,
        Cell nextPlayer, char nextHeading, Reachability reach, Cell stance,
        String pushAction, int priorityBias, int bombDepthSinceExplosion
    ) {
        ArrayList<String> walkActions = reach.actionsTo(stance, nextHeading);
        int nextCost = node.g + walkActions.size() + 1;
        TransitionResult result = new TransitionResult(open.size());

        if (limits.enforceActionLimitDuringSearch && actionOffset + nextCost > limits.maxActions) {
            result.prunedByActionLimit = 1;
            return result;
        }

        String sk = stateKey(nextPlayer, nextHeading, nextBoxes, nextBombs, nextDestroyedWalls);
        if (nextCost >= best.getOrDefault(sk, Integer.MAX_VALUE)) {
            result.prunedByBestCost = 1;
            return result;
        }
        best.put(sk, nextCost);

        ArrayList<String> actions = new ArrayList<>(node.actions);
        actions.addAll(walkActions);
        actions.add(pushAction);

        ArrayList<Cell> path = new ArrayList<>(node.path);
        path.addAll(reach.pathTo(stance, nextHeading));
        path.add(nextPlayer);

        int f = priority(map, limits, nextCost, nextPlayer, nextBoxes, nextBombs, nextDestroyedWalls, null);
        // Apply bomb priority bias: only in non-strict modes, this shifts the
        // f-value downward so bomb states are explored before equivalent box
        // states. The bias does NOT affect g-cost or the final solution cost,
        // only the exploration order. strictShortest never uses this.
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
            && !limits.trimFrontier
            && open.size() > limits.maxFrontier;
        return result;
    }

    // ------------------------------------------------------------------
    // Recognition (unchanged from previous version).
    // ------------------------------------------------------------------

    private RecognitionPlan planRecognition(GridMap map) {
        ArrayList<RecognitionObject> objects = new ArrayList<>();
        for (int id = 1; id <= map.boxCount; id++) {
            if (map.boxes[id] != null) objects.add(new RecognitionObject("B" + id, map.boxes[id]));
        }
        for (int id = 1; id <= map.boxCount; id++) {
            if (map.goals[id] != null) objects.add(new RecognitionObject("T" + id, map.goals[id]));
        }
        if (map.scanBombs) {
            for (int i = 0; i < map.bombCount; i++) objects.add(new RecognitionObject("X" + (i + 1), map.bombs[i]));
        }
        int fullMask = (1 << objects.size()) - 1;
        int poseCount = GridMap.CELLS * 4;
        int stateCount = poseCount * (fullMask + 1);
        int[] frontMask = new int[poseCount];
        int[] leftPose = new int[poseCount];
        int[] rightPose = new int[poseCount];
        int[] forwardPose = new int[poseCount];
        buildRecognitionTables(map, objects, frontMask, leftPose, rightPose, forwardPose);

        int[] parent = new int[stateCount];
        byte[] action = new byte[stateCount];
        Arrays.fill(parent, -2);
        ArrayDeque<Integer> queue = new ArrayDeque<>();
        int startPose = poseIndex(map.player, map.startHeading);
        int startMask = frontMask[startPose];
        int startState = startMask * poseCount + startPose;
        parent[startState] = -1;
        queue.add(startState);
        while (!queue.isEmpty()) {
            int state = queue.removeFirst();
            int mask = state / poseCount;
            int pose = state % poseCount;
            if (mask == fullMask) {
                return reconstructRecognitionPlan(state, poseCount, parent, action, objects);
            }
            addRecognitionTransition(queue, parent, action, frontMask, poseCount, mask, state, leftPose[pose], (byte) 1);
            addRecognitionTransition(queue, parent, action, frontMask, poseCount, mask, state, rightPose[pose], (byte) 2);
            addRecognitionTransition(queue, parent, action, frontMask, poseCount, mask, state, forwardPose[pose], (byte) 3);
        }
        RecognitionPlan failed = new RecognitionPlan();
        failed.message = "无法正面识别所有对象";
        return failed;
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
                if (!map.isWall(front.row, front.col) && !objectOccupied(map, front)) {
                    forwardPose[pose] = poseIndex(front, heading);
                }
            }
        }
    }

    private int objectMask(Cell front, ArrayList<RecognitionObject> objects) {
        int mask = 0;
        for (int i = 0; i < objects.size(); i++) {
            if (front.equals(objects.get(i).pos)) mask |= 1 << i;
        }
        return mask;
    }

    private void addRecognitionTransition(ArrayDeque<Integer> queue, int[] parent, byte[] action,
        int[] frontMask, int poseCount, int mask, int state, int nextPose, byte actionKind) {
        if (nextPose < 0) return;
        int nextMask = mask | frontMask[nextPose];
        int nextState = nextMask * poseCount + nextPose;
        if (parent[nextState] != -2) return;
        parent[nextState] = state;
        action[nextState] = actionKind;
        queue.add(nextState);
    }

    private RecognitionPlan reconstructRecognitionPlan(int goalState, int poseCount,
        int[] parent, byte[] action, ArrayList<RecognitionObject> objects) {
        ArrayList<Integer> reversedPoses = new ArrayList<>();
        ArrayList<String> reversedActions = new ArrayList<>();
        int current = goalState;
        while (current >= 0) {
            reversedPoses.add(current % poseCount);
            if (action[current] != 0) reversedActions.add(actionName(action[current]));
            current = parent[current];
        }
        RecognitionPlan plan = new RecognitionPlan();
        plan.ok = true;
        for (int i = reversedPoses.size() - 1; i >= 0; i--) {
            plan.path.add(poseCell(reversedPoses.get(i)));
            plan.headings.add(poseHeading(reversedPoses.get(i)));
        }
        for (int i = reversedActions.size() - 1; i >= 0; i--) plan.actions.add(reversedActions.get(i));
        plan.order = recognitionOrder(plan.path, plan.headings, objects);
        return plan;
    }

    private static String actionName(byte actionKind) {
        if (actionKind == 1) return "turn_left";
        if (actionKind == 2) return "turn_right";
        return "forward";
    }

    private ArrayList<String> recognitionOrder(List<Cell> path, List<Character> headings, ArrayList<RecognitionObject> objects) {
        ArrayList<String> order = new ArrayList<>();
        boolean[] seen = new boolean[objects.size()];
        for (int step = 0; step < path.size(); step++) {
            Cell pos = path.get(step);
            char heading = headings.get(step);
            Cell front = new Cell(pos.row + dirDr(heading), pos.col + dirDc(heading));
            for (int i = 0; i < objects.size(); i++) {
                if (seen[i]) continue;
                if (front.equals(objects.get(i).pos)) {
                    seen[i] = true;
                    order.add(objects.get(i).label);
                }
            }
        }
        return order;
    }

    // ------------------------------------------------------------------
    // Reachability BFS (no preferBombs parameter -- always mark all targets).
    // ------------------------------------------------------------------

    private Reachability computeReachability(GridMap map, Node node, Occupancy occupancy) {
        ReachWorkspace ws = reachWorkspace;
        ws.nextSearch();
        int remainingTargets = markTargetPoses(map, node, occupancy, ws);
        int head = 0;
        int startPose = poseIndex(node.player, node.heading);
        ws.seenStamp[startPose] = ws.searchGeneration;
        ws.prev[startPose] = -1;
        ws.action[startPose] = 0;
        if (ws.targetStamp[startPose] == ws.targetGeneration) remainingTargets--;
        ws.queue[ws.tail++] = startPose;
        while (head < ws.tail && remainingTargets > 0) {
            int currentPose = ws.queue[head++];
            int currentCell = currentPose / 4;
            int headingIndex = currentPose & 3;
            int row = currentCell / GridMap.COLS;
            int col = currentCell % GridMap.COLS;

            if (addPoseTransition(ws, currentPose, currentCell, LEFT_HEADING_INDEX[headingIndex], (byte) 1)) remainingTargets--;
            if (addPoseTransition(ws, currentPose, currentCell, RIGHT_HEADING_INDEX[headingIndex], (byte) 2)) remainingTargets--;

            int nr = row + DIRS[headingIndex][0];
            int nc = col + DIRS[headingIndex][1];
            if (inside(nr, nc)) {
                int nextCell = nr * GridMap.COLS + nc;
                if (!isWallDynamic(map, nr, nc, node.destroyedWalls)
                    && occupancy.boxAt[nextCell] < 0 && occupancy.bombAt[nextCell] < 0) {
                    if (addPoseTransition(ws, currentPose, nextCell, headingIndex, (byte) 3)) remainingTargets--;
                }
            }
        }
        return new Reachability(startPose, ws.searchGeneration, ws.seenStamp, ws.prev, ws.action);
    }

    private boolean addPoseTransition(ReachWorkspace ws, int currentPose, int nextCell, int nextHeadingIndex, byte actionKind) {
        int nextPose = nextCell * 4 + nextHeadingIndex;
        if (ws.seenStamp[nextPose] == ws.searchGeneration) return false;
        ws.seenStamp[nextPose] = ws.searchGeneration;
        ws.prev[nextPose] = currentPose;
        ws.action[nextPose] = actionKind;
        ws.queue[ws.tail++] = nextPose;
        return ws.targetStamp[nextPose] == ws.targetGeneration;
    }

    private int markTargetPoses(GridMap map, Node node, Occupancy occupancy, ReachWorkspace ws) {
        int count = 0;
        for (Cell box : node.boxes) count += markMovableTargets(map, node, occupancy, ws, box);
        if (map.allowBombPush) {
            for (Cell bomb : node.bombs) count += markMovableTargets(map, node, occupancy, ws, bomb);
        }
        return count;
    }

    private int markMovableTargets(GridMap map, Node node, Occupancy occupancy, ReachWorkspace ws, Cell movable) {
        if (movable == null) return 0;
        int count = 0;
        for (int[] dir : DIRS) {
            int stanceRow = movable.row - dir[0];
            int stanceCol = movable.col - dir[1];
            if (!inside(stanceRow, stanceCol)) continue;
            if (isWallDynamic(map, stanceRow, stanceCol, node.destroyedWalls)) continue;
            int stanceIndex = stanceRow * GridMap.COLS + stanceCol;
            if (occupancy.boxAt[stanceIndex] >= 0 || occupancy.bombAt[stanceIndex] >= 0) continue;
            int pose = stanceIndex * 4 + headingIndex((char) dir[2]);
            if (ws.targetStamp[pose] != ws.targetGeneration) {
                ws.targetStamp[pose] = ws.targetGeneration;
                count++;
            }
        }
        return count;
    }

    // ------------------------------------------------------------------
    // Heuristic and priority.
    // ------------------------------------------------------------------

    private Cell[] orderedBoxes(GridMap map) {
        Cell[] out = new Cell[map.boxCount];
        for (int id = 1; id <= map.boxCount; id++) out[id - 1] = map.boxes[id];
        return out;
    }

    private Cell[] orderedBombs(GridMap map) {
        Cell[] out = new Cell[map.bombCount];
        for (int i = 0; i < map.bombCount; i++) out[i] = map.bombs[i];
        return out;
    }

    private int heuristic(GridMap map, Cell player, Cell[] boxes, Cell[] bombs, int[] destroyedWalls, int[] wallScore) {
        if (allBoxesDelivered(boxes)) return 0;

        int value = 0;
        // Use reverse push distances when no live bomb can change walls,
        // otherwise fall back to Manhattan distance (admissible with dynamic walls).
        boolean usePushDist = (!map.allowBombPush || !hasLiveBomb(bombs));
        int[][] pushDist = usePushDist ? pushDistances(map, destroyedWalls) : null;

        for (int i = 0; i < boxes.length; i++) {
            Cell goal = map.goals[i + 1];
            if (boxes[i] != null && goal != null) {
                int dist = -1;
                if (pushDist != null && i < pushDist.length) dist = pushDist[i][boxes[i].index()];
                if (dist >= 0) {
                    value += dist;
                } else {
                    value += Math.abs(boxes[i].row - goal.row) + Math.abs(boxes[i].col - goal.col);
                }
            }
        }
        value += nextStanceLowerBound(player, boxes, bombs);
        return value;
    }

    private int priority(GridMap map, PerformanceLimits limits, int cost,
        Cell player, Cell[] boxes, Cell[] bombs, int[] destroyedWalls, int[] wallScore) {
        return cost + heuristic(map, player, boxes, bombs, destroyedWalls, wallScore) * Math.max(1, limits.heuristicWeight);
    }

    private int nextStanceLowerBound(Cell player, Cell[] boxes, Cell[] bombs) {
        int best = Integer.MAX_VALUE;
        for (Cell box : boxes) best = Math.min(best, stanceDistance(player, box));
        for (Cell bomb : bombs) best = Math.min(best, stanceDistance(player, bomb));
        return best == Integer.MAX_VALUE ? 0 : best;
    }

    private int stanceDistance(Cell player, Cell movable) {
        if (movable == null) return Integer.MAX_VALUE;
        int best = Integer.MAX_VALUE;
        for (int[] dir : DIRS) {
            int stanceRow = movable.row - dir[0];
            int stanceCol = movable.col - dir[1];
            int dist = Math.abs(player.row - stanceRow) + Math.abs(player.col - stanceCol);
            if (dist < best) best = dist;
        }
        return best;
    }

    private boolean allBoxesDelivered(Cell[] boxes) {
        for (Cell box : boxes) if (box != null) return false;
        return true;
    }

    private int[][] pushDistances(GridMap map, int[] destroyedWalls) {
        String key = destroyedWallsKey(destroyedWalls);
        int[][] cached = pushDistanceCache.get(key);
        if (cached != null) return cached;
        int[][] distances = new int[Math.max(0, map.boxCount)][GridMap.CELLS];
        for (int i = 0; i < distances.length; i++) {
            Arrays.fill(distances[i], -1);
            Cell goal = map.goals[i + 1];
            if (goal != null) fillReversePushDistances(map, goal, destroyedWalls, distances[i]);
        }
        pushDistanceCache.put(key, distances);
        return distances;
    }

    private String destroyedWallsKey(int[] destroyedWalls) {
        if (destroyedWalls.length == 0) return "";
        StringBuilder sb = new StringBuilder(destroyedWalls.length * 4);
        for (int wall : destroyedWalls) sb.append(wall).append(',');
        return sb.toString();
    }

    private void fillReversePushDistances(GridMap map, Cell goal, int[] destroyedWalls, int[] dist) {
        ArrayDeque<Integer> queue = new ArrayDeque<>();
        dist[goal.index()] = 0;
        queue.add(goal.index());
        while (!queue.isEmpty()) {
            int cell = queue.removeFirst();
            int row = cell / GridMap.COLS;
            int col = cell % GridMap.COLS;
            int nextDistance = dist[cell] + 1;
            for (int[] dir : DIRS) {
                int pr = row - dir[0], pc = col - dir[1];
                int sr = pr - dir[0], sc = pc - dir[1];
                if (!inside(pr, pc) || !inside(sr, sc)
                    || isWallDynamic(map, pr, pc, destroyedWalls)
                    || isWallDynamic(map, sr, sc, destroyedWalls)) continue;
                int prev = pr * GridMap.COLS + pc;
                if (dist[prev] >= 0) continue;
                dist[prev] = nextDistance;
                queue.add(prev);
            }
        }
    }

    // ------------------------------------------------------------------
    // Utilities.
    // ------------------------------------------------------------------

    private static int compareNodes(Node a, Node b) {
        if (a.f != b.f) return Integer.compare(a.f, b.f);
        return Integer.compare(b.g, a.g);
    }

    private void trimFrontier(PriorityQueue<Node> open, int maxFrontier) {
        if (maxFrontier <= 0 || open.size() <= maxFrontier) return;
        ArrayList<Node> nodes = new ArrayList<>(open);
        nodes.sort(NativePlanner::compareNodes);
        open.clear();
        for (int i = 0; i < maxFrontier && i < nodes.size(); i++) open.add(nodes.get(i));
    }

    private boolean isGoal(GridMap map, Cell[] boxes) { return allBoxesDelivered(boxes); }

    private boolean isDeadlock(GridMap map, Cell pos, int boxId, Cell[] boxes, int[] destroyedWalls) {
        Cell goal = map.goals[boxId];
        if (goal != null && goal.equals(pos)) return false;
        boolean up = isWallDynamic(map, pos.row - 1, pos.col, destroyedWalls);
        boolean down = isWallDynamic(map, pos.row + 1, pos.col, destroyedWalls);
        boolean left = isWallDynamic(map, pos.row, pos.col - 1, destroyedWalls);
        boolean right = isWallDynamic(map, pos.row, pos.col + 1, destroyedWalls);
        if ((up && left) || (up && right) || (down && left) || (down && right)) return true;

        int boxPosIndex = pos.index();
        for (int top = pos.row - 1; top <= pos.row; top++) {
            for (int lft = pos.col - 1; lft <= pos.col; lft++) {
                boolean containsBox = false, containsGoal = false, blocked = true;
                for (int r = top; r <= top + 1; r++) {
                    for (int c = lft; c <= lft + 1; c++) {
                        if (!inside(r, c)) { blocked = false; continue; }
                        int idx = r * GridMap.COLS + c;
                        if (idx == boxPosIndex) containsBox = true;
                        for (int id = 1; id <= map.boxCount; id++) {
                            Cell g = map.goals[id];
                            if (g != null && g.row == r && g.col == c) containsGoal = true;
                        }
                        if (!isWallDynamic(map, r, c, destroyedWalls) && !hasBoxAtIndex(boxes, idx)) blocked = false;
                    }
                }
                if (containsBox && !containsGoal && blocked) return true;
            }
        }
        return false;
    }

    private boolean hasBoxAtIndex(Cell[] boxes, int index) {
        for (Cell box : boxes) if (box != null && box.index() == index) return true;
        return false;
    }

    private boolean objectOccupied(GridMap map, Cell pos) {
        int idx = pos.index();
        for (int id = 1; id <= map.boxCount; id++)
            if (map.boxes[id] != null && map.boxes[id].index() == idx) return true;
        for (int i = 0; i < map.bombCount; i++)
            if (map.bombs[i] != null && map.bombs[i].index() == idx) return true;
        return false;
    }

    private Occupancy buildOccupancy(Cell[] boxes, Cell[] bombs) {
        Occupancy occupancy = new Occupancy();
        for (int i = 0; i < boxes.length; i++) if (boxes[i] != null) occupancy.boxAt[boxes[i].index()] = i;
        for (int i = 0; i < bombs.length; i++) if (bombs[i] != null) occupancy.bombAt[bombs[i].index()] = i;
        return occupancy;
    }

    private Cell[] copyCells(Cell[] cells) { return Arrays.copyOf(cells, cells.length); }

    private boolean hasLiveBomb(Cell[] bombs) {
        for (Cell bomb : bombs) if (bomb != null) return true;
        return false;
    }

    private String stateKey(Cell player, char heading, Cell[] boxes, Cell[] bombs, int[] destroyedWalls) {
        StringBuilder sb = new StringBuilder();
        sb.append(player.index()).append('@').append(heading).append('|');
        for (Cell box : boxes) sb.append(box == null ? -1 : box.index()).append(',');
        sb.append('|');
        int[] bombIndexes = new int[bombs.length];
        for (int i = 0; i < bombs.length; i++) bombIndexes[i] = bombs[i] == null ? -1 : bombs[i].index();
        Arrays.sort(bombIndexes);
        for (int bomb : bombIndexes) sb.append(bomb).append(',');
        sb.append('|');
        for (int wall : destroyedWalls) sb.append(wall).append(',');
        return sb.toString();
    }

    private int countPushes(ArrayList<String> actions) {
        int count = 0;
        for (String action : actions) {
            if (action.length() == 1 && Character.isUpperCase(action.charAt(0))) count++;
            else if (action.length() == 2 && action.charAt(0) == 'X') count++;
        }
        return count;
    }

    private static int headingIndex(char h) {
        h = Character.toUpperCase(h);
        if (h == 'L') return 0; if (h == 'U') return 1; if (h == 'D') return 2; return 3;
    }
    private static char leftHeading(char h) {
        h = Character.toUpperCase(h);
        if (h == 'U') return 'L'; if (h == 'L') return 'D'; if (h == 'D') return 'R'; return 'U';
    }
    private static char rightHeading(char h) {
        h = Character.toUpperCase(h);
        if (h == 'U') return 'R'; if (h == 'R') return 'D'; if (h == 'D') return 'L'; return 'U';
    }
    private static int dirDr(char h) { return DIRS[headingIndex(h)][0]; }
    private static int dirDc(char h) { return DIRS[headingIndex(h)][1]; }
    private static int poseIndex(Cell cell, char h) { return cell.index() * 4 + headingIndex(h); }
    private static Cell poseCell(int pi) { int c = pi / 4; return new Cell(c / GridMap.COLS, c % GridMap.COLS); }
    private static char poseHeading(int pi) { return HEADINGS[pi & 3]; }
    private boolean inside(int r, int c) { return r >= 0 && c >= 0 && r < GridMap.ROWS && c < GridMap.COLS; }

    private boolean isWallDynamic(GridMap map, int r, int c, int[] destroyedWalls) {
        if (r < 0 || c < 0 || r >= GridMap.ROWS || c >= GridMap.COLS) return true;
        if (map.token(r, c) != '#') return false;
        return Arrays.binarySearch(destroyedWalls, r * GridMap.COLS + c) < 0;
    }

    private boolean isBoundaryWall(int r, int c) {
        return r == 0 || c == 0 || r == GridMap.ROWS - 1 || c == GridMap.COLS - 1;
    }

    private int[] explosionCells(GridMap map, int row, int col, int[] destroyedWalls) {
        int[] scratch = new int[9];
        int count = 0;
        for (int r = row - 1; r <= row + 1; r++) {
            for (int c = col - 1; c <= col + 1; c++) {
                if (!inside(r, c) || isBoundaryWall(r, c)) continue;
                int idx = r * GridMap.COLS + c;
                if (map.token(r, c) == '#' && Arrays.binarySearch(destroyedWalls, idx) < 0) scratch[count++] = idx;
            }
        }
        return Arrays.copyOf(scratch, count);
    }

    private boolean isBombMoveTowardWall(GridMap map, Cell from, Cell to, int[] destroyedWalls) {
        return nearestDestructibleWallDistance(map, to, destroyedWalls)
            < nearestDestructibleWallDistance(map, from, destroyedWalls);
    }

    private int nearestDestructibleWallDistance(GridMap map, Cell cell, int[] destroyedWalls) {
        int best = 9999;
        for (int r = 1; r < GridMap.ROWS - 1; r++) {
            for (int c = 1; c < GridMap.COLS - 1; c++) {
                if (map.token(r, c) != '#') continue;
                if (Arrays.binarySearch(destroyedWalls, r * GridMap.COLS + c) >= 0) continue;
                int dist = Math.abs(cell.row - r) + Math.abs(cell.col - c);
                if (dist < best) best = dist;
            }
        }
        return best;
    }

    private int[] mergeDestroyedWalls(int[] current, int[] added) {
        if (added.length == 0) return current;
        int[] merged = Arrays.copyOf(current, current.length + added.length);
        System.arraycopy(added, 0, merged, current.length, added.length);
        Arrays.sort(merged);
        int unique = 0;
        for (int value : merged) if (unique == 0 || merged[unique - 1] != value) merged[unique++] = value;
        return Arrays.copyOf(merged, unique);
    }

    // ------------------------------------------------------------------
    // Node now carries bombDepthSinceExplosion for depth-based pruning.
    // ------------------------------------------------------------------

    private static final class Node {
        final Cell player;
        final char heading;
        final Cell[] boxes;
        final Cell[] bombs;
        final int[] destroyedWalls;
        final int g;
        final int f;
        final ArrayList<String> actions;
        final ArrayList<Cell> path;
        final int bombDepthSinceExplosion;

        Node(Cell player, char heading, Cell[] boxes, Cell[] bombs, int[] destroyedWalls,
             int g, int f, ArrayList<String> actions, ArrayList<Cell> path,
             int bombDepthSinceExplosion) {
            this.player = player;
            this.heading = heading;
            this.boxes = boxes;
            this.bombs = bombs;
            this.destroyedWalls = destroyedWalls;
            this.g = g;
            this.f = f;
            this.actions = actions;
            this.path = path;
            this.bombDepthSinceExplosion = bombDepthSinceExplosion;
        }
    }

    static final class SearchResult {
        boolean solved;
        String message = "";
        int expanded;
        int maxFrontierSeen;
        int pushes;
        ArrayList<String> actions = new ArrayList<>();
        ArrayList<Cell> path = new ArrayList<>();
        int prunedByDeadlock;
        int prunedByActionLimit;
        int prunedByBestCost;
        int prunedByFrontierTrim;
        boolean timeoutHit;
        boolean expandedLimitHit;
        boolean frontierLimitHit;
        boolean actionLimitHit;
        // Bomb diagnostics.
        int bombMovesGenerated;
        int bombExplosionsGenerated;
        int bombMovesPruned;
        int bombRelevantWallPruned;
        boolean bombPriorityUsed;
        int bombDepthPruned;

        List<Cell> pathWithoutFirst() {
            if (path.size() <= 1) return new ArrayList<>();
            return path.subList(1, path.size());
        }
    }

    static final class TransitionResult {
        boolean frontierLimitHit;
        int maxFrontierSeen;
        int prunedByActionLimit;
        int prunedByBestCost;
        int prunedByFrontierTrim;

        TransitionResult(int maxFrontierSeen) { this.maxFrontierSeen = maxFrontierSeen; }
    }

    private static final class Occupancy {
        final int[] boxAt = new int[GridMap.CELLS];
        final int[] bombAt = new int[GridMap.CELLS];
        Occupancy() { Arrays.fill(boxAt, -1); Arrays.fill(bombAt, -1); }
        boolean hasBox(Cell c) { return c.row >= 0 && c.col >= 0 && c.row < GridMap.ROWS && c.col < GridMap.COLS && boxAt[c.index()] >= 0; }
        boolean hasBomb(Cell c) { return c.row >= 0 && c.col >= 0 && c.row < GridMap.ROWS && c.col < GridMap.COLS && bombAt[c.index()] >= 0; }
    }

    private static final class ReachWorkspace {
        final int[] seenStamp = new int[GridMap.CELLS * 4];
        final int[] targetStamp = new int[GridMap.CELLS * 4];
        final int[] prev = new int[GridMap.CELLS * 4];
        final byte[] action = new byte[GridMap.CELLS * 4];
        final int[] queue = new int[GridMap.CELLS * 4];
        int searchGeneration = 0;
        int targetGeneration = 0;
        int tail = 0;
        void nextSearch() {
            searchGeneration++; targetGeneration++; tail = 0;
            if (searchGeneration == Integer.MAX_VALUE || targetGeneration == Integer.MAX_VALUE) {
                Arrays.fill(seenStamp, 0); Arrays.fill(targetStamp, 0);
                searchGeneration = 1; targetGeneration = 1;
            }
        }
    }

    private static final class Reachability {
        final int startPose, generation;
        final int[] seenStamp, prev;
        final byte[] action;
        Reachability(int s, int g, int[] seen, int[] prev, byte[] act) {
            startPose = s; generation = g; seenStamp = seen; this.prev = prev; action = act;
        }
        boolean canReach(Cell cell, char heading) {
            return cell.row >= 0 && cell.col >= 0 && cell.row < GridMap.ROWS && cell.col < GridMap.COLS
                && seenStamp[poseIndex(cell, heading)] == generation;
        }
        ArrayList<String> actionsTo(Cell target, char heading) {
            ArrayList<String> reversed = new ArrayList<>();
            int cur = poseIndex(target, heading);
            while (cur != startPose) {
                if (cur < 0 || seenStamp[cur] != generation || prev[cur] < 0) return new ArrayList<>();
                reversed.add(NativePlanner.actionName(action[cur]));
                cur = prev[cur];
            }
            ArrayList<String> out = new ArrayList<>();
            for (int i = reversed.size() - 1; i >= 0; i--) out.add(reversed.get(i));
            return out;
        }
        ArrayList<Cell> pathTo(Cell target, char heading) {
            ArrayList<Cell> reversed = new ArrayList<>();
            int cur = poseIndex(target, heading);
            while (cur != startPose) {
                if (cur < 0 || seenStamp[cur] != generation || prev[cur] < 0) return new ArrayList<>();
                reversed.add(poseCell(cur));
                cur = prev[cur];
            }
            ArrayList<Cell> out = new ArrayList<>();
            for (int i = reversed.size() - 1; i >= 0; i--) out.add(reversed.get(i));
            return out;
        }
    }

    private static final class RecognitionObject {
        final String label;
        final Cell pos;
        RecognitionObject(String l, Cell p) { label = l; pos = p; }
    }

    private static final class RecognitionPlan {
        boolean ok;
        String message = "";
        ArrayList<Cell> path = new ArrayList<>();
        ArrayList<Character> headings = new ArrayList<>();
        ArrayList<String> actions = new ArrayList<>();
        ArrayList<String> order = new ArrayList<>();
    }
}
