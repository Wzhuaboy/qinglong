# 顺丰快递积分任务（Cookie 版）

- 脚本：`script/sf/main.py`，依赖同目录 `script/sf/api.py`、`script/sf/code.js`，以及本目录的 `notification.py`
- 来源：`https://github.com/Cat-zaizai/ZaiZaiCat-Checkin`，原文件 `script/sf/main.py` 等
- 文件最后提交：`main.py` / `api.py` 为 2026-02-12，提交 `1c19b4aa93b18d471fd6fb1cfbb5f960b44f5d71`；`code.js` 文件日为 2025-11-24；仓库 README 2026-09-12 仍标“可用”。目录结构按上游原样保留（`script/sf/` 三层），因为 `main.py` 按相对位置算配置路径和模块路径，改平会找不到配置。
- 语言：Python；依赖 `requests`、`PyExecJS`（`api.py` 用 execjs 编译 `code.js`）
- 定时：脚本头为占位 `cron: 1 1 1 1 1`（每年 1 月 1 日，实际等于不跑），需在青龙里自定时间，建议每天跑一次
- 账号配置：不走环境变量，走配置文件 `config/token.json`。把 `config/token.json.example` 复制为 `config/token.json`，按模板格式填自己的 Cookie 等账号信息。`token.json` 不要进仓库，本库只放 `.example` 模板。
- 通知（可选）：`notification.py` 支持 Bark、Server 酱等，配 `config/notification.json`（见 `config/notification.json.example`）或环境变量；不配也能跑，只是不推送。
- 青龙任务命令：`task shunfeng/script/sf/main.py`
- 通知（青龙面板兜底）：跑完（成功和失败都发）除了走原 notification.py 的渠道外，还会发一次青龙通知，标题格式为“顺丰速运积分任务：X成功/Y失败”（异常时为“顺丰快递积分任务异常”），正文为执行汇总（签到成功几/总计几、每账号连续签到/完成任务/获得积分）+ 日志尾部最多 30 行，总长截到约 1800 字符（企业微信应用消息有长度限制，完整日志见青龙运行日志）。原 notification.py 只读 env/config 里的渠道，面板里配的企业微信收不到，所以加了这层兜底。
- 通知通道：优先调青龙面板本地接口 PUT /open/system/notify（带系统 token），走面板“系统设置/通知设置”里配好的渠道（如企业微信）。以前只调 notify.py / sendNotify.js 时收不到，是因为它们只读 QYWX_AM 等环境变量，读不到面板数据库里的配置；`ql notify` 这个子命令在青龙 2.24.0 上不存在。面板接口失败时会在日志里写明原因，再试 notify.py / sendNotify.js（仅环境变量渠道有效）。
