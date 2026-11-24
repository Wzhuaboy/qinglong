// 当前脚本来自于 http://script.diyunzz.cn/ 脚本库下载！
// 官方青龙脚本群1：712734450
// 官方青龙脚本群2：176166044
// 项目通知群：1009084941
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。


// ============================================================
//  本脚本收录自「青龙脚本库」 https://script.diyunzz.cn
//  官方 QQ 群：712734450  ·  投稿 / 交流 / 问题反馈欢迎进群
// ============================================================
/**
 * 饿了么 会员权益中心（engage-hub）青龙脚本
 * ============================================================
 * 逆向目标：https://tb.ele.me/app/TBTakeout/engage-hub/home
 * 项目：TBTakeout/engage-hub v1.3.5（阿里 ICE + React + mtop 协议）
 *
 * 功能：首页聚合 → 查询任务 → 浏览埋点 → 领取任务 → 领取奖励
 *
 * ── 使用方法（青龙面板）────────────────────────────────────
 * 1. 新增环境变量：
 *    名称  ELM_COOKIE
 *    值    抓包得到的登录态 Cookie（至少含 cookie2/SID，_m_h5_tk 会自动获取）
 *    名称  ELM_LAT  /  ELM_LNG   （可选，默认上海 31.2304 / 121.4737）
 * 2. 添加本脚本为 JS 任务，定时每天执行即可。
 *
 * ── 自动登录（可选，二选一）─────────────────────────────────
 *   ELM_LOGIN = sms    短信登录（移植自"我不饿"插件，默认走 H5 mtop 通道，无需签名服务）
 *     ELM_PHONE       手机号。第一次运行发短信并把会话写入 elm_login_state.json
 *     ELM_SMS_CODE    收到验证码后填入此变量再跑一次，即完成登录
 *     ELM_HAVANA_URL  （如需滑块验证）浏览器打开日志里的 h5Url，验证后
 *                     把跳转链接（含 havana_iv_token）填到这里再跑一次
 *   ELM_LOGIN = yyb    应用宝（YYB-Go）微信登录，使用已有账号池 ref
 *   ELM_LOGIN = yyb_qr 应用宝微信扫码入池后登录（需要 YYB_TOKEN 或服务端 IP 白名单）
 *     ELM_FORCE_LOGIN=1 强制本次忽略已有 cookie，首次扫码时使用；成功后改回 0
 *     YYB_BASE_URL    YYB 服务地址，默认 http://43.136.58.132:8317
 *     YYB_REF         账号池里的 ref（账号 id 或 openid），二选一
 *     YYB_TOKEN       集成令牌；不配 YYB_REF 时用它调 /api/dispatch/account 取号
 *     YYB_QR_IMAGE_FILE 扫码图片保存路径，默认脚本旁 yyb_qrcode.jpg
 *     ELM_WX_APPID    饿了么微信小程序 appid，默认 wxece3a9a4c82f58c9
 *     ELM_SNS_TYPE    snsLogin 的 snsType，默认 weixin
 *   ELM_LOGIN_CHANNEL 登录通道，默认 h5（推荐）；设为 gw 且配了 ELM_XSIGN_API 时
 *                     才走 App /gw/ + x-sign 通道（我不饿原版链路，需要自建签名服务）
 *   ELM_XSIGN_API     x-sign 签名服务地址（仅 gw 通道需要）
 *                     路径含 getXSign 时自动走 POST JSON 格式；可用 ELM_XSIGN_FORMAT=json|query 强制指定
 *   ELM_COOKIE_FILE   登录成功后 cookie 落盘位置，默认脚本旁 elm_cookie.txt
 *                     （之后每次运行会优先读取，无需回填环境变量）
 *
 * ── 如何抓 Cookie ──────────────────────────────────────────
 * 手机浏览器 / Charles / Fiddler 打开上述页面，抓任意一个
 * acs.m.taobao.com 或 acs.ele.me 的请求头，取完整 Cookie 字符串。
 *
 * ── 关于 appKey ────────────────────────────────────────────
 * 饿了么 mtop 通用 appKey 为 12574478（web 端）。若请求返回
 * "FAIL_SYS_TOKEN_EMPTY" 或签名错误，请抓包看请求参数里的
 * appKey 真实值，替换下方 APP_KEY（或用 ELM_APPKEY 环境变量）。
 * ============================================================
 */

const https = require('https');
const http = require('http');
const tls = require('tls');
const crypto = require('crypto');
const { URL } = require('url');

/* ───────────────────── 配置区 ───────────────────── */
// COOKIE 用 let：token 过期时会通过 Set-Cookie 自动刷新更新
let COOKIE = process.env.ELM_COOKIE || '';
const BASE_LAT = parseFloat(process.env.ELM_LAT || '31.2304');
const BASE_LNG = parseFloat(process.env.ELM_LNG || '121.4737');
// 每账号运行时在基准坐标±1.2km 抖动（幸运星.py 同款）：同账号每次请求的
// 经纬度完全一致是典型机器特征；抖动在 runAccount 开头做，函数内仍用 LAT/LNG
let LAT = BASE_LAT;
let LNG = BASE_LNG;

function jitterGeo(km) {
  km = km == null ? 1.2 : km;
  const r = km / 111;
  LAT = +(BASE_LAT + (Math.random() * 2 - 1) * r).toFixed(6);
  LNG = +(BASE_LNG + (Math.random() * 2 - 1) * r / Math.max(0.2, Math.cos(BASE_LAT * Math.PI / 180))).toFixed(6);
}
const APP_KEY = process.env.ELM_APPKEY || '12574478';
// 饿了么 mtop 网关（不是淘宝 acs.m.taobao.com，那是淘系网关，不认 alsc 接口）
const GATEWAY = process.env.ELM_GATEWAY || 'https://waimai-guide.ele.me/h5/';
const PAGE_VERSION = '1.3.5'; // 前端包版本，homepage 入参 version 字段
// App 版本号（aladdin 投放参数 prodVersion 用；新抓包显示 12.8.88）
const APP_VERSION = process.env.ELM_APP_VERSION || '12.8.88';
// 调试开关：设为 "1" 时打印每个任务的原始数据，用于核对埋点字段值
const DEBUG = (process.env.ELM_DEBUG || '0') === '1';
// UA：必须与 ttid(android@eleme_android_xx) 一致——任务页是 App 内 WebView，
// 桌面 Chrome UA 与 ttid 自相矛盾，是网关可识别的异常信号
/* 微信小程序环境设备指纹 —— 幸运星.py 实测 405::行为受限 的唯一开关是 UA：
 * 必须是移动端微信小程序 UA（MiniProgramEnv/android），App WebView UA 必被拦。 */
const DEVICE_MODELS = ['22081212C', 'PHB110', 'V2134A', 'SM-S9080', 'PJZ110', 'LIO-AN00', 'M2011K2C', 'PGT-AN10'];
const DEVICE_VERSIONS = ['13', '12', '14', '11'];
const DEVICE_CHANNELS = ['channel35', 'channel50', 'channel60'];
let DEVICE = null;
let UA = process.env.ELM_UA || '';

function pickRandom(arr) { return arr[Math.floor(Math.random() * arr.length)]; }

function makeDevice() {
  const rid = crypto.randomBytes(8).toString('hex');
  const model = pickRandom(DEVICE_MODELS);
  const ver = pickRandom(DEVICE_VERSIONS);
  const ch = pickRandom(DEVICE_CHANNELS);
  const wxv = process.env.ELM_WECHAT_VERSION || '8.0.58';
  return {
    androidIdRaw: rid,
    clientType: `#11.3.0#${ch}#${model}#`,
    androidVersion: ver,
    model,
    channel: ch,
    wechatVersion: wxv,
    os: process.env.ELM_DEVICE_OS || 'android',
    utdid: ('WX' + crypto.createHash('sha1').update(rid + ch).digest('hex').slice(0, 30)).toUpperCase(),
    ua: `Mozilla/5.0 (Linux; Android ${ver}; ${model} Build/TKQ1.220829.002; wv) ` +
        `AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/107.0.0.0 ` +
        `Mobile Safari/537.36 XWEB/1160 MMWEBSDK/20230805 MicroMessenger/${wxv} ` +
        `WeChat/arm64 Weixin NetType/WIFI Language/zh_CN ABI/arm64 MiniProgramEnv/android`,
  };
}

/* 每账号独占且持久化的设备指纹（跨账号不复用，避开"一机多号"关联）。
 * ELM_RESET_DEVICE=1 重新分配。登录流程写的 {deviceId,utdid,appId} 会被保留合并。 */
function loadDevice(reset) {
  let dev = null;
  try {
    if (!reset && DEVICE_FILE && fs.existsSync(DEVICE_FILE)) {
      const j = JSON.parse(fs.readFileSync(DEVICE_FILE, 'utf8'));
      if (j && j.ua && j.utdid) dev = j;
      else if (j && (j.deviceId || j.utdid)) dev = j; // 登录产出的档案，补齐环境字段
    }
  } catch (e) { /* 损坏则重建 */ }
  if (!dev) dev = {};
  if (!dev.ua) {
    const gen = makeDevice();
    for (const k in gen) if (!dev[k]) dev[k] = gen[k];
  }
  if (!dev.utdid) {
    const seed = dev.androidIdRaw || randomStr(16);
    dev.utdid = ('WX' + crypto.createHash('sha1').update(seed + (dev.channel || 'channel50')).digest('hex').slice(0, 30)).toUpperCase();
  }
  try {
    if (DEVICE_FILE) fs.writeFileSync(DEVICE_FILE, JSON.stringify(dev, null, 2));
  } catch (e) { /* 忽略 */ }
  return dev;
}

/* 拟人节流（毫秒）：单步间隔拉到真人浏览区间，可用环境变量覆盖 */
const PACE = {
  nav: [Number(process.env.ELM_PACE_NAV_MIN || 1200), Number(process.env.ELM_PACE_NAV_MAX || 3500)],      // 页面级跳转
  task: [Number(process.env.ELM_PACE_TASK_MIN || 3000), Number(process.env.ELM_PACE_TASK_MAX || 8000)],   // 任务之间
  click: [Number(process.env.ELM_PACE_CLICK_MIN || 1500), Number(process.env.ELM_PACE_CLICK_MAX || 4500)], // 同一任务多次点击
  claim: [Number(process.env.ELM_PACE_CLAIM_MIN || 4000), Number(process.env.ELM_PACE_CLAIM_MAX || 9000)], // 领奖之间
  round: [Number(process.env.ELM_PACE_ROUND_MIN || 10000), Number(process.env.ELM_PACE_ROUND_MAX || 25000)], // 埋点轮→领奖轮之间（回任务页停留）
};
// 命中奖励风控后的冷却时长（默认 10 分钟，±2 分钟抖动），冷却后只重试一次
const RISK_BACKOFF_MS = Number(process.env.ELM_RISK_BACKOFF_MS || 600000);
const RISK_RETRY = (process.env.ELM_RISK_RETRY || '1') === '1';

/* 出口代理：ELM_PROXY=http://user:pass@host:port
 * 机房 IP 容易被事件/奖励接口打标（405::行为受限 / RISK_USER），
 * 走国内家宽/移动代理可改变 IP 画像输入。仅当显式配置时启用。 */
let PROXY_URL = process.env.ELM_PROXY || '';
let _proxyAuth = null;
let _proxyAgent = null;
function resetProxy() { _proxyAuth = null; _proxyAgent = null; }
function proxyConf() {
  if (!PROXY_URL) return null;
  const pu = new URL(PROXY_URL);
  if (_proxyAuth === null && pu.username) {
    _proxyAuth = 'Basic ' + Buffer.from(
      `${decodeURIComponent(pu.username)}:${decodeURIComponent(pu.password)}`
    ).toString('base64');
  }
  return pu;
}
/* HTTPS over HTTP-CONNECT 隧道的 Agent */
function tunnelAgent() {
  if (_proxyAgent) return _proxyAgent;
  const pu = proxyConf();
  if (!pu) return undefined;
  _proxyAgent = new https.Agent({
    keepAlive: true,
    createConnection(opts, cb) {
      const target = `${opts.host}:${opts.port || 443}`;
      const creq = http.request({
        host: pu.hostname,
        port: Number(pu.port) || 80,
        method: 'CONNECT',
        path: target,
        headers: { Host: target, ...(_proxyAuth ? { 'Proxy-Authorization': _proxyAuth } : {}) },
      });
      creq.on('connect', (res, socket) => {
        if (res.statusCode !== 200) {
          socket.destroy();
          cb(new Error(`代理 CONNECT 失败: HTTP ${res.statusCode}`));
          return;
        }
        cb(null, tls.connect({ socket, servername: opts.host }));
      });
      creq.on('error', cb);
      creq.end();
    },
  });
  return _proxyAgent;
}

/* ──────────────────────────────────────────────
 * aladdin 投放参数（逆向自饿了么 App smali：
 *   me/ele/taobao/flash/sale/d/a/d.smali）
 * 这 5 个参数是 mtop.ele.biz.growth.task.* 接口的
 * 网关级投放校验，App 原生环境自动注入：
 *   platform    = "android"
 *   product     = "eleme"
 *   prodVersion = App 版本号（12.8.8）
 *   ttid        = "android@eleme_android_12.8.8"
 *   locationInfos = [{"lng":x,"lat":y}]
 * ────────────────────────────────────────────── */
const ALADDIN = {
  platform: 'android',
  product: 'eleme',
  prodVersion: APP_VERSION,
  ttid: `android@eleme_android_${APP_VERSION}`,
};

/* 逆向得到的接口常量 */
const API = {
  homepage:  'mtop.alsc.interact.et.interact.center.homepage',
  querytask: 'mtop.ele.biz.growth.task.core.querytask',
  receivetask: 'mtop.ele.biz.growth.task.core.receivetask',
  receiveprize: 'mtop.ele.biz.growth.task.core.receiveprize',
  pageview: 'mtop.ele.biz.growth.task.event.pageview',
  trigger: 'mtop.ele.biz.growth.task.event.trigger',
  // 签到并领取奖励（signInRewardStrategy === "SIGNIN_AND_RECEIVE" 时用）
  signin: 'mtop.alsc.interact.playapp.signin.component.signinandreceive',
  // 独立签到（只签到不领奖，默认模式）
  recordsignin: 'mtop.alsc.interact.playapp.signin.component.recordsignin',
};

/* 逆向得到的风控 asac token（硬编码于前端包/App） */
const ASAC = {
  SIGNIN: 'alsc3Lhy681SA5TT4iHgL3',        // signinandreceive 请求头
  PRIZE:  'alscadOjfleDPawx9zVoT0',        // receiveprize 入参
  PAGEVIEW: 'alscFS8BNTO6jivYS7XOAM',      // 任务浏览埋点
  TRIGGER: '2A21607NIIT1ND5C4YXJ6C',       // 点击店铺/THIRD 任务 trigger 请求头
};

/* 任务 bizScene 常量（逆向 R.s_ = "interact_center"） */
const BIZ_SCENE = 'interact_center';

/* homepage 需要的组件码（cpnCodes），逆向自 Ce 函数 */
const CPN_CODES = [
  'PLAY_NOTICE_CPN',
  'INTERACT_RESOURCE_CPN',
  'MORE_MENU_CPN',
  'STAR_MSG_CONTENT_CPN',
  'PLAY_RESOURCE_CPN',
  'INTERACT_CENTER_SKIN_COMPONENT',
  'INTERACT_CENTER_BUBBLE',
  'INTERACT_CENTER_LOTTERY',
];

/* ───────────────────── 工具函数 ───────────────────── */

function md5(s) {
  return crypto.createHash('md5').update(s, 'utf8').digest('hex');
}

function getToken(cookie) {
  const m = cookie.match(/(?:^|;\s*)(_?m_h5_tk)=([^;]+)/);
  if (!m) return null;
  return m[2].split('_')[0];
}

function ts() {
  return String(Date.now());
}

function log(msg) {
  console.log(`[${new Date().toLocaleString('zh-CN', { hour12: false })}] ${msg}`);
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

function jitter(min, max) {
  return min + Math.floor(Math.random() * (max - min + 1));
}

/* 真人区间随机停顿 */
async function humanPause(range) {
  const ms = jitter(range[0], range[1]);
  if (DEBUG) log(`   [节流] 停留 ${(ms / 1000).toFixed(1)}s`);
  await sleep(ms);
}

/* 从任务对象里递归找真实的任务落地页 URL（tb.ele.me/wow/...），找不到返回 null */
function findTaskPageUrl(obj, depth) {
  if (depth == null) depth = 0;
  if (depth > 6 || obj == null) return null;
  if (typeof obj === 'string') {
    const i = obj.indexOf('tb.ele.me/wow/');
    if (i < 0) return null;
    // 回退到协议头，再截到空白/引号/转义符为止
    const p = Math.max(obj.lastIndexOf('https://', i), obj.lastIndexOf('http://', i));
    const start = p >= 0 ? p : i;
    let end = obj.length;
    for (let j = start; j < obj.length; j++) {
      const c = obj[j];
      if (c === '"' || c === "'" || c === '\\' || c === ' ' || c === '\t' || c === '\n') { end = j; break; }
    }
    return obj.slice(start, end).split('\\/').join('/');
  }
  if (typeof obj === 'object') {
    for (const k in obj) {
      const r = findTaskPageUrl(obj[k], depth + 1);
      if (r) return r;
    }
  }
  return null;
}

/* 构造任务页 Referer：优先用任务数据里的真实落地页；
 * 抓包格式：{pageUrl}?animated_transition=1&missioncollectid=..&missionid=..&bizscene=..&o2i_action=GY_TASK_{mid}&taskpageviewasac=..
 */
function taskReferer(task) {
  if ((process.env.ELM_REFERER || '1') === '0') return null;
  const cid = task.missionCollectionId || task.missionCollectId || '';
  const mid = task.missionId || task.missionDefId || '';
  const pageUrl = findTaskPageUrl(task);
  if (!pageUrl) return null;
  // 只补落地页里还没有的参数，避免重复 key
  const params = {
    animated_transition: '1',
    missioncollectid: cid,
    missionid: mid,
    bizscene: BIZ_SCENE,
    o2i_action: mid ? `GY_TASK_${mid}` : '',
    taskpageviewasac: ASAC.PAGEVIEW,
  };
  let ref = pageUrl;
  for (const k in params) {
    if (!params[k] || ref.includes(`${k}=`)) continue;
    ref += `${ref.includes('?') ? '&' : '?'}${k}=${params[k]}`;
  }
  return ref;
}

/* 任务请求头：base 上叠加真实任务页 Referer */
function taskHeaders(task, base) {
  const h = base || {};
  const ref = taskReferer(task);
  if (ref) {
    h.Referer = ref;
    if (DEBUG) log(`   [调试] Referer: ${ref.slice(0, 140)}`);
  }
  return h;
}

/* mtop 签名：md5(token + '&' + t + '&' + appKey + '&' + data) */
function buildSign(token, t, data) {
  return md5(`${token}&${t}&${APP_KEY}&${data}`);
}

/* 从响应 Set-Cookie 提取回传的 cookie 更新。
 * 不能只抓 _m_h5_tk：网关还会在响应里下发 isg/sgcookie/tfstk 等安全 cookie，
 * 丢掉它们会导致事件类接口（pageview 等）被网关拦 405::行为受限。 */
function extractCookieUpdates(setCookieHeaders) {
  if (!setCookieHeaders) return [];
  const lines = Array.isArray(setCookieHeaders) ? setCookieHeaders : [setCookieHeaders];
  const updates = [];
  for (const line of lines) {
    if (!line) continue;
    const first = line.split(';', 1)[0];
    const eq = first.indexOf('=');
    if (eq <= 0) continue;
    const k = first.slice(0, eq).trim();
    const v = first.slice(eq + 1).trim();
    if (!k) continue;
    updates.push(`${k}=${v}`);
  }
  return updates;
}

/* 用新值更新 COOKIE（按字段名替换旧的同名 cookie） */
function updateCookie(cookie, updates) {
  if (!updates || updates.length === 0) return cookie;
  const names = updates.map((u) => u.split('=', 1)[0]);
  const keep = String(cookie).split(';')
    .map((s) => s.trim())
    .filter((s) => s && !names.includes(s.split('=', 1)[0].trim()));
  return keep.concat(updates).join('; ');
}

/* 发起 mtop 请求（POST + subVersion 5.0，自动捕获 token 刷新 + token 过期重试） */
function mtop(apiName, version, data, extraHeaders) {
  // 单次请求（返回 { ret, body }，供外层判断是否 token 过期）
  function doRequest() {
    return new Promise((resolve, reject) => {
      // token 允许为空：Cookie 没有 _m_h5_tk 时也照发请求，
      // 网关会回 FAIL_SYS_TOKEN_EXOIRED + Set-Cookie 下发新 token，重试即可
      const token = getToken(COOKIE) || '';

      const t = ts();
      const dataStr = JSON.stringify(data);
      const sign = buildSign(token, t, dataStr);

      // 网关地址带 5.0 子版本（参考 elm_v3.js，POST 才会回传 Set-Cookie 刷 token）
      const url = new URL(`${GATEWAY}${apiName}/${version}/5.0/`);
      const query = {
        jsv: '2.7.5',
        appKey: APP_KEY,
        t,
        sign,
        api: apiName,
        v: version,
        type: 'originaljson',
        dataType: 'json',
        data: dataStr,
        // aladdin 投放系统必备公共参数（必须放 query，且用 App 原生环境真实值）
        platform: ALADDIN.platform,
        product: ALADDIN.product,
        prodVersion: ALADDIN.prodVersion,
        ttid: ALADDIN.ttid,
      };
      // locationInfos 也要进 query（aladdin 从 query 读）
      if (data && data.locationInfos !== undefined) {
        query.locationInfos = JSON.stringify([{ lng: LNG, lat: LAT }]);
      }
      for (const k in query) url.searchParams.set(k, query[k]);

      const cks = str2dict(COOKIE);
      const uid = cks.UTUSER || cks.munb || cks.userId || '';
      const headers = {
        'User-Agent': UA,
        'Referer': `https://servicewechat.com/${APP_ID}/831/page-frame.html`,
        'Origin': 'https://servicewechat.com',
        'Cookie': COOKIE,
        'Accept': 'application/json,text/plain,*/*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Content-Type': 'application/x-www-form-urlencoded',
        'x-tap': 'wx',
        'x-eleme-requestid': requestId(),
      };
      // 小程序链路一致性头（同账号稳定，跨账号不复用）
      if (DEVICE) {
        if (DEVICE.utdid) headers['x-utdid'] = DEVICE.utdid;
        headers['x-ele-ua'] = buildXEleUa({
          session: cks, lng: LNG, lat: LAT,
          brand: DEVICE.os === 'android' ? 'Xiaomi' : 'Apple',
          model: DEVICE.model || 'iPhone',
          system: DEVICE.os === 'android' ? `Android ${DEVICE.androidVersion}` : 'iOS 17.0',
          wechatVersion: DEVICE.wechatVersion || '8.0.58',
        });
      }
      if (uid) headers['x-uid'] = uid;
      Object.assign(headers, extraHeaders || {});

      const req = https.request(url.toString(), { method: 'POST', headers, agent: tunnelAgent() }, (res) => {
        let body = '';
        res.setEncoding('utf8');
        res.on('data', (c) => (body += c));
        res.on('end', () => {
          // ★ 关键：捕获 Set-Cookie 回传的最新 token
          const updates = extractCookieUpdates(res.headers['set-cookie']);
          if (updates.length > 0) {
            COOKIE = updateCookie(COOKIE, updates);
          }
          try {
            const json = JSON.parse(body);
            const ret = Array.isArray(json.ret) ? json.ret[0] : '';
            resolve({ ret, body: json, tokenRefreshed: updates.length > 0 });
          } catch (e) {
            reject(new Error(`响应解析失败: ${body.slice(0, 200)}`));
          }
        });
      });
      req.on('error', reject);
      req.setTimeout(15000, () => req.destroy(new Error('请求超时')));
      req.end();
    });
  }

  // 外层：token 过期时自动重试（最多重试 2 次）
  return (async () => {
    for (let attempt = 0; attempt < 3; attempt++) {
      const { ret, body, tokenRefreshed } = await doRequest();
      // 判断是否 token/会话相关错误（SESSION_ERROR 时网关也会回传新 token）
      const tokenError = /TOKEN_EXOIRED|TOKEN_EMPTY|TOKEN_EXPIRED|SESSION_ERROR|SESSION_EXPIRED/i.test(ret || '');
      if (tokenError && tokenRefreshed) {
        // token 已刷新，重试
        continue;
      }
      return body;
    }
    // 重试耗尽，返回最后一次结果
    return (await doRequest()).body;
  })();
}

/* 解析 mtop 返回，ret[0] 形如 "SUCCESS::调用成功" 或 "FAIL_SYS_xxx::..." */
function parseRet(res) {
  if (!res) return { ok: false, msg: '空响应' };
  const ret = Array.isArray(res.ret) ? res.ret[0] : '';
  if (typeof ret === 'string' && ret.startsWith('SUCCESS')) {
    // mtop 返回有两层 data：res.data.data 才是业务数据
    const outer = res.data || {};
    const inner = outer.data !== undefined ? outer.data : outer;
    return { ok: true, msg: ret, data: inner };
  }
  return { ok: false, msg: ret || JSON.stringify(res), data: res.data || {} };
}

/* ───────────────────── 业务函数 ───────────────────── */

/* 1. 签到（根据 signInRewardStrategy 选择接口） */
async function doSignin(copyId, signInRewardStrategy, award) {
  log('▶ 开始签到');
  const data = { bizScene: BIZ_SCENE, latitude: LAT, longitude: LNG };
  if (copyId) data.copyId = copyId;
  // 实测必传：今日奖励的 actCode/sceneCode/prizeMark/signInDay，
  // 缺任意一个会 FAIL_BIZ_REWARD_MODE_NOT_SIGNIN_AND_RECEIVE
  for (const k of ['actCode', 'sceneCode', 'prizeMark', 'signInDay']) {
    if (award && award[k] != null && award[k] !== '') data[k] = award[k];
  }

  // SIGNIN_AND_RECEIVE → signinandreceive；否则 → recordsignin（独立签到），失败互换重试
  const order = signInRewardStrategy === 'SIGNIN_AND_RECEIVE'
    ? [API.signin, API.recordsignin] : [API.recordsignin, API.signin];
  let r = { ok: false, msg: '未执行' };
  for (const api of order) {
    const res = await mtop(api, '1.0', data, { asac: ASAC.SIGNIN });
    r = parseRet(res);
    if (r.ok) {
      log(`   签到模式: ${api === API.signin ? '签到并领奖' : '独立签到'}`);
      break;
    }
    if (/已签到|REPEAT|ALREADY/i.test(String(r.msg))) break;
  }
  if (r.ok) {
    // 提取签到奖励（rewards 数组，含 prizeValue/prizeType）
    const rewards = (r.data && r.data.rewards) || [];
    const totalValue = rewards.reduce((sum, item) => sum + Number(item.prizeValue || 0), 0);
    const prizeType = rewards.length > 0 ? (rewards[0].prizeType === 'STAR' ? '幸运星' : (rewards[0].prizeType || '奖励')) : '奖励';
    log(`✅ 签到成功，获得 ${totalValue} ${prizeType}`);
  } else {
    log(`❌ 签到失败: ${r.msg}`);
  }
  return r;
}

/* 2. 首页聚合：拿到 missionCollectionId + 签到 copyId */
async function getHomepage() {
  log('▶ 获取首页聚合数据');
  const data = {
    bizScene: BIZ_SCENE,
    version: PAGE_VERSION,
    latitude: LAT,
    longitude: LNG,
    cpnCodes: JSON.stringify(CPN_CODES),
  };
  const res = await mtop(API.homepage, '1.0', data);
  const r = parseRet(res);
  if (!r.ok) {
    log(`❌ 首页聚合失败: ${r.msg}`);
    return null;
  }

  const d = r.data || {};

  // 首页每个业务字段都是 { success, data } 两层结构
  // missionCollectionId 路径：resource.data.INTERACT_RESOURCE_CPN[0].missionCollectionId
  const resourceData = (d.resource && d.resource.data) || {};
  const cpns = resourceData.INTERACT_RESOURCE_CPN;
  const first = Array.isArray(cpns) ? cpns[0] : null;
  const missionCollectionId = (first && first.missionCollectionId) || '';

  // 签到 copyId 路径：signIn.data.signInQueryPrizeDTOS 中 today 项的 extInfo.copyId
  const signInData = (d.signIn && d.signIn.data) || {};
  const prizeDTOS = Array.isArray(signInData.signInQueryPrizeDTOS) ? signInData.signInQueryPrizeDTOS : [];
  const todayItem = prizeDTOS.find((it) => it && it.today) || null;
  const copyId =
    (todayItem && todayItem.extInfo && todayItem.extInfo.copyId) ||
    (signInData.extInfo && signInData.extInfo.copyId) ||
    '';

  // 签到模式：signInData.signInRewardStrategy
  const signInRewardStrategy = signInData.signInRewardStrategy || '';

  // 今日奖励参数：recordsignin 必传 actCode/sceneCode/prizeMark/signInDay
  let award = {};
  try {
    let ext = todayItem && todayItem.extInfo;
    if (typeof ext === 'string') ext = JSON.parse(ext);
    const arr = (ext && ext.stageAward) || [];
    award = arr[0] || {};
  } catch (e) { award = {}; }

  if (DEBUG) {
    log('   [调试] 首页 resource 字段:');
    log(`   ${JSON.stringify(d.resource).slice(0, 1200)}`);
    log('   [调试] 首页 signIn 字段:');
    log(`   ${JSON.stringify(d.signIn).slice(0, 1200)}`);
  }

  if (missionCollectionId) {
    log('✅ 首页聚合成功');
  } else {
    log('⚠ 首页聚合成功，但未找到 missionCollectionId');
    log(`   业务字段: ${Object.keys(d).join(', ')}`);
  }
  return { missionCollectionId, copyId, signInRewardStrategy, award, raw: d };
}

/* 2. 查询任务列表（需先拿到 missionCollectionId） */
async function queryTasks(missionCollectionId) {
  log('▶ 查询任务列表');
  const loc = JSON.stringify({ lng: LNG, lat: LAT });
  const data = {
    bizScene: BIZ_SCENE,
    accountPlan: 'HAVANA_COMMON',
    longitude: LNG,
    latitude: LAT,
    locationInfos: JSON.stringify([loc]),
    missionCollectionId,
    launchChannels: JSON.stringify([]),
  };
  const res = await mtop(API.querytask, '1.0', data);
  const r = parseRet(res);
  if (!r.ok) {
    log(`❌ 查询任务失败: ${r.msg}`);
    return [];
  }
  // 任务数据在 data.mlist（真实返回字段）
  const d = r.data || {};
  const list = d.mlist;
  if (Array.isArray(list)) {
    log(`   找到 ${list.length} 个任务`);
  } else {
    log('   未找到 mlist，顶层字段：' + Object.keys(d).join(', '));
  }
  return list || [];
}

/* 3. 领取任务（把任务标记为进行中/接取） */
async function receiveTask(task) {
  const data = {
    bizScene: BIZ_SCENE,
    accountPlan: 'HAVANA_COMMON',
    longitude: LNG,
    latitude: LAT,
    locationInfos: JSON.stringify([JSON.stringify({ lng: LNG, lat: LAT })]),
    missionCollectionId: task.missionCollectionId || task.missionCollectId,
    missionId: task.missionId || task.missionDefId,
  };
  const res = await mtop(API.receivetask, '1.0', data);
  return parseRet(res);
}

/* 计算领奖阶段索引（逆向 gv 函数：找第一个 status=FINISH 且 rewardStatus!==SUCCESS 的阶段） */
function rewardStageIndex(task) {
  const stages = task.missionStageDTOS || [];
  for (let i = 0; i < stages.length; i++) {
    const st = stages[i] || {};
    const sa = st.sourceAction || {};
    // y(i): status===FINISH && rewardStatus!==SUCCESS && 非自动发奖
    if (st.status === 'FINISH' && st.rewardStatus !== 'SUCCESS' &&
        sa.actionSubtype !== 'NO_REWARD' && sa.actionSubSubType !== 'REWARD_SEND_AUTO' && sa.actionSubSubType !== 'NOTIFY_REACH_STAGE') {
      return i;
    }
  }
  return -1;
}

/* 从领奖响应里提取干净的奖励摘要（避免打印手机号等敏感信息） */
function prizeSummary(data) {
  const rlist = (data && data.rlist) || [];
  if (rlist.length === 0) return '';
  // 汇总每项奖励：优先用 materialInfo.title（如"60幸运星"）
  const parts = rlist.map((item) => {
    const title = (item && item.materialInfo && item.materialInfo.title) || (item && item.name) || '奖励';
    const value = (item && item.value) || '';
    // 如果 title 已含数量（如"60幸运星"），直接用；否则补 value
    return /\d/.test(title) ? title : `${title}${value ? ' +' + value : ''}`;
  });
  return parts.join('、');
}

/* 4. 领取任务奖励 */
let rewardBlocked = false;
async function receivePrize(task) {
  if (rewardBlocked) {
    return { ok: false, msg: '奖励接口返回 RISK_USER，已停止重复请求', skip: true };
  }
  // 先找可领奖阶段，没有则直接跳过（避免发缺 count 的无效请求）
  const idx = rewardStageIndex(task);
  if (idx < 0) {
    return { ok: false, msg: '无可领奖阶段（已领完或未完成），跳过', skip: true };
  }

  const data = {
    bizScene: BIZ_SCENE,
    accountPlan: 'HAVANA_COMMON',
    longitude: LNG,
    latitude: LAT,
    locationInfos: JSON.stringify([JSON.stringify({ lng: LNG, lat: LAT })]),
    missionCollectionId: task.missionCollectionId || task.missionCollectId,
    missionId: task.missionId || task.missionDefId,
    asac: ASAC.PRIZE,
  };
  if (task.instanceId) data.instanceId = task.instanceId;
  // 阶段奖励字段：取当前可领奖阶段
  const st = task.missionStageDTOS[idx] || {};
  if (st.stageCount != null) data.count = st.stageCount;
  if (st.stageSum != null) data.sum = st.stageSum;

  const res = await mtop(API.receiveprize, '1.0', data, taskHeaders(task));
  if (DEBUG) log(`   [调试] 领奖响应: ${JSON.stringify(res).slice(0, 1200)}`);
  const parsed = parseRet(res);
  const raw = JSON.stringify(res);
  if (/RISK_USER|风控用户|NO_DECISION_ITEM/i.test(raw)) {
    rewardBlocked = true;
    return { ok: false, msg: '奖励发放被风控拦截（RISK_USER），停止本轮领奖', skip: true, risk: true };
  }
  return parsed;
}

/* 一轮领奖：逐个任务尝试领取，命中风控则提前退出（由 rewardBlocked 标记） */
async function claimPass(tasks) {
  for (const task of tasks) {
    if (rewardBlocked) {
      log('   ⏭ 已命中奖励风控，本轮剩余任务跳过');
      break;
    }
    const title = taskTitle(task);
    const btn = taskButton(task);
    log(`\n── 任务: ${title}${btn ? ' [' + btn + ']' : ''} ──`);

    // 调试模式：打印任务原始数据
    if (DEBUG) {
      log(`   [调试] 任务原始数据:`);
      log(`   ${JSON.stringify(task)}`);
    }

    // 尝试领取奖励（只对已完成/阶段完成的任务有效，未完成会报错无害）
    try {
      const rp = await receivePrize(task);
      if (rp.ok) {
        const summary = prizeSummary(rp.data);
        log(`   🎁 领奖成功${summary ? '：' + summary : ''}`);
      } else if (rp.skip) {
        log(`   ⏭ ${rp.msg}`);
      } else {
        log(`   ⚠ 领奖: ${rp.msg}`);
      }
    } catch (e) {
      log(`   ⚠ 领奖异常: ${e.message}`);
    }

    await humanPause(PACE.claim);
  }
}

/* 5. 浏览任务埋点上报（把浏览型任务推进到可领取态） */
async function reportPageview(task) {
  const cfg = task.actionConfig || {};
  const av = cfg.actionValue || {};
  // 只有带 pageSpm 的浏览型任务才需要上报
  const pageFrom = av.pageSpm;
  if (!pageFrom) return { ok: false, msg: '非浏览型任务（无 pageSpm），跳过埋点' };

  const data = {
    bizScene: BIZ_SCENE,
    accountPlan: 'HAVANA_COMMON',
    longitude: LNG,
    latitude: LAT,
    locationInfos: JSON.stringify([JSON.stringify({ lng: LNG, lat: LAT })]),
    // pageview 接口字段名与其他接口不同，为小写
    collectionId: task.missionCollectionId || task.missionCollectId,
    missionId: task.missionId || task.missionDefId,
    pageFrom,
    actionCode: cfg.actionType,
    // 停留时长：下发值±随机抖动（服务端校验停留时长，固定值是典型机器特征）
    viewTime: (() => {
      const base = parseInt(av.pageStageTime, 10);
      return Number.isFinite(base) ? Math.max(3, base) + Math.floor(Math.random() * 8) - 2
                                   : 8 + Math.floor(Math.random() * 9);
    })(),
  };
  if (task.instanceId) data.instanceId = task.instanceId;

  // 注意：pageview 实际调用版本为 1.1
  const res = await mtop(API.pageview, '1.1', data, taskHeaders(task, { asac: ASAC.PAGEVIEW }));
  return parseRet(res);
}

/* 判断任务是否为浏览型（actionType === PAGEVIEW 且有 pageSpm） */
function isPageviewTask(task) {
  const cfg = task.actionConfig || {};
  const av = cfg.actionValue || {};
  return cfg.actionType === 'PAGEVIEW' && !!av.pageSpm;
}

/* 6. THIRD 任务埋点（点击店铺 commercial_click / 跳转第三方 inter_change 都可用） */
async function reportTrigger(task) {
  const now = Date.now();
  const data = {
    latitude: LAT,
    longitude: LNG,
    riskScene: 'duobao_external',   // 关键：所有 THIRD 任务都用这个值（inter_change 用别的会 405）
    bizScene: String(task.missionDefId),
    eventType: 'THIRD',
    eventSubType: 'EVENT_FINISH',
    eventId: now,
    eventIdemPotent: now,
    eventTime: now,
    triggerType: 'SYNC',
    collectionId: String(task.missionCollectionId),
    missionId: String(task.missionDefId),
    missionXId: task.missionXId || '',
  };

  // asac 是 header（逆向自 me/ele/shopdetailv2/header/widget/navigator/i.smali）
  const res = await mtop(API.trigger, '1.1', data, taskHeaders(task, { asac: ASAC.TRIGGER }));
  return parseRet(res);
}

/* 判断任务是否为可本地触发的 THIRD 类型（commercial_click + inter_change 都支持） */
function isTriggerTask(task) {
  const cfg = task.actionConfig || {};
  const av = cfg.actionValue || {};
  return cfg.actionType === 'THIRD' && (av.scenceCode === 'commercial_click' || av.scenceCode === 'inter_change');
}

/* 提取任务的展示标题（真实字段：ext.extValue.pinnedTaskTitle.value 或 missionName） */
function taskTitle(task) {
  const ev = (task.ext && task.ext.extValue) || {};
  const pinned = ev.pinnedTaskTitle;
  if (pinned && pinned.value) return pinned.value;
  return task.missionName || task.showTitle || task.taskName || (task.missionDefId || '未知任务');
}

/* 提取任务的按钮文案（buttonTitle，用于日志） */
function taskButton(task) {
  const ev = (task.ext && task.ext.extValue) || {};
  return ev.buttonTitle || ev.missionRewardButton || '';
}

/* ───────────────── 登录模块（短信 / YYB应用宝） ─────────────────
 * 移植自 chuan我不饿.py 的 ELM 类：
 *   通道：appRequest → https://{host}/gw/{api}/1.0/（x-sign 签名服务）
 *   登录产物：cookie2(=sid) / SID / USERID / token(autoLoginToken)
 *   写进 elm_cookie.txt，之后运行自动读取。
 */

const fs = require('fs');
const path = require('path');

const LOGIN_METHOD = (process.env.ELM_LOGIN || '').toLowerCase();   // sms | yyb | yyb_qr
const FORCE_LOGIN = process.env.ELM_FORCE_LOGIN === '1';
const ELM_PHONE = process.env.ELM_PHONE || '';
const ELM_SMS_CODE = process.env.ELM_SMS_CODE || '';
const ELM_HAVANA_URL = process.env.ELM_HAVANA_URL || '';
const XSIGN_API = process.env.ELM_XSIGN_API || 'http://www.aijiaoer.cn:9707/api/sign';
const YYB_BASE = (process.env.YYB_BASE_URL || 'http://43.136.58.132:8317').replace(/\/+$/, '');
const YYB_TOKEN = process.env.YYB_TOKEN || '';
const YYB_REF = process.env.YYB_REF || '';
const YYB_QR = LOGIN_METHOD === 'yyb_qr' || process.env.YYB_QR === '1';
const YYB_QR_IMAGE_FILE = process.env.YYB_QR_IMAGE_FILE || path.join(__dirname, 'yyb_qrcode.jpg');
const WX_APPID = process.env.ELM_WX_APPID || 'wxece3a9a4c82f58c9'; // 饿了么微信小程序
const SNS_TYPE = process.env.ELM_SNS_TYPE || 'weixin';
let COOKIE_FILE = process.env.ELM_COOKIE_FILE || path.join(__dirname, 'elm_cookie.txt');
let DEVICE_FILE = process.env.ELM_DEVICE_FILE || path.join(__dirname, 'elm_device_profile.json');
const STATE_FILE = path.join(__dirname, 'elm_login_state.json');

const APP_UA = 'MTOPSDK/3.1.1.7 (Android;13;Google;Pixel 4 XL)';
const APP_TTID = `1601274955355@eleme_android_${APP_VERSION}`;
const APP_XKEY = '24895413';
const UMT = 'B2YBzG5LPGzbWBKLrS3gOkXNn2hdsnLq'; // 我不饿同款默认 umt

function randomStr(n) {
  const c = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  let s = '';
  for (let i = 0; i < n; i++) s += c[Math.floor(Math.random() * c.length)];
  return s;
}

function dict2str(o) {
  return Object.keys(o)
    .filter((k) => o[k] !== undefined && o[k] !== null && o[k] !== '')
    .map((k) => `${k}=${o[k]}`)
    .join(';');
}

function str2dict(s) {
  const o = {};
  for (const kv of String(s || '').split(';')) {
    const i = kv.indexOf('=');
    if (i > 0) o[kv.slice(0, i).trim()] = kv.slice(i + 1).trim();
  }
  return o;
}

/* 在嵌套 JSON 里找第一个同名 key（对应 python find_key_value） */
function findKey(obj, key) {
  if (obj && typeof obj === 'object') {
    if (Object.prototype.hasOwnProperty.call(obj, key)) return obj[key];
    for (const k of Object.keys(obj)) {
      const v = findKey(obj[k], key);
      if (v !== undefined) return v;
    }
  }
  return undefined;
}

/* 通用 http/https 请求，返回 {status, headers, body} */
function httpReq(urlStr, opts) {
  opts = opts || {};
  const method = opts.method || 'POST';
  const headers = opts.headers || {};
  const params = opts.params;
  const body = opts.body;
  return new Promise((resolve, reject) => {
    const url = new URL(urlStr);
    if (params) {
      for (const k in params) {
        if (params[k] !== undefined && params[k] !== null) url.searchParams.set(k, params[k]);
      }
    }
    const isHttps = url.protocol !== 'http:';
    const lib = isHttps ? https : http;
    if (body != null && !Object.keys(headers).some((k) => k.toLowerCase() === 'content-length')) {
      headers['Content-Length'] = Buffer.byteLength(body);
    }
    // 配置了 ELM_PROXY 时：https 走 CONNECT 隧道；http 走绝对 URI 转发
    let req;
    const pu = proxyConf();
    if (pu && isHttps) {
      req = lib.request(url.toString(), { method, headers, agent: tunnelAgent() }, handle);
    } else if (pu && !isHttps) {
      if (_proxyAuth) headers['Proxy-Authorization'] = _proxyAuth;
      req = lib.request({
        host: pu.hostname, port: Number(pu.port) || 80, method,
        path: url.toString(), headers,
      }, handle);
    } else {
      req = lib.request(url.toString(), { method, headers }, handle);
    }
    function handle(res) {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () =>
        resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString('utf8') })
      );
    }
    req.on('error', reject);
    req.setTimeout(25000, () => req.destroy(new Error('请求超时')));
    if (body != null) req.write(body);
    req.end();
  });
}

/* 登录会话状态（对应 python ELM 实例字段） */
function newLoginState() {
  const st = {
    cookie: { umt: UMT },
    appId: randomStr(56),
    smsSid: null,
    token: null,
    h5Url: null,
    phone: null,
  };
  st.cookie.utdid = randomStr(24);
  st.cookie.deviceId = randomStr(64);
  return st;
}

/* H5 mtop 通道登录请求：md5(_m_h5_tk & t & appKey & data)，不需要 x-sign。
 * 首次无 token 也照发，网关回 TOKEN_EXOIRED + Set-Cookie 下发 _m_h5_tk 后重试。 */
async function h5LoginReq(st, api, data, version) {
  version = version || '1.0';
  let lastJson = null;
  for (let attempt = 0; attempt < 3; attempt++) {
    const t = String(Date.now());
    const token = (str2dict(dict2str(st.cookie))._m_h5_tk || '').split('_')[0];
    const dataStr = JSON.stringify(data);
    const sign = md5(`${token}&${t}&${APP_KEY}&${dataStr}`);
    const url = new URL(`${GATEWAY}${api}/${version}/`);
    const query = {
      jsv: '2.7.5', appKey: APP_KEY, t, sign, api, v: version,
      type: 'originaljson', dataType: 'json',
    };
    for (const k in query) url.searchParams.set(k, query[k]);
    const res = await httpReq(url.toString(), {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36',
        'Referer': 'https://h5.ele.me/',
        'Origin': 'https://h5.ele.me',
        'Cookie': dict2str(st.cookie),
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: `data=${encodeURIComponent(dataStr)}`,
    });
    // 把 Set-Cookie 全部并进登录会话 cookie（含 _m_h5_tk）
    const setCookies = res.headers['set-cookie'];
    for (const line of setCookies ? [].concat(setCookies) : []) {
      const pair = line.split(';')[0];
      const i = pair.indexOf('=');
      if (i > 0) st.cookie[pair.slice(0, i).trim()] = pair.slice(i + 1).trim();
    }
    lastJson = JSON.parse(res.body);
    const ret = Array.isArray(lastJson.ret) ? lastJson.ret[0] : '';
    if (/TOKEN_EXOIRED|TOKEN_EMPTY|TOKEN_EXPIRED/i.test(ret)) continue;
    return lastJson;
  }
  return lastJson;
}

/* 登录请求入口：默认 h5 通道；配了 ELM_XSIGN_API 且 ELM_LOGIN_CHANNEL=gw 时走 /gw/ + x-sign */
async function loginRequest(st, api, data, gwHost) {
  const useGw = (process.env.ELM_LOGIN_CHANNEL || 'h5').toLowerCase() === 'gw' && process.env.ELM_XSIGN_API;
  if (useGw) {
    const resp = await appRequest(st, gwHost || 'waimai-guide.ele.me', api, data);
    return JSON.parse(resp);
  }
  return h5LoginReq(st, api, data);
}

function saveState(st) {
  try { fs.writeFileSync(STATE_FILE, JSON.stringify(st)); } catch (e) { /* 忽略 */ }
}
function loadState() {
  try {
    const st = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
    if (st && st.cookie) return st;
  } catch (e) { /* 无状态 */ }
  return null;
}
function clearState() {
  try { fs.unlinkSync(STATE_FILE); } catch (e) { /* 忽略 */ }
}

/* x-sign 签名服务（我不饿同款协议；兼容两种接口格式）
 *   - aijiaoer 格式：POST {XSIGN_API}?sign=..&data=..&api=..&...
 *   - getXSign 格式：POST {XSIGN_API}  body={data,api,pageId,uid,sid,deviceId,utdid,wua,ttid,v} (JSON)
 * 路径含 getXSign 时自动走 JSON 格式，也可用 ELM_XSIGN_FORMAT=json|query 强制指定 */
async function getXsign(st, data, api, pageId) {
  pageId = pageId || '';
  const c = st.cookie;
  if (!c.deviceId) c.deviceId = randomStr(64);
  if (!c.utdid) c.utdid = randomStr(24);
  if (c.unb === undefined) c.unb = '';
  const cookie2 = c.cookie2 || '';
  const unb = c.unb || '';

  const fmt = (process.env.ELM_XSIGN_FORMAT || (/getxsign/i.test(XSIGN_API) ? 'json' : 'query')).toLowerCase();
  let res;
  if (fmt === 'json') {
    res = await httpReq(XSIGN_API, {
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({
        data, api, pageId,
        uid: unb, sid: cookie2,
        deviceId: c.deviceId, utdid: c.utdid,
        wua: 'False', ttid: APP_TTID, v: '1.0',
      }),
    });
  } else {
    const sign = md5(`${cookie2}@${unb}#${data}$${api}%${c.deviceId}&${c.utdid}*${pageId}`);
    const qs = new URLSearchParams({
      sign, data, api, pageId,
      sid: cookie2, uid: unb,
      deviceId: c.deviceId, utdid: c.utdid,
      realSID: c.SID || '',
    }).toString();
    res = await httpReq(`${XSIGN_API}?${qs}`, {
      headers: { 'content-type': 'x-www-form-urlencoded' },
    });
  }
  const j = JSON.parse(res.body);
  if (j.status === 400) throw new Error('x-sign 签名服务返回 400');
  if (!j['x-sign']) throw new Error(`x-sign 响应缺少签名: ${res.body.slice(0, 200)}`);
  return j;
}

/* APP 通道请求：POST https://{host}/gw/{api}/1.0/?data=..&wua=..  body=data */
async function appRequest(st, host, api, data) {
  if (typeof data !== 'string') data = JSON.stringify(data);
  const xs = await getXsign(st, data, api);
  const res = await httpReq(`https://${host}/gw/${api}/1.0/`, {
    params: { data, wua: xs['wua'] },
    headers: {
      'x-sgext': encodeURIComponent(xs['x-sgext'] || ''),
      'x-sign': encodeURIComponent(xs['x-sign'] || ''),
      'x-devid': st.cookie.deviceId,
      'x-pv': '6.3',
      'x-features': '1051',
      'x-mini-wua': encodeURIComponent(xs['x-mini-wua'] || ''),
      'content-type': 'application/x-www-form-urlencoded;charset=UTF-8',
      'x-t': xs['x-t'],
      'x-bx-version': '6.6.231206',
      'x-extdata': 'openappkey%3DDEFAULT_AUTH',
      'x-ttid': APP_TTID,
      'x-app-ver': APP_VERSION,
      'x-umt': encodeURIComponent(xs['x-umt'] || ''),
      'x-utdid': encodeURIComponent(st.cookie.utdid),
      'x-appkey': APP_XKEY,
      'x-sid': st.cookie.cookie2 || '',
      'x-uid': st.cookie.unb || '',
      'Cookie': dict2str(st.cookie),
      'User-Agent': APP_UA,
    },
    body: data,
  });
  if (res.status !== 200) throw new Error(`网关 HTTP ${res.status}`);
  return res.body;
}

const EXT_A_FROM = '{"event":"clearAutoLoginInfo"}{"eventName":"autoLoginToken=null|trySdkLogin"}{"event":"clearAutoLoginInfo"}{"eventName":"USER_LOGOUT"}{"eventName":"autoLoginToken=null|trySdkLogin"}{"eventName":"autoLoginToken=null|trySdkLogin"}{"eventName":"autoLoginToken=null|trySdkLogin"}';

function buildExt(st, scene, deviceName) {
  return JSON.stringify({
    apiReferer: EXT_A_FROM,
    apiVersion: '2.0',
    deviceName: deviceName || 'PDRM00',
    sdkTraceId: `${scene}_${st.cookie.utdid}_${Math.floor(Date.now() / 1000)}_PagePhoneLogin`,
    showReigsterPolicy: 'true',
  });
}

function buildLoginInfoBase(st, t) {
  return {
    appName: APP_XKEY,
    appVersion: `android_${APP_VERSION}`,
    biometricState: 'available',
    deviceId: st.cookie.deviceId,
    deviceName: 'Android(AOSP on blueline)',
    ext: { aFrom: EXT_A_FROM, firstLogin: false, huaweiLogin: false, pad: false },
    locale: 'zh_CN',
    pwdEncrypted: false,
    sdkVersion: `android_${APP_VERSION}`,
    site: 25,
    supportBiometricType: 'fingerprint',
    t,
    ttid: APP_TTID,
    useAcitonType: false,
    useDeviceToken: false,
    utdid: st.cookie.utdid,
  };
}

function buildRiskControl(st, t) {
  return JSON.stringify({
    apdId: st.appId,
    appStore: APP_TTID,
    deviceBrand: 'Google',
    deviceModel: 'AOSP on blueline',
    deviceName: 'AOSP on blueline',
    osName: 'android',
    osVersion: '13',
    screenSize: '0x0',
    t: String(t),
    umidToken: st.cookie.umt,
    wua: '',
  });
}

/* 登录成功公共处理：returnValue.data → cookie2/SID/USERID/token */
function applyLoginReturn(st, res) {
  const data = JSON.parse(res.data.returnValue.data);
  st.cookie['token'] = data.autoLoginToken;
  st.cookie['cookie2'] = data.sid;
  const eleExt = JSON.parse(data.loginServiceExt.eleExt);
  const eleNames = [];
  for (const it of eleExt) {
    if (it.name && it.value !== undefined) {
      st.cookie[it.name] = it.value;
      eleNames.push(it.name);
    }
  }
  log('   eleExt 字段: ' + eleNames.join(', '));
}

/* 第一步：发短信验证码 */
async function smsSend(st, phone) {
  const st10 = Math.floor(Date.now() / 1000);
  const t = st10 * 1000;
  const loginInfo = buildLoginInfoBase(st, t);
  loginInfo.codeLength = '4';
  loginInfo.countryCode = 'CN';
  loginInfo.loginId = String(phone);
  loginInfo.loginType = 'taobao';
  loginInfo.phoneCode = '+86';
  const data = {
    ext: buildExt(st, 'smsLogin'),
    loginInfo: JSON.stringify(loginInfo),
    riskControlInfo: buildRiskControl(st, t + 1),
  };
  const res = await loginRequest(st, 'mtop.alsc.mloginService.smssend', data);
  st.smsSid = findKey(res, 'smsSid') || null;
  if (!st.smsSid) {
    const ret = findKey(res, 'ret');
    const msg = findKey(res, 'message');
    throw new Error(`短信发送失败: ${(Array.isArray(ret) ? ret[0] : ret) || msg || JSON.stringify(res).slice(0, 300)}`);
  }
  return true;
}

/* 第二步：验证码登录。返回 true / '需要验证' / 错误消息 */
async function smsLogin(st, phone, code) {
  const t = Date.now();
  const loginInfo = buildLoginInfoBase(st, t);
  loginInfo.countryCode = 'CN';
  loginInfo.loginId = String(phone);
  loginInfo.loginType = 'taobao';
  loginInfo.phoneCode = '+86';
  loginInfo.smsCode = String(code);
  loginInfo.smsSid = st.smsSid;
  const data = {
    ext: buildExt(st, 'smsLogin', 'Android(AOSP on blueline)'),
    loginInfo: JSON.stringify(loginInfo),
    riskControlInfo: buildRiskControl(st, t),
  };
  const res = await loginRequest(st, 'mtop.alsc.mloginService.smslogin', data);
  const code2 = findKey(res, 'code');
  if (String(code2) === '13060') {
    st.token = findKey(res, 'token');
    st.h5Url = findKey(res, 'h5Url');
    return '需要验证';
  }
  if (String(code2) === '3000') {
    applyLoginReturn(st, res);
    return true;
  }
  return findKey(res, 'message') || `登录失败: ${JSON.stringify(res).slice(0, 300)}`;
}

/* 第三步（可选）：滑块验证后用 havana_iv_token 完成登录 */
async function mloginTokenLogin(st, havanaToken) {
  const st10 = Math.floor(Date.now() / 1000);
  const t = st10 * 1000;
  const data = {
    ext: JSON.stringify({
      aliusersdk_h5querystring: `havana_iv_token=${havanaToken}&action=continueLogin`,
      apiVersion: '2.0',
      deviceName: 'PDRM00',
      sdkTraceId: `smsLogin_${st.cookie.utdid}_${st10}_PagePhoneLogin`,
    }),
    tokenInfo: JSON.stringify({
      appName: APP_XKEY,
      appVersion: `android_${APP_VERSION}`,
      biometricState: 'available',
      deviceId: st.cookie.deviceId,
      deviceName: 'OPPO(PDRM00)',
      ext: { aFrom: EXT_A_FROM, firstLogin: false, huaweiLogin: false, pad: false },
      scene: '1015',
      sdkVersion: `android_${APP_VERSION}`,
      site: 25,
      supportBiometricType: 'fingerprint',
      t: 0,
      token: st.token,
      tokenType: 'mloginToken',
      ttid: APP_TTID,
      useAcitonType: true,
      useDeviceToken: true,
      utdid: st.cookie.utdid,
    }),
    riskControlInfo: buildRiskControl(st, t),
  };
  const res = await loginRequest(st, 'mtop.alsc.mloginservice.mlogintokenlogin', data, 'acs.m.goofish.com');
  if (String(findKey(res, 'code')) === '3000') {
    applyLoginReturn(st, res);
    return true;
  }
  return findKey(res, 'message') || `验证登录失败: ${JSON.stringify(res).slice(0, 300)}`;
}

/* YYB：客户微信扫码入池，返回可调度的 ref */
async function yybQrEnroll() {
  const authHeaders = YYB_TOKEN ? { Authorization: `Bearer ${YYB_TOKEN}` } : {};
  const create = await httpReq(`${YYB_BASE}/wx/qrcodeauth?as_base64=true`, {
    method: 'POST',
    headers: { ...authHeaders, 'content-type': 'application/json' },
    body: '{}',
  });
  const cj = JSON.parse(create.body);
  const d = cj && cj.data;
  if (!d || !d.session_id) throw new Error(`YYB 创建扫码会话失败: ${create.body.slice(0, 300)}`);

  const imageUrl = d.image_url ? `${YYB_BASE}${d.image_url.startsWith('/') ? '' : '/'}${d.image_url}` : '';
  if (d.image_base64) {
    try {
      const m = String(d.image_base64).match(/^data:image\/([^;]+);base64,(.+)$/s);
      const raw = m ? m[2] : d.image_base64;
      fs.writeFileSync(YYB_QR_IMAGE_FILE, Buffer.from(raw, 'base64'));
      log(`✅ YYB 微信二维码已保存: ${YYB_QR_IMAGE_FILE}`);
    } catch (e) {
      log(`⚠ YYB 二维码保存失败: ${e.message}`);
    }
  }
  if (imageUrl) log(`   二维码地址（可在浏览器打开）: ${imageUrl}`);
  log('   请用微信扫描 YYB 二维码，并在微信中确认授权');

  const deadline = Date.now() + 160000;
  let lastStatus = '';
  while (Date.now() < deadline) {
    const poll = await httpReq(`${YYB_BASE}/wx/qrcodeauth/${encodeURIComponent(d.session_id)}/poll`, {
      method: 'GET', headers: { ...authHeaders, accept: 'application/json' },
    });
    const pj = JSON.parse(poll.body);
    const pd = (pj && pj.data) || pj || {};
    const status = String(pd.status || pj.status || '').toLowerCase();
    if (status && status !== lastStatus) {
      log(`   YYB 扫码状态: ${status}`);
      lastStatus = status;
    }
    if (status === 'authorized') {
      const confirmed = await httpReq(`${YYB_BASE}/wx/qrcodeauth/${encodeURIComponent(d.session_id)}/confirm`, {
        method: 'POST', headers: { ...authHeaders, 'content-type': 'application/json' }, body: '{}',
      });
      const cj2 = JSON.parse(confirmed.body);
      const ad = (cj2 && cj2.data) || cj2 || {};
      const account = ad.account || ad;
      const ref = account.id != null ? String(account.id) : String(account.openid || account.ref || '');
      if (!ref) throw new Error(`YYB 确认成功但未返回 ref: ${confirmed.body.slice(0, 300)}`);
      log(`✅ YYB 微信已入池，获得 ref=${ref}`);
      return ref;
    }
    if (status === 'expired' || status === 'cancelled' || status === 'canceled') {
      throw new Error(`YYB 二维码已${status === 'expired' ? '过期' : '取消'}，请重新运行`);
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error('YYB 二维码等待超时，请重新运行');
}

/* YYB：取小程序 wx.login code */
async function yybGetCode(refOverride) {
  let ref = refOverride || YYB_REF;
  if (!ref) {
    if (!YYB_TOKEN) throw new Error('需配置 YYB_REF（账号 id/openid）或 YYB_TOKEN（集成令牌，用于取号）');
    const r = await httpReq(`${YYB_BASE}/api/dispatch/account?permission=getCode`, {
      method: 'GET',
      headers: { Authorization: `Bearer ${YYB_TOKEN}` },
    });
    const j = JSON.parse(r.body);
    const acc = j && j.data && j.data.account;
    if (!acc) throw new Error(`YYB 取号失败: ${r.body.slice(0, 200)}`);
    ref = String(acc.id || acc.openid);
    log(`   YYB 分配到账号: ${acc.nickname || ref} (ref=${ref})`);
  }
  const r = await httpReq(`${YYB_BASE}/wxapp/getCode`, {
    headers: {
      ...(YYB_TOKEN ? { Authorization: `Bearer ${YYB_TOKEN}` } : {}),
      'content-type': 'application/json',
    },
    body: JSON.stringify({ ref, app_id: WX_APPID }),
  });
  const j = JSON.parse(r.body);
  const wxcode =
    (j.data && (j.data.code || (j.data.data && j.data.data.code) ||
      (j.data.result && (j.data.result.code || j.data.result.wxCode)))) ||
    j.code ||
    (j.Data && j.Data.code);
  const errMsg = (j.data && (j.data.errMsg ||
    (j.data.result && j.data.result.errMsg))) ||
    j.errMsg || j.message || j.Message || j.msg || '';
  if (!wxcode || (errMsg && !/login:ok/i.test(errMsg) && String(j.code) !== '0')) {
    throw new Error(`YYB getCode 失败: ${r.body.slice(0, 300)}`);
  }
  return wxcode;
}

/* YYB：wx.login code → mtop snsLogin 换登录态 */

/* ───────────────── ipassport 小程序登录（code → Cookie） ─────────────────
 * 移植自 eLeMeCodeDengLu_cli.js（sillyGirl 饿了么Code登录插件剥离版）
 * 链路：wx.login code → POST ipassport.ele.me/mini_program/login.do → 登录态
 * 风控头 bx-ua / mini-janus 为纯本地算法实现，bx-umidtoken 联网申领。
 * ─────────────────────────────────────────────────────────────────── */
const MP_APPID = process.env.ELEME_APPID || WX_APPID;
const MP_APP_VERSION = process.env.ELEME_APP_VERSION || '12.6.3';
const LOGIN_ENDPOINT = process.env.ELEME_LOGIN_ENDPOINT || 'https://ipassport.ele.me/mini_program/login.do';
const UMID_URL = process.env.ELEME_UMID_URL || 'https://ynuf.aliapp.org/w/mu.json';
const DEFAULT_URL = LOGIN_ENDPOINT;
const APP_ID = MP_APPID;
const zlib = require('zlib');
const os = require('os');

const BX_STD64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=";
const BX_SUB64 = "v03TgH2iMLjV7QxCDcrAhuY46nGXFP9B+opwkybRKas58JIEfZS/zdO1tWlmeNUq=";
const BX_FINGERPRINT = zlib
  .brotliDecompressSync(
    Buffer.from(
      "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",
      "base64",
    ),
  )
  .toString();
const BX_RAW_1 = [
  133, 121, 59, 17, 6, 132, 125, 193, 29, 48, 150, 148, 148, 148, 148, 148, 148, 148, 148, 148, 149, 27, 158, 81, 155,
  27, 158, 81, 155, 137, 156, 157, 81, 155, 37, 155, 157, 27, 158, 137, 27, 158, 26, 115, 46, 19, 9, 22, 9, 22, 22, 9,
  21, 19, 33, 20, 9, 31, 9, 22, 21, 39, 39, 34, 93, 79, 120, 100, 105, 39, 39, 39, 39, 39, 39, 25, 133, 191, 183, 188,
  160, 191, 184, 182, 160, 191, 160, 188, 64, 244, 74, 173, 63, 149, 43, 124, 129,
];
const BX_RAW_3 = [
  60, 170, 42, 69, 226, 29, 19, 18, 18, 131, 113, 206, 206, 206, 206, 143, 154, 206, 175, 156, 156, 143, 151, 192, 210,
  143, 128, 129, 128, 151, 131, 129, 155, 157, 208, 206, 198, 173, 212, 178, 187, 157, 139, 156, 157, 178, 214, 216,
  222, 219, 216, 178, 170, 129, 141, 155, 131, 139, 128, 154, 157, 178, 169, 135, 154, 166, 155, 140, 178, 157, 135,
  130, 130, 151, 169, 135, 156, 130, 178, 192, 141, 129, 138, 139, 150, 195, 143, 156, 154, 135, 136, 143, 141, 154,
  157, 178, 151, 151, 140, 195, 157, 129, 155, 156, 141, 139, 178, 139, 130, 139, 131, 139, 177, 143, 157, 157, 139,
  154, 157, 178, 158, 130, 155, 137, 135, 128, 177, 178, 153, 150, 138, 218, 216, 140, 216, 139, 215, 141, 215, 140,
  217, 217, 219, 143, 219, 216, 178, 136, 135, 156, 139, 151, 139, 132, 157, 192, 131, 135, 128, 192, 132, 157, 212,
  221, 218, 222, 212, 218, 219, 199, 211, 206, 206, 206, 206, 143, 154, 206, 163, 129, 138, 155, 130, 139, 192, 130,
  129, 143, 138, 206, 198, 128, 129, 138, 139, 212, 135, 128, 154, 139, 156, 128, 143, 130, 193, 131, 129, 138, 155,
  130, 139, 157, 193, 141, 132, 157, 193, 130, 129, 143, 138, 139, 156, 212, 223, 219, 217, 217, 212, 221, 220, 199,
  229, 238, 238, 238, 238, 112, 60, 200, 174,
];
const BX_RAW_4_HEAD = [85, 15, 84, 168, 232, 56, 214, 214, 212, 108, 151];
const BX_RAW_4_CORE = [
  127, 17, 17, 25, 121, 112, 121, 113, 121, 185, 220, 211, 206, 200, 206, 152, 202, 146, 202, 159, 200, 147, 153, 205,
  158, 147, 200, 146, 173, 154, 153, 133, 157, 133, 152, 172, 217, 206, 199, 206, 202, 216, 206, 171, 171, 28, 120, 124,
  118, 103, 122, 102, 122, 115, 97, 28, 120, 124, 118, 103, 122, 102, 122, 115, 97, 115, 26, 98, 124, 123, 113, 122, 98,
  102, 58, 64, 123, 126, 123, 122, 98, 123, 18, 98, 124, 123, 113, 122, 98, 102, 21, 246, 247,
];

function bxUleb(value) {
  const out = [];
  do {
    const byte = value % 128;
    value = (value - byte) / 128;
    out.push(byte + (value ? 128 : 0));
  } while (value);
  return out;
}

function bxCompress(input) {
  const out = bxUleb(input.length);
  let bits = "";
  let model = ` ${Array.from({ length: 256 }, (_, index) => String.fromCharCode(index)).join("")} `;
  let low = 0;
  let high = 1;
  for (const byte of input) {
    const lower = model.indexOf(String.fromCharCode(byte), 1);
    const upper = byte === 255 ? model.length - 1 : model.indexOf(String.fromCharCode(byte + 1), 1);
    const unit = (high - low) / model.length;
    high = low + unit * upper;
    low += unit * lower;
    model = `${model.slice(0, upper)}${"\0".repeat(27)}${model.slice(upper)}`;
    const highBits = high.toString(2).slice(2);
    const lowBits = low.toString(2).slice(2);
    let shared = 0;
    while (shared < highBits.length && shared < lowBits.length && highBits[shared] === lowBits[shared]) shared += 1;
    bits += highBits.slice(0, shared);
    const scale = 2 ** shared;
    high = (high * scale) % 1;
    low = (low * scale) % 1;
  }
  bits += low.toString(2).slice(2).replace(/0+$/, "");
  while (bits.length > 7) {
    out.push(parseInt(bits.slice(0, 8), 2));
    bits = bits.slice(8);
  }
  out.push(parseInt((bits + "00000000").slice(0, 8), 2));
  return out;
}

function bxTransform(mode, input) {
  const rotate = (value, bits) => ((value << bits) | (value >>> (8 - bits))) & 255;
  const out = [];
  for (let index = 0; index < input.length; index += 2) {
    const first = input[index];
    const second = input[index + 1] ?? 0;
    const pair = (index / 2) & 3;
    let a;
    let b;
    if (mode === 1) {
      if (pair === 0) {
        a = first ^ 235;
        b = second ^ a;
      } else if (pair === 1) {
        a = first ^ 89;
        b = second ^ 52;
      } else if (pair === 2) {
        a = rotate((first - 8) & 255, 4);
        b = rotate((second - 8) & 255, 4);
      } else {
        a = first ^ 2;
        b = second ^ a;
      }
    } else if (mode === 3) {
      if (pair === 0) {
        a = first ^ 111;
        b = second ^ a;
      } else if (pair === 1) {
        a = rotate((first - 2) & 255, 4);
        b = rotate((second - 2) & 255, 4);
      } else if (pair === 2) {
        a = (first + 11) & 255;
        b = (second + 11) & 255;
      } else {
        a = first ^ 78;
        b = second ^ 122;
      }
    } else {
      if (pair === 0) {
        a = first ^ 71;
        b = second ^ 103;
      } else if (pair === 1) {
        a = first ^ 189;
        b = second ^ a;
      } else if (pair === 2) {
        a = rotate((first - 7) & 255, 5);
        b = rotate((second - 7) & 255, 5);
      } else {
        a = (first + 11) & 255;
        b = (second + 11) & 255;
      }
    }
    out.push(a, b);
  }
  return out.slice(0, input.length);
}

function bxSection(payload, mask) {
  const checksum = payload.reduce((sum, byte) => sum + (byte & mask), 0);
  return [...bxUleb(payload.length + 2), (checksum >>> 8) & 255, checksum & 255, ...payload];
}

function bxDynamicInput(timestamp, rng) {
  const random = Array.from({ length: 3 }, () => {
    const value = Number(rng());
    if (!Number.isFinite(value) || value < 0 || value >= 1) {
      const error = new RangeError("BX_UA_RANDOM_INVALID");
      error.code = "BX_UA_RANDOM_INVALID";
      throw error;
    }
    return value;
  });
  const randomId = random[0].toString(36).slice(2) + random[1].toString(36).slice(2);
  const blocks = Math.ceil(BX_FINGERPRINT.length / 80);
  const start = Math.floor(random[2] * blocks) * 80;
  const chunk = BX_FINGERPRINT.slice(start, start + 80);
  const snippet = encodeURI(chunk);
  const time = Buffer.alloc(8);
  time.writeBigUInt64BE(BigInt(timestamp));
  return [
    ...BX_RAW_4_HEAD,
    ...bxUleb(start).map((byte) => byte ^ 249),
    chunk.length ^ 249,
    3 ^ 249,
    ...BX_RAW_4_CORE,
    ...time.map((byte) => byte ^ 147),
    ...bxUleb(randomId.length + snippet.length + 4).map((byte) => byte ^ 81),
    81,
    ...Buffer.from(randomId).map((byte) => byte ^ 81),
    81,
    81,
    ...Buffer.from(snippet).map((byte) => byte ^ 81),
    81,
  ];
}

function encodeBxBase64(bytes) {
  return Buffer.from(bytes)
    .toString("base64")
    .replace(/./g, (character) => BX_SUB64[BX_STD64.indexOf(character)]);
}

const BX_SECTION_1 = bxSection(bxTransform(1, bxCompress(BX_RAW_1)), 248);
const BX_SECTION_3 = bxSection(bxTransform(3, BX_RAW_3), 99);

function buildBxUa({ now = Date.now(), rng = Math.random } = {}) {
  const timestamp = Number(now);
  if (!Number.isSafeInteger(timestamp) || timestamp < 0) {
    const error = new TypeError("BX_UA_NOW_INVALID");
    error.code = "BX_UA_NOW_INVALID";
    throw error;
  }
  if (typeof rng !== "function") {
    const error = new TypeError("BX_UA_RNG_INVALID");
    error.code = "BX_UA_RNG_INVALID";
    throw error;
  }
  const section4 = bxSection(bxTransform(4, bxCompress(bxDynamicInput(timestamp, rng))), 157);
  const body = [...BX_SECTION_1, 4, 0, 9, 5, 4, ...BX_SECTION_3, ...section4];
  const checksum = body.reduce((sum, byte) => sum + (byte & 41), 0);
  const low = timestamp % 0x10000;
  const frame = [
    (low >>> 8) & 255,
    low & 255,
    (body.length >>> 8) & 255,
    body.length & 255,
    (checksum >>> 8) & 255,
    checksum & 255,
    ((low >>> 8) + 41) & 255,
    (low + 41) & 255,
    0,
    4,
    1,
    61,
    ...body,
  ];
  return `317$${encodeBxBase64(frame)}`;
}

const JANUS_SBOX_27 = Buffer.from(
  "7/f/AAgQGCAoMDhASFBYYGhweICIkJigqLC4wMjQ2ODo8PgBCREZISkxOUFJUVlhaXF5gYmRmaGpsbnBydHZ4enx+QIKEhoiKjI6QkpSWmJqcnqCipKaoqqyusLK0tri6vL6AwsTGyMrMztDS1NbY2tze4OLk5ujq7O7w8vT2+Pr8/sEDBQcJCw0PERMVFxkbHR8hIyUnKSstLzEzNTc5Oz0/AUNFR0lLTU9RU1VXWVtdX2FjZWdpa21vcXN1d3l7fX9Bg4WHiYuNj5GTlZeZm52foaOlp6mrra+xs7W3ubu9v4HDxcfJy83P0dPV19nb3d/h4+Xn6evt7/Hz9ff5w==",
  "base64",
);
const JANUS_SBOX_28 = Buffer.from(
  "z9ff5+/3/wAIEBggKDA4QEhQWGBocHiAiJCYoKiwuMDI0Njg6PD4AQkRGSEpMTlBSVFZYWlxeYGJkZmhqbG5wcnR2eHp8fkCChIaIioyOkJKUlpianJ6goqSmqKqsrrCytLa4ury+gMLExsjKzM7Q0tTW2Nrc3uDi5Obo6uzu8PL09vj6/P7BAwUHCQsNDxETFRcZGx0fISMlJykrLS8xMzU3OTs9PwFDRUdJS01PUVNVV1lbXV9hY2VnaWttb3FzdXd5e31/QYOFh4mLjY+Rk5WXmZudn6Gjpaepq62vsbO1t7m7vb+Bw8XHycvNz9HT1dfZ293f4ePl5+nr7e/xw==",
  "base64",
);
const JANUS_SUB64 = "16s/O9tTGMigNwZaCBIQdpKLhHn3FeEUfXjbAvxYcDm0V2q45WS7RJ+8lkouPyrz=";
const JANUS_PLAIN = [
  61,
  224,
  100,
  8,
  229,
  0,
  0,
  0,
  0,
  32,
  1,
  75,
  92,
  149,
  43,
  101,
  83,
  241,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  1,
  0,
  0,
  0,
  0,
  0,
  4,
  37,
  219,
  250,
  192,
  234,
  15,
  129,
  132,
  0,
  0,
  0,
  1,
  101,
  83,
  241,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  90,
  3,
  null,
  0,
  0,
  0,
  0,
  0,
  1,
  134,
  0,
  0,
  3,
  76,
  0,
  1,
  167,
  16,
  102,
  225,
  118,
  90,
  57,
  182,
  89,
  25,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  null,
  72,
  53,
  58,
  205,
  0,
  0,
  0,
  0,
  -2,
  -2,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  0,
  null,
];

function janusU32(value) {
  return [(value >>> 24) & 0xff, (value >>> 16) & 0xff, (value >>> 8) & 0xff, value & 0xff];
}

function janusUrlHash(url) {
  let hash = 0;
  const step = Math.max(1, Math.floor(url.length / 20));
  for (let index = 0; index < url.length; index += step) {
    hash = (Math.imul(31, hash) + url.charCodeAt(index)) | 0;
  }
  return hash >>> 0;
}

function janusChecksum(bytes, mask) {
  let sum = 0;
  for (let index = 0; index < bytes.length; index += 1) {
    sum += (bytes[index] + index) & 0xff & mask;
  }
  return sum;
}

function janusPairs(bytes, key, first, second) {
  const operations = (key & 1) === 0 ? [first, second] : [second, first];
  const output = [];
  for (let index = 0; index < bytes.length; index += 2) {
    output.push(...operations[(index / 2) & 1](bytes[index], bytes[index + 1], key));
  }
  return output.slice(0, bytes.length);
}

function janusUnary(table) {
  return (first, second, key) => [table[(first ?? 0) & 0xff] ^ key, table[(second ?? 0) & 0xff] ^ key];
}

const JANUS_OP_19 = (first, second, key) => [(first ^ 4 ^ key) & 0xff, ((second ?? 0) ^ 112 ^ key) & 0xff];
const JANUS_OP_30 = (first, second, key) => [(first ^ 80 ^ key) & 0xff, ((second ?? 0) ^ 109 ^ key) & 0xff];
const JANUS_OP_24 = (first, second, key) => [(first ^ 116 ^ key) & 0xff, ((second ?? 0) ^ 111 ^ key) & 0xff];
const JANUS_OP_1 = (first, second, key) => {
  const encodedFirst = (first ^ 244 ^ key) & 0xff;
  return [encodedFirst, ((second ?? 0) ^ encodedFirst) & 0xff];
};
const JANUS_OP_32 = (first, second, key) => [((first ?? 0) ^ 97 ^ key) & 0xff, ((second ?? 0) ^ 76 ^ key) & 0xff];
const JANUS_OP_21 = (first, second, key) => [
  first == null ? key : ((first + 177) & 0xff) ^ key,
  second == null ? key : ((second + 177) & 0xff) ^ key,
];

function buildMiniJanus({ now = Date.now(), url = DEFAULT_URL, rng = Math.random } = {}) {
  const timestamp = Number(now);
  if (!Number.isSafeInteger(timestamp) || timestamp < 0) {
    const error = new TypeError("MINI_JANUS_NOW_INVALID");
    error.code = "MINI_JANUS_NOW_INVALID";
    throw error;
  }
  if (typeof rng !== "function") {
    const error = new TypeError("MINI_JANUS_RNG_INVALID");
    error.code = "MINI_JANUS_RNG_INVALID";
    throw error;
  }
  const random = Array.from({ length: 7 }, () => {
    const value = Number(rng());
    if (!Number.isFinite(value) || value < 0 || value >= 1) {
      const error = new RangeError("MINI_JANUS_RANDOM_INVALID");
      error.code = "MINI_JANUS_RANDOM_INVALID";
      throw error;
    }
    return value;
  });
  const targetUrl = String(url);
  const seconds = Math.floor(timestamp / 1000);
  const key = (Math.floor(random[5] * 256) + 232 * (seconds & 0xff) + 16) & 0xff;
  const timeBytes = Buffer.alloc(8);
  timeBytes.writeBigUInt64BE(BigInt(timestamp + 1));

  const segment1 = janusPairs([...timeBytes.subarray(2), 0], key, janusUnary(JANUS_SBOX_27), janusUnary(JANUS_SBOX_28));
  const segment2 = janusPairs([61, 6, 0, 0, 0, 0, 0, 0, 0, 0], key, JANUS_OP_19, JANUS_OP_30);
  const segment3 = janusPairs(
    [...timeBytes.subarray(2), 6, 0, 1, 17, ...Buffer.from("pages/index/index")],
    key,
    JANUS_OP_24,
    JANUS_OP_1,
  );

  const plain = JANUS_PLAIN.slice();
  plain.splice(1, 4, ...janusU32(janusUrlHash(targetUrl)));
  plain.splice(11, 4, ...janusU32(Math.floor(0xffffffff * random[3])));
  plain.splice(15, 4, ...janusU32(seconds));
  plain.splice(33, 4, ...janusU32(Math.floor(0xffffffff * random[2])));
  plain.splice(37, 4, ...janusU32(Math.floor(0xffffffff * random[6])));
  plain.splice(45, 4, ...janusU32(seconds));
  const encodedPlain = janusPairs(plain, key, JANUS_OP_32, JANUS_OP_21);

  const body = [
    key,
    janusChecksum(segment1, 98) & 0xff,
    7,
    ...segment1,
    janusChecksum(segment2, 233) & 0xff,
    10,
    ...segment2,
    janusChecksum(segment3, 191) & 0xff,
    27,
    ...segment3,
    janusChecksum(encodedPlain, 109) & 0xff,
    111,
    ...encodedPlain,
  ];
  const globalChecksum = janusChecksum(body.slice(1), 123);
  const frame = [(globalChecksum >>> 8) & 0xff, globalChecksum & 0xff, ...body];
  const standard = Buffer.from(frame).toString("base64");
  let encoded = "";
  for (const character of standard) encoded += JANUS_SUB64[BX_STD64.indexOf(character)];
  return `12@${encoded}`;
}

function yes(value) {
  return value === true || /^(1|true|y|yes)$/i.test(String(value || "").trim());
}

function request({ url, method = "GET", headers = {}, body = "", timeout = 12000 }) {
  return new Promise((resolve, reject) => {
    const target = new URL(url);
    const transport = target.protocol === "http:" ? http : https;
    const reqOpts = {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port,
      path: target.pathname + target.search,
      method,
      headers,
      timeout,
    };
    // 与 httpReq 一致的代理支持：https 走 CONNECT 隧道，http 走绝对 URI 转发
    const pu = proxyConf();
    if (pu && target.protocol !== "http:") {
      reqOpts.agent = tunnelAgent();
    } else if (pu) {
      reqOpts.hostname = pu.hostname;
      reqOpts.port = Number(pu.port) || 80;
      reqOpts.path = url;
      if (_proxyAuth) reqOpts.headers = { ...headers, "Proxy-Authorization": _proxyAuth };
    }
    const req = transport.request(
      reqOpts,
      (res) => {
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => {
          const text = Buffer.concat(chunks).toString("utf8");
          if ((res.statusCode || 0) >= 200 && (res.statusCode || 0) < 300) {
            resolve({ status: res.statusCode, headers: res.headers, text });
          } else {
            const error = new Error(`HTTP_${res.statusCode || 0}`);
            error.status = res.statusCode || 0;
            error.body = text;
            reject(error);
          }
        });
      },
    );
    req.on("timeout", () => req.destroy(new Error("REQUEST_TIMEOUT")));
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

function stableUtdid(seed = "") {
  return crypto
    .createHash("sha256")
    .update(`${APP_ID}|${seed || os.hostname()}|${os.platform()}|${os.arch()}`)
    .digest("hex")
    .slice(0, 32)
    .toUpperCase();
}

function requestId(now = Date.now()) {
  return `${crypto.randomBytes(16).toString("hex").toUpperCase()}|${now}`;
}

function sessionToXSmallstc(session = {}) {
  const data = { ...session };
  delete data.username;
  return Object.keys(data).length ? JSON.stringify(data) : "";
}

function buildXEleUa({
  session = {},
  lng = "",
  lat = "",
  brand = "microsoft",
  model = "microsoft",
  system = "windows/Unknown",
  wechatVersion = "4.1.11.24",
} = {}) {
  const deviceId =
    session.union_id || session.unionId || session.open_id || session.openId || session.user_id || session.userId || "";
  return [
    "RenderWay/miniProgram",
    `MiniAppId/${APP_ID}`,
    `MiniAppVersion/${MP_APP_VERSION}`,
    deviceId && `DeviceId/${deviceId}`,
    "AppName/Wechat",
    `${brand}/${model}/${system}`,
    `Wechat/${wechatVersion}`,
    "channel/wechat_app",
    "subChannel/wechat_app.default",
    lng && lat && `Longitude/${lng}`,
    lng && lat && `Latitude/${lat}`,
  ]
    .filter(Boolean)
    .join(" ");
}

async function fetchUmid() {
  const result = await request({ url: UMID_URL, method: "POST" });
  const match = result.text.match(/(?:umx\.wu|__fycb)\(['"]([^'"]+)['"]\)/);
  return match ? match[1] : "";
}

async function buildRiskHeaders(opts = {}) {
  const session = opts.session && typeof opts.session === "object" ? opts.session : {};
  const url = String(opts.url || DEFAULT_URL);
  const utdid = String(opts.utdid || stableUtdid(opts.deviceSeed));
  const now = opts.now === undefined ? Date.now() : Number(opts.now);
  const rng = opts.random || Math.random;
  const miniJanusRaw = buildMiniJanus({ url, now, rng });
  const miniJanus = encodeURIComponent(miniJanusRaw);
  const bxUa = buildBxUa({ now, rng });
  let umidToken = String(opts.umidToken || opts["umid-token"] || opts["bx-umidtoken"] || "");
  if (!umidToken && !yes(opts.noNetwork || opts["no-network"])) umidToken = await fetchUmid();

  const headers = {
    "mini-janus": miniJanus,
    "bx-ua": bxUa,
    "x-ele-ua": String(
      opts.xEleUa ||
        buildXEleUa({
          session,
          lng: opts.lng || opts.longitude || "",
          lat: opts.lat || opts.latitude || "",
          brand: opts.brand || "microsoft",
          model: opts.model || "microsoft",
          system: opts.system || "windows/Unknown",
          wechatVersion: opts.wechatVersion || opts.wechat || "4.1.11.24",
        }),
    ),
    "x-eleme-requestid": String(opts.requestId || requestId(opts.now || Date.now())),
    "x-utdid": utdid,
  };
  const smallstc = String(opts.xSmallstc || sessionToXSmallstc(session));
  const uid = String(opts.uid || session.munb || session.user_id || session.userId || "");
  const miniWua = String(opts.xMiniWua || opts["x-mini-wua"] || "");
  if (umidToken) {
    headers["bx-umidtoken"] = umidToken;
    headers["x-umidToken"] = umidToken;
  }
  if (smallstc) headers["x-smallstc"] = smallstc;
  if (uid) headers["x-uid"] = uid;
  if (miniWua) headers["x-mini-wua"] = miniWua;
  return {
    ok: Boolean(miniJanus && bxUa && umidToken),
    params: {
      miniJanus,
      miniJanusRaw,
      bxUa,
      umidToken,
      bxUmidToken: umidToken,
      utdid,
      requestId: headers["x-eleme-requestid"],
    },
    headers,
  };
}

const ACCOUNT_COOKIE_FIELDS = [
  ["cookie2", ["cookie2", "sid"]],
  ["sid", ["sid"]],
  ["SID", ["SID"]],
  ["userId", ["user_id", "userId", "USERID"]],
  ["openId", ["open_id", "openId"]],
  ["unionId", ["union_id", "unionId"]],
  ["sgcookie", ["sgcookie"]],
  ["munb", ["munb"]],
  ["UTUSER", ["UTUSER"]],
  ["st", ["st"]],
];

async function havanaCodeLogin(code, cfg) {
  let risk;
  let riskWarning = "";
  try {
    risk = await buildRiskHeaders({ url: LOGIN_ENDPOINT, session: {}, umidToken: cfg.umid_token });
  } catch (error) {
    risk = await buildRiskHeaders({ url: LOGIN_ENDPOINT, session: {}, noNetwork: true });
    riskWarning = `UMID 自动获取失败，已携带 BX-UA/mini-janus 继续请求：${errorText(error)}`;
  }
  if (!risk.params.umidToken && !riskWarning) riskWarning = "UMID 接口未返回 token，已携带 BX-UA/mini-janus 继续请求";

  const authorizationCode = JSON.stringify({ authorizationCode: String(code) });
  const form = new URLSearchParams([
    ["type", "weixin_mini_program"],
    ["appId", APP_ID],
    ["appName", "eleme"],
    ["appEntrance", "weixin"],
    ["lang", "zh_CN"],
    ["isMobile", "true"],
    ["returnUrl", ""],
    ["needPassWebViewCookie", "false"],
    ["authorizationCode", authorizationCode],
  ]);
  if (risk.params.bxUmidToken) form.set("umidToken", risk.params.bxUmidToken);
  const body = form.toString();
  const headers = Object.assign(
    {
      Accept: "application/json,text/plain,*/*",
      "Content-Type": "application/x-www-form-urlencoded",
      "Accept-Language": "zh-CN,zh;q=0.9",
      "User-Agent": `Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 MicroMessenger/8.0.58 miniProgram/${APP_ID}`,
      Referer: `https://servicewechat.com/${APP_ID}/831/page-frame.html`,
      "x-tap": "wx",
      "Content-Length": Buffer.byteLength(body),
    },
    risk.headers,
  );

  const response = await requestTextAny({
    url: LOGIN_ENDPOINT,
    method: "POST",
    headers,
    body,
    timeout: cfg.request_timeout * 1000,
  });
  const payload = parseJson(response.text);
  const content = payload && typeof payload.content === "object" ? payload.content : {};
  const session = content && typeof content.data === "object" && content.data ? Object.assign({}, content.data) : {};
  if (session.sid && !session.cookie2) session.cookie2 = session.sid;
  const cookie = buildAccountCookie(session);
  const ok = response.status >= 200 && response.status < 300 && Boolean(session.cookie2 || session.sid || session.st);
  if (!ok) {
    const message = content.errorMsg || content.msg || payload.msg || session.titleMsg || "";
    const redirectEntries = ["redirect", "iframeRedirect", "redirectUrl", "iframeRedirectUrl"]
      .filter((key) => session[key] !== undefined && session[key] !== null && session[key] !== "")
      .map((key) => [key, printableValue(session[key], 2400)]);
    const details = [];
    if (message) details.push(`接口消息：${printableValue(message, 800)}`);
    if (redirectEntries.length) {
      details.push("接口返回跳转/绑定流程，未直接下发 Cookie");
      for (const [key, value] of redirectEntries) details.push(`${key}：${value}`);
    }
    if (!details.length)
      details.push(`响应无 sid/st/cookie2（HTTP ${response.status}）：${safePreview(response.text, 180)}`);
    return {
      ok: false,
      status: response.status,
      error: details.join("\n"),
      redirects: Object.fromEntries(redirectEntries),
    };
  }
  return {
    ok: true,
    status: response.status,
    cookie,
    session,
    username: String(session.username || ""),
    userId: String(session.user_id || session.userId || session.USERID || ""),
    openId: String(session.open_id || session.openId || ""),
    riskWarning,
  };
}

function buildAccountCookie(session) {
  const parts = [];
  for (const [outputKey, sourceKeys] of ACCOUNT_COOKIE_FIELDS) {
    let value = "";
    for (const key of sourceKeys) {
      if (session[key] !== undefined && session[key] !== null && String(session[key]) !== "") {
        value = String(session[key]);
        break;
      }
    }
    if (!value) continue;
    parts.push(`${outputKey}=${outputKey === "SID" ? value : encodeURIComponent(value)}`);
  }
  return parts.join("; ");
}

function requestTextAny({ url, method = "GET", headers = {}, body = "", timeout = 30000 }) {
  return new Promise((resolve, reject) => {
    const target = new URL(url);
    const transport = target.protocol === "http:" ? http : https;
    const reqOpts = {
      protocol: target.protocol,
      hostname: target.hostname,
      port: target.port,
      path: target.pathname + target.search,
      method,
      headers,
      timeout,
    };
    const pu = proxyConf();
    if (pu && target.protocol !== "http:") {
      reqOpts.agent = tunnelAgent();
    } else if (pu) {
      reqOpts.hostname = pu.hostname;
      reqOpts.port = Number(pu.port) || 80;
      reqOpts.path = url;
      if (_proxyAuth) reqOpts.headers = { ...headers, "Proxy-Authorization": _proxyAuth };
    }
    const req = transport.request(
      reqOpts,
      (response) => {
        const chunks = [];
        response.on("data", (chunk) => chunks.push(chunk));
        response.on("end", () =>
          resolve({
            status: response.statusCode || 0,
            headers: response.headers,
            text: Buffer.concat(chunks).toString("utf8"),
          }),
        );
      },
    );
    req.on("timeout", () => req.destroy(new Error("请求超时")));
    req.on("error", reject);
    if (body) req.write(body);
    req.end();
  });
}

function nestedValue(payload, keys) {
  const wanted = new Set(keys.map((key) => String(key).toLowerCase()));
  const queue = [payload];
  while (queue.length) {
    const value = queue.shift();
    if (!value || typeof value !== "object") continue;
    for (const [key, child] of Object.entries(value)) {
      if (wanted.has(String(key).toLowerCase()) && child !== null && child !== undefined && child !== "") return child;
      if (child && typeof child === "object") queue.push(child);
    }
  }
  return null;
}

function nestedText(payload, keys) {
  const value = nestedValue(payload, keys);
  return typeof value === "string" || typeof value === "number" ? String(value).trim() : "";
}

function responseMessage(payload) {
  const value = nestedValue(payload, ["errmsg", "errMsg", "message", "msg", "error", "retMsg"]);
  return typeof value === "object"
    ? JSON.stringify(value).slice(0, 300)
    : String(value || "")
        .trim()
        .slice(0, 300);
}

function parseJson(text) {
  try {
    const value = JSON.parse(String(text || ""));
    return value && typeof value === "object" ? value : {};
  } catch (_) {
    return {};
  }
}

function printableValue(value, limit) {
  let text;
  if (typeof value === "string") text = value;
  else {
    try {
      text = JSON.stringify(value);
    } catch (_) {
      text = String(value || "");
    }
  }
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function safePreview(text, limit) {
  return String(text || "")
    .replace(/(cookie2|sid|SID|st|sgcookie)=([^;\s"']+)/g, "$1=***")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, limit || 180);
}

function positiveInt(value, fallback) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : fallback;
}

function errorText(error) {
  return error && error.message ? String(error.message).trim() : String(error || "未知错误").trim();
}

/* ipassport 登录结果 → engage-hub 登录态 */
async function ipassportLogin(st, wxcode) {
  const res = await havanaCodeLogin(wxcode, {
    umid_token: process.env.ELEME_UMID_TOKEN || '',
    request_timeout: Number(process.env.ELEME_TIMEOUT) || 30,
  });
  if (!res.ok) {
    if (res.redirects && res.redirects.redirectUrl) {
      return '该微信尚未绑定饿了么账号（需手机号完成绑定）。'
           + '请先在本微信里打开一次「淘宝闪购」小程序登录绑定后重试';
    }
    return res.error || 'ipassport 登录失败';
  }
  const sess = res.session || {};
  const put = (k, v) => { if (v !== undefined && v !== null && String(v) !== '') st.cookie[k] = String(v); };
  put('cookie2', sess.cookie2 || sess.sid);
  put('sid', sess.sid || sess.cookie2);
  put('SID', sess.SID);
  put('userId', sess.user_id || sess.userId || sess.USERID);
  put('USERID', sess.user_id || sess.userId || sess.USERID);
  put('unb', sess.user_id || sess.userId || sess.USERID);
  put('munb', sess.munb);
  put('UTUSER', sess.UTUSER || sess.user_id || sess.userId);
  put('openId', sess.open_id || sess.openId);
  put('unionId', sess.union_id || sess.unionId);
  put('sgcookie', sess.sgcookie);
  put('st', sess.st);
  if (res.username) log(`   账号: ${res.username}`);
  return true;
}

async function snsLogin(st, wxcode) {
  const t = Date.now();
  const loginInfo = buildLoginInfoBase(st, t);
  // SnsLoginRequest（com.taobao.android.sns4android）字段：appId/snsType/token/userId/trustOpenId
  loginInfo.appId = WX_APPID;
  loginInfo.snsType = SNS_TYPE;
  loginInfo.token = wxcode;
  const data = {
    ext: buildExt(st, 'snsLogin'),
    snsLoginInfo: JSON.stringify(loginInfo),
    riskControlInfo: buildRiskControl(st, t),
  };
  const api = process.env.ELM_YYB_API || 'mtop.alsc.mloginService.snsLogin';
  const res = await loginRequest(st, api, data);
  const code2 = findKey(res, 'code');
  if (String(code2) === '3000') {
    applyLoginReturn(st, res);
    return true;
  }
  if (String(code2) === '13060') {
    st.token = findKey(res, 'token');
    st.h5Url = findKey(res, 'h5Url');
    return '需要验证';
  }
  return findKey(res, 'message') || `snsLogin 失败: ${JSON.stringify(res).slice(0, 300)}`;
}

/* 登录成功后的落盘 + 提示 */
function finishLogin(st) {
  const required = ['cookie2', 'SID', 'USERID', 'token'];
  const missing = required.filter((k) => !st.cookie[k]);
  if (missing.length > 0) {
    log(`⚠ 登录响应缺少必要字段: ${missing.join(', ')}`);
    log('   不伪造补齐字段，后续首页请求会验证实际登录态');
  }
  const ck = dict2str(st.cookie);
  try {
    fs.writeFileSync(COOKIE_FILE, ck);
    fs.writeFileSync(DEVICE_FILE, JSON.stringify({
      deviceId: st.cookie.deviceId || '',
      utdid: st.cookie.utdid || '',
      appId: st.appId || '',
      createdAt: new Date().toISOString(),
    }));
    log(`✅ 登录态已写入 ${COOKIE_FILE}，设备档案已绑定到 ${DEVICE_FILE}`);
  } catch (e) {
    log(`⚠ 登录态或设备档案写文件失败: ${e.message}`);
  }
  log(`   cookie 字段: ${Object.keys(st.cookie).filter((k) => st.cookie[k]).join(', ')}`);
  COOKIE = ck;
  clearState();
}

/* 短信登录流程（两段式：先发短信，填 ELM_SMS_CODE 后再跑一次） */
async function smsLoginFlow() {
  const st = loadState() || newLoginState();

  // 阶段3：havana_iv_token 继续登录
  if (ELM_HAVANA_URL) {
    const m = ELM_HAVANA_URL.match(/havana_iv_token=([^&]+)/);
    if (!m) { log('❌ ELM_HAVANA_URL 里没有 havana_iv_token'); return false; }
    if (!st.token) { log('❌ 缺少登录会话状态，请先发短信并完成 smslogin'); return false; }
    const r = await mloginTokenLogin(st, m[1]);
    if (r === true) { log('✅ 短信登录成功'); finishLogin(st); return true; }
    log(`❌ ${r}`); return false;
  }

  // 阶段2：已发验证码 → smslogin
  if (ELM_SMS_CODE) {
    if (!st.smsSid || !st.phone) {
      log('❌ 未找到已发短信的会话（elm_login_state.json）。请先去掉 ELM_SMS_CODE 跑一次以发送验证码');
      return false;
    }
    const r = await smsLogin(st, st.phone, ELM_SMS_CODE);
    if (r === true) { log('✅ 短信登录成功'); finishLogin(st); return true; }
    if (r === '需要验证') {
      saveState(st);
      log('⚠ 账号需要滑块/二次验证，请用浏览器打开下面链接完成验证：');
      log(`   ${st.h5Url}`);
      log('   验证通过后浏览器会跳转，把跳转后的完整链接填到 ELM_HAVANA_URL 再跑一次');
      return false;
    }
    log(`❌ 短信登录失败: ${r}`);
    return false;
  }

  // 阶段1：发短信
  if (!/^1\d{10}$/.test(ELM_PHONE)) {
    log('❌ 短信登录需要配置 ELM_PHONE（11位手机号）');
    return false;
  }
  if (st.phone && st.phone !== ELM_PHONE) Object.assign(st, newLoginState());
  try {
    await smsSend(st, ELM_PHONE);
  } catch (e) {
    log(`❌ ${e.message}`);
    return false;
  }
  st.phone = ELM_PHONE;
  saveState(st);
  log(`✅ 验证码已发送到 ${ELM_PHONE}`);
  log('   收到后把验证码填到环境变量 ELM_SMS_CODE，再跑一次本脚本即完成登录');
  return false;
}

/* YYB 登录流程：getCode → snsLogin */
async function yybLoginFlow() {
  // 二次验证分支：上次 snsLogin 返回"需要验证"时，用 havana_iv_token 继续
  if (ELM_HAVANA_URL) {
    const st = loadState();
    const m = ELM_HAVANA_URL.match(/havana_iv_token=([^&]+)/);
    if (!m) { log('❌ ELM_HAVANA_URL 里没有 havana_iv_token'); return false; }
    if (!st || !st.token) { log('❌ 缺少登录会话状态，请先跑一次 YYB 登录触发验证'); return false; }
    const r = await mloginTokenLogin(st, m[1]);
    if (r === true) { log('✅ YYB 微信登录成功'); finishLogin(st); return true; }
    log(`❌ ${r}`); return false;
  }

  const st = newLoginState();
  let wxcode;
  try {
    const ref = YYB_QR ? await yybQrEnroll() : null;
    wxcode = await yybGetCode(ref);
  } catch (e) {
    log(`❌ ${e.message}`);
    return false;
  }
  log(`   拿到微信 code: ${String(wxcode).slice(0, 12)}...`);
  let r;
  try {
    if (process.env.ELM_YYB_LEGACY === '1') {
      r = await snsLogin(st, wxcode);
    } else {
      r = await ipassportLogin(st, wxcode);
    }
  } catch (e) {
    log(`❌ 登录请求异常: ${e.message}`);
    return false;
  }
  if (r === true) { log('✅ YYB 微信登录成功'); finishLogin(st); return true; }
  if (r === '需要验证') {
    saveState(st);
    log('⚠ 需要二次验证，请用浏览器打开下面链接完成验证后把跳转链接填到 ELM_HAVANA_URL 再跑一次：');
    log(`   ${st.h5Url}`);
    return false;
  }
  log(`❌ YYB 登录失败: ${r}`);
  log('   提示：默认走 ipassport 小程序 login.do 通道；ELM_YYB_LEGACY=1 可切回旧 snsLogin');
  return false;
}

function taskCookieMissing(cookie) {
  const d = str2dict(cookie);
  return ['cookie2', 'SID', 'USERID'].filter((k) => !d[k]);
}

/* 登录入口：ELM_COOKIE > cookie 文件 > ELM_LOGIN 指定的方式 */
async function ensureLogin() {
  if (COOKIE && !FORCE_LOGIN) {
    const missing = taskCookieMissing(COOKIE);
    if (missing.length === 0) return true;
    log(`⚠ ELM_COOKIE 缺少任务登录字段: ${missing.join(', ')}`);
  }
  try {
    if (!FORCE_LOGIN && fs.existsSync(COOKIE_FILE)) {
      const ck = fs.readFileSync(COOKIE_FILE, 'utf8').trim();
      if (ck) {
        const missing = taskCookieMissing(ck);
        if (missing.length === 0) {
          COOKIE = ck;
          log(`已从 ${COOKIE_FILE} 读取登录态`);
          return true;
        }
        log(`⚠ ${COOKIE_FILE} 不是完整饿了么登录态，缺少: ${missing.join(', ')}`);
      }
    }
  } catch (e) { /* 忽略 */ }

  if (LOGIN_METHOD === 'sms') return smsLoginFlow();
  if (LOGIN_METHOD === 'yyb' || LOGIN_METHOD === 'yyb_qr') return yybLoginFlow();

  log('❌ 未配置 ELM_COOKIE，也未指定登录方式');
  log('   可选：ELM_LOGIN=sms + ELM_PHONE 走短信登录；ELM_LOGIN=yyb + YYB_REF/YYB_TOKEN，或 ELM_LOGIN=yyb_qr 微信扫码');
  return false;
}

/* ───────────────────── 主流程 ───────────────────── */

/* 多账号读取: 遍历 ELM_COOKIE 及 ELM_COOKIE_<uid> 变量
 * (前缀可用 ELM_ENV_PREFIX 覆盖, 与插件 elm.varName 对应)
 * 每个值可按 & / 换行放多段; 段格式:
 *   纯cookie | cookie#代理 | cookie#备注#代理
 *   也兼容 base64 编码的上述格式(防面板 .env 把 # 当注释)
 * 字段识别: 含 = 的是 cookie, 含 :// 的是代理, 其余是备注 */
function parseAccounts() {
  const ENV_PREFIX = String(process.env.ELM_ENV_PREFIX || 'ELM_COOKIE')
    .replace(/[^\w]/g, '') || 'ELM_COOKIE';
  const segs = [];
  const push = (seg, uid) => {
    let remark = '', ck = '', proxy = '';
    for (const p of seg.split('#')) {
      if (!ck && /=/.test(p) && !/^[a-zA-Z][\w+.-]*:\/\//.test(p)) ck = p;
      else if (!proxy && /^[a-zA-Z][\w+.-]*:\/\//.test(p)) proxy = p;
      else if (!remark) remark = p;
    }
    if (ck) segs.push({ remark, ck, proxy, uid: uid || '' });
  };
  for (const key of Object.keys(process.env)) {
    if (key !== ENV_PREFIX && !key.startsWith(ENV_PREFIX + '_')) continue;
    if (key.endsWith('_FILE')) continue;
    const uid = key === ENV_PREFIX ? '' : key.slice(ENV_PREFIX.length + 1);
    const raw = String(process.env[key] || '');
    for (let seg of raw.split(/[&\n]+/)) {
      seg = seg.trim();
      if (!seg) continue;
      if (/^[A-Za-z0-9+/=]+$/.test(seg) && seg.length % 4 === 0 && seg.length >= 16) {
        try {
          const dec = Buffer.from(seg, 'base64').toString('utf8').trim();
          if (dec && /=/.test(dec)) seg = dec;
        } catch (e) { /* 保留原样 */ }
      }
      for (const line of seg.split('\n')) push(line.trim(), uid);
    }
  }
  return segs;
}

async function runAccount() {
  log('===== 饿了么 会员权益中心 自动化开始 =====');
  jitterGeo();
  if (!(await ensureLogin())) return;
  if (!getToken(COOKIE)) {
    log('   Cookie 暂无 _m_h5_tk，首次请求会自动向网关换取');
  }

  // 1. 首页聚合：拿 missionCollectionId 和签到 copyId
  let missionCollectionId = null;
  let copyId = null;
  let signInRewardStrategy = null;
  let award = null;
  try {
    const hp = await getHomepage();
    if (!hp) {
      log('❌ 登录态校验失败，停止本次任务，不继续发送签到/领奖请求');
      return;
    }
    missionCollectionId = hp.missionCollectionId;
    copyId = hp.copyId;
    signInRewardStrategy = hp.signInRewardStrategy;
    award = hp.award;
  } catch (e) {
    log(`❌ 首页聚合异常: ${e.message}`);
    return;
  }

  // 2. 签到（依赖首页返回的 copyId、签到模式和今日奖励参数）
  await humanPause(PACE.nav);
  try {
    await doSignin(copyId, signInRewardStrategy, award);
  } catch (e) {
    log(`❌ 签到异常: ${e.message}`);
  }

  if (!missionCollectionId) {
    log('⚠ 未拿到 missionCollectionId，无法查询任务，流程终止');
    log('   （任务链路依赖首页聚合返回的该 ID）');
    return;
  }

  // 3. 查询任务
  await humanPause(PACE.nav);
  let tasks = [];
  try {
    tasks = await queryTasks(missionCollectionId);
  } catch (e) {
    log(`❌ 查询任务异常: ${e.message}`);
  }

  // 4. 第一轮：对浏览型任务（PAGEVIEW）上报埋点 + 点击型任务（commercial_click）触发
  log('\n===== 第一轮：浏览 + 点击任务埋点 =====');
  for (const task of tasks) {
    if (isPageviewTask(task)) {
      const title = taskTitle(task);
      log(`\n── 浏览任务: ${title} ──`);
      try {
        const rv = await reportPageview(task);
        if (rv.ok) log(`   👁 浏览埋点上报成功`);
        else log(`   ⚠ 浏览埋点: ${rv.msg}`);
      } catch (e) {
        log(`   ⚠ 浏览埋点异常: ${e.message}`);
      }
      await humanPause(PACE.task);
    } else if (isTriggerTask(task)) {
      // THIRD 任务（点击店铺/跳转第三方）：需要触发 finalStageCount 次
      const title = taskTitle(task);
      const sc = (task.actionConfig.actionValue || {}).scenceCode;
      const total = (task.actionConfig.actionValue || {}).finalStageCount || 1;
      const done = (task.stage && task.stage.count) || 0;
      const need = total - done;
      log(`\n── THIRD任务: ${title} (${sc}, 需${total}次, 已${done}次, 补${need}次) ──`);
      for (let i = 0; i < need; i++) {
        try {
          const rv = await reportTrigger(task);
          if (rv.ok) log(`   👆 触发埋点 ${i + 1}/${need} 上报成功`);
          else log(`   ⚠ 触发埋点 ${i + 1}/${need}: ${rv.msg}`);
        } catch (e) {
          log(`   ⚠ 触发埋点异常: ${e.message}`);
        }
        await humanPause(PACE.click);
      }
    }
  }

  // 5. 第二轮：停留一段时间（模拟回到任务页），重新查询后领奖
  await humanPause(PACE.round);
  log('\n===== 第二轮：重新查询 + 领取奖励 =====');
  let tasks2 = [];
  try {
    tasks2 = await queryTasks(missionCollectionId);
  } catch (e) {
    log(`❌ 重新查询任务异常: ${e.message}`);
  }
  await claimPass(tasks2);

  // 命中奖励风控：冷却一段时间后有界重试一次（风控多为临时降权；
  // 重试仍被拦则本轮结束，等下一次定时运行，不继续刷接口）
  if (rewardBlocked && RISK_RETRY) {
    const wait = RISK_BACKOFF_MS + jitter(0, 120000);
    log(`\n⏳ 奖励接口被风控拦截，冷却 ${(wait / 60000).toFixed(1)} 分钟后重试一次`);
    await sleep(wait);
    rewardBlocked = false;
    let tasks3 = [];
    try {
      tasks3 = await queryTasks(missionCollectionId);
    } catch (e) {
      log(`❌ 重试前查询任务异常: ${e.message}`);
    }
    await claimPass(tasks3);
    if (rewardBlocked) {
      log('   ⏭ 重试仍被风控拦截，本轮结束，等待下次定时运行');
    }
  }

  // 把刷新过 _m_h5_tk 的 cookie 回写文件，下次运行直接用
  try { fs.writeFileSync(COOKIE_FILE, COOKIE); } catch (e) { /* 忽略 */ }

  log('\n===== 执行完成 =====');
}

async function main() {
  /* 登录任务(ELM_LOGIN/FORCE_LOGIN): 只登录拿cookie, 不跑任务,
   * 防止任务输出(如"今日已签到")干扰调用方的结果判定 */
  if (LOGIN_METHOD || FORCE_LOGIN) {
    log('===== 登录模式：仅执行登录 =====');
    const ok = await ensureLogin();
    if (!ok) process.exitCode = 1;
    return;
  }
  /* 单账号: 走原有流程 */
  const accounts = parseAccounts();
  if (accounts.length <= 1) {
    DEVICE = loadDevice(process.env.ELM_RESET_DEVICE === '1');
    UA = process.env.ELM_UA || DEVICE.ua;
    await runAccount();
    return;
  }
  /* 多账号: 逐账号独立 cookie/设备档案/代理, 串行+随机间隔模拟真人 */
  log(`===== 共 ${accounts.length} 个账号, 串行执行 =====`);
  const defCookieFile = process.env.ELM_COOKIE_FILE || path.join(__dirname, 'elm_cookie.txt');
  const defDeviceFile = process.env.ELM_DEVICE_FILE || path.join(__dirname, 'elm_device_profile.json');
  for (let i = 0; i < accounts.length; i++) {
    const acc = accounts[i];
    const tag = acc.remark || acc.uid || `账号${i + 1}`;
    log(`\n########## [${i + 1}/${accounts.length}] ${tag} ##########`);
    PROXY_URL = acc.proxy || process.env.ELM_PROXY || '';
    resetProxy();
    const suffix = acc.uid || String(i + 1);
    COOKIE_FILE = defCookieFile.replace(/\.txt$/, `_${suffix}.txt`);
    DEVICE_FILE = defDeviceFile.replace(/\.json$/, `_${suffix}.json`);
    // 优先用上次运行刷新过的 cookie 文件(_m_h5_tk 较新)，否则用面板变量值
    COOKIE = acc.ck;
    try {
      if (fs.existsSync(COOKIE_FILE)) {
        const fck = fs.readFileSync(COOKIE_FILE, 'utf8').trim();
        if (fck && taskCookieMissing(fck).length === 0) {
          const fd = str2dict(fck), ad = str2dict(acc.ck);
          if (fd.cookie2 === ad.cookie2) COOKIE = fck;
        }
      }
    } catch (e) { /* 忽略 */ }
    // 每账号独占设备指纹：小程序 UA + utdid（405 行为受限的决定项）
    DEVICE = loadDevice(process.env.ELM_RESET_DEVICE === '1');
    UA = process.env.ELM_UA || DEVICE.ua;
    rewardBlocked = false;
    try {
      await runAccount();
    } catch (e) {
      log(`❌ 账号[${tag}]执行异常: ${e.message}`);
    }
    if (i < accounts.length - 1) {
      const gap = 30000 + Math.random() * 60000;
      log(`账号间隔 ${(gap / 1000).toFixed(0)} 秒…`);
      await sleep(gap);
    }
  }
  log('\n===== 全部账号执行完毕 =====');
}

main().catch((e) => {
  log(`❌ 未捕获异常: ${e.stack || e.message}`);
});

// 当前脚本来自于 http://script.diyunzz.cn/ 脚本库下载！
// 官方青龙脚本群1：712734450
// 官方青龙脚本群2：176166044
// 项目通知群：1009084941
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。