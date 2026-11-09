# 顺丰速运（协议版）

- 脚本：`sfsy.py`（顺丰速运自动任务 v1.0.1，YYB_SERVER 适配版；与 `shunfeng/` 的 Cookie 版是两个不同实现，不要混用）
- 来源：`https://github.com/SuperNaiBA/YYB-GO-Script`，原文件 `sfsy.py`，取提交 `c55efc23d219dd5b1b61dbd1699c185fa8203cb2`
- 文件最后提交：2026-07-31，提交 `9a51f469b9ff5e8ec163cfaf3b83706f9a948654`
- 语言：Python
- 定时：`1 9,21 * * *`（脚本头，每天 09:01、21:01）
- 环境变量：`YYB_SERVER` 必填，格式 `YYB 地址@微信账号标识`，多账号每行一个
- 文件内开关：`ENABLE_DAILY_TASK`（日常积分任务，默认开）、`ENABLE_MEMBER_DAY`（会员日活动，每月 26–28 日自动执行，默认开）、`CONCURRENT_NUM`（并发数，默认 1）
- 说明：文件配置区的 `TOKEN`、`SYS_CODE` 是小程序协议固定参数，随签名请求一起发送，不是个人 Cookie/token；个人身份来自 YYB 取码。不要把 `YYB_SERVER` 写进仓库，只填青龙环境变量。
- 青龙任务命令：`task shunfeng-suyun/sfsy.py`
- 通知：跑完（成功和失败都发）会发青龙通知，标题格式为“顺丰速运：X成功/Y失败”，正文为执行汇总（成功几/总计几、累计积分、每账号积分/会员日奖品、失败原因）+ 日志尾部最多 30 行，总长截到约 1800 字符（企业微信应用消息有长度限制，完整日志见青龙运行日志）。未捕获到账号凭证时也会发失败通知。
- 通知通道：优先调青龙面板本地接口 PUT /open/system/notify（带系统 token），走面板“系统设置/通知设置”里配好的渠道（如企业微信）。以前只调 notify.py / sendNotify.js 时收不到，是因为它们只读 QYWX_AM 等环境变量，读不到面板数据库里的配置；`ql notify` 这个子命令在青龙 2.24.0 上不存在。面板接口失败时会在日志里写明原因，再试 notify.py / sendNotify.js（仅环境变量渠道有效）。
