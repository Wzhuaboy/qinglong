# 顺丰快递积分任务（Cookie 版）

- 脚本：`script/sf/main.py`，依赖同目录 `script/sf/api.py`、`script/sf/code.js`，以及本目录的 `notification.py`
- 来源：`https://github.com/Cat-zaizai/ZaiZaiCat-Checkin`，原文件 `script/sf/main.py` 等
- 文件最后提交：`main.py` / `api.py` 为 2026-02-12，提交 `1c19b4aa93b18d471fd6fb1cfbb5f960b44f5d71`；`code.js` 文件日为 2025-11-24；仓库 README 2026-09-12 仍标“可用”。目录结构按上游原样保留（`script/sf/` 三层），因为 `main.py` 按相对位置算配置路径和模块路径，改平会找不到配置。
- 语言：Python；依赖 `requests`、`PyExecJS`（`api.py` 用 execjs 编译 `code.js`）
- 定时：脚本头为占位 `cron: 1 1 1 1 1`（每年 1 月 1 日，实际等于不跑），需在青龙里自定时间，建议每天跑一次
- 账号配置：不走环境变量，走配置文件 `config/token.json`。把 `config/token.json.example` 复制为 `config/token.json`，按模板格式填自己的 Cookie 等账号信息。`token.json` 不要进仓库，本库只放 `.example` 模板。
- 通知（可选）：`notification.py` 支持 Bark、Server 酱等，配 `config/notification.json`（见 `config/notification.json.example`）或环境变量；不配也能跑，只是不推送。
- 青龙任务命令：`task shunfeng/script/sf/main.py`
