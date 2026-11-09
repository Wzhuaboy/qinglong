# 无忧计划

- 脚本：`无忧计划.py`
- 来源：`https://github.com/525815266/YYB-Go-Enhanced`，原文件 `scripts/无忧计划.py`
- 文件最后提交：2026-09-28，提交 `ad3e18d199620031edd06c6bb5cc252615cd0934`
- 语言：Python
- 定时：脚本头未注明，建议每天跑一次，时间自定
- 环境变量：`WY_ACCOUNT`，格式 `账号#密码#device_id#备注`，多账号换行分隔；可选 `PROXY_API`、`PROXY_TYPE`、`WY_USER_AGENT`；通知可选 `PUSHPLUS_TOKEN`（脚本内默认值为空，自己填环境变量才推送）
- 配置方法：先在无忧计划 App 注册好账号，账号密码独立版，不依赖 YYB 微信账号。不要把账号密码写进仓库，只填青龙环境变量。
- 青龙任务命令：`task wuyou/无忧计划.py`
