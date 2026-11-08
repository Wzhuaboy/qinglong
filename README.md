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

## 规矩

- token、cookie、密码、缓存文件（如 `chinaTelecom_cache.json`）一律不进仓库，只放青龙面板的环境变量里。
- 本库由 `Wzhuaboy/museai` 里的 `qinglong/` 整理拆分而来，之后青龙脚本只往这里加。
