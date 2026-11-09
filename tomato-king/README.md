# 统一茄皇（协议）

- 脚本：`TomatoKing_5th.py`
- 来源：`https://github.com/hlt1995/qlScripts`，原文件 `TomatoKing_5th.py`
- 文件最后提交：2026-08-07，提交 `e71ae1c2680a1e281c51c1b97ad14d818202588e`
- 语言：Python
- 定时：`25 12 * * *`（脚本头）
- 环境变量：`QH_CK`，格式 `wid#openId`，多账号用 `&` 或换行分隔
- 配置方法：微信进小程序“统一梦时代”→首页“茄皇的家”，抓包 `farmgames.ioutu.cn` 的请求，取 `wid` 和 `openId`（上游 README 提示的方法）。不要把抓到的值写进仓库，只填青龙环境变量。
- 青龙任务命令：`task tomato-king/TomatoKing_5th.py`
- 已补 `notify.py`（上游同款），缺通知模块问题已修；`TomatoKing_5th.py` 的 `from notify import send` 已改成 try/except 兜底。
- 通知：跑完（成功和失败都发）会发青龙通知，标题格式为“统一茄皇五期：X成功/Y失败”，正文为各账号执行日志汇总，截到约 1800 字符（企业微信应用消息有长度限制，完整日志见青龙运行日志）。
- 通知通道：优先调青龙面板本地接口 PUT /open/system/notify（带系统 token），走面板“系统设置/通知设置”里配好的渠道（如企业微信）。以前只调 notify.py / sendNotify.js 时收不到，是因为它们只读 QYWX_AM 等环境变量，读不到面板数据库里的配置；`ql notify` 这个子命令在青龙 2.24.0 上不存在。面板接口失败时会在日志里写明原因，再试 notify.py / sendNotify.js（仅环境变量渠道有效）。
