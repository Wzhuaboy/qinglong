# 众安健康（协议）

- 脚本：`zajk.py`（众安健康微信小程序「签到赚金」）
- 来源：`https://github.com/lcmovie/YYB-GO-Script-i`，原文件 `wx-script/zajk.py`
- 文件最后提交：2026-10-03，提交 `acf34de409ecb79096fdbb8dfaf4b75c5dde3ff6`
- 语言：Python
- 定时：`25 7 * * *`（脚本头，每天 07:25）
- 环境变量：`YYB_SERVER` 必填，格式 `YYB 地址@微信账号标识`，多账号每行一条；可选 `ZAJK_ENABLE_SIGN` / `ZAJK_ENABLE_BROWSE` / `ZAJK_ENABLE_WITHDRAW`（默认开启，填 `0` 关闭）、`ZAJK_WITHDRAW_MIN`（默认 `500`，即满 5 元自动提现）、`ZAJK_LOGIN_RETRY`（默认 `3`）、`ZAJK_DRY_RUN`（填 `1` 只试跑不落库）
- 配置方法：先在自建 yyb-go 里授权好微信账号，再把 `YYB_SERVER` 填进青龙环境变量；基于 YYB 取码登录，全程无需抓包。不要把地址和账号标识写进仓库。
- 青龙任务命令：`task zhongan-jiankang/zajk.py`
