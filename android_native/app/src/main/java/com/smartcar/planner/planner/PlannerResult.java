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
}
