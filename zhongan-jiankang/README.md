# 众安健康（协议）

- 脚本：`zajk.py`（众安健康微信小程序「签到赚金」）
- 来源：`https://github.com/lcmovie/YYB-GO-Script-i`，原文件 `wx-script/zajk.py`
- 文件最后提交：2026-10-03，提交 `acf34de409ecb79096fdbb8dfaf4b75c5dde3ff6`
- 语言：Python
- 定时：`25 7 * * *`（脚本头，每天 07:25）
- 环境变量：`YYB_SERVER` 必填，格式 `YYB 地址@微信账号标识`，多账号每行一条；可选 `ZAJK_ENABLE_SIGN` / `ZAJK_ENABLE_BROWSE` / `ZAJK_ENABLE_WITHDRAW`（默认开启，填 `0` 关闭）、`ZAJK_WITHDRAW_MIN`（默认 `500`，即满 5 元自动提现）、`ZAJK_LOGIN_RETRY`（默认 `3`）、`ZAJK_DRY_RUN`（填 `1` 只试跑不落库）
- 配置方法：先在自建 yyb-go 里授权好微信账号，再把 `YYB_SERVER` 填进青龙环境变量；基于 YYB 取码登录，全程无需抓包。不要把地址和账号标识写进仓库。
- 青龙任务命令：`task zhongan-jiankang/zajk.py`
- 通知：跑完（成功和失败都发）会发青龙通知，标题格式为“众安健康签到：X成功/Y失败”，正文为执行汇总（账号统计、每账号签到/领奖/浏览/总签到金）+ 日志尾部最多 30 行，总长截到约 1800 字符（企业微信应用消息有长度限制，完整日志见青龙运行日志）。面板接口失败时继续走原 notify.py → PushPlus → Server酱 → Bark。
- 通知通道：优先调青龙面板本地接口 PUT /open/system/notify（带系统 token），走面板“系统设置/通知设置”里配好的渠道（如企业微信）。以前只调 notify.py / sendNotify.js 时收不到，是因为它们只读 QYWX_AM 等环境变量，读不到面板数据库里的配置；`ql notify` 这个子命令在青龙 2.24.0 上不存在。面板接口失败时会在日志里写明原因，再试 notify.py / sendNotify.js（仅环境变量渠道有效）。
