package com.dolgurum.bangguseok;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;

/** 헬스 커넥트 권한 화면의 '이 앱이 데이터를 어떻게 쓰나' → 개인정보처리방침을 열고 바로 닫힘 (11/24) */
public class HealthRationale extends Activity {
    @Override
    protected void onCreate(Bundle b) {
        super.onCreate(b);
        try { startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse("https://tough835.github.io/bangguseok-runner/privacy.html"))); } catch (Exception ignored) {}
        finish();
    }
}
