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
