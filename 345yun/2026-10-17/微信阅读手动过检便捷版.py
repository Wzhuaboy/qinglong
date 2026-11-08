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


# 配置说明：


#本脚本修改了推送内容，无需搜一搜进入，点击即可，极大方便了手段过检测！！！！


# 1. 环境变量 QQ_TOKEN: 配置token账号信息支持多账号分隔符：
# 3. 可配置过检测接口
# 4. 环境变量 qqyd_proxy: 配置代理连接，注意代理时长选择！注意代理时长选择！注意代理时长选择！同一账号运行时不要换ip（4.0更新内容）
# 5. 环境变量 PUSHPLUS_TOKEN: PushPlus推送令牌（微信关注PushPlus获得token）
# 6.任务定时  */65 * * * *
# 活动入口 https://wdcdn.qpic.cn/MTMxMDI2NjE5ODc3MDI0NzE_293716_Trl1wa5i_vyhkba8_1760686005?sign=1760686074-368252604-0-7e6d4e2b209cb7904c61f7b5ad6d7463
# 推送检测文章需要在微信里观看检测文章8秒左右，否则当天会被限制不能在看文章（复制检测文章地址，随便发给一个好友观看即可）

import time, json, random, requests, os
from urllib.parse import urlparse, parse_qs, unquote

# -------------------------- PushPlus推送配置（已集成，无需修改）--------------------------
PUSHPLUS_TOKEN = os.getenv("PUSHPLUS_TOKEN")  # 从青龙环境变量读取令牌
def push_to_pushplus(title, content):
    if not PUSHPLUS_TOKEN:
        print("⚠️ 未配置PUSHPLUS_TOKEN，跳过微信推送")
        return
    push_url = "http://www.pushplus.plus/send"
    push_data = {
        "token": PUSHPLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html",
        "topic": ""  # 如需多设备推送，填PushPlus群组topic，无则留空
    }
    try:
        requests.post(push_url, data=push_data, timeout=10)
        print("✅ PushPlus微信推送成功，请注意查收通知～")
    except Exception as e:
        print(f"❌ PushPlus推送失败：{str(e)}")

PROXY_URL = os.getenv("qqyd_proxy")
UA_USER_AGENT = os.getenv("qqyd_ua")
# 配置
API_URL = ''  # 检测文章提交接口URL（有则填，自动过检；无则手动阅读+微信通知）

def get_random_r():
    return str(random.uniform(0, 1))

def gettime():
    return str(int(time.time() * 1000))

def extract_biz(url):
    """从微信公众号文章链接中提取__biz参数值"""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    if '__biz' in query_params:
        return query_params['__biz'][0]
    else:
        return None

def getHomeInfo():
    """获取首页信息"""
    url = 'https://read.tslu.cn/abaaba/getHomeInfo/'
    params = {'token': TOKEN}
    headers = {
        'Host': 'read.tslu.cn',
        'Connection': 'keep-alive',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'User-Agent': UA_USER_AGENT,
        'Origin': 'http://we.e9l.cn',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'http://we.e9l.cn/',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    try:
        response = requests.get(url, headers=headers, params=params, proxies=proxies).json()
        if response.get('code') == 0:
            home_data = response.get('data', {})
            print(
                f"首页信息 - 用户ID: {home_data.get('id', '未知')} | 累计阅读: {home_data.get('dayreads', 0)}天 | 金币: {home_data.get('gold', 0)}")
            return home_data
        else:
            print(f"首页信息获取失败: {response.get('msg', '未知错误')}")
    except Exception as e:
        print(f"首页信息请求异常: {str(e)}")
    return None

def extract_parameters(url):
    """从URL中提取t、ch、u参数"""
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    params = {}
    if 'path=page/search/christmas_jump' in parsed_url.query and 'query=' in parsed_url.query:
        for key, value in query_params.items():
            if key == 'query':
                nested_url = unquote(value[0])
                nested_parsed = urlparse(nested_url)
                nested_params = parse_qs(nested_parsed.query)
                for param in ['t', 'ch', 'u']:
                    if param in nested_params:
                        params[param] = nested_params[param][0]
                break
    else:
        for param in ['t', 'ch', 'u']:
            if param in query_params:
                params[param] = query_params[param][0]
    t = params.get('t', '')
    u = params.get('u', '')
    ch = params.get('ch', '')
    if t=='' or u=='' or ch=='':
        print(f"参数获取异常: {parsed_url}")
        exit(0)
    return t, u, ch

def getReadUrl():
    url = 'https://read.tslu.cn/abaaba/getReadUrl/'
    headers = {
        'Host': 'read.tslu.cn',
        'Connection': 'keep-alive',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'User-Agent': UA_USER_AGENT,
        'Origin': 'http://we.e9l.cn',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'http://we.e9l.cn/',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    params = {'type': 2,'b': str(int(time.time()*1000)), 'token': TOKEN}
    try:
        response = requests.get(url, headers=headers, params=params, proxies=proxies).json()
        return extract_parameters(response['data']['url'])
    except Exception as e:
        print(f"参数获取异常: {str(e)}")
        return '未获取t', '未获取u', '未获取ch'

def check_article(aid, article_url):
    """文章检测逻辑（已替换为PushPlus推送）"""
    print(f"检测文章 [ID:{aid}]")
    if not API_URL:
        print(f"未配置自动过检，启动微信推送提醒手动阅读～")
        title = "⚠️ 紧急！60秒内完成手动阅读 ⚠️"
        content = f'<a href="\n{article_url}\n"target="_blank">👉点击阅读8s以上并返回\n{article_url}\n',
        push_to_pushplus(title, content)  # 调用PushPlus推送到微信
        time.sleep(60)
        return True
    else:
        try:
            resp = requests.post(API_URL, json={"url": article_url,'token': TOKEN,'ua':UA_USER_AGENT,'proxies':proxies}, timeout=60).json()
            if resp['status'] == 'success':
                time.sleep(8)
                print("✅ 自动过检成功")
                return True
            else:
                print(f"❌ 自动过检失败: {resp['message']}")
                return False
        except Exception as e:
            print(f"过检请求异常: {e}")
            return False

def sign_in():
    """执行签到"""
    print("\n--- 执行签到 ---")
    sign_url = "https://read.tslu.cn/abaaba/getxshd/"
    headers = {
        'Host': 'read.tslu.cn',
        'Connection': 'keep-alive',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'User-Agent': UA_USER_AGENT,
        'Origin': 'http://we.e9l.cn',
        'Sec-Fetch-Site': 'cross-site',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'Referer': 'http://we.e9l.cn/',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    }
    params = {'token': TOKEN}
    try:
        response = requests.get(sign_url, params=params, headers=headers, proxies=proxies).json()
        if response.get("code") == 0:
            sign_gold = response.get('golds', 0)
            print(f"签到成功! 获得金币: {sign_gold}")
            # 可选：签到成功推送通知（想关闭就删掉下面2行）
            push_to_pushplus("✅ 签到成功通知", f"今日签到完成，获得金币{sign_gold}枚～累计阅读天数：{getHomeInfo().get('dayreads', 0)}天")
            getHomeInfo()  # 刷新金币显示
        else:
            print(f"签到失败: {response.get('msg', '未知错误')}")
    except Exception as e:
        print(f"签到请求异常: {str(e)}")
    print("--- 签到结束 ---\n")

def make_request(loop_count, initial_params, headers):
    """主循环请求逻辑"""
    url = "https://rdapi.hzjianyue.cn/api/articleTask0428"
    current_jkey = None
    current_params = initial_params.copy()
    current_c = 1
    user_id = initial_params.get("u", "")
    channel_id = initial_params.get("ch", "")
    for i in range(loop_count):
        print(f"\n[第{i + 1}次循环] c值: {current_c}")
        params = current_params.copy()
        params["c"] = current_c
        params["r"] = get_random_r()
        if i > 0 and current_jkey:
            params["jkey"] = current_jkey
        try:
            response = requests.get(url, params=params, headers=headers, proxies=proxies)
            response.raise_for_status()
            result = response.json()
            # 检测第5轮完成
            if result.get("code") == 1 and not result.get("data") and "第5轮已经完成" in result.get("msg", ""):
                print(f"检测到第5轮完成，任务结束!")
                sign_in()
                return
            # 检测其他轮次完成/上限
            if result.get("code") == 1 and not result.get("data"):
                msg = result.get("msg", "")
                print(f"轮次完成: {msg}，终止循环")
                # 可选：任务完成推送通知（想关闭就删掉下面1行）
                push_to_pushplus("✅ 今日任务完成", f"阅读任务已结束，原因：{msg}\n当前金币：{getHomeInfo().get('gold', 0)}枚")
                getHomeInfo()
                return
            # 检测链接失效，重新获取参数
            if result.get("code") == 1 and result.get("msg") == "当前链接已失效, 请获取最新链接哦":
                print("链接失效，重新获取参数...")
                new_t, new_u, new_ch = getReadUrl()
                current_params.update({"t": new_t, "u": new_u, "ch": new_ch})
                user_id, channel_id = new_u, new_ch
                current_jkey = None
                current_c = 1
                continue
            # 处理正常响应
            if result.get("code") == 0:
                data = result.get("data", {})
                current_jkey = data.get("jkey")
                aid = data.get("aid", 0)
                article_url = data.get("url", "")
                _biz = extract_biz(article_url)
                print(f"📖 开始阅读: {article_url}", flush=True)
                print(f"文章信息 - __biz: {_biz} | 已读/总数: {data.get('readNum', 0)}/{data.get('totalNum', 0)}")
                # 触发手动检测的条件
                if _biz in ['MzkyNzYxMDA0Mw==','MzkzNzk3Mjk2MQ==','MzkyMjYxMDAwMA==','Mzk3NTc4MzI1NQ==',
                            'MzI5MjYyNDIxOA==','Mzk0OTYxMDEwNQ==','MzkzNjk3MjIxNg==','MzkzMTk0ODYxOQ==',
                            'MzkzODk3Mjk2NQ==','MzIwOTc0MzYxMg==','MzkyOTk0NzcyNw==','MzkxOTg4MjUzOA==','Mzk4ODQ2OTYyMg==',
                            'MzkzMjk3MDgxNQ==','MzkzOTYxMDQ2Mw==','MzkzODk0NzkwMg==','MzkwODYwOTUxOQ=='] or len(current_jkey) > 35:
                    if not check_article(_biz, article_url):
                        return
                current_c += 1
            else:
                print(f"请求异常: {result.get('msg', '未知错误')}")
                current_c += 1
        except requests.exceptions.RequestException as e:
            print(f"网络请求错误: {e}")
            current_c += 1
        except json.JSONDecodeError:
            print("响应格式错误")
            current_c += 1
        # 延迟处理
        if i < loop_count - 1:
            delay = random.randint(8, 20)
            print(f"等待{delay}秒...")
            time.sleep(delay)
    print(f"\n所有{loop_count}次循环完成")
    getHomeInfo()

if __name__ == "__main__":
    print("="*50)
    print("活动入口：https://wdcdn.qpic.cn/MTMxMDI2NjE5ODc3MDI0NzE_293716_Trl1wa5i_vyhkba8_1760686005?sign=1760686074-368252604-0-7e6d4e2b209cb7904c61f7b5ad6d7463")
    print("="*50)
    print("Q群：711630596")	
    # 读取环境变量
    QQ_TOKEN = os.getenv('QQ_TOKEN')
    if not QQ_TOKEN:
        print("❌ 请先配置环境变量【QQ_TOKEN】（账号token）")
        exit()
    if not UA_USER_AGENT:
        print("❌ 请先配置环境变量【qqyd_ua】（UA信息）")
        exit()
    else:
        print(f"✅ 已加载UA：{UA_USER_AGENT}")
    if PROXY_URL:
        print(f"✅ 已配置代理：{PROXY_URL}")
    else:
        print("ℹ️ 未配置代理【qqyd_proxy】，采用本地网络请求")
    if PUSHPLUS_TOKEN:
        print(f"✅ 已配置PushPlus令牌，将推送通知到微信～")
    else:
        print("⚠️ 未配置环境变量【PUSHPLUS_TOKEN】，仅控制台输出，无微信通知！")
    # 多账号处理
    TOKENS = QQ_TOKEN.split('#')
    print(f"\n✅ 共检测到{len(TOKENS)}个账号，开始依次执行任务...")
    print("="*50)
    for TOKEN in TOKENS:
        print(f"\n📌 正在执行账号：{TOKEN[:8]}****（隐藏部分字符）")
        proxies = {}
        # 代理配置
        if PROXY_URL:
            try:
                get_ip = requests.get(PROXY_URL).text.strip()
                print(f'✅ 获取代理IP成功：{get_ip}')
                proxies = {
                    "http": f"http://{get_ip}",
                    "https": f"http://{get_ip}",
                }
            except Exception as e:
                print(f'❌ 获取代理失败，使用本地网络执行：{str(e)}')
        # 初始操作
        print("\n--- 加载首页信息 ---")
        getHomeInfo()
        print("\n--- 获取阅读参数 ---")
        t, u, ch = getReadUrl()
        initial_params = {
            "t": t,
            "u": u,
            "ch": ch,
            "pageshow": "",
        }
        # 请求头配置
        headers = {
            "Host": "rdapi.hzjianyue.cn",
            "Connection": "keep-alive",
            "User-Agent": UA_USER_AGENT,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "*/*",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9"
        }
        # 执行任务
        loop_times = 39
        print(f"\n✅ 开始执行{loop_times}次阅读循环...")
        make_request(loop_times, initial_params, headers)
        print(f"\n✅ 该账号任务执行完毕！")
        print("="*50)
    print("\n🎉 所有账号任务全部执行完成！")




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