#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
饿了么「幸运星」会员权益中心自动化 · 青龙面板 / 多账号 / Python3
================================================================

逆向目标：https://tb.ele.me/app/TBTakeout/engage-hub/home
项目形态：TBTakeout/engage-hub（阿里 ICE + mtop 协议），签到奖励币种 prizeType = STAR（幸运星）

流程
----
  首页聚合（顺带取幸运星余额并播报）→ 签到 → 夺宝/抽奖 → 下单免单抽奖 → 答题
  → 查询任务 → 浏览/点击埋点 → 重新查询 → 领取任务奖励
  → 刷新余额 + 收益明细 → 兑换商城 → 汇总推送（每个号都带「现有多少星」）

实机验证要点（2026-09-24 实测，勿删）
------------------------------------
  1. 8789/yyb 微信 code 换来的 Cookie 可以直接驱动本脚本；只是不含 _m_h5_tk，
     脚本会自动向 mtop 申领（首个请求由 Set-Cookie 下发）。
  2. ★★ 405::行为受限 的**唯一开关是 UA**：必须是移动端微信小程序 UA
     （Android 形如 `Linux; Android 13; <机型> ... XWEB/1160 MMWEBSDK/20230805
     MicroMessenger/8.0.58 ... MiniProgramEnv/android`；
      iOS 形如 `iPhone ... MicroMessenger/8.0.58 miniProgram/<appid>`）。
     三轮对照实测：
        · 小程序 UA + Referer=tb.ele.me        → SUCCESS
        · 桌面 Chrome UA + 正确 servicewechat Referer → 405::行为受限
        · 小程序 UA + servicewechat Referer    → SUCCESS
     结论：Referer 只是辅助一致性，**UA 不对就一定被拦**。
  3. ★ 签到接口用 recordsignin（策略 RECEIVE_AND_SIGNIN 时），
     且必须带今日奖励参数 actCode / sceneCode / prizeMark / signInDay + copyId，
     缺任一项会 FAIL_BIZ_REWARD_MODE_NOT_SIGNIN_AND_RECEIVE（实测入参补全即 SUCCESS）。
  4. 任务列表在首页聚合返回的 missionCollectionId 下（本账号为 3112）；
     THIRD 任务（inter_change / commercial_click）用 trigger 推进，
     浏览任务（PAGEVIEW）用 pageview 上报；两者都依赖第 2 条的环境头。
  5. 类型 ORDER / P2P 的任务无法自动完成（需真实下单 / 拉好友），自动跳过。
  6. ★ 幸运星余额在**首页聚合**里：data.data.property.data.STAR.amount
     （兑换商城 exchangeV2.data.propertyInfo.remainAmount 是同一个值，作兜底）。
     querypropertydetail 只返回明细 list（没有余额字段，只有 totalRecords），
     所以余额一律从 homepage 取：开跑前报一次、收尾再刷一次，日志形如
     「💰 幸运星 5600 → 5680（本轮 +80）」。

环境变量（账号）
----------------
  ELM_COOKIE        饿了么 Cookie（必须含 _m_h5_tk），多账号换行分隔
  ELM_COOKIE2/3     第二、第三个账号（可选）
  LUCKYSTAR         兼容入口，等价于 ELM_COOKIE
  XX_ACCOUNTS / LS_ACCOUNTS / LUCKYSTAR_ACCOUNTS  同义兼容
  每行写法（两种都认）：
      备注#cookie        ← 推荐（与原 JS 插件一致，形如 小号A#cookie2=xxx; _m_h5_tk=yyy; ...）
      cookie             ← 裸 Cookie，脚本自动从 userId / munb 里取备注

环境变量（参数）
----------------
  ELM_LAT / ELM_LNG            经纬度，默认上海 31.2304 / 121.4737
  ELM_APPKEY                   mtop appKey，默认 12574478（web 端）
  ELM_GATEWAY                  mtop 网关，默认 https://waimai-guide.ele.me/h5/
  ELM_APP_VERSION              aladdin prodVersion，默认 12.8.8
  ELM_TASK_TIMES               每个 THIRD 任务的最大补跑次数，默认 3
  ELM_SKIP_SIGNIN=1            跳过签到
  ELM_SKIP_TASKS=1             只签到，不跑任务
  ELM_SKIP_DRAW=1              跳过夺宝/抽奖
  ELM_EXCHANGE=1               允许自动兑换商城（**会消耗幸运星**，默认只报告不兑）
  ELM_EXCHANGE_MAX             每次最多兑几件，默认 1
  ELM_SKIP_ORDERFREE=1         跳过下单免单抽奖
  ELM_QUIZ_ACTID               趣味话题答题的 actId（在答题页 URL 上，不传则不跑）
  ELM_DRAW_TIMES               每个夺宝组件最多抽几次，默认 1
  ELM_DEBUG=1                  打印每个任务原始数据
  ELM_PROXY                    代理，逗号/换行分隔。三种格式：
                                ① IP|端口|用户|密码|到期日  如 223.15.244.28|9347|4363991|ab7ac092c|2026-10-23
                                  （到期自动停用并警告，过期条目不会用）
                                ② http://user:pass@ip:port
                                ③ ip:port
                                多条时按账号稳定分配（同账号永远同出口 IP）
  ELM_DEVICE_OS                指纹机型：android（默认，与自建面板一致）| ios
  ELM_RESET_DEVICE=1           重置本账号设备指纹（等价面板「重置设备」）
  ELM_DEVICE_API               指纹服务地址（fingerd），如 http://192.168.3.174:18911
                             填了就走服务领指纹（同账号稳定、跨账号/跨项目绝不重复）；
                             留空则本地按面板同款规则生成
  ELM_DEVICE_API_KEY           指纹服务的 X-API-Key（服务端设了 FP_KEY 时必填）
  ELM_DEVICE_SCENE             场景名，默认 eleme（一个服务可给多项目分池统计）
  LUCKYSTAR_DRYRUN=1           只打印将要发送的请求与签名，不实际发出（排查用）

通知
----
  优先用青龙自带 sendNotify，其次内置 pushplus / Server酱 / 企业微信 / 钉钉 / TG / Bark

风控须知（ELM_HUMAN / ELM_STEALTH / ELM_ONCE_PER_DAY 控制）
--------------------------------------------------------
  已内置的规避手段：
    · ★ 决定项 —— UA 必须是移动端微信小程序 UA（见文件顶部第 2 条实测对照），
      Referer=servicewechat.com/<appid>/…/page-frame.html 作辅助一致性
    · 设备/链路头：x-utdid / x-ele-ua / x-uid / x-eleme-requestid（链路 id 每请求都换）
    · 设备指纹：与自建指纹服务同池同规则（机型/版本/渠道随机 + androidId 逐字符 +2
      混淆 + 每账号独占不复用）；可本地生成，也可由 fingerd 统一发放
      （ELM_DEVICE_API），ELM_RESET_DEVICE=1 换设备
    · 拟人节奏：对数正态停顿、任务顺序打乱、viewTime 随机、经纬度 1km 抖动
    · 熔断：连续 2 次 405::行为受限 立即停手，不反复撞
    · 每日一次锁：同一天不重复执行（ELM_FORCE=1 强制）
    · 随机错峰启动 0~15 分钟（ELM_OFFSET_MAX=0 关闭）
    · 账号串行执行 + 8~25s 间隔
  刻意不做的事：
    · 不碰提现 / 邀请助力 / 下单类任务 —— 这几个接口风控最严、性价比最低
    · 不并发、不批量换 IP（IP 与账号属地不一致反而更像机器）
    · 不用来路不明的代理池；要用就选与账号同城、住宅 IP
    · 单账号每天跑 1 次就够，别为多薅反复触发

定时任务
--------
  cron: 30 8 * * *
  task 幸运星.py

用法
----
  python 幸运星.py                 # 正常运行（多账号串行）
  python 幸运星.py --dryrun        # 打印首个账号的请求构造结果，不发请求
  python 幸运星.py --selftest      # 只跑首页聚合，打印原始响应，验证 Cookie 与签名
  python 幸运星.py --dump-account  # 打印解析到的账号（脱敏）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import random
import re
import string
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, urlencode

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

SCRIPT_VERSION = "1.5.0"      # 1.5.0：每个账号播报幸运星余额（跑前 X → 跑后 Y，本轮 +N）
START_TS = time.time()


# =========================================================================== #
#  常量（逆向自 engage-hub v1.3.5）
# =========================================================================== #

API = {
    "homepage":     "mtop.alsc.interact.et.interact.center.homepage",
    "querytask":    "mtop.ele.biz.growth.task.core.querytask",
    "receivetask":  "mtop.ele.biz.growth.task.core.receivetask",
    "receiveprize": "mtop.ele.biz.growth.task.core.receiveprize",
    "pageview":     "mtop.ele.biz.growth.task.event.pageview",
    "trigger":      "mtop.ele.biz.growth.task.event.trigger",
    # 签到并领奖 / 独立签到
    "signin":       "mtop.alsc.interact.playapp.signin.component.signinandreceive",
    "recordsignin": "mtop.alsc.interact.playapp.signin.component.recordsignin",
    # 夺宝/抽奖（1.4.2 前端包逆向）
    "lottery_draw": "mtop.alsc.interact.playapp.reward.lottery.draw",
    # 幸运星资产/明细、兑换商城
    "property_detail": "mtop.koubei.interaction.center.common.querypropertydetail",
    "mall_list":      "mtop.alsc.interact.playapp.reward.right.mallrecall",
    "mall_exchange":  "mtop.alsc.interact.playapp.reward.right.exchange",
    # 下单免单抽奖
    "orderfree_draw": "mtop.alsc.interact.et.orderfree.draw",
    # 趣味话题答题
    "quiz_query":  "mtop.alsc.interact.playapp.quiz.query",
    "quiz_submit": "mtop.alsc.interact.playapp.quiz.submit",
    "quiz_award":  "mtop.alsc.interact.playapp.quiz.award",
}

#: 风控 asac token（逆向自 engage-hub 1.4.2 前端包常量表）
ASAC = {
    "SIGNIN":          "alsc3Lhy681SA5TT4iHgL3",
    "PRIZE":           "alscadOjfleDPawx9zVoT0",
    "PAGEVIEW":        "alscFS8BNTO6jivYS7XOAM",
    "TRIGGER":         "2A21607NIIT1ND5C4YXJ6C",
    "LOTTERY_DRAW":    "alscdZLQXT9DEAlXvQQOLO",   # 夺宝/抽奖
    "MIANDAN_DRAW":    "alsc6AD8Rni21gsqJ5rceg",   # 免单抽奖
    "ORDER_FREE_DRAW": "alscrX2P4rmvl0NhmQgr9x",   # 下单免单
    "MALL_EXCHANGE":   "alsc5KvbdX5mHl3sdv4guV",   # 幸运星兑换商城
    "SNS_TRIGGER":     "alsc8tok9QFxdUiCPfmpbK",   # 分享触发
    "QUIZ_AWARD":      "alsc0Ue9L6Q0YtTZjC3Ovx",   # 答题领奖
}

BIZ_SCENE = "interact_center"
ACCOUNT_PLAN = "HAVANA_COMMON"
PAGE_VERSION = "1.4.2"          # 前端包版本，homepage 的 version 入参（线上当前版本）

CPN_CODES = [
    "PLAY_NOTICE_CPN",
    "INTERACT_RESOURCE_CPN",
    "MORE_MENU_CPN",
    "STAR_MSG_CONTENT_CPN",
    "PLAY_RESOURCE_CPN",
    "INTERACT_CENTER_SKIN_COMPONENT",
    "INTERACT_CENTER_BUBBLE",
    "INTERACT_CENTER_LOTTERY",
]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36")

DEBUG = os.environ.get("ELM_DEBUG", "") == "1"
DRYRUN = os.environ.get("LUCKYSTAR_DRYRUN", "") == "1"
#: 拟人化行为层（默认开；ELM_HUMAN=0 关闭）
HUMAN = os.environ.get("ELM_HUMAN", "1") != "0"
#: 伪装层（默认开；ELM_STEALTH=0 关闭）
STEALTH = os.environ.get("ELM_STEALTH", "1") != "0"
#: 每日只跑一次（默认开，防止青龙重复触发/手动重跑被判定异常；ELM_FORCE=1 强制）
ONCE_PER_DAY = os.environ.get("ELM_ONCE_PER_DAY", "1") != "0"
STATE_FILE = Path(__file__).resolve().parent / "lucky_state.json"
#: 账号级风控标记（命中即中止本轮，不再发写请求）
RISK_RE = re.compile(r"FAIL_BIZ_USER_RISK|用户存在风险|USER_RISK", re.I)

# ---- 设备指纹：与自建指纹面板（192.168.3.174:18903）同一套池与「不复用」规则 ----
DEVICE_MODELS = ["22081212C", "PHB110", "V2134A", "SM-S9080",
                 "PJZ110", "LIO-AN00", "M2011K2C", "PGT-AN10"]
DEVICE_VERSIONS = ["13", "12", "14", "11"]
DEVICE_CHANNELS = ["channel35", "channel50", "channel60"]
DEVICE_FILE = Path(__file__).resolve().parent / "lucky_devices.json"


def random_hex(nbytes: int) -> str:
    return "".join(random.choice("0123456789abcdef") for _ in range(nbytes))


def obfuscate_id(raw: str) -> str:
    """与面板同款混淆：逐字符 +2（不可逆）。"""
    return "".join(chr((ord(c) + 2) & 0xFFFF) for c in raw)


def make_device() -> dict:
    """生成一个设备指纹：机型/版本/渠道从池里随机，ID 全随机（同面板 makeDevice）。"""
    rid = random_hex(16)
    model = random.choice(DEVICE_MODELS)
    ver = random.choice(DEVICE_VERSIONS)
    ch = random.choice(DEVICE_CHANNELS)
    wxv = cfg("ELM_WECHAT_VERSION", "8.0.58")
    return {
        "androidIdRaw": rid,
        "androidIdObfuscated": obfuscate_id(rid),
        "clientType": f"#11.3.0#{ch}#{model}#",
        "androidVersion": ver,
        "model": model,
        "channel": ch,
        "wechatVersion": wxv,
        "os": cfg("ELM_DEVICE_OS", "android"),
        "ua": (f"Mozilla/5.0 (Linux; Android {ver}; {model} Build/TKQ1.220829.002; wv) "
               "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/107.0.0.0 "
               f"Mobile Safari/537.36 XWEB/1160 MMWEBSDK/20230805 MicroMessenger/{wxv} "
               "WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android"),
    }


def device_key(d: dict) -> str:
    return f"{d.get('clientType', '')}#{d.get('androidIdObfuscated', '')}"


def remote_device(api: str, key: str, reset: bool = False) -> dict | None:
    """
    向指纹服务（fingerd / 自建面板）申请设备：同一个 key 会拿回同一台（服务端保证）。
    服务不可用或返回异常时返回 None，调用方自动退回本地生成。
    """
    if not api:
        return None
    url = api if api.rstrip("/").endswith("gen_device") else api.rstrip("/") + "/api/gen_device"
    headers = {}
    ak = cfg("ELM_DEVICE_API_KEY")
    if ak:
        headers["X-API-Key"] = ak
    try:
        r = requests.post(url, timeout=6, headers=headers, json={
            "key": key, "scene": cfg("ELM_DEVICE_SCENE", "eleme"),
            "os": cfg("ELM_DEVICE_OS", "android"), "reset": bool(reset)})
        j = r.json() or {}
        d = j.get("data") or j
        if isinstance(d, dict) and (d.get("androidIdObfuscated") or d.get("clientType")):
            log(f"[指纹] 领取自 {api} → {d.get('model')} / Android {d.get('androidVersion')}"
                f" / {d.get('channel')}")
            return d
        log(f"[指纹] 服务返回异常（{str(j)[:80]}），改用本地生成")
    except Exception as exc:                                # noqa: BLE001
        log(f"[指纹] 服务不可用（{str(exc)[:60]}），改用本地生成")
    return None


def alloc_device(account_key: str, reset: bool = False) -> dict:
    """
    给账号分配**独占且不复用**的设备指纹，并持久化：
      · 同一账号下次运行拿到同一指纹（设备稳定，不会天天换机）
      · 不同账号绝不共用（避开"一机多号"关联）
      · ELM_RESET_DEVICE=1 相当于面板的「重置设备」
    """
    store: dict = {}
    try:
        if DEVICE_FILE.is_file():
            store = json.loads(DEVICE_FILE.read_text(encoding="utf-8")) or {}
    except Exception:                                       # noqa: BLE001
        store = {}
    accs = store.setdefault("accounts", {})
    used = set(store.get("used") or [])
    dev = None if reset else accs.get(account_key)
    if dev is None:
        api = cfg("ELM_DEVICE_API")
        dev = remote_device(api, account_key, reset) if api else None
        if not dev:
            for _ in range(100):                            # 同面板：最多试 100 次找未用过的
                cand = make_device()
                if device_key(cand) not in used:
                    dev = cand
                    break
            else:
                dev = make_device()
        used.add(device_key(dev))
        accs[account_key] = dev
        store["used"] = sorted(used)[-2000:]
        if not dev.get("utdid"):
            dev["utdid"] = ("WX" + hashlib.sha1(
                (dev["androidIdRaw"] + dev["channel"]).encode()).hexdigest()[:30]).upper()
        try:
            DEVICE_FILE.write_text(json.dumps(store, ensure_ascii=False, indent=2),
                                   encoding="utf-8")
        except Exception:                                   # noqa: BLE001
            pass
    return dev


def log(msg: str = "") -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def nap(lo: float, hi: float) -> None:
    time.sleep(random.uniform(lo, hi))


def nap_human(mean: float = 2.0, sigma: float = 0.6, cap: float = 4.0) -> None:
    """对数正态停顿：多数短、偶发长，比均匀分布更像真人手速。"""
    if HUMAN:
        time.sleep(min(random.lognormvariate(math.log(max(mean, 0.2)), sigma), mean * cap))


def jitter(lat: float, lng: float, km: float = 1.2) -> tuple[float, float]:
    """在常用坐标附近做小范围抖动，避免每次请求经纬度完全一致。"""
    if not HUMAN or km <= 0:
        return lat, lng
    r = km / 111.0
    return round(lat + random.uniform(-r, r), 6), round(lng + random.uniform(-r, r) / max(0.2, math.cos(math.radians(lat))), 6)


def cfg(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    return v.strip() if v and v.strip() else default


def md5(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


# =========================================================================== #
#  账号解析
# =========================================================================== #

def parse_cookie_line(line: str) -> tuple[str, str]:
    """
    从一行里剥出 (备注, 纯 Cookie)。

    同时兼容两种写法，判定依据是「# 后面是否还有 key=value」：
        备注#cookie    → 小号A#cookie2=xxx; _m_h5_tk=yyy; ...
        cookie#备注    → cookie2=xxx; _m_h5_tk=yyy; ...#小号A
        裸 cookie      → 直接识别，备注自动从 userId / munb 里取
    """
    s = str(line or "").strip().replace("\u3000", " ")
    if not s:
        return "", ""
    remark = ""
    if "#" in s:
        head, tail = s.split("#", 1)
        if "=" in tail:                 # 备注#cookie
            remark, s = head.strip(), tail.strip()
        else:                           # cookie#备注
            s, remark = head.strip(), tail.strip()
    # 去掉行首的时间戳/标签等干扰，从第一个 key=value 起取到行尾
    parts = s.split()
    start = next((i for i, p in enumerate(parts) if re.match(r"^[A-Za-z0-9_]+=", p)), -1)
    if start < 0:
        return remark, s if "=" in s else ""
    cookie = " ".join(parts[start:]).strip()
    if not remark:
        remark = cookie_remark(cookie)
    return remark, cookie


def cookie_remark(cookie: str) -> str:
    """从 Cookie 里挑一个可读标识当备注，避免把整条 Cookie 打进日志。"""
    get = lambda k: (re.search(rf"(?:^|;\s*){re.escape(k)}=([^;]+)", cookie) or [None, ""])[1]  # noqa: E731
    munb = get("munb")
    uid = get("userId") or get("UTUSER")
    if munb and uid:
        return f"{munb[:-4]}****" if len(munb) > 4 else munb
    if uid:
        return f"uid{uid[-6:]}"
    return "账号"


def load_accounts() -> list[tuple[str, str]]:
    """返回 [(备注, cookie), ...]，去重且保持顺序。"""
    raw = ""
    for name in ("ELM_COOKIE", "LUCKYSTAR", "XX_ACCOUNTS", "LS_ACCOUNTS", "LUCKYSTAR_ACCOUNTS"):
        v = os.environ.get(name)
        if v and v.strip():
            raw = v
            break
    extra = "\n".join(cfg(k) for k in ("ELM_COOKIE2", "ELM_COOKIE3") if cfg(k))
    if extra:
        raw = f"{raw}\n{extra}" if raw else extra

    # 兜底：读「饿了么Code登录」CLI 产出的 cookie 文件（每行 <时间> <openid> <账号> <cookie>）
    if not raw.strip():
        name = cfg("ELM_COOKIE_FILE", "eleme_cookie.txt")
        here = Path(__file__).resolve().parent
        for cand in (Path(name), here / name, Path.cwd() / name, Path("/ql/data") / name,
                     Path("/ql/data/scripts") / name):
            try:
                if cand.is_file():
                    txt = cand.read_text(encoding="utf-8", errors="ignore")
                    if txt.strip():
                        log(f"📂 Cookie 来源：文件 {cand}")
                        raw = txt
                        break
            except Exception:                                   # noqa: BLE001
                continue

    out, seen = [], set()
    for line in raw.split("\n"):
        # 允许用 & 拼一行多号（Cookie 本身不含 & 作为分隔符时安全）
        for seg in line.split("&") if "&" in line and "=" not in line.split("&")[0] else [line]:
            remark, cookie = parse_cookie_line(seg)
            if not cookie or cookie in seen:
                continue
            # 必须像 Cookie：至少 2 组 key=value
            if len(re.findall(r"[A-Za-z0-9_]+=", cookie)) < 2:
                log(f"⚠ 跳过疑似非 Cookie 的行：{seg[:60]}…")
                continue
            seen.add(cookie)
            out.append((remark or f"账号{len(out) + 1}", cookie))
    return out


# =========================================================================== #
#  网络层：mtop
# =========================================================================== #

class MtopError(Exception):
    pass


class ElmAccount:
    """单账号：mtop 会话 + 业务编排。"""

    def __init__(self, remark: str, cookie: str) -> None:
        self.remark = remark
        self.cookie = cookie.strip()
        self.lat = float(cfg("ELM_LAT", "31.2304"))
        self.lng = float(cfg("ELM_LNG", "121.4737"))
        self.app_key = cfg("ELM_APPKEY", "12574478")
        self.gateway = cfg("ELM_GATEWAY", "https://waimai-guide.ele.me/h5/").rstrip("/") + "/"
        self.app_version = cfg("ELM_APP_VERSION", "12.8.8")
        self.task_times = int(cfg("ELM_TASK_TIMES", "3") or 3)
        self.session = requests.Session()
        self.proxies = self._proxies()
        self.result: dict[str, str] = {}
        self.risk_flagged = False
        #: 幸运星余额（跑之前 / 跑之后），用于日志里给每个号播报「现有多少币」
        self.star_start: int | None = None
        self.star_end: int | None = None
        # ★ 实测关键：必须伪装成微信小程序环境，否则所有写接口返回 405::行为受限
        self.appid = cfg("ELEME_APPID", "wxece3a9a4c82f58c9")
        self.uid = self._cookie_get("UTUSER") or self._cookie_get("userId")
        # 设备指纹：按账号独占、跨账号不复用、跨运行稳定（详见 alloc_device）。
        # key 优先用 munb/UTUSER/userId —— 可读且与其他项目（共用 fingerd 时）对得上，
        # 取不到才退回 Cookie 哈希。
        self.account_key = (self._cookie_get("munb") or self._cookie_get("UTUSER")
                            or self._cookie_get("userId")
                            or hashlib.md5(self.cookie.encode()).hexdigest()[:12])
        self.dev = alloc_device(self.account_key,
                               reset=os.environ.get("ELM_RESET_DEVICE") == "1")
        self.wechat_version = self.dev.get("wechatVersion") or cfg("ELM_WECHAT_VERSION", "8.0.58")
        self.utdid = self.dev.get("utdid", "") if STEALTH else ""
        self.hdr = {
            "User-Agent": self.dev["ua"] if STEALTH else
                          ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                           "AppleWebKit/605.1.15 Mobile/15E148 "
                           f"MicroMessenger/{self.wechat_version} miniProgram/{self.appid}"),
            "Referer": f"https://servicewechat.com/{self.appid}/831/page-frame.html",
            "Origin": "https://servicewechat.com",
            "Accept": "application/json,text/plain,*/*",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Language": "zh-CN,zh;q=0.9",
            "x-tap": "wx",
        }
        if STEALTH:
            # 真实小程序环境必带的设备/链路头（格式逆向自登录 CLI）。
            # 账号间 utdid 互不相同 —— 同一台机器多账号共用指纹是典型的关联风控特征。
            self.hdr.update({
                "x-utdid": self.utdid,
                "x-ele-ua": " ".join(filter(None, [
                    "RenderWay/miniProgram",
                    f"MiniAppId/{self.appid}",
                    f"MiniAppVersion/{self.app_version}",
                    f"DeviceId/{self.uid}" if self.uid else "",
                    "AppName/Wechat",
                    (f"Xiaomi/{self.dev['model']}/Android {self.dev['androidVersion']}"
                     if self.dev.get("os") == "android"
                     else "Apple/iPhone/iOS 17.0"),
                    f"Wechat/{self.wechat_version}",
                    "channel/wechat_app",
                    "subChannel/wechat_app.default",
                    f"Longitude/{self.lng:.4f}",
                    f"Latitude/{self.lat:.4f}",
                ])),
            })
            if self.uid:
                self.hdr["x-uid"] = self.uid

    # ---------- 基础 ----------
    def _proxies(self) -> dict | None:
        """
        解析代理环境变量，支持三种格式（逗号/换行分隔多条）：
          1. 长效代理：IP|端口|用户名|密码|过期日期
             如 223.15.244.28|9347|4363991|ab7ac092c|2026-10-23
          2. http://user:pass@ip:port  /  http://ip:port
          3. ip:port
        规则：
          · 过期条目自动剔除（打警告，绝不用过期代理跑请求）
          · 多条时按账号 cookie 哈希稳定选取（同账号永远同一出口 IP）
        """
        raw = cfg("ELM_PROXY") or cfg("LUCKYSTAR_PROXY") or cfg("PROXY") or cfg("GLOBAL_PROXY")
        if not raw or not raw.strip():
            return None
        entries = [e.strip() for e in re.split(r"[,\n]+", raw) if e.strip()]
        today = datetime.now().strftime("%Y-%m-%d")
        usable: list[str] = []
        for e in entries:
            parts = e.split("|")
            if len(parts) == 5:                          # 长效格式 IP|PORT|USER|PASS|EXPIRE
                ip, port, user, pwd, expire = (x.strip() for x in parts)
                if expire and expire < today:            # 字符串比较即日期比较
                    log(f"⚠ 代理 {ip}:{port} 已于 {expire} 过期，跳过")
                    continue
                e = f"http://{quote(user)}:{quote(pwd)}@{ip}:{port}"
            elif "://" not in e:
                e = "http://" + e
            usable.append(e)
        if not usable:
            log("⚠ 所有代理条目均已过期，本次直连运行")
            return None
        pick = usable[0] if len(usable) == 1 else \
            usable[int(hashlib.md5(self.cookie.encode()).hexdigest(), 16) % len(usable)]
        return {"http": pick, "https": pick}

    def _log(self, msg: str) -> None:
        log(f"【{self.remark}】{msg}")

    def _cookie_get(self, key: str) -> str:
        from urllib.parse import unquote                             # noqa: PLC0415
        m = re.search(rf"(?:^|;\s*){re.escape(key)}=([^;]*)", self.cookie)
        return unquote(m.group(1)) if m else ""

    @property
    def token(self) -> str:
        """mtop 签名 token = Cookie 里 _m_h5_tk 的下划线前段。"""
        m = re.search(r"(?:^|;\s*)_?m_h5_tk=([^;]+)", self.cookie)
        return m.group(1).split("_")[0] if m else ""

    def _update_cookie(self, set_cookie: str) -> bool:
        if not set_cookie:
            return False
        upd = []
        for k in ("_m_h5_tk", "_m_h5_tk_enc"):
            m = re.search(rf"{k}=([^;,\s]+)", set_cookie)
            if m:
                upd.append(f"{k}={m.group(1)}")
        if not upd:
            return False
        clean = re.sub(r";\s*_m_h5_tk(_enc)?=[^;]*", "", self.cookie, flags=re.I)
        self.cookie = clean.rstrip("; ") + "; " + "; ".join(upd)
        return True

    @staticmethod
    def _grab_set_cookie(resp) -> str:
        """尽量把响应里所有 Set-Cookie 都收齐（requests 合并后常被截断）。"""
        parts = []
        try:
            parts.extend(resp.raw.headers.getlist("Set-Cookie"))
        except Exception:                                       # noqa: BLE001
            pass
        single = resp.headers.get("Set-Cookie", "")
        if single and single not in parts:
            parts.append(single)
        return "; ".join(parts)

    def prime_token(self) -> bool:
        """
        App 端 Cookie 通常不含 _m_h5_tk —— mtop 会在首个请求里通过
        Set-Cookie 下发 <token>_<ts>，拿到后才能签名。这里主动申领一次。
        """
        if self.token:
            return True
        if DRYRUN:
            self._log("[dryrun] Cookie 无 _m_h5_tk，跳过申领（真机运行会自动获取）")
            return True
        self._log("Cookie 无 _m_h5_tk，向 mtop 申领签名 token …")
        for attempt in range(3):
            try:
                self.mtop(API["querytask"], "1.0", {"bizScene": BIZ_SCENE}, retry=2)
            except Exception as exc:                            # noqa: BLE001
                if not self.token:
                    self._log(f"   申领第 {attempt + 1} 次未拿到：{str(exc)[:80]}")
            if self.token:
                self._log(f"✅ 已获取 token {self.token[:8]}…")
                return True
            time.sleep(1.0)
        self._log("❌ 仍未拿到 _m_h5_tk，请抓 H5 端（tb.ele.me）完整 Cookie")
        return False

    # ---------- mtop 请求 ----------
    def mtop(self, api: str, version: str, data: dict,
             extra_headers: dict | None = None, retry: int = 3) -> dict:
        """POST + subVersion 5.0，自动处理 token 刷新与过期重试。"""
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        for attempt in range(retry):
            t = str(int(time.time() * 1000))
            query = {
                "jsv": "2.7.5",
                "appKey": self.app_key,
                "t": t,
                "sign": md5(f"{self.token}&{t}&{self.app_key}&{payload}"),
                "api": api,
                "v": version,
                "type": "originaljson",
                "dataType": "json",
                "data": payload,
                # aladdin 投放校验（App 原生环境注入，缺一不可）
                "platform": "android",
                "product": "eleme",
                "prodVersion": self.app_version,
                "ttid": f"android@eleme_android_{self.app_version}",
            }
            if "locationInfos" in data:
                query["locationInfos"] = json.dumps([{"lng": self.lng, "lat": self.lat}],
                                                    separators=(",", ":"))
            url = f"{self.gateway}{api}/{version}/5.0/?" + urlencode(query)

            if DRYRUN:
                self._log(f"[dryrun] {api} v{version}")
                self._log(f"         token={self.token[:8]}…  sign={query['sign']}")
                self._log(f"         data={payload[:200]}")
                return {"ret": ["SUCCESS::dryrun"], "data": {"data": {}}}

            headers = dict(self.hdr)
            headers["Cookie"] = self.cookie
            if STEALTH:                     # 链路追踪 id 必须每次不同，否则一眼假
                headers["x-eleme-requestid"] = (
                    hashlib.sha1(os.urandom(16)).hexdigest().upper() + "|" + t)
            headers.update(extra_headers or {})
            try:
                resp = self.session.post(url, headers=headers, timeout=15, verify=False,
                                         proxies=self.proxies)
            except Exception as exc:                            # noqa: BLE001
                if attempt == retry - 1:
                    raise MtopError(f"网络异常：{str(exc)[:120]}") from exc
                time.sleep(1.5 * (attempt + 1))
                continue

            refreshed = self._update_cookie(self._grab_set_cookie(resp))
            try:
                js = resp.json()
            except Exception:                                   # noqa: BLE001
                raise MtopError(f"响应非 JSON：{resp.text[:160]}") from None
            ret = js.get("ret")
            ret0 = ret[0] if isinstance(ret, list) and ret else ""
            if re.search(r"TOKEN_EXOIRED|TOKEN_EXPIRED|TOKEN_EMPTY", str(ret0), re.I):
                if refreshed:
                    time.sleep(0.8)
                    continue                                    # token 已刷新，重试
                raise MtopError(f"token 失效且未回传新 token：{ret0}")
            return js
        raise MtopError("请求重试次数耗尽")

    def parse_ret(self, res: dict) -> dict:
        """mtop 返回解包：ret[0] 以 SUCCESS 开头，业务数据在 data.data。

        顺手做账号级风控识别：命中 FAIL_BIZ_USER_RISK / 用户存在风险 说明账号已被
        平台标记，继续发写请求只会加重（实测同项目的老脚本也是立刻中止）。
        """
        if not res:
            return {"ok": False, "msg": "空响应", "data": {}}
        ret = res.get("ret")
        ret0 = ret[0] if isinstance(ret, list) and ret else ""
        out = ({"ok": True, "msg": ret0, "data": (res.get("data") or {}).get("data",
                res.get("data") or {})} if str(ret0).startswith("SUCCESS")
               else {"ok": False, "msg": ret0 or str(res)[:120], "data": res.get("data") or {}})
        if not self.risk_flagged and RISK_RE.search(str(ret0)):
            self.risk_flagged = True
            self._log(f"🚫 账号被风控标记：{str(ret0)[:70]}")
            self._log("   → 本轮立即中止，不再发任何写请求（继续请求只会加重）：")
            self._log("     1) ELM_RESET_DEVICE=1 换设备指纹，或换用 App 抓包 Cookie")
            self._log("     2) 换出口 IP / 降低频率（单账号每天 1 次就够）")
            self._log("     3) 或等 24h~7d 标记自然衰减再试")
        return out

    # ---------- 业务 ----------
    def homepage(self) -> dict | None:
        self.lat, self.lng = jitter(self.lat, self.lng)
        data = {
            "bizScene": BIZ_SCENE,
            "version": PAGE_VERSION,
            "latitude": self.lat,
            "longitude": self.lng,
            "cpnCodes": json.dumps(CPN_CODES, separators=(",", ":")),
        }
        r = self.parse_ret(self.mtop(API["homepage"], "1.0", data))
        if not r["ok"]:
            self._log(f"❌ 首页聚合失败：{r['msg']}")
            return None
        d = r["data"] or {}
        # missionCollectionId: resource.data.INTERACT_RESOURCE_CPN[0].missionCollectionId
        cpns = ((d.get("resource") or {}).get("data") or {}).get("INTERACT_RESOURCE_CPN")
        first = cpns[0] if isinstance(cpns, list) and cpns else {}
        mission_collection_id = (first or {}).get("missionCollectionId", "")
        # 签到 copyId: signIn.data.signInQueryPrizeDTOS[today].extInfo.copyId
        signin_data = (d.get("signIn") or {}).get("data") or {}
        dtos = signin_data.get("signInQueryPrizeDTOS") or []
        today = next((x for x in dtos if isinstance(x, dict) and x.get("today")), {}) or {}
        copy_id = (((today.get("extInfo") or {}).get("copyId"))
                   or ((signin_data.get("extInfo") or {}).get("copyId")) or "")
        strategy = signin_data.get("signInRewardStrategy", "")
        # 今日奖励参数（actCode / sceneCode / prizeMark / signInDay）—— 签到接口必传，
        # 缺了会报 FAIL_BIZ_REWARD_MODE_NOT_SIGNIN_AND_RECEIVE
        awards = ((today.get("extInfo") or {}).get("stageAward")) or []
        award = awards[0] if awards else {}
        signed_today = bool(today.get("signIn"))
        if DEBUG:
            self._log(f"[调试] homepage signIn={json.dumps(d.get('signIn'), ensure_ascii=False)[:600]}")
        if mission_collection_id:
            self._log("✅ 首页聚合成功")
        else:
            self._log(f"⚠ 首页成功但无 missionCollectionId，业务字段：{list(d.keys())}")
        lotteries = ((d.get("resource") or {}).get("data") or {}).get("INTERACT_CENTER_LOTTERY") or []
        return {"missionCollectionId": mission_collection_id, "copyId": copy_id,
                "signInRewardStrategy": strategy, "award": award,
                "signedToday": signed_today, "lotteries": lotteries,
                "orderFree": d.get("orderFreeDraw"),
                "star": self._star_from(d)}

    @staticmethod
    def _star_from(d: dict) -> int | None:
        """
        从首页聚合 data 里取幸运星余额：
          主取 data.property.data.STAR.amount（实测 5600）
          兜底 data.exchangeV2.data.propertyInfo.remainAmount（兑换商城带的同值）
        """
        v = (((d.get("property") or {}).get("data") or {}).get("STAR") or {}).get("amount")
        if v in (None, ""):
            v = (((d.get("exchangeV2") or {}).get("data") or {})
                 .get("propertyInfo") or {}).get("remainAmount")
        try:
            return int(float(v)) if v not in (None, "") else None
        except Exception:                                   # noqa: BLE001
            return None

    def refresh_star(self) -> int | None:
        """重新拉一次首页聚合取余额（只读，不触发任何写行为）；失败返回 None。"""
        try:
            r = self.parse_ret(self.mtop(API["homepage"], "1.0", {
                "bizScene": BIZ_SCENE, "version": PAGE_VERSION,
                "latitude": self.lat, "longitude": self.lng,
                "cpnCodes": json.dumps(CPN_CODES, separators=(",", ":")),
            }))
        except Exception:                                   # noqa: BLE001
            return None
        return self._star_from(r.get("data") or {}) if r.get("ok") else None

    def signin(self, copy_id: str = "", strategy: str = "",
               award: dict | None = None, signed_today: bool = False) -> None:
        if cfg("ELM_SKIP_SIGNIN") == "1":
            self.result["签到"] = "➖ 已跳过"
            return
        if signed_today:
            self.result["签到"] = "✅ 今日已签"
            return
        award = award or {}
        data = {"bizScene": BIZ_SCENE, "latitude": self.lat, "longitude": self.lng}
        if copy_id:
            data["copyId"] = copy_id
        # ★ 实测必传：今日奖励的 actCode / sceneCode / prizeMark / signInDay，
        #   缺任意一个都会 FAIL_BIZ_REWARD_MODE_NOT_SIGNIN_AND_RECEIVE
        for src, dst in (("actCode", "actCode"), ("sceneCode", "sceneCode"),
                         ("prizeMark", "prizeMark"), ("signInDay", "signInDay")):
            if award.get(src) not in (None, ""):
                data[dst] = award[src]
        order = ((API["signin"], API["recordsignin"]) if strategy == "SIGNIN_AND_RECEIVE"
                 else (API["recordsignin"], API["signin"]))
        r = {"ok": False, "msg": "未执行"}
        mode = ""
        for api in order:
            try:
                r = self.parse_ret(self.mtop(api, "1.0", data, {"asac": ASAC["SIGNIN"]}))
            except Exception as exc:                            # noqa: BLE001
                r = {"ok": False, "msg": str(exc)}
            if r["ok"]:
                mode = "签到并领奖" if api == API["signin"] else "独立签到"
                break
            if re.search(r"已签到|REPEAT|ALREADY", str(r.get("msg", "")), re.I):
                break
        if not r["ok"]:
            msg = str(r.get("msg", ""))
            self.result["签到"] = ("✅ 今日已签" if re.search(r"已签到|REPEAT|ALREADY", msg, re.I)
                              else f"❌ {msg[:60]}")
            return
        if r["ok"]:
            rewards = (r["data"] or {}).get("rewards") or []
            total = sum(int(float(x.get("prizeValue") or x.get("equityValue") or 0))
                        for x in rewards if isinstance(x, dict))
            ptype = "幸运星" if (rewards and rewards[0].get("prizeType") == "STAR") else (
                (rewards[0].get("prizeType") if rewards else "") or "奖励")
            self.result["签到"] = f"✅ +{total} {ptype}（{mode}）"

    # ---------- 公共参数（前端 Kj()/定位 的等价物） ----------
    def _kj(self) -> dict:
        return {"bizScene": BIZ_SCENE, "version": PAGE_VERSION}

    def _loc(self) -> dict:
        return {"latitude": self.lat, "longitude": self.lng}

    def wallet(self) -> None:
        """幸运星资产：余额（首页 property）+ 今日收益（明细 querypropertydetail）。"""
        # 余额：此时今日收益已入账，重新拉一次首页拿最新值
        end = self.refresh_star()
        if end is not None:
            self.star_end = end
        try:
            r = self.parse_ret(self.mtop(API["property_detail"], "1.0", {
                **self._kj(), **self._loc(), "convertType": "INTERACT_CENTER",
                "pageNo": 1, "pageSize": 20}))
        except Exception as exc:                            # noqa: BLE001
            self.result["资产"] = f"❌ {str(exc)[:40]}"
            return
        if not r["ok"]:
            self.result["资产"] = f"❌ {str(r.get('msg'))[:40]}"
            return
        d = r["data"] or {}
        today = datetime.now().strftime("%Y-%m-%d")
        got = 0
        for it in (d.get("list") or []):
            if str(it.get("gmtCreateStr", "")).startswith(today) and it.get("detailType") == "GRANT":
                try:
                    got += int(float(it.get("amount") or 0))
                except Exception:                           # noqa: BLE001
                    pass
        self.result["资产"] = f"今日 +{got}"

    def mall(self) -> None:
        """
        兑换商城：列出可兑商品。默认**只报告不兑换**（兑换会花掉幸运星，
        属于花钱行为，必须显式开启）：ELM_EXCHANGE=1 才自动兑，ELM_EXCHANGE_MAX 限件数。
        """
        try:
            r = self.parse_ret(self.mtop(API["mall_list"], "1.0", {
                **self._kj(), **self._loc(), "propertyBizType": "STAR",
                "pageNo": 1, "pageSize": 10}))
        except Exception as exc:                            # noqa: BLE001
            self.result["兑换"] = f"❌ {str(exc)[:40]}"
            return
        if not r["ok"]:
            self.result["兑换"] = f"❌ {str(r.get('msg'))[:40]}"
            return
        items = (r["data"] or {}).get("list") or []
        ready, near = [], []
        for it in items:
            ex = it.get("exchangeInfo") or {}
            status = str(ex.get("exchangeStatus") or "")
            cost = ex.get("consumeAmount") or 0
            gap = ex.get("gapAmount") or 0
            name = ((it.get("materialInfo") or {}).get("title")
                    or (it.get("bizExtInfo") or {}).get("exchangeIntroduction", "")[:14]
                    or f"商品{str(it.get('exchangeId'))[-4:]}")
            if status in ("PROPERTY_NOT_ENOUGH",) or gap:
                near.append(f"{name}（差 {gap} 星）")
            elif status in ("", "INIT", "EXCHANGE_ABLE", "CAN_EXCHANGE", "ONLINE"):
                ready.append((name, cost, it))
            else:
                near.append(f"{name}[{status}]")
        self._log(f"🛒 兑换商城 {len(items)} 件：可兑 {len(ready)}｜接近 {len(near)}")
        for x in near[:3]:
            self._log(f"   · {x}")
        if not ready:
            self.result["兑换"] = f"➖ 暂无可兑（{near[0] if near else '无商品'}）"
            return
        if cfg("ELM_EXCHANGE") != "1":
            self.result["兑换"] = "➖ 可兑 " + "、".join(n for n, _, _ in ready[:2]) + "（未开启自动兑）"
            self._log("   （想自动兑请设 ELM_EXCHANGE=1 —— 会消耗幸运星，确认后再开）")
            return
        done = 0
        for name, cost, it in ready[: max(1, int(cfg("ELM_EXCHANGE_MAX", "1") or 1))]:
            try:
                rr = self.parse_ret(self.mtop(API["mall_exchange"], "1.0", {
                    **self._kj(), **self._loc(),
                    "actId": it.get("exchangeActId"),
                    "exchangeCollectionId": it.get("exchangeCollectionId"),
                    "exchangeId": it.get("exchangeId"),
                    "actCode": it.get("actCode"),
                    "propertyBizType": "STAR",
                }, {"asac": ASAC["MALL_EXCHANGE"]}))
            except Exception as exc:                        # noqa: BLE001
                self._log(f"   ⚠ 兑换失败：{str(exc)[:50]}")
                continue
            if rr["ok"]:
                done += 1
                self._log(f"   ✅ 已兑换：{name}（-{cost} 星）")
            else:
                self._log(f"   ⚠ 兑换[{name}]：{str(rr.get('msg'))[:60]}")
            nap_human(2.0)
        self.result["兑换"] = (f"✅ 成功兑 {done} 件" if done else "➖ 兑换未成功")

    def orderfree_draw(self, order_free: dict) -> None:
        """下单免单抽奖（需 cityId，通常要真下单才有机会；失败静默）。"""
        if cfg("ELM_SKIP_ORDERFREE") == "1":
            return
        data = (order_free or {}).get("data") or {}
        city_id = ((data.get("extInfo") or {}).get("cityId")
                   or cfg("ELM_CITY_ID", ""))
        payload = {**self._kj(), "bizScene": "order_free_draw",
                   "longitude": str(self.lng), "latitude": str(self.lat)}
        if city_id:
            payload["cityId"] = city_id
        try:
            r = self.parse_ret(self.mtop(API["orderfree_draw"], "1.0", payload,
                                         {"asac": ASAC["ORDER_FREE_DRAW"]}))
        except Exception:                                   # noqa: BLE001
            return
        if r["ok"]:
            self.result["免单抽"] = "✅ " + (self.lottery_prize(r["data"]) or "已抽")
            self._log(f"🎟 下单免单抽奖：{self.result['免单抽']}")
        elif DEBUG:
            self._log(f"🎟 下单免单抽奖未成：{str(r.get('msg'))[:60]}")

    def quiz(self) -> None:
        """
        趣味话题答题：actId 不在首页返回里（在答题页 URL 上），
        需用 ELM_QUIZ_ACTID 显式传入才执行。
        """
        act = cfg("ELM_QUIZ_ACTID")
        if not act:
            return
        src = cfg("ELM_QUIZ_SOURCE", "INTERACT_CENTER")
        try:
            r = self.parse_ret(self.mtop(API["quiz_query"], "1.0", {
                "actId": act, "bizScene": src, "source": src, **self._loc()}))
            if not r["ok"]:
                self._log(f"❓ 答题取题失败：{str(r.get('msg'))[:50]}")
                return
            d = r["data"] or {}
            q = d.get("questionDTO") or (d.get("questionList") or [{}])[0]
            copy_id = d.get("copyId") or ""
            answered, correct = d.get("answeredCount", 0), d.get("correctCount", 0)
            self._log(f"❓ 答题 已答{answered}/对{correct}")
            qid = q.get("questionId")
            opts = q.get("optionList") or q.get("options") or []
            if not qid or not opts:
                self.result["答题"] = "➖ 今日无题"
                return
            oid = (opts[0] or {}).get("optionId") or (opts[0] or {}).get("id")
            rs = self.parse_ret(self.mtop(API["quiz_submit"], "1.0", {
                "actId": act, "bizScene": src, "source": src, "copyId": copy_id,
                "questionId": qid, "optionId": oid, **self._loc()}))
            if not rs["ok"]:
                self.result["答题"] = f"➖ {str(rs.get('msg'))[:30]}"
                return
            ra = self.parse_ret(self.mtop(API["quiz_award"], "1.0", {
                "actId": act, "bizScene": src, "source": src, "copyId": copy_id,
                **self._loc()}, {"asac": ASAC["QUIZ_AWARD"]}))
            self.result["答题"] = ("🎁 " + self.lottery_prize(ra["data"]) if ra["ok"]
                              else f"➖ {str(ra.get('msg'))[:30]}")
            self._log(f"❓ 答题结果：{self.result['答题']}")
        except Exception as exc:                            # noqa: BLE001
            self._log(f"❓ 答题异常：{str(exc)[:50]}")

    def draw_lottery(self, lotteries: list) -> None:
        """
        夺宝/抽奖（mtop.alsc.interact.playapp.reward.lottery.draw）。
        入参与风控头 asac 都逆向自 engage-hub 1.4.2 前端包；
        每个组件默认抽 ELM_DRAW_TIMES 次（默认 1），未中奖/无机会即停。
        """
        if cfg("ELM_SKIP_DRAW") == "1":
            self.result["夺宝"] = "➖ 已跳过"
            return
        if not lotteries:
            self.result["夺宝"] = "➖ 本次无夺宝入口"
            return
        times = max(1, int(cfg("ELM_DRAW_TIMES", "1") or 1))
        wins, notes = 0, []
        for c in lotteries:
            act_id = (c or {}).get("actId")
            comp_id = (c or {}).get("componentId")
            if not act_id or not comp_id:
                continue
            for k in range(times):
                if self.risk_flagged:
                    break
                data = {
                    "actId": act_id,
                    "componentId": comp_id,
                    "bizScene": "INTERACT_CENTER_LOT",
                    "bizCode": "INTERACT_CENTER_LOT",
                    "longitude": str(self.lng),
                    "latitude": str(self.lat),
                    "extParams": json.dumps({"desc": "幸运福利"}, ensure_ascii=False),
                }
                try:
                    r = self.parse_ret(self.mtop(API["lottery_draw"], "1.0", data,
                                                 {"asac": ASAC["LOTTERY_DRAW"]}))
                except Exception as exc:                    # noqa: BLE001
                    notes.append(f"异常{str(exc)[:30]}")
                    break
                if r["ok"]:
                    prize = self.lottery_prize(r["data"])
                    wins += 1
                    notes.append(prize)
                    self._log(f"🎰 夺宝中奖：{prize}")
                    nap_human(1.4)
                    continue
                msg = str(r.get("msg", ""))
                if re.search(r"NO_ENOUGH_REMAIN|CHANCE|已抽完|次数|日剩", msg, re.I):
                    self._log(f"🎰 夺宝 次数已用完（{msg.split('::')[-1][:20]}）")
                    notes.append("今日次数已用完")
                elif re.search(r"未中奖|NO_DECISION_STRATEGY|NOT_WINNING", msg, re.I):
                    self._log("🎰 夺宝 未中奖")
                    notes.append("未中奖")
                else:
                    self._log(f"🎰 夺宝 {msg[:40]}")
                    notes.append(msg[:40])
                break
        if wins:
            self.result["夺宝"] = f"✅ 中 {wins} 次：{'、'.join(notes[:4])}"
        elif notes:
            self.result["夺宝"] = f"➖ {notes[0]}"
        else:
            self.result["夺宝"] = "➖ 无机会"

    @staticmethod
    def lottery_prize(data) -> str:
        """从抽奖返回里提炼奖励描述（幸运星/券/红包）。"""
        items = data if isinstance(data, list) else [data]
        out = []
        for it in items:
            if not isinstance(it, dict):
                continue
            dis = it.get("discountInfo") or {}
            info = it.get("materialInfo") or it.get("rightMaterialInfoDTO") or {}
            amount = dis.get("reductionYuan") or dis.get("reduction") or dis.get("amount")
            btype = str(dis.get("benefitType") or it.get("prizeType") or "")
            name = (info.get("title") if isinstance(info, dict) else "") or \
                {"VIRTUAL_INTEGRAL": "幸运星", "STAR": "幸运星", "COUPON": "优惠券",
                 "RED_PACKET": "红包"}.get(btype, btype or "奖励")
            if dis.get("benefitType") == "VIRTUAL_INTEGRAL":
                out.append(f"+{amount or ''} 幸运星".replace(" 幸运星", " 幸运星")
                           + (f"（{dis.get('reductionYuan')}元）" if dis.get("reductionYuan") else ""))
            elif name and amount and str(amount) not in str(name):
                out.append(f"{name} +{amount}")
            else:
                out.append(str(name))
        return "、".join(x for x in out if x) or "奖励"

    def query_tasks(self, mission_collection_id: str) -> list[dict]:
        loc = json.dumps({"lng": self.lng, "lat": self.lat}, separators=(",", ":"))
        data = {
            "bizScene": BIZ_SCENE,
            "accountPlan": ACCOUNT_PLAN,
            "longitude": self.lng,
            "latitude": self.lat,
            "locationInfos": json.dumps([loc], separators=(",", ":")),
            "missionCollectionId": mission_collection_id,
            "launchChannels": "[]",
        }
        r = self.parse_ret(self.mtop(API["querytask"], "1.0", data))
        if not r["ok"]:
            self._log(f"❌ 查询任务失败：{r['msg']}")
            return []
        lst = (r["data"] or {}).get("mlist")
        if not isinstance(lst, list):
            self._log(f"⚠ 未找到 mlist，字段：{list((r['data'] or {}).keys())}")
            return []
        if DEBUG:
            for t in lst:
                self._log(f"[调试] task={json.dumps(t, ensure_ascii=False)[:800]}")
        return lst

    # ---- 埋点 ----
    @staticmethod
    def _is_pageview(task: dict) -> bool:
        ac = task.get("actionConfig") or {}
        return ac.get("actionType") == "PAGEVIEW" and bool((ac.get("actionValue") or {}).get("pageSpm"))

    @staticmethod
    def _is_trigger(task: dict) -> bool:
        ac = task.get("actionConfig") or {}
        sc = (ac.get("actionValue") or {}).get("scenceCode")
        return ac.get("actionType") == "THIRD" and sc in ("commercial_click", "inter_change")

    def report_pageview(self, task: dict) -> dict:
        ac = task.get("actionConfig") or {}
        av = ac.get("actionValue") or {}
        loc = json.dumps({"lng": self.lng, "lat": self.lat}, separators=(",", ":"))
        data = {
            "bizScene": BIZ_SCENE,
            "accountPlan": ACCOUNT_PLAN,
            "longitude": self.lng,
            "latitude": self.lat,
            "locationInfos": json.dumps([loc], separators=(",", ":")),
            "collectionId": task.get("missionCollectionId") or task.get("missionCollectId"),
            "missionId": task.get("missionId") or task.get("missionDefId"),
            "pageFrom": av.get("pageSpm"),
            "actionCode": ac.get("actionType"),
            # 停留秒数随机（服务端会校验停留时长，固定值是最典型的机器特征）
            "viewTime": (max(3, int(av["pageStageTime"])) + random.randint(-2, 5)
                         if str(av.get("pageStageTime", "")).isdigit() else random.randint(8, 16)),
        }
        if task.get("instanceId"):
            data["instanceId"] = task["instanceId"]
        # pageview 实际版本为 1.1
        return self.parse_ret(self.mtop(API["pageview"], "1.1", data,
                                        {"asac": ASAC["PAGEVIEW"]}))

    def report_trigger(self, task: dict) -> dict:
        now = int(time.time() * 1000)
        data = {
            "latitude": self.lat,
            "longitude": self.lng,
            "riskScene": "duobao_external",     # 关键：THIRD 任务统一用这个值
            "bizScene": str(task.get("missionDefId")),
            "eventType": "THIRD",
            "eventSubType": "EVENT_FINISH",
            "eventId": now,
            "eventIdemPotent": now,
            "eventTime": now,
            "triggerType": "SYNC",
            "collectionId": str(task.get("missionCollectionId")),
            "missionId": str(task.get("missionDefId")),
            "missionXId": task.get("missionXId") or "",
        }
        # 注：原 JS 版这里把 asac 传在了第 5 个（不存在的）参数位，等于没发；
        #     此处保持一致，避免多带 header 反而被风控拦。
        return self.parse_ret(self.mtop(API["trigger"], "1.1", data))

    # ---- 领奖 ----
    @staticmethod
    def reward_stage_index(task: dict) -> int:
        for i, st in enumerate(task.get("missionStageDTOS") or []):
            st = st or {}
            sa = st.get("sourceAction") or {}
            if (st.get("status") == "FINISH" and st.get("rewardStatus") != "SUCCESS"
                    and sa.get("actionSubtype") != "NO_REWARD"
                    and sa.get("actionSubSubType") not in ("REWARD_SEND_AUTO", "NOTIFY_REACH_STAGE")):
                return i
        return -1

    def receive_prize(self, task: dict) -> dict:
        idx = self.reward_stage_index(task)
        if idx < 0:
            return {"ok": False, "skip": True, "msg": "无可领奖阶段（已领完或未完成）"}
        loc = json.dumps({"lng": self.lng, "lat": self.lat}, separators=(",", ":"))
        data = {
            "bizScene": BIZ_SCENE,
            "accountPlan": ACCOUNT_PLAN,
            "longitude": self.lng,
            "latitude": self.lat,
            "locationInfos": json.dumps([loc], separators=(",", ":")),
            "missionCollectionId": task.get("missionCollectionId") or task.get("missionCollectId"),
            "missionId": task.get("missionId") or task.get("missionDefId"),
            "asac": ASAC["PRIZE"],
        }
        if task.get("instanceId"):
            data["instanceId"] = task["instanceId"]
        st = (task.get("missionStageDTOS") or [])[idx] or {}
        if st.get("stageCount") is not None:
            data["count"] = st["stageCount"]
        if st.get("stageSum") is not None:
            data["sum"] = st["stageSum"]
        return self.parse_ret(self.mtop(API["receiveprize"], "1.0", data))

    @staticmethod
    def task_title(task: dict) -> str:
        ev = ((task.get("ext") or {}).get("extValue")) or {}
        pinned = ev.get("pinnedTaskTitle") or {}
        if pinned.get("value"):
            return str(pinned["value"])
        return str(task.get("missionName") or task.get("showTitle") or task.get("taskName")
                   or task.get("missionDefId") or "未知任务")

    @staticmethod
    def prize_name(item: dict) -> str:
        """奖励展示名：兼容 materialInfo / rightMaterialInfoDTO 两套字段，兜底用币种名。"""
        item = item or {}
        for holder in ("materialInfo", "rightMaterialInfoDTO", "prizeMaterialInfo"):
            title = ((item.get(holder) or {}).get("title")) or ""
            if title:
                break
        else:
            title = item.get("name") or ""
        if not title:
            ptype = item.get("prizeType") or ""
            title = {"STAR": "幸运星", "INTEGRAL_PROPERTY": "积分", "COUPON": "优惠券",
                     "RED_PACKET": "红包"}.get(ptype, ptype or "奖励")
        value = item.get("prizeValue") or item.get("equityValue") or item.get("value") or ""
        if value in ("", None):
            return title
        return title if re.search(r"\d", str(title)) else f"{title} +{value}"

    @classmethod
    def prize_summary(cls, data: dict) -> str:
        return "、".join(cls.prize_name(x) for x in ((data or {}).get("rlist") or [])[:4])

    # ---------- 编排 ----------
    def run(self) -> dict:
        self._log(f"开始｜设备 {self.dev.get('model')} / Android {self.dev.get('androidVersion')}"
                  f" / {self.dev.get('channel')}")
        if not self.token and not self.prime_token():
            self.result["Cookie"] = "❌ 缺少 _m_h5_tk 且申领失败"
            self._log(self.result["Cookie"])
            return self.result

        mission_collection_id, copy_id, strategy, award, signed = "", "", "", {}, False
        hp: dict = {}
        try:
            hp = self.homepage() or {}
            mission_collection_id = hp.get("missionCollectionId", "")
            copy_id = hp.get("copyId", "")
            strategy = hp.get("signInRewardStrategy", "")
            award = hp.get("award") or {}
            signed = bool(hp.get("signedToday"))
        except Exception as exc:                                # noqa: BLE001
            self._log(f"❌ 首页聚合异常：{exc}")

        # 开跑前先播报本号现有幸运星（跑完会再报一次，方便看这轮薅到多少）
        self.star_start = hp.get("star")
        if self.star_start is None:
            self.star_start = self.refresh_star()
        if self.star_start is not None:
            self._log(f"💰 现有幸运星：{self.star_start}")
            self.result["余额"] = f"{self.star_start} 星"

        self.signin(copy_id, strategy, award, signed)

        # 夺宝/抽奖（首页聚合给出的 INTERACT_CENTER_LOTTERY 组件）
        try:
            self.draw_lottery(hp.get("lotteries") or [])
        except Exception as exc:                                # noqa: BLE001
            self.result["夺宝"] = f"❌ {exc}"
            self._log(f"⚠ 夺宝异常：{exc}")

        # 下单免单抽奖 / 答题（有入口才做）
        try:
            self.orderfree_draw(hp.get("orderFree") or {})
        except Exception as exc:                                # noqa: BLE001
            self._log(f"⚠ 免单抽异常：{str(exc)[:40]}")
        try:
            self.quiz()
        except Exception as exc:                                # noqa: BLE001
            self._log(f"⚠ 答题异常：{str(exc)[:40]}")

        if self.risk_flagged:                    # 账号已被标记，写请求一律不再发
            self.result["任务"] = "⛔ 风控中止（未再发写请求）"
            return self.finish(brief=True)      # 被标记就别再刷接口，只播报余额

        if not mission_collection_id:
            self.result["任务"] = "➖ 无 missionCollectionId，跳过"
            self._log("⚠ 未拿到 missionCollectionId，任务链路终止")
            return self.finish()

        if cfg("ELM_SKIP_TASKS") == "1":
            self.result["任务"] = "➖ 已跳过"
            return self.finish()

        try:
            tasks = self.query_tasks(mission_collection_id)
        except Exception as exc:                                # noqa: BLE001
            self.result["任务"] = f"❌ 查询异常 {exc}"
            return self.finish()

        # 第一轮：浏览埋点 + THIRD 触发
        kinds: dict[str, int] = {}
        for t in tasks:
            at = str(((t.get("actionConfig") or {}).get("actionType")) or "?")
            kinds[at] = kinds.get(at, 0) + 1
        self._log(f"第一轮：{len(tasks)} 个任务（" +
                  "、".join(f"{k}×{v}" for k, v in sorted(kinds.items())) + "），开始埋点")
        blocked = 0
        if HUMAN:                                   # 打乱顺序，别每次都是固定套路
            random.shuffle(tasks)
        for task in tasks:
            if self.risk_flagged:                # 埋点途中被标记 -> 立刻收手
                self._log("🚫 已被风控标记，中止剩余埋点")
                break
            title = self.task_title(task)
            try:
                if self._is_pageview(task):
                    r = self.report_pageview(task)
                    if r["ok"]:
                        self._log(f"👁 浏览[{title}] 上报成功")
                    else:
                        msg = str(r["msg"])
                        self._log(f"👁 浏览[{title}] ⚠ {msg[:50]}")
                        if "405" in msg or "受限" in msg:
                            blocked += 1
                            if blocked >= 2:        # 已被限流就别继续撞，越撞越黑
                                self._log("⛔ 连续行为受限，停止本轮埋点（改天/换 IP 再试）")
                                break
                    nap_human(1.6)
                elif self._is_trigger(task):
                    av = (task.get("actionConfig") or {}).get("actionValue") or {}
                    total = int(av.get("finalStageCount") or 1)
                    done = int((task.get("stage") or {}).get("count") or 0)
                    need = min(max(0, total - done), self.task_times)
                    self._log(f"👆 点击[{title}] {av.get('scenceCode')} 需{total}次/已{done}次/补{need}次")
                    for i in range(need):
                        r = self.report_trigger(task)
                        if not r["ok"]:
                            self._log(f"   ⚠ 触发 {i + 1}/{need}：{str(r['msg'])[:50]}")
                            break
                        nap_human(2.2)
            except Exception as exc:                            # noqa: BLE001
                self._log(f"⚠ 埋点异常[{title}]：{exc}")

        # 第二轮：重新查询 + 领奖
        try:
            tasks2 = self.query_tasks(mission_collection_id)
        except Exception as exc:                                # noqa: BLE001
            self._log(f"❌ 重新查询异常：{exc}")
            tasks2 = tasks
        got, ok_cnt = [], 0
        for task in tasks2:
            if self.risk_flagged:                # 领奖途中被标记 -> 立刻收手
                self._log("🚫 已被风控标记，中止剩余领奖")
                break
            title = self.task_title(task)
            try:
                r = self.receive_prize(task)
                if r.get("ok"):
                    ok_cnt += 1
                    s = self.prize_summary(r.get("data") or {})
                    got.append(s or title)
                    self._log(f"🎁 领奖[{title}] 成功{s and '：' + s}")
                elif r.get("skip"):
                    pass
                elif DEBUG:
                    self._log(f"⚠ 领奖[{title}]：{str(r.get('msg'))[:60]}")
                nap_human(1.8)
            except Exception as exc:                            # noqa: BLE001
                self._log(f"⚠ 领奖异常[{title}]：{exc}")
        self.result["任务"] = (f"✅ 领到 {ok_cnt} 份：{'、'.join(got[:5])}" if got
                           else f"➖ 无可领（{len(tasks2)} 个任务）")
        return self.finish()

    def finish(self, brief: bool = False) -> dict:
        """
        统一收尾（所有出口都走这里，保证每个账号的日志里都有余额一行）：
          资产/余额刷新 → 兑换商城 → 打印「现有 X → Y（本轮 +N）」→ 结果汇总
        brief=True（风控中止）时不再发任何请求，只播报已知余额。
        """
        if not brief:
            try:
                self.wallet()                   # 内部会刷新余额（此时今日收益已入账）
            except Exception as exc:                            # noqa: BLE001
                self._log(f"⚠ 资产查询异常：{str(exc)[:40]}")
            try:
                self.mall()
            except Exception as exc:                            # noqa: BLE001
                self._log(f"⚠ 兑换商城异常：{str(exc)[:40]}")
        s, e = self.star_start, self.star_end
        if s is not None and e is not None and e != s:
            self._log(f"💰 幸运星 {s} → {e}（本轮 {'+' if e >= s else ''}{e - s}）")
        elif e is not None:
            self._log(f"💰 幸运星余额：{e}")
        elif s is not None:
            self._log(f"💰 幸运星余额：{s}")
        self.result["余额"] = (f"{s} → {e} 星" if (s is not None and e is not None and e != s)
                          else f"{e if e is not None else s} 星"
                          if (e is not None or s is not None) else "")
        if not self.result.get("余额"):
            self.result.pop("余额", None)
        line = " ".join(f"{k}:{v}" for k, v in self.result.items())
        if line:
            self._log(line)
        return self.result


# =========================================================================== #
#  通知
# =========================================================================== #

def send_notify(content: str) -> None:
    log("\n" + "=" * 46)
    log(content)
    log("=" * 46)
    try:
        import notify                                       # type: ignore # noqa: PLC0415
        notify.send("饿了么幸运星", content)
        log("[通知] 已通过青龙 sendNotify 推送")
        return
    except Exception:                                       # noqa: BLE001
        pass
    title = "饿了么幸运星"
    ok = False
    try:
        if cfg("PUSH_PLUS_TOKEN"):
            requests.post("http://www.pushplus.plus/send", timeout=10,
                          json={"token": cfg("PUSH_PLUS_TOKEN"), "title": title, "content": content})
            ok = True
        if cfg("PUSH_KEY"):
            requests.post(f"https://sctapi.ftqq.com/{cfg('PUSH_KEY')}.send", timeout=10,
                          data={"title": title, "desp": content})
            ok = True
        if cfg("WECOM_WEBHOOK") or cfg("QYWX_KEY"):
            url = cfg("WECOM_WEBHOOK") or cfg("QYWX_KEY")
            if not url.startswith("http"):
                url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={url}"
            requests.post(url, timeout=10, json={"msgtype": "text", "text": {"content": content}})
            ok = True
        if cfg("DINGTALK_WEBHOOK"):
            url, secret = cfg("DINGTALK_WEBHOOK"), cfg("DINGTALK_SECRET")
            if secret:
                ts = str(round(time.time() * 1000))
                sign = quote(base64.b64encode(hmac.new(secret.encode(), f"{ts}\n{secret}".encode(),
                                                       hashlib.sha256).digest()))
                url = f"{url}&timestamp={ts}&sign={sign}"
            requests.post(url, timeout=10, json={"msgtype": "text", "text": {"content": content}})
            ok = True
        if cfg("TG_BOT_TOKEN") and cfg("TG_CHAT_ID"):
            requests.post(f"https://api.telegram.org/bot{cfg('TG_BOT_TOKEN')}/sendMessage",
                          timeout=10, data={"chat_id": cfg("TG_CHAT_ID"), "text": content[:4000]})
            ok = True
        if cfg("BARK_PUSH") or cfg("BARK"):
            url = cfg("BARK_PUSH") or cfg("BARK")
            if not url.startswith("http"):
                url = f"https://api.day.app/{url}"
            requests.post(f"{url.rstrip('/')}/{quote(title)}/{quote(content[:400])}", timeout=10)
            ok = True
    except Exception as exc:                                # noqa: BLE001
        log(f"[通知] 推送异常：{exc}")
    if not ok:
        log("[通知] 未配置推送渠道，仅输出日志")


# =========================================================================== #
#  入口
# =========================================================================== #

def main() -> int:
    argv = sys.argv[1:]
    log(f"===== 饿了么「幸运星」自动任务 v{SCRIPT_VERSION}"
        f"{' [DRYRUN]' if DRYRUN else ''} =====")

    accounts = load_accounts()
    if "--dump-account" in argv:
        for i, (rmk, ck) in enumerate(accounts, 1):
            tk = (re.search(r"_?m_h5_tk=([^;]+)", ck) or [None, ""])[1]
            log(f"[{i}] 备注={rmk} token={tk[:10]}… cookie长度={len(ck)} 组数="
                f"{len(re.findall(r'[A-Za-z0-9_]+=', ck))}")
        log(f"共 {len(accounts)} 个账号")
        return 0

    if not accounts:
        msg = ("❌ 未读到饿了么 Cookie。请设置环境变量 ELM_COOKIE（多账号换行分隔，"
               "每行可写「备注#cookie」）")
        log(msg)
        send_notify(msg)
        return 1

    log(f"账号 {len(accounts)} 个 | 经纬度 {cfg('ELM_LAT', '31.2304')},{cfg('ELM_LNG', '121.4737')} "
        f"| appKey {cfg('ELM_APPKEY', '12574478')} | 代理 {'开' if accounts and ElmAccount(*accounts[0]).proxies else '关'}")
    if accounts:
        _px = ElmAccount(*accounts[0]).proxies
        if _px:
            _h = _px["http"]
            _host = re.sub(r"^https?://", "", _h).split("@")[-1].split("/")[0]
            _masked = re.sub(r"(//[^:]+):[^@]+@", r"\1:***@", _h)
            log(f"🌐 代理出口（账号1）：{_host}（{_masked}）")
    no_token = [rmk for rmk, ck in accounts if not re.search(r"_?m_h5_tk=", ck)]
    if no_token:
        log(f"ℹ {len(no_token)} 个账号的 Cookie 不含 _m_h5_tk（App 端 Cookie 形态），"
            f"运行时将自动向 mtop 申领；若申领失败请改用 tb.ele.me H5 端抓到的完整 Cookie")
    no_token = [rmk for rmk, ck in accounts if not re.search(r"_?m_h5_tk=", ck)]
    if no_token:
        log(f"ℹ {len(no_token)} 个账号的 Cookie 不含 _m_h5_tk（App 端 Cookie 形态），"
            f"运行时将自动向 mtop 申领；若申领失败请改用 tb.ele.me H5 端抓到的完整 Cookie")

    if "--risk-check" in argv:
        acc = ElmAccount(*accounts[0])
        log(f"[体检] 账号 {acc.remark}｜设备 {acc.dev.get('model')} / Android "
            f"{acc.dev.get('androidVersion')} / {acc.dev.get('channel')}")
        _ua = acc.hdr["User-Agent"]
        _mp = bool(re.search(r"MiniProgramEnv|miniProgram/|XWEB/|MMWEBSDK/", _ua))
        log(f"[体检] 环境头：小程序 UA = {'✓' if _mp else '✗（写接口必被 405 拦）'}｜"
            f"x-utdid = {acc.hdr.get('x-utdid', '(未发)')[:14]}…｜"
            f"x-ele-ua = {'✓' if acc.hdr.get('x-ele-ua') else '✗'}")
        if not acc.prime_token():
            log("[体检] ❌ 拿不到 _m_h5_tk，Cookie 可能已失效")
            return 1
        verdict = []
        hp = None
        try:
            hp = acc.homepage()
            verdict.append(("首页聚合", "✅ 通过" if hp else "❌ 失败"))
        except Exception as exc:                            # noqa: BLE001
            verdict.append(("首页聚合", f"❌ {exc}"))
        mid = (hp or {}).get("missionCollectionId", "")
        tasks = acc.query_tasks(mid) if mid else []
        verdict.append(("任务列表", f"✅ {len(tasks)} 个" if tasks else "❌ 空"))
        pv = next((t for t in tasks if acc._is_pageview(t)), None)
        if pv:
            r = acc.report_pageview(pv)
            verdict.append(("浏览埋点(写)", "✅ 放行" if r.get("ok")
                            else f"⛔ 被拦：{str(r.get('msg'))[:40]}"))
        tk = next((t for t in tasks if acc._is_trigger(t)), None)
        if tk:
            r = acc.report_trigger(tk)
            verdict.append(("点击埋点(写)", "✅ 放行" if r.get("ok")
                            else f"⛔ 被拦：{str(r.get('msg'))[:40]}"))
        log("")
        for name, res in verdict:
            log(f"[体检] {name:14s} {res}")
        blocked = any(("被拦" in v) or ("❌" in v) for _, v in verdict)
        log("")
        log("[体检] 结论：" + ("⛔ 当前指纹/环境被风控拦截 → 试 ELM_RESET_DEVICE=1 换设备，"
                            "或检查 Cookie 是否过期"
                            if blocked else
                            "✅ 全链路放行（写接口未被拦截），可以正常跑"))
        return 0 if not blocked else 1

    if "--dryrun" in argv:
        ElmAccount(*accounts[0]).run()
        log("\n[dryrun] 以上为请求构造结果，未发出任何真实请求")
        return 0

    if "--selftest" in argv:
        acc = ElmAccount(*accounts[0])
        log(f"[自检] {acc.remark} token={acc.token[:10]}…")
        try:
            acc.mtop(API["querytask"], "1.0", {"bizScene": BIZ_SCENE})
        except Exception as exc:                            # noqa: BLE001
            log(f"[自检] ❌ {exc}")
            return 1
        try:
            r = acc.parse_ret(acc.mtop(API["homepage"], "1.0", {
                "bizScene": BIZ_SCENE, "version": PAGE_VERSION,
                "latitude": acc.lat, "longitude": acc.lng,
                "cpnCodes": json.dumps(CPN_CODES, separators=(",", ":")),
            }))
            log(f"[自检] homepage ok={r['ok']} msg={str(r['msg'])[:80]}")
            log(f"[自检] 业务字段：{list((r['data'] or {}).keys())[:12]}")
            if not r["ok"]:
                log("[自检] 失败原因通常是：Cookie 过期 / _m_h5_tk 缺失 / 需要在同一网络环境重抓")
        except Exception as exc:                            # noqa: BLE001
            log(f"[自检] ❌ {exc}")
        return 0

    # ---- 每日一次锁：同一天重复执行（cron 配错 / 手动重跑）本身就是异常信号 ----
    today = datetime.now().strftime("%Y-%m-%d")
    state: dict = {}
    try:
        if STATE_FILE.is_file():
            state = json.loads(STATE_FILE.read_text(encoding="utf-8")) or {}
    except Exception:                                       # noqa: BLE001
        state = {}
    if (ONCE_PER_DAY and not DRYRUN and state.get("last_success_day") == today
            and os.environ.get("ELM_FORCE") != "1"):
        log(f"⏭ 今日（{today}）已成功执行过，跳过以免重复请求；强制重跑请设 ELM_FORCE=1")
        return 0

    # 随机错峰启动（固定整点是最易被识别的特征）；ELM_OFFSET_MAX=0 关闭
    off_max = int(cfg("ELM_OFFSET_MAX", "900") or 0)
    if HUMAN and not DRYRUN and off_max > 0:
        wait = random.randint(0, off_max)
        log(f"⏳ 随机错峰启动：本次随机等待 {wait}s（约 {wait // 60} 分 {wait % 60} 秒）")
        log(f"   这是防风控用的正常行为，不是卡住；嫌慢可把环境变量 ELM_OFFSET_MAX 设为 0")
        left = wait
        while left > 0:                     # 分段等待 + 进度播报，避免青龙里看着像挂死
            step = min(30, left)
            time.sleep(step)
            left -= step
            if left:
                log(f"   ⏳ 错峰等待中…还剩 {left}s")
        if wait:
            log("▶ 错峰结束，开始执行")

    rows, ok_cnt = [], 0
    for i, (rmk, ck) in enumerate(accounts, 1):
        log(f"\n══════════ 账号 {i}/{len(accounts)}：{rmk} ══════════")
        try:
            res = ElmAccount(rmk, ck).run()
            if str(res.get("签到", "")).startswith("✅") or str(res.get("任务", "")).startswith("✅"):
                ok_cnt += 1
        except Exception as exc:                            # noqa: BLE001
            res = {"签到": f"❌ 异常 {exc}"}
        rows.append((rmk, res))
        if i < len(accounts):
            nap(8.0, 25.0)                                  # 账号间隔拉大：短时间同段请求最易被关联

    keys = ["余额", "签到", "夺宝", "任务", "兑换", "资产", "答题", "Cookie"]
    lines = [f"饿了么幸运星完成 {ok_cnt}/{len(accounts)}",
             f"耗时 {int(time.time() - START_TS)}s　{datetime.now():%Y-%m-%d %H:%M:%S}", ""]
    for rmk, res in rows:
        lines.append(f"【{rmk}】")
        lines.extend(f"  {k}：{res[k]}" for k in keys if res.get(k))
    if ok_cnt:
        try:
            STATE_FILE.write_text(json.dumps(
                {**state, "last_success_day": today,
                 "last_success_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                 "accounts": [r for r, _ in rows]}, ensure_ascii=False, indent=2),
                encoding="utf-8")
        except Exception:                                   # noqa: BLE001
            pass
    send_notify("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
