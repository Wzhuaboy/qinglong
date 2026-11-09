#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
new Env('顺丰快递积分任务');
cron: 1 1 1 1 1
"""
"""
顺丰快递积分任务自动化脚本

功能：
1. 从token.json配置文件读取账号信息
2. 支持多账号管理
3. 自动执行签到和积分任务
4. 推送执行结果通知

Author: ZaiZaiCat
Date: 2025-01-20
"""

import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from notification import send_notification, NotificationSound

# 导入API模块（当前目录）
from api import SFExpressAPI, ShareLoginInfo

# 延迟时间常量配置 (秒)
DELAY_BETWEEN_ACCOUNTS = (3, 8)      # 账号间切换延迟
DELAY_AFTER_SIGN = (2, 5)           # 签到后延迟
DELAY_BETWEEN_TASKS = (10, 15)      # 任务间延迟

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 青龙通知用日志尾部缓冲（logging 输出走 stderr，stdout 的 Tee 抓不到，改用 handler 接）
import io
_ql_log_buf = io.StringIO()


def _ql_log_tail(lines=30):
    return "\n".join(_ql_log_buf.getvalue().splitlines()[-lines:])

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
        logger.info("📨 青龙通知已发（面板通知设置）")
        return True
    logger.info("⚠️ [通知] 面板接口发送失败：%s，尝试 notify.py" % reason)
    sender = _ql_load_notify_py()
    if sender is None:
        logger.info("⚠️ [通知] 未找到 notify.py，通知未发出")
        return False
    try:
        sender.send(title, content)
        logger.info("📨 通知已通过 notify.py 发送（仅环境变量配置的渠道有效，未配则静默不发）")
        return True
    except Exception as exc:
        logger.info("⚠️ [通知] notify.py 发送失败：%s" % exc)
        return False




@dataclass(frozen=True)
class SFAccountConfig:
    """顺丰账号配置"""

    account_name: str
    sign: str
    user_agent: str
    channel: str
    device_id: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SFAccountConfig":
        """从配置字典构建账号配置"""
        account_name = data.get("account_name") or "未命名账号"
        sign = data.get("sign") or ""
        user_agent = data.get("user_agent") or ""
        channel = data.get("channel") or ""
        device_id = data.get("device_id") or ""

        missing_fields = []
        if not sign:
            missing_fields.append("sign")
        if not channel:
            missing_fields.append("channel")
        if not device_id:
            missing_fields.append("device_id")

        if missing_fields:
            missing_text = "、".join(missing_fields)
            raise ValueError(f"账号【{account_name}】缺少必填字段: {missing_text}")

        return cls(
            account_name=account_name,
            sign=sign,
            user_agent=user_agent,
            channel=channel,
            device_id=device_id
        )


class SFTasksManager:
    """顺丰积分任务管理器"""

    def __init__(self, config_path: str = None):
        """
        初始化任务管理器

        Args:
            config_path: 配置文件路径，默认为项目根目录下的config/token.json
        """
        if config_path is None:
            config_path = project_root / "config" / "token.json"
        else:
            config_path = Path(config_path)

        self.config_path = config_path
        self.site_name = "顺丰速运"
        self.accounts: List[SFAccountConfig] = []
        self.task_summary = []
        self.load_config()

    def load_config(self) -> None:
        """加载配置文件"""
        try:
            logger.info(f"正在读取配置文件: {self.config_path}")
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)

            # 获取顺丰的配置
            sf_config = config.get("sf", {})
            raw_accounts = sf_config.get("accounts", [])

            self.accounts = []
            for raw_account in raw_accounts:
                try:
                    self.accounts.append(SFAccountConfig.from_dict(raw_account))
                except ValueError as e:
                    logger.error(f"账号配置异常: {e}")

            if not self.accounts:
                logger.warning("配置文件中没有找到顺丰账号信息")
            else:
                logger.info(f"成功加载 {len(self.accounts)} 个账号配置")

        except FileNotFoundError:
            logger.error(f"配置文件不存在: {self.config_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"配置文件JSON格式错误: {e}")
            raise
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            raise

    def get_task_list(self, sf_api: SFExpressAPI) -> List[Dict[str, Any]]:
        """
        获取顺丰积分任务列表

        Args:
            sf_api: SF API实例

        Returns:
            List[Dict[str, Any]]: 任务列表
        """
        try:
            result = sf_api.query_point_task_and_sign()
            task_list = result.get("obj", {}).get("taskTitleLevels", [])
            logger.info(f"获取到 {len(task_list)} 个任务")
            return task_list
        except Exception as e:
            logger.error(f"获取任务列表失败: {e}")
            return []

    @staticmethod
    def extract_task_code(task: Dict[str, Any]) -> str:
        """从任务信息中提取task_code"""
        task_code = task.get("taskCode")
        if task_code:
            return task_code

        button_redirect = task.get("buttonRedirect", "")
        if not button_redirect:
            return ""

        decoded_redirect = unquote(button_redirect)
        ug_param = ""

        if "_ug_view_param=" in decoded_redirect:
            ug_param = decoded_redirect.split("_ug_view_param=", 1)[1]
        else:
            for candidate in (button_redirect, decoded_redirect):
                try:
                    query = urlparse(candidate).query
                    if not query:
                        continue
                    params = parse_qs(query)
                    if params.get("_ug_view_param"):
                        ug_param = params["_ug_view_param"][0]
                        break
                except Exception:
                    continue

        if not ug_param:
            return ""

        ug_param = unquote(ug_param).strip()

        try:
            ug_data = json.loads(ug_param)
            if isinstance(ug_data, dict):
                return ug_data.get("taskId", "")
        except json.JSONDecodeError:
            match = re.search(r'"taskId"\s*:\s*"([^"]+)"', ug_param)
            if match:
                return match.group(1)

        return ""

    def fetch_login_info(self, account: SFAccountConfig) -> Optional[ShareLoginInfo]:
        """
        获取账号登录信息（user_id + cookies）

        Args:
            account: 账号配置

        Returns:
            ShareLoginInfo | None: 登录信息
        """
        logger.info(f"[{account.account_name}] 开始请求分享登录接口")
        login_info = SFExpressAPI.share_login(
            sign=account.sign,
            user_agent=account.user_agent or None
        )

        if not login_info.success:
            logger.warning(f"[{account.account_name}] 分享登录失败: {login_info.error}")
            return None

        if not login_info.user_id or not login_info.cookies:
            logger.warning(f"[{account.account_name}] 分享登录返回数据不完整")
            return None

        logger.info(f"[{account.account_name}] 分享登录成功，已获取用户信息")
        return login_info

    def auto_sign_and_fetch_package(self, sf_api: SFExpressAPI, account_name: str) -> Dict[str, Any]:
        """
        自动签到并获取礼包

        Args:
            sf_api: SF API实例
            account_name: 账号名称

        Returns:
            Dict[str, Any]: 签到结果，包含成功状态和连续签到天数
        """
        try:
            logger.info(f"[{account_name}] 开始执行自动签到获取礼包...")
            result = sf_api.automatic_sign_fetch_package()

            if result.get("success"):
                obj = result.get("obj", {})
                has_finish_sign = obj.get("hasFinishSign", 0)
                count_day = obj.get("countDay", 0)
                package_list = obj.get("integralTaskSignPackageVOList", [])

                if has_finish_sign == 1:
                    logger.info(f"[{account_name}] 今日已完成签到，连续签到 {count_day} 天")
                else:
                    logger.info(f"[{account_name}] 签到成功！连续签到 {count_day} 天")

                # 记录获得的礼包
                if package_list:
                    logger.info(f"[{account_name}] 获得签到礼包:")
                    for package in package_list:
                        package_name = package.get("commodityName", "未知礼包")
                        invalid_date = package.get("invalidDate", "")
                        logger.info(f"[{account_name}] - {package_name} (有效期至: {invalid_date})")
                else:
                    logger.info(f"[{account_name}] 未获得签到礼包")

                return {'success': True, 'days': count_day, 'already_signed': has_finish_sign == 1}
            else:
                error_msg = result.get("errorMessage", "未知错误")
                logger.warning(f"[{account_name}] 签到失败: {error_msg}")
                return {'success': False, 'days': 0, 'error': error_msg}

        except Exception as e:
            logger.error(f"[{account_name}] 自动签到时发生错误: {e}")
            return {'success': False, 'days': 0, 'error': str(e)}

    def process_single_task(self, task: Dict[str, Any], sf_api: SFExpressAPI, account_name: str) -> Dict[str, Any]:
        """
        处理单个任务

        Args:
            task: 任务信息
            sf_api: SF API实例
            account_name: 账号名称

        Returns:
            Dict[str, Any]: 任务执行结果
        """
        task_title = task.get('title', '未知任务')
        task_code = self.extract_task_code(task)

        if not task_code:
            logger.warning(f"[{account_name}] 任务 {task_title} 缺少任务代码，跳过")
            return {'title': task_title, 'success': False, 'points': 0}

        try:
            finish_result = sf_api.finish_task(task_code)
            if finish_result and finish_result.get('success'):
                logger.info(f"[{account_name}] 任务 {task_title} 完成成功")

                # 获取任务奖励
                reward_result = sf_api.fetch_tasks_reward()
                logger.info(f"[{account_name}] 任务奖励获取结果: {reward_result}")

                # 提取获得的积分
                points = 0
                if reward_result and reward_result.get('success'):
                    obj_list = reward_result.get('obj', [])
                    if isinstance(obj_list, list):
                        for item in obj_list:
                            points += item.get('point', 0)

                return {'title': task_title, 'success': True, 'points': points}
            else:
                logger.warning(f"[{account_name}] 任务 {task_title} 完成失败或无返回结果")
                return {'title': task_title, 'success': False, 'points': 0}
        except Exception as e:
            logger.error(f"[{account_name}] 执行任务 {task_title} 时发生错误: {e}")
            return {'title': task_title, 'success': False, 'points': 0}

    def process_account_tasks(self, account: SFAccountConfig) -> Dict[str, Any]:
        """
        处理单个账号的所有任务

        Args:
            account: 账号信息

        Returns:
            Dict[str, Any]: 账号任务执行统计
        """
        account_name = account.account_name

        # 初始化账号统计
        account_stat = {
            'account_name': account_name,
            'sign_success': False,
            'sign_days': 0,
            'total_tasks': 0,
            'completed_tasks': 0,
            'total_points': 0,
            'available_points': None,
            'tasks': []
        }

        if not account.sign:
            logger.error(f"账号 {account_name} 配置信息不完整，缺少sign，跳过处理")
            account_stat['error'] = '配置信息不完整'
            return account_stat

        logger.info(f"开始处理账号: {account_name}")

        try:
            login_info = self.fetch_login_info(account)
            if login_info is None:
                account_stat['error'] = '分享登录失败'
                return account_stat

            # 创建API实例
            sf_api = SFExpressAPI(
                cookies=login_info.cookies,
                device_id=account.device_id,
                user_id=login_info.user_id,
                user_agent=account.user_agent,
                channel=account.channel
            )

            # 首先执行自动签到获取礼包
            sign_result = self.auto_sign_and_fetch_package(sf_api, account_name)
            account_stat['sign_success'] = sign_result.get('success', False)
            account_stat['sign_days'] = sign_result.get('days', 0)

            # 签到后稍作延时
            sign_delay = random.uniform(*DELAY_AFTER_SIGN)
            logger.info(f"[{account_name}] 签到完成，延时 {sign_delay:.2f} 秒后继续任务...")
            time.sleep(sign_delay)

            # 获取任务列表
            task_list = self.get_task_list(sf_api)

            if not task_list:
                logger.warning(f"[{account_name}] 未获取到任务列表")
            else:
                logger.info(f"[{account_name}] 获取到 {len(task_list)} 个任务")

                # 处理每个任务
                for i, task in enumerate(task_list, 1):
                    logger.info(f"[{account_name}] 开始处理第 {i}/{len(task_list)} 个任务")

                    if task.get("taskPeriod") != "D":
                        logger.info(f"[{account_name}] 任务 {task.get('title', '未知任务')} 非日常任务，跳过")
                        continue

                    account_stat['total_tasks'] += 1

                    # 如果任务已完成，跳过
                    if task.get("status") == 3:
                        logger.info(f"[{account_name}] 任务 {task.get('title', '未知任务')} 已完成，跳过")
                        continue

                    delay_time = random.uniform(*DELAY_BETWEEN_TASKS)
                    logger.info(f"[{account_name}] 准备执行任务 {task.get('title', '未知任务')}，延时 {delay_time:.2f} 秒...")
                    time.sleep(delay_time)

                    task_result = self.process_single_task(task, sf_api, account_name)
                    account_stat['tasks'].append(task_result)

                    if task_result.get('success'):
                        account_stat['completed_tasks'] += 1
                        account_stat['total_points'] += task_result.get('points', 0)

            # 查询账号积分信息（当前积分）
            user_info_result = sf_api.query_user_info()
            if user_info_result.get("success"):
                user_info_obj = user_info_result.get("obj", {})
                available_points = user_info_obj.get("availablePoints")
                account_stat['available_points'] = available_points
                logger.info(f"[{account_name}] 当前积分: {available_points}")
            else:
                error_msg = user_info_result.get("errorMessage") or user_info_result.get("error") or "未知错误"
                logger.warning(f"[{account_name}] 查询当前积分失败: {error_msg}")

        except Exception as e:
            logger.error(f"处理账号 {account_name} 时发生错误: {e}")
            account_stat['error'] = str(e)

        return account_stat

    def run_all_accounts(self) -> None:
        """执行所有账号的任务处理"""
        if not self.accounts:
            logger.warning("没有配置的账号，程序退出")
            return

        logger.info(f"开始执行任务，共 {len(self.accounts)} 个账号")

        for i, account in enumerate(self.accounts, 1):
            logger.info(f"\n{'='*60}")
            logger.info(f"处理第 {i}/{len(self.accounts)} 个账号")
            logger.info(f"{'='*60}")

            account_stat = self.process_account_tasks(account)
            self.task_summary.append(account_stat)
            logger.info(f"账号 {i} 处理完成")

            # 账号间添加延时，避免频繁切换
            if i < len(self.accounts):
                account_delay = random.uniform(*DELAY_BETWEEN_ACCOUNTS)
                logger.info(f"账号切换延时 {account_delay:.2f} 秒...")
                time.sleep(account_delay)

        logger.info("所有账号任务处理完成")

    def send_notification(self, start_time: datetime, end_time: datetime) -> None:
        """
        发送任务执行汇总推送通知

        Args:
            start_time: 任务开始时间
            end_time: 任务结束时间
        """
        try:
            duration = (end_time - start_time).total_seconds()

            # 计算总体统计
            total_accounts = len(self.task_summary)
            total_sign_success = sum(1 for stat in self.task_summary if stat.get('sign_success'))
            total_completed = sum(stat.get('completed_tasks', 0) for stat in self.task_summary)
            total_points = sum(stat.get('total_points', 0) for stat in self.task_summary)

            # 构建推送标题
            title = f"{self.site_name}积分任务完成 ✅"

            # 构建推送内容
            content_parts = [
                f"📊 总体统计",
                f"━━━━━━━━━━━━━━━━",
                f"👥 账号数量: {total_accounts}个",
                f"✅ 签到成功: {total_sign_success}/{total_accounts}",
                f"📝 完成任务: {total_completed}个",
                f"🎁 获得积分: {total_points}分",
                f"⏱️ 执行耗时: {int(duration)}秒",
                "",
                f"📋 账号详情",
                f"━━━━━━━━━━━━━━━━"
            ]

            # 添加每个账号的详细信息
            for i, stat in enumerate(self.task_summary, 1):
                account_name = stat.get('account_name', f'账号{i}')
                sign_days = stat.get('sign_days', 0)
                completed = stat.get('completed_tasks', 0)
                points = stat.get('total_points', 0)
                available_points = stat.get('available_points')

                # 账号摘要
                if stat.get('error'):
                    content_parts.append(f"❌ [{account_name}] 执行失败")
                    content_parts.append(f"   错误: {stat['error']}")
                else:
                    sign_status = "✅" if stat.get('sign_success') else "❌"
                    content_parts.append(f"{sign_status} [{account_name}]")
                    content_parts.append(f"   📅 连续签到: {sign_days}天")
                    content_parts.append(f"   📝 完成任务: {completed}个")
                    content_parts.append(f"   🎁 获得积分: {points}分")
                    if available_points is not None:
                        content_parts.append(f"   💰 当前积分: {available_points}分")

                # 账号之间添加空行
                if i < len(self.task_summary):
                    content_parts.append("")

            # 添加完成时间
            content_parts.append("━━━━━━━━━━━━━━━━")
            content_parts.append(f"🕐 {end_time.strftime('%Y-%m-%d %H:%M:%S')}")

            content = "\n".join(content_parts)

            # 发送推送
            send_notification(
                title=title,
                content=content,
                sound=NotificationSound.BIRDSONG
            )
            logger.info(f"✅ {self.site_name}任务汇总推送发送成功")

        except Exception as e:
            logger.error(f"❌ 发送任务汇总推送失败: {str(e)}", exc_info=True)


    def send_ql_notification(self, start_time: datetime, end_time: datetime) -> None:
        """青龙通知兜底：走面板接口（面板通知设置/企业微信）。
        现有的 send_notification 走自带 notification.py，只读 env/config 里的
        QYWX 等渠道，面板里配的企业微信收不到，所以这里再发一次面板接口。"""
        try:
            total = len(self.task_summary)
            ok = sum(1 for stat in self.task_summary if stat.get('sign_success'))
            points = sum(stat.get('total_points', 0) for stat in self.task_summary)
            title = f"{self.site_name}积分任务：{ok}成功/{total - ok}失败"
            lines = [
                f"{self.site_name}积分任务",
                "",
                f"总结：{ok} 成功 / {total - ok} 失败",
                f"签到成功：{ok}/{total}",
                f"获得积分：{points}分",
            ]
            for i, stat in enumerate(self.task_summary, 1):
                account_name = stat.get('account_name', f'账号{i}')
                if stat.get('error'):
                    lines.append(f"❌ [{account_name}] 执行失败：{str(stat['error'])[:120]}")
                else:
                    sign_status = "✅" if stat.get('sign_success') else "❌"
                    lines.append(
                        f"{sign_status} [{account_name}] 连续签到 {stat.get('sign_days', 0)}天｜"
                        f"完成 {stat.get('completed_tasks', 0)} 个任务｜获得 {stat.get('total_points', 0)} 分"
                    )
            content = "\n".join(lines)
            _tail = _ql_log_tail()
            if _tail:
                content += "\n\n📋 日志尾部（最近30行）:\n" + _tail
            _ql_notify(title, content)
        except Exception as e:
            logger.error(f"❌ 发送青龙通知失败: {str(e)}", exc_info=True)


def log_task_header(title: str, timestamp: datetime) -> None:
    """打印任务执行标题"""
    logger.info("=" * 60)
    logger.info(f"{title} - {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)


def main():
    """主函数"""
    # 青龙通知取日志尾部：把 root logger 的记录同时写进内存缓冲
    _ql_log_handler = logging.StreamHandler(_ql_log_buf)
    _ql_log_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logging.getLogger().addHandler(_ql_log_handler)
    # 记录开始时间
    start_time = datetime.now()
    log_task_header("顺丰快递积分任务开始执行", start_time)

    try:
        # 创建任务管理器
        manager = SFTasksManager()

        # 执行所有账号的任务
        manager.run_all_accounts()

        # 记录结束时间
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.info("=" * 60)
        logger.info(f"顺丰快递积分任务执行完成 - {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"执行耗时: {int(duration)} 秒")
        logger.info("=" * 60)

        # 发送推送通知（自带 notification.py 渠道 + 青龙面板接口兜底）
        if manager.task_summary:
            manager.send_notification(start_time, end_time)
            manager.send_ql_notification(start_time, end_time)
        else:
            _ql_notify("顺丰快递积分任务：0成功/0失败", "⚠️ 没有配置账号，程序退出（请先配好 shunfeng/config/token.json）")

        return 0

    except Exception as e:
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        logger.error(f"任务执行异常: {str(e)}", exc_info=True)

        # 发送错误通知
        try:
            send_notification(
                title=f"顺丰快递积分任务异常 ❌",
                content=(
                    f"❌ 任务执行异常\n"
                    f"💬 错误信息: {str(e)}\n"
                    f"⏱️ 执行耗时: {int(duration)}秒\n"
                    f"🕐 完成时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}"
                ),
                sound=NotificationSound.ALARM
            )
        except Exception:
            logger.error("发送异常通知失败", exc_info=True)

        _ql_notify(
            "顺丰快递积分任务异常 ❌",
            "❌ 任务执行异常\n💬 错误信息: %s\n⏱️ 执行耗时: %d秒\n🕐 完成时间: %s" % (
                str(e), int(duration), end_time.strftime("%Y-%m-%d %H:%M:%S")),
        )
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
