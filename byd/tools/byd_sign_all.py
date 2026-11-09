"""比亚迪小程序 · 多账号批量签到。

账号配置: data/byd_accounts.json（运行时可直接编辑，增删账号即时生效）
  [
    {"name": "账号A", "session_id": "xxxx", "note": "备注(可选)"},
    {"name": "账号B", "session_id": "yyyy"}
  ]

签到状态: data/byd_state.json —— 管理页 tools/byd_admin.py 与它共用，
批量签到跑完（无论手动还是 cron）页面刷新即可看到最新状态。

用法:
  python tools/byd_sign_all.py                # 按顺序签所有账号
  python tools/byd_sign_all.py --name 账号A   # 只重签指定账号
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from byd_app_sign import call, check_session  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACCOUNTS_PATH = os.path.join(BASE_DIR, "data", "byd_accounts.json")
STATE_PATH = os.path.join(BASE_DIR, "data", "byd_state.json")

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
        print("📨 青龙通知已发（面板通知设置）")
        return True
    print("⚠️ [通知] 面板接口发送失败：%s，尝试 notify.py" % reason)
    sender = _ql_load_notify_py()
    if sender is None:
        print("⚠️ [通知] 未找到 notify.py，通知未发出")
        return False
    try:
        sender.send(title, content)
        print("📨 通知已通过 notify.py 发送（仅环境变量配置的渠道有效，未配则静默不发）")
        return True
    except Exception as exc:
        print("⚠️ [通知] notify.py 发送失败：%s" % exc)
        return False



# ---------- 配置与状态读写 ----------

def load_accounts() -> List[Dict[str, Any]]:
    """读账号配置。文件不存在/损坏返回 []，由调用方提示。"""
    try:
        with open(ACCOUNTS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError) as exc:
        print(f"[警告] 账号配置读不到: {ACCOUNTS_PATH} ({exc})", file=sys.stderr)
        return []
    accounts = []
    for i, item in enumerate(raw or [], 1):
        if not isinstance(item, dict):
            continue
        sid = str(item.get("session_id") or "").strip()
        if not sid:
            print(f"[警告] 第 {i} 条账号缺 session_id，跳过", file=sys.stderr)
            continue
        accounts.append({
            "name": str(item.get("name") or f"账号{i}").strip(),
            "session_id": sid,
            "note": str(item.get("note") or "").strip(),
        })
    return accounts


def load_accounts_raw() -> List[Dict[str, Any]]:
    """读原始配置列表（不做归一化），供管理页增删改用。"""
    try:
        with open(ACCOUNTS_PATH, encoding="utf-8") as f:
            raw = json.load(f)
        return raw if isinstance(raw, list) else []
    except (OSError, ValueError):
        return []


def save_accounts(accounts: List[Dict[str, Any]]) -> None:
    """把账号配置原子写回磁盘。"""
    os.makedirs(os.path.dirname(ACCOUNTS_PATH), exist_ok=True)
    tmp = ACCOUNTS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(accounts, f, ensure_ascii=False, indent=2)
    os.replace(tmp, ACCOUNTS_PATH)


def load_state() -> Dict[str, Any]:
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {"updated_at": None, "accounts": {}}


def save_state(state: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)


# ---------- 签到 ----------

def sign_one(acc: Dict[str, Any]) -> Dict[str, Any]:
    """签到一个账号，返回写入状态文件的结果条目。

    status 取值:
      ok        签到成功
      duplicate 今日已签过
      failed    接口返回非 200 —— 大概率 session_id 过期，页面上标红
      error     网络异常/响应解不开 —— 不一定是过期，但也标出来
    """
    res: Dict[str, Any] = {
        "date": time.strftime("%Y-%m-%d"),
        "last_run": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_days": None,
        "integral": None,
    }
    payload = {
        "session_id": acc["session_id"],
        "app_version": "240",
        "app_client": "mina",
        "date": "",
        "isCard": "0",
    }
    try:
        r = call("activity/sign/signIn", payload)
    except Exception as exc:  # requests 网络异常
        res.update(status="error", ret=None, expired=False,
                   msg=f"网络异常: {exc}")
        return res

    dec = r.get("decrypted")
    if not dec:
        res.update(status="error", ret=None, expired=False,
                   msg=f"响应解不开(HTTP {r.get('status')}): {str(r.get('raw'))[:100]}")
        return res
    try:
        obj = json.loads(dec)
    except ValueError:
        res.update(status="error", ret=None, expired=False, msg=f"响应不是 JSON: {dec[:100]}")
        return res

    ret = obj.get("ret")
    if str(ret) == "200":
        data = obj.get("data") or {}
        dup = bool(data.get("duplicate"))
        res.update(
            status="duplicate" if dup else "ok",
            ret=ret, expired=False,
            duration_days=data.get("durationDays"),
            integral=data.get("integral"),
            msg=obj.get("msg") or "",
        )
    else:
        # 已知过期症状: ret="401" msg="网络繁忙，请稍后重试"。
        # 用小程序启动时的 checkSession 接口复核，把「确认过期」和「其他错误」分开：
        #   10011 = "3rd服务器session过期" → 确认过期
        #   200   = session 还活着，签到失败另有原因（不标红误导换 session）
        msg = obj.get("msg") or dec[:100]
        expired = True
        try:
            ck = json.loads(check_session(acc["session_id"]).get("decrypted") or "{}")
            ck_ret = str(ck.get("ret"))
            if ck_ret == "10011":
                msg = f"session 已过期（checkSession 确认），请重新抓包"
            elif ck_ret == "200":
                expired = False
                msg = f"签到失败但 session 有效（{msg}），稍后重试或反馈"
        except Exception:
            pass  # 复核失败就维持原判：宁可误报也不漏报
        res.update(status="failed", ret=ret, expired=expired, msg=msg)
    return res


def run_all(only_name: Optional[str] = None) -> Dict[str, Any]:
    """批量签到并把结果合并进状态文件。返回最新状态。"""
    accounts = load_accounts()
    state = load_state()
    entries = state.setdefault("accounts", {})

    targets = accounts
    if only_name:
        targets = [a for a in accounts if a["name"] == only_name]
        if not targets:
            raise SystemExit(f"配置里没有名为「{only_name}」的账号")

    for acc in targets:
        print(f"[{acc['name']}] 签到中 ...", flush=True)
        res = sign_one(acc)
        entries[acc["name"]] = res
        print(f"[{acc['name']}] {res['status']} | {res.get('msg') or ''}")
        time.sleep(1)  # 账号之间隔一秒，别打太密

    state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_state(state)
    return state


def _ql_byd_title_and_content(state, names, tail):
    """通知用标题和正文：只统计本次签过的账号（state 里还留着往次的结果，不能全算）。"""
    entries = (state or {}).get("accounts", {}) or {}
    lines = []
    ok = fail = 0
    for name in names:
        res = entries.get(name) or {}
        status = str(res.get("status") or "")
        if status in ("ok", "duplicate"):
            ok += 1
            detail = "签到成功" if status == "ok" else "今天已签过"
            if res.get("integral") is not None:
                detail += "，积分 %s" % res.get("integral")
            if res.get("duration_days") is not None:
                detail += "，已连续 %s 天" % res.get("duration_days")
            lines.append("✅ [%s] %s" % (name, detail))
        else:
            fail += 1
            lines.append("❌ [%s] %s" % (name, str(res.get("msg") or "失败")[:120]))
    content = "比亚迪小程序签到\n\n总结：%d 成功 / %d 失败\n%s" % (ok, fail, "\n".join(lines) if lines else "（无账号结果）")
    if tail:
        content += "\n\n📋 日志尾部（最近30行）:\n" + tail
    return "比亚迪签到：%d成功/%d失败" % (ok, fail), content


def main() -> None:
    ap = argparse.ArgumentParser(description="比亚迪小程序多账号批量签到")
    ap.add_argument("--name", help="只签指定名字的账号（默认全部）")
    args = ap.parse_args()

    tee = _QlLogTee(sys.stdout)
    sys.stdout = tee
    if not load_accounts():
        sys.stdout = tee.stream
        _ql_notify("比亚迪签到：0成功/0失败", "❌ 没有可签到的账号，请先编辑 data/byd_accounts.json（填 32 位 session_id，2 小时有效）")
        raise SystemExit(f"没有可签到的账号，请先编辑 {ACCOUNTS_PATH}")
    names = [a["name"] for a in load_accounts() if not args.name or a["name"] == args.name]
    try:
        state = run_all(args.name)
    except SystemExit:
        sys.stdout = tee.stream
        _tail = tee.tail()
        _ql_notify("比亚迪签到：0成功/0失败", "❌ 签到中断（可能是指定的账号名不存在）" + ("\n\n📋 日志尾部（最近30行）:\n" + _tail if _tail else ""))
        raise
    sys.stdout = tee.stream
    _ql_notify(*_ql_byd_title_and_content(state, names, tee.tail()))


if __name__ == "__main__":
    main()
