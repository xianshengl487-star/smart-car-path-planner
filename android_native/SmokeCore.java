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
            if (!optimal.solved) { fail(label + " failed: " + optimal.message); failed++; }
            else if (optimal.totalCost != expectedOptimalCosts[levelId - 100]) {
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
            if (!fast.solved) { fail(label + " failed: " + fast.message); failed++; }
            else if (fast.totalCost < optimal.totalCost) { fail(label + " cost below optimal"); failed++; }
            else if (levelId == 103 && !containsExplosion(fast)) { fail(label + " missing bomb explosion"); failed++; }
            else {
                String err = ActionReplayValidator.validate(map, fast);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + fast.totalCost + " expanded=" + fast.expanded); passed++; }
            }
        }

        // --- Test 7: 103 stm32Strict ---
        {
            PlannerResult tight103 = planner.solve(GridMap.template(103), PerformanceLimits.stm32Strict());
            String label = "103 stm32Strict";
            if (!tight103.solved) { fail(label + " failed: " + tight103.message); failed++; }
            else if (tight103.maxFrontierSeen > PerformanceLimits.stm32Strict().maxFrontier) {
                fail(label + " exceeded frontier budget: " + tight103.maxFrontierSeen); failed++;
            } else {
                String err = ActionReplayValidator.validate(GridMap.template(103), tight103);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + tight103.totalCost + " expanded=" + tight103.expanded); passed++; }
            }
        }

        // --- Test 8: 103 relaxed budget ---
        {
            PlannerResult fast103 = planner.solve(GridMap.template(103), PerformanceLimits.stm32Relaxed());
            String label = "103 relaxed budget";
            if (!fast103.solved) { fail(label + " failed: " + fast103.message); failed++; }
            else if (fast103.expanded > 30000) { fail(label + " expanded too high: " + fast103.expanded); failed++; }
            else if (fast103.maxFrontierSeen > PerformanceLimits.stm32Relaxed().maxFrontier) {
                fail(label + " frontier exceeded: " + fast103.maxFrontierSeen); failed++;
            } else { pass(label + " expanded=" + fast103.expanded + " frontier=" + fast103.maxFrontierSeen); passed++; }
        }

        // --- Test 9: 103 explosion+validate ---
        {
            PlannerResult fast103 = planner.solve(GridMap.template(103), PerformanceLimits.stm32Relaxed());
            String label = "103 relaxed explosion+validate";
            if (!fast103.solved) { fail(label + " failed: " + fast103.message); failed++; }
            else if (!containsExplosion(fast103)) { fail(label + " missing explosion"); failed++; }
            else {
                String err = ActionReplayValidator.validate(GridMap.template(103), fast103);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " OK"); passed++; }
            }
        }

        // --- Test 10: 103 strict bomb diags ---
        {
            PlannerResult opt103 = planner.solve(GridMap.template(103), PerformanceLimits.strictShortest());
            String label = "103 strict bomb diags";
            if (!opt103.solved) { fail(label + " failed: " + opt103.message); failed++; }
            else if (!containsExplosion(opt103)) { fail(label + " missing explosion in strict mode"); failed++; }
            else {
                String err = ActionReplayValidator.validate(GridMap.template(103), opt103);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " bombMoves=" + opt103.bombMovesGenerated + " bombBoom=" + opt103.bombExplosionsGenerated); passed++; }
            }
        }

        // --- Test 11-14: illegal maps ---
        { GridMap bad = new GridMap(); bad.setToken(5,1,'.'); bad.setToken(3,4,'1'); bad.setToken(3,10,'a'); bad.rebuildObjects();
          PlannerResult r = planner.solve(bad, PerformanceLimits.strictShortest());
          String L = "no P"; if (r.solved) { fail(L); failed++; } else { pass(L + ": " + r.message); passed++; } }
        { GridMap bad = GridMap.template(101); bad.setToken(3,10,'.'); bad.rebuildObjects();
          PlannerResult r = planner.solve(bad, PerformanceLimits.strictShortest());
          String L = "B1 no T1"; if (r.solved) { fail(L); failed++; } else { pass(L + ": " + r.message); passed++; } }
        { GridMap bad = new GridMap(); bad.setToken(0,5,'.'); bad.setToken(3,4,'1'); bad.setToken(3,10,'a'); bad.rebuildObjects();
          PlannerResult r = planner.solve(bad, PerformanceLimits.strictShortest());
          String L = "boundary"; if (r.solved) { fail(L); failed++; } else { pass(L + ": " + r.message); passed++; } }
        { GridMap bad = GridMap.template(101); bad.setToken(6,1,'P'); bad.rebuildObjects();
          PlannerResult r = planner.solve(bad, PerformanceLimits.strictShortest());
          String L = "multi P"; if (r.solved) { fail(L); failed++; } else { pass(L + ": " + r.message); passed++; } }

        // --- Test 15: maxPushActions=1 enforcement ---
        { GridMap map = GridMap.template(101);
          PerformanceLimits tiny = PerformanceLimits.strictShortest();
          tiny.enforceActionLimitDuringSearch = true;
          tiny.maxPushActions = 1;
          PlannerResult r = planner.solve(map, tiny);
          String L = "maxPushActions=1";
          if (r.solved) { fail(L); failed++; } else { pass(L + ": " + r.message); passed++; } }

        // --- Test 16: 103 relaxed not recognition-only ---
        {
            PlannerResult r = planner.solve(GridMap.template(103), PerformanceLimits.stm32Relaxed());
            String label = "103 not-recog-only";
            if (!r.solved) { fail(label + " failed: " + r.message); failed++; }
            else if (r.recognitionCost > 0 && r.actions.size() <= r.recognitionCost) {
                fail(label + " only recognition actions, no push!"); failed++;
            } else { pass(label + " actions=" + r.actions.size() + " recog=" + r.recognitionCost); passed++; }
        }

        // --- Test 17: strict no bomb bias ---
        {
            PlannerResult r = planner.solve(GridMap.template(103), PerformanceLimits.strictShortest());
            String label = "103 strict no bias";
            if (!r.solved) { fail(label + " failed: " + r.message); failed++; }
            else if (r.bombPriorityUsed) { fail(label + " bombPriorityUsed should be false"); failed++; }
            else { pass(label + " bombPriorityUsed=false"); passed++; } }

        // --- Test 18: 103 strict validation ---
        {
            PlannerResult r = planner.solve(GridMap.template(103), PerformanceLimits.stm32Strict());
            String label = "103 strict validation";
            if (!r.solved) { fail(label + " failed: " + r.message); failed++; }
            else {
                String err = ActionReplayValidator.validate(GridMap.template(103), r);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + r.totalCost); passed++; } } }

        // --- Test 19: 104 strictShortest (4 boxes, no bombs) ---
        {
            PlannerResult r = planner.solve(GridMap.template(104), PerformanceLimits.strictShortest());
            String label = "104 strictShortest";
            if (!r.solved) { fail(label + " failed: " + r.message); failed++; }
            else {
                String err = ActionReplayValidator.validate(GridMap.template(104), r);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + r.totalCost + " expanded=" + r.expanded); passed++; } } }

        // --- Test 20: 105 strictShortest (2 bombs) ---
        {
            PlannerResult r = planner.solve(GridMap.template(105), PerformanceLimits.strictShortest());
            String label = "105 strictShortest";
            if (!r.solved) { fail(label + " failed: " + r.message); failed++; }
            else if (!containsExplosion(r)) { fail(label + " missing explosion"); failed++; }
            else {
                String err = ActionReplayValidator.validate(GridMap.template(105), r);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + r.totalCost + " expanded=" + r.expanded); passed++; } } }

        // --- Test 21: 106 strictShortest (recognition + bomb) ---
        {
            PlannerResult r = planner.solve(GridMap.template(106), PerformanceLimits.strictShortest());
            String label = "106 strictShortest";
            if (!r.solved) { fail(label + " failed: " + r.message); failed++; }
            else if (r.recognitionCost == 0) { fail(label + " missing recognition"); failed++; }
            else if (!containsExplosion(r)) { fail(label + " missing explosion"); failed++; }
            else {
                String err = ActionReplayValidator.validate(GridMap.template(106), r);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + r.totalCost + " expanded=" + r.expanded); passed++; } } }

        // --- Test 22: 104 stm32Relaxed ---
        {
            PlannerResult r = planner.solve(GridMap.template(104), PerformanceLimits.stm32Relaxed());
            String label = "104 stm32Relaxed";
            if (!r.solved) { fail(label + " failed: " + r.message); failed++; }
            else {
                String err = ActionReplayValidator.validate(GridMap.template(104), r);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + r.totalCost + " expanded=" + r.expanded); passed++; } } }

        // --- Test 23: 105 stm32Relaxed ---
        {
            PlannerResult r = planner.solve(GridMap.template(105), PerformanceLimits.stm32Relaxed());
            String label = "105 stm32Relaxed";
            if (!r.solved) { fail(label + " failed: " + r.message); failed++; }
            else if (!containsExplosion(r)) { fail(label + " missing explosion"); failed++; }
            else {
                String err = ActionReplayValidator.validate(GridMap.template(105), r);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + r.totalCost + " expanded=" + r.expanded); passed++; } } }

        // --- Test 24: 106 stm32Relaxed ---
        {
            PlannerResult r = planner.solve(GridMap.template(106), PerformanceLimits.stm32Relaxed());
            String label = "106 stm32Relaxed";
            if (!r.solved) { fail(label + " failed: " + r.message); failed++; }
            else if (r.recognitionCost == 0) { fail(label + " missing recognition"); failed++; }
            else {
                String err = ActionReplayValidator.validate(GridMap.template(106), r);
                if (err != null) { fail(label + " validation: " + err); failed++; }
                else { pass(label + " cost=" + r.totalCost + " expanded=" + r.expanded); passed++; } } }

        // --- Test 25: map codec 106 roundtrip preserves hard-map flags ---
        {
            String label = "map codec 106 roundtrip";
            try {
                GridMap source = GridMap.template(106);
                String text = MapTextCodec.encode(source, 106, "smoke-hard");
                MapTextCodec.DecodeResult decoded = MapTextCodec.decode(text, 101);
                GridMap.ValidationResult validation = decoded.map.validate();
                if (decoded.levelId != 106) { fail(label + " level changed: " + decoded.levelId); failed++; }
                else if (!sameCells(source, decoded.map)) { fail(label + " cells changed"); failed++; }
                else if (!validation.ok) { fail(label + " validation failed: " + validation.message); failed++; }
                else if (!decoded.map.requiresRecognition || !decoded.map.allowBombPush) { fail(label + " flags changed"); failed++; }
                else { pass(label); passed++; }
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
        for (int i = 0; i < GridMap.CELLS; i++) if (a.cells[i] != b.cells[i]) return false;
        return true;
    }
    private static void pass(String msg) { System.out.println("PASS: " + msg); }
    private static void fail(String msg) { System.out.println("FAIL: " + msg); }
}
