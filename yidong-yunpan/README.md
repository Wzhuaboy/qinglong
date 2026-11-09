# 移动云盘（139 云盘云朵任务）

- 脚本：`139_yunduo.py`（139 云盘云朵任务自动执行，纯 Python 标准库，无需 pip 装依赖）
- 来源：`https://github.com/deeplee/personal-scripts`，原文件 `139_yunduo.py`
- 文件最后提交：2026-08-06，提交 `a199be481bbc7baf462280dae99caf4cb3cf6c06`
- 语言：Python
- 定时：`0 9 * * *`（脚本头，每天 09:00）
- 环境变量：`YDYP_ACCOUNTS`（多账号：每行一个，格式 `手机号|Basic token`）；或单账号 `YDYP_PHONE` + `YDYP_AUTH`；可选 `YDYP_TRY_ALL`、通知 `PUSHPLUS_TOKEN`、`SENDKEY`
- 配置方法：网页版移动云盘抓包，取请求头里的 `Authorization` Basic token，填进青龙环境变量。不要把 token 写进仓库。
- 青龙任务命令：`task yidong-yunpan/139_yunduo.py`
- 已补 `notify.py`（上游同款），缺通知模块问题已修。
- 通知：跑完（成功和失败都发）会发青龙通知，标题格式为“139云盘云朵任务: X/Y 账号成功”，正文为执行汇总（每账号任务结果）+ 日志尾部最多 30 行，总长截到约 1800 字符（企业微信应用消息有长度限制，完整日志见青龙运行日志）。面板接口失败时继续走 PushPlus → Server酱。
- 通知通道：优先调青龙面板本地接口 PUT /open/system/notify（带系统 token），走面板“系统设置/通知设置”里配好的渠道（如企业微信）。以前只调 notify.py / sendNotify.js 时收不到，是因为它们只读 QYWX_AM 等环境变量，读不到面板数据库里的配置；`ql notify` 这个子命令在青龙 2.24.0 上不存在。面板接口失败时会在日志里写明原因，再试 notify.py / sendNotify.js（仅环境变量渠道有效）。
