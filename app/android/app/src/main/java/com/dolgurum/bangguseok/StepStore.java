package com.dolgurum.bangguseok;

import android.content.Context;
import android.content.SharedPreferences;
import java.util.Calendar;

/**
 * 하루 걸음 계산기.
 * 폰의 걸음 칩(TYPE_STEP_COUNTER)은 '폰을 켠 뒤 누적 걸음'만 알려 줌 → 날짜별로 기준점을 잡아 '오늘 걸음'으로 바꿈.
 *  - base  : 오늘 0시 무렵(또는 설치·재부팅 직후)의 누적값
 *  - carry : 오늘 재부팅 전에 이미 걸은 걸음
 *  - last  : 마지막으로 읽은 누적값 (15분마다 + 앱 열 때 갱신)
 * 날짜가 바뀐 뒤 처음 읽을 때, 마지막 읽기~0시 사이 걸음은 오늘로 들어감 (최대 15분치 오차).
 */
public class StepStore {
    private static final String P = "bgsj_steps";

    public static String dayKey() {   // 웹과 같은 형식: 2026-11-15 (0 채우지 않음)
        Calendar c = Calendar.getInstance();
        return c.get(Calendar.YEAR) + "-" + (c.get(Calendar.MONTH) + 1) + "-" + c.get(Calendar.DAY_OF_MONTH);
    }

    public static synchronized long update(Context ctx, long value) {
        SharedPreferences sp = ctx.getSharedPreferences(P, Context.MODE_PRIVATE);
        SharedPreferences.Editor ed = sp.edit();
        String today = dayKey();
        String day = sp.getString("day", null);
        long base = sp.getLong("base", value), carry = sp.getLong("carry", 0), last = sp.getLong("last", value);
        long lastT = sp.getLong("time", 0), now = System.currentTimeMillis();
        if (day == null) { day = today; base = value; carry = 0; last = value; }   // 처음 설치: 지금부터 셈
        boolean rebooted = value < last;
        if (rebooted) { carry += Math.max(0, last - base); base = 0; }
        if (!today.equals(day)) {   // 날이 바뀜: 어제 합계를 기록으로 남기고 새로 시작
            /* 11/23 보스 폰(아침 8시 삼성 187 · 앱 374): 밤에 폰이 잠들면 15분 읽기가 몇 시간씩 밀려,
               마지막 읽기 뒤 걸음(대부분 0시 전)이 다음 날 첫 읽기 때 '오늘'로 몰렸음.
               → 마지막 읽기가 30분 넘게 지났으면 그사이 걸음은 어제 것으로 봄 (밤 사이엔 거의 안 걷고, 23:45 알람이 마지막 읽기를 0시 가까이로 당김)
                 30분 안이면 예전처럼 마지막 읽기에서 끊음 */
            boolean longGap = lastT > 0 && now - lastT > 30L * 60 * 1000;
            long upTo = rebooted ? 0 : (longGap ? value : last);
            long yesterday = carry + Math.max(0, upTo - base);
            ed.putLong("hist_" + day, yesterday);
            base = upTo; carry = 0; day = today;
        }
        long steps = carry + Math.max(0, value - base);
        ed.putString("day", day).putLong("base", base).putLong("carry", carry).putLong("last", value)
          .putLong("today_" + today, steps).putLong("hist_" + today, steps).putLong("time", System.currentTimeMillis()).apply();
        return steps;
    }

    public static long hist(Context ctx, String day) {
        return ctx.getSharedPreferences(P, Context.MODE_PRIVATE).getLong("hist_" + day, -1);
    }
}
