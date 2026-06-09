package com.smartcar.planner;

import android.app.Activity;
import android.content.pm.ActivityInfo;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;

import com.smartcar.planner.planner.GridMap;
import com.smartcar.planner.planner.NativePlanner;
import com.smartcar.planner.planner.PerformanceLimits;
import com.smartcar.planner.planner.PlannerResult;

public final class MainActivity extends Activity {
    private MapEditorView mapView;
    private TextView resultText;
    private Spinner levelSpinner;
    private Spinner brushSpinner;
    private Spinner limitSpinner;
    private Button playButton;
    private Button stepButton;
    private Button speedButton;
    private PlannerResult currentResult;
    private boolean playing;
    private int speedIndex = 0;

    private final NativePlanner planner = new NativePlanner();
    private final char[] brushValues = {'.', '#', 'P', '1', 'a', '2', 'b', '3', 'c', 'X'};
    private final int[] speedValues = {1, 2, 4, 8};
    private final Handler playbackHandler = new Handler(Looper.getMainLooper());
    private final Runnable playbackTick = new Runnable() {
        @Override
        public void run() {
            if (!playing) return;
            advancePlayback(1);
            if (playing) playbackHandler.postDelayed(this, playbackDelayMs());
        }
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE);

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.HORIZONTAL);
        root.setPadding(dp(10), dp(10), dp(10), dp(10));

        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(0, 0, dp(10), 0);

        TextView title = new TextView(this);
        CharSequence appLabel = getApplicationInfo().loadLabel(getPackageManager());
        title.setText(String.valueOf(appLabel) + "\n横屏跑图测试");
        title.setTextSize(22);
        title.setGravity(Gravity.CENTER_HORIZONTAL);
        panel.addView(title, new LinearLayout.LayoutParams(-1, -2));

        levelSpinner = spinner(new String[]{"101 只推箱", "102 识别+推箱", "103 识别箱/目标+炸弹"});
        brushSpinner = spinner(new String[]{".", "#", "P", "B1", "T1", "B2", "T2", "B3", "T3", "X"});
        limitSpinner = spinner(new String[]{"严格最短", "STM32 快速", "STM32 极限"});
        panel.addView(levelSpinner, new LinearLayout.LayoutParams(-1, -2));
        panel.addView(brushSpinner, new LinearLayout.LayoutParams(-1, -2));
        panel.addView(limitSpinner, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        Button templateButton = new Button(this);
        templateButton.setText("载入模板");
        Button runButton = new Button(this);
        runButton.setText("手机本机跑图");
        buttons.addView(templateButton, new LinearLayout.LayoutParams(0, -2, 1));
        buttons.addView(runButton, new LinearLayout.LayoutParams(0, -2, 1));
        panel.addView(buttons);

        LinearLayout playback = new LinearLayout(this);
        playback.setOrientation(LinearLayout.HORIZONTAL);
        playButton = new Button(this);
        stepButton = new Button(this);
        speedButton = new Button(this);
        playButton.setText("播放");
        stepButton.setText("单步");
        updateSpeedButton();
        playback.addView(playButton, new LinearLayout.LayoutParams(0, -2, 1));
        playback.addView(stepButton, new LinearLayout.LayoutParams(0, -2, 1));
        playback.addView(speedButton, new LinearLayout.LayoutParams(0, -2, 1));
        panel.addView(playback);

        mapView = new MapEditorView(this);
        mapView.setEditListener(() -> {
            stopPlayback();
            currentResult = null;
            resultText.setText("地图已编辑，请重新跑图。");
        });

        resultText = new TextView(this);
        resultText.setTextSize(14);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(resultText);
        panel.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));

        root.addView(panel, new LinearLayout.LayoutParams(dp(320), -1));
        root.addView(mapView, new LinearLayout.LayoutParams(0, -1, 1));

        setContentView(root);

        brushSpinner.setOnItemSelectedListener(new SimpleItemSelectedListener(pos -> mapView.setBrush(brushValues[pos])));
        templateButton.setOnClickListener(v -> loadSelectedTemplate());
        runButton.setOnClickListener(v -> runPlanner());
        playButton.setOnClickListener(v -> togglePlayback());
        stepButton.setOnClickListener(v -> {
            stopPlayback();
            advancePlayback(1);
        });
        speedButton.setOnClickListener(v -> cycleSpeed());
        loadSelectedTemplate();
    }

    @Override
    protected void onPause() {
        super.onPause();
        stopPlayback();
    }

    private Spinner spinner(String[] values) {
        Spinner spinner = new Spinner(this);
        spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, values));
        return spinner;
    }

    private void loadSelectedTemplate() {
        stopPlayback();
        currentResult = null;
        int level = 101 + levelSpinner.getSelectedItemPosition();
        mapView.setMap(GridMap.template(level));
        resultText.setText("已载入 " + level + "，请横屏编辑/播放。");
    }

    private void runPlanner() {
        stopPlayback();
        PerformanceLimits limits;
        int mode = limitSpinner.getSelectedItemPosition();
        if (mode == 0) {
            limits = PerformanceLimits.strictShortest();
        } else if (mode == 1) {
            limits = PerformanceLimits.stm32Relaxed();
        } else {
            limits = PerformanceLimits.stm32Strict();
        }
        PlannerResult result = planner.solve(mapView.getMap(), limits);
        currentResult = result;
        mapView.setResult(result);
        updateResultText();
        if (result.solved) startPlayback();
    }

    private void togglePlayback() {
        if (playing) {
            stopPlayback();
        } else {
            startPlayback();
        }
    }

    private void startPlayback() {
        if (currentResult == null || currentResult.actions.isEmpty()) return;
        if (mapView.getAnimationStep() >= mapView.getActionCount()) mapView.setAnimationStep(0);
        playing = true;
        playButton.setText("暂停");
        playbackHandler.removeCallbacks(playbackTick);
        playbackHandler.postDelayed(playbackTick, playbackDelayMs());
    }

    private void stopPlayback() {
        playing = false;
        playbackHandler.removeCallbacks(playbackTick);
        if (playButton != null) playButton.setText("播放");
    }

    private void advancePlayback(int steps) {
        if (currentResult == null) {
            stopPlayback();
            return;
        }
        int nextStep = Math.min(mapView.getAnimationStep() + steps, mapView.getActionCount());
        mapView.setAnimationStep(nextStep);
        updateResultText();
        if (nextStep >= mapView.getActionCount()) stopPlayback();
    }

    private void cycleSpeed() {
        speedIndex = (speedIndex + 1) % speedValues.length;
        updateSpeedButton();
        if (playing) {
            playbackHandler.removeCallbacks(playbackTick);
            playbackHandler.postDelayed(playbackTick, playbackDelayMs());
        }
        updateResultText();
    }

    private int playbackDelayMs() {
        return Math.max(45, 420 / speedValues[speedIndex]);
    }

    private void updateSpeedButton() {
        if (speedButton != null) speedButton.setText("快进 x" + speedValues[speedIndex]);
    }

    private void updateResultText() {
        PlannerResult result = currentResult;
        if (result == null) return;
        int step = mapView.getAnimationStep();
        StringBuilder sb = new StringBuilder();
        sb.append(result.solved ? "OK" : "FAILED")
            .append("  frame=").append(step).append('/').append(mapView.getActionCount())
            .append("  speed=x").append(speedValues[speedIndex]).append('\n');
        sb.append(result.message).append('\n');
        sb.append("cost=").append(result.totalCost)
            .append(", scan=").append(result.recognitionCost)
            .append(", pushes=").append(result.pushes).append('\n');
        sb.append("expanded=").append(result.expanded)
            .append(", frontierMax=").append(result.maxFrontierSeen).append('\n');
        if (step > 0 && step <= result.actions.size()) {
            sb.append("currentAction=").append(result.actions.get(step - 1)).append('\n');
        }
        sb.append("actions=").append(result.actions).append('\n');
        sb.append("recognition=").append(result.recognitionOrder);
        resultText.setText(sb.toString());
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private interface SelectionCallback {
        void onSelected(int position);
    }

    private static final class SimpleItemSelectedListener implements android.widget.AdapterView.OnItemSelectedListener {
        private final SelectionCallback callback;

        SimpleItemSelectedListener(SelectionCallback callback) {
            this.callback = callback;
        }

        @Override
        public void onItemSelected(android.widget.AdapterView<?> parent, android.view.View view, int position, long id) {
            callback.onSelected(position);
        }

        @Override
        public void onNothingSelected(android.widget.AdapterView<?> parent) {
        }
    }
}
