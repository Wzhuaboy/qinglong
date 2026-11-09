# 统一茄皇（协议）

- 脚本：`TomatoKing_5th.py`
- 来源：`https://github.com/hlt1995/qlScripts`，原文件 `TomatoKing_5th.py`
- 文件最后提交：2026-08-07，提交 `e71ae1c2680a1e281c51c1b97ad14d818202588e`
- 语言：Python
- 定时：`25 12 * * *`（脚本头）
- 环境变量：`QH_CK`，格式 `wid#openId`，多账号用 `&` 或换行分隔
- 配置方法：微信进小程序“统一梦时代”→首页“茄皇的家”，抓包 `farmgames.ioutu.cn` 的请求，取 `wid` 和 `openId`（上游 README 提示的方法）。不要把抓到的值写进仓库，只填青龙环境变量。
- 青龙任务命令：`task tomato-king/TomatoKing_5th.py`
- 已补 `notify.py`（上游同款），缺通知模块问题已修；`TomatoKing_5th.py` 的 `from notify import send` 已改成 try/except 兜底。
