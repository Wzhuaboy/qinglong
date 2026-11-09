# 可口可乐（协议）

- 脚本：`kekoukele.js`（可口可乐微信小程序签到得积分）
- 来源：`https://github.com/chizinini43-commits/QLqiandao`，原文件 `wxapp/kekoukele.js`
- 文件最后提交：2026-05-14，提交 `19322d4e9f4b0cad29e36302e0f47f18a855d05c`
- 语言：JavaScript
- 定时：`30 9 * * 1`（脚本头，每周一 09:30）
- 环境变量：`kekoukele`（账号，多账号按青龙常用换行分隔；单个账号内以 `#` 分隔字段，首位为 `wcsid`）；另需 `wx_server_url` + `wx_auth`（WeChatCodeServer 取码服务的地址与密钥）
- 配置方法：先搭好或找好 WeChatCodeServer 取码服务，把 `wx_server_url`、`wx_auth` 和 `kekoukele` 填进青龙环境变量。不要把密钥和账号写进仓库。
- 青龙任务命令：`task kekoukele/kekoukele.js`
