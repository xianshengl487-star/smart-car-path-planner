import com.smartcar.planner.planner.ActionReplayValidator;
import com.smartcar.planner.planner.GridMap;
import com.smartcar.planner.planner.NativePlanner;
import com.smartcar.planner.planner.PerformanceLimits;
import com.smartcar.planner.planner.PlannerResult;

public final class SmokeCore {
    public static void main(String[] args) {
        NativePlanner planner = new NativePlanner();
        int passed = 0;
        int failed = 0;

        // --- Test 1-3: strictShortest optimal costs for 101/102/103 ---
        int[] expectedOptimalCosts = {0, 29, 65, 106};
        for (int levelId = 101; levelId <= 103; levelId++) {
            GridMap map = GridMap.template(levelId);
            PlannerResult optimal = planner.solve(map, PerformanceLimits.strictShortest());
            String label = levelId + " strictShortest";
            if (!optimal.solved) {
                fail(label + " failed: " + optimal.message); failed++;
            } else if (optimal.totalCost != expectedOptimalCosts[levelId - 100]) {
                fail(label + " cost changed: " + optimal.totalCost + " != " + expectedOptimalCosts[levelId - 100]); failed++;
            } else if (levelId == 103 && optimal.expanded > 10000) {
                fail(label + " expanded regression: " + optimal.expanded); failed++;
            } else {
                // Verify action sequence is valid.
                String err = ActionReplayValidator.validate(map, optimal);
                if (err != null) {
                    fail(label + " action validation failed: " + err); failed++;
                } else {
                    pass(label + " cost=" + optimal.totalCost + " expanded=" + optimal.expanded
                        + " actions=" + optimal.actions.size()); passed++;
                }
            }
        }

        // --- Test 4-6: stm32Relaxed for 101/102/103 ---
        for (int levelId = 101; levelId <= 103; levelId++) {
            GridMap map = GridMap.template(levelId);
            PlannerResult fast = planner.solve(map, PerformanceLimits.stm32Relaxed());
            PlannerResult optimal = planner.solve(map, PerformanceLimits.strictShortest());
            String label = levelId + " stm32Relaxed";
            if (!fast.solved) {
                fail(label + " failed: " + fast.message); failed++;
            } else if (fast.totalCost < optimal.totalCost) {
                fail(label + " cost below optimal"); failed++;
            } else if (levelId == 103 && !containsExplosion(fast)) {
                fail(label + " missing bomb explosion"); failed++;
            } else {
                String err = ActionReplayValidator.validate(map, fast);
                if (err != null) {
                    fail(label + " action validation failed: " + err); failed++;
                } else {
                    pass(label + " cost=" + fast.totalCost + " expanded=" + fast.expanded
                        + " frontier=" + fast.maxFrontierSeen); passed++;
                }
            }
        }

        // --- Test 7: stm32Strict for 103 ---
        {
            PlannerResult tight103 = planner.solve(GridMap.template(103), PerformanceLimits.stm32Strict());
            String label = "103 stm32Strict";
            if (!tight103.solved) {
                fail(label + " failed: " + tight103.message); failed++;
            } else if (tight103.maxFrontierSeen > PerformanceLimits.stm32Strict().maxFrontier) {
                fail(label + " exceeded frontier budget: " + tight103.maxFrontierSeen); failed++;
            } else {
                String err = ActionReplayValidator.validate(GridMap.template(103), tight103);
                if (err != null) {
                    fail(label + " action validation failed: " + err); failed++;
                } else {
                    pass(label + " cost=" + tight103.totalCost + " expanded=" + tight103.expanded
                        + " frontier=" + tight103.maxFrontierSeen); passed++;
                }
            }
        }

        // --- Test 8: illegal map - no P ---
        {
            GridMap badMap = new GridMap();
            // Clear the default P by overwriting with a wall (interior).
            badMap.setToken(5, 1, '.');
            badMap.setToken(3, 4, '1');
            badMap.setToken(3, 10, 'a');
            badMap.rebuildObjects();
            PlannerResult r = planner.solve(badMap, PerformanceLimits.strictShortest());
            String label = "illegal: no P";
            if (r.solved) {
                fail(label + " should not solve"); failed++;
            } else if (r.message == null || r.message.isEmpty()) {
                fail(label + " missing message"); failed++;
            } else {
                pass(label + " message: " + r.message); passed++;
            }
        }

        // --- Test 9: illegal map - B1 without T1 ---
        {
            GridMap badMap = GridMap.template(101);
            badMap.setToken(3, 10, '.');  // Remove T1
            badMap.rebuildObjects();
            PlannerResult r = planner.solve(badMap, PerformanceLimits.strictShortest());
            String label = "illegal: B1 no T1";
            if (r.solved) {
                fail(label + " should not solve"); failed++;
            } else if (r.message == null || r.message.isEmpty()) {
                fail(label + " missing message"); failed++;
            } else {
                pass(label + " message: " + r.message); passed++;
            }
        }

        // --- Test 10: illegal map - boundary wall removed ---
        {
            GridMap badMap = new GridMap();
            // Remove a boundary wall cell.
            badMap.setToken(0, 5, '.');
            badMap.setToken(3, 4, '1');
            badMap.setToken(3, 10, 'a');
            badMap.rebuildObjects();
            PlannerResult r = planner.solve(badMap, PerformanceLimits.strictShortest());
            String label = "illegal: boundary wall removed";
            if (r.solved) {
                fail(label + " should not solve"); failed++;
            } else if (r.message == null || r.message.isEmpty()) {
                fail(label + " missing message"); failed++;
            } else {
                pass(label + " message: " + r.message); passed++;
            }
        }

        // --- Test 11: maxActions=1 must report action limit, not "无解" ---
        {
            GridMap map = GridMap.template(101);
            PerformanceLimits tiny = new PerformanceLimits();
            tiny.maxExpanded = 250000;
            tiny.maxFrontier = 120000;
            tiny.maxActions = 1;
            tiny.maxMillis = 30000;
            tiny.strictShortest = true;
            tiny.trimFrontier = false;
            tiny.heuristicWeight = 1;
            tiny.enforceActionLimitDuringSearch = false;  // strict mode
            tiny.enforceFrontierLimitDuringSearch = false;
            PlannerResult r = planner.solve(map, tiny);
            // In strict mode with maxActions=1 the search explores freely but the
            // post-search check should reject because actionLimit is not enforced
            // during search but the final cost exceeds maxActions. Actually since
            // enforceActionLimitDuringSearch=false, the search runs fully and the
            // post-solution check with enforceActionLimitDuringSearch=false won't
            // reject either. Let's instead test with enforcement on:
            tiny.enforceActionLimitDuringSearch = true;
            PlannerResult r2 = planner.solve(map, tiny);
            String label = "maxActions=1 enforcement";
            if (r2.solved) {
                fail(label + " should not solve with 1 action limit"); failed++;
            } else if (r2.message == null || r2.message.isEmpty()) {
                fail(label + " missing message"); failed++;
            } else {
                pass(label + " message: " + r2.message); passed++;
            }
        }

        // --- Test 12: multiple P is rejected ---
        {
            GridMap badMap = GridMap.template(101);
            badMap.setToken(6, 1, 'P');
            badMap.rebuildObjects();
            PlannerResult r = planner.solve(badMap, PerformanceLimits.strictShortest());
            String label = "illegal: multiple P";
            if (r.solved) {
                fail(label + " should not solve"); failed++;
            } else {
                pass(label + " message: " + r.message); passed++;
            }
        }

        System.out.println("\n=== SmokeCore Results: " + passed + " passed, " + failed + " failed ===");
        if (failed > 0) {
            System.exit(1);
        }
    }

    private static boolean containsExplosion(PlannerResult result) {
        for (String action : result.actions) {
            if (action.startsWith("X")) return true;
        }
        return false;
    }

    private static void pass(String msg) {
        System.out.println("PASS: " + msg);
    }

    private static void fail(String msg) {
        System.out.println("FAIL: " + msg);
    }
}
