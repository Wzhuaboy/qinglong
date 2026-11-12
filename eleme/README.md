# 饿了么幸运星

- 脚本：`幸运星.py` v1.5.0（饿了么会员权益中心，不是淘宝闪购幸运星）
- 流程：首页聚合取余额 → 签到 → 夺宝抽奖 → 下单免单抽 → 答题 → 查任务 → 浏览/点击埋点 → 再查领奖 → 刷新余额 → 兑换商城 → 汇总推送
- 定时：`30 8 * * *`，命令 `task eleme/幸运星.py`，每天 1 次

## 环境变量（只填青龙面板，不写进仓库）

| 变量 | 必填 | 说明 |
|---|---|---|
| `ELM_COOKIE` | 必填 | 饿了么 Cookie，多账号换行分隔，每行 `备注#cookie`，含 `_m_h5_tk` 最好 |
| `ELM_LAT` / `ELM_LNG` | 建议 | 经纬度，默认上海 31.2304 / 121.4737；船寮镇用 28.26105 / 120.21058 |
| `ELM_QUIZ_ACTID` | 答题才用 | 趣味话题答题的 actId，在答题页 URL 上，不传不跑 |
| `ELM_EXCHANGE` | 默认不开 | 设为 `1` 才自动兑换商城，会消耗幸运星；默认只报告不兑 |

## 自检

```
python eleme/幸运星.py --dump-account
python eleme/幸运星.py --selftest
python eleme/幸运星.py --risk-check
```

## 依赖

Python 3 + `requests` + `urllib3`。
