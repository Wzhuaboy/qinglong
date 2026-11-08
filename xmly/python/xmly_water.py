#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
喜马拉雅「喝水补贴」无限刷金币  ★ 实测可用（2026-10-14 实测连刷 60+ 次成功）

=====================================================================
原理（全部由抓包样本逐字节逆向确认，非猜测）
=====================================================================
喝水任务领奖**不需要任何广告凭证**，只要一条有效 XUID ticket：

    POST https://adse.wsa.ximalaya.com/incentive/ting/welfare/rewardGoldCoin/{ts}
         ?rn-credit-bundle-version=0.0.1176
    Cookie: 1&_device=android&<deviceId>&9.5.13;1&_token=<uid>&<token>;channel=and-d12;
            impl=com.ximalaya.ting.android;qimei36=<...>;osversion=36;fp=<...>
    User-Agent: ting_9.5.13(V2452A,Android36)
    body: {"requestId":"<uuid>","ts":<ms>,"coins":50,"sourceName":"DRINK_WATER_AGAIN",
           "rewardType":17,"ticket":"<TICKET>","signature":"<md5>","retry":0,"fallbackReq":0,
           "index":1,"startSource":"mine_page","roundId":"<uuid>"}
    → {"toast":"恭喜获得126金币","coins":126,"balance":21265,"success":true,"code":200}

签名公式（用两条抓包样本逐字节验证命中）：
    signature = md5(requestId & uid & rewardType & coins & ticket & ecpm & encryptType
                    & ts & retry & salt)
    salt = 0ab3443b71834b33be675af744d76ef0aaa74cd2b60c4b67   (= XUID_ticketConfig.coinTask.salt)
    喝水请求的 ecpm / encryptType 是空串

★★ 三个关键点（之前一直失败的原因）★★
  1. 主机是 **adse.wsa.ximalaya.com**（带 wsa），不是 adse.ximalaya.com
  2. **rewardType 必须用 17 (DRINK_WATER_AGAIN)**
         · 17 → 反复领，每次随机 100~190 金币，实测 60+ 次无上限
         · 16 (DRINK_WATER_NORMAL) → 该杯位领过后回 10003「您太热情了」
  3. 同一条 ticket 可重复使用；返回 10003 说明 ticket 过期，重新抓一条即可


=====================================================================
用法
=====================================================================
    # A) 从 HAR 抓包自动提取 ticket（推荐，一条命令搞定）
    python3 python/xmly_water.py from-har --in work/har/capture.har

    # B) 手动塞一条 ticket（从 rewardGoldCoin 请求体的 "ticket" 字段复制）
    python3 python/xmly_water.py set-ticket 'TACas82...'

    # C) 开刷
    python3 python/xmly_water.py status                       # 水杯 + 余额 + ticket
    python3 python/xmly_water.py once                         # 试一次
    python3 python/xmly_water.py farm --times 200 --interval 1.5
"""

import argparse
import gzip
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SESSION_FILE = os.path.join(ROOT, "session.json")
TICKET_FILE = os.path.join(ROOT, "work", "ticket.txt")

# 金币本账号表（accounts.js）：账号/密码 + 每日刷币额度
sys.path.insert(0, HERE)
try:
    import accounts as ACC
except Exception:                                    # 容错，不影响其它功能
    ACC = None

HOST = "https://adse.wsa.ximalaya.com/"
SALT = "0ab3443b71834b33be675af744d76ef0aaa74cd2b60c4b67"
BUNDLE_VER = "0.0.1176"
CTX = ssl.create_default_context()

# 抓包实测的 App 端 Cookie 形状（deviceId / qimei36 可换成自己的；服务端不严格校验）
APP_COOKIE_TAIL = ("channel=and-d12;impl=com.ximalaya.ting.android;"
                   "qimei36=0f03a024e94e1d063b1f4c1310001dc1a102;osversion=36;fp=009527657x2022q2")
UA_APP = "ting_9.5.13(V2452A,Android36)"
FALLBACK_TICKET = None   # 运行时从 work/accounts/<uid>/ticket.txt 读

# ★ 本地签票：文件里没有 ticket 就用 libnativelib.so 现签（不需要真机）
#   XMLY_MINT=0 可关掉；--no-mint 同效
DEVICE_FALLBACK = "a18bde8f-3964-347a-afc5-9b29fe592465"
MINT = os.environ.get("XMLY_MINT", "1") != "0"


def device_id(dev=None):
    """设备号：ticket 的 uuid 和 cookie 的 1&_device 必须用同一个。
    优先 accounts.js 顶层的 deviceId；没有就生成一个并落盘（每人一份，别共用）。"""
    if dev:
        return str(dev)
    if os.environ.get("XMLY_DEVICE"):
        return os.environ["XMLY_DEVICE"]
    if ACC is not None:
        try:
            cfg = ACC.load()
            d = cfg.get("deviceId")
            if d:
                return str(d)
            import uuid as _u
            d = str(_u.uuid4())
            cfg["deviceId"] = d
            ACC.save(cfg)
            print("[+] 已生成本机设备号并写入 accounts.js：%s" % d)
            return d
        except Exception:
            pass
    return DEVICE_FALLBACK


DEFAULT_DEVICE = DEVICE_FALLBACK   # 兼容旧引用

REWARD_TYPE = {
    "DRINK_WATER_NORMAL": 16,
    "DRINK_WATER_AGAIN": 17,      # ★ 无限刷，随机 100~190
    "DRINK_WATER_DOUBLE": 20,     # ★★ 无限刷，+610/次（最高）
    "SPINNING_WHEEL": 21,         # ★ 无限刷，+100/次
    "EXCHANGE_GIFT": 30,          # ★★ 无限刷，+500/次
    "FLIP": 7,                    # ★ 无限刷，+9/次
    "GAME_TASK": 33,              # ★ 无限刷，+10/次
    "NEW_SPINNING_WHEEL_PAGE": 35,  # 仅一次（+500）
    "EXCHANGE": 22,
    "AD_VIDEO": 5,
    "LISTEN_TASK": 12,
    "DAILY": 6,
    "EXTRA_REWARDS": 13,
    "SHARE_COINS": 15,            # 2026-10-21 真机 HAR 实锤（App 内点分享，coins=0 服务端定额）；门限待小量验证
}

# ★ 实测可无限刷的金矿（rewardType, sourceName, coins 参数, 单次约值）
#   扫描全 43 个 rewardType 得出；其余类型各有独立服务端门（见 FINDINGS §51/§55）
MINES = [
    (20, "DRINK_WATER_DOUBLE", 100, 610),   # 最高收益
    (30, "EXCHANGE_GIFT", 100, 500),
    (17, "DRINK_WATER_AGAIN", 50, 145),
    (21, "SPINNING_WHEEL", 100, 100),
]


# ------------------------------------------------------------------ 基础
# ★ 多账号：每个账号一份独立凭据（work/accounts/<uid>/{session.json,ticket.txt}）
#   旧路径（work/ticket.txt、根目录 session.json）只作兜底，并且必须解出 uid 比对，
#   绝不把 A 账号的 ticket / token 用到 B 账号上。
CUR_UID = None          # 由 --uid 设定；None → 用 accounts.js 的 activeUid


def _uid_or_active(uid=None):
    if uid:
        return str(uid)
    if CUR_UID:
        return str(CUR_UID)
    if ACC is not None:
        try:
            u = ACC.active_uid()
            if u:
                return str(u)
        except Exception:
            pass
    return load_uid_from_session()


def _b64_any(seg):
    """ticket 用的是 url-safe base64（含 - 和 _），标准 b64decode 会把它们丢掉导致错位"""
    import base64
    s = seg.replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    return base64.b64decode(s, validate=False)


def _ticket_plain(ticket):
    """穷举起始偏移，取最长的可读串（base64 边界不对齐，实测 off=35 才对齐到明文）"""
    if not ticket:
        return None
    best = None
    for off in range(0, 90):
        seg = ticket[off:]
        if len(seg) < 20:
            break
        try:
            d = _b64_any(seg)
        except Exception:
            continue
        for m in re.finditer(rb"[ -~]{16,}", d):
            s = m.group()
            if best is None or len(s) > len(best):
                best = s
    return best


def ticket_uid(ticket):
    """解出 ticket 绑定的 uid（明文尾巴 `…!b=<biz>&s=<scene>&u=<uid>`）"""
    plain = _ticket_plain(ticket)
    if not plain:
        return None
    m = re.search(rb"u=(\d+)", plain)
    return m.group(1).decode() if m else None


def ticket_scope(ticket):
    """解出 ticket 的 b=/s=（业务/场景），用于判断它是不是金币场景的 ticket"""
    plain = _ticket_plain(ticket)
    if not plain:
        return None
    m = re.search(rb"b=([a-z_]+)&s=([a-z_]+)", plain)
    return (m.group(1).decode(), m.group(2).decode()) if m else None


def load_account(uid=None):
    """从 accounts.js 取账号（含账号/密码）"""
    if ACC is None:
        return None
    try:
        return ACC.pick(uid=_uid_or_active(uid))
    except Exception:
        return None


def load_uid_from_session(uid=None):
    p = ACC.session_path(uid) if (ACC and uid) else SESSION_FILE
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                s = json.load(f)
            for k in ("uid", "userId"):
                if s.get(k):
                    return str(s[k])
        except Exception:
            pass
    return None


def load_uid(uid=None):
    u = _uid_or_active(uid)
    if u:
        return str(u)
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, encoding="utf-8") as f:
                s = json.load(f)
            for k in ("uid", "userId"):
                if s.get(k):
                    return str(s[k])
        except Exception:
            pass
    return "608255219"


def _session_files(uid):
    """该账号的 session 候选：账号目录，再旧的全局 session.json"""
    out = []
    if ACC and uid:
        out.append(ACC.session_path(uid))
    elif uid:
        # ACC 加载失败时（如旧版 accounts.py 在 Windows 上缺 fcntl），
        # 手工补上与 import-session 写入一致的账号目录路径，避免读写不一致读不到 token
        out.append(os.path.join(ROOT, "work", "accounts", str(uid), "session.json"))
    out.append(SESSION_FILE)
    return out


def load_token(uid=None):
    uid = _uid_or_active(uid)
    # 环境变量 XMLY_TOKEN 优先级最高（慕斯加，仿 XMLY_DEVICE 的官方后门）：
    # 青龙面板里把 token 填进环境变量即可，免 import-session、免 session.json。
    # 值粘贴「608776240&xxxx」原值或带 1&_token= 前缀的整段都认。
    env_tok = (os.environ.get("XMLY_TOKEN") or "").strip().strip('"').strip("'")
    if env_tok.startswith("1&_token="):
        env_tok = env_tok[len("1&_token="):].split(";")[0].strip()
    if env_tok:
        tok_uid = env_tok.split("&")[0]
        if not uid or not tok_uid or tok_uid == str(uid):
            return env_tok
    for p in _session_files(uid):
        if not os.path.exists(p):
            continue
        try:
            with open(p, encoding="utf-8") as f:
                s = json.load(f)
        except Exception:
            continue
        ck = s.get("cookie") or ""
        m = re.search(r"1&_token=([^;]+)", ck)
        if not m:
            continue
        tok = m.group(1)
        # ★ 防串号：session 自身 uid / token 前缀 uid 必须与目标账号一致
        su = str(s.get("uid") or s.get("userId") or "")
        tok_uid = tok.split("&")[0]
        if uid and su and su != str(uid):
            continue
        if uid and tok_uid and tok_uid != str(uid):
            continue
        return tok
    return None


def _ticket_files(uid):
    out = []
    if ACC and uid:
        out.append(ACC.ticket_path(uid))
    out.append(TICKET_FILE)          # 旧路径兜底
    return out


def mint_ticket(uid, device=None, scope=("incentives", "gold_reward")):
    """★ 本地现签一条 ticket（不需要真机 / 不需要抓包）。
    原理见 python/xmly_ticket.py：Unicorn 跑 libnativelib.so 的 getTicket()。"""
    sys.path.insert(0, HERE)
    import xmly_ticket as T
    return T.mint(str(uid), device=device_id(device), scope=scope)


def load_ticket(uid=None, allow_mint=None):
    uid = _uid_or_active(uid)
    for p in _ticket_files(uid):
        if not os.path.exists(p):
            continue
        t = open(p, encoding="utf-8").read().strip()
        if not t:
            continue
        tu = ticket_uid(t)
        # ★ 防串号：ticket 里带的 u= 必须等于目标 uid
        if uid and tu and str(tu) != str(uid):
            continue
        sc = ticket_scope(t)
        # 场景不对（不是金币场景）的 ticket 用了也是 10003，直接跳过
        if sc and sc[1] not in ("gold_reward", "gold_reward_again"):
            continue
        return t
    # ★ 文件里没有 → 本地现签（不再需要真机抓包）
    want_mint = MINT if allow_mint is None else allow_mint
    if uid and want_mint:
        try:
            tk = mint_ticket(uid)
            print("[+] 本地签发 ticket：uid=%s (%d 字节)" % (uid, len(tk)))
            return tk
        except Exception as e:
            print("[!] 本地签发失败（回退到已存 ticket）：%s" % e)
    return FALLBACK_TICKET if not uid else None


def save_ticket(t, uid=None):
    uid = _uid_or_active(uid)
    p = ACC.ticket_path(uid) if (ACC and uid) else TICKET_FILE
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(t.strip())
    tu = ticket_uid(t)
    warn = ""
    if tu and uid and str(tu) != str(uid):
        warn = "  ⚠ 该 ticket 绑定 uid=%s，与账号 %s 不符！" % (tu, uid)
    print("[+] ticket 已保存 → %s%s" % (p, warn))
    return p


def build_cookie(device=None, uid=None):
    uid = _uid_or_active(uid)
    tok = load_token(uid) or (str(uid) + "&")
    return "1&_device=android&%s&9.5.13;1&_token=%s;%s" % (device_id(device), tok, APP_COOKIE_TAIL)


def http(method, path, body=None, cookie=None, timeout=20):
    h = {"User-Agent": UA_APP, "Accept": "*/*", "Accept-Encoding": "gzip",
         "Cookie": cookie or build_cookie()}
    data = None
    if body is not None:
        h["Content-Type"] = "application/json; charset=utf-8"
        data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(HOST + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return resp.status, raw.decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            if e.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
        except Exception:
            pass
        return e.code, raw.decode("utf-8", "replace")
    except Exception as e:
        return -1, json.dumps({"error": str(e)}, ensure_ascii=False)


def jget(body):
    try:
        return json.loads(body)
    except Exception:
        return {}


# ------------------------------------------------------------------ 查询
def balance():
    st, b = http("GET", "incentive/ting/welfare/queryGoldCoinPage/%d"
                 "?transactionType=1&requestVersion=20250520&rn-credit-bundle-version=%s"
                 % (int(time.time() * 1000), BUNDLE_VER))
    return (jget(b).get("data") or {}).get("coins")


def water_state():
    st, b = http("GET", "incentive/ting/welfare/queryWaterInfo/%d?rn-credit-bundle-version=%s"
                 % (int(time.time() * 1000), BUNDLE_VER))
    d = jget(b).get("data") or {}
    return [(w.get("index"), w.get("status"), w.get("coins")) for w in (d.get("waterInfo") or [])]


# ------------------------------------------------------------------ 刷
def drink(ticket=None, index=1, rtype=17, coins=50, uid=None):
    """单次领喝水奖励。rewardType=17 才能反复领。"""
    ticket = ticket or load_ticket()
    if not ticket:
        print("[!] 没有 ticket：先 from-har 或 set-ticket")
        return None
    uid = uid or load_uid()
    rid = str(uuid.uuid4())
    ts = int(time.time() * 1000)
    sig = hashlib.md5(("%s&%s&%d&%d&%s&&&%d&0&%s"
                       % (rid, uid, rtype, coins, ticket, ts, SALT)).encode()).hexdigest()
    body = {"requestId": rid, "ts": ts, "coins": coins,
            "sourceName": "DRINK_WATER_AGAIN" if rtype == 17 else "DRINK_WATER_NORMAL",
            "rewardType": rtype, "ticket": ticket, "signature": sig,
            "retry": 0, "fallbackReq": 0, "index": index,
            "startSource": "mine_page", "roundId": str(uuid.uuid4())}
    st, b = http("POST", "incentive/ting/welfare/rewardGoldCoin/%d"
                 "?rn-credit-bundle-version=%s" % (ts, BUNDLE_VER), body)
    return jget(b).get("data") or {"_raw": b[:200]}



def reward(rtype, source, coins=100, index=1, ticket=None, extra=None):
    """通用发奖调用（供 mega / 各金矿复用）"""
    ticket = ticket or load_ticket()
    uid = load_uid()
    rid = str(uuid.uuid4())
    ts = int(time.time() * 1000)
    sig = hashlib.md5(("%s&%s&%d&%d&%s&&&%d&0&%s"
                       % (rid, uid, rtype, coins, ticket, ts, SALT)).encode()).hexdigest()
    body = {"requestId": rid, "ts": ts, "coins": coins, "sourceName": source,
            "rewardType": rtype, "ticket": ticket, "signature": sig,
            "retry": 0, "fallbackReq": 0, "index": index,
            "startSource": "mine_page", "roundId": str(uuid.uuid4())}
    if extra:
        body.update(extra)
    st, b = http("POST", "incentive/ting/welfare/rewardGoldCoin/%d"
                 "?rn-credit-bundle-version=%s" % (ts, BUNDLE_VER), body)
    return jget(b).get("data") or {"_raw": b[:200]}


def do_share(times, interval):
    """分享得金币（rewardType=15，SHARE_COINS）。2026-10-21 真机 HAR 样本：
    App 内点分享时 coins 传 0、金额由服务端定。服务端门限未知 → 小量试探，
    连续失败 2 次即停，避免硬敲触发限频/风控。"""
    tk = load_ticket()
    if not tk:
        print("[!] 缺 ticket：python3 python/xmly_water.py from-har --in <har>")
        return
    allowed, acc, cfg, msg = _limit_gate()
    print("金币本额度: %s" % msg)
    if not allowed:
        return
    print("起始余额: %s" % balance())
    ok = total = 0
    fails = 0
    for i in range(times):
        d = reward(15, "SHARE_COINS", 0, ticket=tk)
        if d.get("success"):
            ok += 1
            fails = 0
            got = d.get("coins") or 0
            total += got
            _realtime_bump(acc, got, balance=d.get("balance"))
            print("  #%d ✔ +%-5s 余额 %-7s %s" % (i + 1, got, d.get("balance"), d.get("toast") or ""))
        else:
            fails += 1
            print("  #%d ✘ code=%-6s %s" % (i + 1, d.get("code"), d.get("toast") or d.get("_raw") or ""))
            if fails >= 2:
                print("  连续失败 2 次，停（多半已达今日门限或被限频）")
                break
        if i + 1 < times:
            time.sleep(interval)
    print("分享金币：成功 %d 次，合计 +%d，末次余额 %s" % (ok, total, balance()))


def do_mega(times, interval):
    """★ 终极金矿：循环刷 MINES 里所有类型（20/30/17/21）"""
    tk = load_ticket()
    if not tk:
        print("[!] 缺 ticket：python3 python/xmly_water.py from-har --in <har>")
        return
    allowed, acc, cfg, msg = _limit_gate()
    print("金币本额度: %s" % msg)
    if not allowed:
        return
    start_bal = balance()
    if ACC is not None and acc is not None:
        _reset, acc = ACC.refresh_day(acc, balance=start_bal)
        if _reset:
            print("★ 新的一天，今日已刷已归零")
    cfg = (ACC.load() if ACC is not None else cfg) or cfg
    limit = int((cfg or {}).get("dailyLimit") or 100000)
    done = int((acc or {}).get("todayFarmed") or 0)
    if ACC is not None and acc is not None and acc.get("lastBalance") is None and start_bal is not None:
        ACC.bump(acc, 0, balance=start_bal)
    print("起始余额: %s" % start_bal)
    print("（每出一笔都会实时写入 accounts.js，中断也不丢计数）")
    stat = {m[0]: [0, 0] for m in MINES}
    failstat = {}
    bal = None
    # ★ 开刷前先低频试分享金币（rewardType=15）：10067 是冷却门，隔 60 秒重试，最多 3 次
    s_ok = s_tot = 0
    for k in range(3):
        d = reward(15, "SHARE_COINS", 0, ticket=tk)
        if d.get("success"):
            got = d.get("coins") or 0
            s_ok += 1
            s_tot += got
            bal = d.get("balance")
            _realtime_bump(acc, got, balance=bal)
            print("  [分享] ✔ +%s 余额 %s" % (got, bal))
            break
        print("  [分享] ✘ code=%s %s" % (d.get("code"), d.get("toast") or ""))
        if d.get("code") != 10067 or k == 2:
            break
        time.sleep(60)
    try:
        for i in range(times):
            rtype, source, coins, _ = MINES[i % len(MINES)]
            d = reward(rtype, source, coins, ticket=tk)
            if d.get("success"):
                got = d.get("coins") or 0
                stat[rtype][0] += 1
                stat[rtype][1] += got
                bal = d.get("balance")
                _realtime_bump(acc, got, balance=bal)              # ★ 实时写盘
            elif d.get("code") == 10003:
                failstat[10003] = failstat.get(10003, 0) + 1   # 该类型暂时用尽，继续下一个
            else:
                _c = d.get("code")
                failstat[_c] = failstat.get(_c, 0) + 1
            if (i + 1) % 16 == 0:
                tot = sum(v[1] for v in stat.values())
                a2 = (ACC.pick(uid=acc.get("uid")) if (ACC and acc) else None) or {}
                print("  [%d] %s | 合计 +%d | 今日已刷 %s | 余额 %s" % (
                    i + 1, " ".join("t%d:%d次+%d" % (rt, v[0], v[1]) for rt, v in stat.items()),
                    tot, a2.get("todayFarmed"), bal))
            if ACC is not None and acc is not None and (i + 1) % 10 == 0:
                acc = ACC.reload_account(acc)
                done = int(acc.get("todayFarmed") or 0)
            if done >= limit:
                print("     ★ 今日已刷达上限 %d，停止" % limit)
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[!] 收到中断；已实时落盘，进度不会丢")
    tot = sum(v[1] for v in stat.values())
    print("\n=== 战果 ===")
    for rt, v in stat.items():
        name = dict((m[0], m[1]) for m in MINES)[rt]
        print("  rewardType=%-3s %-22s %4d 次  +%d" % (rt, name, v[0], v[1]))
    if s_ok:
        print("  rewardType=%-3s %-22s %4d 次  +%d" % (15, "SHARE_COINS", s_ok, s_tot))
    if failstat:
        print("  未成功原因统计: %s" % (failstat,))
    end_bal = balance()
    print("  合计 +%d，余额 %s" % (tot + s_tot, end_bal))
    if ACC is not None and acc is not None:
        a2 = ACC.pick(uid=acc.get("uid")) or acc
        real = max(0, (end_bal or 0) - (start_bal or 0))
        ledger = int(a2.get("todayFarmed") or 0)
        if abs(ledger - (done + real)) > 5:
            print("  [i] 口径校验：账本 %s，余额 delta %s（App 端可能同时在赚）" % (ledger, done + real))
        ACC.bump(a2, 0, balance=end_bal)
        print("★ 金币本：今日已刷 %s / %s" % (a2.get("todayFarmed"), limit))


def _limit_gate():
    """返回 (allowed, account, cfg, msg)"""
    if ACC is None:
        return True, None, None, "（无 accounts.js，不限额）"
    acc = load_account()
    cfg = ACC.load()
    ok, msg = ACC.check_limit(acc, cfg)
    return ok, acc, cfg, msg


def _realtime_bump(acc, coins, balance=None):
    """★ 实时落盘：每出一笔就把金币写进 accounts.js（进程被杀也不丢计数）"""
    if ACC is None or acc is None:
        return None
    try:
        ACC.bump(acc, coins, balance=balance)
    except Exception as e:
        print("     [warn] accounts.js 回写失败: %s" % e)
    return acc.get("todayFarmed")


def do_farm(times, interval, index=1, rtype=17):
    tk = load_ticket()
    if not tk:
        print("[!] 缺 ticket：python3 python/xmly_water.py from-har --in work/har/capture.har")
        return
    allowed, acc, cfg, msg = _limit_gate()
    print("金币本额度: %s" % msg)
    if not allowed:
        return
    start_bal = balance()
    if ACC is not None and acc is not None:
        _reset, acc = ACC.refresh_day(acc, balance=start_bal)     # ★ 跨天自动归零并落盘
        if _reset:
            print("★ 新的一天，今日已刷已归零")
    cfg = (ACC.load() if ACC is not None else cfg) or cfg
    limit = int((cfg or {}).get("dailyLimit") or 100000)
    done = int((acc or {}).get("todayFarmed") or 0)
    if ACC is not None and acc is not None and acc.get("lastBalance") is None and start_bal is not None:
        ACC.bump(acc, 0, balance=start_bal)
    print("起始余额: %s   water: %s" % (start_bal, water_state()))
    print("（每出一笔都会实时写入 accounts.js，中断也不丢计数）")
    ok = total = 0
    bal = None
    try:
        for i in range(times):
            d = drink(tk, index=index, rtype=rtype)
            if d is None:
                return
            if d.get("success"):
                ok += 1
                got = d.get("coins") or 0
                total += got
                bal = d.get("balance")
                now_done = _realtime_bump(acc, got, balance=bal)      # ★ 实时写盘
                print("  #%3d ✔ +%-5s 余额 %-7s 今日已刷 %-8s %s" % (
                    i + 1, got, bal, now_done, d.get("toast") or ""))
            else:
                code = d.get("code")
                print("  #%3d ✘ code=%-6s %s" % (i + 1, code, d.get("toast") or d.get("_raw")))
                if code == 10003:
                    print("     → ticket 失效：在 App 里重新领一次喝水，再 from-har 取新 ticket")
                    break
                if code in (10015, 20001, -200):
                    print("     → 触发风控限频，建议冷却后把 --interval 调大到 4~5 秒再跑")
                    break
                if ok == 0:
                    print("     → 首刷即失败，检查 ticket / 会话")
                    break
            # ★ 每 10 次重读文件：跨进程共享额度（别的进程刷的也算进来）
            if ACC is not None and acc is not None and (i + 1) % 10 == 0:
                acc = ACC.reload_account(acc)
                done = int(acc.get("todayFarmed") or 0)
            # ★ 日限额：达到上限立即停
            if done >= limit:
                print("     ★ 今日已刷 %d / 上限 %d，达到上限，停止" % (done, limit))
                break
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[!] 收到中断；已实时落盘，进度不会丢")
    end_bal = balance()
    print("\n成功 %d 次，合计 %d 金币，末次余额 %s" % (ok, total, bal))
    print("最终余额:", end_bal)
    if ACC is not None and acc is not None:
        a2 = ACC.pick(uid=acc.get("uid")) or acc
        real = max(0, (end_bal or 0) - (start_bal or 0))
        ledger = int(a2.get("todayFarmed") or 0)
        if abs(ledger - (done + real)) > 5:
            print("[i] 口径校验：账本 %s，余额 delta %s，差 %s（App 端可能同时在赚）"
                  % (ledger, done + real, ledger - (done + real)))
        ACC.bump(a2, 0, balance=end_bal)
        print("★ 金币本：今日已刷 %s / %s" % (a2.get("todayFarmed"), limit))


# ------------------------------------------------------------------ 会话导入
def import_session(uid, token_value, phone=None, nickname=None, verify=True):
    """把网页扫码拿到的 `1&_token=<uid>&<token>` 落成该账号的 session.json

    网页（Cloudflare Worker）扫完码只回显 token，落盘还是在本机做，
    所以这里是最短的那一步：一条命令把账号接进金币本。
    """
    import datetime
    uid = str(uid).strip()
    token_value = (token_value or "").strip()
    if not uid or not token_value:
        print("[!] 需要 --uid 和 --token（网页上「Token」那一栏）")
        return None
    if not token_value.startswith(uid + "&") and "&" not in token_value:
        print("[!] token 形状不对，应该是 `%s&<token>`；网页上直接复制整栏即可" % uid)
    sess = {
        "uid": int(uid) if uid.isdigit() else uid,
        "cookie": "1&_token=" + token_value,
        "source": "qr-web",
        "saved_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    p = ACC.session_path(uid) if ACC else os.path.join(ROOT, "work", "accounts", uid, "session.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(sess, f, ensure_ascii=False, indent=2)
    os.chmod(p, 0o600)
    print("[+] 会话已落盘 → %s" % p)

    if ACC is not None:
        existing = ACC.pick(uid=uid)
        if not existing:
            cur = ACC.add_account(phone, None, uid, nickname or ("听友" + uid))
            print("[+] 已登记到 accounts.js：uid=%s" % uid)
        else:
            cur = existing
            if phone or nickname:
                cur = ACC.add_account(phone or existing.get("phone"), None, uid,
                                      nickname or existing.get("nickname"))
        ACC.set_active_uid(uid)
        print("[+] 已设为默认账号")

    global CUR_UID
    CUR_UID = uid
    if verify:
        bal = balance()
        print("[*] 会话校验：余额 = %s" % bal)
        if bal is None:
            print("    ⚠ 拿不到余额，token 可能无效或已过期")
        else:
            tk = load_ticket(uid)
            print("[*] ticket：%s" % ("✔ 已有" if tk else "✘ 还缺（App 里领一次喝水后 from-har 导入）"))
    return p


# ------------------------------------------------------------------ HAR 提取
def from_har(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        har = json.load(f)
    entries = har.get("log", {}).get("entries", [])
    found = []
    for e in entries:
        req = e.get("request", {})
        pd = (req.get("postData") or {}).get("text") or ""
        if "rewardGoldCoin" in req.get("url", "") and "ticket" in pd:
            try:
                body = json.loads(pd)
            except Exception:
                continue
            resp = ((e.get("response", {}).get("content") or {}).get("text") or "")
            found.append((req["url"], body, resp))
    if not found:
        print("[!] HAR 里没有 rewardGoldCoin 请求。请在 App 里成功领一次喝水再抓。")
        return None
    best = None
    for url, body, resp in found:
        sc = 0
        if body.get("rewardType") == 17:
            sc += 5
        if body.get("rewardType") == 16:
            sc += 3
        if body.get("ticket"):
            sc += 2
        if '"success": true' in resp or '"success":true' in resp:
            sc += 2
        if best is None or sc > best[0]:
            best = (sc, url, body, resp)
    _, url, body, resp = best
    tk = body.get("ticket")
    # ★ ticket 自带 uid（u=<uid>）→ 按它的归属账号存，避免抓谁的包存到别人头上
    global CUR_UID
    tu = ticket_uid(tk)
    if tu:
        CUR_UID = tu
        if ACC is not None and not ACC.pick(uid=tu):
            ACC.add_account(phone=None, uid=tu, nickname="听友" + tu)
            print("[+] 新账号已登记到 accounts.js：uid=%s" % tu)
    save_ticket(tk, uid=tu)
    if tu:
        tpath = ACC.ticket_path(tu) if ACC else None
        print("    该 ticket 归属 uid=%s → 独立存放%s" % (tu, "  " + tpath if tpath else ""))
    sfile = os.path.join(ROOT, "work", "water_sample.json")
    with open(sfile, "w", encoding="utf-8") as f:
        json.dump({"url": url, "body": body, "response": resp[:1500]}, f, ensure_ascii=False, indent=2)
    print("[+] 完整样本 → %s" % sfile)
    print("    rewardType=%s coins=%s index=%s sourceName=%s" % (
        body.get("rewardType"), body.get("coins"), body.get("index"), body.get("sourceName")))
    print("    ticket=%s…" % tk[:44])
    print("    从 %d 条 rewardGoldCoin 捕获中选出" % len(found))
    return tk


# ------------------------------------------------------------------ main
def _list_accounts():
    """列出 accounts.js 里的账号 + 各自凭据齐备情况"""
    if ACC is None:
        print("无 accounts.js")
        return
    cfg = ACC.load()
    act = ACC.active_uid()
    print("dailyLimit = %s    activeUid = %s" % (cfg.get("dailyLimit"), act))
    for a in cfg.get("accounts") or []:
        uid = str(a.get("uid") or "")
        global CUR_UID
        CUR_UID = uid or None
        tk = load_ticket(uid)
        tok = load_token(uid)
        bal = None
        try:
            bal = ACC.check_limit(a, cfg)
        except Exception:
            pass
        print("\n  ● %s  uid=%s  %s" % (a.get("phone") or "(未填手机号)", uid,
                                        a.get("nickname") or ""))
        print("      登录会话: %s" % ("✔ 有 token" if tok else "✘ 缺（要登录一次）"))
        print("      ticket  : %s" % ("✔ " + tk[:28] + "…" if tk else "✘ 缺（要抓一次 / 或本地生成）"))
        if tk:
            tu = ticket_uid(tk)
            print("               绑定 uid=%s %s" % (tu, "✔ 一致" if tu == uid else "⚠ 不一致！"))
        print("      今日已刷: %s  %s" % (a.get("todayFarmed"),
                                         ("→ " + bal[1]) if bal and bal[1] else ""))
    CUR_UID = None


def main():
    ap = argparse.ArgumentParser(description="喝水无限刷金币（rewardType=17）")
    ap.add_argument("--uid", default=None, help="指定账号 uid（默认用 accounts.js 的 activeUid）")
    ap.add_argument("--no-mint", action="store_true",
                    help="禁用本地签票（默认文件里没有 ticket 就本地现签）")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    sub.add_parser("once")
    sub.add_parser("accounts", help="列出金币本所有账号与凭据状态")
    p_mint = sub.add_parser("mint", help="本地签发 ticket（不需要真机）")
    p_mint.add_argument("--save", action="store_true", help="写入该账号的 ticket.txt")
    p_use = sub.add_parser("use", help="切换默认账号")
    p_use.add_argument("uid")
    p_add = sub.add_parser("add-account", help="新增账号到金币本")
    p_add.add_argument("--phone", default=None)
    p_add.add_argument("--password", default=None)
    p_add.add_argument("--uid", dest="new_uid", default=None)
    p_add.add_argument("--nickname", default=None)
    p_add.add_argument("--activate", action="store_true", help="新增后设为默认账号")
    p_rm = sub.add_parser("remove-account", help="从金币本移除账号（含其凭据目录）")
    p_rm.add_argument("uid")
    p_f = sub.add_parser("farm")
    p_f.add_argument("--times", type=int, default=100)
    p_f.add_argument("--interval", type=float, default=1.5)
    p_f.add_argument("--index", type=int, default=1)
    p_f.add_argument("--reward-type", type=int, default=17)
    p_l = sub.add_parser("limit")
    p_l.add_argument("--set", type=int, default=None, help="改每日上限")
    p_l.add_argument("--today", type=int, default=None, help="改今日已刷值")
    p_l.add_argument("--reset", action="store_true", help="今日已刷归零")
    p_m = sub.add_parser("mega")
    p_m.add_argument("--times", type=int, default=200)
    p_m.add_argument("--interval", type=float, default=1.5)
    p_s = sub.add_parser("share", help="分享得金币（rewardType=15，小量试探）")
    p_s.add_argument("--times", type=int, default=5)
    p_s.add_argument("--interval", type=float, default=5)
    p_h = sub.add_parser("from-har")
    p_h.add_argument("--in", dest="infile", required=True)
    p_t = sub.add_parser("set-ticket")
    p_t.add_argument("ticket")
    p_i = sub.add_parser("import-session", help="导入网页扫码拿到的 token，生成该账号会话")
    p_i.add_argument("--uid", dest="s_uid", required=True)
    p_i.add_argument("--token", required=True, help="网页上 1&_token 的完整值（<uid>&<token>）")
    p_i.add_argument("--phone", default=None)
    p_i.add_argument("--nickname", default=None)
    p_i.add_argument("--no-verify", action="store_true")
    args = ap.parse_args()

    # --uid 全局生效（cmd 上的 --uid 优先）
    global CUR_UID, MINT
    nsu = getattr(args, "new_uid", None)
    CUR_UID = args.uid or None
    if getattr(args, "no_mint", False):
        MINT = False

    cmd = args.cmd or "status"
    if cmd == "accounts":
        _list_accounts()
        return
    if cmd == "mint":
        u = _uid_or_active()
        if not u:
            print("需要 uid：--uid <uid>")
            return
        try:
            tk = mint_ticket(u)
        except Exception as ex:
            print("[!] 签发失败:", ex)
            return
        print("uid    =", u)
        print("长度   =", len(tk))
        print("ticket =", tk)
        print("内嵌 uid =", ticket_uid(tk))
        if args.save:
            save_ticket(tk, uid=u)
        return
    if cmd == "use":
        u = ACC.set_active_uid(args.uid) if ACC else None
        print("默认账号 → uid=%s" % u)
        _list_accounts()
        return
    if cmd == "add-account":
        if ACC is None:
            print("无 accounts.js")
            return
        cur = ACC.add_account(args.phone, args.password, nsu, args.nickname)
        print("已加入金币本:", json.dumps(cur, ensure_ascii=False))
        if args.activate:
            ACC.set_active_uid(cur.get("uid"))
            print("已设为默认账号")
        print()
        print("该账号还差两样才能刷：")
        print("  ① 登录会话（1&_token）→ python3 python/xmly_session.py --uid %s qr" % cur.get("uid"))
        print("  ② ticket             → App 里领一次喝水，抓包后 from-har --in <har>")
        return
    if cmd == "remove-account":
        if ACC is None:
            print("无 accounts.js")
            return
        cfg = ACC.load()
        before = len(cfg.get("accounts") or [])
        cfg["accounts"] = [a for a in (cfg.get("accounts") or [])
                           if str(a.get("uid")) != str(args.uid)]
        if cfg.get("activeUid") and str(cfg["activeUid"]) == str(args.uid):
            cfg.pop("activeUid", None)
        ACC.save(cfg)
        print("已从 accounts.js 移除 uid=%s（%d → %d 个账号）"
              % (args.uid, before, len(cfg["accounts"])))
        import shutil
        d = os.path.join(os.path.dirname(HERE), "work", "accounts", str(args.uid))
        if os.path.isdir(d):
            shutil.rmtree(d)
            print("已删除凭据目录:", d)
        return
    if cmd == "status":
        print("账号 uid:", _uid_or_active())
        print("水杯 (index,status,coins):", water_state())
        print("金币余额:", balance())
        tk = load_ticket()
        print("ticket:", (tk[:44] + "…") if tk else "（无，先 from-har 或 set-ticket）")
        if ACC is not None:
            a = load_account()
            _r, a = ACC.refresh_day(a, balance=balance())
            if _r:
                print("金币本: ★ 新的一天，今日已刷已归零")
            _ok, _msg = ACC.check_limit(a, ACC.load())
            print("金币本: %s  %s" % ("可继续" if _ok else "★今日已刷满", _msg))
    elif cmd == "once":
        d = drink()
        print(json.dumps(d, ensure_ascii=False)[:400] if d else "无 ticket")
        print("余额:", balance())
    elif cmd == "farm":
        do_farm(args.times, args.interval, args.index, args.reward_type)
    elif cmd == "limit":
        if ACC is None:
            print("无 accounts.js")
            return
        _r, _a = ACC.refresh_day(load_account(), balance=balance())   # 跨天自动归零并落盘
        if _r:
            print("★ 新的一天，今日已刷已归零")
        cfg = ACC.load()
        acc = load_account()
        if args.set is not None:
            cfg["dailyLimit"] = args.set
            ACC.save(cfg)
            print("每日上限 →", args.set)
        if args.reset:
            ACC.set_today(0, acc=acc, balance=balance())
            print("今日已刷已归零")
        if args.today is not None:
            ACC.set_today(args.today, acc=acc, balance=balance())
            print("今日已刷 →", args.today)
        cfg = ACC.load()
        a = load_account()
        ok, msg = ACC.check_limit(a, cfg)
        print("账号 %s  uid=%s" % ((a or {}).get("phone"), (a or {}).get("uid")))
        print("  dailyLimit   = %s" % cfg.get("dailyLimit"))
        print("  todayFarmed  = %s" % (a or {}).get("todayFarmed"))
        print("  date         = %s" % (a or {}).get("date"))
        print("  状态         = %s" % ("可继续" if ok else "今日已刷满，停止"))
        print("  %s" % msg)
    elif cmd == "mega":
        do_mega(args.times, args.interval)
    elif cmd == "share":
        do_share(args.times, args.interval)
    elif cmd == "from-har":
        from_har(args.infile)
    elif cmd == "set-ticket":
        save_ticket(args.ticket)
        d = drink()
        print("试刷一次:", json.dumps(d, ensure_ascii=False)[:200] if d else "失败")
    elif cmd == "import-session":
        import_session(args.s_uid, args.token, args.phone, args.nickname,
                       verify=not args.no_verify)


if __name__ == "__main__":
    main()
