package com.smartcar.planner.planner;

public final class PerformanceLimits {
    public int maxExpanded = 60000;
    public int maxFrontier = 12000;
    public int maxActions = 128;
    public long maxMillis = 600;
    public boolean strictShortest = true;
    public boolean trimFrontier = false;
    public int heuristicWeight = 1;

    // When false, the search phase does not hard-cut nodes that exceed maxActions
    // or the frontier cap. strictShortest must set this to false so that true
    // optimal solutions are never silently pruned during A* expansion.
    public boolean enforceActionLimitDuringSearch = true;
    public boolean enforceFrontierLimitDuringSearch = true;

    // Bomb search controls: only active in non-strict modes.
    // In strict mode these are all false to preserve optimality.
    public boolean bombPriorityBias = false;      // negative f-offset for bomb actions
    public int bombMoveDepthLimit = 16;           // max consecutive bomb moves without explosion

    public static PerformanceLimits strictShortest() {
        PerformanceLimits limits = new PerformanceLimits();
        limits.maxExpanded = 250000;
        limits.maxFrontier = Integer.MAX_VALUE;
        limits.maxActions = Integer.MAX_VALUE;
        limits.maxMillis = 30000;
        limits.strictShortest = true;
        limits.trimFrontier = false;
        limits.heuristicWeight = 1;
        limits.enforceActionLimitDuringSearch = false;
        limits.enforceFrontierLimitDuringSearch = false;
        limits.bombPriorityBias = false;  // NEVER bias in strict mode
        limits.bombMoveDepthLimit = 0;    // disabled in strict mode
        return limits;
    }

    public static PerformanceLimits stm32Strict() {
        PerformanceLimits limits = new PerformanceLimits();
        limits.maxExpanded = 6000;
        limits.maxFrontier = 1200;
        limits.maxActions = 192;
        limits.maxMillis = 1000;
        limits.strictShortest = false;
        limits.trimFrontier = true;
        limits.heuristicWeight = 3;
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
        limits.maxActions = 192;
        limits.maxMillis = 30000;
        limits.strictShortest = false;
        limits.trimFrontier = true;
        limits.heuristicWeight = 2;
        limits.enforceActionLimitDuringSearch = true;
        limits.enforceFrontierLimitDuringSearch = true;
        limits.bombPriorityBias = true;
        limits.bombMoveDepthLimit = 16;
        return limits;
    }
}
