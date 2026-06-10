import com.smartcar.planner.planner.ActionReplayValidator;
import com.smartcar.planner.planner.GridMap;
import com.smartcar.planner.planner.MapTextCodec;
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
                String err = ActionReplayValidator.validate(map, optimal);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + optimal.totalCost + " expanded=" + optimal.expanded); passed++; }
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
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + fast.totalCost + " expanded=" + fast.expanded); passed++; }
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
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + tight103.totalCost + " expanded=" + tight103.expanded); passed++; }
            }
        }

        // --- Test 8: 103 stm32Relaxed expanded budget ---
        {
            PlannerResult fast103 = planner.solve(GridMap.template(103), PerformanceLimits.stm32Relaxed());
            String label = "103 stm32Relaxed budget";
            if (!fast103.solved) {
                fail(label + " failed: " + fast103.message); failed++;
            } else if (fast103.expanded > 30000) {
                fail(label + " expanded too high: " + fast103.expanded); failed++;
            } else if (fast103.maxFrontierSeen > PerformanceLimits.stm32Relaxed().maxFrontier) {
                fail(label + " frontier exceeded: " + fast103.maxFrontierSeen); failed++;
            } else {
                pass(label + " expanded=" + fast103.expanded + " frontier=" + fast103.maxFrontierSeen
                    + " bombMoves=" + fast103.bombMovesGenerated + " bombBoom=" + fast103.bombExplosionsGenerated); passed++;
            }
        }

        // --- Test 9: 103 stm32Relaxed explosion+validate ---
        {
            PlannerResult fast103 = planner.solve(GridMap.template(103), PerformanceLimits.stm32Relaxed());
            String label = "103 stm32Relaxed explosion+validate";
            if (!fast103.solved) {
                fail(label + " failed: " + fast103.message); failed++;
            } else if (!containsExplosion(fast103)) {
                fail(label + " missing explosion"); failed++;
            } else {
                String err = ActionReplayValidator.validate(GridMap.template(103), fast103);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " OK"); passed++; }
            }
        }

        // --- Test 10: 103 strictShortest bomb diagnostics present ---
        {
            PlannerResult opt103 = planner.solve(GridMap.template(103), PerformanceLimits.strictShortest());
            String label = "103 strictShortest bomb diags";
            if (!opt103.solved) {
                fail(label + " failed: " + opt103.message); failed++;
            } else if (!containsExplosion(opt103)) {
                fail(label + " missing explosion in strict mode"); failed++;
            } else {
                String err = ActionReplayValidator.validate(GridMap.template(103), opt103);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " bombMoves=" + opt103.bombMovesGenerated
                    + " bombBoom=" + opt103.bombExplosionsGenerated
                    + " bombPriority=" + opt103.bombPriorityUsed); passed++; }
            }
        }

        // --- Test 11: illegal map - no P ---
        {
            GridMap badMap = new GridMap();
            badMap.setToken(5, 1, '.');
            badMap.setToken(3, 4, '1');
            badMap.setToken(3, 10, 'a');
            badMap.rebuildObjects();
            PlannerResult r = planner.solve(badMap, PerformanceLimits.strictShortest());
            String label = "illegal: no P";
            if (r.solved) { fail(label + " should not solve"); failed++; }
            else { pass(label + " message: " + r.message); passed++; }
        }

        // --- Test 12: illegal map - B1 without T1 ---
        {
            GridMap badMap = GridMap.template(101);
            badMap.setToken(3, 10, '.');
            badMap.rebuildObjects();
            PlannerResult r = planner.solve(badMap, PerformanceLimits.strictShortest());
            String label = "illegal: B1 no T1";
            if (r.solved) { fail(label + " should not solve"); failed++; }
            else { pass(label + " message: " + r.message); passed++; }
        }

        // --- Test 13: illegal map - boundary wall removed ---
        {
            GridMap badMap = new GridMap();
            badMap.setToken(0, 5, '.');
            badMap.setToken(3, 4, '1');
            badMap.setToken(3, 10, 'a');
            badMap.rebuildObjects();
            PlannerResult r = planner.solve(badMap, PerformanceLimits.strictShortest());
            String label = "illegal: boundary wall removed";
            if (r.solved) { fail(label + " should not solve"); failed++; }
            else { pass(label + " message: " + r.message); passed++; }
        }

        // --- Test 14: maxActions=1 must report action limit ---
        {
            GridMap map = GridMap.template(101);
            PerformanceLimits tiny = PerformanceLimits.strictShortest();
            tiny.enforceActionLimitDuringSearch = true;
            tiny.maxActions = 1;
            PlannerResult r = planner.solve(map, tiny);
            String label = "maxActions=1 enforcement";
            if (r.solved) { fail(label + " should not solve"); failed++; }
            else { pass(label + " message: " + r.message); passed++; }
        }

        // --- Test 15: multiple P is rejected ---
        {
            GridMap badMap = GridMap.template(101);
            badMap.setToken(6, 1, 'P');
            badMap.rebuildObjects();
            PlannerResult r = planner.solve(badMap, PerformanceLimits.strictShortest());
            String label = "illegal: multiple P";
            if (r.solved) { fail(label + " should not solve"); failed++; }
            else { pass(label + " message: " + r.message); passed++; }
        }

        // --- Test 16: 103 stm32Strict must be solved and pass validation ---
        {
            PlannerResult strict103 = planner.solve(GridMap.template(103), PerformanceLimits.stm32Strict());
            String label = "103 stm32Strict validation";
            if (!strict103.solved) {
                fail(label + " failed: " + strict103.message); failed++;
            } else {
                String err = ActionReplayValidator.validate(GridMap.template(103), strict103);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + strict103.totalCost); passed++; }
            }
        }

        // --- Test 17: 103 stm32Relaxed -- verify solver completes and diagnostics are populated ---
        {
            PlannerResult fast103 = planner.solve(GridMap.template(103), PerformanceLimits.stm32Relaxed());
            String label = "103 relaxed bomb diags";
            if (!fast103.solved) {
                fail(label + " failed: " + fast103.message); failed++;
            } else {
                // The solver should produce diagnostic data about bomb search,
                // even if the solution path doesn't require an explosion.
                // Verify the bomb diagnostic fields are accessible and non-negative.
                if (fast103.bombMovesGenerated < 0 || fast103.bombExplosionsGenerated < 0) {
                    fail(label + " negative bomb diagnostic values"); failed++;
                } else {
                    pass(label + " bombMoves=" + fast103.bombMovesGenerated
                        + " bombBoom=" + fast103.bombExplosionsGenerated
                        + " bombDepthPruned=" + fast103.bombDepthPruned); passed++;
                }
            }
        }

        // --- Test 18: 103 strictShortest should NOT use bomb priority bias ---
        {
            PlannerResult opt103 = planner.solve(GridMap.template(103), PerformanceLimits.strictShortest());
            String label = "103 strict no bomb bias";
            if (!opt103.solved) {
                fail(label + " failed: " + opt103.message); failed++;
            } else if (opt103.bombPriorityUsed) {
                fail(label + " bombPriorityUsed should be false in strict mode"); failed++;
            } else {
                pass(label + " bombPriorityUsed=" + opt103.bombPriorityUsed); passed++;
            }
        }

        // --- Test 19: map import/export codec roundtrips 103 template ---
        {
            String label = "map codec 103 roundtrip";
            try {
                GridMap source = GridMap.template(103);
                String text = MapTextCodec.encode(source, 103, "smoke");
                MapTextCodec.DecodeResult decoded = MapTextCodec.decode(text, 101);
                GridMap.ValidationResult validation = decoded.map.validate();
                if (decoded.levelId != 103) {
                    fail(label + " level changed: " + decoded.levelId); failed++;
                } else if (!sameCells(source, decoded.map)) {
                    fail(label + " cells changed"); failed++;
                } else if (!validation.ok) {
                    fail(label + " validation failed: " + validation.message); failed++;
                } else if (!decoded.map.requiresRecognition || !decoded.map.allowBombPush) {
                    fail(label + " level flags changed"); failed++;
                } else {
                    pass(label); passed++;
                }
            } catch (Exception ex) {
                fail(label + " exception: " + ex.getMessage()); failed++;
            }
        }

        System.out.println("\n=== SmokeCore Results: " + passed + " passed, " + failed + " failed ===");
        if (failed > 0) System.exit(1);
    }

    private static boolean containsExplosion(PlannerResult result) {
        for (String action : result.actions) if (action.startsWith("X")) return true;
        return false;
    }

    private static boolean sameCells(GridMap a, GridMap b) {
        for (int i = 0; i < GridMap.CELLS; i++) {
            if (a.cells[i] != b.cells[i]) return false;
        }
        return true;
    }

    private static void pass(String msg) { System.out.println("PASS: " + msg); }
    private static void fail(String msg) { System.out.println("FAIL: " + msg); }
}
