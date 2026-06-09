package com.smartcar.planner.planner;

public final class PerformanceLimits {
    public int maxExpanded = 60000;
    public int maxFrontier = 12000;
    public int maxActions = 128;
    public long maxMillis = 600;
    public boolean strictShortest = true;
    public boolean trimFrontier = false;
    public int heuristicWeight = 1;

    public static PerformanceLimits strictShortest() {
        PerformanceLimits limits = new PerformanceLimits();
        limits.maxExpanded = 250000;
        limits.maxFrontier = 120000;
        limits.maxActions = 192;
        limits.maxMillis = 30000;
        limits.strictShortest = true;
        limits.trimFrontier = false;
        limits.heuristicWeight = 1;
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
        return limits;
    }
}
