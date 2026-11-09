# 红色火箭（协议）

- 脚本：`hshj.js`（华泰基金指慧家，2026-11-02 单文件版）
- 来源：`https://github.com/lcmovie/YYB-GO-Script-i`，原文件 `wx-script/hshj.js`
- 文件最后提交：2026-11-05，提交 `fbcc9ce4307c5c35c739f5c20bd631fa7e5134c7`
- 语言：JavaScript（Node.js >= 18）
- 定时：`26 10,13 * * *`（脚本头，每天 10:26、13:26）
- 环境变量：`YYB_SERVER` 必填，格式 `YYB 地址@账号ref`，多账号换行；可选 `YYB_API_KEY` / `YYB_PROTOCOL_TOKEN`（YYB 启用协议鉴权时填）、`WX_ID`（只跑指定 ref，格式 `ref#备注`，多账号换行或 `&` 分隔；不填默认跑 `YYB_SERVER` 全部账号）
- 配置方法：先在自建 yyb-go 里授权好微信账号，再把 `YYB_SERVER` 填进青龙环境变量。不要把地址和账号标识写进仓库。
- 注意：首次运行需联网，自动下载约 88MB 公开识别资源到脚本目录，脚本目录需可写；含签到、每日活动、口令查询与兑换，现金红包须手动领。
- 青龙任务命令：`task hongse-huojian/hshj.js`
- 通知：跑完（成功和失败都发）会发青龙通知，标题格式为“红色火箭：X成功/Y失败”，正文为账号汇总（当前积分、红包记录、需手动领取的红包）+ 日志尾部最多 30 行，总长截到约 1800 字符（企业微信应用消息有长度限制，完整日志见青龙运行日志）。未配 YYB_SERVER 时标题为“红色火箭：未执行”。sendNotify.js 只作备用：/ql/data/scripts/sendNotify.js 由青龙启动时从 sample 复制，文件在，但它同样只读环境变量，不能当主通道。
- 通知通道：优先调青龙面板本地接口 PUT /open/system/notify（带系统 token），走面板“系统设置/通知设置”里配好的渠道（如企业微信）。以前只调 notify.py / sendNotify.js 时收不到，是因为它们只读 QYWX_AM 等环境变量，读不到面板数据库里的配置；`ql notify` 这个子命令在青龙 2.24.0 上不存在。面板接口失败时会在日志里写明原因，再试 notify.py / sendNotify.js（仅环境变量渠道有效）。
