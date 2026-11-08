#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
accounts.js 读写（金币本账号表）—— 支持实时落盘与并发安全

accounts.js 是 JS 模块，但内容保持 JSON 兼容，这里用「剥掉 // 注释 → 再剥
module.exports 包裹」的方式解析（顺序反了会解析失败），避免为了读一个配置去跑 node。

并发安全：
  · 进程内  threading.RLock
  · 跨进程  fcntl.flock（.accounts.lock）
  · 写盘    temp 文件 + os.replace（原子替换，读方永不会看到半截文件）

对外接口：
  load() / accounts() / pick(uid,phone) / save(cfg)
  bump(acc, delta, balance=None)   累加今日已刷并立即落盘（跨天自动归零）
  check_limit(acc, cfg) -> (bool, msg)
"""

import datetime
import json
import os
import re
import tempfile
import threading

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:  # Windows 上没有 fcntl：退化为进程内锁 + 原子写盘
    fcntl = None
    _HAS_FCNTL = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATHS = [os.path.join(ROOT, "accounts.js"),
         os.path.join(ROOT, "python", "accounts.js")]
DEFAULT_LIMIT = 100000

_LOCK = threading.RLock()
_CTX = threading.local()


class _FileLock:
    """跨进程文件锁（可重入：同线程内嵌套只加一次）"""

    def __init__(self, path):
        self.path = path + ".lock"
        self.fh = None
        self.depth = getattr(_CTX, "depth", 0)

    def __enter__(self):
        if self.depth == 0:
            self.fh = open(self.path, "a+")
            if _HAS_FCNTL:
                fcntl.flock(self.fh.fileno(), fcntl.LOCK_EX)
        _CTX.depth = self.depth + 1
        return self

    def __exit__(self, *exc):
        _CTX.depth = max(0, getattr(_CTX, "depth", 1) - 1)
        if self.depth == 0 and self.fh is not None:
            try:
                if _HAS_FCNTL:
                    fcntl.flock(self.fh.fileno(), fcntl.LOCK_UN)
                self.fh.close()
            except Exception:
                pass
            self.fh = None
        return False


HEADER = """// ============================================================================
//  喜马拉雅金币本 —— 账号与每日刷币额度
//  由 python/xmly_water.py 实时读写（每出一笔金币就落盘，中断不丢计数）
//  规则：todayFarmed 达到 dailyLimit(默认 100000) 就停止当天刷币
// ============================================================================
module.exports = """


def path():
    for p in PATHS:
        if os.path.exists(p):
            return p
    return PATHS[0]


def _strip_js(text):
    """剥注释 → 剥 module.exports → 容忍尾逗号"""
    t = text.strip()
    out, in_str, esc = [], False, False
    i = 0
    while i < len(t):
        c = t[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < len(t) and t[i + 1] == "/":
            while i < len(t) and t[i] != "\n":
                i += 1
            continue
        out.append(c)
        i += 1
    t = "".join(out).strip()
    t = re.sub(r"^(module\.exports|exports\.default|export\s+default)\s*=\s*", "", t).strip()
    t = re.sub(r";\s*$", "", t).strip()
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    return t


def _parse(raw):
    if not raw or not raw.strip():
        return None
    body = _strip_js(raw)
    try:
        cfg = json.loads(body)
    except Exception:
        body2 = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)\s*:", r'\1"\2":', body)
        cfg = json.loads(body2)
    cfg.setdefault("dailyLimit", DEFAULT_LIMIT)
    cfg.setdefault("accounts", [])
    return cfg


def load():
    p = path()
    if not os.path.exists(p):
        return {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
    with _LOCK, _FileLock(p):
        with open(p, encoding="utf-8") as f:
            raw = f.read()
    try:
        cfg = _parse(raw)
    except Exception:
        cfg = None
    if cfg is None:
        # 文件空/半截（异常情况）：不覆盖，回退到内置默认，避免把已有数据抹掉
        return {"dailyLimit": DEFAULT_LIMIT, "accounts": [], "_corrupt": True}
    return cfg


def accounts():
    return load().get("accounts") or []


def pick(uid=None, phone=None):
    """取账号。
    ★ 给了 uid/phone 就是**严格查找**：找不到返回 None。
      （以前会回落到 accounts[0]，导致「不存在」被误判成「存在」，
        网页扫到的号没法被正确登记/识别，是踩过的坑。）
      只有两个参数都不给时才返回第一个账号。
    """
    accs = accounts()
    if uid is None and phone is None:
        return accs[0] if accs else None
    for a in accs:
        if uid is not None and str(a.get("uid")) == str(uid):
            return a
        if phone is not None and str(a.get("phone")) == str(phone):
            return a
    return None


def has(uid=None, phone=None):
    """这个账号是否已在金币本里"""
    return pick(uid=uid, phone=phone) is not None


def save(cfg):
    """原子写：temp → os.replace，读方永远看不到半截文件"""
    p = path()
    cfg.pop("_corrupt", None)
    data = HEADER + json.dumps(cfg, ensure_ascii=False, indent=2) + ";\n"
    with _LOCK, _FileLock(p):
        d = os.path.dirname(p) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".accounts.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
    return p


def today():
    return datetime.date.today().isoformat()


# ---------------------------------------------------------------- 多账号存储
# 每个账号一份独立凭据，避免串号：
#   work/accounts/<uid>/session.json   登录会话（cookie / token）
#   work/accounts/<uid>/ticket.txt     XUID ticket（金币动作接口用）
def acct_dir(uid):
    d = os.path.join(ROOT, "work", "accounts", str(uid or "").strip())
    os.makedirs(d, exist_ok=True)
    return d


def ticket_path(uid):
    return os.path.join(acct_dir(uid), "ticket.txt")


def session_path(uid):
    return os.path.join(acct_dir(uid), "session.json")


def add_account(phone, password=None, uid=None, nickname=None, **extra):
    """新增/更新账号（按 uid 或 phone 去重）。返回写入后的账号 dict。"""
    p = path()
    with _LOCK, _FileLock(p):
        try:
            with open(p, encoding="utf-8") as f:
                cfg = _parse(f.read()) or {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        except Exception:
            cfg = {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        accs = cfg.setdefault("accounts", [])
        cur = None
        for a in accs:
            if (uid and str(a.get("uid")) == str(uid)) or \
               (phone and str(a.get("phone")) == str(phone)):
                cur = a
                break
        if cur is None:
            cur = {}
            accs.append(cur)
        cur["phone"] = phone or cur.get("phone")
        if password:
            cur["password"] = password
        if uid:
            cur["uid"] = str(uid)
        if nickname:
            cur["nickname"] = nickname
        cur.setdefault("date", today())
        cur.setdefault("todayFarmed", 0)
        cur.update(extra)
        data = HEADER + json.dumps(cfg, ensure_ascii=False, indent=2) + ";\n"
        d = os.path.dirname(p) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".accounts.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, p)
        except Exception:
            try: os.unlink(tmp)
            except Exception: pass
            raise
    return cur


def active_uid():
    """accounts.js 顶层 activeUid；没设就用第一个账号"""
    cfg = load()
    u = cfg.get("activeUid")
    if u:
        return str(u)
    a = pick()
    return str(a.get("uid")) if a and a.get("uid") else None


def set_active_uid(uid):
    p = path()
    with _LOCK, _FileLock(p):
        try:
            with open(p, encoding="utf-8") as f:
                cfg = _parse(f.read()) or {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        except Exception:
            cfg = {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        cfg["activeUid"] = str(uid)
        data = HEADER + json.dumps(cfg, ensure_ascii=False, indent=2) + ";\n"
        d = os.path.dirname(p) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".accounts.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, p)
        except Exception:
            try: os.unlink(tmp)
            except Exception: pass
            raise
    return str(uid)


def bump(acc, delta, balance=None):
    """★ 实时落盘：整个 read-modify-write 在锁内完成，不会丢更新"""
    if acc is None:
        return None
    p = path()
    with _LOCK, _FileLock(p):
        # 重新读最新，避免用陈旧副本覆盖别的进程写入
        try:
            with open(p, encoding="utf-8") as f:
                cfg = _parse(f.read()) or {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        except Exception:
            cfg = {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        accs = cfg.setdefault("accounts", [])
        cur = None
        for a in accs:
            if (acc.get("uid") and str(a.get("uid")) == str(acc.get("uid"))) or \
               (acc.get("phone") and str(a.get("phone")) == str(acc.get("phone"))):
                cur = a
                break
        if cur is None:
            cur = dict(acc)
            accs.append(cur)
        # 把调用方改过的字段合并回来（date/todayFarmed 以文件为准再累加）
        if acc.get("date") and acc["date"] != cur.get("date"):
            cur["date"] = acc["date"]
        for k in ("phone", "password", "uid", "nickname"):
            if acc.get(k) and not cur.get(k):
                cur[k] = acc[k]
        if cur.get("date") != today():
            cur["date"] = today()
            cur["todayFarmed"] = 0
            if balance is not None:
                cur["todayStartBalance"] = balance
        cur["todayFarmed"] = int(cur.get("todayFarmed") or 0) + int(delta or 0)
        if balance is not None:
            cur["lastBalance"] = balance
        cur.setdefault("todayStartBalance", cur.get("lastBalance"))
        data = HEADER + json.dumps(cfg, ensure_ascii=False, indent=2) + ";\n"
        d = os.path.dirname(p) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".accounts.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, p)
        except Exception:
            try:
                os.unlink(tmp)
            except Exception:
                pass
            raise
        acc.update(cur)
        return acc


def set_today(value, acc=None, balance=None):
    """把 todayFarmed 写成绝对值（--today/--reset 用；bump 只能累加）"""
    p = path()
    with _LOCK, _FileLock(p):
        try:
            with open(p, encoding="utf-8") as f:
                cfg = _parse(f.read()) or {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        except Exception:
            cfg = {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        accs = cfg.setdefault("accounts", [])
        key = acc or pick() or {}
        cur = None
        for a in accs:
            if (key.get("uid") and str(a.get("uid")) == str(key.get("uid"))) or \
               (key.get("phone") and str(a.get("phone")) == str(key.get("phone"))):
                cur = a
                break
        if cur is None:
            cur = dict(key)
            accs.append(cur)
        cur["date"] = today()
        cur["todayFarmed"] = int(value or 0)
        if balance is not None:
            cur["lastBalance"] = balance
            cur["todayStartBalance"] = balance
            cur["todayFarmed"] = 0 if value is None else int(value)
        data = HEADER + json.dumps(cfg, ensure_ascii=False, indent=2) + ";\n"
        d = os.path.dirname(p) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".accounts.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, p)
        except Exception:
            try: os.unlink(tmp)
            except Exception: pass
            raise
        if acc is not None:
            acc.update(cur)
        return cur


def refresh_day(acc=None, balance=None):
    """★ 跨天刷新并**落盘**：date != 今天 → todayFarmed 归零、date 改成今天。
    返回 (是否发生了刷新, 刷新后的账号)。"""
    if acc is None:
        acc = pick()
    if acc is None:
        return False, None
    if acc.get("date") == today():
        return False, acc
    old_date, old = acc.get("date"), acc.get("todayFarmed")
    acc["date"] = today()
    acc["todayFarmed"] = 0
    if balance is not None:
        acc["todayStartBalance"] = balance
        acc["lastBalance"] = balance
    # 落盘
    p = path()
    with _LOCK, _FileLock(p):
        try:
            with open(p, encoding="utf-8") as f:
                cfg = _parse(f.read()) or {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        except Exception:
            cfg = {"dailyLimit": DEFAULT_LIMIT, "accounts": []}
        for a in cfg.setdefault("accounts", []):
            if (acc.get("uid") and str(a.get("uid")) == str(acc.get("uid"))) or \
               (acc.get("phone") and str(a.get("phone")) == str(acc.get("phone"))):
                a["date"] = acc["date"]
                a["todayFarmed"] = 0
                if balance is not None:
                    a["todayStartBalance"] = balance
                    a["lastBalance"] = balance
                break
        else:
            cfg["accounts"].append(acc)
        data = HEADER + json.dumps(cfg, ensure_ascii=False, indent=2) + ";\n"
        d = os.path.dirname(p) or "."
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".accounts.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(data); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, p)
        except Exception:
            try: os.unlink(tmp)
            except Exception: pass
            raise
    return True, acc


def reload_account(acc):
    """从文件重新读该账号（跨进程共享额度用）"""
    if acc is None:
        return pick()
    fresh = pick(uid=acc.get("uid"), phone=acc.get("phone"))
    if fresh:
        acc.update(fresh)
    return acc


def check_limit(acc, cfg=None):
    """返回 (是否还能刷, 说明)"""
    cfg = cfg or load()
    limit = int(cfg.get("dailyLimit") or DEFAULT_LIMIT)
    if acc is None:
        return True, "无账号记录，不限额"
    if acc.get("date") != today():
        return True, "新的一天，已归零"
    done = int(acc.get("todayFarmed") or 0)
    if done >= limit:
        return False, "今日已刷 %d / 上限 %d，停止" % (done, limit)
    return True, "今日已刷 %d / 上限 %d，额度剩 %d" % (done, limit, limit - done)


if __name__ == "__main__":
    import sys
    cfg = load()
    if len(sys.argv) > 1 and sys.argv[1] == "add":
        # python3 accounts.py add <phone> [password] [uid] [nickname]
        a = sys.argv[1:]
        phone = a[1] if len(a) > 1 else None
        pwd = a[2] if len(a) > 2 else None
        uid = a[3] if len(a) > 3 else None
        nick = a[4] if len(a) > 4 else None
        cur = add_account(phone, pwd, uid, nick)
        print("已写入账号:", json.dumps(cur, ensure_ascii=False))
        raise SystemExit(0)
    print("accounts.js =", path())
    print("dailyLimit  =", cfg.get("dailyLimit"))
    print("activeUid   =", active_uid())
    for a in cfg.get("accounts") or []:
        ok, msg = check_limit(a, cfg)
        print("  %-13s uid=%-11s %s  %s" % (a.get("phone"), a.get("uid"),
                                            "可继续" if ok else "已刷满", msg))
