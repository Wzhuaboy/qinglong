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

#注册链接：https://x-yq.orbexa.cc/r/I67D7322BC3
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Orbexa 自动化任务脚本 - 青龙面板版
作者：Rain
功能：自动登录、观看广告、领取金币、自动提现
注册链接：https://x-yq.orbexa.cc/r/I67D7322BC3
环境变量：
  ORBEXA_ACCOUNTS = 邮箱#密码&邮箱#密码
  ORBEXA_DEBUG = true/false
  ORBEXA_WITHDRAW_ENABLE = true/false，是否开启自动提现，默认 true
  ORBEXA_WITHDRAW_AMOUNT = 提现金额，默认 0.3（需先实名认证并绑定支付宝）
"""

import hashlib
import json
import os
import random
import re
import time
import uuid
from typing import Dict, Optional, Tuple

import requests

# ==================== 配置区 ====================

ENV_ACCOUNTS = "ORBEXA_ACCOUNTS"
ENV_DEBUG = "ORBEXA_DEBUG"
ENV_WITHDRAW_ENABLE = "ORBEXA_WITHDRAW_ENABLE"
ENV_WITHDRAW_AMOUNT = "ORBEXA_WITHDRAW_AMOUNT"

BASE_URL = "https://x-api.orbexa.cc"
USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 15; 25053RT47C Build/AQ3A.250107.001)"

# ==================== 日志系统 ====================

class Logger:
    @staticmethod
    def info(msg: str):
        print(f"[{time.strftime('%H:%M:%S')}] ℹ️ {msg}")
    
    @staticmethod
    def success(msg: str):
        print(f"[{time.strftime('%H:%M:%S')}] ✅ {msg}")
    
    @staticmethod
    def error(msg: str):
        print(f"[{time.strftime('%H:%M:%S')}] ❌ {msg}")
    
    @staticmethod
    def warning(msg: str):
        print(f"[{time.strftime('%H:%M:%S')}] ⚠️ {msg}")
    
    @staticmethod
    def debug(msg: str):
        if os.getenv(ENV_DEBUG, "false").lower() == "true":
            print(f"[{time.strftime('%H:%M:%S')}] 🔍 {msg}")
    
    @staticmethod
    def log(msg: str):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")


# ==================== 核心类 ====================

class OrbexaApi:
    def __init__(self, email: str, password: str, device_id: Optional[str] = None):
        self.email = email
        self.password = password
        self.device_id = device_id or self._generate_device_id()
        self.token = None
        self.logged_in_once = False
        self.session = requests.Session()
    
    @staticmethod
    def _generate_device_id() -> str:
        random_bytes = random.getrandbits(256).to_bytes(32, 'big')
        return random_bytes.hex()
    
    @staticmethod
    def _solve_math(question: str) -> int:
        pattern = re.compile(r'(-?\d+)\s*([+\-*/×÷xX])\s*(-?\d+)\s*=\s*\?')
        match = pattern.search(question)
        
        if not match:
            raise ValueError(f"无法解析数学题: {question}")
        
        num1 = int(match.group(1))
        operator = match.group(2)
        num2 = int(match.group(3))
        
        operators = {
            '+': lambda a, b: a + b,
            '-': lambda a, b: a - b,
            '*': lambda a, b: a * b,
            '×': lambda a, b: a * b,
            'x': lambda a, b: a * b,
            'X': lambda a, b: a * b,
            '/': lambda a, b: a // b if a % b == 0 else a / b,
            '÷': lambda a, b: a // b if a % b == 0 else a / b,
        }
        
        if operator not in operators:
            raise ValueError(f"未知运算符: {operator}")
        
        return int(operators[operator](num1, num2))
    
    def _raw_api(self, path: str, body: Optional[Dict] = None, authed: bool = False, method: str = "POST", extra_headers: Optional[Dict] = None) -> Tuple[int, Dict]:
        url = BASE_URL + path
        
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "X-Device-Id": self.device_id,
            "User-Agent": USER_AGENT,
        }
        
        if authed and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        if extra_headers:
            headers.update(extra_headers)
        
        Logger.debug(f"请求: {method} {path}")
        if body:
            Logger.debug(f"Body: {json.dumps(body, ensure_ascii=False)}")
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, headers=headers, timeout=30)
            else:
                response = self.session.post(url, json=body or {}, headers=headers, timeout=30)
            
            status_code = response.status_code
            
            try:
                response_data = response.json()
            except:
                response_data = {"raw": response.text[:200]} if response.text else {}
            
            return status_code, response_data
            
        except Exception as e:
            Logger.error(f"请求异常: {e}")
            return 500, {"error": str(e)}
    
    def _request(self, path: str, body: Optional[Dict] = None, authed: bool = True, 
                 retries: int = 4, method: str = "POST", extra_headers: Optional[Dict] = None) -> Tuple[int, Dict]:
        attempt = 0
        
        while attempt < retries:
            status_code, data = self._raw_api(path, body, authed, method, extra_headers)
            
            if status_code == 401 and authed and not self.logged_in_once:
                Logger.warning("token 已失效，尝试自动重新登录…")
                if self._login():
                    attempt = 0
                    continue
            
            if status_code >= 400:
                if status_code in [400, 403, 404, 409]:
                    return status_code, data
                
                attempt += 1
                if attempt < retries:
                    wait_time = (1 << attempt)
                    Logger.warning(f"请求异常 HTTP {status_code}，{wait_time} 秒后重试: {path}")
                    time.sleep(wait_time)
                    continue
            
            return status_code, data
        
        raise Exception(f"请求失败: {path}")
    
    def _login(self) -> bool:
        try:
            Logger.log(f"🔐 正在登录: {self.email}")
            
            status, data = self._raw_api(
                "/auth/security/challenge",
                {"scene": "login-password"},
                authed=False
            )
            
            if status != 200:
                raise Exception(f"安全挑战失败: HTTP {status}")
            
            question = data.get("question", "")
            ticket = data.get("ticket", "")
            
            if not question or not ticket:
                raise Exception("安全挑战返回数据不完整")
            
            answer = self._solve_math(question)
            Logger.log(f"🧮 验证码: {question} = {answer}")
            
            login_body = {
                "email": self.email,
                "password": self.password,
                "securityTicket": ticket,
                "securityAnswer": str(answer)
            }
            
            status, data = self._raw_api(
                "/auth/login/password",
                login_body,
                authed=False
            )
            
            if 200 <= status < 300:
                self.token = data.get("accessToken")
                if not self.token:
                    raise Exception("登录成功但未返回 token")
                
                self.logged_in_once = True
                Logger.success("登录成功（token 2 小时有效）")
                return True
            else:
                error_msg = data.get("message", data.get("raw", "未知错误"))
                raise Exception(f"登录失败: HTTP {status} {error_msg}")
                
        except Exception as e:
            Logger.error(f"登录失败: {e}")
            return False
    
    def get_balance(self) -> str:
        try:
            status, data = self._request("/me", authed=True, method="GET")
            
            if status != 200:
                raise Exception(f"获取余额失败: HTTP {status}")
            
            user = data.get("user", {})
            coins = user.get("coins", "?")
            balance = user.get("balance", "?")
            
            return f"金币: {coins}   现金: {balance}"
            
        except Exception as e:
            Logger.error(f"获取余额失败: {e}")
            return "获取余额失败"
    
    def _claim_coin(self, task: Dict) -> Dict:
        try:
            if not task.get("canClaim", False):
                Logger.warning(f"任务不可领取（status={task.get('status')}），跳过")
                return {}
            
            status, data = self._request(
                "/coin/claims",
                {"type": "DAILY_CLAIM"},
                authed=True
            )
            
            if status in [200, 201]:
                amount = data.get("amount", "?")
                business_no = data.get("businessNo", "")
                Logger.success(f"🎉 领取成功: {amount} 金币（单号 {business_no}）")
            else:
                message = data.get("message", str(data))
                Logger.warning(f"⚠️ 领取返回 {status}: {message}（可能已领过）")
            
            return data.get("incrementalTask", {})
            
        except Exception as e:
            Logger.error(f"领取金币失败: {e}")
            return {}
    
    def _report_reward(self, task_id: str) -> bool:
        try:
            status, data = self._request(
                f"/ad-tasks/{task_id}/reward",
                {},
                authed=True
            )
            
            if status in [200, 201]:
                amount = data.get("amount", "?")
                Logger.success(f"🎉 奖励领取成功: {amount} 金币")
                return True
            else:
                message = data.get("message", str(data))
                Logger.warning(f"⚠️ 奖励领取返回 {status}: {message}（可能已领过）")
                return False
                
        except Exception as e:
            Logger.error(f"领取奖励失败: {e}")
            return False
    
    def _watch_item(self, task_id: str, item_id: str) -> Dict:
        try:
            Logger.log(f"  🎬 开始观看广告 item={item_id[:8]}…")
            
            status, data = self._request(
                f"/ad-tasks/{task_id}/items/{item_id}/start",
                {},
                authed=True
            )
            
            if status not in [200, 201]:
                raise Exception(f"开始观看失败: HTTP {status}")
            
            for attempt in range(41):
                time.sleep(1)
                
                status, data = self._request(
                    f"/ad-tasks/{task_id}/items/{item_id}/heartbeat",
                    {},
                    authed=True
                )
                
                if status not in [200, 201]:
                    Logger.warning(f"  ⚠️ 心跳失败: HTTP {status}")
                    continue
                
                task = data.get("task", {})
                item = task.get("item", {}) if task else None
                item_status = item.get("status") if item else None
                
                if item_status == "COMPLETED":
                    viewed_seconds = item.get("viewedSeconds", "?")
                    Logger.success(f"  ✅ 广告完成（心跳 x{attempt+1}，观看 {viewed_seconds}s）")
                    return data
                
                if (attempt + 1) % 10 == 0:
                    viewed = item.get("viewedSeconds") if item else None
                    remaining = item.get("remainingSeconds") if item else None
                    Logger.log(f"  ❤️ 观看中… 已看 {viewed}s / 剩余 {remaining}s")
            
            raise Exception("广告观看超时")
            
        except Exception as e:
            Logger.error(f"观看广告失败: {e}")
            return {}
    
    def _watch_round(self, task_id: str, label: str, known_item_id: Optional[str] = None) -> Dict:
        try:
            Logger.log(f"🚀 {label} 开始，task={task_id[:8]}…")
            
            for attempt in range(7):
                if known_item_id and attempt == 0:
                    item_id = known_item_id
                else:
                    status, data = self._request(
                        f"/ad-tasks/{task_id}/next",
                        authed=True,
                        method="GET"
                    )
                    
                    if status not in [200, 201]:
                        Logger.warning(f"  ⚠️ 获取下一条广告失败: HTTP {status}")
                        break
                    
                    task = data.get("task", {})
                    item = task.get("item", {}) if task else None
                    
                    if not item:
                        if task and task.get("status") == "COMPLETED":
                            completed_count = task.get("completedCount", 0)
                            can_reward = task.get("canReward", False)
                            Logger.success(f"  🏆 {label} 完成（{completed_count}/6, canReward={can_reward}）")
                            return data
                        
                        Logger.warning(f"  ⚠️ 没有更多广告")
                        break
                    
                    item_id = item.get("id")
                    slot_number = item.get("slotNumber")
                    Logger.log(f"  📌 [第{attempt+1}条] /next -> item={item_id[:8]} (slot {slot_number})")
                
                result = self._watch_item(task_id, item_id)
                
                task = result.get("task", {})
                if task and task.get("status") == "COMPLETED":
                    completed_count = task.get("completedCount", 0)
                    can_reward = task.get("canReward", False)
                    Logger.success(f"  🏆 {label} 完成（{completed_count}/6, canReward={can_reward}）")
                    return result
                
                known_item_id = None
            
            return {}
            
        except Exception as e:
            Logger.error(f"{label} 失败: {e}")
            return {}
    
    def claim_daily(self) -> Dict:
        try:
            Logger.log("📅 [轮次1] 每日任务 DAILY_GATE")
            
            status, data = self._request(
                "/ad-tasks/daily-gate",
                {},
                authed=True,
                method="POST"
            )
            
            if status in [200, 201]:
                Logger.success(f"✅ 每日任务获取成功 (HTTP {status})")
                task = data.get("task")
                
                if not task:
                    Logger.warning("⚠️ 响应中没有 task 字段")
                    return {}
                
                task_id = task.get("id")
                task_status = task.get("status")
                completed = task.get("completedCount", 0)
                Logger.log(f"📅 每日任务 task={task_id[:8]}… 状态={task_status} 进度={completed}/6")
                
                if task_status == "COMPLETED" and task.get("canClaim", False):
                    Logger.log("💰 任务已完成且可领取，直接领")
                    return self._claim_coin(task)
                
                if task_status in ["ACTIVE", "IN_PROGRESS"]:
                    item = task.get("item")
                    known_item_id = None
                    if item and item.get("status") == "VIEWING":
                        known_item_id = item.get("id")
                        remaining = item.get("remainingSeconds", "?")
                        Logger.info(f"📌 发现正在观看的广告: {known_item_id[:8]}… 剩余 {remaining}s")
                    
                    result = self._watch_round(task_id, "每日任务", known_item_id)
                    
                    status, data = self._request(
                        "/ad-tasks/daily-gate",
                        {},
                        authed=True,
                        method="POST"
                    )
                    if status in [200, 201]:
                        task = data.get("task")
                        if task:
                            return self._claim_coin(task)
                    return {}
                
                Logger.warning(f"⏭️ 未知任务状态: {task_status}")
                return {}
            else:
                Logger.warning(f"⏭️ 每日任务失败: HTTP {status}")
                return {}
            
        except Exception as e:
            Logger.error(f"每日任务失败: {e}")
            return {}
    
    def claim_incremental(self, inc_task: Optional[Dict] = None) -> bool:
        try:
            Logger.log("⚡ [轮次2] 增量任务 INCREMENTAL")
            
            if not inc_task:
                status, data = self._request(
                    "/ad-tasks/incremental",
                    authed=True,
                    method="GET"
                )
                
                if status not in [200, 201]:
                    Logger.warning("⏭️ 没有增量任务（可能今天已领完），跳过轮次2")
                    return False
                
                task = data.get("task")
                if not task:
                    Logger.warning("⏭️ 没有增量任务")
                    return False
                
                inc_task = task
            
            task_id = inc_task.get("id")
            status = inc_task.get("status")
            completed_count = inc_task.get("completedCount", 0)
            
            Logger.log(f"⚡ 增量任务 task={task_id[:8]}… 状态={status} 进度={completed_count}/6")
            
            if status == "COMPLETED" and inc_task.get("canReward", False):
                Logger.log("💰 任务已看完，直接领")
                return self._report_reward(task_id)
            
            item = inc_task.get("item", {})
            known_item_id = item.get("id") if item else None
            
            result = self._watch_round(task_id, "增量任务", known_item_id)
            
            return self._report_reward(task_id)
            
        except Exception as e:
            Logger.error(f"增量任务失败: {e}")
            return False
    
    def auto_withdraw(self, amount: float = 0.3) -> bool:
        """自动提现：查询档位 → 获取提现验证码 → 提交提现申请"""
        try:
            Logger.log(f"💰 开始自动提现，金额: {amount} 元")
            
            # 1. 获取提现配置，匹配对应金额档位
            status, data = self._request("/withdrawal/config", authed=True, method="GET")
            if status != 200:
                Logger.warning(f"⚠️ 获取提现配置失败: HTTP {status}")
                return False
            
            tiers = data.get("tiers", [])
            tier_id = None
            for tier in tiers:
                if float(tier.get("amount", 0)) == float(amount):
                    tier_id = tier.get("id")
                    break
            
            if not tier_id:
                Logger.warning(f"⚠️ 未找到金额 {amount} 对应的提现档位")
                return False
            
            # 2. 获取提现专用验证码
            status, data = self._raw_api(
                "/auth/security/challenge",
                {"scene": "withdrawal-submit"},
                authed=False
            )
            if status != 200:
                Logger.warning(f"⚠️ 获取提现验证码失败: HTTP {status}")
                return False
            
            question = data.get("question", "")
            ticket = data.get("ticket", "")
            if not question or not ticket:
                Logger.warning("⚠️ 提现验证码返回数据不完整")
                return False
            
            try:
                answer = str(self._solve_math(question))
            except Exception as e:
                Logger.error(f"提现验证码解析失败: {e}")
                return False
            Logger.log(f"🧮 提现验证码: {question} = {answer}")
            
            # 3. 提交提现申请（带幂等键防重复提交）
            withdraw_data = {
                "tierId": tier_id,
                "amount": f"{amount:.2f}",
                "accountType": "BALANCE",
                "provider": "ALIPAY",
                "securityTicket": ticket,
                "securityAnswer": answer
            }
            extra_headers = {"Idempotency-Key": str(uuid.uuid4())}
            
            status, data = self._request(
                "/withdrawals",
                withdraw_data,
                authed=True,
                extra_headers=extra_headers
            )
            
            if status in [200, 201]:
                order_no = data.get("requestNo", data.get("businessNo", "未知单号"))
                withdraw_status = data.get("status", "未知状态")
                Logger.success(f"🎉 提现申请提交成功 | 单号: {order_no} | 状态: {withdraw_status}")
                return True
            
            err_msg = data.get("message", data.get("msg", str(data)))
            if "今日已达上限" in str(err_msg) or "已提现" in str(err_msg):
                Logger.warning("ℹ️ 今日已提现过或达上限")
            elif "余额不足" in str(err_msg):
                Logger.warning("ℹ️ 余额不足")
            else:
                Logger.error(f"提现失败: HTTP {status} {err_msg}")
            return False
            
        except Exception as e:
            Logger.error(f"自动提现异常: {e}")
            return False
    
    def run(self, withdraw_enable: bool = True, withdraw_amount: float = 0.3) -> bool:
        try:
            if not self._login():
                return False
            
            balance = self.get_balance()
            Logger.log(f"💰 {balance}")
            
            inc_task = self.claim_daily()
            
            self.claim_incremental(inc_task)
            
            balance = self.get_balance()
            Logger.log(f"💰 {balance}")
            
            # 自动提现
            if withdraw_enable:
                time.sleep(2)
                self.auto_withdraw(withdraw_amount)
            
            return True
            
        except Exception as e:
            Logger.error(f"运行失败: {e}")
            return False


# ==================== 配置解析 ====================

def parse_accounts(accounts_str: str) -> list:
    accounts = []
    
    if not accounts_str:
        return accounts
    
    for account_str in accounts_str.split('&'):
        account_str = account_str.strip()
        if not account_str:
            continue
        
        parts = account_str.split('#')
        if len(parts) != 2:
            Logger.warning(f"账号格式错误，跳过: {account_str}")
            continue
        
        email = parts[0].strip()
        password = parts[1].strip()
        
        if email and password:
            accounts.append({"email": email, "password": password})
        else:
            Logger.warning(f"账号信息不完整，跳过: {account_str}")
    
    return accounts


def send_notification(title: str, content: str):
    try:
        if 'send' in dir():
            send(title, content)
        else:
            print(f"\n📢 {title}\n{content}\n")
    except:
        print(f"\n📢 {title}\n{content}\n")


def main():
    print("=" * 60)
    print("🚀 Orbexa 自动化任务脚本")
    print("📝 作者：柏油马路")
    print("=" * 60)
    
    withdraw_enable = os.getenv(ENV_WITHDRAW_ENABLE, "true").strip().lower() == "true"
    try:
        withdraw_amount = float(os.getenv(ENV_WITHDRAW_AMOUNT, "0.3").strip())
    except ValueError:
        withdraw_amount = 0.3
    
    accounts_str = os.getenv(ENV_ACCOUNTS, "")
    
    if not accounts_str:
        print("❌ 未配置账号，请设置环境变量: ORBEXA_ACCOUNTS")
        print("   格式: 邮箱#密码&邮箱#密码")
        print("   示例: 2176035636@qq.com#yourpassword")
        return
    
    accounts = parse_accounts(accounts_str)
    
    if not accounts:
        print("❌ 没有有效的账号配置")
        return
    
    print(f"📧 共 {len(accounts)} 个账号")
    if withdraw_enable:
        print(f"💰 自动提现已开启，每账号提现 {withdraw_amount} 元")
    else:
        print("💰 自动提现已关闭（设置 ORBEXA_WITHDRAW_ENABLE=true 可开启）")
    print("=" * 60)
    
    success_count = 0
    results = []
    
    for i, account in enumerate(accounts, 1):
        print(f"\n{'='*60}")
        print(f"📧 账号 {i}/{len(accounts)}: {account['email']}")
        print(f"{'='*60}")
        
        account_device_id = hashlib.sha256(
            f"orbexa_{account['email']}_2024".encode()
        ).hexdigest()
        print(f"📱 设备 ID: {account_device_id[:16]}...")
        
        api = OrbexaApi(
            email=account['email'],
            password=account['password'],
            device_id=account_device_id
        )
        
        try:
            if api.run(withdraw_enable=withdraw_enable, withdraw_amount=withdraw_amount):
                success_count += 1
                results.append(f"✅ {account['email']} 成功")
            else:
                results.append(f"❌ {account['email']} 失败")
        except Exception as e:
            results.append(f"❌ {account['email']} 异常: {e}")
            print(f"\n❌ 账号 {account['email']} 异常: {e}")
        
        if i < len(accounts):
            print("\n⏳ 等待 10 秒后处理下一个账号...")
            time.sleep(10)
    
    print(f"\n{'='*60}")
    print(f"📊 任务完成: {success_count}/{len(accounts)} 个账号成功")
    print("=" * 60)
    
    summary = f"成功: {success_count}/{len(accounts)} 个账号\n\n"
    summary += "\n".join(results)
    send_notification("任务完成", summary)


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