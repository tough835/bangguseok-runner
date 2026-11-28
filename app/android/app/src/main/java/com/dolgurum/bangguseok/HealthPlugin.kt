package com.dolgurum.bangguseok

import android.content.Intent
import android.net.Uri
import androidx.activity.result.ActivityResult
import androidx.health.connect.client.HealthConnectClient
import androidx.health.connect.client.PermissionController
import androidx.health.connect.client.permission.HealthPermission
import androidx.health.connect.client.records.StepsRecord
import androidx.health.connect.client.request.AggregateGroupByPeriodRequest
import androidx.health.connect.client.request.ReadRecordsRequest
import java.time.ZoneId
import androidx.health.connect.client.time.TimeRangeFilter
import com.getcapacitor.JSArray
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
 *  steps()        → { ok, day, steps, history{ "2026-11-23": n, ... 7일 }, hours{ "2026-11-23": [0시..23시 걸음 24개], ... 오늘+7일 } }
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
                /* 11/24 보스 폰: 삼성 헬스 '걸음' 켰는데도 0 → 합계(aggregate)는 '데이터 우선순위' 목록에 든 앱만 셈.
                   그래서 걸음 기록을 직접 읽어 앱별로 더해 둠 → 합계가 0이면 삼성 헬스 것(없으면 가장 많은 앱) 사용 */
                val zone = ZoneId.systemDefault()
                val byDay = HashMap<LocalDate, HashMap<String, Long>>()
                val byHour = HashMap<LocalDate, HashMap<String, LongArray>>()   // 11/28 보스 '일 = 시간대 그래프': 날·앱별 0~23시 걸음 (기록 가운데 시각 기준)
                var recN = 0
                var token: String? = null
                do {
                    val res = client().readRecords(ReadRecordsRequest(StepsRecord::class, TimeRangeFilter.between(start, end), pageSize = 5000, pageToken = token))
                    for (rec in res.records) {
                        recN++
                        val d = rec.startTime.atZone(zone).toLocalDate()
                        val m = byDay.getOrPut(d) { HashMap() }
                        val o = rec.metadata.dataOrigin.packageName
                        m[o] = (m[o] ?: 0L) + rec.count
                        val mid = rec.startTime.plusMillis((rec.endTime.toEpochMilli() - rec.startTime.toEpochMilli()) / 2).atZone(zone)
                        val hm = byHour.getOrPut(mid.toLocalDate()) { HashMap() }
                        val arr = hm.getOrPut(o) { LongArray(24) }
                        arr[mid.hour] += rec.count
                    }
                    token = res.pageToken
                } while (token != null && recN < 60000)
                val agg = HashMap<LocalDate, Long>()
                for (g in rows) agg[g.startTime.toLocalDate()] = g.result[StepsRecord.COUNT_TOTAL] ?: 0L
                fun pick(d: LocalDate): Long {
                    val a = agg[d] ?: 0L
                    if (a > 0) return a
                    val m = byDay[d] ?: return 0L
                    return m["com.sec.android.app.shealth"] ?: (m.values.maxOrNull() ?: 0L)
                }
                val hist = JSObject()
                for (i in 1..7) { val d = today.minusDays(i.toLong()); hist.put(key(d), pick(d)) }
                val now = pick(today)
                /* 시간대: 하루 합계와 같은 앱(삼성 헬스 우선, 없으면 가장 많은 앱)의 시간별 걸음 → 하루 합계에 맞춰 비율로 맞춤 */
                val hours = JSObject()
                for (i in 0..7) {
                    val d = today.minusDays(i.toLong()); val hm = byHour[d] ?: continue
                    val arr = hm["com.sec.android.app.shealth"] ?: hm.values.maxByOrNull { it.sum() } ?: continue
                    val sum = arr.sum(); val tot = pick(d); if (sum <= 0L) continue
                    val ja = JSArray(); for (h in 0..23) ja.put(if (tot > 0) Math.round(arr[h].toDouble() * tot / sum) else arr[h])
                    hours.put(key(d), ja)
                }
                r.put("hours", hours)
                val dbg = JSObject()   // 실험실 화면용: 오늘 합계 · 기록 수 · 앱별 걸음
                dbg.put("agg", agg[today] ?: 0L); dbg.put("records", recN)
                val og = JSObject(); (byDay[today] ?: HashMap()).forEach { (k, v) -> og.put(k, v) }; dbg.put("origins", og)
                r.put("debug", dbg)
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
