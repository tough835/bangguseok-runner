package com.dolgurum.bangguseok;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import java.util.Calendar;

/**
 * 11/23: 매일 23:45 무렵 폰을 깨워 걸음 칩을 한 번 읽음 → 하루 경계를 0시 가까이에서 끊음.
 * (15분 읽기는 밤에 폰이 잠들면 몇 시간씩 밀림) · 정확한 시각 알람 권한이 필요 없는 '잠든 중에도 울리는' 알람 사용
 */
public class StepMidnight extends BroadcastReceiver {
    @Override public void onReceive(Context ctx, Intent intent) {
        final PendingResult pr = goAsync();
        final Context app = ctx.getApplicationContext();
        new Thread(() -> {
            try { long v = StepReader.readOnce(app, 8000); if (v >= 0) StepStore.update(app, v); }
            catch (Exception ignored) {}
            finally { schedule(app); pr.finish(); }
        }).start();
    }

    public static void schedule(Context ctx) {
        try {
            AlarmManager am = (AlarmManager) ctx.getSystemService(Context.ALARM_SERVICE);
            if (am == null) return;
            Calendar c = Calendar.getInstance();
            c.set(Calendar.HOUR_OF_DAY, 23); c.set(Calendar.MINUTE, 45); c.set(Calendar.SECOND, 0); c.set(Calendar.MILLISECOND, 0);
            if (c.getTimeInMillis() <= System.currentTimeMillis() + 60000) c.add(Calendar.DAY_OF_MONTH, 1);
            PendingIntent pi = PendingIntent.getBroadcast(ctx, 4523, new Intent(ctx, StepMidnight.class), PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
            am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, c.getTimeInMillis(), pi);
        } catch (Exception ignored) {}
    }
}
