package com.dolgurum.bangguseok;

import android.app.backup.BackupManager;
import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.nio.charset.StandardCharsets;

/**
 * 11/23 기록 지키기: 웹 화면 기록(기록 옮기기 코드와 같은 내용)을 앱 파일(files/keep.txt)에 거울처럼 저장.
 * 안드로이드 자동 백업(구글 계정 백업, 하루 1번 충전·와이파이 중)이 이 파일을 올려 두었다가
 * 앱을 지우고 다시 깔거나 폰을 바꾸면 설치 때 되살려 줌 → 웹 화면이 처음 켜질 때 비어 있으면 이걸로 채움.
 * window.Capacitor.Plugins.Keep.set({ v }) / get() → { v }
 */
@CapacitorPlugin(name = "Keep")
public class KeepPlugin extends Plugin {
    private File f() { return new File(getContext().getFilesDir(), "keep.txt"); }

    @PluginMethod
    public void set(PluginCall call) {
        String v = call.getString("v", "");
        try {
            File tmp = new File(getContext().getFilesDir(), "keep.tmp");
            try (FileOutputStream o = new FileOutputStream(tmp)) { o.write(v.getBytes(StandardCharsets.UTF_8)); o.getFD().sync(); }
            if (!tmp.renameTo(f())) { f().delete(); tmp.renameTo(f()); }
            try { new BackupManager(getContext()).dataChanged(); } catch (Exception ignored) {}
            JSObject r = new JSObject(); r.put("n", v.length()); call.resolve(r);
        } catch (Exception e) { call.reject("keep set: " + e.getMessage()); }
    }

    @PluginMethod
    public void get(PluginCall call) {
        JSObject r = new JSObject();
        try {
            File k = f();
            if (k.exists()) {
                byte[] b = new byte[(int) k.length()];
                try (FileInputStream in = new FileInputStream(k)) { int off = 0, n; while (off < b.length && (n = in.read(b, off, b.length - off)) > 0) off += n; }
                r.put("v", new String(b, StandardCharsets.UTF_8));
            } else r.put("v", "");
            call.resolve(r);
        } catch (Exception e) { r.put("v", ""); call.resolve(r); }
    }
}
