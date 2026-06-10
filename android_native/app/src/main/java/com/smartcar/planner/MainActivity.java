package com.smartcar.planner;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.net.Uri;
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
import android.widget.Toast;

import com.smartcar.planner.planner.GridMap;
import com.smartcar.planner.planner.MapTextCodec;
import com.smartcar.planner.planner.NativePlanner;
import com.smartcar.planner.planner.PerformanceLimits;
import com.smartcar.planner.planner.PlannerResult;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.PrintWriter;
import java.io.StringWriter;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.Date;
import java.util.Locale;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;

public final class MainActivity extends Activity {
    private static final int REQUEST_IMPORT_MAP = 3101;
    private static final int REQUEST_EXPORT_REPORT = 3102;

    private MapEditorView mapView;
    private TextView resultText;
    private Spinner levelSpinner;
    private Spinner brushSpinner;
    private Spinner limitSpinner;
    private Button playButton;
    private Button stepButton;
    private Button speedButton;
    private Button runButton;
    private Button importButton;
    private Button reportButton;
    private PlannerResult currentResult;
    private boolean playing;
    private int speedIndex = 0;
    private String pendingReportText = "";
    private String lastExceptionText = "";

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

    // Background thread for solving; this keeps long searches off the UI thread.
    private final ExecutorService solverExecutor = Executors.newSingleThreadExecutor();
    private final AtomicBoolean solving = new AtomicBoolean(false);

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

        levelSpinner = spinner(new String[]{
            "101 只推箱",
            "102 识别+推箱",
            "103 识别箱/目标+炸弹",
            "104 四箱困难",
            "105 双炸弹破墙",
            "106 识别+炸弹困难"
        });
        brushSpinner = spinner(new String[]{".", "#", "P", "B1", "T1", "B2", "T2", "B3", "T3", "X"});
        limitSpinner = spinner(new String[]{"严格最短", "STM32 快速", "STM32 极限"});
        panel.addView(levelSpinner, new LinearLayout.LayoutParams(-1, -2));
        panel.addView(brushSpinner, new LinearLayout.LayoutParams(-1, -2));
        panel.addView(limitSpinner, new LinearLayout.LayoutParams(-1, -2));

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.HORIZONTAL);
        Button templateButton = new Button(this);
        templateButton.setText("载入模板");
        runButton = new Button(this);
        runButton.setText("手机本机跑图");
        buttons.addView(templateButton, new LinearLayout.LayoutParams(0, -2, 1));
        buttons.addView(runButton, new LinearLayout.LayoutParams(0, -2, 1));
        panel.addView(buttons);

        LinearLayout fileButtons = new LinearLayout(this);
        fileButtons.setOrientation(LinearLayout.HORIZONTAL);
        importButton = new Button(this);
        reportButton = new Button(this);
        importButton.setText("导入地图");
        reportButton.setText("导出报告");
        fileButtons.addView(importButton, new LinearLayout.LayoutParams(0, -2, 1));
        fileButtons.addView(reportButton, new LinearLayout.LayoutParams(0, -2, 1));
        panel.addView(fileButtons);

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
            lastExceptionText = "";
            resultText.setText("地图已编辑，请重新跑图。");
        });

        resultText = new TextView(this);
        resultText.setTextSize(14);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(resultText);
        panel.addView(scroll, new LinearLayout.LayoutParams(-1, 0, 1));

        root.addView(panel, new LinearLayout.LayoutParams(dp(340), -1));
        root.addView(mapView, new LinearLayout.LayoutParams(0, -1, 1));

        setContentView(root);

        brushSpinner.setOnItemSelectedListener(new SimpleItemSelectedListener(pos -> mapView.setBrush(brushValues[pos])));
        templateButton.setOnClickListener(v -> loadSelectedTemplate());
        runButton.setOnClickListener(v -> runPlanner());
        importButton.setOnClickListener(v -> importMap());
        reportButton.setOnClickListener(v -> exportReport());
        playButton.setOnClickListener(v -> togglePlayback());
        stepButton.setOnClickListener(v -> {
            stopPlayback();
            advancePlayback(1);
        });
        speedButton.setOnClickListener(v -> cycleSpeed());
        loadSelectedTemplate();
    }

    @Override
    @SuppressWarnings("deprecation")
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (resultCode != RESULT_OK || data == null || data.getData() == null) return;
        Uri uri = data.getData();
        if (requestCode == REQUEST_IMPORT_MAP) {
            handleImportedMap(uri);
        } else if (requestCode == REQUEST_EXPORT_REPORT) {
            writeReport(uri);
        }
    }

    @Override
    protected void onPause() {
        super.onPause();
        stopPlayback();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        solverExecutor.shutdownNow();
    }

    private Spinner spinner(String[] values) {
        Spinner spinner = new Spinner(this);
        spinner.setAdapter(new ArrayAdapter<>(this, android.R.layout.simple_spinner_dropdown_item, values));
        return spinner;
    }

    private void loadSelectedTemplate() {
        stopPlayback();
        currentResult = null;
        lastExceptionText = "";
        int level = selectedLevel();
        mapView.setMap(GridMap.template(level));
        resultText.setText("已载入 " + level + "，请横屏编辑/播放。");
    }

    private void runPlanner() {
        if (solving.getAndSet(true)) return;
        stopPlayback();
        runButton.setEnabled(false);
        runButton.setText("正在求解...");

        PerformanceLimits limits;
        int mode = limitSpinner.getSelectedItemPosition();
        if (mode == 0) {
            limits = PerformanceLimits.strictShortest();
        } else if (mode == 1) {
            limits = PerformanceLimits.stm32Relaxed();
        } else {
            limits = PerformanceLimits.stm32Strict();
        }
        final GridMap mapCopy = mapView.getMap().copy();
        final PerformanceLimits finalLimits = limits;

        solverExecutor.execute(() -> {
            PlannerResult result;
            String exceptionText = "";
            try {
                result = planner.solve(mapCopy, finalLimits);
            } catch (Throwable t) {
                result = new PlannerResult();
                result.solved = false;
                result.message = "求解异常: " + t.getClass().getSimpleName() + ": " + safeMessage(t);
                exceptionText = stackTraceToString(t);
            }
            final PlannerResult finalResult = result;
            final String finalExceptionText = exceptionText;
            runOnUiThread(() -> {
                currentResult = finalResult;
                lastExceptionText = finalExceptionText;
                mapView.setResult(finalResult);
                updateResultText();
                runButton.setEnabled(true);
                runButton.setText("手机本机跑图");
                solving.set(false);
                // Start playback when recognition succeeded, even if the
                // push search failed (timeout/limit). This lets the user see
                // the recognition animation and understand what happened.
                // However, skip auto-play for partial recognition only (push
                // truly unsolvable) to avoid misleading the user.
                if (finalResult.solved ||
                    (finalResult.recognitionCost > 0 && !finalResult.partialRecognitionOnly)) {
                    startPlayback();
                }
            });
        });
    }

    private void importMap() {
        stopPlayback();
        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("text/*");
        try {
            startActivityForResult(intent, REQUEST_IMPORT_MAP);
        } catch (ActivityNotFoundException ex) {
            Intent fallback = new Intent(Intent.ACTION_GET_CONTENT);
            fallback.addCategory(Intent.CATEGORY_OPENABLE);
            fallback.setType("text/*");
            startActivityForResult(Intent.createChooser(fallback, "选择地图文件"), REQUEST_IMPORT_MAP);
        }
    }

    private void handleImportedMap(Uri uri) {
        try {
            String text = readText(uri);
            MapTextCodec.DecodeResult decoded = MapTextCodec.decode(text, selectedLevel());
            if (decoded.levelId >= 101 && decoded.levelId <= 106) {
                levelSpinner.setSelection(decoded.levelId - 101);
            }
            stopPlayback();
            currentResult = null;
            lastExceptionText = "";
            mapView.setMap(decoded.map);
            GridMap.ValidationResult validation = decoded.map.copy().validate();
            StringBuilder sb = new StringBuilder();
            sb.append("导入地图成功：level=").append(decoded.levelId).append('\n');
            sb.append(validation.ok ? "地图校验通过" : "地图校验失败: " + validation.message);
            sb.append("\n可继续编辑，或直接点击“手机本机跑图”。");
            resultText.setText(sb.toString());
            showToast("地图导入成功");
        } catch (Exception ex) {
            lastExceptionText = stackTraceToString(ex);
            resultText.setText("导入地图失败: " + safeMessage(ex) + "\n可点击“导出报告”保存错误详情。");
            showToast("导入失败");
        }
    }

    private void exportReport() {
        pendingReportText = buildReportText("manual-export");
        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("text/plain");
        intent.putExtra(Intent.EXTRA_TITLE, "smart-car-error-report-" + timestampForFile() + ".txt");
        try {
            startActivityForResult(intent, REQUEST_EXPORT_REPORT);
        } catch (ActivityNotFoundException ex) {
            lastExceptionText = stackTraceToString(ex);
            resultText.setText("导出报告失败: 系统没有可用的文件保存器。\n" + safeMessage(ex));
            showToast("导出失败");
        }
    }

    private void writeReport(Uri uri) {
        try (OutputStream out = getContentResolver().openOutputStream(uri)) {
            if (out == null) throw new IOException("无法打开输出文件");
            out.write(pendingReportText.getBytes(StandardCharsets.UTF_8));
            out.flush();
            showToast("错误报告已导出");
            resultText.setText("错误报告已导出。\n\n" + resultText.getText());
        } catch (Exception ex) {
            lastExceptionText = stackTraceToString(ex);
            resultText.setText("导出报告失败: " + safeMessage(ex));
            showToast("导出失败");
        }
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
        if (result.partialRecognitionOnly) {
            sb.append("⚠️ 仅识别完成");
        } else {
            sb.append(result.solved ? "✅ OK" : "❌ FAILED");
        }
        sb.append("  frame=").append(step).append('/').append(mapView.getActionCount())
            .append("  speed=x").append(speedValues[speedIndex]).append('\n');
        if (result.partialRecognitionOnly) {
            sb.append("当前仅为识别路径，不是完整推箱方案\n");
        }
        sb.append(result.message).append('\n');
        sb.append("cost=").append(result.totalCost)
            .append(", scan=").append(result.recognitionCost)
            .append(", pushes=").append(result.pushes).append('\n');
        sb.append("expanded=").append(result.expanded)
            .append(", frontierMax=").append(result.maxFrontierSeen).append('\n');
        String diag = result.diagnosticsString();
        if (!diag.isEmpty()) {
            sb.append("diag: ").append(diag).append('\n');
        }
        if (!result.wallSeveranceWarnings.isEmpty()) {
            for (String w : result.wallSeveranceWarnings) {
                sb.append("⚠ ").append(w).append('\n');
            }
        }
        if (step > 0 && step <= result.actions.size()) {
            sb.append("currentAction=").append(result.actions.get(step - 1)).append('\n');
        }
        sb.append("actions=").append(result.actions).append('\n');
        sb.append("recognition=").append(result.recognitionOrder);
        resultText.setText(sb.toString());
    }

    private String buildReportText(String reason) {
        GridMap mapCopy = mapView.getMap().copy();
        GridMap.ValidationResult validation = mapCopy.validate();
        PlannerResult result = currentResult;

        StringBuilder sb = new StringBuilder();
        sb.append("Smart Car Planner Error Report\n");
        sb.append("generatedAt=").append(new SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.ROOT).format(new Date())).append('\n');
        sb.append("reason=").append(reason).append('\n');
        sb.append("appVersion=").append(appVersionString()).append('\n');
        sb.append("selectedLevel=").append(selectedLevel()).append('\n');
        sb.append("limitMode=").append(limitSpinner.getSelectedItem()).append('\n');
        sb.append("validation=").append(validation.ok ? "OK" : "FAILED").append('\n');
        if (!validation.ok) sb.append("validationMessage=").append(validation.message).append('\n');
        sb.append('\n');

        sb.append("[PlannerResult]\n");
        if (result == null) {
            sb.append("status=NOT_RUN\n");
        } else {
            sb.append("solved=").append(result.solved).append('\n');
            sb.append("message=").append(result.message).append('\n');
            sb.append("totalCost=").append(result.totalCost).append('\n');
            sb.append("recognitionCost=").append(result.recognitionCost).append('\n');
            sb.append("pushes=").append(result.pushes).append('\n');
            sb.append("expanded=").append(result.expanded).append('\n');
            sb.append("maxFrontierSeen=").append(result.maxFrontierSeen).append('\n');
            sb.append("recognitionSolved=").append(result.recognitionSolved).append('\n');
            sb.append("pushStageSolved=").append(result.pushStageSolved).append('\n');
            sb.append("partialRecognitionOnly=").append(result.partialRecognitionOnly).append('\n');
            sb.append("pushStageMessage=").append(result.pushStageMessage).append('\n');
            sb.append("diagnostics=").append(result.diagnosticsString()).append('\n');
            sb.append("actions=").append(result.actions).append('\n');
            sb.append("recognition=").append(result.recognitionOrder).append('\n');
            if (!result.wallSeveranceWarnings.isEmpty()) {
                sb.append("wallSeveranceWarnings=").append(result.wallSeveranceWarnings).append('\n');
            }
        }
        sb.append('\n');

        sb.append("[VisibleText]\n");
        sb.append(resultText == null ? "" : resultText.getText()).append('\n').append('\n');

        if (lastExceptionText != null && !lastExceptionText.isEmpty()) {
            sb.append("[Exception]\n");
            sb.append(lastExceptionText).append('\n');
        }

        sb.append("[Map]\n");
        sb.append(MapTextCodec.encode(mapCopy, selectedLevel(), "report-map"));
        return sb.toString();
    }

    private String readText(Uri uri) throws IOException {
        try (InputStream in = getContentResolver().openInputStream(uri)) {
            if (in == null) throw new IOException("无法打开输入文件");
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            int read;
            while ((read = in.read(chunk)) != -1) {
                buffer.write(chunk, 0, read);
            }
            return new String(buffer.toByteArray(), StandardCharsets.UTF_8);
        }
    }

    private int selectedLevel() {
        return 101 + levelSpinner.getSelectedItemPosition();
    }

    private String appVersionString() {
        try {
            android.content.pm.PackageInfo info = getPackageManager().getPackageInfo(getPackageName(), 0);
            return info.versionName + " (" + info.versionCode + ")";
        } catch (Exception ex) {
            return "unknown";
        }
    }

    private String timestampForFile() {
        return new SimpleDateFormat("yyyyMMdd-HHmmss", Locale.ROOT).format(new Date());
    }

    private static String safeMessage(Throwable t) {
        String msg = t.getMessage();
        return msg == null || msg.isEmpty() ? t.toString() : msg;
    }

    private static String stackTraceToString(Throwable t) {
        StringWriter sw = new StringWriter();
        t.printStackTrace(new PrintWriter(sw));
        return sw.toString();
    }

    private void showToast(String message) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show();
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
