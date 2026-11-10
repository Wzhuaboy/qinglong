# 飞米阅读

- 脚本：`feimi.py`（原 `upload.py` 改的青龙版）
- 目标：每天读 30 篇，停留 6~9 秒，前 3 篇尽量真机推送过检测
- 后端：`https://hwz.tslu.cn`，计次：`https://rdapi.hzjianyue.cn/api/articleTask0428`
- 入口：邀请码 ID `197705`，二维码解出来是 `http://1794312838.sxqovp.asia/pages/inviteGo.html?id=197705&t=1794312838`，经 `https://hwz.tslu.cn/api/getInviteRedirectUrl/?id=197705` 跳到 `http://feimiyin.cn?id=197705`

## 飞米怎么登录（已核实）

飞米是 H5 站，不是小程序 wx.login，自家 yyb-go 取码不适用。

1. 在浏览器（不要用微信内置浏览器）打开 `http://feimiyin.cn?id=197705`
2. 页面出 6 位登录码（10 分钟有效）+ 二维码，用微信扫码打开验证页，把 6 位码填进去点验证并登录
3. 登录后 token 存在浏览器 localStorage 的 `userToken` 里（Windows Chrome：F12 → Application → Local Storage → `userToken`），也可以抓包看 `getHomeInfo/?token=...` 那串
4. 把 token 填进青龙环境变量 `FEIMI_TOKEN`，不要发聊天里

## 环境变量（只填青龙面板，不写进仓库）

| 变量 | 必填 | 说明 |
|---|---|---|
| `FEIMI_TOKEN` | 方式 A 必填 | 飞米 token，直跑，不走登录 |
| `FEIMI_USERNAME` / `FEIMI_PASSWORD` / `FEIMI_OPENIDS` | 方式 C 才用 | 951 平台（`http://951.bllnl.fun:18080`）账号 + OpenID，平台代取 token |

## 走法

- 方式 A（已可用）：只填 `FEIMI_TOKEN`，`--check` 能走到 `getHomeInfo` 那步，假 token 会回 `code 201 未登录`，真 token 就能继续。
- 方式 C（原版）：填 951 平台账号密码 + OpenID，脚本走平台取 token。

## 自检

```
python3 feimi.py --check
```

只验登录、基线、票据、领第一篇，不进阅读循环、不计金币。

## 依赖

Python 3 + `requests` + `cryptography`。
