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
DOGE 自动 青龙脚本
=========================================================
cron: 0 30 8,20 * * *     每天 8:30 / 20:30 运行两次
new Env('DOGE 自动');

变量: DOGE
格式: 邮箱#密码         单个账号
      邮箱1#密码1       多个账号换行分隔
      邮箱2#密码2

依赖: requests

可选变量:
  DOGE_MINE_MIN   挖矿门槛，可用余额达到该值才挖矿，默认 100
  DOGE_MINE       设为 0 关闭挖矿
  DOGE_SELL       设为 0 关闭释放（卖出 DOGE）
  DOGE_BUY        设为 0 关闭购买额度
  DOGE_DELAY      行为上报间隔秒数，默认 1.0

流程: 签到 -> 行为任务 -> 领取 -> 购买额度 -> 释放卖出 -> 挖矿 -> 状态
"""

import os
import re
import sys
import json
import time
import uuid
import urllib.parse

try:
    import requests
    from requests.adapters import HTTPAdapter
except ImportError:
    print("缺少依赖，请先执行: pip3 install requests")
    sys.exit(1)

requests.packages.urllib3.disable_warnings()

# ================================================================== 常量配置

# 入口域名（来自 aidoge-android-config.json 路由表，按 priority 排序）
DEFAULT_ORIGINS = [
    "https://aidoge.app",
    "https://aidoge368.com",
    "https://aidoge556.com",
    "https://aidoge398.com",
    "https://aidoge225.com",
    "https://aidoge330.com",
]

# serverFn 端点哈希（全部来自 HAR 逐条校准）
FN_REPORT    = "a23c72732a833d0b17d84918afcc1ed146d01e2f32ae0d0052d32c6b28724a44"
FN_CLAIM     = "c65127e8d310dcad412e21f480ca9109dabea18d91fac7f4b16e7233ab1be0ec"
FN_MINING    = "76c0f3f3804b45e67766aeaf54011d74a68f7b4aa8ea43f89324e2af1bfb6721"
FN_TASKS     = "0e59c06a846b9dae6914758d5a31dd88f1d4a21671c42fe1b5ca5b96a3b5d152"
FN_ECO       = "af5f6ee10330c9661d3f4631b881230bfd3b93ad4118cbdcfa5e01725827a9f9"
FN_MINE_LS   = "80105393ff64a7db607b2d9db04447534ed74277714d8be5b18eb24cc88d9295"
FN_BALANCE   = "ceab2d1564caeaa81b06a4b6292bcd94d86556fa1250a9fd9af7ea17fc9ba78b"
FN_QUOTA     = "8eb1c427c808da8e12e2d580555ba695ab194454ddc63e740aac64519b4facce"
FN_TRADE_Q   = "cb1090e9d975aa2e38378d11f2b1169ae092933833dbcc33ecdfe4985cf50011"
FN_TRADE     = "c134cc159b19023c846fd756480183a4932298466cab67200e716ed1f254a81e"
FN_BUY_Q     = "2352f5029b20edae3904b3daf13b5885e1f9e398705a33c6b1a6e3da57c86bbe"
FN_BUY       = "ae253903f251328d8ded20b32f0ed1b2c2679064e840aebf0d8f28107f464cac"

# 卖出标的
TRADE_MARKET = "crypto"
TRADE_SYMBOL = "DOGE"

# 任务 key -> 需要上报的行为 kind
BEHAVIOR_KINDS = {
    "daily_login":        "daily_login",
    "view_market":        "view_market",
    "view_strategies":    "view_strategies",
    "enter_doge":         "enter_doge",
    "view_mining_status": "view_mining_status",
}

# 行为 kind -> 中文名（用于日志展示）
KIND_LABELS = {
    "daily_login":        "每日登录",
    "view_market":        "查看行情",
    "view_strategies":    "查看策略中心",
    "enter_doge":         "进入DOGE生态",
    "view_mining_status": "查看挖矿状态",
}

# 行为上报间隔（秒），避免连续快速请求
BEHAVIOR_DELAY = float(os.getenv("DOGE_DELAY", "1.0"))

# 挖矿门槛：可用余额达到该值才发起挖矿
MINE_MIN_BALANCE = float(os.getenv("DOGE_MINE_MIN", "100"))

# 认证配置（可在环境变量中覆盖）
ENV_APIKEY = os.getenv("DOGE_APIKEY", "").strip()
ENV_ORIGIN = os.getenv("DOGE_ORIGIN", "").strip()
ENV_MINE = os.getenv("DOGE_MINE", "1").strip() not in ("0", "false", "False")
ENV_SELL = os.getenv("DOGE_SELL", "1").strip() not in ("0", "false", "False")
ENV_BUY = os.getenv("DOGE_BUY", "1").strip() not in ("0", "false", "False")

# 内置 anon apikey（抓包实证，有效期至 2026-10-27）
# 过期时用 DOGE_APIKEY 环境变量覆盖，或从站点重新抓取
BUILTIN_APIKEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJyb2xlIjoiYW5vbiIsImlzcyI6InN1cGFiYXNlIiwiYXVkIjoiYXV0aGVudGljYXRlZCIsImlhdCI6MTc5MDQ5NzI2OSwiZXhwIjoxNzkzMDg5MjY5fQ."
    "mmf-UNUZbmHZOqlOV06jTpz584LROWCTd3j5CYhh7Hk"
)

UA = ("Mozilla/5.0 (Linux; Android 16; 2410DPN6CC Build/BP2A.250605.031.A3; wv) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
      "Chrome/150.0.7871.181 Mobile Safari/537.36 AIDOGEApp/0.2.3")


# ================================================================== 序列化

class Zero:
    """语义为 t:2 的数值槽位（sessionId=0 / key=0 等空值必须用 t:2）"""
    __slots__ = ("v",)

    def __init__(self, v=0):
        self.v = v


def enc(node, i=1):
    """
    编码为服务端 t 结构（HAR 逐字节校准）。
      Zero   -> {"t":2,"s":v}   空值槽位
      number -> {"t":0,"s":n}   普通整数
      bool   -> {"t":2,"s":3|2}
      字符串 -> {"t":1,"s":str}
      对象   -> {"t":10,"i":depth,...}  i 从 1 起随嵌套递增
    """
    if isinstance(node, Zero):
        return {"t": 2, "s": node.v}
    if node is None:
        return {"t": 2, "s": 0}
    if isinstance(node, bool):
        return {"t": 2, "s": 3 if node else 2}
    if isinstance(node, (int, float)):
        return {"t": 0, "s": node}
    if isinstance(node, str):
        return {"t": 1, "s": node}
    if isinstance(node, list):
        return {"t": 9, "i": i, "a": [enc(x, i + 1) for x in node], "o": 0}
    if isinstance(node, dict):
        keys = list(node.keys())
        return {"t": 10, "i": i, "p": {"k": keys, "v": [enc(node[k], i + 1) for k in keys]}, "o": 0}
    raise TypeError("unsupported: %s" % type(node))


def dec(node):
    """解码服务端 t 结构"""
    if not isinstance(node, dict):
        return node
    t = node.get("t")
    if t == 10:
        p = node.get("p", {})
        return {k: dec(v) for k, v in zip(p.get("k", []), p.get("v", []))}
    if t == 9:
        return [dec(x) for x in node.get("a", [])]
    if t in (0, 1, 2, 3):
        return node.get("s")
    return node


def wrap(data):
    """外层信封（两层 data 包裹，与抓包一致）"""
    inner = {"t": 10, "i": 0, "p": {"k": ["data"], "v": [enc(data, 1)]}, "o": 0}
    return {"t": inner, "f": 127, "m": []}


def unwrap(raw):
    """解析响应，剥掉 data 外层并取出 result"""
    try:
        out = dec(json.loads(raw))
    except Exception:
        return None
    if isinstance(out, dict) and "data" in out:
        out = out["data"]
    if isinstance(out, dict) and "result" in out:
        return out["result"]
    return out


def fnum(x):
    """数值转字符串，去掉多余小数零（用于下单金额字段）"""
    try:
        s = "%.8f" % float(x)
    except (TypeError, ValueError):
        return str(x)
    s = s.rstrip("0").rstrip(".")
    return s or "0"


def fit(x):
    """金额收敛到 8 位小数，避免浮点尾巴"""
    return float("%.8f" % float(x))


def tofloat(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


# ================================================================== 通知

def send_notify(title, content):
    """青龙通知推送（存在则用，不存在静默跳过）"""
    try:
        sys.path.insert(0, "/ql/data/scripts")
        from notify import send
        send(title, content)
        return True
    except Exception:
        pass
    try:
        sys.path.insert(0, os.path.expanduser("~/scripts"))
        from notify import send
        send(title, content)
        return True
    except Exception:
        return False


# ================================================================== 客户端

class AiDoge:
    def __init__(self, email, password, index=1):
        self.email = email
        self.password = password
        self.index = index
        self.origins = ([ENV_ORIGIN] if ENV_ORIGIN else []) + DEFAULT_ORIGINS
        self.origin = None
        self.api_key = ENV_APIKEY or BUILTIN_APIKEY
        self.install_id = str(uuid.uuid4())
        self.access_token = None
        self.refresh_token = None
        self.mine_state = None
        self.sess = requests.Session()
        self.sess.mount("https://", HTTPAdapter(pool_maxsize=8))

    # ---------------- 底层

    def _headers(self, auth=True, login=False):
        base = self.origin or self.origins[0]
        h = {
            "accept": "*/*",
            "content-type": "application/json;charset=UTF-8",
            "origin": base,
            "referer": base + ("/login?redirect=%2Flogin" if login else "/"),
            "user-agent": UA,
            "x-requested-with": "app.aidoge.mobile",
            "x-doge-install": self.install_id,
            "x-client-info": "supabase-js/2.116.0; runtime=web",
            "x-supabase-api-version": "2024-01-01",
            "accept-language": "zh-CN,zh;q=0.9",
        }
        if self.api_key:
            h["apikey"] = self.api_key
        if auth and self.access_token:
            h["authorization"] = "Bearer " + self.access_token
        elif self.api_key and login:
            # 登录阶段 authorization 携带 anon key（抓包实证）
            h["authorization"] = "Bearer " + self.api_key
        return h

    def _get(self, url, auth=True, extra=None):
        h = self._headers(auth)
        if extra:
            h.update(extra)
        try:
            r = self.sess.get(url, headers=h, timeout=25, verify=False)
            return r.status_code, r.text
        except Exception as e:
            return 0, str(e)

    def _post(self, url, body, auth=True, extra=None):
        h = self._headers(auth)
        if extra:
            h.update(extra)
        try:
            r = self.sess.post(url, headers=h, data=json.dumps(body),
                               timeout=25, verify=False)
            return r.status_code, r.text
        except Exception as e:
            return 0, str(e)

    # ---------------- 初始化

    def discover(self):
        for o in self.origins:
            st, raw = self._get(o + "/.well-known/aidoge-android-config.json", auth=False)
            if st == 200 and "routes" in (raw or ""):
                self.origin = o
                return o
        self.origin = self.origins[0]
        return self.origin

    def fetch_apikey(self):
        if self.api_key:
            return self.api_key
        st, raw = self._get(self.origin + "/", auth=False)
        for pat in (r'apikey["\']?\s*[:=]\s*["\']([A-Za-z0-9_.\-]+)',
                    r'(eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,})'):
            m = re.search(pat, raw or "")
            if m:
                self.api_key = m.group(1)
                return self.api_key
        return None

    def login(self):
        url = self.origin + "/identity/auth/v1/token?grant_type=password"
        body = {"email": self.email, "password": self.password, "gotrue_meta_security": {}}
        st, raw = self._post(url, body, auth=False, extra={
            "referer": self.origin + "/login?redirect=%2Flogin",
            "origin": self.origin,
        })
        try:
            j = json.loads(raw)
        except Exception:
            return False, "响应异常(%s): %s" % (st, (raw or "")[:120])
        if "access_token" in j:
            self.access_token = j["access_token"]
            self.refresh_token = j.get("refresh_token")
            u = j.get("user", {})
            return True, "%s (uid=%s)" % (u.get("email", self.email), u.get("id", "?")[:8])
        return False, j.get("error_description") or j.get("msg") or j.get("message") or (raw or "")[:120]

    def _serverfn(self, hsh, method, payload=None):
        url = self.origin + "/_serverFn/" + hsh
        sf = {"x-tsr-serverfn": "true",
              "accept": "application/x-tss-framed, application/x-ndjson, application/json"}
        if method == "GET":
            p = urllib.parse.quote(json.dumps(wrap(payload or {}), separators=(",", ":")))
            st, raw = self._get(url + "?payload=" + p, extra=sf)
        else:
            st, raw = self._post(url, wrap(payload or {}), extra=sf)
        return unwrap(raw)

    def report(self, kind):
        body = {
            "kind": kind,
            "requestId": str(uuid.uuid4()),
            "device": {"installId": self.install_id, "platform": "web"},
        }
        res = self._serverfn(FN_REPORT, "POST", body)
        # 响应形如 {"ok":2,"duplicate":3}
        # ok:      本次是否为新记录（2=否 3=是）
        # duplicate: 是否已上报过（2=否 3=是）
        # 只要拿到合法响应即视为上报成功（奖励由服务端异步生成）
        if isinstance(res, dict) and "duplicate" in res:
            return res.get("duplicate") != 3   # 返回 True 表示本次是新上报
        return isinstance(res, dict) and "ok" in res

    def tasks(self):
        res = self._serverfn(FN_TASKS, "GET", {"page": 1, "status": "all"})
        if isinstance(res, dict):
            return res
        res = self._serverfn(FN_ECO, "GET", {})
        if isinstance(res, dict):
            return res.get("eco", {})
        return {}

    def balance(self):
        res = self._serverfn(FN_BALANCE, "GET")
        for it in res or []:
            if it.get("kind") == "doge":
                return it
        return {}

    def claim(self, reward_id):
        body = {
            "action": "claim",
            "rewardId": reward_id,
            "key": Zero(0),
            "requestId": str(uuid.uuid4()),
        }
        res = self._serverfn(FN_CLAIM, "POST", body)
        if isinstance(res, dict) and res.get("status") == "paid":
            return True, "领取完成 %s +%s" % (res.get("title"), res.get("amount"))
        if isinstance(res, dict):
            return False, "%s[%s]" % (res.get("title"), res.get("status"))
        return False, "失败"

    def checkin(self):
        body = {"action": "checkin", "rewardId": Zero(0), "key": Zero(0),
                "requestId": str(uuid.uuid4())}
        res = self._serverfn(FN_CLAIM, "POST", body)
        if isinstance(res, dict) and res.get("status") == "paid":
            return True, "+%s streak=%s" % (res.get("amount"), res.get("streak"))
        if res in (1, "1"):
            return True, "今日已签到"
        return False, str(res)

    def claim_all(self, retry=3, wait=1.5):
        """领取全部 claimable（行为上报后奖励为异步生成，需轮询）"""
        rewards = []
        for _ in range(retry):
            rewards = (self.tasks().get("rewards") or [])
            if any(r.get("status") == "claimable" for r in rewards):
                break
            time.sleep(wait)
        pend = [r for r in rewards if r.get("status") == "claimable"]
        got = []
        for r in pend:
            ok, info = self.claim(r["id"])
            if ok:
                got.append(info)
            time.sleep(0.4)
        return got

    # ---------------- 挖矿

    def mining_state(self):
        """
        挖矿面板。关键字段（HAR 实证）：
          rows           历史订单，principal=当前本金，initial_amount=初始本金
          available      真正可再投入的闲置 DOGE（已扣掉所有 running 单的本金）
          activeSessions 正在跑的订单
          policy         min_amount / max_amount 单笔上下限
        """
        res = self._serverfn(FN_MINE_LS, "GET", {"page": 1, "status": "all"})
        if isinstance(res, dict):
            return res
        return {}

    def mining_rows(self):
        return (self.mining_state().get("rows") or [])

    def _mine_call(self, action, amount, session_id):
        """挖矿单一动作：start / add / stop"""
        body = {"action": action, "amount": amount,
                "sessionId": session_id, "requestId": str(uuid.uuid4())}
        res = self._serverfn(FN_MINING, "POST", body)
        if isinstance(res, dict) and res.get("id"):
            return True, res
        return False, res

    def stop_all_running(self):
        """停止全部 running 订单，返回[(id, 收益)]"""
        st = self.mining_state()
        run = [r for r in (st.get("activeSessions") or [])
               if r.get("status") == "running"]
        if not run:
            run = [r for r in (st.get("rows") or []) if r.get("status") == "running"]
        stopped = []
        for r in run:
            ok, res = self._mine_call("stop", 0, r["id"])
            if ok:
                stopped.append((r["id"], res.get("earned")))
            else:
                stopped.append((r["id"], "失败:%s" % res))
            time.sleep(0.5)
        return stopped

    def mine(self, min_balance=None):
        """
        挖矿。动作语义（HAR 实证）：
          start  新建订单，sessionId 必须是 0
          add    追加到已有订单，sessionId 必须是订单 id
          stop   停止订单，amount=0
        之前用 start 带已有 id 去"追加"，服务端只回 1（受理但不变动），等于空跑。
        策略：新建 -> 追加 -> 全部停止后重建。
        self.mine_state: ok / zero / skipped / accepted / fail
        """
        st = self.mining_state()
        if not isinstance(st, dict) or "available" not in st:
            # 面板异常，退回余额口径
            bal = self.balance()
            st = {"available": max(0.0, tofloat(bal.get("balance")) - tofloat(bal.get("frozen")))}

        pol = st.get("policy") or {}
        avail = tofloat(st.get("available"))
        server_min = tofloat(pol.get("min_amount"), 0.0)
        server_max = tofloat(pol.get("max_amount"), 0.0)
        # 门槛取环境变量与服务端下限的较大者，两边都不违反
        threshold = max(MINE_MIN_BALANCE, server_min)
        running = [r for r in (st.get("activeSessions") or [])
                   if r.get("status") == "running"]
        if not running:
            running = [r for r in (st.get("rows") or []) if r.get("status") == "running"]

        if avail <= 0:
            self.mine_state = "zero"
            return False, "可用余额为0，无可投本金 (门槛 %.0f 在挖=%d单)" % (
                threshold, len(running))

        if avail < threshold:
            self.mine_state = "skipped"
            return False, "余额不足跳过: 可用 %.2f < 门槛 %.0f，还差 %.2f (在挖=%d单)" % (
                avail, threshold, threshold - avail, len(running))

        amount = fit(avail if not server_max else min(avail, server_max))
        before = fit(avail)

        # ---- 依次尝试：新建 -> 追加（或反之，视是否有在挖订单）
        if running:
            plan = [("add", running[0]["id"], "追加"),
                    ("start", Zero(0), "新建")]
        else:
            plan = [("start", Zero(0), "新建")]

        notes = []
        for action, sid, label in plan:
            ok, res = self._mine_call(action, amount, sid)
            if not ok:
                notes.append("%s被拒(%s)" % (label, res))
                continue
            time.sleep(0.9)
            st2 = self.mining_state()
            avail2 = tofloat(st2.get("available"))
            if avail2 < before - 1e-9:
                self.mine_state = "ok"
                return True, "%s principal=%s 投入=%s 剩余可用=%s" % (
                    label, res.get("principal"), amount, avail2)
            notes.append("%s未生效(可用仍=%s)" % (label, avail2))

        # ---- 兜底：全部订单停止，重新开挖
        stopped = self.stop_all_running()
        if stopped:
            notes.append("已停止 %d 单" % len(stopped))
        time.sleep(1.0)
        st3 = self.mining_state()
        avail3 = tofloat(st3.get("available"))
        if avail3 <= 0:
            self.mine_state = "fail"
            return False, "停止后在无可投余额 (%s)" % "；".join(notes)
        amount3 = fit(avail3 if not server_max else min(avail3, server_max))
        ok, res = self._mine_call("start", amount3, Zero(0))
        if ok:
            time.sleep(0.9)
            st4 = self.mining_state()
            if tofloat(st4.get("available")) < avail3 - 1e-9:
                self.mine_state = "ok"
                return True, "全部停止后重建 principal=%s 投入=%s（%s）" % (
                    res.get("principal"), amount3, "；".join(notes))
        self.mine_state = "fail"
        return False, "挖矿失败: %s" % ("；".join(notes) or "无响应")

    # ---------------- 额度 / 释放 / 购买

    def quota_panel(self):
        """
        额度面板。字段（HAR 实证）：
          doge    可用 DOGE
          usdt    可用 USDT
          quota.remaining      今日还能卖出的 DOGE 数量
          quota.minimum        单笔最小卖出量
          quota.sold/enabled   今日已卖 / 是否开放
          policy.minUsdt/stepUsdt/quotaPerUsdt/giftPerUsdt  购买额度规则
        """
        res = self._serverfn(FN_QUOTA, "GET", {"page": 1})
        return res if isinstance(res, dict) else {}

    def sell_quote(self, amount):
        """卖出报价，返回 proposal（含 quoteId / policyVersion / qty）"""
        res = self._serverfn(FN_TRADE_Q, "GET", {
            "market": TRADE_MARKET, "symbol": TRADE_SYMBOL,
            "side": "sell", "amount": fit(amount),
        })
        return res if isinstance(res, dict) else {}

    def sell(self, quote):
        """按报价成交"""
        body = {
            "market": TRADE_MARKET,
            "symbol": TRADE_SYMBOL,
            "side": "sell",
            "amount": quote.get("qty") or quote.get("amount"),
            "quoteId": quote.get("quoteId"),
            "policyVersion": quote.get("policyVersion"),
            "requestId": str(uuid.uuid4()),
        }
        res = self._serverfn(FN_TRADE, "POST", body)
        if isinstance(res, dict) and res.get("id"):
            return True, res
        return False, res

    def release_all(self, max_rounds=3):
        """
        释放：把今日剩余额度内的 DOGE 全部卖掉。
        一轮只下一单（剩余额度可能一次就吃掉），最多重试 max_rounds 轮。
        返回 (成交明细列表, 结束原因)
        """
        done = []
        reason = "无剩余额度"
        for _ in range(max_rounds):
            panel = self.quota_panel()
            if not panel:
                return done, "额度面板读取失败"
            doge = tofloat(panel.get("doge"))
            q = panel.get("quota") or {}
            remaining = tofloat(q.get("remaining"))
            minimum = tofloat(q.get("minimum"), 1.0) or 1.0
            if tofloat(q.get("enabled"), 3) == 3:
                reason = "释放功能未开放"
                break
            if remaining <= 0:
                reason = "今日额度已用完(今日已卖 %s)" % q.get("sold")
                break
            amount = fit(min(doge, remaining))
            if amount <= 0:
                reason = "DOGE 余额为0"
                break
            if amount < minimum:
                reason = "可卖 %.4f 低于最小 %.0f" % (amount, minimum)
                break
            quote = self.sell_quote(amount)
            prop = quote.get("proposal") or {}
            if not prop or not prop.get("quoteId"):
                reason = "报价失败(price=%s msg=%s)" % (quote.get("price"), quote.get("message"))
                break
            ok, res = self.sell(prop)
            if not ok:
                reason = "下单被拒(%s)" % res
                break
            done.append({
                "qty": tofloat(res.get("qty")),
                "turnover": tofloat(res.get("turnover")),
                "price": tofloat(res.get("avg_price")),
                "status": res.get("status"),
            })
            time.sleep(0.8)
        return done, reason

    def quota_preview(self, amount):
        """购买额度预览，返回 version / purchaseCount / quota / gift"""
        res = self._serverfn(FN_BUY_Q, "GET", {"amount": fnum(amount)})
        return res if isinstance(res, dict) else {}

    def buy_quota(self, amount):
        """购买额度（amount 为 USDT，按整档）"""
        pv = self.quota_preview(amount)
        body = {
            "amount": fnum(amount),
            "expected": pv.get("version"),
            "purchaseCount": pv.get("purchaseCount", 0),
            "requestId": str(uuid.uuid4()),
        }
        res = self._serverfn(FN_BUY, "POST", body)
        if isinstance(res, dict) and res.get("id"):
            return True, res, pv
        return False, res, pv

    def topup_quota(self):
        """
        购买额度：按 USDT 余额能买多少档买多少，1 USDT 起。
        返回 (是否成交, 说明)
        """
        panel = self.quota_panel()
        if not panel:
            return False, "额度面板读取失败"
        usdt = tofloat(panel.get("usdt"))
        pol = panel.get("policy") or {}
        step = tofloat(pol.get("stepUsdt"), 1.0) or 1.0
        minu = tofloat(pol.get("minUsdt"), 1.0) or 1.0
        amount = fit(int(usdt / step) * step)
        if amount < minu:
            return False, "USDT %.8f 不足起购 %.0f，跳过" % (usdt, minu)
        ok, res, pv = self.buy_quota(amount)
        if ok:
            return True, "花费 %s USDT -> 额度 +%s 赠送 %s" % (
                fnum(res.get("paid")), fnum(res.get("quota")), fnum(res.get("gift")))
        return False, "购买被拒(预览version=%s): %s" % (pv.get("version"), res)

    def release_and_topup(self):
        """
        买额度 -> 按当日额度全部卖出。
        只买一轮：用余额买到的额度是当日上限的一部分，卖出的 USDT 不再滚回去买额度，
        否则会陷入"卖出-买额度-再卖出"的自我消耗。
        """
        sells = []
        notes = []

        if ENV_BUY:
            ok, info = self.topup_quota()
            notes.append(("买额度 " + info) if ok else info)
            time.sleep(0.6)

        if ENV_SELL:
            got, reason = self.release_all()
            if got:
                sells = got
                notes.append("卖出 %d 笔" % len(got))
            else:
                notes.append("释放跳过: " + reason)

        return sells, notes


# ================================================================== 变量解析

def parse_accounts(raw):
    """
    解析 DOGE 变量。
    支持换行 / & / ; 分隔多账号，账号格式 邮箱#密码
    兼容中文冒号与全角字符
    """
    if not raw:
        return []
    raw = raw.replace("\\n", "\n").replace("\\r", "")
    parts = re.split(r"[\n\r&;]+", raw)
    out = []
    for seg in parts:
        seg = seg.strip()
        if not seg or "#" not in seg:
            continue
        email, _, pwd = seg.partition("#")
        email = email.strip()
        pwd = pwd.strip()
        if email and pwd:
            out.append((email, pwd))
    # 去重
    seen, uniq = set(), []
    for e, p in out:
        if e not in seen:
            seen.add(e)
            uniq.append((e, p))
    return uniq


# ================================================================== 单账号流程

def run_one(idx, total, email, password):
    tag = "[%d/%d]" % (idx, total)
    mask = email if "@" not in email else email.split("@")[0][:3] + "***@" + email.split("@")[1]
    print("\n%s ===== 账号 %s =====" % (tag, mask))
    logs = []

    bot = AiDoge(email, password, index=idx)
    bot.discover()
    bot.fetch_apikey()

    ok, info = bot.login()
    if not ok:
        print("%s 登录失败: %s" % (tag, info))
        return False, "登录失败: %s" % info
    print("%s 登录成功 uid=%s" % (tag, info))

    # 1) 签到
    ok, info = bot.checkin()
    print("%s 签到 %s" % (tag, ("领取完成 " + info) if ok else ("失败 " + info)))
    if ok:
        logs.append("签到 " + info)
    time.sleep(0.5)

    # 2) 完成任务（逐项执行，每项间隔 BEHAVIOR_DELAY 秒）
    print("%s 完成任务（间隔 %.1fs）" % (tag, BEHAVIOR_DELAY))
    items = list(BEHAVIOR_KINDS.values())
    for i, kind in enumerate(items, 1):
        label = KIND_LABELS.get(kind, kind)
        fresh = bot.report(kind)
        print("%s   [%d/%d] %-14s %s" % (
            tag, i, len(items), label, "任务完成" if fresh else "今日已完成"))
        if i < len(items):
            time.sleep(BEHAVIOR_DELAY)
    print("%s 任务完成 %d 项" % (tag, len(items)))

    # 3) 领取
    got = bot.claim_all()
    print("%s 领取完成 %d 项" % (tag, len(got)))
    logs += got

    # 4) 买额度 + 释放卖出
    sell_tag = "未启用"
    if ENV_SELL or ENV_BUY:
        sells, notes = bot.release_and_topup()
        for n in notes:
            print("%s %s" % (tag, n))
        if sells:
            qty = sum(s["qty"] for s in sells)
            usd = sum(s["turnover"] for s in sells)
            sell_tag = "卖出%.4f DOGE/%.4f USDT(%d笔)" % (qty, usd, len(sells))
            print("%s %s" % (tag, sell_tag))
            logs.append("释放 " + sell_tag)
        else:
            sell_tag = "未卖出"

    # 5) 挖矿
    mine_tag = "未启用"
    if ENV_MINE:
        bot.claim_all()
        ok, info = bot.mine()
        st = bot.mine_state
        if ok:
            mine_tag = "成功"
            print("%s 挖矿 成功 %s" % (tag, info))
            logs.append("挖矿 " + info)
        elif st == "skipped":
            mine_tag = "余额不足跳过"
            print("%s 挖矿 跳过：%s" % (tag, info))
            print("%s         门槛 %.0f（环境变量 %.0f）才投入，本次保持不动" % (
                tag, MINE_MIN_BALANCE, MINE_MIN_BALANCE))
        elif st == "zero":
            mine_tag = "无可投余额"
            print("%s 挖矿 跳过：%s" % (tag, info))
        elif st == "accepted":
            mine_tag = "已受理未变动"
            print("%s 挖矿 已受理但未变动：%s" % (tag, info))
        else:
            mine_tag = "失败"
            print("%s 挖矿 失败：%s" % (tag, info))

        # 只有真正发出投入请求才需要等异步奖励生成
        if st in ("ok", "accepted"):
            time.sleep(1.2)
            got2 = bot.claim_all()
            if got2:
                print("%s 挖矿后领取完成 %d 项" % (tag, len(got2)))
                logs += got2

    # 6) 状态
    b = bot.balance()
    run = [r for r in bot.mining_rows() if r.get("status") == "running"]
    principal = sum(tofloat(r.get("principal")) for r in run)
    panel = bot.quota_panel()
    q = (panel.get("quota") or {}) if isinstance(panel, dict) else {}
    summary = "DOGE=%s 冻结=%s 在挖=%d单/本金%s USDT=%s 今日剩余额度=%s" % (
        b.get("balance"), b.get("frozen"), len(run), fnum(principal),
        panel.get("usdt") if isinstance(panel, dict) else "?",
        q.get("remaining", "?"))
    print("%s %s" % (tag, summary))
    return True, "%s | 签到+奖励共 %d 项 | 释放=%s | 挖矿=%s | %s" % (
        mask, len(logs), sell_tag, mine_tag, summary)


# ================================================================== 主流程

def main():
    raw = os.getenv("DOGE", "").strip()
    accounts = parse_accounts(raw)
    if not accounts:
        print("未找到有效账号，请配置变量 DOGE，格式: 邮箱#密码 (多账号换行)")
        return 1

    print("=" * 62)
    print(" DOGE 自动   账号数: %d" % len(accounts))
    print("=" * 62)

    results = []
    for i, (email, pwd) in enumerate(accounts, 1):
        try:
            ok, msg = run_one(i, len(accounts), email, pwd)
        except Exception as e:
            ok, msg = False, "异常: %s" % e
            print("[%d/%d] 异常: %s" % (i, len(accounts), e))
        results.append((ok, msg))

    print("\n" + "=" * 62)
    print(" 执行汇总")
    print("=" * 62)
    succ = sum(1 for ok, _ in results if ok)
    for ok, msg in results:
        print(("✓ " if ok else "✗ ") + msg)
    print("\n成功 %d / 共 %d" % (succ, len(results)))

    if results:
        send_notify("DOGE 自动", "\n".join(
            ("✅ " if ok else "❌ ") + m for ok, m in results))
    return 0 if succ else 1


if __name__ == "__main__":
    sys.exit(main())


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