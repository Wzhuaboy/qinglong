# cron: 25 12 * * *
# const $ = new Env('统一茄皇的家-第五期')

# QH_CK 账号格式：wid#openId
# 多账号用 & 或换行分隔，例如：3149997835#oBk224...U7MM&10062340803#oBk224...G08I

import base64
import json
import os
import random
import time

import requests

try:
    from notify import send
except ImportError:
    def send(title, content=""):
        print(f"{title}\n{content}")

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    CRYPTO_BACKEND = "cryptography"
except ImportError:
    try:
        from Crypto.Cipher import AES, PKCS1_OAEP
        from Crypto.Hash import SHA256
        from Crypto.PublicKey import RSA

        CRYPTO_BACKEND = "pycryptodome"
    except ImportError:
        CRYPTO_BACKEND = None


BASE_URL = "https://farmgames.ioutu.cn"

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


PUBLIC_KEY = (
    "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA70sK419vy3MabW3lEGlk"
    "7Zh1u78OdnVlioVazp5Y46eBh+/TDqo/wZ9VrQ/4MmAtoP0vJ2vmwP5gqO3WPoj"
    "b07WddXfF1eU+5M+Rj3s0eSRrvZvBcGZ3qK0dOgZJScK66IDQazt/c4xqhDcsI"
    "tIyNRahUqB/IKc6E80GZJvMvFtZVSCseAXC0mAJXhi1AdUOlP+3Pv0fiUVejTJp"
    "1j7LBNWJ7Z5/8mRcclQH0vmxsdYsaV3qZiJ2d/CfNoKcwmI2IWmeZy8NP5U8Hn"
    "0AsxPEwjdHoEqG/iy/SoA46TZL+RLtWqUSHXpaKR/VFN0rbl25SE91X8FTfLqyD"
    "8LfGMCwRQIDAQAB"
)
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 26_5_2 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.75(0x18004b42) NetType/WIFI Language/zh_CN "
    "miniProgram/wx532ecb3bdaaf92f9"
)
SUPPORTED_TASK_TYPES = {"SIGN", "BROWSE", "SHARE"}
FRIEND_TASK_TYPE = "FRIEND_STEAL_ENERGY"
FRIEND_STATUS_CLAIMABLE = "0"


def parse_users():
    """QH supports one account per line (or separated by &): wid#openId."""
    raw = os.getenv("QH_CK", "").replace("&", "\n")
    users = []
    errors = []
    for index, line in enumerate(raw.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        parts = [item.strip() for item in line.split("#")]
        if len(parts) < 2 or not parts[0] or not parts[1]:
            errors.append(f"第{index}条配置格式错误，应为 wid#openId")
            continue
        wid, open_id = parts[0], parts[-1]
        if not open_id.startswith("o"):
            errors.append(
                f"第{index}条配置的第二项不像 openId；新活动不再使用手机号，请改为 wid#openId"
            )
            continue
        users.append((wid, open_id))
    return users, errors


def encrypt_payload(payload):
    """Match the H5 client: RSA-OAEP-SHA256 + AES-256-GCM."""
    if CRYPTO_BACKEND is None:
        raise RuntimeError(
            "缺少加密依赖，请安装 cryptography（pip install cryptography）"
        )

    plaintext = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    aes_key = os.urandom(32)
    iv = os.urandom(12)
    public_key_der = base64.b64decode(PUBLIC_KEY)

    if CRYPTO_BACKEND == "cryptography":
        public_key = serialization.load_der_public_key(public_key_der)
        encrypted_data = AESGCM(aes_key).encrypt(iv, plaintext, None)
        encrypted_key = public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )
    else:
        cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
        ciphertext, tag = cipher.encrypt_and_digest(plaintext)
        encrypted_data = ciphertext + tag
        public_key = RSA.import_key(public_key_der)
        encrypted_key = PKCS1_OAEP.new(public_key, hashAlgo=SHA256).encrypt(aes_key)

    return {
        "data": base64.b64encode(encrypted_data).decode(),
        "key": base64.b64encode(encrypted_key).decode(),
        "iv": base64.b64encode(iv).decode(),
    }


class TomatoClient:
    def __init__(self, wid, open_id):
        self.wid = wid
        self.open_id = open_id
        self.tomato_user_id = None
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Content-Type": "application/json",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}/?wid={wid}&openId={open_id}",
            }
        )

    def request(self, method, path, payload=None, encrypted=True, retry=2):
        url = f"{BASE_URL}{path}"
        for attempt in range(retry + 1):
            kwargs = {"timeout": 20}
            if payload:
                kwargs["json"] = encrypt_payload(payload) if encrypted else payload
                if encrypted:
                    kwargs["headers"] = {"X-Request-Encrypted": "true"}
            response = self.session.request(method, url, **kwargs)
            if response.status_code == 429 and attempt < retry:
                retry_after = response.headers.get("Retry-After", "2")
                try:
                    wait_seconds = max(1.0, float(retry_after))
                except ValueError:
                    wait_seconds = 2.0
                time.sleep(wait_seconds + attempt)
                continue
            response.raise_for_status()
            try:
                result = response.json()
            except ValueError as exc:
                raise RuntimeError(f"接口返回非 JSON 数据：{response.text[:200]}") from exc

            msg = str(result.get("msg", ""))
            if result.get("code") == 200:
                return result
            if attempt < retry and (
                response.status_code == 429 or "频繁" in msg or "稍后" in msg
            ):
                time.sleep(2.5 + attempt * 1.5)
                continue
            raise RuntimeError(msg or f"接口返回 code={result.get('code')}")
        raise RuntimeError("请求重试后仍未成功")

    def login(self):
        result = self.request(
            "POST",
            "/api/web/open/tomato/login",
            {
                "shareTomatoUserId": None,
                "openId": self.open_id,
                "wid": self.wid,
                "queryCardStatus": True,
            },
        )
        data = result.get("data") or {}
        token = data.get("token")
        if not token:
            raise RuntimeError("登录响应中没有 token")
        self.session.headers["Authorization"] = token
        self.tomato_user_id = data.get("tomatoUserId")
        return data

    def home(self):
        return self.request("GET", "/api/web/member/tomato/home").get("data") or {}

    def tasks(self):
        return self.request("GET", "/api/web/member/tomato/tasks").get("data") or []

    def complete_task(self, task):
        task_type = task.get("taskType")
        payload = {"taskType": task_type}
        if task_type != "SHARE":
            payload["browseTarget"] = task.get("browseTarget") or ""
        elif self.tomato_user_id:
            try:
                self.request(
                    "POST",
                    "/api/web/member/tomato/miniprogram/qrcode/create",
                    {
                        "page": "packages/wm-cloud-qiehuang/home/index",
                        "scene": str(self.tomato_user_id),
                    },
                )
            except Exception:
                # The official client also falls back to an empty QR URL.
                pass
        return self.request(
            "POST", "/api/web/member/tomato/tasks/complete", payload
        ).get("data") or {}

    def friends(self, page_size=20):
        friends = []
        page_num = 1
        while True:
            result = self.request(
                "GET",
                f"/api/web/member/tomato/friends?pageNum={page_num}&pageSize={page_size}",
            )
            rows = result.get("rows") or []
            friends.extend(rows)
            total = int(result.get("total") or 0)
            if not rows or (total and len(friends) >= total) or len(rows) < page_size:
                break
            page_num += 1
        return friends

    def friend_home(self, friend_user_id):
        return self.request(
            "GET",
            f"/api/web/member/tomato/friends/{friend_user_id}/home",
        ).get("data") or {}

    def steal_friend_energy(self, friend_user_id):
        return self.request(
            "POST",
            "/api/web/member/tomato/friends/steal",
            {"friendTomatoUserId": friend_user_id},
        ).get("data")

    def use_energy(self):
        return self.request(
            "POST", "/api/web/member/tomato/energy/use", encrypted=False
        ).get("data") or {}


def short_open_id(open_id):
    return f"{open_id[:6]}...{open_id[-4:]}" if len(open_id) > 12 else open_id


def home_line(data, prefix="📊 当前状态"):
    return (
        f"{prefix}：⚡能量 {data.get('energyBalance', 0)}｜"
        f"🍅番茄 {data.get('tomatoBalance', 0)}｜"
        f"🌱{data.get('stageName', '未知阶段')} "
        f"{data.get('currentExp', 0)}/{data.get('stageRequiredExp', 0)}"
    )


def process_user(wid, open_id, index):
    logs = []
    client = TomatoClient(wid, open_id)

    login_data = client.login()
    logs.append(f"✅ 登录成功：{login_data.get('nickName') or '未设置昵称'}")
    home = client.home()
    logs.append(home_line(home))

    completed = 0
    skipped = 0
    friend_task = None
    for task in client.tasks():
        name = task.get("taskName") or task.get("taskCode") or "未知任务"
        task_type = task.get("taskType")
        if task_type == FRIEND_TASK_TYPE:
            friend_task = task
            if str(task.get("completed")) == "1":
                logs.append(f"✔️ 任务已完成：{name}")
            continue
        if str(task.get("completed")) == "1":
            logs.append(f"✔️ 任务已完成：{name}")
            continue
        if task_type not in SUPPORTED_TASK_TYPES:
            skipped += 1
            logs.append(f"⏭️ 跳过任务：{name}（需在小程序内操作）")
            continue
        try:
            result = client.complete_task(task)
            reward = result.get("rewardText") or task.get("rewardText") or "已领取"
            logs.append(f"✔️ 任务完成：{name}，{reward}")
            completed += 1
        except Exception as exc:
            logs.append(f"❌️ 任务失败：{name}，{exc}")
        time.sleep(random.uniform(2.5, 3.5))

    try:
        claimable_friends = [
            friend
            for friend in client.friends()
            if str(friend.get("friendStatus")) == FRIEND_STATUS_CLAIMABLE
            and friend.get("friendTomatoUserId")
        ]
        stolen_count = 0
        stolen_energy = 0
        failed_count = 0
        for friend in claimable_friends:
            friend_user_id = friend["friendTomatoUserId"]
            try:
                friend_home = client.friend_home(friend_user_id)
                amount = int(friend_home.get("stealAmount") or 0)
                if str(friend_home.get("canSteal")) != "1" or amount <= 0:
                    continue
                client.steal_friend_energy(friend_user_id)
                stolen_count += 1
                stolen_energy += amount
            except Exception:
                failed_count += 1
            time.sleep(random.uniform(1.5, 2.5))

        if stolen_count:
            detail = f"🤝 好友能量：成功收取 {stolen_count} 位好友，共 {stolen_energy} 能量"
            if failed_count:
                detail += f"，失败 {failed_count} 位"
            logs.append(detail)
            if friend_task and str(friend_task.get("completed")) != "1":
                completed += 1
        elif failed_count:
            logs.append(f"🤝 好友能量：收取失败 {failed_count} 位")
        else:
            logs.append("🤝 好友能量：暂无可收取能量")
    except Exception as exc:
        logs.append(f"❌️ 好友能量失败：{exc}")

    home = client.home()
    energy = int(home.get("energyBalance") or 0)
    if energy > 0:
        before_tomato = int(home.get("tomatoBalance") or 0)
        try:
            grown = client.use_energy()
            after_tomato = int(grown.get("tomatoBalance") or 0)
            gained = int(grown.get("gainedTomatoAmount") or 0)
            if not gained:
                gained = max(0, after_tomato - before_tomato)
            logs.append(f"☀️ 使用能量：{grown.get('usedEnergyAmount', energy)}")
            home = grown
        except Exception as exc:
            logs.append(f"❌️ 使用能量失败：{exc}")
    else:
        logs.append("☀️ 使用能量：当前没有可用能量")

    logs.append(home_line(home, "📈 最新状态"))
    logs.append(f"✅ 本次完成任务 {completed} 个，跳过 {skipped} 个")
    return logs


def render_report(all_logs):
    lines = ["统一茄皇五期"]
    for logs in all_logs:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.extend(logs)
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


def main():
    print("🍅 统一茄皇 - 第五期")
    users, config_errors = parse_users()
    if CRYPTO_BACKEND is None:
        message = "缺少加密依赖，请安装 cryptography：pip install cryptography"
        print(message)
        _ql_notify("统一茄皇五期：0成功/0失败", message)
        return
    if not users:
        detail = "；".join(config_errors) if config_errors else "未读取到 QH 环境变量"
        message = f"没有可用账号：{detail}。格式为 wid#openId"
        print(message)
        _ql_notify("统一茄皇五期：0成功/0失败", message)
        return

    all_logs = []
    for index, (wid, open_id) in enumerate(users, 1):
        print(f"\n===== 账号 {index}（wid={wid}）=====")
        try:
            logs = process_user(wid, open_id, index)
        except Exception as exc:
            logs = [
                f"账号{index}（wid={wid}｜openId={short_open_id(open_id)}）",
                f"❌️ 处理失败：{exc}",
            ]
        all_logs.append(logs)
        print("\n".join(logs))
        if index < len(users):
            time.sleep(random.uniform(3, 5))

    if config_errors:
        all_logs.append(["配置提醒"] + config_errors)
    report = render_report(all_logs)
    # 汇总本身就是各账号的执行日志（_ql_notify 内会截到约 1800 字符，不另附尾部）
    _ok = sum(1 for _logs in all_logs if not any("❌" in _l for _l in _logs))
    _fail = len(all_logs) - _ok
    _ql_notify("统一茄皇五期：%d成功/%d失败" % (_ok, _fail), report)


if __name__ == "__main__":
    main()