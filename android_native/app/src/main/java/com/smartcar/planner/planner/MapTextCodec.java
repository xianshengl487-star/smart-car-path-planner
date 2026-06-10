package com.smartcar.planner.planner;

import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/** Text import/export for 16x12 planner maps. */
public final class MapTextCodec {
    private MapTextCodec() {
    }

    public static final class DecodeResult {
        public GridMap map;
        public int levelId;
    }

    public static String encode(GridMap map, int levelId, String title) {
        StringBuilder sb = new StringBuilder();
        sb.append("// SmartCarPlannerMap v1\n");
        if (title != null && !title.isEmpty()) {
            sb.append("// ").append(title.replace('\n', ' ')).append('\n');
        }
        sb.append("rows=").append(GridMap.ROWS)
            .append(" cols=").append(GridMap.COLS)
            .append(" level=").append(levelId)
            .append(" heading=").append(map.startHeading)
            .append(" recognition=").append(map.requiresRecognition)
            .append(" scanBombs=").append(map.scanBombs)
            .append(" allowBombPush=").append(map.allowBombPush)
            .append('\n');
        for (int r = 0; r < GridMap.ROWS; r++) {
            for (int c = 0; c < GridMap.COLS; c++) {
                if (c > 0) sb.append(' ');
                sb.append(tokenToText(map.token(r, c)));
            }
            sb.append('\n');
        }
        return sb.toString();
    }

    public static DecodeResult decode(String text, int fallbackLevelId) {
        if (text == null || text.trim().isEmpty()) {
            throw new IllegalArgumentException("地图文件为空");
        }

        int levelId = normalizeLevel(fallbackLevelId);
        Character heading = null;
        Boolean recognition = null;
        Boolean scanBombs = null;
        Boolean allowBombPush = null;
        List<char[]> rows = new ArrayList<>();

        String[] lines = text.replace("\r\n", "\n").replace('\r', '\n').split("\n");
        for (String raw : lines) {
            String line = raw.trim();
            if (line.isEmpty()) continue;
            if (line.startsWith("//")) continue;
            if (line.indexOf('=') >= 0 && !looksLikeMapRow(line)) {
                String[] parts = line.split("\\s+");
                for (String part : parts) {
                    int eq = part.indexOf('=');
                    if (eq <= 0 || eq >= part.length() - 1) continue;
                    String key = part.substring(0, eq).toLowerCase(Locale.ROOT);
                    String value = part.substring(eq + 1);
                    if ("level".equals(key)) {
                        levelId = normalizeLevel(parseInt(value, "level"));
                    } else if ("heading".equals(key)) {
                        heading = parseHeading(value);
                    } else if ("recognition".equals(key)) {
                        recognition = parseBoolean(value, key);
                    } else if ("scanbombs".equals(key)) {
                        scanBombs = parseBoolean(value, key);
                    } else if ("allowbombpush".equals(key)) {
                        allowBombPush = parseBoolean(value, key);
                    }
                }
                continue;
            }
            rows.add(parseMapRow(line, rows.size()));
        }

        if (rows.size() != GridMap.ROWS) {
            throw new IllegalArgumentException("地图行数必须是 " + GridMap.ROWS + "，实际是 " + rows.size());
        }

        GridMap map = new GridMap();
        for (int r = 0; r < GridMap.ROWS; r++) {
            char[] row = rows.get(r);
            if (row.length != GridMap.COLS) {
                throw new IllegalArgumentException("第 " + (r + 1) + " 行列数必须是 "
                    + GridMap.COLS + "，实际是 " + row.length);
            }
            for (int c = 0; c < GridMap.COLS; c++) {
                map.setToken(r, c, row[c]);
            }
        }
        applyLevelFlags(map, levelId);
        if (heading != null) map.startHeading = heading.charValue();
        if (recognition != null) map.requiresRecognition = recognition.booleanValue();
        if (scanBombs != null) map.scanBombs = scanBombs.booleanValue();
        if (allowBombPush != null) map.allowBombPush = allowBombPush.booleanValue();
        map.rebuildObjects();

        DecodeResult result = new DecodeResult();
        result.map = map;
        result.levelId = levelId;
        return result;
    }

    public static void applyLevelFlags(GridMap map, int levelId) {
        map.requiresRecognition = levelId == 102 || levelId == 103;
        map.scanBombs = false;
        map.allowBombPush = levelId == 103;
    }

    private static char[] parseMapRow(String line, int zeroBasedRow) {
        if (line.indexOf(' ') >= 0 || line.indexOf('\t') >= 0) {
            String[] tokens = line.split("\\s+");
            if (tokens.length != GridMap.COLS) {
                throw new IllegalArgumentException("第 " + (zeroBasedRow + 1) + " 行列数必须是 "
                    + GridMap.COLS + "，实际是 " + tokens.length);
            }
            char[] row = new char[GridMap.COLS];
            for (int i = 0; i < tokens.length; i++) {
                row[i] = textToToken(tokens[i], zeroBasedRow, i);
            }
            return row;
        }
        if (line.length() != GridMap.COLS) {
            throw new IllegalArgumentException("第 " + (zeroBasedRow + 1) + " 行列数必须是 "
                + GridMap.COLS + "，实际是 " + line.length());
        }
        char[] row = new char[GridMap.COLS];
        for (int i = 0; i < GridMap.COLS; i++) {
            row[i] = compactCharToToken(line.charAt(i), zeroBasedRow, i);
        }
        return row;
    }

    private static boolean looksLikeMapRow(String line) {
        String compact = line.replace(" ", "").replace("\t", "");
        if (compact.length() != GridMap.COLS) return false;
        for (int i = 0; i < compact.length(); i++) {
            char ch = compact.charAt(i);
            if (".#PEX1234abcd".indexOf(ch) < 0) return false;
        }
        return true;
    }

    private static char compactCharToToken(char ch, int row, int col) {
        if (".#PEX1234abcd".indexOf(ch) >= 0) return ch;
        throw new IllegalArgumentException("非法地图字符 '" + ch + "' at row="
            + (row + 1) + ", col=" + (col + 1));
    }

    private static char textToToken(String value, int row, int col) {
        String token = value.trim();
        if (token.length() == 1) {
            return compactCharToToken(token.charAt(0), row, col);
        }
        String upper = token.toUpperCase(Locale.ROOT);
        if (upper.length() == 2 && upper.charAt(0) == 'B') {
            int id = parseId(upper.charAt(1), token, row, col);
            return (char) ('0' + id);
        }
        if (upper.length() == 2 && upper.charAt(0) == 'T') {
            int id = parseId(upper.charAt(1), token, row, col);
            return (char) ('a' + id - 1);
        }
        throw new IllegalArgumentException("非法地图 token '" + token + "' at row="
            + (row + 1) + ", col=" + (col + 1));
    }

    private static int parseId(char ch, String token, int row, int col) {
        if (ch >= '1' && ch <= '4') return ch - '0';
        throw new IllegalArgumentException("编号只支持 1..4，非法 token '" + token + "' at row="
            + (row + 1) + ", col=" + (col + 1));
    }

    private static String tokenToText(char token) {
        if (token >= '1' && token <= '4') return "B" + token;
        if (token >= 'a' && token <= 'd') return "T" + (token - 'a' + 1);
        return Character.toString(token);
    }

    private static int normalizeLevel(int levelId) {
        if (levelId >= 101 && levelId <= 103) return levelId;
        if (levelId >= 1 && levelId <= 3) return 100 + levelId;
        return 101;
    }

    private static int parseInt(String value, String key) {
        try {
            return Integer.parseInt(value.trim());
        } catch (NumberFormatException ex) {
            throw new IllegalArgumentException(key + " 不是有效数字: " + value);
        }
    }

    private static Character parseHeading(String value) {
        if (value == null || value.isEmpty()) {
            throw new IllegalArgumentException("heading 不能为空");
        }
        char h = Character.toUpperCase(value.charAt(0));
        if (h == 'U' || h == 'D' || h == 'L' || h == 'R') return Character.valueOf(h);
        throw new IllegalArgumentException("heading 只能是 U/D/L/R");
    }

    private static Boolean parseBoolean(String value, String key) {
        String v = value.toLowerCase(Locale.ROOT);
        if ("true".equals(v) || "1".equals(v) || "yes".equals(v)) return Boolean.TRUE;
        if ("false".equals(v) || "0".equals(v) || "no".equals(v)) return Boolean.FALSE;
        throw new IllegalArgumentException(key + " 只能是 true/false");
    }
}
