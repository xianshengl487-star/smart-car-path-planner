package com.smartcar.planner.planner;

import java.util.ArrayList;
import java.util.List;

public final class PlannerResult {
    public boolean solved;
    public String message = "";
    public int totalCost;
    public int recognitionCost;
    public int pushes;
    public int expanded;
    public int maxFrontierSeen;
    public final List<String> actions = new ArrayList<>();
    public final List<Cell> playerPath = new ArrayList<>();
    public final List<String> recognitionOrder = new ArrayList<>();

    // Diagnostic counters.
    public int prunedByDeadlock;
    public int prunedByActionLimit;
    public int prunedByBestCost;
    public int prunedByFrontierTrim;
    public boolean timeoutHit;
    public boolean expandedLimitHit;
    public boolean frontierLimitHit;
    public boolean actionLimitHit;

    // Bomb diagnostics.
    public int bombMovesGenerated;
    public int bombExplosionsGenerated;
    public int bombMovesPruned;
    public int bombRelevantWallPruned;
    public boolean bombPriorityUsed;
    public int bombDepthPruned;

    // Partial result tracking.
    public boolean partialRecognitionOnly;
    public boolean pushStageFailed;
    public String nextStageHint = "";
    public int remainingPushBudget;

    public String diagnosticsString() {
        StringBuilder sb = new StringBuilder();
        if (timeoutHit) sb.append("timeout ");
        if (expandedLimitHit) sb.append("expandedLimit ");
        if (frontierLimitHit) sb.append("frontierLimit ");
        if (actionLimitHit) sb.append("actionLimit ");
        if (prunedByDeadlock > 0) sb.append("deadlockPruned=").append(prunedByDeadlock).append(' ');
        if (prunedByActionLimit > 0) sb.append("actionPruned=").append(prunedByActionLimit).append(' ');
        if (prunedByBestCost > 0) sb.append("costPruned=").append(prunedByBestCost).append(' ');
        if (prunedByFrontierTrim > 0) sb.append("frontierTrimmed=").append(prunedByFrontierTrim).append(' ');
        if (bombMovesGenerated > 0 || bombExplosionsGenerated > 0) {
            sb.append("bombMoves=").append(bombMovesGenerated)
              .append(" bombBoom=").append(bombExplosionsGenerated).append(' ');
        }
        if (bombRelevantWallPruned > 0) sb.append("bombWallPruned=").append(bombRelevantWallPruned).append(' ');
        if (bombDepthPruned > 0) sb.append("bombDepthPruned=").append(bombDepthPruned).append(' ');
        if (bombPriorityUsed) sb.append("bombPriority ");
        if (pushStageFailed) sb.append("pushStageFailed ");
        return sb.toString().trim();
    }
}
