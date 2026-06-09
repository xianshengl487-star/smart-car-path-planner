import com.smartcar.planner.planner.GridMap;
import com.smartcar.planner.planner.NativePlanner;
import com.smartcar.planner.planner.PerformanceLimits;
import com.smartcar.planner.planner.PlannerResult;

public final class SmokeCore {
    public static void main(String[] args) {
        NativePlanner planner = new NativePlanner();
        int[] expectedOptimalCosts = {0, 29, 65, 106};
        for (int levelId = 101; levelId <= 103; levelId++) {
            GridMap map = GridMap.template(levelId);
            PlannerResult optimal = planner.solve(map, PerformanceLimits.strictShortest());
            if (!optimal.solved) {
                throw new IllegalStateException(levelId + " optimal failed: " + optimal.message);
            }
            if (optimal.totalCost != expectedOptimalCosts[levelId - 100]) {
                throw new IllegalStateException(levelId
                    + " optimal cost changed: " + optimal.totalCost
                    + " != " + expectedOptimalCosts[levelId - 100]);
            }
            if (levelId == 103 && optimal.expanded > 10000) {
                throw new IllegalStateException("103 optimal expanded regression: " + optimal.expanded);
            }
            PlannerResult fast = planner.solve(map, PerformanceLimits.stm32Relaxed());
            if (!fast.solved) {
                throw new IllegalStateException(levelId + " fast failed: " + fast.message);
            }
            if (fast.totalCost < optimal.totalCost) {
                throw new IllegalStateException(levelId + " fast cost is below optimal cost");
            }
            if (levelId == 103 && !containsExplosion(fast)) {
                throw new IllegalStateException("103 should include at least one bomb explosion action");
            }
            System.out.println(levelId
                + " optimalCost=" + optimal.totalCost
                + " optimalExpanded=" + optimal.expanded
                + " fastCost=" + fast.totalCost
                + " scan=" + fast.recognitionCost
                + " pushes=" + fast.pushes
                + " fastExpanded=" + fast.expanded
                + " fastFrontier=" + fast.maxFrontierSeen);
        }

        PlannerResult tight103 = planner.solve(GridMap.template(103), PerformanceLimits.stm32Strict());
        if (!tight103.solved) {
            throw new IllegalStateException("103 STM32 tight failed: " + tight103.message);
        }
        if (tight103.maxFrontierSeen > PerformanceLimits.stm32Strict().maxFrontier) {
            throw new IllegalStateException("103 STM32 tight exceeded frontier budget: " + tight103.maxFrontierSeen);
        }
        System.out.println("103 stm32Tight solved=true"
            + " cost=" + tight103.totalCost
            + " expanded=" + tight103.expanded
            + " frontier=" + tight103.maxFrontierSeen);
    }

    private static boolean containsExplosion(PlannerResult result) {
        for (String action : result.actions) {
            if (action.startsWith("X")) return true;
        }
        return false;
    }
}
