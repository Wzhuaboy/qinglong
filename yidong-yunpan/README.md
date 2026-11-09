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
