# cron: 0 */6 * * *
# feimi.py - 飞米阅读 (青龙版)
# 账号密码/OpenID 一律走青龙环境变量, 不写进仓库:
#   FEIMI_USERNAME / FEIMI_PASSWORD / FEIMI_OPENIDS (一行一个, 也可用 & 或逗号分隔)
#   FEIMI_PLATFORM_URL (可选, 默认 http://951.bllnl.fun:18080)
# 自检: python3 feimi.py --check (只验链路, 不计金币)
# 飞米是 H5 站 (feimiyin.cn, 后端 hwz.tslu.cn), 不是小程序 wx.login, 自家 yyb-go 取码不适用:
#   登录是浏览器里拿 6 位码, 微信扫码填码验证, token 存 localStorage userToken
#   方式 A - token 直跑 (唯一已验证的路): 青龙环境变量 FEIMI_TOKEN 填飞米 token, 不用 951 平台, 不用登录
#   方式 C - 951 平台 (原版): 填 FEIMI_USERNAME / FEIMI_PASSWORD / FEIMI_OPENIDS, 平台代取 token
#   过检测: 没配 951 平台账号时自动跳过真机推送, 只走静态阅读
# 微信交流  https://qr61.cn/oHjkWn/qoABO89# 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本无关！均由使用者自行承担。

# -*- coding: utf-8 -*-

"""
使用说明
http://951.bllnl.fun:18080登录YYB
注册登录账号     
获取openid  脚本中改openid  一行一个
还有填写注册的      账号密码
还有填写注册的      账号密码
还有填写注册的      账号密码
脚本自动过检测
脚本自动过检测
脚本自动过检测
脚本自动过检测
脚本自动过检测
==================================================================================
"""

import io
import os
import sys
import json
import time
import random
import logging
import urllib.parse

import requests

                                                   
                                           
                                           
OPENID_LIST = os.environ.get("FEIMI_OPENIDS", "")

TARGET = 30                                                          
STAY_MIN = 6                                                         
STAY_MAX = 9                                                

REAL_FIRST_N = 3                                                                  

                                 
PLATFORM_URL = os.environ.get("FEIMI_PLATFORM_URL", "http://951.bllnl.fun:18080")
USERNAME = os.environ.get("FEIMI_USERNAME", "")
PASSWORD = os.environ.get("FEIMI_PASSWORD", "")
FEIMI_TOKEN = os.environ.get("FEIMI_TOKEN", "")

      
API = "https://hwz.tslu.cn"
TASK_API = "https://rdapi.hzjianyue.cn/api/articleTask0428"
                                                        

"""
YYB Token 平台 · 取 token 客户端（供各阅读脚本复用）
=====================================================
直接对接平台接口 /api/token/get（账号密码 + 自己的 openid 认证），
不再依赖 UniGate（20:5699）。请求/响应全程 AES 加密。

用法：
    from platform_token import get_token
    token, name, extra = get_token("可乐", PLATFORM, USERNAME, PASSWORD, OPENID)
"""
import json
import base64
import hashlib
import time
import urllib.request
import urllib.error

ENC_KEY = "yyb-token-v5-9f3a7c2e8b6d4f1a"                
YYB_ID = "yyb1"                                                  

                                    
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))
_CLIENT_UA = "yyb-token-client/1.0 (reading platform)"

                 
PROJECTS = {
    "飞米": "feimi", "壹点": "tnkj", "美添赚": "hmtz", "恰恰": "qqyd",
    "鱼儿": "yuer", "鱼儿阅读": "yuer", "可乐": "kele", "猫看": "maokan",
}


def _decrypt(payload):
    """解密平台 AES-CBC 响应"""
    from cryptography.hazmat.primitives import padding as sympad
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    key = hashlib.sha256(ENC_KEY.encode("utf-8")).digest()
    raw = base64.b64decode(payload)
    dec = Cipher(algorithms.AES(key), modes.CBC(raw[:16])).decryptor()
    out = dec.update(raw[16:]) + dec.finalize()
    unp = sympad.PKCS7(128).unpadder()
    return json.loads((unp.update(out) + unp.finalize()).decode("utf-8"))


def get_token(project, platform, username, password, openid, retries=3, timeout=60):
    """从平台取 token。
    返回 (token, token_name, extra)；失败自动重试 retries 次后抛异常。
    """
    key = PROJECTS.get(project, project)
    body = {
        "yyb_id": YYB_ID,
        "project": key,
        "username": username,
        "password": password,
        "openid": openid,
    }
    url = platform.rstrip("/") + "/api/token/get"
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "User-Agent": _CLIENT_UA})
            with _OPENER.open(req, timeout=timeout) as r:
                j = json.loads(r.read().decode("utf-8"))
            d = _decrypt(j["c"])
            if d.get("ok"):
                return d.get("token"), d.get("token_name", "token"), d.get("extra", {})
            last_err = d.get("error", "取 token 失败")
        except Exception as e:
            last_err = str(e)
        if attempt < retries:
            time.sleep(3)
    raise RuntimeError("平台取 token 失败: %s" % last_err)


def admin_get_token(admin_base, admin_token, project, openid="", retries=3, timeout=60):
    """管理端取 token：Bearer 鉴权码，可用任意 openid（留空由服务端从池自动轮转）。

    返回 (token, token_name, extra, openid)。失败自动重试 retries 次后抛异常。
    """
    key = PROJECTS.get(project, project)
    body = {"project": key}
    if openid:
        body["openid"] = openid
    url = admin_base.rstrip("/") + "/admin/api/token/get"
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "User-Agent": _CLIENT_UA,
                         "Authorization": "Bearer " + admin_token})
            with _OPENER.open(req, timeout=timeout) as r:
                j = json.loads(r.read().decode("utf-8"))
            d = _decrypt(j["c"])
            if d.get("ok"):
                return d.get("token"), d.get("token_name", "token"), \
                    d.get("extra", {}), d.get("openid", openid)
            last_err = d.get("error", "取 token 失败")
        except Exception as e:
            last_err = str(e)
        if attempt < retries:
            time.sleep(3)
    raise RuntimeError("管理端取 token 失败: %s" % last_err)


def admin_check_read(admin_base, admin_token, openid, article_url, retries=2, timeout=60):
    """管理端过检测：Bearer 鉴权码派单，可用任意 openid（池里全部，含未绑定平台的 YYB 账号）。

    openid 传空字符串时由服务端自动从池轮转挑选。
    返回 (ok, message, openid)。返回 False 表示平台拒绝了（如鉴权码限额/链接去重），
    网络异常会重试后抛异常。
    """
    body = {"article_url": article_url}
    if openid:
        body["openid"] = openid
    url = admin_base.rstrip("/") + "/admin/api/check/receive"
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "User-Agent": _CLIENT_UA,
                         "Authorization": "Bearer " + admin_token})
            with _OPENER.open(req, timeout=timeout) as r:
                j = json.loads(r.read().decode("utf-8"))
            d = _decrypt(j["c"])
            if d.get("ok"):
                return True, d.get("message", ""), d.get("openid", openid)
            return False, (d.get("error") or d.get("message") or "过检失败"), \
                d.get("openid", openid)
        except Exception as e:
            last_err = str(e)
        if attempt < retries:
            time.sleep(2)
    raise RuntimeError("管理端过检失败: %s" % last_err)


def check_read(platform, username, password, openid, article_url, retries=2, timeout=60):
    """平台过检测：用该账号自己的 openid 做真机阅读检测（不能代检）。

    返回 (ok, message, openid)。返回 False 表示平台拒绝了（如每日限额/归属校验），
    网络异常会重试后抛异常。
    """
    body = {
        "username": username,
        "password": password,
        "openid": openid,
        "article_url": article_url,
    }
    url = platform.rstrip("/") + "/api/check/receive"
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url, data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "User-Agent": _CLIENT_UA})
            with _OPENER.open(req, timeout=timeout) as r:
                j = json.loads(r.read().decode("utf-8"))
            d = _decrypt(j["c"])
            if d.get("ok"):
                return True, d.get("message", ""), d.get("openid", openid)
            return False, (d.get("error") or d.get("message") or "过检失败"), \
                d.get("openid", openid)
        except Exception as e:
            last_err = str(e)
        if attempt < retries:
            time.sleep(2)
    raise RuntimeError("平台过检失败: %s" % last_err)

TIMEOUT = 20
MAX_INSUFFICIENT = 3                                           
MAX_UNKNOWN = 3                                         
COOLDOWN_CODES = {402}                                       
RELOGIN_CODES = {201}                                      

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                      errors="replace", line_buffering=True)
    except Exception:
        pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("feimi_auto")

                             
UA_WX = ("Mozilla/5.0 (Linux; Android 13; 22081212C Build/TKQ1.220829.002; wv) "
         "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/150.0.7871.189 "
         "Mobile Safari/537.36 MicroMessenger/8.0.78.3180(0x28004E3B) WeChat/arm64 "
         "NetType/WIFI Language/zh_CN ABI/arm64")
BASE_HEADERS = {
    "User-Agent": UA_WX,
    "Accept": "application/json, text/plain, */*",
    "x-requested-with": "xmlhttprequest",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
}


def classify(code):
    """把计次接口 code 归成统一动作。"""
    if code == 0:
        return "success"
    if code == 1:
        return "insufficient"
    if code in COOLDOWN_CODES:
        return "cooldown"
    if code in RELOGIN_CODES:
        return "relogin"
    return "unknown"


def human_sleep(seconds, label=""):
    """分段拟人停留：拆 3~5 段短睡，末段补足差额，保证实际时长不低于计划；返回实际停留秒数。"""
    total = max(1, int(seconds))
    t0 = time.time()
    segs = random.randint(3, 5)
    chunk = total / segs
    for i in range(segs):
        seg = max(0.4, chunk + random.uniform(-0.8, 0.8))
        if i == segs - 1:
            seg = max(seg, total - (time.time() - t0))
        time.sleep(seg)
    if label:
        log.info("  [%s] 停留完成 %ds", label, total)
    return total


                                                                       
def full_login(openid):
    """取 token: 优先 FEIMI_TOKEN 直跑, 否则走 951 平台 (原版)。飞米 H5 登录不用 yyb-go 取码。"""
    if FEIMI_TOKEN:
        log.info("token 直跑: 使用 FEIMI_TOKEN, 跳过登录")
        return FEIMI_TOKEN, "FEIMI_TOKEN", "token直跑"
    token, name, extra = get_token(
        "飞米", PLATFORM_URL, USERNAME, PASSWORD, openid)
    log.info("平台取 token 成功: %s", name)
    info = {
        "id": extra.get("id"),
        "invite_id": extra.get("invite_id"),
        "gold": extra.get("gold"),
        "dayreads": extra.get("dayreads"),
    }
    return token, info, "平台"


                                                 
class Reader:
    def __init__(self, openid=""):
        self.openid = openid
        self.session = requests.Session()
        self.session.headers.update(BASE_HEADERS)
        self.token = ""
        self.label = ""
        self.ticket = {}                      
        self.referer = ""                                  
        self.cur_url = ""                    
        self.jkey = None
        self.c = 1
        self.confirmed = 0                 
        self.art_total = 0
        self.fail_total = 0
        self.real_ok = 0
        self.real_fail = 0
        self.before = None                             
        self.home = {}

                              
    def login(self):
        token, info, label = full_login(self.openid)
        self.token, self.label = token, label
        self.home = info

                              
    def home_info(self):
        r = self.session.get(f"{API}/abaaba/getHomeInfo/?token={self.token}",
                             timeout=TIMEOUT)
        d = r.json()
        if d.get("code") != 0:
            return None, d
        self.home = d["data"]
        return d["data"], d

                                 
    def fetch_ticket(self):
        r = self.session.get(
            f"{API}/abaaba/getReadUrl/?b={int(time.time()*1000)}&token={self.token}",
            timeout=TIMEOUT)
        d = r.json()
        if d.get("code") != 0:
            log.warning("getReadUrl code=%s msg=%s", d.get("code"), d.get("msg"))
            return False
        art_url = d["data"]["url"]
        q = urllib.parse.parse_qs(urllib.parse.urlparse(art_url).query)
        self.ticket = {k: v[0] for k, v in q.items()}
        self.referer = art_url
        log.info("本轮票据: %s", self.ticket)
        return True

                                
    def task(self, jkey, c, retry=3):
        params = dict(self.ticket)
        if jkey:
            params["jkey"] = jkey
        params["c"] = str(c)
        params["pageshow"] = ""
        params["r"] = str(random.random())
        url = TASK_API + "?" + urllib.parse.urlencode(params)
        for attempt in range(1, retry + 1):
            try:
                r = self.session.get(
                    url, headers={"Referer": self.referer}, timeout=TIMEOUT)
                return r.json()
            except Exception as e:
                log.error("计次接口网络异常(第%d次): %s", attempt, e)
                time.sleep(2 * attempt)
        return {"code": "NETFAIL", "msg": "network fail after retries"}

                                
    def push_real(self, url):
        """发平台过检测（用自己 openid 真机打开）；返回 (ok, openid, message)。失败由上层降级。"""
        if not USERNAME or not PASSWORD:
            return False, "-", "未配 951 平台账号, 跳过真机推送走静态"
        try:
            ok, msg, oid = check_read(
                PLATFORM_URL, USERNAME, PASSWORD, self.openid, url, retries=1)
            if ok:
                log.info("  [真机] 平台过检成功 | openid: %s | %s", oid, msg)
                return True, oid, msg
            log.warning("  [真机] 平台过检返回失败 | %s", msg)
            return False, oid, msg
        except Exception as e:
            log.warning("  [真机] 平台过检异常: %s", e)
            return False, "-", str(e)

                                       
    def absorb(self, d):
        data = d.get("data") or {}
        if data.get("url"):
            self.cur_url = data["url"]
        if data.get("jkey"):
            self.jkey = data["jkey"]
        return data

                                              
    def open_first(self):
        d = self.task(None, 1)
        if classify(d.get("code")) != "success":
            log.error("领篇失败: code=%s msg=%s", d.get("code"), d.get("msg"))
            return False
        data = self.absorb(d)
        self.c = 2
        log.info("领出文章 | readNum=%s/%s is_close=%s | %s",
                 data.get("readNum"), data.get("totalNum"),
                 data.get("is_close"), data.get("msg"))
        return True

                                 
    def run(self):
                      
        self.login()
        base, _ = self.home_info()
        if base is None:
            return "login_fail"
        self.before = (int(base["dayreads"]), int(base["gold"]))
        log.info("基线: dayreads=%s gold=%s 单价=%s/篇",
                 base["dayreads"], base["gold"], base["read_gold"])

                
        if not self.fetch_ticket():
            return "cooldown"

                              
        if not self.open_first():
            return "stop"

        insufficient = unknown = relogin_done = 0
        stop_reason = "done"

                                          
        while self.confirmed < TARGET:
                                          
            channel = "静态"
            if self.confirmed < REAL_FIRST_N:
                ok, _oid, _msg = self.push_real(self.cur_url)
                if ok:
                    self.real_ok += 1
                    channel = "真机"
                else:
                    self.real_fail += 1
                    channel = "静态(真机推送失败降级)"

            stay = random.uniform(STAY_MIN, STAY_MAX)
            human_sleep(stay, f"第{self.confirmed+1}篇[{channel}]")

            d = self.task(self.jkey, self.c)
            action = classify(d.get("code"))
            data = self.absorb(d)

            if action == "success":
                self.confirmed += 1
                self.c += 1
                self.art_total += 1
                unknown = 0
                log.info("✅ 第%d篇[%s]确认成功 | readNum=%s/%s is_close=%s | %s",
                         self.confirmed, channel, data.get("readNum"),
                         data.get("totalNum"), data.get("is_close"),
                         data.get("msg") or d.get("msg"))

                                                               
                is_close = str(data.get("is_close", "0")) == "1"
                log.info("进度: readNum=%s/%s", data.get("readNum"),
                         data.get("totalNum"))
                if is_close:
                    log.info("平台本轮文章已读完(is_close=1)，停止")
                    stop_reason = "round_done"
                    break

            elif action == "insufficient":
                insufficient += 1
                self.fail_total += 1
                log.warning("阅读时间不足，同篇重试(%d/%d) | 新 jkey 已轮换",
                            insufficient, MAX_INSUFFICIENT)
                if insufficient > MAX_INSUFFICIENT:
                    log.error("连续 %d 次停留不足，停止", MAX_INSUFFICIENT)
                    stop_reason = "stop"
                    break
                time.sleep(8)

            elif action == "relogin":
                if relogin_done:
                    log.error("重登后仍返回未登录，停止")
                    stop_reason = "stop"
                    break
                log.warning("token 失效，重新登录一次…")
                try:
                    self.login()
                    relogin_done = 1
                    self.jkey = None
                    self.c = 1
                    insufficient = unknown = 0
                    if not self.fetch_ticket():
                        stop_reason = "cooldown"
                        break
                    if not self.open_first():
                        stop_reason = "stop"
                        break
                    continue
                except Exception as e:
                    log.error("重登失败: %s", e)
                    stop_reason = "stop"
                    break

            elif action == "cooldown":
                log.warning("平台冷却/公告/没文章: code=%s msg=%s",
                            d.get("code"), d.get("msg"))
                stop_reason = "cooldown"
                break

            else:
                unknown += 1
                log.warning("未知码 code=%s msg=%s，3s 后退避(%d/%d)",
                            d.get("code"), d.get("msg"), unknown, MAX_UNKNOWN)
                if unknown > MAX_UNKNOWN:
                    log.error("未知码连续 %d 次，停止", MAX_UNKNOWN)
                    stop_reason = "stop"
                    break
                time.sleep(3)

                 
        end, _ = self.home_info()
        if end:
            dn0, g0 = self.before
            dn1, g1 = int(end["dayreads"]), int(end["gold"])
            log.info("================ 汇总 ================")
            log.info("平台侧结算: dayreads %s → %s (+%s) | gold %s → %s (+%s)",
                     dn0, dn1, dn1 - dn0, g0, g1, g1 - g0)
        else:
            log.info("================ 汇总 ================")
        log.info("脚本计数: 成功 %d 篇 | 失败 %d 篇 | 真机推送成功 %d 失败 %d",
                 self.art_total, self.fail_total, self.real_ok, self.real_fail)
        log.info("停止原因: %s", stop_reason)
        return stop_reason


def smoke_check(r):
    """--check 自检：登录 → 基线档案 → 取票据 → 领第一篇。
    不进阅读循环、不等待、不计金币，用来上线前验证链路通不通。"""
    r.login()
    base, d = r.home_info()
    if base is None:
        log.error("档案校验失败: %s", json.dumps(d, ensure_ascii=False)[:200])
        return False
    log.info("基线: dayreads=%s gold=%s 单价=%s/篇",
             base["dayreads"], base["gold"], base["read_gold"])
    if not r.fetch_ticket():
        log.error("取票据失败")
        return False
    if not r.open_first():
        log.error("领第一篇失败")
        return False
    log.info("✅ 自检通过：登录、票据、领链链路正常（未进入阅读循环，未结算）")
    return True


def parse_openid_list(raw_str):
    import re as _re
    parts = _re.split(r"[\n,&;]+", raw_str or "")
    return [p.strip() for p in parts if p.strip() and not p.strip().startswith("#")]


def main():
    openid_list = parse_openid_list(OPENID_LIST)
    if FEIMI_TOKEN and not openid_list:
        openid_list = ["token-direct"]
    if not openid_list:
        log.error("未配置 OPENID_LIST"); sys.exit(1)
    if "--check" in sys.argv:
        log.info("===== 自检模式：只验链路，不计金币 =====")
        try:
            if not smoke_check(Reader(openid_list[0])):
                sys.exit(1)
        except Exception as e:
            log.error("自检异常: %s", e)
            sys.exit(1)
        return

    log.info("===== %d 个 openid | 目标 %d 篇 | 间隔 %d~%ds | 前 %d 篇真机推送 =====",
             len(openid_list), TARGET, STAY_MIN, STAY_MAX, REAL_FIRST_N)
    for idx, oid in enumerate(openid_list, 1):
        log.info("----- [%d/%d] %s -----", idx, len(openid_list), oid)
        try:
            Reader(oid).run()
        except Exception as e:
            log.error("运行异常: %s", e)
        if idx < len(openid_list):
            log.info("· 等待 10 秒再切换下一个账号 ...")
            time.sleep(10)


if __name__ == "__main__":
    main()

# === 灰太狼项目群:1125984055 ===
