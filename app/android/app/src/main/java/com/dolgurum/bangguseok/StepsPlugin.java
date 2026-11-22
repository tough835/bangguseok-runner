package com.dolgurum.bangguseok;

import android.Manifest;
import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.Build;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;
import java.util.Calendar;
import java.util.concurrent.TimeUnit;

/** 웹 화면에서 window.Capacitor.Plugins.Steps 로 부름 */
@CapacitorPlugin(name = "Steps", permissions = { @Permission(alias = "activity", strings = { Manifest.permission.ACTIVITY_RECOGNITION }) })
public class StepsPlugin extends Plugin {

    private boolean needsPerm() { return Build.VERSION.SDK_INT >= 29 && getPermissionState("activity") != PermissionState.GRANTED; }

    private void schedule() {
        PeriodicWorkRequest req = new PeriodicWorkRequest.Builder(StepWorker.class, 15, TimeUnit.MINUTES).build();
        WorkManager.getInstance(getContext()).enqueueUniquePeriodicWork("bgsj-steps", ExistingPeriodicWorkPolicy.KEEP, req);
        StepMidnight.schedule(getContext());   // 11/23: 매일 23:45 한 번 더 읽기
    }

    @PluginMethod
    public void start(PluginCall call) {   // 권한 묻기 + 15분 읽기 예약 + 오늘 걸음
        if (needsPerm()) { requestPermissionForAlias("activity", call, "afterPerm"); return; }
        schedule(); today(call);
    }

    @PermissionCallback
    private void afterPerm(PluginCall call) {
        if (needsPerm()) { JSObject r = new JSObject(); r.put("available", false); r.put("reason", "permission"); call.resolve(r); return; }
        schedule(); today(call);
    }

    /* 11/18: 운동 중 실시간 걸음 (삼성헬스처럼 폰을 몸에 지니고 러닝머신·계단) — 걸음마다 'step' 알림
       걸음 감지기(STEP_DETECTOR)가 있으면 한 걸음씩 바로, 없으면 걸음 칩(STEP_COUNTER) 값의 차이로 */
    private SensorManager liveSm; private SensorEventListener liveL; private long liveBase = -1;
    @PluginMethod
    public void liveStart(PluginCall call) {
        if (needsPerm()) { JSObject r = new JSObject(); r.put("ok", false); r.put("reason", "permission"); call.resolve(r); return; }
        liveStopInner();
        liveSm = (SensorManager) getContext().getSystemService(Context.SENSOR_SERVICE);
        Sensor det = liveSm == null ? null : liveSm.getDefaultSensor(Sensor.TYPE_STEP_DETECTOR);
        Sensor cnt = liveSm == null ? null : liveSm.getDefaultSensor(Sensor.TYPE_STEP_COUNTER);
        final boolean useDet = det != null;
        liveBase = -1;
        liveL = new SensorEventListener() {
            @Override public void onSensorChanged(SensorEvent e) {
                int n;
                if (useDet) n = Math.max(1, Math.round(e.values.length > 0 ? e.values[0] : 1));
                else { long v = (long) e.values[0]; if (liveBase < 0) { liveBase = v; return; } n = (int) (v - liveBase); liveBase = v; if (n <= 0) return; }
                JSObject d = new JSObject(); d.put("n", n); notifyListeners("step", d);
            }
            @Override public void onAccuracyChanged(Sensor sensor, int accuracy) {}
        };
        boolean ok = (useDet ? det : cnt) != null && liveSm.registerListener(liveL, useDet ? det : cnt, SensorManager.SENSOR_DELAY_FASTEST, 0);
        JSObject r = new JSObject(); r.put("ok", ok); r.put("type", useDet ? "detector" : "counter"); call.resolve(r);
    }
    private void liveStopInner() { try { if (liveSm != null && liveL != null) liveSm.unregisterListener(liveL); } catch (Exception ignored) {} liveL = null; }
    @PluginMethod
    public void liveStop(PluginCall call) { liveStopInner(); call.resolve(); }
    @Override
    protected void handleOnDestroy() { liveStopInner(); }

    @PluginMethod
    public void today(PluginCall call) {
        if (needsPerm()) { JSObject r = new JSObject(); r.put("available", false); r.put("reason", "permission"); call.resolve(r); return; }
        new Thread(() -> {
            long v = StepReader.readOnce(getContext(), 3000);
            JSObject r = new JSObject();
            if (v < 0) { r.put("available", false); r.put("reason", "sensor"); call.resolve(r); return; }
            r.put("available", true);
            r.put("day", StepStore.dayKey());
            r.put("steps", StepStore.update(getContext(), v));
            JSObject hist = new JSObject();   // 지난 7일 (앱을 며칠 안 열어도 채워 넣게)
            Calendar c = Calendar.getInstance();
            for (int i = 1; i <= 7; i++) {
                c.add(Calendar.DAY_OF_MONTH, -1);
                String k = c.get(Calendar.YEAR) + "-" + (c.get(Calendar.MONTH) + 1) + "-" + c.get(Calendar.DAY_OF_MONTH);
                long h = StepStore.hist(getContext(), k);
                if (h >= 0) hist.put(k, h);
            }
            r.put("history", hist);
            call.resolve(r);
        }).start();
    }
}
