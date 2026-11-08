# 345云脚本库同步

来源：https://script.345yun.cn （青龙脚本分享站，用户上传的签到/阅读/羊毛类脚本）

## 目录规则

- 按上传日期分文件夹：`qinglong/345yun/YYYY-MM-DD/`，文件夹里是当天上传的全部脚本原文件
- 每个日期文件夹带一份 `README.md` 清单：文件名、站内 ID、上传时间、站内登记的 sha256、下载文件 sha256、校验结果

## 同步方式

- 元数据接口：`GET https://script.345yun.cn/api/scripts`（一次返回全部脚本，字段含 id、filename、file_type、upload_time、file_hash），按 upload_time 的日期前缀在本地过滤
- 文件直链：`GET https://script.345yun.cn/api/download/direct/{id}`（无需登录）
- 站点下载时会在文件头尾各加一段来源声明（头部 11 行、尾部 12 行，个别文件无尾部段），站内登记的 file_hash 是原始文件哈希：校验时剥掉这段声明后比对
- 同步脚本：本目录 `sync_345yun.py`，用法 `python3 sync_345yun.py --date 2026-10-17`（默认同步昨天）

## 节奏

- 每天 23:55（Asia/Shanghai）由慕斯定时同步前一天上传的全部脚本并推送到本仓库
- 2026-10-17 这批是首次手动同步（2026-10-20 补的）
