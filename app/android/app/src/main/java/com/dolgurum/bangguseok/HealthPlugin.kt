package com.dolgurum.bangguseok

import android.content.Intent
import android.net.Uri
import androidx.activity.result.ActivityResult
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateGroupByPeriodRequest
import androidx.health.connect.client.time.TimeRangeFilter
import com.getcapacitor.JSObject
import com.getcapacitor.Plugin
import com.getcapacitor.PluginCall
import com.getcapacitor.PluginMethod
import com.getcapacitor.annotation.ActivityCallback
import com.getcapacitor.annotation.CapacitorPlugin
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import java.time.LocalDate
import java.time.Period

/**
 * 11/24 헬스 커넥트(Health Connect): 삼성 헬스가 센 걸음을 그대로 받아 옴 → 삼성 헬스 숫자와 같게.
 * 걸음 수 '읽기' 하나만 요청. 웹 화면에서 window.Capacitor.Plugins.Health 로 부름.
 *  status()       → { available, update, granted }
 *  request()      → 권한 화면 → { granted }
 *  steps()        → { ok, day, steps, history{ "2026-11-23": n, ... 7일 } }
 *  openSettings() → 헬스 커넥트 설정 화면
 */
@CapacitorPlugin(name = "Health")
class HealthPlugin : Plugin() {
    private val perms = setOf(HealthPermission.getReadPermission(StepsRecord::class))
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val hcPkg = "com.google.android.apps.healthdata"

    private fun sdk(): Int = try { HealthConnectClient.getSdkStatus(context, hcPkg) } catch (e: Exception) { HealthConnectClient.SDK_UNAVAILABLE }
    private fun client() = HealthConnectClient.getOrCreate(context, hcPkg)
    private suspend fun granted(): Boolean = try { client().permissionController.getGrantedPermissions().containsAll(perms) } catch (e: Exception) { false }
    private fun key(d: LocalDate) = "${d.year}-${d.monthValue}-${d.dayOfMonth}"   // 웹과 같은 형식 (0 채우지 않음)

    @PluginMethod
    fun status(call: PluginCall) {
        scope.launch {
            val s = sdk()
            val r = JSObject()
            r.put("available", s == HealthConnectClient.SDK_AVAILABLE)
            r.put("update", s == HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED)
            r.put("granted", s == HealthConnectClient.SDK_AVAILABLE && granted())
            call.resolve(r)
        }
    }

    @PluginMethod
    fun request(call: PluginCall) {
        val s = sdk()
        if (s == HealthConnectClient.SDK_UNAVAILABLE_PROVIDER_UPDATE_REQUIRED) {   // 헬스 커넥트 앱 설치·업데이트 필요 (안드로이드 13 이하)
            try {
                val i = Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=$hcPkg&url=healthconnect%3A%2F%2Fonboarding"))
                i.setPackage("com.android.vending"); i.putExtra("overlay", true); i.putExtra("callerId", context.packageName)
                activity.startActivity(i)
            } catch (e: Exception) {}
            val r = JSObject(); r.put("granted", false); r.put("reason", "update"); call.resolve(r); return
        }
        if (s != HealthConnectClient.SDK_AVAILABLE) { val r = JSObject(); r.put("granted", false); r.put("reason", "unavailable"); call.resolve(r); return }
        val intent = PermissionController.createRequestPermissionResultContract(hcPkg).createIntent(context, perms)
        startActivityForResult(call, intent, "afterRequest")
    }

    @ActivityCallback
    private fun afterRequest(call: PluginCall?, result: ActivityResult) {
        if (call == null) return
        scope.launch { val r = JSObject(); r.put("granted", granted()); call.resolve(r) }
    }

    @PluginMethod
    fun steps(call: PluginCall) {
        scope.launch {
            val r = JSObject()
            try {
                if (sdk() != HealthConnectClient.SDK_AVAILABLE || !granted()) { r.put("ok", false); r.put("reason", "permission"); call.resolve(r); return@launch }
                val today = LocalDate.now()
                val start = today.minusDays(7).atStartOfDay()
                val end = today.plusDays(1).atStartOfDay()
                val rows = client().aggregateGroupByPeriod(
                    AggregateGroupByPeriodRequest(setOf(StepsRecord.COUNT_TOTAL), TimeRangeFilter.between(start, end), Period.ofDays(1)))
                val hist = JSObject()
                var now = 0L
                for (g in rows) {
                    val d = g.startTime.toLocalDate()
                    val n = g.result[StepsRecord.COUNT_TOTAL] ?: 0L
                    if (d == today) now = n else hist.put(key(d), n)
                }
                r.put("ok", true); r.put("day", key(today)); r.put("steps", now); r.put("history", hist)
            } catch (e: Exception) {
                r.put("ok", false); r.put("reason", "error"); r.put("msg", e.javaClass.simpleName + ": " + (e.message ?: ""))
            }
            call.resolve(r)
        }
    }

    @PluginMethod
    fun openSettings(call: PluginCall) {
        try { activity.startActivity(Intent(HealthConnectClient.ACTION_HEALTH_CONNECT_SETTINGS)) } catch (e: Exception) {}
        call.resolve()
    }
}
