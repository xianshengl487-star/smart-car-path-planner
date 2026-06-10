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
        if (!search.solved) return result;

        result.actions.addAll(search.actions);
        result.playerPath.addAll(search.pathWithoutFirst());
        result.pushes = search.pushes;
        result.totalCost = result.actions.size();
        if (result.actions.size() > limits.maxActions) {
            result.solved = false;
            result.message = "动作数超过 STM32 限制: " + result.actions.size() + " > " + limits.maxActions;
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
        Node start = new Node(
            startPlayer,
            startHeading,
            startBoxes,
            startBombs,
            startDestroyedWalls,
            0,
            priority(map, limits, 0, startPlayer, startBoxes, startBombs, startDestroyedWalls),
            new ArrayList<>(),
            new ArrayList<>()
        );
        start.path.add(startPlayer);
        open.add(start);
        best.put(stateKey(start.player, start.heading, start.boxes, start.bombs, start.destroyedWalls), 0);

        int expanded = 0;
        int maxFrontierSeen = 1;
        while (!open.isEmpty()) {
            if (System.currentTimeMillis() - startMillis > limits.maxMillis) {
                failed.message = "达到 STM32 时间限制 " + limits.maxMillis + "ms";
                failed.expanded = expanded;
                failed.maxFrontierSeen = maxFrontierSeen;
                return failed;
            }
            if (expanded >= limits.maxExpanded) {
                failed.message = "达到 STM32 扩展节点限制 " + limits.maxExpanded;
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
                return ok;
            }

            boolean forceBombFirst = !limits.strictShortest
                && map.allowBombPush
                && node.destroyedWalls.length == 0
                && hasLiveBomb(node.bombs);
            Occupancy occupancy = buildOccupancy(node.boxes, node.bombs);
            Reachability reach = computeReachability(map, node, occupancy, forceBombFirst);

            for (int boxIndex = 0; boxIndex < node.boxes.length; boxIndex++) {
                if (forceBombFirst) break;
                Cell box = node.boxes[boxIndex];
                if (box == null) continue;
                for (int[] dir : DIRS) {
                    int dr = dir[0];
                    int dc = dir[1];
                    char pushHeading = (char) dir[2];
                    Cell stance = new Cell(box.row - dr, box.col - dc);
                    if (!reach.canReach(stance, pushHeading)) continue;

                    Cell pushed = new Cell(box.row + dr, box.col + dc);
                    if (
                        isWallDynamic(map, pushed.row, pushed.col, node.destroyedWalls)
                            || occupancy.hasBox(pushed)
                            || occupancy.hasBomb(pushed)
                    ) {
                        continue;
                    }

                    Cell[] nextBoxes = copyCells(node.boxes);
                    boolean delivered = pushed.equals(map.goals[boxIndex + 1]);
                    nextBoxes[boxIndex] = delivered ? null : pushed;
                    if (!delivered && isDeadlock(map, pushed, boxIndex + 1, nextBoxes, node.destroyedWalls)) continue;

                    TransitionResult transition = appendTransition(
                        map,
                        limits,
                        actionOffset,
                        open,
                        best,
                        node,
                        nextBoxes,
                        node.bombs,
                        node.destroyedWalls,
                        box,
                        pushHeading,
                        reach,
                        stance,
                        Character.toString(pushHeading)
                    );
                    maxFrontierSeen = Math.max(maxFrontierSeen, transition.maxFrontierSeen);
                    if (transition.frontierLimitHit) {
                        failed.message = "达到 STM32 frontier 限制 " + limits.maxFrontier;
                        failed.expanded = expanded;
                        failed.maxFrontierSeen = maxFrontierSeen;
                        return failed;
                    }
                }
            }

            if (map.allowBombPush) {
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
                        if (isWallDynamic(map, target.row, target.col, node.destroyedWalls)) {
                            int[] destroyedByExplosion = explosionCells(map, target.row, target.col, node.destroyedWalls);
                            if (destroyedByExplosion.length == 0) continue;
                            nextBombs[bombIndex] = null;
                            nextDestroyed = mergeDestroyedWalls(node.destroyedWalls, destroyedByExplosion);
                            action = "X" + (char) dir[2];
                        } else {
                            if (!isBombMoveTowardWall(map, bomb, target, node.destroyedWalls)) continue;
                            nextBombs[bombIndex] = target;
                            action = "x" + (char) dir[2];
                        }

                        TransitionResult transition = appendTransition(
                            map,
                            limits,
                            actionOffset,
                            open,
                            best,
                            node,
                            node.boxes,
                            nextBombs,
                            nextDestroyed,
                            bomb,
                            pushHeading,
                            reach,
                            stance,
                            action
                        );
                        maxFrontierSeen = Math.max(maxFrontierSeen, transition.maxFrontierSeen);
                        if (transition.frontierLimitHit) {
                            failed.message = "达到 STM32 frontier 限制 " + limits.maxFrontier;
                            failed.expanded = expanded;
                            failed.maxFrontierSeen = maxFrontierSeen;
                            return failed;
                        }
                    }
                }
            }
        }
        failed.message = "无解";
        failed.expanded = expanded;
        failed.maxFrontierSeen = maxFrontierSeen;
        return failed;
    }

    private TransitionResult appendTransition(
        GridMap map,
        PerformanceLimits limits,
        int actionOffset,
        PriorityQueue<Node> open,
        HashMap<String, Integer> best,
        Node node,
        Cell[] nextBoxes,
        Cell[] nextBombs,
        int[] nextDestroyedWalls,
        Cell nextPlayer,
        char nextHeading,
        Reachability reach,
        Cell stance,
        String pushAction
    ) {
        ArrayList<String> walkActions = reach.actionsTo(stance, nextHeading);
        int nextCost = node.g + walkActions.size() + 1;
        TransitionResult result = new TransitionResult(open.size());
        if (actionOffset + nextCost > limits.maxActions) return result;

        String sk = stateKey(nextPlayer, nextHeading, nextBoxes, nextBombs, nextDestroyedWalls);
        if (nextCost >= best.getOrDefault(sk, Integer.MAX_VALUE)) return result;
        best.put(sk, nextCost);

        ArrayList<String> actions = new ArrayList<>(node.actions);
        actions.addAll(walkActions);
        actions.add(pushAction);

        ArrayList<Cell> path = new ArrayList<>(node.path);
        path.addAll(reach.pathTo(stance, nextHeading));
        path.add(nextPlayer);

        int f = priority(map, limits, nextCost, nextPlayer, nextBoxes, nextBombs, nextDestroyedWalls);
        open.add(new Node(nextPlayer, nextHeading, copyCells(nextBoxes), copyCells(nextBombs), nextDestroyedWalls, nextCost, f, actions, path));
        if (limits.trimFrontier) trimFrontier(open, limits.maxFrontier);
        result.maxFrontierSeen = Math.max(result.maxFrontierSeen, open.size());
        result.frontierLimitHit = !limits.trimFrontier && open.size() > limits.maxFrontier;
        return result;
    }

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

    private void buildRecognitionTables(
        GridMap map,
        ArrayList<RecognitionObject> objects,
        int[] frontMask,
        int[] leftPose,
        int[] rightPose,
        int[] forwardPose
    ) {
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
            RecognitionObject obj = objects.get(i);
            if (front.equals(obj.pos)) mask |= 1 << i;
        }
        return mask;
    }

    private void addRecognitionTransition(
        ArrayDeque<Integer> queue,
        int[] parent,
        byte[] action,
        int[] frontMask,
        int poseCount,
        int mask,
        int state,
        int nextPose,
        byte actionKind
    ) {
        if (nextPose < 0) return;
        int nextMask = mask | frontMask[nextPose];
        int nextState = nextMask * poseCount + nextPose;
        if (parent[nextState] != -2) return;
        parent[nextState] = state;
        action[nextState] = actionKind;
        queue.add(nextState);
    }

    private RecognitionPlan reconstructRecognitionPlan(
        int goalState,
        int poseCount,
        int[] parent,
        byte[] action,
        ArrayList<RecognitionObject> objects
    ) {
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
            int pose = reversedPoses.get(i);
            plan.path.add(poseCell(pose));
            plan.headings.add(poseHeading(pose));
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
                RecognitionObject obj = objects.get(i);
                if (front.equals(obj.pos)) {
                    seen[i] = true;
                    order.add(obj.label);
                }
            }
        }
        return order;
    }

    private Reachability computeReachability(GridMap map, Node node, Occupancy occupancy, boolean forceBombFirst) {
        ReachWorkspace ws = reachWorkspace;
        ws.nextSearch();
        int remainingTargets = markTargetPoses(map, node, occupancy, ws, forceBombFirst);
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

            if (addPoseTransition(ws, currentPose, currentCell, LEFT_HEADING_INDEX[headingIndex], (byte) 1)) {
                remainingTargets--;
            }
            if (addPoseTransition(ws, currentPose, currentCell, RIGHT_HEADING_INDEX[headingIndex], (byte) 2)) {
                remainingTargets--;
            }

            int nr = row + DIRS[headingIndex][0];
            int nc = col + DIRS[headingIndex][1];
            if (inside(nr, nc)) {
                int nextCell = nr * GridMap.COLS + nc;
                if (
                    !isWallDynamic(map, nr, nc, node.destroyedWalls)
                        && occupancy.boxAt[nextCell] < 0
                        && occupancy.bombAt[nextCell] < 0
                ) {
                    if (addPoseTransition(ws, currentPose, nextCell, headingIndex, (byte) 3)) {
                        remainingTargets--;
                    }
                }
            }
        }
        return new Reachability(startPose, ws.searchGeneration, ws.seenStamp, ws.prev, ws.action);
    }

    private boolean addPoseTransition(
        ReachWorkspace ws,
        int currentPose,
        int nextCell,
        int nextHeadingIndex,
        byte actionKind
    ) {
        int nextPose = nextCell * 4 + nextHeadingIndex;
        if (ws.seenStamp[nextPose] == ws.searchGeneration) return false;
        ws.seenStamp[nextPose] = ws.searchGeneration;
        ws.prev[nextPose] = currentPose;
        ws.action[nextPose] = actionKind;
        ws.queue[ws.tail++] = nextPose;
        return ws.targetStamp[nextPose] == ws.targetGeneration;
    }

    private int markTargetPoses(
        GridMap map,
        Node node,
        Occupancy occupancy,
        ReachWorkspace ws,
        boolean forceBombFirst
    ) {
        int count = 0;
        if (!forceBombFirst) {
            for (Cell box : node.boxes) count += markMovableTargets(map, node, occupancy, ws, box);
        }
        if (map.allowBombPush) {
            for (Cell bomb : node.bombs) count += markMovableTargets(map, node, occupancy, ws, bomb);
        }
        return count;
    }

    private int markMovableTargets(
        GridMap map,
        Node node,
        Occupancy occupancy,
        ReachWorkspace ws,
        Cell movable
    ) {
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

    private int heuristic(GridMap map, Cell player, Cell[] boxes, Cell[] bombs, int[] destroyedWalls) {
        if (allBoxesDelivered(boxes)) return 0;

        int value = 0;
        int[][] pushDistances = (!map.allowBombPush || !hasLiveBomb(bombs))
            ? pushDistances(map, destroyedWalls)
            : null;
        for (int i = 0; i < boxes.length; i++) {
            Cell goal = map.goals[i + 1];
            if (boxes[i] != null && goal != null) {
                int dist = -1;
                if (pushDistances != null && i < pushDistances.length) dist = pushDistances[i][boxes[i].index()];
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

    private int priority(
        GridMap map,
        PerformanceLimits limits,
        int cost,
        Cell player,
        Cell[] boxes,
        Cell[] bombs,
        int[] destroyedWalls
    ) {
        return cost + heuristic(map, player, boxes, bombs, destroyedWalls) * Math.max(1, limits.heuristicWeight);
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
        for (Cell box : boxes) {
            if (box != null) return false;
        }
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
                int previousRow = row - dir[0];
                int previousCol = col - dir[1];
                int stanceRow = previousRow - dir[0];
                int stanceCol = previousCol - dir[1];
                if (
                    !inside(previousRow, previousCol)
                        || !inside(stanceRow, stanceCol)
                        || isWallDynamic(map, previousRow, previousCol, destroyedWalls)
                        || isWallDynamic(map, stanceRow, stanceCol, destroyedWalls)
                ) {
                    continue;
                }
                int previous = previousRow * GridMap.COLS + previousCol;
                if (dist[previous] >= 0) continue;
                dist[previous] = nextDistance;
                queue.add(previous);
            }
        }
    }

    private static int compareNodes(Node a, Node b) {
        if (a.f != b.f) return Integer.compare(a.f, b.f);
        // Deeper nodes usually have fewer remaining pushes when f ties, which keeps
        // the bounded STM32 frontier focused instead of filling with walking variants.
        return Integer.compare(b.g, a.g);
    }

    private void trimFrontier(PriorityQueue<Node> open, int maxFrontier) {
        if (maxFrontier <= 0 || open.size() <= maxFrontier) return;
        ArrayList<Node> nodes = new ArrayList<>(open);
        nodes.sort(NativePlanner::compareNodes);
        open.clear();
        for (int i = 0; i < maxFrontier && i < nodes.size(); i++) open.add(nodes.get(i));
    }

    private boolean isGoal(GridMap map, Cell[] boxes) {
        return allBoxesDelivered(boxes);
    }

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
                boolean containsBox = false;
                boolean containsGoal = false;
                boolean blocked = true;
                for (int r = top; r <= top + 1; r++) {
                    for (int c = lft; c <= lft + 1; c++) {
                        if (!inside(r, c)) {
                            blocked = false;
                            continue;
                        }
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
        for (Cell box : boxes) {
            if (box != null && box.index() == index) return true;
        }
        return false;
    }

    private boolean objectOccupied(GridMap map, Cell pos) {
        int idx = pos.index();
        for (int id = 1; id <= map.boxCount; id++) {
            if (map.boxes[id] != null && map.boxes[id].index() == idx) return true;
        }
        for (int i = 0; i < map.bombCount; i++) {
            if (map.bombs[i] != null && map.bombs[i].index() == idx) return true;
        }
        return false;
    }

    private Occupancy buildOccupancy(Cell[] boxes, Cell[] bombs) {
        Occupancy occupancy = new Occupancy();
        for (int i = 0; i < boxes.length; i++) {
            if (boxes[i] != null) occupancy.boxAt[boxes[i].index()] = i;
        }
        for (int i = 0; i < bombs.length; i++) {
            if (bombs[i] != null) occupancy.bombAt[bombs[i].index()] = i;
        }
        return occupancy;
    }

    private Cell[] copyCells(Cell[] cells) {
        return Arrays.copyOf(cells, cells.length);
    }

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

    private static int headingIndex(char heading) {
        char h = Character.toUpperCase(heading);
        if (h == 'L') return 0;
        if (h == 'U') return 1;
        if (h == 'D') return 2;
        return 3;
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
        return DIRS[headingIndex(heading)][0];
    }

    private static int dirDc(char heading) {
        return DIRS[headingIndex(heading)][1];
    }

    private static int poseIndex(Cell cell, char heading) {
        return cell.index() * 4 + headingIndex(heading);
    }

    private static Cell poseCell(int poseIndex) {
        int cell = poseIndex / 4;
        return new Cell(cell / GridMap.COLS, cell % GridMap.COLS);
    }

    private static char poseHeading(int poseIndex) {
        return HEADINGS[poseIndex & 3];
    }

    private boolean inside(int row, int col) {
        return row >= 0 && col >= 0 && row < GridMap.ROWS && col < GridMap.COLS;
    }

    private boolean isWallDynamic(GridMap map, int row, int col, int[] destroyedWalls) {
        if (row < 0 || col < 0 || row >= GridMap.ROWS || col >= GridMap.COLS) return true;
        if (map.token(row, col) != '#') return false;
        return Arrays.binarySearch(destroyedWalls, row * GridMap.COLS + col) < 0;
    }

    private boolean isBoundaryWall(int row, int col) {
        return row == 0 || col == 0 || row == GridMap.ROWS - 1 || col == GridMap.COLS - 1;
    }

    private int[] explosionCells(GridMap map, int row, int col, int[] destroyedWalls) {
        int[] scratch = new int[9];
        int count = 0;
        for (int r = row - 1; r <= row + 1; r++) {
            for (int c = col - 1; c <= col + 1; c++) {
                if (!inside(r, c) || isBoundaryWall(r, c)) continue;
                int idx = r * GridMap.COLS + c;
                if (map.token(r, c) == '#' && Arrays.binarySearch(destroyedWalls, idx) < 0) {
                    scratch[count++] = idx;
                }
            }
        }
        return Arrays.copyOf(scratch, count);
    }

    private boolean isBombMoveTowardWall(GridMap map, Cell from, Cell to, int[] destroyedWalls) {
        int before = nearestDestructibleWallDistance(map, from, destroyedWalls);
        int after = nearestDestructibleWallDistance(map, to, destroyedWalls);
        return after < before;
    }

    private int nearestDestructibleWallDistance(GridMap map, Cell cell, int[] destroyedWalls) {
        int best = 9999;
        for (int r = 1; r < GridMap.ROWS - 1; r++) {
            for (int c = 1; c < GridMap.COLS - 1; c++) {
                if (map.token(r, c) != '#') continue;
                int idx = r * GridMap.COLS + c;
                if (Arrays.binarySearch(destroyedWalls, idx) >= 0) continue;
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
        for (int value : merged) {
            if (unique == 0 || merged[unique - 1] != value) merged[unique++] = value;
        }
        return Arrays.copyOf(merged, unique);
    }

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

        Node(
            Cell player,
            char heading,
            Cell[] boxes,
            Cell[] bombs,
            int[] destroyedWalls,
            int g,
            int f,
            ArrayList<String> actions,
            ArrayList<Cell> path
        ) {
            this.player = player;
            this.heading = heading;
            this.boxes = boxes;
            this.bombs = bombs;
            this.destroyedWalls = destroyedWalls;
            this.g = g;
            this.f = f;
            this.actions = actions;
            this.path = path;
        }
    }

    private static final class SearchResult {
        boolean solved;
        String message = "";
        int expanded;
        int maxFrontierSeen;
        int pushes;
        ArrayList<String> actions = new ArrayList<>();
        ArrayList<Cell> path = new ArrayList<>();

        List<Cell> pathWithoutFirst() {
            if (path.size() <= 1) return new ArrayList<>();
            return path.subList(1, path.size());
        }
    }

    private static final class TransitionResult {
        boolean frontierLimitHit;
        int maxFrontierSeen;

        TransitionResult(int maxFrontierSeen) {
            this.maxFrontierSeen = maxFrontierSeen;
        }
    }

    private static final class Occupancy {
        final int[] boxAt = new int[GridMap.CELLS];
        final int[] bombAt = new int[GridMap.CELLS];

        Occupancy() {
            Arrays.fill(boxAt, -1);
            Arrays.fill(bombAt, -1);
        }

        boolean hasBox(Cell cell) {
            return insideCell(cell) && boxAt[cell.index()] >= 0;
        }

        boolean hasBomb(Cell cell) {
            return insideCell(cell) && bombAt[cell.index()] >= 0;
        }

        private boolean insideCell(Cell cell) {
            return cell.row >= 0 && cell.col >= 0 && cell.row < GridMap.ROWS && cell.col < GridMap.COLS;
        }
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
            searchGeneration++;
            targetGeneration++;
            tail = 0;
            if (searchGeneration == Integer.MAX_VALUE || targetGeneration == Integer.MAX_VALUE) {
                Arrays.fill(seenStamp, 0);
                Arrays.fill(targetStamp, 0);
                searchGeneration = 1;
                targetGeneration = 1;
            }
        }
    }

    private static final class Reachability {
        final int startPose;
        final int generation;
        final int[] seenStamp;
        final int[] prev;
        final byte[] action;

        Reachability(int startPose, int generation, int[] seenStamp, int[] prev, byte[] action) {
            this.startPose = startPose;
            this.generation = generation;
            this.seenStamp = seenStamp;
            this.prev = prev;
            this.action = action;
        }

        boolean canReach(Cell cell, char heading) {
            if (cell.row < 0 || cell.col < 0 || cell.row >= GridMap.ROWS || cell.col >= GridMap.COLS) return false;
            return seenStamp[poseIndex(cell, heading)] == generation;
        }

        ArrayList<String> actionsTo(Cell target, char heading) {
            ArrayList<String> reversed = new ArrayList<>();
            int current = poseIndex(target, heading);
            while (current != startPose) {
                if (current < 0 || seenStamp[current] != generation || prev[current] < 0) return new ArrayList<>();
                reversed.add(NativePlanner.actionName(action[current]));
                current = prev[current];
            }
            ArrayList<String> out = new ArrayList<>();
            for (int i = reversed.size() - 1; i >= 0; i--) out.add(reversed.get(i));
            return out;
        }

        ArrayList<Cell> pathTo(Cell target, char heading) {
            ArrayList<Cell> reversed = new ArrayList<>();
            int current = poseIndex(target, heading);
            while (current != startPose) {
                if (current < 0 || seenStamp[current] != generation || prev[current] < 0) return new ArrayList<>();
                reversed.add(poseCell(current));
                current = prev[current];
            }
            ArrayList<Cell> out = new ArrayList<>();
            for (int i = reversed.size() - 1; i >= 0; i--) out.add(reversed.get(i));
            return out;
        }
    }

    private static final class RecognitionObject {
        final String label;
        final Cell pos;

        RecognitionObject(String label, Cell pos) {
            this.label = label;
            this.pos = pos;
        }
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
