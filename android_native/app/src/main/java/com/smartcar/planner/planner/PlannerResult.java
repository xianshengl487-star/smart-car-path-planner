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

    // Diagnostic counters -- describe why a solve failed or what was pruned.
    public int prunedByDeadlock;
    public int prunedByActionLimit;
    public int prunedByBestCost;
    public int prunedByFrontierTrim;
    public boolean timeoutHit;
    public boolean expandedLimitHit;
    public boolean frontierLimitHit;
    public boolean actionLimitHit;

    /** Build a one-line summary of diagnostic counters for display. */
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
        return sb.toString().trim();
    }
}
