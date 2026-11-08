# 当前脚本来自于 http://script.345yun.cn 脚本库下载！
# 当前脚本来自于 http://2.345yun.cn 脚本库下载！
# 当前脚本来自于 http://2.345yun.cc 脚本库下载！
# 脚本库官方QQ群1群: 429274456
# 脚本库官方QQ群2群: 1077801222
# 脚本库官方QQ群3群: 433030897
# 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
# 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
# 您在使用脚本库下载的脚本时自行检查判断风险。
# 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快音全自动一体化脚本
签名: s = keyname|HMAC-SHA256(secret, 排序参数串) (apple/grape/mango 三key随机)
配置: KY_AUTH=device_id#refresh_token (90天有效), 

★ 2026-10-08 修订
  1. 翻倍任务完整化：double_loop 遍历所有业务场景 + double_after 在原奖励后即时触发
  2. 新增大转盘全流程：big_turntable 抽光次数 + _try_turntable_stages 领多阶段累计
  3. auto_prereq 移除转盘（转盘走独立流程）
  4. TASK_TYPES 补全转盘多阶段
  5. run_all 中 double_loop 前置/循环复查；big_turntable 独立调用
"""
import os, sys, json, time, base64, ssl, gzip, hashlib, hmac as _hmac
import urllib.request, urllib.parse

API = "https://api.kaixinyf.cn"
H5 = "https://h5.kaixinyf.cn"
SA = "https://sa.kaixinyf.cn"
GAME = "https://game.kaixinyf.cn"
SIGN_KEYS = {"apple": "apple-is-foolish", "grape": "vitisvinieral0o0", "mango": "yellowfruit-+*o0"}
INTERVAL = int(os.getenv("KY_INTERVAL", "15"))
DOUBLE_MAX = int(os.getenv("KY_DOUBLE_MAX", "10"))
LISTEN_INTERVAL = int(os.getenv("KY_LISTEN_INTERVAL", "36"))
LISTEN_MAX = int(os.getenv("KY_LISTEN_MAX", "120"))
LOOPS = int(os.getenv("KY_LOOPS", "8"))

def log(m): print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)

def _split_env(v):
    out = []
    for p in v.replace("\n", "&").split("&"):
        p = p.strip()
        if p.startswith("KY_AUTH="): p = p[8:].strip()
        if p: out.append(p)
    return out

def collect_accounts():
    accs, seen = [], set()
    for p in _split_env(os.getenv("KY_AUTH", "")):
        if p not in seen: seen.add(p); accs.append(p)
    for name in sorted(os.environ.keys()):
        if name.startswith("KY_AUTH") and name != "KY_AUTH":
            for p in _split_env(os.environ[name]):
                if p not in seen: seen.add(p); accs.append(p)
    return accs

class Ky:
    def __init__(self, auth):
        parts = auth.split("#")
        self.device_id = parts[0].strip()
        self.refresh_token = parts[1].strip() if len(parts) > 1 else ""
        self.app_v = self.client_v = "5.84.00"
        self.access = ""
        self.ctx = ssl.create_default_context()
        self.ua = f"kuaiyin/{self.client_v} (OPPO/PJH110; android/14) okVersion/okhttp/3.14.9"

    def _signed(self, extra=None, keyname="grape"):
        p = {"access_token": self.access, "utm-source": "oppo", "app_v": self.app_v,
             "device_id": self.device_id, "client_v": self.client_v,
             "proj": "kuaiyin_h5", "platform": "Android", "request_source": "app"}
        if extra: p.update(extra)
        p["t"] = str(int(time.time() * 1000))
        h = []
        for k in sorted(p.keys()): h.append(k + "=" + str(p[k]))
        joined = "&".join(h)
        sig = _hmac.new(SIGN_KEYS[keyname].encode(), joined.encode(), hashlib.sha256).hexdigest().upper()
        p["s"] = keyname + "|" + sig
        return p

    def _req(self, url, body, headers, retries=2):
        for i in range(retries + 1):
            try:
                req = urllib.request.Request(url, data=body, headers=headers, method="POST")
                resp = urllib.request.urlopen(req, timeout=25, context=self.ctx)
                raw = resp.read()
                try: raw = gzip.decompress(raw)
                except Exception: pass
                return json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                if i < retries: time.sleep(2)
        return {"code": "-1", "message": "请求失败"}

    def _hdrs(self):
        return {
            "content-type": "application/x-www-form-urlencoded", "platform": "Android",
            "client-v": self.client_v, "app-v": self.app_v, "utm-source": "oppo",
            "ky-union-id": "ky3295e0d12a504c25988a0371da4027cb",
            "platform-v": "14", "platform-brand": "OPPO", "platform-model": "PJH110",
            "network-type": "wifi", "device-id": self.device_id,
            "oaid": "652F00B4240F4D01B7B688F355D82541bc2d6e8bd5e5fcd4e96c5fac56f60edf",
            "access-token": self.access, "app-name": "kuaiyin", "is-teenager": "0",
            "currentplaystatus": "0", "user-agent": self.ua,
        }

    def login(self):
        if not self.refresh_token:
            log("! 缺少 refresh_token"); return False
        base = {"refresh_token": self.refresh_token, "device_id": self.device_id,
                "platform": "Android", "client_v": self.client_v, "app_v": self.app_v,
                "utm-source": "oppo", "request_source": "app", "proj": "kuaiyin_h5"}
        hdrs = {k: v for k, v in self._hdrs().items() if k != "access-token"}
        for kn in SIGN_KEYS:
            p = dict(base)
            p["t"] = str(int(time.time() * 1000))
            h = []
            for k in sorted(p.keys()): h.append(k + "=" + str(p[k]))
            sig = _hmac.new(SIGN_KEYS[kn].encode(), "&".join(h).encode(), hashlib.sha256).hexdigest().upper()
            p["s"] = kn + "|" + sig
            r = self._req(API + "/passport/get_token", urllib.parse.urlencode(p).encode(), hdrs)
            if r.get("code") == "0" and r.get("data", {}).get("access_token"):
                self.access = r["data"]["access_token"]
                log(f"✅ 登录成功（refresh_token 刷新）"); return True
            time.sleep(1)
        log("⚠️ 登录失败: refresh_token 可能过期"); return False

    def call(self, path, extra=None, plain=False):
        p = {"access_token": self.access, "utm-source": "oppo", "app_v": self.app_v,
             "device_id": self.device_id, "client_v": self.client_v,
             "proj": "kuaiyin_h5", "platform": "Android", "request_source": "app"}
        if extra: p.update(extra)
        params = p if plain else self._signed(extra)
        body = urllib.parse.urlencode(params).encode()
        return self._req(H5 + path, body, self._hdrs())

    def _signed_sa(self, extra):
        p = {"platform": "Android", "client_v": self.client_v, "app_v": self.app_v}
        if extra: p.update(extra)
        p["t"] = str(int(time.time() * 1000))
        h = []
        for k in sorted(p.keys()): h.append(k + "=" + str(p[k]))
        joined = "&".join(h)
        kn = list(SIGN_KEYS)[int(time.time()) % 3]
        sig = _hmac.new(SIGN_KEYS[kn].encode(), joined.encode(), hashlib.sha256).hexdigest().upper()
        p["s"] = kn + "|" + sig
        return p

    def call_sa(self, path, extra):
        params = self._signed_sa(extra)
        body = urllib.parse.urlencode(params).encode()
        return self._req(API + path, body, self._hdrs())

    def call_game(self, path, extra=None):
        params = self._signed(extra)
        body = urllib.parse.urlencode(params).encode()
        return self._req(H5 + path, body, self._hdrs())

    # ============ 听歌时长自动上报 ============
    def send_coin(self, level):
        r = self.call_sa("/VideoMusic/SendCoin", {
            "mode": "music", "level": str(level),
            "used_fast_time": "0", "is_exposure": "true"
        })
        if r.get("code") == "0":
            d = r.get("data") or {}
            next_lv = d.get("level", level + 1)
            coin = d.get("coin", 0)
            piggy = (d.get("piggy") or {}).get("coin", 0)
            log(f"🎵 听歌上报 level={level}→{next_lv} +{coin}金币 存钱罐={piggy}")
            return True, next_lv, coin
        else:
            msg = r.get("message", "")
            log(f"⚠️ SendCoin level={level}: {msg}")
            return False, level, 0

    def claim_listen_reward(self, reward_id, task_type="listen_music_reward_5"):
        """getListenMusicReward 领取听歌奖励 (game域) ★ 已插入 double_after"""
        r = self.call_game("/api/welfare/getListenMusicReward", {
            "id": str(reward_id), "task_type": task_type
        })
        if r.get("code") == "0":
            d = r.get("data") or {}
            amt = d.get("reward_amount", 0)
            log(f"✅ 听歌奖励 id={reward_id} [{task_type}] +{amt}金币")
            # ★ 新增：原奖励后立即触发翻倍（时效窗口内）
            if amt:
                time.sleep(0.3)
                self.double_after("listen_music_time_reward", amt)
            return amt
        return 0

    def report_listen_time(self, listen_sec, active_sec, page="task"):
        r = self.call_game("/api/window/windows", {
            "page": page, "listen_time": str(listen_sec), "active_time": str(active_sec)
        })
        return r.get("code") == "0"

    def get_one_task(self, task_type):
        r = self.call("/api/welfare/GetOneTask", {"taskType": task_type})
        if r.get("code") == "0":
            return r.get("data") or {}
        return {}

    def get_dots(self):
        r = self.call("/api/welfare/getDot")
        d = r.get("data") or {}
        parts = []
        for k in ["task", "welfare", "fission"]:
            v = d.get(k) or {}
            parts.append(f"{k}={v.get('num')}")
        log(f"🔴 红点: {' '.join(parts)}")
        return d

    def get_welfare_dot(self, page="red_package"):
        r = self.call_game("/api/welfare/GetWelfareDot", {"page": page})
        if r.get("code") == "0":
            dot = (r.get("data") or {}).get("dot", 0)
            if dot: log(f"🔴 福利页[{page}] 有{dot}个红点待领")
            return dot
        return 0

    def share_info(self):
        r = self.call("/api/invite/get_share_info")
        if r.get("code") == "0":
            d = r.get("data") or {}
            invite_code = d.get("invite_code") or d.get("code", "")
            if invite_code:
                log(f"🔗 我的邀请码: {invite_code}")
            return d
        return {}

    def ad_interstitial(self):
        r = self.call("/api/task/getAdInterstitialInfo", {"interstitial_interface": "", "platform": "Android"})
        d = (r.get("data") or {}).get("interstitial_info") or {}
        return d

    def listen_music_auto(self):
        log(f"🎧 === 听歌时长自动上报开始 (最多{LISTEN_MAX}首, 间隔{LISTEN_INTERVAL}秒) ===")
        total_coin = 0
        level = 1
        reward_id = 1
        send_count = 0
        listen_sec = 0
        active_sec = 0

        prog = self.get_one_task("continuous_listen_music_10")
        if prog: log(f"  连续听歌任务进度: {prog.get('task_value')}/{prog.get('target_value')} status={prog.get('progress_status')}")

        for tid in range(1, 6):
            for tt in ["listen_music_reward_5", "listen_music_reward_4"]:
                amt = self.claim_listen_reward(tid, tt)
                if amt > 0:
                    total_coin += amt
                time.sleep(1)

        for i in range(LISTEN_MAX):
            ok, next_lv, coin = self.send_coin(level)
            if not ok:
                if next_lv != level:
                    level = next_lv
                    ok, next_lv, coin = self.send_coin(level)
                if not ok:
                    log(f"🛑 听歌上报终止: 服务端拒绝 (可能已达每日上限)")
                    break
            total_coin += coin
            level = next_lv
            send_count += 1
            listen_sec += LISTEN_INTERVAL
            active_sec += LISTEN_INTERVAL

            if send_count % 3 == 0:
                self.report_listen_time(listen_sec, active_sec)

            if send_count % 2 == 0:
                for tt in ["listen_music_reward_5", "listen_music_reward_4"]:
                    amt = self.claim_listen_reward(reward_id, tt)
                    if amt > 0:
                        total_coin += amt
                        reward_id += 1
                    time.sleep(1)

            if send_count % 5 == 0:
                for tt in ["listen_to_songs_1","listen_to_songs_3","listen_to_songs_5",
                           "listen_to_songs_10","listen_to_songs_15","listen_to_songs_20",
                           "listen_to_songs_25","listen_to_songs_30","listen_music_time_v2"]:
                    r = self.call("/api/welfare/GetReward", {"taskType": tt, "page": "global_red_package"})
                    if r.get("code") == "0":
                        amt = (r.get("data") or {}).get("reward_amount", 0)
                        if amt: total_coin += amt; log(f"✅ 听歌阶段[{tt}] +{amt}金币")
                    time.sleep(1)

            if i < LISTEN_MAX - 1:
                time.sleep(LISTEN_INTERVAL)

        for tid in range(1, reward_id + 3):
            for tt in ["listen_music_reward_5", "listen_music_reward_4"]:
                amt = self.claim_listen_reward(tid, tt)
                if amt > 0: total_coin += amt
                time.sleep(1)
        for tt in ["listen_to_songs_1","listen_to_songs_3","listen_to_songs_5","listen_to_songs_7",
                    "listen_to_songs_10","listen_to_songs_15","listen_to_songs_20","listen_to_songs_25",
                    "listen_to_songs_30","listen_to_songs_40","listen_to_songs_50","listen_to_songs_60",
                    "listen_to_songs_80","listen_to_songs_four","listen_to_songs_five","listen_to_songs_six",
                    "listen_music_time_v2","listen_music_open_red_envelope1"]:
            r = self.call("/api/welfare/GetReward", {"taskType": tt, "page": "global_red_package"})
            if r.get("code") == "0":
                amt = (r.get("data") or {}).get("reward_amount", 0)
                if amt: total_coin += amt; log(f"✅ 听歌终扫[{tt}] +{amt}金币")
            time.sleep(1)
        r = self.call("/api/Welfare/GetRedPackageAccumulativeList")
        info = (r.get("data") or {}).get("listen_music_time_reward_info") or {}
        for rp in (info.get("red_packet_list") or []):
            rid = rp.get("rid")
            if rid and rp.get("status") == 2:
                rr = self.call("/api/welfare/listenOpenRedPacketReward", {"id": str(rid)})
                if rr.get("code") == "0":
                    amt = (rr.get("data") or {}).get("coin", 0)
                    if amt: total_coin += amt; log(f"✅ 听歌红包#{rid} +{amt}金币")
                time.sleep(1)
        r = self.call("/api/FreeListenV2/GetInfo")
        if r.get("code") == "0":
            d = r.get("data") or {}
            for item in (d.get("reward_list") or [])[:3]:
                tid = item.get("task_id")
                if tid:
                    rr = self.call("/api/FreeListenV2/GetReward", {"task_id": str(tid)})
                    if rr.get("code") == "0":
                        amt = (rr.get("data") or {}).get("coin", 0)
                        if amt: total_coin += amt; log(f"✅ 免费听#{tid} +{amt}金币")
                    time.sleep(1)
        log(f"🎧 === 听歌完成: 共{send_count}首 +{total_coin}金币 ===")
        return total_coin

    def sign_all(self):
        for name, path, extra in [
            ("每日签到", "/api/SignIn/WelfareSignIn", None),
            ("打卡签到", "/api/task/clock_sign_in", None),
            ("全球红包签到", "/api/signIn/GlobalRedpackageSignGetReward", None),
        ]:
            r = self.call(path, extra)
            if r.get("code") == "0":
                d = r.get("data") or {}
                amt = d.get("today_reward", d.get("reward_amount", d.get("is_success", "")))
                log(f"✅ {name} +{amt}金币" if (d.get("today_is_sign_in") or d.get("is_success")) else f"ℹ️ {name} 今日已签")
                # ★ 新增：签到后尝试翻倍
                if isinstance(amt, (int, float)) and amt > 0:
                    time.sleep(0.3)
                    self.double_after("WelfareSignIn", amt)
            else:
                log(f"⚠️ {name}: {r.get('message')}")
            time.sleep(INTERVAL)

    def clock_loop(self):
        log("⏰ 打卡循环领取（最多30次）")
        total = 0
        claimed = 0
        for i in range(30):
            r = self.call("/api/task/GetClockSignIn")
            if r.get("code") != "0":
                log(f"ℹ️ 打卡状态查询失败: {r.get('message')}")
                break
            d = r.get("data") or {}
            if not d.get("enable_sign_in"):
                log(f"ℹ️ 打卡已不可领 (本次循环+{total}金币)")
                break
            rr = self.call("/api/task/clock_sign_in")
            if rr.get("code") == "0":
                dd = rr.get("data") or {}
                amt = dd.get("reward_amount", 0)
                if amt:
                    total += amt; claimed += 1
                    log(f"✅ 打卡#{i+1} +{amt}金币 (剩余{dd.get('remaining_reward_times')}次)")
                    # ★ 新增：打卡后翻倍
                    time.sleep(0.3)
                    self.double_after("clock_sign_in", amt)
                cd = dd.get("count_down", 0)
                if cd > 0:
                    if cd > 60:
                        log(f"⏳ 下次打卡需等{cd}秒，本次循环结束")
                        break
                    log(f"⏳ 等{cd}秒再领...")
                    time.sleep(min(cd, 30))
            else:
                log(f"ℹ️ 打卡#{i+1}: {rr.get('message')}")
                break
            time.sleep(1)
        if claimed:
            log(f"⏰ 打卡循环合计 +{total}金币 ({claimed}次)")
        return total

    def envelopes(self):
        """拆红包（普通+大额）★ 已插入 double_after"""
        total = 0
        r = self.call("/api/OpenEnvelopesDay/EnvelopesDetail")
        envs = r.get("data", {}).get("open_envelopes") or [] if r.get("code") == "0" else []
        for e in envs:
            if e.get("status") == 0:
                if e.get("type") == "large":
                    rr = self.call("/api/OpenEnvelopesDay/EnvelopesBigOpen", {"envelopes_num": e["id"], "position": ""})
                else:
                    rr = self.call("/api/OpenEnvelopesDay/EnvelopesNormalOpen", {"envelopes_num": e["id"], "app_name": "kuaiyin"})
                if rr.get("code") == "0":
                    c = rr.get("data", {}).get("coin", 0); total += c
                    log(f"✅ 拆红包#{e['id']} +{c}金币")
                    # ★ 新增：拆完立即触发翻倍
                    if c > 0:
                        time.sleep(0.3)
                        total += self.double_after("openEnvelopesDay", c)
                time.sleep(INTERVAL)
        log(f"📦 红包合计 +{total}金币")

    def timing_redpack(self):
        """定时红包轮询开包 ★ 已插入 double_after"""
        total = 0
        claimed = 0
        for rd in range(LOOPS):
            r = self.call("/api/task/get_timing_red_packs")
            d = r.get("data") if r.get("code") == "0" else []
            if not isinstance(d, list):
                break
            now = int(time.time())
            any_opened = False
            for t in d[:10]:
                tid = t.get("task_id")
                if not tid:
                    continue
                next_t = t.get("next_time", 0)
                if next_t and next_t > now:
                    continue
                rr = self.call("/api/task/open_timing_red_pack", {"task_id": str(tid)})
                if rr.get("code") == "0":
                    c = rr.get("data", {}).get("coin", 0)
                    if c:
                        total += c; claimed += 1; any_opened = True
                        log(f"✅ 定时红包#{tid} +{c}金币")
                        # ★ 新增：开包后立即触发翻倍
                        time.sleep(0.3)
                        total += self.double_after("redPackage", c)
                time.sleep(2)
            if not any_opened:
                waits = [t.get('next_time', 0) - now for t in d if t.get('next_time', 0) > now]
                nearest = min(waits) if waits else 30
                if nearest > 60:
                    log(f"📬 定时红包最近可开还需{nearest}s, 本轮结束")
                    break
                log(f"📬 定时红包等待{nearest}s再开...")
                time.sleep(min(nearest, 30))
        if claimed:
            log(f"📬 定时红包合计 +{total}金币 ({claimed}次)")
        return total

    def bubble(self):
        total = 0
        for tid in ["1", "2"]:
            r = self.call("/api/welfare/getBubbleTaskReward", {"task_id": tid})
            if r.get("code") == "0":
                c = (r.get("data") or {}).get("coin", 0); total += c
                log(f"✅ 气泡任务#{tid} +{c}金币")
            else:
                log(f"ℹ️ 气泡#{tid}: {r.get('message')}")
            time.sleep(INTERVAL)
        r2 = self.call("/api/Welfare/GetRedPackageAccumulativeList")
        piggy = (r2.get("data") or {}).get("piggy") or {}
        bts = piggy.get("task_list", {}).get("bubble_task") or []
        for bt in bts:
            if bt.get("task_type") == "free":
                tid = bt.get("task_id")
                if tid:
                    rr = self.call("/api/welfare/getBubbleTaskReward", {"task_id": str(tid)})
                    if rr.get("code") == "0":
                        c = (rr.get("data") or {}).get("coin", 0); total += c
                        log(f"✅ 存钱罐气泡#{tid} +{c}金币 (free+{bt.get('reward_coin')})")
                    else:
                        log(f"ℹ️ 存钱罐气泡#{tid}: {rr.get('message')}")
                    time.sleep(INTERVAL)
        log(f"🫧 气泡合计 +{total}金币")

    def rewards(self):
        tts = ["store_praise", "redpack_video", "reward_module_double", "dining_4",
               "listen_music_reward_5", "continuous_listen_music_10", "open_envelopes_day_6",
               "new_user_coin", "sign_in_app_1", "dp_ad_view2", "ad_video_big_1",
               "big_turntable_4", "sleep_red_package_2", "task_fission_1", "new_user_gift"]
        total = 0
        for tt in tts:
            r = self.call("/api/task/receive_reward", {"task_type": tt})
            if r.get("code") == "0":
                c = (r.get("data") or {}).get("coin", 0)
                if c > 0: total += c; log(f"✅ 任务[{tt}] +{c}金币")
            time.sleep(1)
        log(f"💰 任务发奖合计 +{total}金币")

    def online_reward(self):
        total = 0
        r = self.call("/api/Task/GetOnlineRewardList")
        d = r.get("data") or {}
        rpl = d.get("red_packet_list") or []
        if not rpl:
            log("ℹ️ 无在线奖励可领")
            return 0
        for rp in rpl:
            rid = rp.get("id") or rp.get("rid")
            if rid:
                rr = self.call("/api/Task/ReceiveOnlineReward", {"rid": str(rid)})
                if rr.get("code") == "0":
                    c = (rr.get("data") or {}).get("coin", 0)
                    if c:
                        total += c; log(f"✅ 在线奖励#{rid} +{c}金币")
                else:
                    msg = rr.get("message") or ""
                    if msg and "未" not in msg and "不存在" not in msg and "无" not in msg:
                        log(f"ℹ️ 在线#{rid}: {msg[:40]}")
                time.sleep(INTERVAL)
        if total:
            log(f"📡 在线奖励合计 +{total}金币")
        return total

    def listen_rewards(self):
        r = self.call("/api/Welfare/GetRedPackageAccumulativeList")
        d = r.get("data") or {}
        info = d.get("listen_music_time_reward_info") or {}
        for rp in (info.get("red_packet_list") or []):
            rid = rp.get("rid")
            if rid and rp.get("status") == 2:
                rr = self.call("/api/welfare/listenOpenRedPacketReward", {"id": str(rid)})
                if rr.get("code") == "0":
                    c = (rr.get("data") or {}).get("coin", 0)
                    if c: log(f"✅ 听歌红包#{rid} +{c}金币")
                time.sleep(INTERVAL)
        log("🎵 听歌红包检查完成")

    def piggy_bank(self):
        r = self.call("/api/Welfare/RewardPiggyBank")
        d = r.get("data") or {}
        log(f"🐷 存钱罐: 已存{d.get('coin')}金币 (上限{d.get('coin_limit') or d.get('amount')})")
        r2 = self.call("/api/Welfare/GetRedPackageAccumulativeList")
        piggy = (r2.get("data") or {}).get("piggy") or {}
        log(f"🐷 累积缓存: {piggy.get('coin')}/{piggy.get('coin_limit')}")
        tl = piggy.get("task_list") or {}
        tct = tl.get("tomorrow_coin_task")
        if tct and tct.get("task_id"):
            rr = self.call("/api/Welfare/RewardRedPackageAccumulative", {"id": str(tct["task_id"])})
            if rr.get("code") == "0":
                cc = (rr.get("data") or {}).get("coin", 0)
                if cc: log(f"✅ 明日存钱罐 +{cc}金币")
            time.sleep(INTERVAL)
        for bt in (tl.get("bubble_task") or []):
            if bt.get("task_type") == "free":
                rr = self.call("/api/Welfare/RewardRedPackageAccumulative", {"id": str(bt.get("task_id"))})
                if rr.get("code") == "0":
                    cc = (rr.get("data") or {}).get("coin", 0)
                    if cc: log(f"✅ 累积气泡 +{cc}金币")
                time.sleep(INTERVAL)

    def welfare_tasks(self):
        r = self.call("/api/welfare/myWelfareNew", {"push_permission": "1"})
        if r.get("code") != "0": return
        d = r.get("data") or {}
        ui = d.get("userInfo") or {}
        log(f"👤 金币={ui.get('coin')} 余额={ui.get('balance')}元")
        for item in d.get("content") or []:
            for tl in item.get("task_list") or []:
                for t in tl.get("task_list") or []:
                    tt = t.get("task_type")
                    if tt:
                        rr = self.call("/api/task/receive_reward", {"task_type": tt})
                        c = (rr.get("data") or {}).get("coin", 0) if rr.get("code") == "0" else 0
                        if c > 0: log(f"✅ 动态任务[{tt}] +{c}金币")
                        time.sleep(1)

    def auto_prereq(self):
        """前置条件自动完成引擎 ★ 已移除 big_turntable_4（转盘走独立流程）"""
        log("🔧 前置条件自动完成引擎")
        r = self.call("/api/welfare/GetRedPackageAndNewTask")
        unfinished = []
        if r.get("code") == "0":
            rpt = (r.get("data") or {}).get("red_package_task") or {}
            for t in (rpt.get("dailyTask") or []):
                tt = t.get("task_type")
                if tt and t.get("progress_status") == 0:
                    unfinished.append(tt)
        log(f"  未完成任务 {len(unfinished)} 个")
        listen_tts = [t for t in unfinished if t.startswith("listen_to_songs") or t.startswith("listen_music_reward")]
        if listen_tts:
            log(f"🎵 听歌类前置: {len(listen_tts)}个任务需听歌时长, 自动上报推进")
            n = 0
            level = 1
            for i in range(10):
                ok, next_lv, coin = self.send_coin(level)
                if ok:
                    level = next_lv; n += 1
                else:
                    break
                time.sleep(1)
            log(f"🎵 前置听歌上报完成 ({n}首)")
            for tt in listen_tts:
                page = "global_red_package" if tt.startswith("listen_to_songs") else "my_welfare"
                rr = self.call("/api/welfare/GetReward", {"taskType": tt, "page": page})
                if rr.get("code") == "0":
                    amt = (rr.get("data") or {}).get("reward_amount", 0)
                    if amt: log(f"✅ 前置完成[{tt}] +{amt}金币")
                time.sleep(1)
        # ★ 修改：移除 big_turntable_4
        prog_tts = [t for t in unfinished if t in ("dining_4", "sleep_red_package_2")]
        if prog_tts:
            log(f"📈 进度类前置: {prog_tts} 上报进度")
            for tt in prog_tts:
                rr = self.call("/api/welfare/TaskProgress", {"taskType": tt})
                if rr.get("code") == "0":
                    log(f"✅ 进度上报[{tt}] 完成")
                time.sleep(1)
                rr2 = self.call("/api/welfare/GetReward", {"taskType": tt, "page": "my_welfare"})
                if rr2.get("code") == "0":
                    amt = (rr2.get("data") or {}).get("reward_amount", 0)
                    if amt: log(f"✅ 进度任务[{tt}] +{amt}金币")
                time.sleep(1)
        ad_tts = [t for t in unfinished if t in ("dp_ad_view2", "ad_video_big_1", "chest_ad_video_1", "huiyuan_1", "huiyuan_2")]
        if ad_tts:
            log(f"📢 广告类前置: {ad_tts} 需真实广告凭证, 试领跳过")
            for tt in ad_tts:
                rr = self.call("/api/welfare/GetReward", {"taskType": tt, "page": "my_welfare"})
                if rr.get("code") == "0":
                    amt = (rr.get("data") or {}).get("reward_amount", 0)
                    if amt: log(f"✅ 广告任务[{tt}] +{amt}金币")
                time.sleep(1)
        log("🔧 前置条件引擎完成")

    # ================================================================
    #  ★ 翻倍任务完整版（替换原 double_loop）
    # ================================================================
    def double_loop(self):
        """翻倍任务完整流程：遍历所有业务 → 拿配置 → 上报曝光 → 领取翻倍"""
        log("🎬 翻倍任务完整流程（遍历业务场景）")
        total = 0

        BUSINESS = [
            ("openEnvelopesDay",     "拆红包",     "6.0"),
            ("redPackage",           "红包",       "6.0"),
            ("piggy_bank",           "存钱罐",     "6.0"),
            ("listen_music_time_reward", "听歌红包", "6.0"),
            ("WelfareSignIn",        "福利签到",   "100.0"),
            ("clock_sign_in",        "打卡签到",   "61.0"),
            ("SignIn",               "签到",       "50.0"),
            ("BigTurntable",         "大转盘",     "100.0"),
            ("Dining",               "外卖",       "200.0"),
            ("reward_module",        "通用任务",   "6.0"),
        ]

        for bn, name, rn in BUSINESS:
            r = self.call("/api/common/getRewardModule", {
                "type": "customize", "rewardType": "coin",
                "businessName": bn, "rewardNum": rn,
                "beforeRewardNum": rn, "ecpm_code": ""
            })
            if r.get("code") != "0":
                continue
            d = r.get("data") or {}
            vm = d.get("videoModel") or {}
            if not vm:
                continue

            leave = d.get("videoLeaveCount", 0)
            video_reward = vm.get("videoReward", 0)
            if leave <= 0 or video_reward <= 0:
                log(f"  ℹ️ [{name}] 翻倍剩{leave}次 奖励{video_reward} → 无可翻")
                continue

            try:
                pe = json.loads(vm.get("param_ext") or "{}")
            except Exception:
                pe = {}
            dbl_tt = pe.get("task_type", "") or pe.get("taskType", "")
            log(f"  🎬 [{name}] 翻倍奖励={video_reward} 剩{leave}次 "
                f"task_type={dbl_tt or '-'} param_ext={str(vm.get('param_ext',''))[:60]}")

            for imp_bn in ["myWelfareSignInPageVideo", bn, "myWelfareVideo",
                           "doubleRewardVideo", "globalPageVideo"]:
                self.call("/api/ad/impress_for_video", {"business_name": imp_bn})
                time.sleep(0.3)

            claim_attempts = []
            if dbl_tt:
                claim_attempts += [
                    ("GetAdVideoBigReward", "/api/welfare/GetAdVideoBigReward",
                     {"task_type": dbl_tt}),
                    ("GetDpReward", "/api/Ad/GetDpReward",
                     {"re": "1", "task_type": dbl_tt, "code": ""}),
                    ("GetReward(翻倍)", "/api/welfare/GetReward",
                     {"taskType": dbl_tt, "page": "global_red_package"}),
                ]
            claim_attempts += [
                ("GetRedPackageDoubleReward", "/api/Welfare/GetRedPackageDoubleReward",
                 {"business_name": bn}),
                ("DoubleReward", "/api/welfare/DoubleReward",
                 {"task_type": dbl_tt, "business_name": bn}),
                ("getRewardVideoReward", "/api/common/getRewardVideoReward",
                 {"businessName": bn, "rewardNum": rn}),
                ("GetDpAdViewReward", "/api/Welfare/GetDpAdViewReward",
                 {"ecpm_code": ""}),
            ]

            got = 0
            for cname, cpath, cextra in claim_attempts:
                rr = self.call(cpath, cextra)
                if rr.get("code") == "0":
                    dd = rr.get("data") or {}
                    amt = (dd.get("coin") or dd.get("reward_coin")
                           or dd.get("reward_amount") or video_reward)
                    if amt:
                        total += amt; got = amt
                        log(f"    ✅ [{name}] 翻倍成功 via {cname} +{amt}金币")
                        break
                else:
                    msg = rr.get("message") or ""
                    if msg and not any(k in msg for k in ("未","不存在","无","凭证","完成")):
                        log(f"    ℹ️ [{name}] {cname}: {msg[:40]}")
                time.sleep(0.5)
            if not got:
                log(f"    ℹ️ [{name}] 未拿到翻倍（多半需真实广告凭证）")
            time.sleep(1)

        if total:
            log(f"🎬 翻倍任务合计 +{total}金币")
        else:
            log("🎬 翻倍任务无收益（需真实广告凭证时正常）")
        return total

    def double_after(self, business_name, reward_num):
        """原奖励后立即触发翻倍检查（时效窗口内）"""
        try:
            r = self.call("/api/common/getRewardModule", {
                "type": "customize", "rewardType": "coin",
                "businessName": business_name,
                "rewardNum": str(float(reward_num)),
                "beforeRewardNum": str(float(reward_num)),
                "ecpm_code": ""
            })
        except Exception:
            return 0
        if r.get("code") != "0":
            return 0
        d = r.get("data") or {}
        vm = d.get("videoModel") or {}
        if not vm or d.get("videoLeaveCount", 0) <= 0:
            return 0
        try:
            pe = json.loads(vm.get("param_ext") or "{}")
        except Exception:
            pe = {}
        dbl_tt = pe.get("task_type", "")
        video_reward = vm.get("videoReward", 0)

        self.call("/api/ad/impress_for_video",
                  {"business_name": "myWelfareSignInPageVideo"})
        for cname, cpath, cextra in [
            ("GetAdVideoBigReward", "/api/welfare/GetAdVideoBigReward",
             {"task_type": dbl_tt}),
            ("GetDpReward", "/api/Ad/GetDpReward",
             {"re": "1", "task_type": dbl_tt, "code": ""}),
            ("GetReward", "/api/welfare/GetReward",
             {"taskType": dbl_tt, "page": "global_red_package"}),
        ]:
            if not dbl_tt and cname != "GetReward":
                continue
            rr = self.call(cpath, cextra)
            if rr.get("code") == "0":
                amt = (rr.get("data") or {}).get("coin", video_reward)
                if amt:
                    log(f"    🎬 翻倍[{business_name}] +{amt}金币 via {cname}")
                    return amt
            time.sleep(0.4)
        return 0

    # ================================================================
    #  ★ 新增大转盘全流程
    # ================================================================
    def _try_turntable_stages(self):
        """尝试领取所有 big_turntable_N 阶段奖励，返回金币"""
        got = 0
        stages = [f"big_turntable_{n}" for n in
                  (1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20, 30, 50)]
        for tt in stages:
            try:
                r = self.call("/api/welfare/GetReward",
                              {"taskType": tt, "page": "my_welfare"})
            except Exception:
                continue
            if r.get("code") == "0":
                amt = (r.get("data") or {}).get("reward_amount", 0)
                if amt:
                    got += int(amt)
                    log(f"  ✅ 转盘累计[{tt}] +{amt}金币")
            time.sleep(0.4)
        return got

    def big_turntable(self):
        """大转盘全流程：查信息 → 抽光所有次数 → 领多阶段累计奖励"""
        log("🎰 大转盘任务（抽满）")
        total = 0
        draw_count = 0
        info = {}

        info_paths = [
            ("/api/BigTurntable/GetInfo", None),
            ("/api/BigTurntable/GetTaskInfo", None),
            ("/api/BigTurntable/GetBigTurntableInfo", None),
            ("/api/activity/get_big_turntable_info", None),
            ("/api/task/GetBigTurntableInfo", None),
            ("/api/welfare/GetBigTurntableInfo", None),
            ("/api/activity/getBigTurntableInfo", {"page": "big_turntable"}),
            ("/api/Task/GetBigTurntable", None),
            ("/api/lottery/get_info", {"type": "big_turntable"}),
            ("/api/activity/get_lottery_info", {"type": "big_turntable"}),
        ]
        for path, extra in info_paths:
            try:
                r = self.call(path, extra)
            except Exception:
                continue
            if r.get("code") == "0" and r.get("data"):
                info = r.get("data") or {}
                log(f"  🎰 转盘信息 via {path}")
                log(f"     {json.dumps(info, ensure_ascii=False)[:300]}")
                break
            time.sleep(0.4)

        free_times = 0
        ad_times = 0
        for k in ("free_times", "free_count", "remain_free_times",
                  "free_draw_times", "draw_times", "remain_times", "count"):
            if info.get(k) is not None:
                try: free_times = int(info[k])
                except Exception: pass
                break
        for k in ("ad_times", "video_times", "ad_count",
                  "remain_ad_times", "video_draw_times"):
            if info.get(k) is not None:
                try: ad_times = int(info[k])
                except Exception: pass
                break
        if not free_times and isinstance(info.get("task_list"), list):
            for t in info["task_list"]:
                tt = t.get("task_type", "")
                if tt.startswith("big_turntable"):
                    free_times += int(t.get("reward_times") or t.get("times") or 1)
        log(f"  🎰 免费{free_times}次 + 广告{ad_times}次")

        max_draws = min(max(free_times + ad_times + 5, 8), 40)
        draw_paths = [
            ("/api/BigTurntable/Draw", None),
            ("/api/BigTurntable/Lottery", None),
            ("/api/BigTurntable/StartDraw", None),
            ("/api/BigTurntable/Receive", None),
            ("/api/activity/big_turntable_draw", None),
            ("/api/activity/big_turntable_lottery", None),
            ("/api/task/BigTurntableDraw", None),
            ("/api/Task/BigTurntableDraw", None),
            ("/api/task/big_turntable_draw", None),
            ("/api/lottery/draw", {"type": "big_turntable"}),
            ("/api/activity/draw", {"activity_type": "big_turntable"}),
        ]
        for i in range(max_draws):
            got = False
            exhausted = False
            for path, extra in draw_paths:
                try:
                    r = self.call(path, extra)
                except Exception:
                    continue
                if r.get("code") == "0":
                    d = r.get("data") or {}
                    amt = (d.get("coin") or d.get("reward_coin")
                           or d.get("reward_amount") or d.get("rewardCoin") or 0)
                    prize = (d.get("prize_name") or d.get("prize")
                             or d.get("name") or d.get("text") or "?")
                    total += int(amt or 0)
                    draw_count += 1
                    log(f"  🎰 第{draw_count}抽: {prize} +{amt}金币 "
                        f"(via {path.split('/')[-1]})")
                    got = True
                    self._try_turntable_stages()
                    break
                else:
                    msg = r.get("message") or ""
                    if any(k in msg for k in ["次数", "用完", "不足", "没", "无"]):
                        exhausted = True
                        break
                time.sleep(0.3)
            if exhausted:
                log(f"  ℹ️ 抽奖次数用尽（已抽 {draw_count} 次）")
                break
            if not got and i < 3:
                log("  ℹ️ 未找到可用的抽奖接口，终止")
                break
            time.sleep(1)

        total += self._try_turntable_stages()

        log(f"🎰 大转盘合计 +{total}金币（{draw_count} 次抽奖）")
        return total

    def ad_reward_claim(self):
        log("🎬 广告翻倍奖励模拟领取（尝试,需真实广告凭证）")
        cfg = None
        for bn in ["redPackage", "openEnvelopesDay", "piggy_bank", "listen_music_time_reward"]:
            r = self.call("/api/common/getRewardModule", {
                "type": "customize", "rewardType": "coin", "businessName": bn,
                "rewardNum": "6.0", "beforeRewardNum": "6.0", "ecpm_code": ""})
            if r.get("code") == "0":
                d = r.get("data") or {}
                if d.get("videoModel"):
                    cfg = d
                    break
            time.sleep(1)
        if not cfg:
            log("ℹ️ 无可翻倍奖励配置，跳过广告模块")
            return 0
        vm = cfg.get("videoModel") or {}
        task_type = ""
        try:
            pe = json.loads(vm.get("param_ext") or "{}")
            task_type = pe.get("task_type", "") or ""
        except Exception:
            task_type = ""
        video_reward = vm.get("videoReward", 0)
        leave = cfg.get("videoLeaveCount", 0)
        log(f"🎬 探测到翻倍配置: task_type={task_type} 翻倍奖励={video_reward} 剩余次数={leave}")

        r = self.call("/api/ad/impress_for_video", {"business_name": "myWelfareSignInPageVideo"})
        if r.get("code") == "0":
            d = r.get("data") or {}
            log(f"📢 广告位加载: ad_reward={d.get('ad_reward')}")
        time.sleep(1)

        attempts = []
        if task_type:
            attempts.append(("GetAdVideoBigReward(看视频赚金币)", "/api/welfare/GetAdVideoBigReward",
                             {"task_type": task_type}))
            attempts.append(("GetDpReward(广告奖励)", "/api/Ad/GetDpReward",
                             {"re": "1", "task_type": task_type, "code": ""}))
        attempts.append(("GetDpAdViewReward(广告跳转奖励)", "/api/Welfare/GetDpAdViewReward",
                         {"ecpm_code": ""}))
        attempts.append(("GetInsertScreenAdReward(插屏奖励)", "/api/Ad/GetInsertScreenAdReward", {}))
        attempts.append(("GetInformationFlowAdReward(信息流)", "/api/common/GetInformationFlowAdReward",
                         {"task_id": ""}))
        attempts.append(("GetRenderingTaskReward(渲染任务)", "/api/Welfare/GetRenderingTaskReward", {}))
        attempts.append(("GetJiZhunReward(基准奖励)", "/api/welfare/GetJiZhunReward", {"show_num": "1"}))
        attempts.append(("getScreenOffResPositionReward(息屏奖励)", "/api/task/getScreenOffResPositionReward", {"source": "1"}))
        attempts.append(("PushFeed/GetReward(推送奖励)", "/api/PushFeed/GetReward", {"page": "welfare", "is_first": "1"}))
        got = 0
        for name, path, extra in attempts:
            try:
                r = self.call(path, extra)
            except Exception as ex:
                log(f"⚠️ {name}: 请求异常 {ex}")
                continue
            code = r.get("code")
            if code == "0":
                d = r.get("data") or {}
                amt = d.get("coin") or d.get("reward_coin") or d.get("reward_amount") or 0
                got += amt or 0
                log(f"✅ {name}: +{amt}金币")
            else:
                m = r.get("message") or ""
                log(f"ℹ️ {name}: 需真实广告凭证(code={code}{' '+m[:20] if m else ''})，跳过")
        if got == 0:
            log("🎬 广告翻倍奖励需真实观看广告(ecpm_code服务端交叉校验)，已自动跳过")
        return got

    def countdown_reward(self):
        total = 0
        claimed = 0
        for rid in range(1, 100):
            r = self.call("/api/CountdownReward/ReceiveReward", {"rid": str(rid)})
            if r.get("code") == "0":
                c = (r.get("data") or {}).get("reward_coin", 0)
                if c:
                    total += c; claimed += 1
                    log(f"✅ 倒计时#{rid} +{c}金币")
            else:
                if claimed == 0:
                    log(f"ℹ️ 倒计时不可领({(r.get('message') or '')[:30]}), 跳过")
                break
            time.sleep(2)
        for rd in range(LOOPS - 1):
            r = self.call("/api/Welfare/GetRedPackageAccumulativeList")
            info = (r.get("data") or {}).get("listen_music_time_reward_info") or {}
            rpl = info.get("red_packet_list") or []
            got_any = False
            for rp in rpl:
                rid = rp.get("rid")
                if rid and rp.get("status") == 2 and not rp.get("complete"):
                    rr = self.call("/api/welfare/listenOpenRedPacketReward", {"id": str(rid)})
                    if rr.get("code") == "0":
                        c = (rr.get("data") or {}).get("coin", 0)
                        if c:
                            total += c; claimed += 1; got_any = True
                            log(f"✅ 听歌红包#{rid} +{c}金币 (轮询{rd+2})")
                    time.sleep(2)
            if not got_any:
                time.sleep(5)
        if claimed:
            log(f"⏳ 倒计时+红包轮询合计 +{total}金币 ({claimed}次)")
        return total

    def welfare_sign_extra(self):
        log("📅 福利签到增强")
        total = 0
        r = self.call("/api/welfare/GetWelfarePageInfo", {"page": "welfare"})
        if r.get("code") == "0":
            si = (r.get("data") or {}).get("sign_info") or {}
            log(f"📅 今日可签+{si.get('today_reward')} 累计{si.get('reward_count')} 今日已签={si.get('today')}")
        for name, path, extra in [
            ("新手窗口签到", "/api/NewUserGuide/GetSignInWindowReward", None),
            ("新手视频签到", "/api/NewUserGuide/GetSignInVideoReward", None),
        ]:
            rr = self.call(path, extra)
            if rr.get("code") == "0":
                dd = rr.get("data") or {}
                amt = dd.get("reward_amount") or dd.get("coin") or dd.get("reward_coin") or 0
                if amt:
                    total += amt; log(f"✅ {name} +{amt}金币")
            else:
                msg = rr.get("message") or ""
                if msg and "未" not in msg and "不存在" not in msg:
                    log(f"ℹ️ {name}: {msg[:50]}")
            time.sleep(INTERVAL)
        rr = self.call("/api/welfare/SignInRegress")
        if rr.get("code") == "0":
            dd = rr.get("data") or {}
            amt = dd.get("reward_amount") or dd.get("coin") or 0
            if amt:
                total += amt; log(f"✅ 回归签到 +{amt}金币")
        time.sleep(INTERVAL)
        rr = self.call("/api/SignIn/MusicPageSign", {"day": "1"})
        if rr.get("code") == "0":
            dd = rr.get("data") or {}
            amt = dd.get("reward_amount") or dd.get("coin") or dd.get("reward_coin") or 0
            if amt:
                total += amt; log(f"✅ 音乐页签到 +{amt}金币")
        time.sleep(INTERVAL)
        rr = self.call("/api/task/incrClockSignInVideoTimes")
        if rr.get("code") == "0":
            log("✅ 打卡视频次数+1")
        time.sleep(INTERVAL)
        rr = self.call("/api/Task/MarkViewMusicDetailPage")
        if rr.get("code") == "0":
            log("✅ 听歌页标记完成")
        if total:
            log(f"📅 签到增强合计 +{total}金币")
        return total

    def news_chest(self):
        log("📰 锁屏新闻宝箱")
        total = 0
        r = self.call("/api/ViewNews/GetLockScreenNewsChestList/Info")
        if r.get("code") == "0":
            d = r.get("data") or {}
            items = d if isinstance(d, list) else (d.get("chest_list") or d.get("list") or [])
            for c in items:
                cid = c.get("chest_id") or c.get("id")
                if cid and c.get("status") in (None, 1):
                    rr = self.call("/api/ViewNews/ReceiveLockScreenChestReward", {"chest_id": str(cid)})
                    if rr.get("code") == "0":
                        amt = (rr.get("data") or {}).get("coin", 0)
                        if amt:
                            total += amt; log(f"✅ 新闻宝箱#{cid} +{amt}金币")
                    time.sleep(INTERVAL)
        else:
            log(f"ℹ️ 新闻宝箱: {r.get('message') or '无数据'}")
        if total:
            log(f"📰 新闻宝箱合计 +{total}金币")
        return total

    # ---------- 全任务领取 ----------
    # ★ 修改：TASK_TYPES 补全转盘多阶段
    TASK_TYPES = [
        # 听歌系列
        "listen_to_songs_1","listen_to_songs_3","listen_to_songs_5","listen_to_songs_7",
        "listen_to_songs_10","listen_to_songs_15","listen_to_songs_20","listen_to_songs_25",
        "listen_to_songs_30","listen_to_songs_40","listen_to_songs_50","listen_to_songs_60",
        "listen_to_songs_80","listen_to_songs_five","listen_to_songs_four","listen_to_songs_six",
        "listen_music_reward_4","listen_music_reward_5","listen_music_time_v2","listen_music_open_red_envelope1",
        # 红包系列
        "open_envelopes_day","open_envelopes_day_2","open_envelopes_day_3","open_envelopes_day_6",
        # 登录/签到系列
        "continue_log_in_2","continue_log_in_3","continue_log_in_5","sign_in_app_1","sign_in_app",
        "global_redpackage_sign_in","wechat_clock_quanju","new_user_continuous_sign_in_3","click_to_finish",
        "invite_friend_quanju","publish_task","new_user_coin",
        # 生活任务
        "dining_4","sleep_red_package_2","task_fission_1",
        "long_time_fission",
        # ★ 转盘系列（补全）
        "big_turntable_1","big_turntable_2","big_turntable_3","big_turntable_4",
        "big_turntable_5","big_turntable_6","big_turntable_8","big_turntable_10",
        "big_turntable_12","big_turntable_15","big_turntable_20","big_turntable_30",
        "big_turntable_50",
        # 裂变/锁屏/其他
        "background_popup","show_lock_screen","show_lock_screen_other",
        "chest_ad_video_1","chest_jump_open","AI_","activity_AND_1",
        # 广告任务
        "ad_video_big_1","dp_ad_view2","huiyuan_1","huiyuan_2",
    ]

    def all_tasks(self):
        log("📋 开始全任务领取")
        total = 0
        r = self.call("/api/welfare/GetRedPackageAndNewTask")
        dyn_types = []
        if r.get("code") == "0":
            d = r.get("data") or {}
            rpt = d.get("red_package_task") or {}
            for grp in [rpt.get("dailyTask"), rpt.get("task_list")]:
                if isinstance(grp, list):
                    for t in grp:
                        tt = t.get("task_type")
                        if tt and tt not in dyn_types:
                            dyn_types.append(tt)
            log(f"  动态任务树 {len(dyn_types)} 个")
        r2 = self.call("/api/welfare/GetWelfarePageTask", {"page": "welfare"})
        if r2.get("code") == "0":
            d2 = r2.get("data") or {}
            for grp in (d2.get("task_list") or d2.get("daily_task") or []):
                if isinstance(grp, list):
                    for t in grp:
                        tt = t.get("task_type")
                        if tt and tt not in dyn_types:
                            dyn_types.append(tt)
            if isinstance(d2, list):
                def walk(o):
                    if isinstance(o, dict):
                        tt = o.get("task_type")
                        if tt and tt not in dyn_types:
                            dyn_types.append(tt)
                        for v in o.values():
                            walk(v)
                    elif isinstance(o, list):
                        for v in o:
                            walk(v)
                walk(d2)
        r3 = self.call("/api/welfare/myWelfareNew", {"push_permission": "1"})
        if r3.get("code") == "0":
            for item in ((r3.get("data") or {}).get("content") or []):
                for tl in (item.get("task_list") or []):
                    for t in (tl.get("task_list") or []):
                        tt = t.get("task_type")
                        if tt and tt not in dyn_types:
                            dyn_types.append(tt)
        log(f"  动态任务树 {len(dyn_types)} 个(含福利页/每日任务)")
        all_tt = dyn_types + [t for t in self.TASK_TYPES if t not in dyn_types]
        for tt in all_tt:
            page = "global_red_package" if tt.startswith(("listen_to_songs", "continue_log_in", "global_redpackage", "wechat_clock")) else "my_welfare"
            r = self.call("/api/welfare/GetReward", {"taskType": tt, "page": page})
            if r.get("code") == "0":
                d = r.get("data") or {}
                amt = d.get("reward_amount", 0)
                total += amt or 0
                if amt:
                    log(f"✅ [{tt}] +{amt}金币")
            time.sleep(2)
        log(f"💰 全任务合计 +{total}金币")
        return total

    def chest_task(self):
        r = self.call("/api/welfare/GetChestTask")
        if r.get("code") == "0":
            d = r.get("data") or {}
            chest = d.get("chest") or {}
            log(f"🎁 宝箱: {chest.get('text')} status={chest.get('status')}")
            if chest.get("status") == 1:
                rr = self.call("/api/welfare/GetReward", {"taskType": "chest_jump_open", "page": "my_welfare"})
                log(f"  开宝箱: {rr.get('message') or rr.get('code')}")

    def regress_task(self):
        r = self.call("/api/welfare/getRegressTask")
        if r.get("code") == "0":
            d = r.get("data") or {}
            for t in (d.get("regress_task_list") or [])[:5]:
                tt = t.get("task_type")
                if tt:
                    rr = self.call("/api/welfare/GetReward", {"taskType": tt, "page": "my_welfare"})
                    if rr.get("code") == "0":
                        amt = (rr.get("data") or {}).get("reward_amount", 0)
                        log(f"✅ 回归[{tt}] +{amt}金币")
                    time.sleep(2)

    def sleep_task(self):
        base = {"access_token": self.access, "utm-source": "oppo", "app_v": self.app_v,
                "client_v": self.client_v, "device_id": self.device_id,
                "platform": "Android", "platform_brand": "OPPO", "platform_model": "PJH110",
                "proj": "kuaiyin_h5", "request_source": "h5",
                "tourist_token": "", "t": str(int(time.time()))}
        h = []
        for k in sorted(base.keys()): h.append(k + "=" + str(base[k]))
        joined = "&".join(h)
        kn = "grape"
        sig = _hmac.new(SIGN_KEYS[kn].encode(), joined.encode(), hashlib.sha256).hexdigest().upper()
        base["s"] = kn + "|" + sig
        body = urllib.parse.urlencode(base).encode()
        r = self._req(GAME + "/api_game/sleep_game/get_task_info", body, self._hdrs())
        if r.get("code") == "0":
            d = r.get("data") or {}
            log(f"😴 睡觉任务: status={d.get('status')} 可看广告+{d.get('watch_ad_reward')}金币 上限{d.get('reward_coins_max')}")
            if d.get("watch_ad_times") is not None and d.get("watch_ad_times") < 3:
                log(f"  还可看{d.get('watch_ad_reward')}金币广告 {d.get('watch_ad_times')}/3次")
        else:
            log(f"⚠️ 睡觉任务: {r.get('message')}")

    def sign_list(self):
        r = self.call("/api/task/get_sign_in_list", {"page": "1"})
        log(f"📅 签到列表: {json.dumps(r.get('data'), ensure_ascii=False)[:200]}")

    def music_list(self):
        r = self.call("/api/activity/get_music_list")
        rows = (r.get("data") or {}).get("rows") or [] if r.get("code") == "0" else []
        log(f"🎵 听歌任务 {len(rows)}个")

    def reward_record(self):
        r = self.call("/api/earnInterest/get_reward_record_v2")
        log(f"💰 收益: {json.dumps(r.get('data'), ensure_ascii=False)[:200]}")

    def ad_info(self):
        r = self.call("/api/ad/impress_for_video", {"business_name": "myWelfareSignInPageVideo"})
        d = r.get("data") or {}
        log(f"📢 广告配置: 奖励={d.get('ad_reward')}金币")

    def wallet(self):
        r = self.call("/api/me/wallet")
        d = (r.get("data") or {}).get("profile") or {}
        log(f"👛 钱包: 余额{d.get('balance_total')}元 可提{d.get('balance_available')}元")

    def fission(self):
        r = self.call("/api/Fission/get_fission_page_info")
        log(f"🔗 裂变页: {json.dumps(r.get('data'), ensure_ascii=False)[:200]}")

    def lock_screen(self):
        r = self.call("/api/LockScreen/GetTaskList")
        if r.get("code") == "0":
            lst = (r.get("data") or {}).get("list") or []
            log(f"🔒 锁屏任务 {len(lst)}个")
            for t in lst[:5]:
                tt = t.get("task_type")
                amt = t.get("coin_num")
                log(f"  🔒 {t.get('title')} +{amt}金币 status={t.get('status')}")
                if t.get("status") == 0 and tt:
                    rr = self.call("/api/LockScreen/GetReward", {"task_type": tt})
                    if rr.get("code") == "0":
                        c = (rr.get("data") or {}).get("coin", 0) or amt
                        log(f"    ✅ 领取 +{c}金币")
                    else:
                        log(f"    ⚠️ 领取: {rr.get('message')}")
                    time.sleep(6)
        else:
            log(f"⚠️ 锁屏任务: {r.get('message')}")

    def fission_sign(self):
        r = self.call("/api/Fission/get_fission_page_info")
        if r.get("code") == "0":
            d = r.get("data") or {}
            s = d.get("sign_in_info") or {}
            if not s.get("today_is_signed"):
                rr = self.call("/api/welfare/GetReward", {"taskType": "global_redpackage_sign_in", "page": "global_red_package"})
                if rr.get("code") == "0":
                    log(f"✅ 裂变签到 +{s.get('sign_in_reward')}金币")
            else:
                log(f"ℹ️ 裂变签到 今日已签")

    def report(self):
        r = self.call("/api/me/wallet")
        prof = (r.get("data") or {}).get("profile") or {}
        coin = prof.get("coin")
        if coin is None:
            w = self.call("/api/welfare/myWelfareNew", {"push_permission": "1"})
            ui = (w.get("data") or {}).get("userInfo") or {}
            coin = ui.get("coin")
        log(f"👛 钱包: 余额总额={prof.get('balance_total')}元 可用={prof.get('balance_available')}元 可提={prof.get('balance_withdrawable')}元 金币={coin}")
        return {"balance": prof.get('balance_total'), "coin": coin}

    def free_listen(self):
        r = self.call("/api/FreeListenV2/GetInfo")
        if r.get("code") == "0":
            d = r.get("data") or {}
            log(f"🎧 免费听: 倒计时{d.get('countdown')}秒 可用{d.get('available_num')} 已领{d.get('received_num')} 时长{d.get('reward_duration_total')}")

    def withdraw_info(self):
        r = self.call("/api/withdrawl/get_page_info_v2")
        if r.get("code") == "0":
            d = r.get("data") or {}
            ui = d.get("user_info") or {}
            log(f"💳 提现页: 余额={ui.get('balance_total')} 可提={ui.get('balance_withdrawable')}")
        r = self.call("/api/me/wallet")
        prof = (r.get("data") or {}).get("profile") or {}
        log(f"💳 可提现={prof.get('balance_withdrawable')}元 金币={prof.get('coin')}")

    def info(self):
        self.report()
        self.free_listen()
        r = self.call("/api/welfare/GetWelfarePageInfo", {"page": "my_welfare"})
        if r.get("code") == "0":
            s = (r.get("data") or {}).get("sign_info") or {}
            log(f"📅 福利签到: 今日+{s.get('today_reward')} 累计奖励{s.get('reward_count')} 可签{s.get('can_sign')}")
        r = self.call("/api/Task/GetOnlineRewardList")
        d = r.get("data") or {}
        log(f"📡 在线奖励: {len(d.get('red_packet_list') or [])}个待领")
        r = self.call("/api/Invite/WelfareFundPage", {"invite_code": ""})
        log(f"🔗 邀请福利: {json.dumps(r.get('data'), ensure_ascii=False)[:120]}")
        self.withdraw_info()

    def invite_bind(self, code="38DZA4"):
        ways = [
            ("fill_invite_code/v1", "/api/task/fill_invite_code", {"invite_code": code, "invite_type": "1"}),
            ("fill_invite_code/v2", "/api/task/fill_invite_code", {"invite_code": code, "invite_type": "2"}),
            ("fill_invite_code/v0", "/api/task/fill_invite_code", {"invite_code": code}),
            ("app_fill_invite_code_check", "/api/task/app_fill_invite_code_check", None),
        ]
        for name, path, extra in ways:
            r = self.call(path, extra)
            if r.get("code") == "0":
                return True
            msg = r.get("message", "")
            if any(k in msg for k in ["已绑定", "绑定过", "10天", "注册10", "已填写", "填写过"]):
                return False
            time.sleep(1)
        return False

    # ★ 修改：run_all 中 double_loop 前置 + 循环复查，big_turntable 独立调用
    def run_all(self):
        log(f"=== 账号 {self.device_id} 全自动任务 ===")
        if not self.login(): return
        time.sleep(2)
        self.report()
        time.sleep(2)
        self.invite_bind()
        time.sleep(2)
        self.double_loop()          # ★ 先扫一遍存量翻倍
        self.sign_all()             # 内部已触发 double_after
        self.clock_loop()
        self.envelopes()            # 内部已插入 double_after
        self.timing_redpack()       # 内部已插入 double_after
        self.bubble()
        self.welfare_sign_extra()
        self.auto_prereq()
        self.all_tasks()
        self.chest_task()
        self.big_turntable()        # ★ 新增大转盘
        self.regress_task()
        self.rewards()
        self.welfare_tasks()
        self.online_reward()
        self.news_chest()
        self.piggy_bank()
        self.sleep_task()
        self.wallet()
        self.ad_info()
        self.ad_reward_claim()
        self.lock_screen()
        self.fission_sign()
        log(f"🔁 高频收益循环开始 ({LOOPS}轮)")
        for rd in range(LOOPS):
            self.countdown_reward()
            self.listen_rewards()
            self.piggy_bank()
            self.clock_loop()
            self.double_loop()      # ★ 每轮复查翻倍
            if rd < LOOPS - 1:
                time.sleep(INTERVAL)
        self.listen_music_auto()
        self.get_dots()
        self.share_info()
        time.sleep(2)
        self.report()
        self.withdraw_info()
        log(f"=== 账号 {self.device_id} 完成 ===")

def main():
    args = sys.argv[1:]
    accs = collect_accounts()
    if not accs:
        log("! 未配置 KY_AUTH=device_id#refresh_token"); sys.exit(1)
    log(f"共 {len(accs)} 个账号")
    cmds = {
        "sign": lambda k: k.sign_all(), "envelopes": lambda k: k.envelopes(),
        "timing": lambda k: k.timing_redpack(), "bubble": lambda k: k.bubble(),
        "reward": lambda k: k.rewards(), "online": lambda k: k.online_reward(),
        "listen": lambda k: k.listen_rewards(), "piggy": lambda k: k.piggy_bank(),
        "double": lambda k: k.double_loop(), "adclaim": lambda k: k.ad_reward_claim(),
        "welfare": lambda k: k.welfare_tasks(), "countdown": lambda k: k.countdown_reward(),
        "clock": lambda k: k.clock_loop(), "wsign": lambda k: k.welfare_sign_extra(),
        "news": lambda k: k.news_chest(), "prereq": lambda k: k.auto_prereq(),
        "wallet": lambda k: k.wallet(), "record": lambda k: k.reward_record(),
        "signlist": lambda k: k.sign_list(), "music": lambda k: k.music_list(),
        "fission": lambda k: k.fission(), "lockscreen": lambda k: k.lock_screen(),
        "report": lambda k: k.report(), "info": lambda k: k.info(),
        "withdraw": lambda k: k.withdraw_info(), "freelisten": lambda k: k.free_listen(),
        "invite": lambda k: k.invite_bind(),
        "tasks": lambda k: k.all_tasks(), "chest": lambda k: k.chest_task(),
        "regress": lambda k: k.regress_task(), "sleep": lambda k: k.sleep_task(),
        "sendcoin": lambda k: k.listen_music_auto(), "listenauto": lambda k: k.listen_music_auto(),
        # ★ 新增：转盘命令
        "turntable": lambda k: k.big_turntable(),
        "wheel": lambda k: k.big_turntable(),
    }
    for auth in accs:
        ky = Ky(auth)
        if not args:
            ky.run_all()
        else:
            c = args[0].lower()
            if c in cmds and ky.login():
                cmds[c](ky)
            else:
                print("用法: 脚本 [all|sign|envelopes|timing|bubble|countdown|tasks|chest|regress|sleep|reward|online|listen|piggy|double|welfare|wallet|record|signlist|music|fission|lockscreen|report|info|withdraw|freelisten|invite|sendcoin|listenauto|turntable|wheel]")

if __name__ == "__main__":
    main()

# 当前脚本来自于 http://script.345yun.cn 脚本库下载！
# 当前脚本来自于 http://2.345yun.cn 脚本库下载！
# 当前脚本来自于 http://2.345yun.cc 脚本库下载！
# 脚本库官方QQ群1群: 429274456
# 脚本库官方QQ群2群: 1077801222
# 脚本库官方QQ群3群: 433030897
# 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
# 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
# 您在使用脚本库下载的脚本时自行检查判断风险。
# 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。