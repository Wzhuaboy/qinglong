#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# name: 众安健康
# cron: 25 7 * * *
"""
name: 众安健康签到
cron: 25 7 * * *

众安健康微信小程序「签到赚金」每日签到 + 每周浏览任务 + 满 5 元自动提现，
基于 YYB-Go-Enhanced 自动取码登录，全程无需抓包。

青龙环境变量：
  YYB_SERVER            必填，YYB-Go-Enhanced 地址@微信账号标识，多账号每行一条
                        例：yyb-go:8000@1
  YYB_API_KEY           可选，对应 YYB_PROTOCOL_TOKEN，设置后带 Authorization 头
  ZAJK_DRY_RUN          可选，=1 只查询不执行任何写操作（建议首次这样试）
  ZAJK_ENABLE_SIGN      可选，默认 1；=0 关闭每日签到
  ZAJK_ENABLE_BROWSE    可选，默认 1；=0 关闭「每周浏览任务」自动上报
  ZAJK_ENABLE_WITHDRAW  可选，默认 1；=0 关闭自动提现
  ZAJK_WITHDRAW_MIN     可选，提现门槛（单位：分），默认 500（即 5 元）
  ZAJK_LOGIN_RETRY      可选，登录重试次数，默认 3（code 一次性，失败会换新 code 重试）
  ZAJK_REQUEST_TIMEOUT  可选，单次请求超时秒数，默认 30
  ZAJK_RANDOM_HEADERS   可选，默认 1；=0 关闭随机 User-Agent
  ZAJK_DEBUG            可选，=1 打印请求/响应明细，便于排查接口变动

依赖：requests
通知：优先使用青龙内置 notify.py；未配置时回落到 PushPlus / Server酱 / Bark。
      通知里固定输出每个账号的「总签到金 初始 → 最终」与「可提现金额」，便于对账。
      通知失败不影响结果。
功能：查询活动状态 -> 每日签到 -> 领取待领奖励球 -> 完成每周浏览任务 -> 再领球
      -> 满 5 元自动提现 -> 汇总通知。多账号串行。

作者：lcmovie https://github.com/lcmovie
"""
from __future__ import annotations

import importlib.util
import json
import os
import random
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

try:
    import requests
except ImportError:
    print("❌ 缺少依赖：pip install requests")
    sys.exit(1)

APP_NAME = "众安健康签到"
HERE = Path(__file__).resolve().parent

# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #
APP_NO = "wxbac45cc1588a5a75"                      # 众安健康小程序 AppID
API_BASE = "https://ihealth.zhongan.com/api/lemon"  # lemon 服务
CHANNEL = "c20195660470001"                        # 默认渠道（weapp_zunxiang）
ACTIVITY = "ONA20220411001"                        # 签到赚金活动编码
ENV_SOURCE = "miniprogram"

# --------------------------------------------------------------------------- #
# 配置
# --------------------------------------------------------------------------- #
DRY_RUN = os.getenv("ZAJK_DRY_RUN", "") == "1"
ENABLE_SIGN = os.getenv("ZAJK_ENABLE_SIGN", "1") != "0"
ENABLE_BROWSE = os.getenv("ZAJK_ENABLE_BROWSE", "1") != "0"
ENABLE_WITHDRAW = os.getenv("ZAJK_ENABLE_WITHDRAW", "1") != "0"
WITHDRAW_MIN = int(os.getenv("ZAJK_WITHDRAW_MIN", "500") or "500")
LOGIN_RETRY = int(os.getenv("ZAJK_LOGIN_RETRY", "3") or "3")
TIMEOUT = int(os.getenv("ZAJK_REQUEST_TIMEOUT", "30") or "30")
RANDOM_HEADERS = os.getenv("ZAJK_RANDOM_HEADERS", "1") != "0"
DEBUG = os.getenv("ZAJK_DEBUG", "") == "1"

_UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x67001435) "
    "NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF",
    "Mozilla/5.0 (Linux; Android 14; M2012K11AC Build/UKQ1.220917.002) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36 MicroMessenger/8.0.49.2560"
    "(0x28003137) XWEB/1260115 MMWEBSDK/20250501 MMWEBID/1234 MiniProgramEnv/Android",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.49(0x18003136) NetType/WIFI "
    "Language/zh_CN MiniProgramEnv/Mac",
]
_CURRENT_UA = random.choice(_UA_POOL) if RANDOM_HEADERS else _UA_POOL[0]


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def log(*args: Any) -> None:
    print(*args, flush=True)


def dbg(*args: Any) -> None:
    if DEBUG:
        log("   🔍 [debug]", *args)


def clean(v: Any, limit: int = 120) -> str:
    """文本字段清洗：去引号/空白/零宽字符，防脏值进日志。"""
    if v is None:
        return ""
    s = str(v).strip("\"'` \t\r\n\u200b")
    return s if len(s) <= limit else s[:limit] + "…"


def yuan(cents: Any) -> str:
    """分 -> 元 字符串。"""
    try:
        return "¥%.2f" % (int(cents) / 100.0)
    except (TypeError, ValueError):
        return "¥?"


def preview(obj: Any, limit: int = 240) -> str:
    try:
        return clean(json.dumps(obj, ensure_ascii=False), limit)
    except Exception:
        return clean(repr(obj), limit)


class ApiError(Exception):
    pass


# --------------------------------------------------------------------------- #
# HTTP 客户端
# --------------------------------------------------------------------------- #
class Client:
    def __init__(self) -> None:
        self.token: str = ""
        self.open_id: str = ""
        self.sess = requests.Session()
        self.sess.headers.update({
            "User-Agent": _CURRENT_UA,
            "Accept": "application/json",
        })

    # ---------------- 底层 ---------------- #
    def _headers(self) -> Dict[str, str]:
        h = dict(self.sess.headers)
        if self.token:
            h["Access-Token"] = self.token
        return h

    def _unwrap(self, resp: Dict[str, Any], path: str) -> Dict[str, Any]:
        code = str(resp.get("code", ""))
        if code != "0":
            raise ApiError(f"{path} 业务失败 code={code}: {clean(resp.get('message'))}")
        return resp.get("result") or {}

    def _post(self, path: str, body: Dict[str, Any], *, login: bool = True) -> Dict[str, Any]:
        url = API_BASE + path
        headers = self._headers()
        if login:
            headers["Content-Type"] = "application/json"
        r = self.sess.post(url, json=body, headers=headers, timeout=TIMEOUT)
        dbg("POST", path, "->", r.status_code, preview(r.text, 200))
        if r.status_code >= 400:
            raise ApiError(f"HTTP {r.status_code} @ {path}")
        try:
            return r.json()
        except Exception:
            raise ApiError(f"非 JSON 响应 @ {path}: {clean(r.text)}")

    def _get(self, path: str, params: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        url = API_BASE + path
        r = self.sess.get(url, params=params, headers=self._headers(), timeout=TIMEOUT)
        dbg("GET", path, "->", r.status_code, preview(r.text, 200))
        if r.status_code >= 400:
            raise ApiError(f"HTTP {r.status_code} @ {path}")
        try:
            return r.json()
        except Exception:
            raise ApiError(f"非 JSON 响应 @ {path}: {clean(r.text)}")

    # ---------------- 业务封装 ---------------- #
    def login(self, code: str) -> str:
        """GET 登录（code 走 query，POST 会 500），result 即 Access-Token。"""
        resp = self._get(f"/v1/wechatApplet/login/{CHANNEL}", params={"code": code})
        # 注意：token 长度 120+，绝不能走 clean() 截断（截断会破坏 token 且带省略号
        # 进请求头，触发 latin-1 encode 错误）
        token = str(resp.get("result") or "").strip("\"'` \t\r\n\u200b")
        if str(resp.get("code", "")) != "0" or not token:
            raise ApiError(f"Login 未返回 token: {preview(resp)}")
        self.token = token
        return token

    def home_page(self) -> Dict[str, Any]:
        resp = self._post("/v1/common/activity/homePage",
                          {"channelCode": CHANNEL, "activityCode": ACTIVITY})
        return self._unwrap(resp, "homePage")

    def sign_in(self) -> Dict[str, Any]:
        resp = self._post("/v1/common/activity/signIn",
                          {"channelCode": CHANNEL, "activityCode": ACTIVITY,
                           "envSource": ENV_SOURCE})
        return self._unwrap(resp, "signIn")

    def receive_ball(self, award_detail_id: Any) -> Dict[str, Any]:
        resp = self._post("/v1/common/activity/lottery",
                          {"channelCode": CHANNEL, "activityCode": ACTIVITY,
                           "id": award_detail_id, "envSource": ENV_SOURCE})
        return self._unwrap(resp, "lottery")

    def browse_award(self, activity_code: str, channel_code: str,
                     goods_code: str, task_id: str) -> Dict[str, Any]:
        resp = self._post("/v1/applet/mgm/activity/add/award",
                          {"activityCode": activity_code, "channelCode": channel_code,
                           "goodsCode": goods_code, "taskId": task_id})
        return self._unwrap(resp, "add/award")

    def check_real_name(self) -> bool:
        resp = self._get("/v1/sign/activity/check/realName")
        return bool((resp.get("result")))

    def withdraw(self, amount: int) -> Dict[str, Any]:
        resp = self._post("/v1/common/activity/withdraw",
                          {"channelCode": CHANNEL, "activityCode": ACTIVITY,
                           "amount": amount, "envSource": ENV_SOURCE})
        return self._unwrap(resp, "withdraw")

    def award_list(self) -> List[Dict[str, Any]]:
        resp = self._post("/v1/common/activity/awardList",
                          {"channelCode": CHANNEL, "activityCode": ACTIVITY})
        result = self._unwrap(resp, "awardList")
        return result.get("detailList") or []


# --------------------------------------------------------------------------- #
# 登录
# --------------------------------------------------------------------------- #
def yyb_get_code(host: str, ref: str) -> Tuple[str, str]:
    """YYB 取 wx.login code -> (code, openid)。"""
    url = host.rstrip("/") + "/wxapp/getCode"
    headers = {"User-Agent": _CURRENT_UA, "Content-Type": "application/json"}
    api_key = (os.getenv("YYB_API_KEY", "") or "").strip()
    if api_key:
        headers["Authorization"] = api_key
    r = requests.post(url, json={"app_id": APP_NO, "ref": str(ref)}, headers=headers, timeout=TIMEOUT)
    dbg("YYB getCode", r.status_code, preview(r.text, 300))
    if r.status_code != 200:
        raise ApiError(f"YYB 取码失败 HTTP {r.status_code}: {clean(r.text)}")
    data = r.json()
    payload = data.get("data") or {}
    if not (payload.get("result") or {}).get("code"):
        raise ApiError(f"YYB 未返回 code: {clean(r.text)}")
    return clean((payload.get("result") or {}).get("code")), clean(payload.get("openid"))


def login(host: str, ref: str) -> Client:
    """取码登录，code 一次性，失败换新 code 重试。"""
    last: Optional[Exception] = None
    for attempt in range(1, LOGIN_RETRY + 1):
        try:
            code, openid = yyb_get_code(host, ref)
            client = Client()
            client.open_id = openid
            token = client.login(code)
            dbg("token =", token[:24], "...")
            return client
        except Exception as exc:
            last = exc
            log(f"   ⚠️ 第 {attempt}/{LOGIN_RETRY} 次登录失败：{clean(exc, 200)}")
            if attempt < LOGIN_RETRY:
                time.sleep(1.5 * attempt)
    raise ApiError(f"登录失败：{clean(last, 200)}")


# --------------------------------------------------------------------------- #
# 业务
# --------------------------------------------------------------------------- #
def parse_browse_task(link: str) -> Optional[Dict[str, str]]:
    """从商品链接解析浏览任务四参数；缺一不可。"""
    try:
        q = parse_qs(urlparse(link).query)
        need = ("activityCode", "healthChannelCode", "goodsId", "taskId")
        if all(k in q and q[k][0] for k in need):
            return {
                "activityCode": q["activityCode"][0],
                "channelCode": q["healthChannelCode"][0],
                "goodsCode": q["goodsId"][0],
                "taskId": q["taskId"][0],
            }
    except Exception:
        pass
    return None


def receive_all_balls(client: Client, max_rounds: int = 3) -> Tuple[int, str]:
    """循环领取待领奖励球（无 url 的），返回 (领取个数, 描述)。"""
    got = 0
    notes: List[str] = []
    for _ in range(max_rounds):
        page = client.home_page()
        balls = page.get("valuableRewardList") or []
        if not balls:
            break
        progressed = False
        for ball in balls:
            if ball.get("url"):
                notes.append(f"跳转型奖励[{clean(ball.get('desc'))}]需手动")
                continue
            bdid = ball.get("awardDetailId")
            try:
                client.receive_ball(bdid)
                got += 1
                progressed = True
                notes.append(f"{clean(ball.get('desc'))}{clean(ball.get('amount'))}")
                log(f"   🎁 领取奖励球：{clean(ball.get('desc'))} {clean(ball.get('amount'))}")
            except Exception as exc:
                log(f"   ⚠️ 领球失败({bdid})：{clean(exc, 160)}")
            time.sleep(0.6)
        if not progressed:
            break
        time.sleep(1)
    return got, "、".join(notes) if notes else ""


def run_account(host: str, ref: str, label: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"label": label, "ref": ref}
    log(f"\n{'=' * 62}\n账号 {label}\n{'=' * 62}")

    try:
        client = login(host, ref)
    except Exception as exc:
        log(f"   ❌ {clean(exc, 220)}")
        result.update(error=clean(exc, 220))
        return result

    # ---------------- 初始状态 ---------------- #
    try:
        page = client.home_page()
    except Exception as exc:
        log(f"   ❌ 获取活动数据失败：{clean(exc, 200)}")
        result.update(error=f"获取活动数据失败：{clean(exc, 200)}")
        return result

    if not page:
        log("   ⏭️ 活动数据为空，跳过")
        result.update(skipped=True, summary="活动数据为空")
        return result

    # login=False => 该微信从未打开过众安健康小程序（未完成微信授权绑定，
    # userStatus=unbound）， signIn/lottery 会被服务端以 20003「未登录」拒绝
    if page.get("login") is False:
        log("   ⏭️ 该微信未授权众安健康（从未打开过小程序），跳过；"
            "需真人用该微信打开一次「众安健康」小程序完成授权后才会生效")
        result.update(skipped=True, summary="未授权（需真人打开一次小程序）")
        return result

    if page.get("signInData") is None:
        log("   ⏭️ 该账号未参与签到赚金活动（signInData 为空），跳过")
        result.update(skipped=True, summary="未参与活动")
        return result

    sum_award_0 = int(page.get("sumAward") or 0)
    allow_0 = int(page.get("sumAllowWithdraw") or 0)
    signed = bool(page.get("signInStatus"))
    today_amount = int(page.get("amount") or 0)
    result["sum_before"] = sum_award_0
    result["allow_before"] = allow_0
    log(f"   💰 总签到金 {yuan(sum_award_0)}　可提现 {yuan(allow_0)}　"
        f"今日{'已' if signed else '未'}签到（可得 {yuan(today_amount)}）")

    # ---------------- 每日签到 ---------------- #
    sign_msg = ""
    if DRY_RUN:
        sign_msg = "干跑模式，未执行签到" if not signed else "今天已经签到"
    elif not ENABLE_SIGN:
        sign_msg = "已关闭签到（ZAJK_ENABLE_SIGN=0）"
    elif signed:
        sign_msg = "今天已经签到"
    else:
        try:
            r = client.sign_in()
            got_today = int(r.get("today") or 0)
            sign_msg = f"签到成功 +{yuan(got_today)}"
            log(f"   ✍️ {sign_msg}")
        except Exception as exc:
            sign_msg = f"签到异常：{clean(exc, 200)}"
            log(f"   ⚠️ {sign_msg}")
    result["sign"] = sign_msg

    # ---------------- 领取待领奖励球 ---------------- #
    balls_got, balls_note = ("", "")
    if DRY_RUN:
        n = len(page.get("valuableRewardList") or [])
        balls_got, balls_note = 0, f"干跑：待领球 {n} 个"
    else:
        balls_got, balls_note = receive_all_balls(client)

    # ---------------- 每周浏览任务 ---------------- #
    browse_done: List[str] = []
    browse_fail: List[str] = []
    if DRY_RUN:
        todo = [it.get("goodsCode") for it in (page.get("productRecommendList") or [])
                if not it.get("status")]
        browse_done = [f"{g}(干跑)" for g in todo]
    elif ENABLE_BROWSE:
        for item in (client.home_page().get("productRecommendList") or []):
            if item.get("status"):
                continue
            task = parse_browse_task(clean(item.get("link"), 600))
            if not task:
                browse_fail.append(f"{item.get('goodsCode')}(链接缺参数)")
                continue
            try:
                client.browse_award(task["activityCode"], task["channelCode"],
                                    task["goodsCode"], task["taskId"])
                browse_done.append(str(task["goodsCode"]))
                log(f"   📱 浏览任务完成：商品 {task['goodsCode']}")
            except Exception as exc:
                browse_fail.append(f"{task['goodsCode']}({clean(exc, 80)})")
                log(f"   ⚠️ 浏览任务失败 {task['goodsCode']}：{clean(exc, 160)}")
            time.sleep(0.8)
        # 浏览可能产生新奖励球，再领一轮
        extra_got, extra_note = receive_all_balls(client, max_rounds=2)
        balls_got += extra_got
        if extra_note:
            balls_note = (balls_note + "、" + extra_note) if balls_note else extra_note
    result["browse_done"] = browse_done
    result["browse_fail"] = browse_fail

    # ---------------- 自动提现 ---------------- #
    withdraw_msg = ""
    try:
        page2 = client.home_page()
        allow_now = int(page2.get("sumAllowWithdraw") or 0)
        withdrawn_flag = bool(page2.get("withdrawn"))
        if DRY_RUN:
            withdraw_msg = f"干跑：可提现 {yuan(allow_now)}"
        elif not ENABLE_WITHDRAW:
            withdraw_msg = f"已关闭提现（可提现 {yuan(allow_now)}）"
        elif withdrawn_flag:
            withdraw_msg = "本期已提现过"
        elif allow_now >= WITHDRAW_MIN:
            real_name = client.check_real_name()
            if not real_name:
                withdraw_msg = f"可提现 {yuan(allow_now)} 但未实名，需手动实名后提现"
            else:
                try:
                    client.withdraw(allow_now)
                    withdraw_msg = f"✅ 已提现 {yuan(allow_now)} 至微信零钱"
                except Exception as exc:
                    withdraw_msg = f"提现失败：{clean(exc, 160)}"
        else:
            withdraw_msg = f"可提现 {yuan(allow_now)}，未达 {yuan(WITHDRAW_MIN)} 门槛"
        log(f"   💳 提现：{withdraw_msg}")
    except Exception as exc:
        withdraw_msg = f"提现检查异常：{clean(exc, 160)}"
        log(f"   ⚠️ {withdraw_msg}")
    result["withdraw"] = withdraw_msg

    # ---------------- 最终状态 ---------------- #
    try:
        page3 = client.home_page()
        sum_award_1 = int(page3.get("sumAward") or 0)
        allow_1 = int(page3.get("sumAllowWithdraw") or 0)
    except Exception:
        sum_award_1, allow_1 = sum_award_0, allow_0
    result["sum_after"] = sum_award_1
    result["allow_after"] = allow_1
    log(f"   💰 总签到金 {yuan(sum_award_0)} → {yuan(sum_award_1)}"
        f"（本次 {'+' if sum_award_1 >= sum_award_0 else ''}"
        f"{yuan(max(0, sum_award_1 - sum_award_0))}）")
    result["balls"] = balls_got
    result["balls_note"] = balls_note
    return result


# --------------------------------------------------------------------------- #
# 通知
# --------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------
# 青龙通知（走面板通知设置，例如面板里配的企业微信）
# 背景：notify.py 只读 QYWX_AM 等环境变量，读不到面板数据库里的通知配置，
# 所以只调它时面板里配的企业微信收不到。本函数优先调青龙面板本地接口
# PUT /open/system/notify（带系统 token，见 /ql/data/config/token.json），
# 该接口由面板后端按数据库里的通知配置发出去；失败时在日志里写明原因，
# 再试 notify.py（仅环境变量渠道有效）。通知发不发得出去绝不影响主流程。
# 截断规则：正文先取执行汇总，再加日志尾部最多 30 行，总长截到约 1800 字符
# （企业微信应用消息有长度限制，完整日志会被截断或发失败）。
# ---------------------------------------------------------------------------
import subprocess as _ql_subprocess
import urllib.error as _ql_urlerror
import urllib.request as _ql_urlrequest

_QL_NOTIFY_MAX_LEN = 1800
_QL_NOTIFY_TAIL_LINES = 30


def _ql_truncate(text, limit=_QL_NOTIFY_MAX_LEN):
    text = (text or "").strip()
    if len(text) > limit:
        return text[:limit] + "\n……（内容已截断，完整日志见青龙运行日志）"
    return text


class _QlLogTee:
    """把 print 输出同时写进内存缓冲，供通知取日志尾部；屏幕输出不受影响。"""

    def __init__(self, stream):
        import io as _io
        import threading as _th
        self.stream = stream
        self.buf = _io.StringIO()
        self.lock = _th.Lock()

    def write(self, s):
        with self.lock:
            try:
                self.stream.write(s)
            except Exception:
                pass
            try:
                self.buf.write(s)
            except Exception:
                pass
        return len(s)

    def flush(self):
        with self.lock:
            try:
                self.stream.flush()
            except Exception:
                pass

    def tail(self, lines=_QL_NOTIFY_TAIL_LINES):
        return "\n".join(self.buf.getvalue().splitlines()[-lines:])


def _ql_panel_token(force_regen=False):
    """读青龙系统 token：先读缓存文件，过期/缺失时用面板自带的 token.js 重新生成。"""
    import json as _json
    import time as _time
    if not force_regen:
        for _path in (
            os.environ.get("QL_NOTIFY_TOKEN_FILE", "") or "",
            "/ql/data/config/token.json",
            "/ql/config/token.json",
        ):
            if not _path:
                continue
            try:
                with open(_path, encoding="utf-8") as _f:
                    _data = _json.load(_f)
                _tok = str(_data.get("value") or "").strip()
                _exp = int(_data.get("expiration") or 0)
                if _tok and _exp > _time.time() + 30:
                    return _tok
            except Exception:
                continue
    for _cmd in (["node", "/ql/static/build/token.js"], ["node", "/ql/build/token.js"]):
        try:
            _r = _ql_subprocess.run(_cmd, capture_output=True, text=True, timeout=30)
            if _r.returncode == 0:
                _parts = (_r.stdout or "").strip().split()
                if _parts:
                    return _parts[-1]
        except Exception:
            continue
    return ""

def _ql_panel_notify(title, content):
    """调面板接口发通知。返回 (True, '') 或 (False, 原因)。"""
    import json as _json
    import time as _time
    port = (os.environ.get("QL_NOTIFY_PORT", "") or os.environ.get("QlPort", "") or "5700").strip() or "5700"
    token = _ql_panel_token()
    if not token:
        return False, "读不到青龙系统 token（/ql/data/config/token.json 不存在/已过期，且 node token.js 重新生成失败）"
    body = _json.dumps({"title": title, "content": content}, ensure_ascii=False).encode("utf-8")
    for attempt in range(2):
        try:
            req = _ql_urlrequest.Request(
                "http://127.0.0.1:%s/open/system/notify?t=%d" % (port, int(_time.time())),
                data=body,
                headers={"Authorization": "Bearer " + token, "Content-Type": "application/json;charset=UTF-8"},
                method="PUT",
            )
            with _ql_urlrequest.urlopen(req, timeout=15) as resp:
                data = _json.loads(resp.read().decode("utf-8", "replace"))
            if data.get("code") == 200:
                return True, ""
            if data.get("code") == 401 and attempt == 0:
                token = _ql_panel_token(force_regen=True)
                if not token:
                    return False, "面板接口返回 401 且重新生成 token 失败"
                continue
            return False, "面板通知接口返回 code=%s：%s" % (data.get("code"), str(data.get("message") or "")[:120])
        except _ql_urlerror.HTTPError as exc:
            if exc.code == 401 and attempt == 0:
                token = _ql_panel_token(force_regen=True)
                if not token:
                    return False, "面板接口返回 HTTP 401 且重新生成 token 失败"
                continue
            return False, "面板通知接口 HTTP %s" % exc.code
        except Exception as exc:
            return False, "连接青龙面板接口失败：%s" % exc
    return False, "面板通知接口调用失败"


def _ql_load_notify_py():
    """加载 notify.py（同目录 → /ql/data/scripts → /ql/scripts），找不到返回 None。"""
    import importlib.util as _ilu
    from pathlib import Path as _Path
    here = _Path(__file__).resolve().parent
    for _path in (here / "notify.py", _Path("/ql/data/scripts/notify.py"), _Path("/ql/scripts/notify.py")):
        if not _path.exists():
            continue
        try:
            spec = _ilu.spec_from_file_location("ql_notify_fallback", _path)
            mod = _ilu.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "send"):
                return mod
        except Exception:
            continue
    return None


def _ql_notify(title, content):
    """发青龙通知：优先走面板接口（面板通知设置/企业微信），失败再试 notify.py。绝不抛异常。"""
    content = _ql_truncate(content)
    try:
        ok, reason = _ql_panel_notify(title, content)
    except Exception as exc:
        ok, reason = False, "面板通知调用异常：%s" % exc
    if ok:
        log("📨 青龙通知已发（面板通知设置）")
        return True
    log("⚠️ [通知] 面板接口发送失败：%s，尝试 notify.py" % reason)
    sender = _ql_load_notify_py()
    if sender is None:
        log("⚠️ [通知] 未找到 notify.py，通知未发出")
        return False
    try:
        sender.send(title, content)
        log("📨 通知已通过 notify.py 发送（仅环境变量配置的渠道有效，未配则静默不发）")
        return True
    except Exception as exc:
        log("⚠️ [通知] notify.py 发送失败：%s" % exc)
        return False


def load_notify():
    for path in (Path(HERE) / "notify.py",
                 Path("/ql/data/scripts/notify.py"),
                 Path("/ql/scripts/notify.py"),
                 Path("/ql/data/notify.py")):
        if path.exists():
            try:
                spec = importlib.util.spec_from_file_location("zajk_qinglong_notify", path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                if hasattr(mod, "send"):
                    return mod
            except Exception as exc:
                log(f"⚠️ [通知] 加载 {path} 失败：{clean(exc, 120)}")
    return None


def send_notify(title: str, content: str) -> None:
    ok, reason = _ql_panel_notify(title, content)
    if ok:
        log("📨 通知已通过青龙面板接口发送（走面板通知设置）")
        return
    log(f"⚠️ [通知] 面板接口发送失败：{reason}，尝试 notify.py")
    sender = load_notify()
    if sender:
        try:
            sender.send(title, content)
            log("📨 通知已通过青龙 notify.py 发送")
            return
        except Exception as exc:
            log(f"⚠️ [通知] notify.py 发送失败：{clean(exc, 160)}，尝试回落通道")
    else:
        log("⚠️ [通知] 未找到青龙 notify.py，使用脚本自带通道")
    # 回落：PushPlus / Server酱 / Bark
    token = (os.getenv("PUSH_PLUS_TOKEN", "") or "").strip()
    if token:
        try:
            requests.post("https://www.pushplus.plus/send",
                          json={"token": token, "title": title, "content": content,
                                "template": "txt"},
                          timeout=TIMEOUT)
            log("📨 通知已通过 PushPlus 发送")
            return
        except Exception as exc:
            log(f"⚠️ [通知] PushPlus 失败：{clean(exc, 120)}")
    sckey = (os.getenv("SC_KEY", "") or "").strip()
    if sckey:
        try:
            requests.post(f"https://sc.ftqq.com/{sckey}.send",
                          data={"title": title, "desp": content}, timeout=TIMEOUT)
            log("📨 通知已通过 Server酱 发送")
            return
        except Exception as exc:
            log(f"⚠️ [通知] Server酱 失败：{clean(exc, 120)}")
    bark = (os.getenv("BARK_PUSH", "") or "").strip()
    if bark:
        try:
            requests.get(f"{bark}/{title}/{content[:120]}", timeout=TIMEOUT)
            log("📨 通知已通过 Bark 发送")
        except Exception as exc:
            log(f"⚠️ [通知] Bark 失败：{clean(exc, 120)}")
    log("⚠️ [通知] 所有通道均未配置或失败，仅保留日志")


# --------------------------------------------------------------------------- #
# 汇总
# --------------------------------------------------------------------------- #
def build_report(results: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    if DRY_RUN:
        lines.append("🔶 干跑模式（ZAJK_DRY_RUN=1），未执行任何写操作")
    ok = [r for r in results if not r.get("error") and not r.get("skipped")]
    skip = [r for r in results if r.get("skipped")]
    fail = [r for r in results if r.get("error")]
    lines.append(f"账号统计：{len(ok)} 成功 / {len(skip)} 跳过 / {len(fail)} 失败")

    for r in ok:
        lines.append(f"\n—— 账号 {r['label']} ——")
        lines.append(f"签到：{r.get('sign') or '—'}")
        if r.get("balls") or r.get("balls_note"):
            lines.append(f"领奖：{r.get('balls')} 个（{r.get('balls_note')}）")
        if r.get("browse_done"):
            lines.append(f"每周浏览：完成 {len(r['browse_done'])} 个（{'、'.join(r['browse_done'])}）")
        if r.get("browse_fail"):
            lines.append(f"每周浏览：失败 {len(r['browse_fail'])} 个（{'、'.join(r['browse_fail'])}）")
        lines.append(f"总签到金：{yuan(r.get('sum_before'))} → {yuan(r.get('sum_after'))}")
        lines.append(f"可提现：{yuan(r.get('allow_after'))}　{r.get('withdraw') or ''}")

    for r in skip:
        lines.append(f"\n—— 账号 {r['label']} ——\n⏭️ 跳过：{r.get('summary') or '未参与活动'}")
    for r in fail:
        lines.append(f"\n—— 账号 {r['label']} ——\n❌ {r.get('error')}")
    return "\n".join(lines)


def main() -> int:
    tee = _QlLogTee(sys.stdout)
    sys.stdout = tee
    log(f"🟢 {APP_NAME} 启动 @ {time.strftime('%Y-%m-%d %H:%M:%S')}")
    if DRY_RUN:
        log("🔶 干跑模式：只查询不执行")

    yyb_raw = (os.getenv("YYB_SERVER", "") or "").strip()
    if not yyb_raw:
        log("❌ 未配置 YYB_SERVER（格式：地址@账号ID，多账号每行一条）")
        sys.stdout = tee.stream
        _ql_notify("众安健康签到：0成功/0失败", "❌ 未配置 YYB_SERVER（格式：地址@账号ID，多账号每行一条）")
        return 1

    accounts: List[Tuple[str, str]] = []
    for line in yyb_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if "@" in line:
            host, ref = line.rsplit("@", 1)
        else:
            host, ref = line, "1"
        if host and not host.startswith("http"):
            host = "http://" + host
        accounts.append((host, clean(ref)))
    if not accounts:
        log("❌ YYB_SERVER 解析结果为空")
        sys.stdout = tee.stream
        _ql_notify("众安健康签到：0成功/0失败", "❌ YYB_SERVER 解析结果为空")
        return 1
    log(f"共 {len(accounts)} 个账号待处理")

    results: List[Dict[str, Any]] = []
    for idx, (host, ref) in enumerate(accounts, 1):
        try:
            results.append(run_account(host, ref, f"{ref}"))
        except Exception as exc:  # 单账号异常不拖垮整体
            log(f"   ❌ 账号 {ref} 处理异常：{clean(exc, 200)}")
            results.append({"label": ref, "ref": ref, "error": clean(exc, 200)})

    report = build_report(results)
    log(f"\n{'=' * 62}\n汇总\n{'=' * 62}\n{report}")
    sys.stdout = tee.stream
    _ok = sum(1 for r in results if not r.get("error") and not r.get("skipped"))
    _fail = sum(1 for r in results if r.get("error"))
    _tail = tee.tail()
    if _tail:
        report = report + "\n\n📋 日志尾部（最近30行）:\n" + _tail
    send_notify(f"{APP_NAME}：{_ok}成功/{_fail}失败", report)

    real_fail = [r for r in results if r.get("error")]
    return 1 if real_fail else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
