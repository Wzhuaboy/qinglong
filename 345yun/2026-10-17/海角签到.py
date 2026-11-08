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

import requests
import json
import base64

try:
    from notify import send as send_notification
except ImportError:
    send_notification = None

# 多个账号配置（用户名/密码）
ACCOUNTS = [
    {"username": "账号1", "password": "密码1"},
    {"username": "账号2", "password": "密码2"},
    # 可继续添加更多账号
]

LOGIN_URL = "https://haijiao.com/api/login/signin"
SIGN_IN_URL = "https://haijiao.com/api/user/user_sign_in"

def decode_base64_json(data, max_attempts=50):
    current_data_str = data
    if not isinstance(current_data_str, str):
        return None

    for _ in range(max_attempts):
        try:
            decoded_layer = base64.b64decode(current_data_str.encode('utf-8')).decode('utf-8')
        except Exception:
            break
        if decoded_layer == current_data_str:
            break
        try:
            return json.loads(decoded_layer)
        except json.JSONDecodeError:
            current_data_str = decoded_layer
    return None

def login(username, password):
    s = requests.Session()
    common_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36 Edg/138.0.0.0',
        'Accept': 'application/json, text/plain, */*',
        'Origin': 'https://haijiao.com',
        'pcver': '2',
    }

    login_headers = common_headers.copy()
    login_headers.update({
        'Content-Type': 'application/json;charset=UTF-8',
        'Referer': 'https://haijiao.com/login',
    })

    try:
        r = s.post(LOGIN_URL, json={"username": username, "password": password},
                   headers=login_headers, timeout=15, allow_redirects=True)
        r.raise_for_status()
        res = r.json()

        if res.get("success") is False:
            return False, res.get("message", "登录失败，未知错误")

        if "data" not in res:
            return False, f"登录响应缺少'data'字段：{json.dumps(res, ensure_ascii=False)}"

        decoded_data = decode_base64_json(res.get('data'))

        if not decoded_data or \
           not isinstance(decoded_data.get("user"), dict) or \
           decoded_data.get("user", {}).get("id") is None or \
           decoded_data.get("token") is None:
            return False, "登录数据解析失败或信息缺失"

        user_id = decoded_data["user"]["id"]
        token = decoded_data["token"]
        nickname = decoded_data["user"].get("nickname", username)

        signin_headers = common_headers.copy()
        signin_headers.update({
            'Referer': 'https://haijiao.com/',
            'x-user-id': str(user_id),
            'x-user-token': token,
        })

        return True, {
            'session': s,
            'headers': signin_headers,
            'nickname': nickname
        }
    except requests.exceptions.RequestException as e:
        return False, f"网络请求错误：{e}"
    except json.JSONDecodeError:
        return False, f"响应非JSON格式：{r.text[:500]}..."
    except Exception as e:
        return False, f"登录异常：{e}"

def sign_in(session, headers):
    try:
        r = session.post(SIGN_IN_URL, headers=headers, timeout=10)
        r.raise_for_status()
        res = r.json()

        if res.get("success") is False:
            msg = res.get("message", "未能获取签到信息")
            if "今天已签到" in msg:
                return False, "今天已签到"
            if "请重新登录" in msg:
                return False, "登录失效"
            return False, msg

        if "success" not in res:
            return False, f"签到响应无'success'字段：{json.dumps(res, ensure_ascii=False)}"

        return True, "签到成功"
    except requests.exceptions.RequestException as e:
        return False, f"网络请求错误：{e}"
    except json.JSONDecodeError:
        return False, f"签到响应非JSON格式：{r.text[:500]}..."
    except Exception as e:
        return False, f"签到异常：{e}"

def send_notif(message):
    if send_notification:
        try:
            send_notification("海角签到", message)
        except Exception as e:
            print(f"通知发送失败：{e}")
    else:
        print("通知功能不可用。")

if __name__ == "__main__":
    all_messages = []

    for acc in ACCOUNTS:
        username = acc["username"]
        password = acc["password"]

        login_success, login_data = login(username, password)

        if login_success:
            session = login_data['session']
            headers = login_data['headers']
            nickname = login_data['nickname']

            sign_success, result = sign_in(session, headers)
            if sign_success:
                msg = f"账号【{nickname}】签到成功"
            elif result == "今天已签到":
                msg = f"账号【{nickname}】今天已签到"
            else:
                msg = f"账号【{nickname}】签到失败：{result}"
        else:
            msg = f"账号【{username}】登录失败：{login_data}"

        print(msg)
        all_messages.append(msg)

    send_notif("\n".join(all_messages))


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