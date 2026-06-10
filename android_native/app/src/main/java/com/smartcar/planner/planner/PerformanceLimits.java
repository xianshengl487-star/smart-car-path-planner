package com.smartcar.planner.planner;

public final class PerformanceLimits {
    public int maxExpanded = 60000;
    public int maxFrontier = 12000;
    public long maxMillis = 600;
    public boolean strictShortest = true;
    public boolean trimFrontier = false;
    public int heuristicWeight = 1;

    // Action budget split: recognition and push phases have separate budgets.
    public int maxRecognitionActions = 120;
    public int maxPushActions = 192;
    public int maxTotalActions = 260;

    public boolean enforceActionLimitDuringSearch = true;
    public boolean enforceFrontierLimitDuringSearch = true;

    // Bomb search controls.
    public boolean bombPriorityBias = false;
    public int bombMoveDepthLimit = 16;

    public static PerformanceLimits strictShortest() {
        PerformanceLimits limits = new PerformanceLimits();
        limits.maxExpanded = 250000;
        limits.maxFrontier = Integer.MAX_VALUE;
        limits.maxMillis = 30000;
        limits.strictShortest = true;
        limits.trimFrontier = false;
        limits.heuristicWeight = 1;
        limits.maxRecognitionActions = Integer.MAX_VALUE;
        limits.maxPushActions = Integer.MAX_VALUE;
        limits.maxTotalActions = Integer.MAX_VALUE;
        limits.enforceActionLimitDuringSearch = false;
        limits.enforceFrontierLimitDuringSearch = false;
        limits.bombPriorityBias = false;
        limits.bombMoveDepthLimit = 0;
        return limits;
    }

    public static PerformanceLimits stm32Strict() {
        PerformanceLimits limits = new PerformanceLimits();
        limits.maxExpanded = 6000;
        limits.maxFrontier = 1200;
        limits.maxMillis = 1000;
        limits.strictShortest = false;
        limits.trimFrontier = true;
        limits.heuristicWeight = 3;
        limits.maxRecognitionActions = 80;
        limits.maxPushActions = 192;
        limits.maxTotalActions = 260;
        limits.enforceActionLimitDuringSearch = true;
        limits.enforceFrontierLimitDuringSearch = true;
        limits.bombPriorityBias = true;
        limits.bombMoveDepthLimit = 12;
        return limits;
    }

    public static PerformanceLimits stm32Relaxed() {
        PerformanceLimits limits = new PerformanceLimits();
        limits.maxExpanded = 250000;
        limits.maxFrontier = 50000;
        limits.maxMillis = 30000;
        limits.strictShortest = false;
        limits.trimFrontier = true;
        limits.heuristicWeight = 2;
        limits.maxRecognitionActions = 80;
        limits.maxPushActions = 192;
        limits.maxTotalActions = 260;
        limits.enforceActionLimitDuringSearch = true;
        limits.enforceFrontierLimitDuringSearch = true;
        limits.bombPriorityBias = true;
        limits.bombMoveDepthLimit = 16;
        return limits;
    }
}
