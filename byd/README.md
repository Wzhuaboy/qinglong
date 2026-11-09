# 比亚迪小程序批量签到

- 脚本：`tools/byd_sign_all.py`，依赖同目录 `tools/byd_app_sign.py`
- 来源：`https://github.com/fanturbo/bydSign`，原文件 `tools/` 下
- 文件最后提交：2026-10-13，提交 `1fef192fb8ecc12cd43d71fc919d176eed276434`
- 语言：Python；依赖 `requests`、`pycryptodome`（`byd_app_sign.py` 用 AES）
- 定时：脚本头未注明，上游 README 建议每天早上 8 点
- 账号配置：不走环境变量，走配置文件 `data/byd_accounts.json`。把 `data/byd_accounts.example.json` 复制为 `data/byd_accounts.json`，格式 `{"name": "账号名", "session_id": "32 位 session_id", "note": "备注(可选)"}`，支持多个账号。`byd_accounts.json` 和运行时生成的 `data/byd_state.json` 不要进仓库，本库只放 `.example` 模板。
- 配置方法：抓包 `weixin90.bydauto.com.cn` 的请求，取 32 位 `session_id` 填进去；作者自述 session 仅 2 小时有效，过期需重抓重填。手动取 session 可用上游的 `tools/byd_get_session.py`（未入仓）。
- 说明：`byd_app_sign.py` 含小程序协议破解参数（AppSecret、AES key/iv），属协议常量、非个人凭证，脚本签名校验要用；`tools/byd_admin.py`（管理页）未入仓，上游有需要可再取。
- 运行：`python tools/byd_sign_all.py`（签所有账号）或加 `--name 账号名` 只签一个；青龙任务命令：`task byd/tools/byd_sign_all.py`
