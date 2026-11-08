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

import time, json, random, requests, os

def getHomeInfo():
    """获取首页信息"""
    url = 'https://read.tslu.cn/abaaba/getHomeInfo/'
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
        response = requests.get(url, headers=headers, params=params).json()
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


UA_USER_AGENT = os.getenv("qqyd_ua")
QQ_TOKEN = os.getenv('QQ_TOKEN')
TOKENS = QQ_TOKEN.split('#')
for TOKEN in TOKENS:
    getHomeInfo()

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