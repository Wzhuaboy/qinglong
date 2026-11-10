# 飞米阅读

- 脚本：`feimi.py`（原 `upload.py` 改的青龙版）
- 目标：每天读 30 篇，停留 6~9 秒，前 3 篇尽量真机推送过检测
- 后端：`https://hwz.tslu.cn`，计次：`https://rdapi.hzjianyue.cn/api/articleTask0428`

## 环境变量（只填青龙面板，不写进仓库）

| 变量 | 必填 | 说明 |
|---|---|---|
| `FEIMI_TOKEN` | 方式 A 必填 | 飞米 token，直跑，不走登录 |
| `FEIMI_OPENIDS` | 方式 B 必填 | yyb-go 的 ref（OpenID），一行一个，也可用 `&` 或逗号分隔 |
| `FEIMI_APPID` | 方式 B 必填 | 飞米小程序 AppID，`wx` 开头 |
| `FEIMI_LOGIN_URL` | 方式 B 必填 | 飞米在 `hwz.tslu.cn` 上拿 code 换 token 的登录接口完整地址 |
| `YYB_SERVER` | 选填 | 自家 yyb-go，默认 `http://120.77.1.90:8000` |
| `FEIMI_USERNAME` / `FEIMI_PASSWORD` | 方式 C 才用 | 951 平台（`http://951.bllnl.fun:18080`）账号，不推荐 |

## 两种走法

- 方式 A（已可用）：只填 `FEIMI_TOKEN`，`--check` 能走到 `getHomeInfo` 那步，假 token 会回 `code 201 未登录`，真 token 就能继续。
- 方式 B（待补）：填 `FEIMI_OPENIDS` + `FEIMI_APPID` + `FEIMI_LOGIN_URL`，脚本先找自家 yyb-go 取 code，再 POST 到登录接口换 token。缺一个会明确报错，不会偷偷去调 951 平台。

## 自检

```
python3 feimi.py --check
```

只验登录、基线、票据、领第一篇，不进阅读循环、不计金币。

## 依赖

Python 3 + `requests` + `cryptography`。
