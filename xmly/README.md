# 喜马拉雅金币脚本 · 分享版

一个纯 Python 的自动化脚本：**扫码拿一次 token → 之后每天本地跑，金币自动进账，不需要手机、不需要抓包。**

---

## 0. 先看这个（30 秒）

整套东西只需要两步：

1. **去扫码网站拿 token**（一次性，给每个账号各扫一次）
2. **在本机跑脚本**（之后每天都用它）

ticket 是脚本**本地算出来的**（把 App 里的 `libnativelib.so` 用 CPU 模拟器跑起来现签），
所以抓包、真机、root 全都不需要。

---

## 1. 装环境

需要 **Python 3.9+**（3.14 实测可用）。

```bash
pip install -r requirements.txt
# 国内慢的话：
# pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple
```

装完自检一下（会打印一条 201 字符的 ticket，说明模拟器正常）：

```bash
python3 python/xmly_ticket.py --uid 1
```

> 目录里已经带了 `work/so/libnativelib.so`（从喜马拉雅 9.5.13.3 里提取的 arm64 库），
> 没有它就没法本地签 ticket，别删。

---

## 2. 打开扫码网站拿 token

### 👉 https://xmly.openfan.dpdns.org

直接点开就行 👉 **https://xmly.openfan.dpdns.org**

步骤：

1. 手机打开 **喜马拉雅 App → 我的 → 扫一扫**
2. 扫描网页上的二维码，手机上点 **确认登录**
3. 网页上会显示两样东西，把它们复制下来：
   - **UID**（一串数字，例如 `608255219`）
   - **Token**（很长的一串，形如 `608255219&4EBF91F0140N...`）

> 二维码过期会自动换新的；也可以点「换一张二维码」手动换。

**关于隐私（重要）**：每个浏览器打开页面时会分到一个独立的随机会话编号
（页面上那行「你的会话编号」），二维码和 token 都只回给那一个页面：

- 别人同时开着这个网站，看到的是**他自己那张码**，不会看到你的
- token 投递到你页面后，**服务端那份立刻删除**（页面会提示）。我们不留存
- 页面也不经手账号密码，登录全程在喜马拉雅服务器和你手机之间完成

所以放心扫，扫完把 token 复制走就行；不复制的话关掉页面就没了。

---

## 3. 把账号加进本机金币本

把上一步复制的 **UID** 和 **Token** 填进来（token 记得用英文单引号包住）：

```bash
python3 python/xmly_water.py import-session --uid 你的UID --token '你的Token'
```

它会做三件事：

- 把会话写进 `work/accounts/<你的UID>/session.json`
- 把账号登记进 `accounts.js`
- 立刻查一次余额验证 token 是否有效

看到余额数字就成功了。

### 再加第二个账号

重复第 2、3 步即可（换一个喜马拉雅账号扫）。每个账号一份独立凭据，互不串号。
想切换默认账号：

```bash
python3 python/xmly_water.py accounts      # 看所有账号和状态
python3 python/xmly_water.py use <uid>     # 切默认账号
```

---

## 4. 开始刷金币

### 先看一眼状态

```bash
python3 python/xmly_water.py status
```

会打印：水杯进度、金币余额、ticket 状态、今日已刷额度。

### 正式刷

```bash
# 推荐参数：每次间隔 4 秒（太快会触发风控）
python3 python/xmly_water.py farm --times 200 --interval 4
```

输出长这样：

```
[+] 本地签发 ticket：uid=608255219 (201 字节)
起始余额: 13028   water: [...]
  #  1 ✔ +145   余额 13173  今日已刷 145    恭喜获得145金币
  #  2 ✔ +178   余额 13351  今日已刷 323    恭喜获得178金币
  ...
```

### 更凶的刷法（收益更高）

```bash
python3 python/xmly_water.py mega --times 300 --interval 4
```

`mega` 会轮流打四种金矿（单次收益从高到低）：

| 类型 | 说明 | 单次约 |
|---|---|---|
| `rewardType=20` | 喝水翻倍 | **+610** |
| `rewardType=30` | 兑换好礼 | **+500** |
| `rewardType=17` | 喝水 | +100~190 |
| `rewardType=21` | 转盘 | +100 |

---

## 5. 日常维护

```bash
# 今天刷了多少 / 还能刷多少
python3 python/xmly_water.py limit

# 改每日上限（默认 10 万）
python3 python/xmly_water.py limit --set 50000

# 今日额度归零（想重跑时用）
python3 python/xmly_water.py limit --reset

# 本地重新签一条 ticket（一般不用手动做，脚本会自动签）
python3 python/xmly_water.py mint

# 账号出问题（余额查不到 / 报 10030 未登录）→ 回网站重扫一次，再 import-session
```

### 挂后台 / 定时

```bash
nohup python3 python/xmly_water.py mega --times 400 --interval 5 > farm.log 2>&1 &

# 每天 9 点自动刷
crontab -e
# 0 9 * * * cd /你的路径 && python3 python/xmly_water.py mega --times 300 --interval 5 >> farm.log 2>&1
```

---

## 6. 报错对照表

| 返回 | 含义 | 怎么办 |
|---|---|---|
| `200` + 金币 | 成功 | — |
| `10015` / `20001` 您太热情了 | **风控限频** | 停 10~30 分钟，把 `--interval` 调到 5~8 秒 |
| `10003` | ticket 失效 | 脚本会自动重新签；还不行就回网站重扫换 token |
| `10030` 未登录 | 会话 token 过期 | 回网站重扫一次，再 `import-session` |
| `10034` ab实验未命中 | 缺设备段 | 正常不会出现；确认 `accounts.js` 里有 `deviceId` |
| 余额查不到（`None`） | token 失效或网络问题 | 先 `status` 看，再考虑重扫 |

---

## 7. 目录结构

```
.
├── README.md                  ← 你正在看的
├── requirements.txt
├── accounts.js                ← 账号表 + 每日额度（脚本自动读写）
├── python/
│   ├── xmly_water.py          ← 主脚本（farm / mega / status / import-session …）
│   ├── xmly_ticket.py         ← 本地签发 ticket
│   ├── xmly_native.py         ← libnativelib.so 的 CPU 模拟器
│   └── accounts.py            ← 账号表读写
└── work/
    ├── so/libnativelib.so     ← 签 ticket 用的库，别删
    └── accounts/<uid>/
        ├── session.json       ← 你的登录会话
        └── ticket.txt         ← （可选）已缓存的 ticket
```

---

## 8. 一句话原理（好奇的话）

App 领金币时要带一条 `ticket`，它是 App 用 `libnativelib.so` **在本地算出来的一串签名**：

```
ticket = 'T' + os + end + base64( 时间戳 + 设备号 + 随机数 + 签名 + "com.ximalaya.ting.android!1.3.27!9.5.13.3!" + attr )
attr   = "b=incentives&s=gold_reward&u=<uid>"
```

关键在于 `attr` 里的 **uid 是 App 自己填进去的**，服务端只是照单验签、不会核对"这个 uid 是否真的来自这台设备"。
所以只要能把那个签名函数跑起来，就能给任意 uid 现签一条合法 ticket —— 这个脚本干的就是这件事
（用 Unicorn 把 arm64 的 `libnativelib.so` 加载进内存直接调用 `getTicket()`，耗时约 1 秒）。

---

## 免责声明

仅供个人学习、研究自动化接口使用。请自行评估风险，不要用于任何商业用途或大规模滥用。

---

## 仓库版特别说明（慕斯注）

`work/so/libnativelib.so` 是二进制文件，GitHub 推送通道传不了原文，仓库里存的是它的 base64 文本版 `work/so/libnativelib.so.b64`（内容一字不差，md5 001620091e2e68de014363a0b756f262）。拉库后先还原一次：

```bash
base64 -d work/so/libnativelib.so.b64 > work/so/libnativelib.so
```

在 xmly 目录里执行上面这一行就行。还原后其余用法和原包一致。

## 环境变量方式（青龙推荐，慕斯加）

脚本已支持 `XMLY_TOKEN` 环境变量（load_token 里优先级最高，逻辑仿官方的 XMLY_DEVICE）：

- 青龙面板「环境变量」里新建 `XMLY_TOKEN`，值填 token 原值（形如 `608776240&xxxx`，带 `1&_token=` 前缀粘整段也认）
- 再建 `XMLY_DEVICE` 填设备号
- 之后每日任务命令不用再 import-session，直接跑 farm/mega 即可；token 过期时只改环境变量里这一个值
