# 拼多多果园公众号版（协议）

- 脚本：`pddgy-gzh.js`（拼多多果园公众号版微信小程序 code 静默登录 + 每日签到，附带浇水）
- 来源：`https://github.com/smallfawn/QLScriptPublic.git`，原文件 `wxapp/pddgy-公众号版.js`（311 行），原文件名里的“公众号版”保留在这里说明，入仓后改用 ASCII 文件名 `pddgy-gzh.js`
- smallfawn 库当前 HEAD：`640dbac72a991fbc3c8cdedb17ad204eee3c15d9`（2026-10-17，docs 自动更新提交；本次入仓从该 HEAD 拉取）
- 语言：JavaScript；依赖 `axios`（青龙自带）
- 定时：`28 9,13 * * *`（脚本头，每天 09:28、13:28）
- 环境变量：`pddgy_gzh`（注意不是 `pddgy`；账号，多账号按青龙常用 `&` 或换行分隔；单个账号内以 `#` 分隔，首位为 openid/账号标识，后面可加备注）
- 取码（二选一，YYB 优先）：
  - **优先走 yyb-go**：填 `YYB_SERVER` 即可（格式“地址@账号ref”，多行多账号；与习酒、红色火箭、众安、顺丰速运、可口可乐共用同一个，已配好的不用重填）。`wcs.js` 的 `getCode` 会 POST `{server}/wxapp/getCode`，请求体 `{ref, app_id}`，`app_id` 为拼多多果园公众号版小程序的 `wx839691cce7c102bb`；成功响应形如 `{"code":0,"msg":"success","data":{"openid":"...","result":{"code":"<微信code>","errMsg":"login:ok"}}}`（协议照抄 `hongse-huojian/hshj.js` 的 `yybPost` 与 `shunfeng-suyun/sfsy.py` 的 `_get_wx_code`）。2026-11-10 起 YYB 的 ref 按账号取：`pddgy_gzh` 里每行 OpenID 就是该账号的 ref，`YYB_SERVER` 只提供服务器地址；没传 openid 时才回落第一行。取码失败时该账号记为失败并继续下一个，不抛错中断。`YYB_SERVER` 已配时不再走 WeChatCodeServer。
  - **回落走 WeChatCodeServer**：没配 `YYB_SERVER` 时才走，需另填 `wx_server_url` + `wx_auth`（自建或有授权的取码服务地址与密钥）。不要把密钥和账号写进仓库。
- `pddgy_gzh` 填法（YYB 模式）：填 `YYB_SERVER` 里 `@` 后面的 OpenID，一个账号填一个，多账号按 `&` 或换行分隔；2026-11-10 起取码按该账号自己的 OpenID 取，多微信号各跑各的。只填 `1` 作占位计数时回落到 `YYB_SERVER` 第一行。
- 取码后的流程（未改）：拿到 code 后 GET `https://mobile.yangkeduo.com/garden_index_lz_0.html?...&code=${code}&state=BASE` 换 Cookie（`PDDAccessToken` / `pdd_user_id` / `pdd_user_uin`），再调首页接口拿 `tubetoken` 和水滴数，签到调 `/manor/common/apply/activity`，附带浇水调 `/manor/water/cost`。code 必须是真实有效的微信 code，假 code 换不到真 Cookie，所以通取码链路不等于能跑通签到。首次使用需先在微信里打开“多多果园”小程序完成注册、授权或绑定手机号，否则 yyb-go 也拿不到有效 code。

- 入仓改动（相对原脚本，只改三处，签到/浇水业务逻辑未改）：
  - `pddgy-gzh.js` 里 `require("../tools/env.js")` 改成 `require("./tools/env")`，env.js 跟脚本在同一个拉库目录里，不再依赖仓库根目录是否同步（可口可乐同款修复）。
  - `wcs.js` 照 `kekoukele/wcs.js` 原样抄来，只改头部注释里的脚本名/appid 说明，`getCode` 逻辑未动：有 `YYB_SERVER` 优先走 yyb-go，没配才回落 `POST /wx/code`。
  - 删了 `login()` 里打印 Cookie 的那行 `console.log`，不把 `PDDAccessToken` 等 Cookie 打进日志和通知尾部；`Task.run()` 接好 `checkin()` 返回的 `{ok, already, blocked, msg}`，每账号记一个结果供通知汇总。
- 依赖文件：
  - `pddgy-gzh/tools/env.js`：上游 smallfawn 同仓库 `tools/env.js` 原样复制，7106 字节，与 `kekoukele/tools/env.js`、仓库根目录 `tools/env.js` 的 md5 完全一致。放在 `pddgy-gzh/tools/` 下、与脚本同目录，是因为脚本里写的是 `require("./tools/env")`。
  - `pddgy-gzh/wcs.js`：`kekoukele/wcs.js` 原样复制，只改注释（脚本名/appid 说明、取 code 返回形状按本脚本的 `const { data } = await wechat.getCode(...)` 写），逻辑未动；与 smallfawn 原版 `wxapp/wcs.js`（1839 字节）相比，只改了 `getCode` 的分发，`cloudInit`/`cloudCall` 与原来的 WeChatCodeServer 路径原样保留。
  - 注意：`pddgy-gzh/tools/env.js` 的 `sendMsg` 会 `require("./sendNotify.js")`（即 `pddgy-gzh/tools/sendNotify.js`，未入仓），找不到时只打一行“发送通知失败”日志，不影响主流程退出；真正的跑完通知走的是 `pddgy-gzh.js` 里的面板接口通知（见下）。
- 青龙任务命令：`task pddgy-gzh/pddgy-gzh.js`
- 通知：跑完（成功和失败都发）会发青龙通知，标题格式为“拼多多果园公众号版：X成功/Y失败”，正文为执行汇总（每账号签到结果、水滴数）+ 日志尾部最多 30 行，总长截到约 1800 字符（企业微信应用消息有长度限制，完整日志见青龙运行日志）。未配任何取码服务（既无 `YYB_SERVER` 也无 `wx_server_url`/`wx_auth`）或未找到变量 `pddgy_gzh` 时标题为“拼多多果园公众号版：未执行”。
- 通知通道：优先调青龙面板本地接口 PUT /open/system/notify（带系统 token），走面板“系统设置/通知设置”里配好的渠道（如企业微信）。以前只调 notify.py / sendNotify.js 时收不到，是因为它们只读 QYWX_AM 等环境变量，读不到面板数据库里的配置；`ql notify` 这个子命令在青龙 2.24.0 上不存在。面板接口失败时会在日志里写明原因，再试 notify.py / sendNotify.js（仅环境变量渠道有效）。

- 原 smallfawn 脚本处理办法：不要删 smallfawn 库、不要改它共用的 `wxapp/wcs.js`（同目录几十个小程序脚本共用它，改了全受影响）；用户在青龙面板里只需把 smallfawn 那条“拼多多果园公众号版”定时任务（`28 9,13 * * *`，任务命令是 smallfawn 库下的 `wxapp/pddgy-公众号版.js`）禁用/删除，只留新库这条 `task pddgy-gzh/pddgy-gzh.js`，否则两条会重复跑。青龙面板里拉库更新后，新任务会自动注册（`ql repo` 的任务按脚本头 cron 生成），记得核对不要留两条。
- 验证（2026-11-09，假服务 stub，未用真实账号/code）：①只配 `YYB_SERVER` 指向假 yyb-go：假服务收到 POST `/wxapp/getCode`（`{ref, app_id}` 正确），脚本拿到假 code 后去拼多多登录换 Cookie 失败（假 code 的预期结果），证明取码链路通了、不是模块找不到也不是“未配置”；②只配 `wx_server_url`/`wx_auth` 指向假 WeChatCodeServer：收到 POST `/wx/code`（带 `auth` 头），同样走到登录那步，旧路没被改坏；③什么都不配：正常走“未配置微信SERVER配置”分支退出并通知，无模块找不到报错。三个 JS 文件均过 `node --check`。用与青龙一致的相对路径结构（在 `pddgy-gzh/` 目录内跑 `node pddgy-gzh.js`，不依赖仓库根目录）重测。
- 实跑验证待用户回报：用户正在去微信里登录“多多果园”小程序授权，授权完成后再在青龙上跑一次本脚本，看签到是否成功。
