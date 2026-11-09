# 可口可乐（协议）

- 脚本：`kekoukele.js`（可口可乐微信小程序签到得积分）
- 来源：`https://github.com/chizinini43-commits/QLqiandao`，原文件 `wxapp/kekoukele.js`
- 文件最后提交：2026-05-14，提交 `19322d4e9f4b0cad29e36302e0f47f18a855d05c`
- 语言：JavaScript
- 定时：`30 9 * * 1`（脚本头，每周一 09:30）
- 环境变量：`kekoukele`（账号，多账号按青龙常用换行分隔；单个账号内以 `#` 分隔字段，首位为 `wcsid`）；另需 `wx_server_url` + `wx_auth`（WeChatCodeServer 取码服务的地址与密钥）
- 配置方法：先搭好或找好 WeChatCodeServer 取码服务，把 `wx_server_url`、`wx_auth` 和 `kekoukele` 填进青龙环境变量。不要把密钥和账号写进仓库。
- 青龙任务命令：`task kekoukele/kekoukele.js`
- 通知：跑完（成功和失败都发）会发青龙通知，标题格式为“可口可乐小程序：X成功/Y失败”，正文为执行汇总（每账号签到结果、剩余快乐瓶）+ 日志尾部最多 30 行，总长截到约 1800 字符（企业微信应用消息有长度限制，完整日志见青龙运行日志）。未配微信 SERVER 时标题为“可口可乐小程序：未执行”。
- 注意：本脚本 require `../tools/env` 与 `./wcs.js`，这两个文件未随库入仓，在青龙上直接跑会报找不到模块，需另外补齐（本次只加了通知逻辑，未改这一依赖）。
- 通知通道：优先调青龙面板本地接口 PUT /open/system/notify（带系统 token），走面板“系统设置/通知设置”里配好的渠道（如企业微信）。以前只调 notify.py / sendNotify.js 时收不到，是因为它们只读 QYWX_AM 等环境变量，读不到面板数据库里的配置；`ql notify` 这个子命令在青龙 2.24.0 上不存在。面板接口失败时会在日志里写明原因，再试 notify.py / sendNotify.js（仅环境变量渠道有效）。
