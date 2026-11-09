# qinglong

青龙面板专用脚本库，只放青龙跑的任务脚本，不放其他项目。

## 拉库命令

在青龙面板订阅里拉取本仓库：

```
ql repo https://github.com/Wzhuaboy/qinglong.git "" "" "" "main"
```

## 目录

- `tongcheng/` — 同程旅行里程任务（yyb-go 版，每天 07:30，签到 + 任务 + 短剧 + 钞级省抽奖）。环境变量：`tclx`（应用宝 OpenID）、`yyb_go_url`（自建 yyb-go 地址，如 `http://120.77.1.90:8000`）。
- `xmly/` — 喜马拉雅金币任务。`accounts.js` 是空账号模板，账号与 token 由脚本运行时写入，不要手填真实 token 进仓库。
- `345yun/` — 345 云脚本库每日同步（按日期分文件夹）+ 同步脚本 `sync_345yun.py`。
- `tomato-king/` — 统一茄皇（协议），文件日 2026-08-07。环境变量：`QH_CK`（`wid#openId`）。
- `wuyou/` — 无忧计划，文件日 2026-09-28。环境变量：`WY_ACCOUNT`（`账号#密码#device_id#备注`）。
- `hongse-huojian/` — 红色火箭（协议），文件日 2026-11-05。环境变量：`YYB_SERVER`。
- `kekoukele/` — 可口可乐小程序签到，文件日 2026-05-14。环境变量：`kekoukele` + `wx_server_url` / `wx_auth`。
- `zhongan-jiankang/` — 众安健康（协议），文件日 2026-10-03。环境变量：`YYB_SERVER`。
- `yidong-yunpan/` — 移动云盘云朵任务，文件日 2026-08-06。环境变量：`YDYP_ACCOUNTS`（`手机号|Basic token`）。
- `shunfeng/` — 顺丰快递积分任务（Cookie 版），`main.py` 文件日 2026-02-12。账号走 `config/token.json`（只放 `.example` 模板，不放真实配置）。
- `shunfeng-suyun/` — 顺丰速运（协议版），文件日 2026-07-31。环境变量：`YYB_SERVER`。
- `byd/` — 比亚迪小程序批量签到，文件日 2026-10-13。账号走 `data/byd_accounts.json`（只放 `.example` 模板，不放真实配置）。

## 规矩

- token、cookie、密码、缓存文件（如 `chinaTelecom_cache.json`）一律不进仓库，只放青龙面板的环境变量里。
- 本库由 `Wzhuaboy/museai` 里的 `qinglong/` 整理拆分而来，之后青龙脚本只往这里加。
