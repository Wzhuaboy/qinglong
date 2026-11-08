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

import time
import json
import base64
import hashlib
import random
import string
import urllib.parse
import re
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import OrderedDict
from curl_cffi import requests  
from Crypto.Cipher import AES, DES3, PKCS1_v1_5
from Crypto.Util.Padding import pad, unpad
from Crypto.PublicKey import RSA
#傻子传谣。当然智者跑本的，也最好看看，虽说开源的，但也有傻子信

# ===================== 【必填配置】修改这里 =====================
TEST_ACCOUNTS = os.getenv("chinaTelecomAccount", "")
CHANNEL_ID = "156000009079"
ACTIVITY_ID = "ai119"
TEMPLATE_ID = ""
TEMPLATE_CONF_ID = ""
LOTTERY_COST_SCORE = 20
OTHER_ACCOUNTS_LOTTERY_ENABLED = False  # 是否允许除第一个账号外的账号抽奖
XIEQU_PROXY_URL = os.getenv("XIEQU_PROXY_URL", "")
# ==============================================================

# ================= 加解密核心 =================
def md5(t): return hashlib.md5(t.encode()).hexdigest()

def rsa_encrypt(t):
    pub = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDBkLT15ThVgz6/NOl6s8GNPofdWzWbCkWnkaAm7O2LjkM1H7dMvzkiqdxU02jamGRHLX/ZNMCXHnPcW/sDhiFCBN18qFvy8g6VYb9QtroI09e176s+ZCtiv7hbin2cCTj99iUpnEloZm19lwHyo69u5UMiPMpq0/XKBO8lYhN/gwIDAQAB
-----END PUBLIC KEY-----"""
    return base64.b64encode(PKCS1_v1_5.new(RSA.import_key(pub)).encrypt(t.encode())).decode()

def des3_op(t, decrypt=False):
    key = b"1234567`90koiuyhgtfrdews"
    c = DES3.new(key, DES3.MODE_CBC, b"\x00"*8)
    if decrypt: 
        try: return unpad(c.decrypt(bytes.fromhex(t)), 8).decode()
        except: return t
    return c.encrypt(pad(t.encode(), 8)).hex()

class ImCrypto:
    def __init__(self):
        self.ts = str(int(time.time() * 1000))
        self.rdm = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
        m_ts = md5(self.ts)
        self.key_h = md5(base64.b64encode((m_ts + self.rdm).encode()).decode() + self.rdm)
        self.e_k = md5(base64.b64encode(self.rdm.encode()).decode() + m_ts + self.key_h)[:16]
        self.e_i = md5(base64.b64encode(self.ts.encode()).decode() + md5(self.rdm) + self.key_h)[:16]

    def encrypt(self, d):
        s = json.dumps(d, separators=(',', ':'), ensure_ascii=False)
        c = AES.new(self.e_k.encode(), AES.MODE_CBC, self.e_i.encode())
        return base64.b64encode(c.encrypt(pad(s.encode('utf-8'), 16))).decode()

    def decrypt(self, t):
        try:
            d_k = md5(base64.b64encode(self.ts.encode()).decode() + self.key_h + md5(self.rdm))[:16]
            d_i = md5(base64.b64encode(self.rdm.encode()).decode() + self.key_h + md5(self.ts))[:16]
            c = AES.new(d_k.encode(), AES.MODE_CBC, d_i.encode())
            return unpad(c.decrypt(base64.b64decode(t)), 16).decode('utf-8')
        except: return t

def check_and_update_token(res, current_token):
    new_auth = res.headers.get("authorization") or res.headers.get("Authorization")
    if new_auth:
        new_token = new_auth.replace("Bearer ", "").strip()
        if new_token and new_token != current_token:
            print("🔄 [拦截器] 捕获到下发的刷新 Token，已动态更新凭证！")
            return new_token
    return current_token


_SESSION_PROXY_STATE = {}
_XIEQU_WHITELIST_STATE = {"checked": False, "public_ip": ""}


def create_browser_session():
    session = requests.Session(impersonate="chrome120", trust_env=False)
    session.headers.update({
        "User-Agent": "CtClient;13.3.0;Android;14;V2203A",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://ai.imusic.cn",
        "X-Requested-With": "com.ct.client",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    })
    try:
        session.proxies = {}
    except Exception:
        try:
            session.proxies.clear()
        except Exception:
            pass
    try:
        session.verify = False
    except Exception:
        pass
    return session


def get_public_ip():
    for url in ("http://ping0.cc", "http://ip.sb"):
        try:
            ip_text = requests.get(url, timeout=5).text.strip()
            if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", ip_text):
                return ip_text
        except Exception:
            continue
    return ""


def manage_xiequ_whitelist(force=False):
    if not XIEQU_PROXY_URL:
        return

    uid = str(os.getenv("XIEQU_UID", "")).strip()
    ukey = str(os.getenv("XIEQU_UKEY", "")).strip()
    if not uid or not ukey:
        return

    state = _XIEQU_WHITELIST_STATE
    if state.get("checked") and not force:
        return

    print("🌐 检测到携趣代理 API 配置，即将执行白名单检测...")

    current_ip = get_public_ip()
    if not current_ip:
        state["checked"] = False
        print("⚠️ 无法获取本机公网IP，本次先跳过携趣白名单检测，后续会自动重试")
        return
    print(f"[*] 本机公网IP: {current_ip}，正在检测携趣白名单...")

    try:
        get_url = f"http://op.xiequ.cn/IpWhiteList.aspx?uid={uid}&ukey={ukey}&act=get"
        white_list = requests.get(get_url, timeout=5).text
        if current_ip in white_list:
            state["public_ip"] = current_ip
            state["checked"] = True
            print("[+] 当前公网IP已在携趣白名单中，状态良好。")
            return

        add_url = (
            f"http://op.xiequ.cn/IpWhiteList.aspx?uid={uid}&ukey={ukey}"
            f"&act=add&ip={current_ip}&meno=ai_luck_win_auto"
        )
        add_resp = requests.get(add_url, timeout=5)
        state["public_ip"] = current_ip
        state["checked"] = True
        print(f"[+] 当前公网IP不在白名单中，已自动添加: {current_ip}")
        print(f"[+] 携趣接口返回: {str(add_resp.text or '').strip()}")
    except Exception as exc:
        state["checked"] = False
        print(f"⚠️ 携趣白名单检测/添加失败，已忽略: {exc}")


def get_session_proxy_state(session):
    sid = id(session)
    if sid not in _SESSION_PROXY_STATE:
        _SESSION_PROXY_STATE[sid] = {"proxy_url": "", "fetched_at": 0.0}
    return _SESSION_PROXY_STATE[sid]


def infer_xiequ_scheme(source):
    try:
        query = urllib.parse.parse_qs(urllib.parse.urlparse(source).query)
        so = str((query.get("so") or [""])[0]).strip()
        if so == "3":
            return "socks5h"
    except Exception:
        pass
    return "http"


def mask_proxy_url(proxy_url):
    if not proxy_url:
        return ""
    try:
        parsed = urllib.parse.urlparse(proxy_url if "://" in proxy_url else f"http://{proxy_url}")
        host = parsed.hostname or ""
        port = parsed.port or ""
        if host:
            return f"{parsed.scheme or 'http'}://{host}:{port}"
    except Exception:
        pass
    return proxy_url


def is_direct_proxy_value(value):
    text = str(value or "").strip()
    if not text:
        return False
    if re.match(r"^(https?|socks5h?)://[^/\s]+$", text, re.I):
        return True
    return bool(re.match(r"^[^:/\s]+:\d+$", text))


def normalize_proxy_value(proxy_value, scheme_hint="http"):
    text = str(proxy_value or "").strip()
    if not text:
        raise ValueError("代理地址为空")
    if re.match(r"^(https?|socks5h?)://", text, re.I):
        return text
    return f"{scheme_hint}://{text}"


def parse_xiequ_proxy_response(resp_text, source_url=""):
    text = str(resp_text or "").strip()
    if not text:
        raise ValueError("携趣代理返回为空")
    if text.startswith("DB") or text.startswith("Err"):
        raise ValueError(f"携趣代理提取失败: {text}")

    lines = [line.strip() for line in re.split(r"[\r\n\t]+", text) if line.strip()]
    scheme_hint = infer_xiequ_scheme(source_url)
    for line in lines:
        if line.startswith("DB") or line.startswith("Err"):
            raise ValueError(f"携趣代理提取失败: {line}")
        if is_direct_proxy_value(line):
            return normalize_proxy_value(line, scheme_hint)
    raise ValueError(f"携趣代理返回格式无法识别: {text}")


def fetch_xiequ_proxy():
    if not XIEQU_PROXY_URL:
        return ""
    if is_direct_proxy_value(XIEQU_PROXY_URL):
        return normalize_proxy_value(XIEQU_PROXY_URL, infer_xiequ_scheme(XIEQU_PROXY_URL))

    manage_xiequ_whitelist()

    last_exc = None
    total_attempts = 3
    for attempt in range(1, total_attempts + 1):
        proxy_session = create_browser_session()

        try:
            res = proxy_session.get(
                XIEQU_PROXY_URL,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10
            )
            try:
                res.raise_for_status()
            except Exception as exc:
                raise ValueError(f"携趣代理提取接口请求失败: {exc}")
            return parse_xiequ_proxy_response(res.text, XIEQU_PROXY_URL)
        except Exception as exc:
            last_exc = exc
            if attempt >= total_attempts:
                break
            print(f"⚠️ [携趣代理] 提取失败，准备重试 {attempt}/{total_attempts - 1}: {exc}")
            time.sleep(0.8)

    raise ValueError(f"携趣代理提取失败: {last_exc}")


def disable_session_proxy(session):
    try:
        session.proxies = {}
    except Exception:
        try:
            session.proxies.clear()
        except Exception:
            pass
    state = get_session_proxy_state(session)
    state["proxy_url"] = ""
    state["fetched_at"] = 0.0


def apply_session_proxy(session, proxy_url, reason=""):
    if not proxy_url:
        return ""
    proxies = {"http": proxy_url, "https": proxy_url}
    try:
        session.proxies = proxies
    except Exception:
        try:
            session.proxies.update(proxies)
        except Exception as exc:
            raise RuntimeError(f"当前运行环境不支持给 Session 设置代理: {exc}")
    state = get_session_proxy_state(session)
    state["proxy_url"] = proxy_url
    state["fetched_at"] = time.time()
    prefix = f"[{reason}] " if reason else ""
    print(f"🌐 {prefix}已启用代理: {mask_proxy_url(proxy_url)}")
    return proxy_url


def refresh_session_proxy(session, reason="", force=False):
    if not XIEQU_PROXY_URL:
        return ""
    state = get_session_proxy_state(session)
    if state.get("proxy_url") and not force:
        return state["proxy_url"]
    proxy_url = fetch_xiequ_proxy()
    return apply_session_proxy(session, proxy_url, reason=reason)


def ensure_session_proxy(session, reason=""):
    if not XIEQU_PROXY_URL:
        return ""
    state = get_session_proxy_state(session)
    if state.get("proxy_url"):
        return state["proxy_url"]
    return refresh_session_proxy(session, reason=reason or "自动初始化代理", force=True)


def prepare_proxy_for_action(session, reason=""):
    if not XIEQU_PROXY_URL:
        return ""
    return ensure_session_proxy(session, reason=reason)


def is_retryable_request_exception(exc):
    text = str(exc or "").lower()
    markers = [
        "curl: (5)", "curl: (6)", "curl: (7)", "curl: (18)", "curl: (28)", "curl: (60)",
        "curl: (35)", "curl: (52)", "curl: (55)", "curl: (56)",
        "failed to connect", "could not connect", "connection refused",
        "connection reset", "connection aborted", "timed out", "timeout",
        "empty reply", "recv failure", "send failure", "proxy", "ssl connect",
        "ssl certificate problem", "certificate problem", "self signed certificate"
    ]
    return any(marker in text for marker in markers)


def safe_ai_request(session, method, url, reason="", retry_count=None, **kwargs):
    attempt_count = max(1, safe_int(retry_count, 3) or 3)
    method_name = str(method or "post").strip().lower()
    request_func = getattr(session, method_name, None)
    if request_func is None:
        raise AttributeError(f"Session 不支持请求方法: {method_name}")

    last_exc = None
    for attempt in range(1, attempt_count + 1):
        if XIEQU_PROXY_URL:
            if attempt == 1:
                ensure_session_proxy(session, reason=reason or "AI请求")
            else:
                refresh_session_proxy(session, reason=f"{reason or 'AI请求'}重试#{attempt}", force=True)

        request_kwargs = dict(kwargs)
        request_kwargs.setdefault("timeout", 10)
        request_kwargs.setdefault("verify", False)
        try:
            return request_func(url, **request_kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt >= attempt_count or not is_retryable_request_exception(exc):
                raise
            print(
                f"⚠️ [{reason or url}] 请求异常，准备重试 {attempt}/{attempt_count - 1}: {exc}"
            )
            time.sleep(0.8)

    if last_exc:
        raise last_exc
    raise RuntimeError(f"{reason or url} 请求失败")


def get_headers(crypto_inst, token="", is_share=False):
    # 成功脚本对所有活动接口统一使用活动主页面 Referer；分享页仅通过
    # invitationCode 和入口会话体现，避免制作接口被识别为旧分享页面。
    ref = f"https://ai.imusic.cn/h5v/fusion/ai-luck-winnew?cc={CHANNEL_ID}&ca=w7x6"
    headers = {
        "User-Agent": "CtClient;13.3.0;Android;14;V2203A",
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://ai.imusic.cn",
        "Referer": ref,
        "X-Requested-With": "com.ct.client",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "imencrypt": "1",
        "imtimestamp": crypto_inst.ts,
        "imrandomnum": crypto_inst.rdm,
        "imencryptkey": crypto_inst.key_h,
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers

# ===================== 【已优化】账号解析函数，兼容#和@分隔 =====================
def parse_accounts(raw_text):
    accounts = []
    if not raw_text.strip():
        raise ValueError("未填写任何账号，请在青龙环境变量 chinaTelecomAccount 中填写 手机号#密码#AndroidID 格式")
        
    normalized = raw_text.replace("\r", "\n").replace("&", "\n")
    for part in normalized.split("\n"):
        item = part.strip()
        if not item:
            continue
            
        # 兼容 # 和 @ 两种分隔符；末尾可带 16 位十六进制 AndroidID
        android_id = ""
        if "#" in item:
            parts = item.split("#")
            phone = parts[0]
            has_android = len(parts) >= 3 and re.fullmatch(r"[0-9a-fA-F]{16}", parts[-1])
            android_id = parts[-1] if has_android else ""
            password = "#".join(parts[1:-1]) if has_android else "#".join(parts[1:])
        elif "@" in item:
            phone, password = item.split("@", 1)
        else:
            raise ValueError(f"账号格式错误，支持 手机号#密码 或 手机号#密码#AndroidID: {item}")
            
        phone = phone.strip()
        password = password.strip()
        if not phone or not password:
            raise ValueError(f"账号格式错误，手机号或密码为空: {item}")
        accounts.append((phone, password, android_id))
        
    return accounts


def safe_int(v, default=0):
    try:
        return int(str(v).strip())
    except Exception:
        return default


def extract_code(resp_text):
    try:
        return str(json.loads(resp_text).get("code", "")).strip()
    except Exception:
        return ""


def is_success_response(resp_text):
    code = extract_code(resp_text)
    return code == "0000" or '"code":"0000"' in resp_text


def parse_json_text(resp_text, default=None):
    if default is None:
        default = {}
    try:
        return json.loads(resp_text)
    except Exception:
        return default


def extract_desc(resp_text):
    data = parse_json_text(resp_text, {})
    return str(data.get("desc") or data.get("description") or "").strip()


def extract_response_data(resp_obj):
    if not isinstance(resp_obj, dict):
        return {}
    data = resp_obj.get("data")
    if isinstance(data, dict):
        inner = data.get("data")
        if isinstance(inner, dict) and inner:
            return inner
        return data
    return resp_obj


def print_invite_response_log(invite_code, resp_text):
    if not invite_code:
        return
    resp_json = parse_json_text(resp_text, {})
    resp_data = extract_response_data(resp_json)
    mask_code = invite_code[:10] + "..." if len(invite_code) > 10 else invite_code
    parts = [f"invitationCode={mask_code}"]
    code = str(resp_json.get("code") or "").strip()
    desc = str(resp_json.get("desc") or resp_json.get("message") or resp_json.get("description") or "").strip()
    make_id = str(resp_data.get("makeId") or "").strip()
    task_id = str(resp_data.get("taskid") or resp_data.get("taskId") or "").strip()
    if code:
        parts.append(f"code={code}")
    if desc:
        parts.append(f"desc={desc}")
    if make_id:
        parts.append(f"makeId={make_id}")
    if task_id:
        parts.append(f"taskid={task_id}")
    print(f"📨 邀请关联响应: {' | '.join(parts)}")


def is_truthy_flag(value):
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def parse_datetime_text(value):
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%d",
    ):
        try:
            return datetime.strptime(text, fmt)
        except Exception:
            continue
    return None


def decode_response_text(crypto_inst, resp_text):
    dec_text = crypto_inst.decrypt(resp_text)
    if dec_text != resp_text:
        return dec_text
    return resp_text


def load_telecom_token_cache():
    cache_path = Path("chinaTelecom_cache.json")
    if not cache_path.exists():
        return {}
    try:
        raw_text = cache_path.read_text(encoding="utf-8").strip()
        if not raw_text:
            return {}
        data = json.loads(raw_text)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"⚠️ 本地电信缓存读取失败，已忽略: {exc}")
        return {}


def save_telecom_token_cache(cache_data):
    if not isinstance(cache_data, dict):
        return
    cache_path = Path("chinaTelecom_cache.json")
    tmp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
    try:
        tmp_path.write_text(
            json.dumps(cache_data, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8"
        )
        tmp_path.replace(cache_path)
    except Exception as exc:
        print(f"⚠️ 本地电信缓存写入失败，已忽略: {exc}")
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def get_cached_telecom_login(phone):
    cache_data = load_telecom_token_cache()
    item = cache_data.get(str(phone))
    if not isinstance(item, dict):
        return {}
    telecom_token = str(item.get("token") or "").strip()
    user_id = str(item.get("userId") or "").strip()
    if not telecom_token or not user_id:
        return {}
    return item


def update_telecom_token_cache(phone, login_success_result):
    if not isinstance(login_success_result, dict):
        return
    cache_data = load_telecom_token_cache()
    item = dict(login_success_result)
    item["phoneNbr"] = str(item.get("phoneNbr") or phone).strip()
    cache_data[str(phone)] = item
    save_telecom_token_cache(cache_data)


def delete_telecom_token_cache(phone):
    cache_data = load_telecom_token_cache()
    key = str(phone)
    if key not in cache_data:
        return
    cache_data.pop(key, None)
    save_telecom_token_cache(cache_data)


def ensure_valid_sso_login_result(res_sso):
    if not isinstance(res_sso, dict):
        raise Exception(f"SSO返回格式异常: {res_sso}")
    token = str(res_sso.get("token") or "").strip()
    mobile = str(res_sso.get("mobile") or "").strip()
    if not token or not mobile:
        msg = str(res_sso.get("desc") or res_sso.get("msg") or res_sso.get("message") or res_sso).strip()
        raise Exception(f"SSO登录失败: {msg}")
    return token, mobile, res_sso.get("enDataCode")


def do_password_login(session, crypto_inst, phone, password, android_id=""):
    ts_l = time.strftime("%Y%m%d%H%M%S")
    en_p = "".join(chr(ord(c)+2) for c in phone)
    en_pwd = "".join(chr(ord(c)+2) for c in password)
    
    use_android = bool(re.fullmatch(r"[0-9a-fA-F]{16}", str(android_id or "")))
    if use_android:
        client_type = "#11.0.0#channel8#Xiaomi 20#"
        cipher_head, system_version, device_uid = f"Xiaomi 20 8.0.0.{android_id[:12]}", "8.0.0", ""
    else:
        client_type = "#10.5.0#channel50#iPhone 14 Pro Max#"
        cipher_head, system_version, device_uid = f"iPhone 14 15.4.{crypto_inst.rdm[:12]}", "15.4.0", crypto_inst.rdm
    fields = {"loginType": "4", "loginAuthCipherAsymmertric": rsa_encrypt(f"{cipher_head}{phone}{ts_l}{password}0$$$0."),
              "deviceUid": device_uid, "phoneNum": en_p, "authentication": en_pwd, "systemVersion": system_version,
              "isChinatelecom": "" if use_android else "0"}
    if use_android:
        fields.update({"androidId": "".join(chr(ord(c)+2) for c in android_id), "loginAuthCipher": ""})
    login_body = {"headerInfos": {"code": "userLoginNormal", "timestamp": ts_l, "shopId": "20002", "source": "110003", "sourcePassword": "Sid98s", "userLoginName": en_p, "clientType": client_type}, "content": {"fieldData": fields}}
    res_l = safe_ai_request(
        session,
        "post",
        "https://appgologin.189.cn:9031/login/client/userLoginNormal",
        reason="电信账密登录",
        json=login_body
    ).json()
    
    if res_l.get("responseData", {}).get("resultCode") != "0000":
        print(f"❌ 电信账密登录失败: {res_l}")
        raise Exception("Telecom Login Fail")

    l_succ = res_l["responseData"]["data"]["loginSuccessResult"]
    tk_val, uid = l_succ['token'], l_succ['userId']
    update_telecom_token_cache(phone, l_succ)
    print("✓ 账密验证通过，已更新本地电信缓存，正在换取 Ticket...")
    return build_ticket_from_login_seed(session, phone, tk_val, uid)


def do_login(session, crypto_inst, phone, password, android_id=""):
    has_android_id = bool(re.fullmatch(r"[0-9a-fA-F]{16}", str(android_id or "")))
    print("--- 1. 电信登录 & 获取凭证 ---")
    print("登录策略：缓存优先；" + ("缓存失效后使用 AndroidID 账密登录" if has_android_id else "未提供 AndroidID，仅使用已有缓存，缓存失效后跳过账密登录"))
    cached_login = get_cached_telecom_login(phone)
    if cached_login:
        try:
            print("♻️ 命中本地电信缓存，正在换取 Ticket...")
            ticket = build_ticket_from_login_seed(
                session,
                phone,
                str(cached_login.get("token") or "").strip(),
                str(cached_login.get("userId") or "").strip(),
            )
            print("--- 2. SSO 登录 & 身份指纹激活 ---")
            res_sso = sso_login_by_ticket(session, ticket)
            token, mobile, en_data_code = ensure_valid_sso_login_result(res_sso)
            print("✓ 本地电信缓存可用，已跳过账密登录")
            return token, mobile, en_data_code, ticket
        except Exception as exc:
            print((f"⚠️ 本地电信缓存不可用，准备使用 AndroidID 账密登录: {exc}"
                   if has_android_id else f"⚠️ 本地电信缓存不可用，且未提供 AndroidID，跳过账密登录: {exc}"))
            if not is_retryable_request_exception(exc):
                delete_telecom_token_cache(phone)

    if not has_android_id:
        raise Exception("本账号未提供有效 AndroidID，且本地电信缓存不可用；手机号#密码账号无法继续登录")

    print("♻️ 未命中可用缓存，准备使用 AndroidID 进行账密登录")
    ticket = do_password_login(session, crypto_inst, phone, password, android_id)

    print("--- 2. SSO 登录 & 身份指纹激活 ---")
    res_sso = sso_login_by_ticket(session, ticket)
    token, mobile, en_data_code = ensure_valid_sso_login_result(res_sso)
    return token, mobile, en_data_code, ticket


def build_ticket_from_login_seed(session, phone, telecom_token, user_id):
    ts_l = time.strftime("%Y%m%d%H%M%S")
    xml = f"<Request><HeaderInfos><Code>getSingle</Code><Timestamp>{ts_l}</Timestamp><BroadAccount></BroadAccount><BroadToken></BroadToken><ClientType>#9.6.1#channel50#iPhone 14 Pro Max#</ClientType><ShopId>20002</ShopId><Source>110003</Source><SourcePassword>Sid98s</SourcePassword><Token>{telecom_token}</Token><UserLoginName>{phone}</UserLoginName></HeaderInfos><Content><Attach>test</Attach><FieldData><TargetId>{des3_op(str(user_id))}</TargetId><Url>4a6862274835b451</Url></FieldData></Content></Request>"
    res_xml = safe_ai_request(
        session,
        "post",
        "https://appgologin.189.cn:9031/map/clientXML",
        reason="电信换Ticket",
        data=xml,
        headers={"Content-Type": "application/xml"}
    ).text
    tk_match = re.search(r'<Ticket>(.*?)</Ticket>', res_xml)
    if not tk_match:
        print("❌ Ticket 获取失败！")
        raise Exception("Ticket Regex Match Fail")
    return des3_op(tk_match.group(1), decrypt=True)


def sso_login_by_ticket(session, ticket):
    return safe_ai_request(
        session,
        "post",
        "https://ai.imusic.cn/vapi/vue_login/sso_login_v2",
        reason="SSO登录",
        json={"portal":"45","channelId":CHANNEL_ID,"ticket":ticket,"user118100cn":"user118100cn"}
    ).json()


def warmup_session(session, crypto_inst, token, mobile):
    print("--- 3. 环境全量模拟 (Warmup) ---")
    active_token = token
    
    h_share = get_headers(crypto_inst, active_token, is_share=True)
    res1 = safe_ai_request(
        session,
        "post",
        f"https://ai.imusic.cn/vapi/new_member/get_user_info?channelId={CHANNEL_ID}&portal=45&mobile={mobile}",
        reason="Warmup-用户信息",
        headers=h_share,
        data=""
    )
    active_token = check_and_update_token(res1, active_token)
    
    h_share = get_headers(crypto_inst, active_token, is_share=True)
    res2 = safe_ai_request(
        session,
        "post",
        f"https://ai.imusic.cn/vapi/vrbt/check_user_state?mobile={mobile}&is4G=1&is5G=1&isDX=1&channelId={CHANNEL_ID}&portal=45",
        reason="Warmup-用户状态",
        headers=h_share,
        data=""
    )
    active_token = check_and_update_token(res2, active_token)
    
    en_init = crypto_inst.encrypt({"channelId": CHANNEL_ID, "portal": "45", "mobile": mobile, "method": "init"})
    h_share = get_headers(crypto_inst, active_token, is_share=True)
    res3 = safe_ai_request(
        session,
        "post",
        f"https://ai.imusic.cn/hapi/en/api?formData={urllib.parse.quote(en_init)}",
        reason="Warmup-init",
        headers=h_share,
        data=""
    )
    active_token = check_and_update_token(res3, active_token)
    
    ugc_p = crypto_inst.encrypt({"channelId": CHANNEL_ID, "portal": "45", "mobile": mobile})
    h_share = get_headers(crypto_inst, active_token, is_share=True)
    res4 = safe_ai_request(
        session,
        "post",
        f"https://ai.imusic.cn/hapi/diy_ugc/imu/get_ugc_info?formData={urllib.parse.quote(ugc_p)}",
        reason="Warmup-ugc信息",
        headers=h_share,
        data=""
    )
    active_token = check_and_update_token(res4, active_token)

    time.sleep(0.5)
    return active_token

def query_template_meta(session, token):
    h = get_headers(ImCrypto(), token, is_share=False)
    res = safe_ai_request(
        session,
        "post",
        f"https://ai.imusic.cn/hapi/de/api?pageNo=1&pageSize=50&activityId={ACTIVITY_ID}_4&apiName=diy%2FDiyVideoApi%2FqueryActRecommendTemplateList&channelId={CHANNEL_ID}&portal=45",
        reason="查询模板列表",
        headers=h,
        data=""
    )
    data = res.json()
    rows = data.get("data", {}).get("list", [])
    selected = next((item for item in rows
                         if ((TEMPLATE_ID and item.get("templateId") == TEMPLATE_ID)
                             or (TEMPLATE_CONF_ID and item.get("templateConfId") == TEMPLATE_CONF_ID))
                         and item.get("templateId")), None)
    if selected is None:
        selected = next((item for item in rows
                         if item.get("mediaType") == "video"
                         and safe_int(item.get("imageCount"), 0) == 0
                         and item.get("userWords") and item.get("templateId")), None)
    if selected:
        item = selected
        if item:
            return {
                "templateConfId": item.get("templateConfId") or "",
                "templateId": item.get("templateId") or "",
                "userWords": item.get("userWords") or "古风插画，姐姐坐在秋千上。",
                "videoName": item.get("videoName") or "创作",
                "background": item.get("background") or "",
                "isAI": 1 if str(item.get("isAI", 0)) == "1" else 0,
                "arrangeId": item.get("arrangeId") or "",
            }
    return {
        "templateConfId": TEMPLATE_CONF_ID,
        "templateId": TEMPLATE_ID,
        "userWords": "古风插画，姐姐坐在秋千上。",
        "videoName": "创作",
        "background": "",
        "isAI": 0,
        "arrangeId": "",
    }


def post_encrypted_api(session, crypto_inst, token, api_path, payload, is_share=False):
    enc_str = crypto_inst.encrypt(payload)
    api_url = f"https://ai.imusic.cn{api_path}?formData={urllib.parse.quote(enc_str)}"
    h = get_headers(crypto_inst, token, is_share=is_share)
    res = safe_ai_request(
        session,
        "post",
        api_url,
        reason=f"加密接口 {api_path}",
        headers=h,
        data=""
    )
    return res, check_and_update_token(res, token)


def send_stat_message(session, crypto_inst, token, mobile, actname, actparam):
    payload = OrderedDict([
        ("channelId", CHANNEL_ID),
        ("portal", "45"),
        ("mobile", mobile),
        ("actname", actname),
        ("actparam", actparam if str(actparam).endswith("_ca_w7x6") else str(actparam) + "_ca_w7x6"),
        ("sid", getattr(session, "_activity_sid", "")),
        ("invitationCode", getattr(session, "_invite_code", "") or "")
    ])
    return post_encrypted_api(session, crypto_inst, token, "/vapi/vue_stat/sendMessage", payload, is_share=False)


def open_activity_page(session, invite_code=""):
    """Open the new activity entry so the server issues its activity session cookie."""
    if getattr(session, "_activity_sid", ""):
        return session._activity_sid
    # 必须从 /ca/w7x6 进入：该跳转响应才会下发真实 imusic/JSESSIONID。
    # 直接访问 h5 页面虽然返回 200，但不会建立活动会话，制作接口会返回 10019。
    target = "https://ai.imusic.cn/ca/w7x6"
    for _ in range(3):
        res = safe_ai_request(session, "get", target, reason="打开活动入口", allow_redirects=False)
        if res.status_code in (301, 302, 303, 307, 308):
            target = urllib.parse.urljoin(target, res.headers.get("Location", ""))
            parsed = urllib.parse.urlsplit(target)
            if parsed.path.endswith("/ai-luck-winnew") and invite_code:
                q = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
                q.update({"isshare": "0", "invitationCode": invite_code})
                target = urllib.parse.urlunsplit(parsed._replace(query=urllib.parse.urlencode(q)))
            continue
        if res.status_code == 200:
            try:
                session._activity_sid = str(session.cookies.get("imusic") or "")
                return session._activity_sid
            except Exception:
                # curl_cffi may iterate cookie names (strings), while requests
                # exposes Cookie objects; support both implementations.
                for item in session.cookies:
                    if getattr(item, "name", item) == "imusic":
                        session._activity_sid = str(getattr(item, "value", "") or "")
                        return session._activity_sid
                return ""
        break
    return ""


def mark_invite_entry(session, crypto_inst, token, mobile, invite_code):
    """Decode the opaque invitation token and emit the official share beacon."""
    if not invite_code:
        return token
    try:
        res, active_token = post_encrypted_api(
            session, crypto_inst, token, "/hapi/en/api",
            OrderedDict([("activityId", ACTIVITY_ID), ("mobile", invite_code), ("type", 2),
                         ("invitationCode", invite_code),
                         ("apiName", "diy/DiyVideoApi/getEncryptDecryptMobile"),
                         ("channelId", CHANNEL_ID), ("portal", "45")]),
            is_share=False)
        info = parse_json_text(crypto_inst.decrypt(res.text), {})
        if str(info.get("code")) != "0000" or not info.get("data"):
            return active_token
        inviter = str(info.get("data")).split("|", 1)[0]
        if inviter:
            _, active_token = send_stat_message(
                session, crypto_inst, active_token, mobile,
                "activity_vring_sharinglink_h5_20260128",
                f"activityID_{ACTIVITY_ID}_templateID_null_vidioID_null_分享人手机号_{inviter}_被分享手机号_{mobile}_templateconfID_null_entrance_{CHANNEL_ID}")
        return active_token
    except Exception as exc:
        print(f"⚠️ 邀请入口处理失败，继续执行活动: {exc}")
        return token


def query_fun_play_score(session, crypto_inst, token, mobile):
    res, active_token = post_encrypted_api(
        session,
        crypto_inst,
        token,
        "/hapi/en/api",
        OrderedDict([
            ("activityId", ACTIVITY_ID),
            ("mobile", mobile),
            ("apiName", "act/LaborApi/getOperationTotalScoreOrRemainingScore"),
            ("channelId", CHANNEL_ID),
            ("portal", "45")
        ]),
        is_share=False
    )
    dec_text = crypto_inst.decrypt(res.text)
    score_data = {}
    try:
        score_data = json.loads(dec_text).get("data", {}) or {}
        print(f"📊 当前积分: totalScore={score_data.get('totalScore', '')}, remainingScore={score_data.get('remainingScore', '')}")
    except Exception:
        pass
    return active_token, score_data


def extract_lottery_point_award(award_name):
    text = str(award_name or "").strip()
    if "点数" not in text:
        return 0
    match = re.search(r"(\d+)\s*点数", text)
    if not match:
        return 0
    return safe_int(match.group(1), 0)


def run_lottery(session, crypto_inst, token, mobile):
    active_token, score_data = query_fun_play_score(session, crypto_inst, token, mobile)
    remaining_score = safe_int(score_data.get("remainingScore"), 0)
    lottery_count = remaining_score // LOTTERY_COST_SCORE
    print(f"🎰 可用积分={remaining_score}，按每次{LOTTERY_COST_SCORE}积分计算，当前可抽奖 {lottery_count} 次")
    if lottery_count <= 0:
        return active_token

    for index in range(1, lottery_count + 1):
        res, active_token = post_encrypted_api(
            session,
            crypto_inst,
            active_token,
            "/hapi/en/api",
            OrderedDict([
                ("activityId", ACTIVITY_ID),
                ("mobile", mobile),
                ("apiName", "act/LaborApi/operationIntegralLottery"),
                ("channelId", CHANNEL_ID),
                ("portal", "45")
            ]),
            is_share=False
        )
        dec_text = crypto_inst.decrypt(res.text)
        print(f"🎁 第{index}次抽奖结果: {dec_text}")
        resp_obj = parse_json_text(dec_text, {})
        award_data = resp_obj.get("data", {}) or {}
        award_index = str(award_data.get("awardIndex") or "").strip()
        award_id = str(award_data.get("awardId") or "").strip()
        award_name = str(award_data.get("awardName") or "").strip()
        if is_lottery_phone_fee_index(award_index) or ("话费" in award_name and award_id):
            print(f"📲 抽中奖励话费，准备立即领取: awardName={award_name}, awardId={award_id}, awardIndex={award_index}")
            try:
                if award_id:
                    active_token, claim_resp = claim_lottery_phone_fee_award(
                        session, crypto_inst, active_token, mobile, award_id
                    )
                    print(f"📝 话费领取响应: {claim_resp}")
                else:
                    print("⚠️ 抽中话费但响应里缺少 awardId，稍后走中奖记录补领")
            except Exception as exc:
                print(f"⚠️ 抽中奖励话费后立即领取失败，稍后走中奖记录补领: {exc}")

        point_award = extract_lottery_point_award(award_name)
        if point_award > 0:
            print(f"🧮 抽中 {point_award} 点数，本轮不按新增点数补抽")
        time.sleep(0.2)

    return active_token


def query_current_issue_info(session, crypto_inst, token):
    res, active_token = post_encrypted_api(
        session,
        crypto_inst,
        token,
        "/hapi/en/api",
        OrderedDict([
            ("activityId", ACTIVITY_ID),
            ("apiName", "act/LaborApi/getOperationCurrentIssueInfo"),
            ("channelId", CHANNEL_ID),
            ("portal", "45")
        ]),
        is_share=False
    )
    dec_text = crypto_inst.decrypt(res.text)
    issue_data = parse_json_text(dec_text, {}).get("data", {}) or {}
    return active_token, issue_data


def build_phase_info_from_issue(issue_data):
    if not isinstance(issue_data, dict):
        return None
    start_dt = parse_datetime_text(issue_data.get("startTime"))
    end_dt = parse_datetime_text(issue_data.get("endTime"))
    current_dt = parse_datetime_text(issue_data.get("currentTime")) or datetime.now()
    if not start_dt or not end_dt:
        return None

    day_index = (current_dt.date() - start_dt.date()).days + 1
    day_index = max(1, min(3, day_index))
    return {
        "issue_name": str(issue_data.get("issueName") or "").strip(),
        "issue_number": str(issue_data.get("issueNumber") or "").strip(),
        "start_dt": start_dt,
        "end_dt": end_dt,
        "current_dt": current_dt,
        "day_index": day_index,
    }


def build_fallback_phase_info():
    now_dt = datetime.now()
    day_offset = (now_dt.toordinal() - 1) % 3
    phase_start = datetime.combine(now_dt.date() - timedelta(days=day_offset), datetime.min.time())
    phase_end = phase_start + timedelta(days=3, seconds=-1)
    day_index = (now_dt.date() - phase_start.date()).days + 1
    day_index = max(1, min(3, day_index))
    return {
        "issue_name": "当前期次(回退推断)",
        "issue_number": "",
        "start_dt": phase_start,
        "end_dt": phase_end,
        "current_dt": now_dt,
        "day_index": day_index,
    }


def get_phase_info(session, crypto_inst, token):
    active_token, issue_data = query_current_issue_info(session, crypto_inst, token)
    phase_info = build_phase_info_from_issue(issue_data)
    if not phase_info:
        phase_info = build_fallback_phase_info()
        print("⚠️ 当前期次接口解析失败，已按 3 天一期规则回退推断")

    print(
        f"🗓️ 当前期次: {phase_info['issue_name']} ({phase_info['issue_number']}) | "
        f"{phase_info['start_dt']:%Y-%m-%d} ~ {phase_info['end_dt']:%Y-%m-%d} | "
        f"第 {phase_info['day_index']} 天"
    )
    return active_token, phase_info


def record_belongs_to_phase(record, phase_info):
    if not isinstance(record, dict) or not phase_info:
        return False
    issue_number = str(phase_info.get("issue_number") or "").strip()
    if issue_number and str(record.get("workId") or "").strip() == issue_number:
        return True

    record_dt = parse_datetime_text(record.get("dataTime") or record.get("createDate") or record.get("createTime"))
    if not record_dt:
        return False
    return phase_info["start_dt"] <= record_dt <= phase_info["end_dt"]


def classify_point_record(record):
    area = str(record.get("area") or "").strip().upper()
    video_name = str(record.get("videoName") or "").strip()
    score_type = str(record.get("scoreType") or "").strip()
    score_desc = str(record.get("scoreDesc") or "").strip()

    if area == "PRODUCTION" or score_type == "1" or "制作获得" in video_name or ("制作" in score_desc or "创作" in score_desc):
        return "production"
    if area == "SET_VIDEO" or score_type == "6" or "设置获得" in video_name or "彩铃" in score_desc or "设置" in score_desc:
        return "set_video"
    if score_type in ("4", "5") or "消耗" in video_name:
        return "consume"
    return "other"


def summarize_phase_point_records(records, phase_info):
    today = (phase_info or {}).get("current_dt", datetime.now()).date()
    summary = {
        "production_total": 0,
        "production_today": 0,
        "set_total": 0,
        "set_today": 0,
        "positive_today_total": 0,
    }
    for record in records or []:
        record_dt = parse_datetime_text(record.get("dataTime") or record.get("createDate") or record.get("createTime"))
        record_day = record_dt.date() if record_dt else None
        record_type = classify_point_record(record)

        if record_type == "production":
            summary["production_total"] += 1
            if record_day == today:
                summary["production_today"] += 1
                summary["positive_today_total"] += 1
        elif record_type == "set_video":
            summary["set_total"] += 1
            if record_day == today:
                summary["set_today"] += 1
                summary["positive_today_total"] += 1
    return summary


def query_points_record_page(session, crypto_inst, token, mobile, page_no=1, page_size=100):
    res, active_token = post_encrypted_api(
        session,
        crypto_inst,
        token,
        "/hapi/en/api",
        OrderedDict([
            ("activityId", ACTIVITY_ID),
            ("mobile", mobile),
            ("pageNo", page_no),
            ("pageSize", page_size),
            ("apiName", "act/LaborApi/getOperationRecordList"),
            ("channelId", CHANNEL_ID),
            ("portal", "45")
        ]),
        is_share=False
    )
    data = parse_json_text(crypto_inst.decrypt(res.text), {}).get("data", {}) or {}
    return active_token, data


def query_award_record_page(session, crypto_inst, token, mobile, page_no=1, page_size=20):
    res, active_token = post_encrypted_api(
        session,
        crypto_inst,
        token,
        "/hapi/en/api",
        OrderedDict([
            ("activityId", ACTIVITY_ID),
            ("mobile", mobile),
            ("pageNo", page_no),
            ("pageSize", page_size),
            ("apiName", "act/LaborApi/getOperationPrizeRecordList"),
            ("channelId", CHANNEL_ID),
            ("portal", "45")
        ]),
        is_share=False
    )
    data = parse_json_text(crypto_inst.decrypt(res.text), {}).get("data", {}) or {}
    return active_token, data


def is_lottery_phone_fee_index(award_index):
    return str(award_index or "").strip() in ("16320105", "16320205", "16320305")


def fetch_award_records(session, crypto_inst, token, mobile):
    active_token = token
    page_no = 1
    total_pages = 1
    records = []
    while page_no <= total_pages:
        active_token, page_data = query_award_record_page(
            session, crypto_inst, active_token, mobile, page_no, 50
        )
        record_list = page_data.get("list") or []
        total_pages = max(page_no, safe_int(page_data.get("pages"), 1))
        records.extend(record_list)
        if not record_list or page_no >= total_pages:
            break
        page_no += 1
        time.sleep(0.08)
    return active_token, records


def format_ticket_time(value, date_only=False):
    dt = parse_datetime_text(value)
    if dt:
        return dt.strftime("%Y-%m-%d" if date_only else "%Y-%m-%d %H:%M:%S")
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("T", " ").replace("/", "-")
    if date_only and " " in text:
        text = text.split(" ", 1)[0]
    return text


def ticket_has_contact_info(item):
    if not isinstance(item, dict):
        return False
    return any(str(item.get(key) or "").strip() for key in ("telephone", "contacter", "address"))


def get_coupon_ticket_status_text(item):
    status = str((item or {}).get("ticketStatus") or "").strip()
    if status == "0":
        draw_time = format_ticket_time((item or {}).get("drawTime"), date_only=True)
        return f"待开奖({draw_time})" if draw_time else "待开奖"
    if status == "1":
        return "已中奖(已填收货信息)" if ticket_has_contact_info(item) else "已中奖(待填收货信息)"
    if status:
        return "未中奖"
    return "未知"


def query_my_coupon_tickets(session, crypto_inst, token, mobile):
    res, active_token = post_encrypted_api(
        session,
        crypto_inst,
        token,
        "/hapi/en/api",
        OrderedDict([
            ("mobile", mobile),
            ("activityId", ACTIVITY_ID),
            ("apiName", "act/LaborApi/getOperationMyTickets"),
            ("channelId", CHANNEL_ID),
            ("portal", "45")
        ]),
        is_share=False
    )
    dec_text = decode_response_text(crypto_inst, res.text)
    resp_obj = parse_json_text(dec_text, {})
    data = resp_obj.get("data")
    if isinstance(data, list):
        tickets = data
    elif isinstance(data, dict):
        tickets = data.get("list") or data.get("rows") or data.get("data") or []
    else:
        tickets = []
    if not isinstance(tickets, list):
        tickets = []
    return active_token, tickets, resp_obj, dec_text


def ticket_belongs_to_current_issue(item, phase_info):
    if not isinstance(item, dict) or not isinstance(phase_info, dict):
        return False
    current_issue_name = str(phase_info.get("issue_name") or "").strip()
    current_issue_number = str(phase_info.get("issue_number") or "").strip()
    ticket_issue_name = str(item.get("issueName") or "").strip()
    if current_issue_name and ticket_issue_name and ticket_issue_name == current_issue_name:
        return True
    for key in ("issueNumber", "issueNo", "issueId", "workId"):
        value = str(item.get(key) or "").strip()
        if current_issue_number and value and value == current_issue_number:
            return True
    return False


def query_coupon_ticket_status(session, crypto_inst, token, mobile, phase_info=None, reason=""):
    active_token, tickets, resp_obj, dec_text = query_my_coupon_tickets(
        session, crypto_inst, token, mobile
    )
    prefix = f"[{reason}] " if reason else ""
    code = str(resp_obj.get("code") or "").strip()
    if code and code != "0000":
        desc = extract_desc(dec_text) or dec_text
        print(f"⚠️ {prefix}我的券码查询失败: {desc}")
        return active_token

    if not tickets:
        print(f"🎟️ {prefix}我的券码: 暂无券码")
        return active_token

    pending_tickets = [item for item in tickets if str(item.get("ticketStatus") or "").strip() == "0"]
    winning_tickets = [item for item in tickets if str(item.get("ticketStatus") or "").strip() == "1"]
    losing_tickets = [item for item in tickets if str(item.get("ticketStatus") or "").strip() not in ("0", "1")]
    current_issue_tickets = [item for item in tickets if ticket_belongs_to_current_issue(item, phase_info)]
    current_issue_name = str((phase_info or {}).get("issue_name") or "").strip()
    if not current_issue_name and current_issue_tickets:
        current_issue_name = str(current_issue_tickets[0].get("issueName") or "").strip()

    print(
        f"🎟️ {prefix}我的券码: 共{len(tickets)}张"
        f"{f'，本期{len(current_issue_tickets)}张' if current_issue_tickets else ''}"
        f"，待开奖{len(pending_tickets)}张，已中奖{len(winning_tickets)}张，未中奖{len(losing_tickets)}张"
    )

    if current_issue_tickets:
        current_issue_pending = [item for item in current_issue_tickets if str(item.get("ticketStatus") or "").strip() == "0"]
        current_issue_winning = [item for item in current_issue_tickets if str(item.get("ticketStatus") or "").strip() == "1"]
        current_issue_losing = [item for item in current_issue_tickets if str(item.get("ticketStatus") or "").strip() not in ("0", "1")]
        print(
            f"🎟️ {prefix}{current_issue_name or '当前期次'}: "
            f"待开奖{len(current_issue_pending)}张，已中奖{len(current_issue_winning)}张，未中奖{len(current_issue_losing)}张"
        )

    if not winning_tickets:
        if pending_tickets:
            nearest_draw = format_ticket_time(pending_tickets[0].get("drawTime"), date_only=True)
            if nearest_draw:
                print(f"🎟️ {prefix}当前暂无已中奖券码，待开奖券码将在 {nearest_draw} 开奖")
            else:
                print(f"🎟️ {prefix}当前暂无已中奖券码，仍有 {len(pending_tickets)} 张券码待开奖")
        else:
            print(f"🎟️ {prefix}当前暂无已中奖券码")
        return active_token

    waiting_fill_count = 0
    for index, item in enumerate(winning_tickets, start=1):
        if not ticket_has_contact_info(item):
            waiting_fill_count += 1
        issue_name = str(item.get("issueName") or "").strip() or "未知期次"
        winning_index = str(item.get("winningIndex") or "").strip()
        ticket_serial = str(item.get("ticketSerial") or "").strip()
        draw_time = format_ticket_time(item.get("drawTime"), date_only=True)
        obtain_time = format_ticket_time(item.get("obtainTime"))
        status_text = get_coupon_ticket_status_text(item)

        parts = [issue_name, status_text]
        if winning_index:
            parts.append(f"序号={winning_index}")
        if ticket_serial:
            parts.append(f"券码={ticket_serial}")
        if draw_time:
            parts.append(f"开奖时间={draw_time}")
        if obtain_time:
            parts.append(f"获得时间={obtain_time}")
        print(f"🎟️ {prefix}中奖 {index}/{len(winning_tickets)}: {' | '.join(parts)}")

    if waiting_fill_count > 0:
        print(f"📦 {prefix}有 {waiting_fill_count} 张中奖券码待填写收货信息，请前往“我的券码”处理")
    return active_token


def claim_lottery_phone_fee_award(session, crypto_inst, token, mobile, award_id):
    res, active_token = post_encrypted_api(
        session,
        crypto_inst,
        token,
        "/hapi/en/api",
        OrderedDict([
            ("mobile", mobile),
            ("awardId", award_id),
            ("activityId", ACTIVITY_ID),
            ("apiName", "act/LaborApi/extractPhoneBill"),
            ("channelId", CHANNEL_ID),
            ("portal", "45")
        ]),
        is_share=False
    )
    return active_token, decode_response_text(crypto_inst, res.text)


def claim_pending_phone_fee_awards(session, crypto_inst, token, mobile, reason="", award_records=None):
    active_token = token
    records = award_records
    if records is None:
        active_token, records = fetch_award_records(session, crypto_inst, token, mobile)
    pending_records = [
        item for item in (records or [])
        if is_lottery_phone_fee_index(item.get("awardIndex"))
        and str(item.get("status") or "").strip() == "0"
        and str(item.get("awardId") or "").strip()
    ]
    if not pending_records:
        return active_token

    prefix = f"[{reason}] " if reason else ""
    print(f"🎁 {prefix}发现 {len(pending_records)} 条未领取话费，开始补领")
    claimed_count = 0
    for index, item in enumerate(pending_records, start=1):
        award_id = str(item.get("awardId") or "").strip()
        award_name = str(item.get("awardName") or "").strip()
        lottery_date = str(item.get("lotteryDate") or "").strip()
        print(f"🎁 {prefix}补领 {index}/{len(pending_records)}: {award_name} | awardId={award_id} | lotteryDate={lottery_date}")
        try:
            active_token, resp_text = claim_lottery_phone_fee_award(
                session, crypto_inst, active_token, mobile, award_id
            )
            print(f"📝 {prefix}话费领取响应: {resp_text}")
            if extract_code(resp_text) == "0000":
                claimed_count += 1
        except Exception as exc:
            print(f"⚠️ {prefix}话费补领失败，已忽略当前记录: {exc}")
        time.sleep(0.2)

    print(f"✅ {prefix}话费补领结束，成功 {claimed_count}/{len(pending_records)}")
    return active_token


def query_phase_records(session, crypto_inst, token, mobile, phase_info, query_awards=True):
    active_token = token
    page_no = 1
    total_pages = 1
    phase_records = []

    while page_no <= total_pages:
        active_token, page_data = query_points_record_page(
            session, crypto_inst, active_token, mobile, page_no, 100
        )
        record_list = page_data.get("list") or []
        total_pages = max(page_no, safe_int(page_data.get("pages"), 1))
        phase_records.extend([item for item in record_list if record_belongs_to_phase(item, phase_info)])
        if not record_list or page_no >= total_pages:
            break
        page_no += 1
        time.sleep(0.08)

    award_data = {}
    if query_awards:
        active_token, award_data = query_award_record_page(session, crypto_inst, active_token, mobile)

    summary = summarize_phase_point_records(phase_records, phase_info)
    print(
        f"📒 本期点数明细: 制作获得 {summary['production_total']} 次"
        f"(今日 {summary['production_today']} 次)，设置获得 {summary['set_total']} 次"
        f"(今日 {summary['set_today']} 次)"
    )
    if query_awards:
        print(f"🎁 本期中奖记录总数: {safe_int(award_data.get('total'), 0)}")
    return active_token, phase_records, summary, award_data


def query_ai_result_videos_page(session, crypto_inst, token, mobile, page_no=1, page_size=50):
    res, active_token = post_encrypted_api(
        session,
        crypto_inst,
        token,
        "/hapi/en/api",
        OrderedDict([
            ("mobile", mobile),
            ("aid", ACTIVITY_ID),
            ("pageNo", page_no),
            ("pageSize", page_size),
            ("apiName", "diy/AiApi/queryAiResultVideos"),
            ("channelId", CHANNEL_ID),
            ("portal", "45")
        ]),
        is_share=False
    )
    data = parse_json_text(crypto_inst.decrypt(res.text), {}).get("data", {}) or {}
    return active_token, data


def fetch_ai_result_videos(session, crypto_inst, token, mobile):
    active_token = token
    page_no = 1
    total = None
    works = []
    while True:
        active_token, page_data = query_ai_result_videos_page(
            session, crypto_inst, active_token, mobile, page_no, 50
        )
        diy_list = page_data.get("diyList") or []
        works.extend(diy_list)
        total = safe_int(page_data.get("total"), len(works))
        if not diy_list or len(works) >= total:
            break
        page_no += 1
        time.sleep(0.08)
    return active_token, works


def get_work_video_id(work):
    return str((work or {}).get("video_id") or (work or {}).get("videoId") or "").strip()


def get_work_en_video_id(work):
    return str((work or {}).get("en_video_id") or (work or {}).get("enVideoId") or "").strip()


def get_work_name(work):
    return str((work or {}).get("name") or (work or {}).get("videoName") or "AI作品").strip()


def get_work_aid(work):
    return str((work or {}).get("description") or ACTIVITY_ID).strip() or ACTIVITY_ID


def get_work_template_id(work):
    return str(
        (work or {}).get("video_template_id")
        or (work or {}).get("templateId")
        or ""
    ).strip()


def get_work_template_conf_id(work):
    return str(
        (work or {}).get("piece_id")
        or (work or {}).get("template_conf_id")
        or (work or {}).get("templateConfId")
        or ""
    ).strip()


def get_number_template_id(template_id):
    text = str(template_id or "").strip()
    match = re.search(r"\d+", text)
    return match.group(0) if match else text


def get_work_set_status_text(work):
    diy_desc = str((work or {}).get("diy_desc") or (work or {}).get("diyDesc") or "").strip()
    valid_date = str((work or {}).get("validDate") or (work or {}).get("valid_date") or "").strip()
    return f"diy_state={safe_int((work or {}).get('diy_state'), 0)}, state={safe_int((work or {}).get('state'), 0)}, diy_desc={diy_desc!r}, validDate={valid_date!r}"


def is_work_already_set_or_setting(work):
    if not isinstance(work, dict):
        return False
    diy_state = safe_int(work.get("diy_state"), 0)
    state = safe_int(work.get("state"), 0)
    diy_desc = str(work.get("diy_desc") or work.get("diyDesc") or "").strip()
    if diy_state in (1, 2):
        return True
    if state == 2:
        return True
    if any(flag in diy_desc for flag in ("设置成功", "已提交设置", "设置中", "生效中")):
        return True
    return False


def find_work_by_video_id(works, video_id):
    target = str(video_id or "").strip()
    if not target:
        return None
    for work in works or []:
        if get_work_video_id(work) == target:
            return work
    return None


def refresh_single_work_status(session, crypto_inst, token, mobile, video_id):
    active_token, works = fetch_ai_result_videos(session, crypto_inst, token, mobile)
    return active_token, find_work_by_video_id(works, video_id)


def is_current_phase_work(work, phase_info):
    if not phase_info:
        return False
    create_dt = parse_datetime_text(work.get("create_time"))
    if not create_dt:
        return False
    return phase_info["start_dt"] <= create_dt <= phase_info["end_dt"]


def is_work_eligible_for_set_ring(work):
    if not isinstance(work, dict):
        return False
    audit_state = safe_int(work.get("audit_state"), 0)
    if audit_state != 1:
        return False
    if is_work_already_set_or_setting(work):
        return False
    state = safe_int(work.get("state"), 0)
    if state not in (0, 1):
        return False
    return bool(work.get("video_id") or work.get("videoId"))


def choose_set_ring_candidates(works, phase_info, limit_count):
    eligible = [work for work in works or [] if is_work_eligible_for_set_ring(work)]

    def sort_key(work):
        create_dt = parse_datetime_text(work.get("create_time")) or datetime.min
        return -int(create_dt.timestamp()) if create_dt != datetime.min else 0

    eligible.sort(key=sort_key)
    return eligible[:max(0, limit_count)]


def send_set_ring_stat_events(session, crypto_inst, token, mobile, work):
    active_token = token
    aid = get_work_aid(work)
    template_id = get_work_template_id(work)
    template_num = get_number_template_id(template_id)
    template_conf_id = get_work_template_conf_id(work)
    if not aid or not template_num:
        return active_token

    events = [
        (
            "page_vring_setsec_20250616",
            f"activityID_{aid}_templateID_{template_num}_entrance_{CHANNEL_ID}_templateconfID_{template_conf_id}",
        ),
        (
            "activity_vring_setsec_20250616",
            f"activityID_{aid}_templateID_{template_num}_ringID_null_entrance_{CHANNEL_ID}_templateconfID_{template_conf_id}",
        ),
        (
            "activity_vring_my_set_20250616",
            f"activityID_{aid}_templateID_{template_num}_entrance_{CHANNEL_ID}_templateconfID_{template_conf_id}",
        ),
    ]
    for actname, actparam in events:
        try:
            _, active_token = send_stat_message(session, crypto_inst, active_token, mobile, actname, actparam)
            time.sleep(0.05)
        except Exception as exc:
            print(f"⚠️ 设彩铃埋点失败({actname})，已忽略: {exc}")
    return active_token


def post_plain_form_api(session, crypto_inst, token, api_path, payload, is_share=False):
    headers = get_headers(crypto_inst, token, is_share=is_share).copy()
    for key in ("imencrypt", "imtimestamp", "imrandomnum", "imencryptkey"):
        headers.pop(key, None)
    res = safe_ai_request(
        session,
        "post",
        f"https://ai.imusic.cn{api_path}",
        reason=f"明文接口 {api_path}",
        headers=headers,
        data=payload
    )
    return res, check_and_update_token(res, token)


def query_set_ring_user_state(session, crypto_inst, token, mobile):
    headers = get_headers(crypto_inst, token, is_share=True)
    res = safe_ai_request(
        session,
        "post",
        f"https://ai.imusic.cn/vapi/vrbt/check_user_state?mobile={mobile}&is4G=1&is5G=1&isDX=1&channelId={CHANNEL_ID}&portal=45",
        reason="设彩铃预检-用户状态",
        headers=headers,
        data=""
    )
    active_token = check_and_update_token(res, token)
    try:
        resp_json = res.json()
    except Exception:
        resp_json = parse_json_text(res.text, {})
    data = extract_response_data(resp_json)
    return active_token, resp_json, data if isinstance(data, dict) else {}


def query_set_ring_open_tip(session, crypto_inst, token, mobile):
    headers = get_headers(crypto_inst, token, is_share=False)
    res = safe_ai_request(
        session,
        "post",
        f"https://ai.imusic.cn/vapi/vue_client/query_open_video_tip?mobile={mobile}&actid={ACTIVITY_ID}&config=1&isVrtMonth=1&isAutoRing=1&portal=45&channelId={CHANNEL_ID}",
        reason="设彩铃预检-开通提示",
        headers=headers,
        data=""
    )
    active_token = check_and_update_token(res, token)
    try:
        resp_json = res.json()
    except Exception:
        resp_json = parse_json_text(res.text, {})
    data = extract_response_data(resp_json)
    if not isinstance(data, dict) or not data:
        data = resp_json if isinstance(resp_json, dict) else {}
    return active_token, resp_json, data


def query_set_ring_service_member_info(session, crypto_inst, token, mobile):
    headers = get_headers(crypto_inst, token, is_share=True)
    res = safe_ai_request(
        session,
        "post",
        f"https://ai.imusic.cn/vapi/new_member/get_user_info?channelId={CHANNEL_ID}&portal=45&mobile={mobile}",
        reason="设彩铃预检-服务权益",
        headers=headers,
        data=""
    )
    active_token = check_and_update_token(res, token)
    try:
        resp_json = res.json()
    except Exception:
        resp_json = parse_json_text(res.text, {})
    member_data = {}
    if isinstance(resp_json, dict):
        member_data = (
            resp_json.get("memberInfo")
            or ((resp_json.get("data") or {}).get("memberInfo") if isinstance(resp_json.get("data"), dict) else {})
            or extract_response_data(resp_json)
            or {}
        )
    return active_token, resp_json, member_data if isinstance(member_data, dict) else {}


def build_set_ring_account_precheck(open_tip_data, state_data, member_data):
    open_tip_data = open_tip_data if isinstance(open_tip_data, dict) else {}
    state_data = state_data if isinstance(state_data, dict) else {}
    member_data = member_data if isinstance(member_data, dict) else {}

    is_dx = str(state_data.get("isDX") or "").strip() == "1"
    has_volte = (
        str(state_data.get("user_4g") or "").strip() == "1"
        or str(state_data.get("user_5g") or "").strip() == "1"
    )
    vrbt_enabled = is_truthy_flag(open_tip_data.get("vrbt"))
    order_status = str(open_tip_data.get("orderStatus") or "").strip()
    diy_left_raw = str(member_data.get("privilegeVrbtDIYLeftNum") or "").strip()
    diy_exp_raw = str(member_data.get("privilegeVrbtDIYExperienceLeftNum") or "").strip()
    specific_left_raw = str(member_data.get("specificRingLeftNum") or "").strip()
    diy_left = safe_int(diy_left_raw, 0)
    diy_exp_left = safe_int(diy_exp_raw, 0)
    specific_left = safe_int(specific_left_raw, 0)

    direct_eligible = False
    reason = ""
    if not is_dx:
        reason = "非电信号码"
    elif not has_volte:
        reason = "未检测到4G/5G VoLTE条件"
    elif not vrbt_enabled:
        reason = (
            str(open_tip_data.get("tip") or "").strip()
            or str(open_tip_data.get("limitOpenTip") or "").strip()
            or "当前未开通视频彩铃功能"
        )
    elif order_status in ("1", "2"):
        reason = "视频彩铃功能正在开通中"
    elif diy_left_raw == "-1" or diy_left > 0 or diy_exp_left > 0 or specific_left > 0:
        direct_eligible = True
        reason = (
            str(open_tip_data.get("tip") or "").strip()
            or str(member_data.get("balanceOrderTimesTip") or "").strip()
            or "可免验证码直设"
        )
    else:
        reason = (
            str(member_data.get("balanceOrderTimesTip") or "").strip()
            or "当前账号无可直设权益"
        )

    return OrderedDict([
        ("isDX", state_data.get("isDX")),
        ("user4g", state_data.get("user_4g")),
        ("user5g", state_data.get("user_5g")),
        ("vrbt", open_tip_data.get("vrbt")),
        ("orderStatus", order_status),
        ("tip", open_tip_data.get("tip")),
        ("privilegeVrbtDIYLeftNum", diy_left_raw),
        ("privilegeVrbtDIYExperienceLeftNum", diy_exp_raw),
        ("specificRingLeftNum", specific_left_raw),
        ("balanceOrderTimesTip", member_data.get("balanceOrderTimesTip")),
        ("directEligible", direct_eligible),
        ("reason", reason),
    ])


def is_set_ring_accepted(resp_text):
    code = extract_code(resp_text)
    if code == "0000":
        return True
    if code == "10008":
        return True
    desc = extract_desc(resp_text)
    return "已提交设置" in desc or "设置成功" in desc


def submit_set_ring(session, crypto_inst, token, mobile, work):
    payload = OrderedDict([
        ("channelId", CHANNEL_ID),
        ("portal", "45"),
        ("mobile", mobile),
        ("videoId", str(work.get("video_id") or work.get("videoId") or "")),
        ("name", work.get("name") or work.get("videoName") or "AI作品"),
        ("aid", work.get("description") or ACTIVITY_ID),
        ("validCode", ""),
        ("visibility", safe_int(work.get("visibility"), 0)),
        ("other_diy", safe_int(work.get("other_diy"), 1)),
        ("state", 2),
        ("sendMsgType", "act_order"),
        ("isOpenResonance", 0),
        ("isCheckAuto", 0),
        ("column", "")
    ])
    print(f"📦 设彩铃payload: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}")

    active_token = token
    res, active_token = post_encrypted_api(
        session,
        crypto_inst,
        active_token,
        "/hapi/diy_ugc/au/order_or_update",
        payload,
        is_share=False
    )
    resp_text = decode_response_text(crypto_inst, res.text)
    if is_set_ring_accepted(resp_text):
        return active_token, resp_text

    res_plain, active_token = post_plain_form_api(
        session,
        crypto_inst,
        active_token,
        "/hapi/diy_ugc/au/order_or_update",
        payload,
        is_share=False
    )
    return active_token, decode_response_text(crypto_inst, res_plain.text)


def run_set_ring_flow(session, crypto_inst, token, mobile, phase_info, phase_records=None, point_summary=None):
    active_token = token
    if point_summary is None:
        active_token, phase_records, point_summary, _ = query_phase_records(
            session, crypto_inst, active_token, mobile, phase_info, query_awards=False
        )

    remaining_set_quota = max(0, 2 - safe_int(point_summary.get("set_total"), 0))
    if remaining_set_quota <= 0:
        print("🔔 本期设置彩铃奖励次数已满(2 次)，跳过设彩铃")
        return active_token

    precheck_snapshot = None
    precheck_complete = False
    try:
        active_token, state_raw, state_data = query_set_ring_user_state(
            session, crypto_inst, active_token, mobile
        )
        active_token, open_tip_raw, open_tip_data = query_set_ring_open_tip(
            session, crypto_inst, active_token, mobile
        )
        active_token, member_raw, member_data = query_set_ring_service_member_info(
            session, crypto_inst, active_token, mobile
        )
        precheck_snapshot = build_set_ring_account_precheck(open_tip_data, state_data, member_data)
        precheck_complete = bool(state_raw) and bool(open_tip_raw) and bool(member_raw)
        precheck_snapshot["checked"] = precheck_complete
        print(
            "🔍 彩铃直设账号预检: "
            f"{json.dumps(precheck_snapshot, ensure_ascii=False, separators=(',', ':'), default=str)}"
        )
        if precheck_complete and not precheck_snapshot["directEligible"]:
            print(f"⏭️ 当前账号不满足免验证码直设条件，跳过设彩铃: {precheck_snapshot['reason']}")
            return active_token
    except Exception as exc:
        print(f"⚠️ 彩铃直设账号预检失败，本轮继续尝试设彩铃: {exc}")

    active_token, works = fetch_ai_result_videos(session, crypto_inst, active_token, mobile)
    candidates = choose_set_ring_candidates(works, phase_info, remaining_set_quota)
    if not candidates:
        print("🔕 暂无可设置为彩铃的 AI 作品")
        return active_token

    print(f"🎼 本期剩余设彩铃奖励次数: {remaining_set_quota}，准备尝试 {len(candidates)} 个作品")
    accepted_count = 0
    for index, work in enumerate(candidates, start=1):
        work_name = get_work_name(work)
        video_id = get_work_video_id(work)
        if XIEQU_PROXY_URL:
            prepare_proxy_for_action(session, reason=f"设彩铃#{index}")
        print(
            f"🎵 尝试设彩铃 {index}/{len(candidates)}: {work_name} | "
            f"videoId={video_id}"
        )
        try:
            active_token = send_set_ring_stat_events(session, crypto_inst, active_token, mobile, work)
            active_token, resp_text = submit_set_ring(session, crypto_inst, active_token, mobile, work)
            print(f"📝 设彩铃响应: {resp_text}")
            accepted = is_set_ring_accepted(resp_text)
            if accepted:
                accepted_count += 1
                if accepted_count >= remaining_set_quota:
                    print("🔔 已达到本期设彩铃奖励上限，本轮提前结束")
                    break
        except Exception as exc:
            print(f"❌ 设彩铃失败，已跳过当前作品: {exc}")
        time.sleep(0.5)

    print(f"✅ 本轮设彩铃完成，已提交/成功 {accepted_count} 个作品")
    return active_token


def premake_prepare(session, crypto_inst, token, mobile, template_meta, invite_code=""):
    active_token = token
    if invite_code:
        open_activity_page(session, invite_code)
        if not getattr(session, "_invite_entry_done", False):
            active_token = mark_invite_entry(session, crypto_inst, active_token, mobile, invite_code)
            session._invite_entry_done = True
    template_id = template_meta.get("templateId") or TEMPLATE_ID
    template_conf_id = template_meta.get("templateConfId") or TEMPLATE_CONF_ID

    _, active_token = send_stat_message(
        session, crypto_inst, active_token, mobile,
        "page_vring_index", f"玩转AI赢手机_activityID_{ACTIVITY_ID}_entrance_{CHANNEL_ID}")

    res_pkg, active_token = post_encrypted_api(
        session,
        crypto_inst,
        active_token,
        "/hapi/en/api",
        OrderedDict([
            ("channelId", CHANNEL_ID),
            ("portal", "45"),
            ("mobile", mobile),
            ("templateId", template_id),
            ("aid", ACTIVITY_ID),
            ("apiName", "ismp/IsmpApi/queryAiMakePkgInfo")
        ]),
        is_share=False
    )

    stat_events = [
        ("activity_vring_make_1.9", f"_activityID_{ACTIVITY_ID}_templateID_{template_id}_entrance_{CHANNEL_ID}_templateconfID_{template_conf_id}"),
        ("activity_2511AI-makeonekey_1.6", f"activityID_{ACTIVITY_ID}_templateID_{template_id}_entrance_{CHANNEL_ID}_templateconfID_{template_conf_id}"),
    ]
    for actname, actparam in stat_events:
        _, active_token = send_stat_message(session, crypto_inst, active_token, mobile, actname, actparam)
        time.sleep(0.08)

    return active_token


def query_make_pkg_info(session, crypto_inst, token, mobile, template_meta=None):
    template_meta = template_meta or {}
    res, active_token = post_encrypted_api(
        session,
        crypto_inst,
        token,
        "/hapi/en/api",
        OrderedDict([
            ("channelId", CHANNEL_ID),
            ("portal", "45"),
            ("mobile", mobile),
            ("templateId", template_meta.get("templateId") or TEMPLATE_ID),
            ("aid", ACTIVITY_ID),
            ("apiName", "ismp/IsmpApi/queryAiMakePkgInfo")
        ]),
        is_share=False
    )
    dec_text = crypto_inst.decrypt(res.text)
    pkg_info = {}
    try:
        pkg_info = json.loads(dec_text).get("data", {}) or {}
    except Exception:
        pass

    package_left = safe_int(pkg_info.get("privilegeVrbtAIVideoLeftNum"), 0)
    free_left = safe_int(pkg_info.get("templateDailyNum"), 0)
    phase_make_left = estimate_phase_make_quota(pkg_info)
    print(
        f"🎬 制作次数: packageLeft={package_left}, "
        f"freeLeft={free_left}, phaseLeft={phase_make_left}, totalEstimate={estimate_make_attempts(pkg_info)}"
    )
    return active_token, pkg_info


def estimate_make_attempts(pkg_info):
    if not isinstance(pkg_info, dict):
        return 0
    package_left = safe_int(pkg_info.get("privilegeVrbtAIVideoLeftNum"), 0)
    free_left = safe_int(pkg_info.get("templateDailyNum"), 0)
    if package_left < 0 or free_left < 0:
        return max(1, 30)
    return min(max(package_left, 0) + max(free_left, 0), 30)


def estimate_phase_make_quota(pkg_info):
    if not isinstance(pkg_info, dict):
        return 3
    aid_left = safe_int(pkg_info.get("privilegeVrbtAIVideoLeftNum"), -1)
    if aid_left >= 0:
        return min(max(aid_left, 0), 3)
    return min(estimate_make_attempts(pkg_info), 3)


def plan_make_attempts(pkg_info, point_summary=None):
    available_attempts = estimate_make_attempts(pkg_info)
    phase_quota_left = estimate_phase_make_quota(pkg_info)
    produced_total = safe_int((point_summary or {}).get("production_total"), 0)
    record_quota_left = max(0, 3 - produced_total)
    if available_attempts <= 0 or phase_quota_left <= 0 or record_quota_left <= 0:
        return 0
    return min(available_attempts, phase_quota_left, record_quota_left)


def make_request(session, crypto_inst, token, mobile, invite_code, template_meta):
    rand_name = f"{template_meta['videoName']}{random.randint(100000, 999999)}"
    payload = OrderedDict([
        ("channelId", CHANNEL_ID), ("portal", "45"), ("mobile", mobile),
        ("makeId", ""), ("userPhotos", ""), ("background", template_meta.get("background", "")),
        ("userWords", template_meta["userWords"]),
        ("videoName", rand_name), ("templateId", template_meta.get("templateId") or TEMPLATE_ID),
        ("templateConfId", template_meta.get("templateConfId") or TEMPLATE_CONF_ID),
        ("templateName", rand_name), ("aid", ACTIVITY_ID), ("aiPack", 0),
        ("arrangeId", template_meta.get("arrangeId", "")), ("autoOrderUgc", 0),
        ("inviterMobile", ""),
        ("fromType", ""), ("sessionId", ""), ("voice", ""),
        ("videoOwnerCode", ""), ("videoResourceCode", ""), ("workId", ""),
        ("imageMakeType", ""), ("songId", ""), ("imageRate", ""), ("productionType", "")
    ])
    print(f"🧩 当前模板参数: templateId={template_meta.get('templateId') or TEMPLATE_ID}, templateConfId={template_meta.get('templateConfId') or TEMPLATE_CONF_ID}, isAI={template_meta.get('isAI', 0)}, arrangeId={template_meta.get('arrangeId', '')!s}, background={template_meta.get('background', '')!r}")
    enc_str = crypto_inst.encrypt(payload)
    api_url = f"https://ai.imusic.cn/hapi/diy_video/au/template_make_add_v2?formData={urllib.parse.quote(enc_str)}"

    h = get_headers(crypto_inst, token, is_share=False)
    return safe_ai_request(
        session,
        "post",
        api_url,
        reason="提交AI制作",
        headers=h,
        data=""
    )


def submit_make_task(session, crypto_inst, token, mobile, invite_code, ticket, template_meta):
    active_token = premake_prepare(session, crypto_inst, token, mobile, template_meta, invite_code)
    res = make_request(session, crypto_inst, active_token, mobile, invite_code, template_meta)
    active_token = check_and_update_token(res, active_token)
    resp_text = crypto_inst.decrypt(res.text)

    if extract_code(resp_text) == "10013":
        trace_id = ""
        try:
            trace_id = json.loads(resp_text).get("imuTraceId") or ""
        except Exception:
            pass

        if trace_id:
            h_rem = get_headers(crypto_inst, active_token, True)
            _, active_token = send_stat_message(
                session,
                crypto_inst,
                active_token,
                mobile,
                "page_vring_index",
                f"玩转AI赢手机_activityID_{ACTIVITY_ID}_entrance_{CHANNEL_ID}"
            )
            time.sleep(0.05)
            _, active_token = send_stat_message(
                session,
                crypto_inst,
                active_token,
                mobile,
                "activity_vring_make_1.9",
                f"_activityID_{ACTIVITY_ID}_entrance_{CHANNEL_ID}"
            )

            rem_en = crypto_inst.encrypt({"method": "remedy", "traceId": trace_id, "mobile": mobile})
            res_rem = safe_ai_request(
                session,
                "post",
                f"https://ai.imusic.cn/hapi/en/api?formData={urllib.parse.quote(rem_en)}",
                reason="AI制作-remedy",
                headers=h_rem,
                data=""
            )
            active_token = check_and_update_token(res_rem, active_token)

            res_refresh = sso_login_by_ticket(session, ticket)
            active_token = res_refresh.get("token") or active_token
            active_token = premake_prepare(session, crypto_inst, active_token, mobile, template_meta, invite_code)

            time.sleep(1)
            res_final = make_request(session, crypto_inst, active_token, mobile, invite_code, template_meta)
            active_token = check_and_update_token(res_final, active_token)
            resp_text = crypto_inst.decrypt(res_final.text)
            print(f"🎉 最终响应结果: {resp_text}")
        else:
            print(f"⚠️ 收到 10013 但缺少 imuTraceId: {resp_text}")
    else:
        print(f"📝 制作响应: {resp_text}")

    print_invite_response_log(invite_code, resp_text)
    return active_token, resp_text

def run_single_account(phone, password, allow_lottery=True, android_id=""):
    print(f"\n{'=' * 20} 开始处理账号 {phone} {'=' * 20}")
    total_attempts = 2
    for account_attempt in range(1, total_attempts + 1):
        session = create_browser_session()
        disable_session_proxy(session)
        global_crypto = ImCrypto()
        session._activity_sid = ""
        session._invite_code = ""
        session._invite_entry_done = False

        session.cookies.set('cc', CHANNEL_ID, domain='ai.imusic.cn')

        if account_attempt > 1:
            print(f"🔁 账号级重试 {account_attempt}/{total_attempts}")

        try:
            if XIEQU_PROXY_URL:
                if account_attempt == 1:
                    print("🌐 已启用携趣短效代理轮换，当前策略：单账号复用IP，失败时再切换")
                refresh_session_proxy(session, reason="账密登录前初始化", force=True)

            token, mobile, _, ticket = do_login(session, global_crypto, phone, password, android_id)
            invite_code = "9e2f5ca4b9d3edb3f256420c5d99804a7729b5b7eb2c111f7856d33bb552acce"
            session._invite_code = invite_code
            active_token = warmup_session(session, global_crypto, token, mobile)
            active_token, phase_info = get_phase_info(session, global_crypto, active_token)
            template_meta = query_template_meta(session, active_token)
            active_token, pkg_info = query_make_pkg_info(session, global_crypto, active_token, mobile, template_meta)
            point_summary = None
            phase_records = None
            success_count = 0
            day_index = safe_int(phase_info.get("day_index"), 1)

            print("🔍 制作前先查询点数明细/中奖记录")
            active_token, phase_records, point_summary, _ = query_phase_records(
                session, global_crypto, active_token, mobile, phase_info, query_awards=True
            )

            planned_attempts = plan_make_attempts(pkg_info, point_summary)
            print(
                f"📝 本次制作计划: day={day_index}, "
                f"packageLeft={safe_int(pkg_info.get('privilegeVrbtAIVideoLeftNum'), 0)}, "
                f"made={safe_int((point_summary or {}).get('production_total'), 0)}, "
                f"phaseMakeLeft={estimate_phase_make_quota(pkg_info)}, "
                f"planned={planned_attempts}"
            )

            if planned_attempts <= 0:
                if point_summary and safe_int(point_summary.get("production_total"), 0) >= 3:
                    print("⏭️ 本期“制作获得”已满 3 次，跳过 AI 制作")
                else:
                    print("📭 当前无可执行的 AI 制作次数，跳过制作")
            else:
                for attempt in range(1, min(planned_attempts, 30) + 1):
                    print(f"\n🎞️ 开始第 {attempt}/{planned_attempts} 次制作")
                    if XIEQU_PROXY_URL:
                        prepare_proxy_for_action(session, reason=f"制作#{attempt}")
                    try:
                        active_token, resp_text = submit_make_task(
                            session,
                            global_crypto,
                            active_token,
                            mobile,
                            invite_code,
                            ticket,
                            template_meta
                        )
                    except Exception as exc:
                        print(f"❌ 第 {attempt} 次制作异常，已跳过本次: {exc}")
                        continue

                    if not is_success_response(resp_text):
                        print(f"⛔ 第 {attempt} 次制作失败，停止继续制作")
                        break

                    success_count += 1
                    active_token, pkg_info = query_make_pkg_info(session, global_crypto, active_token, mobile, template_meta)
                    print(
                        f"🔁 已成功制作 {success_count} 次，"
                        f"本期剩余奖励制作次数 {estimate_phase_make_quota(pkg_info)}"
                    )
                    time.sleep(0.5)

            if phase_records is None or point_summary is None:
                active_token, phase_records, point_summary, _ = query_phase_records(
                    session, global_crypto, active_token, mobile, phase_info, query_awards=False
                )

            active_token = run_set_ring_flow(
                session,
                global_crypto,
                active_token,
                mobile,
                phase_info,
                phase_records=phase_records,
                point_summary=point_summary,
            )

            active_token, award_records = fetch_award_records(
                session, global_crypto, active_token, mobile
            )
            active_token = claim_pending_phone_fee_awards(
                session, global_crypto, active_token, mobile, reason="抽奖前补领", award_records=award_records
            )
            time.sleep(1)
            if allow_lottery:
                active_token = run_lottery(session, global_crypto, active_token, mobile)
                active_token, award_records = fetch_award_records(
                    session, global_crypto, active_token, mobile
                )
                active_token = claim_pending_phone_fee_awards(
                    session, global_crypto, active_token, mobile, reason="抽奖后补领", award_records=award_records
                )
            else:
                print("⏭️ 已关闭第一个账号抽奖开关，跳过当前账号抽奖")
                active_token, award_records = fetch_award_records(
                    session, global_crypto, active_token, mobile
                )

            active_token = query_coupon_ticket_status(
                session, global_crypto, active_token, mobile, phase_info=phase_info, reason="券码中奖情况"
            )

            print(f"✅ 账号 {phone} 处理完成")
            return
        except Exception as e:
            err_text = str(e)
            if account_attempt < total_attempts and is_retryable_request_exception(e):
                print(
                    f"⚠️ 账号 {phone} 本轮网络/代理异常，准备整体重试 "
                    f"{account_attempt}/{total_attempts - 1}: {err_text}"
                )
                time.sleep(1.2)
                continue
            print(f"❌ 账号 {phone} 处理失败，已跳过: {err_text}")
            return
        finally:
            try:
                session.close()
            except Exception:
                pass


def run():
    accounts = parse_accounts(TEST_ACCOUNTS)
    print(f"共解析到 {len(accounts)} 个账号")
    for idx, account in enumerate(accounts, start=1):
        phone, password = account[:2]
        android_id = account[2] if len(account) > 2 else ""
        print(f"\n#### [{idx}/{len(accounts)}] ####")
        print("账号凭证：" + ("手机号#密码#AndroidID（缓存失效可账密登录）" if android_id else "手机号#密码（仅缓存登录，缓存失效将跳过）"))
        allow_lottery = OTHER_ACCOUNTS_LOTTERY_ENABLED if idx != 1 else False
        run_single_account(phone, password, allow_lottery=allow_lottery, android_id=android_id)

if __name__ == "__main__":
    run()


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