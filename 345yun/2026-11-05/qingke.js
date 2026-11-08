// 当前脚本来自于 http://script.345yun.cn 脚本库下载！
// 当前脚本来自于 http://2.345yun.cn 脚本库下载！
// 当前脚本来自于 http://2.345yun.cc 脚本库下载！
// 脚本库官方QQ群1群: 429274456
// 脚本库官方QQ群2群: 1077801222
// 脚本库官方QQ群3群: 433030897
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。

#!/usr/bin/env node
// cron: 40 8,12,18 * * *
// 手机号注册，下载APP，登录后，先实名认证（姓名，身份证号），然后填入环境变量运行脚本

/**
 * 轻客 APP 红包自动领取（青龙 Node 脚本，函数式实现，无 class）
 *
 *轻客注册地址 : https://qingke.junfengkeji.top/s/kJhFUADTUghiTJiHOoGaaQ
 * 依赖：无第三方库，仅 Node.js 内置模块（建议 Node 16+）。
 *
 * 环境变量：
 *   QINGKE_ACCOUNTS      必填，多账号，每行 手机号#密码，换行或 & 分隔，例如：
 *                        13358981037#goodbye123&13900001111#pass456
 *   QINGKE_DEVICE_ID     可选，设备 ID，默认按手机号生成固定值
 *   QINGKE_MAX_CLAIM     可选，单次运行最多领几个红包，默认 5
 *   QINGKE_SESSION_SECONDS 可选，浏览时长秒数，默认 30
 *   QINGKE_LIST_PAGES    可选，列表翻页数，默认 3
 */

const crypto = require('crypto');
const http = require('http');
const https = require('https');
const tls = require('tls');

const BASE_URL = (process.env.QINGKE_BASE_URL || 'https://qingke.junfengkeji.top').replace(/\/+$/, '');
const APP_VERSION = '2.1.2';
const USER_AGENT =
  'Mozilla/5.0 (Linux; Android 10; M2007J17C Build/QKQ1.200628.002; wv) ' +
  'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/87.0.4280.101 ' +
  'Mobile Safari/537.36 uni-app (Immersed/33.090908) Html5Plus/1.0';

function log(msg) {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  console.log(`[${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}] ${msg}`);
}

const nowMs = () => Date.now();

function randStr(n = 10) {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let s = '';
  for (let i = 0; i < n; i++) s += chars.charAt(Math.floor(Math.random() * chars.length));
  return s;
}

// 生成抓包里那种 前缀-毫秒时间戳-随机串 的 sessionNo / idempotencyKey
const genKey = (prefix, n = 10) => `${prefix}-${nowMs()}-${randStr(n)}`;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const randSleep = (min, max) => {
  const ms = min + Math.floor(Math.random() * (max - min + 1));
  return sleep(ms);
};

const maskPhone = (p) => (p && p.length >= 7 ? `${p.slice(0, 3)}****${p.slice(-4)}` : p);

/* ---------------- 代理 / HTTPS 请求 ---------------- */

// 支持 HTTPS_PROXY / ALL_PROXY 环境变量的 CONNECT 隧道
function getProxy() {
  const raw =
    process.env.HTTPS_PROXY || process.env.https_proxy ||
    process.env.ALL_PROXY || process.env.all_proxy || '';
  if (!raw) return null;
  try {
    return new URL(raw);
  } catch (e) {
    return null;
  }
}

function bypassProxy(host) {
  const raw = process.env.NO_PROXY || process.env.no_proxy || '';
  if (!raw) return false;
  const h = host.toLowerCase();
  return raw.split(',').map((s) => s.trim().toLowerCase()).filter(Boolean).some((entry) => {
    if (entry === '*') return true;
    const e = entry.replace(/^\./, '');
    return h === e || h.endsWith(`.${e}`);
  });
}

function createProxyTunnel(proxy, host, port, timeout) {
  return new Promise((resolve, reject) => {
    const headers = { Host: `${host}:${port}` };
    if (proxy.username) {
      const auth = `${decodeURIComponent(proxy.username)}:${decodeURIComponent(proxy.password)}`;
      headers['Proxy-Authorization'] = `Basic ${Buffer.from(auth).toString('base64')}`;
    }
    const req = http.request({
      host: proxy.hostname,
      port: proxy.port || 80,
      method: 'CONNECT',
      path: `${host}:${port}`,
      headers,
      timeout,
    });
    req.on('connect', (res, socket) => {
      if (res.statusCode !== 200) {
        socket.destroy();
        reject(new Error(`proxy CONNECT ${res.statusCode}`));
        return;
      }
      const tlsSocket = tls.connect({ socket, servername: host }, () => resolve(tlsSocket));
      tlsSocket.once('error', reject);
    });
    req.on('timeout', () => req.destroy(new Error('proxy timeout')));
    req.on('error', reject);
    req.end();
  });
}

// 基于 Node 内置 https 的请求，返回解析后的 JSON（失败时返回带 code 的对象）
async function httpsRequest(method, url, { headers = {}, body = null, timeout = 25000 } = {}) {
  const u = new URL(url);
  const port = Number(u.port) || 443;
  const proxy = getProxy();
  let tunnelSocket = null;
  if (proxy && !bypassProxy(u.hostname)) {
    try {
      tunnelSocket = await createProxyTunnel(proxy, u.hostname, port, timeout);
    } catch (e) {
      return { code: 'proxy_error', message: `代理连接失败: ${e.message}`, _status: 0 };
    }
  }

  return new Promise((resolve) => {
    const opts = {
      method,
      hostname: u.hostname,
      port,
      path: u.pathname + u.search,
      headers,
      timeout,
    };
    if (tunnelSocket) {
      const agent = new https.Agent({ keepAlive: false });
      agent.createConnection = () => tunnelSocket;
      opts.agent = agent;
    }
    const req = https.request(opts, (res) => {
      let raw = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        raw += chunk;
      });
      res.on('end', () => {
        let data;
        try {
          data = JSON.parse(raw);
        } catch (e) {
          data = { code: 'invalid_response', message: raw.slice(0, 200) };
        }
        if (!data || typeof data !== 'object') {
          data = { code: 'invalid_response', message: String(data) };
        }
        data._status = res.statusCode;
        resolve(data);
      });
    });
    req.on('timeout', () => req.destroy(new Error('timeout')));
    req.on('error', (e) => resolve({ code: 'network_error', message: e.message, _status: 0 }));
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

/* ---------------- 配置 / 账号 ---------------- */

function loadConfig() {
  const num = (v, def) => {
    const n = parseInt(v, 10);
    return Number.isFinite(n) && n > 0 ? n : def;
  };
  return {
    maxClaim: num(process.env.QINGKE_MAX_CLAIM, 5),
    sessionSeconds: num(process.env.QINGKE_SESSION_SECONDS, 30),
    listPages: num(process.env.QINGKE_LIST_PAGES, 5),
    deviceId: (process.env.QINGKE_DEVICE_ID || '').trim(),
  };
}

function parseAccounts() {
  const accounts = [];
  const raw = (process.env.QINGKE_ACCOUNTS || '').trim();
  if (!raw) return accounts;
  raw.replace(/&/g, '\n').split(/\r?\n/).forEach((line) => {
    const t = line.trim();
    if (!t) return;
    const idx = t.indexOf('#');
    if (idx <= 0) return;
    const phone = t.slice(0, idx).trim();
    const password = t.slice(idx + 1).trim();
    if (phone && password) accounts.push({ phone, password });
  });
  return accounts;
}

function defaultDeviceId(phone) {
  const md5 = crypto.createHash('md5').update(phone).digest('hex');
  const digits = (md5.replace(/\D/g, '') + '0000000000000').slice(0, 13);
  return `platform-${digits}-${md5.slice(0, 10)}`;
}

// 账号上下文对象（替代 class 实例）
function createAccount(phone, password, deviceId) {
  return {
    phone,
    password,
    deviceId: deviceId || defaultDeviceId(phone),
    token: null,
  };
}

/* ---------------- 接口封装 ---------------- */

function buildHeaders(acc, auth = true) {
  const h = {
    'X-Qingke-Session-Version': '2',
    'X-Device-Id': acc.deviceId,
    'X-Qingke-App-Code': 'root',
    'X-App-Version': APP_VERSION,
    'Content-Type': 'application/json',
    'user-agent': USER_AGENT,
  };
  if (auth && acc.token) h.Authorization = `Bearer ${acc.token}`;
  return h;
}

async function request(acc, method, path, { body = null, params = null, auth = true } = {}) {
  let url = BASE_URL + path;
  if (params) {
    const qs = new URLSearchParams(params).toString();
    if (qs) url += (url.includes('?') ? '&' : '?') + qs;
  }
  const headers = Object.assign({}, buildHeaders(acc, auth), { 'Accept-Encoding': 'identity' });
  if (body) headers['Content-Length'] = Buffer.byteLength(JSON.stringify(body));
  return httpsRequest(method, url, { headers, body, timeout: 25000 });
}

async function api(acc, method, path, options = {}) {
  let res = await request(acc, method, path, options);
  if (options.auth !== false && res._status === 401) {
    log('登录态失效，重新登录');
    await login(acc);
    res = await request(acc, method, path, options);
  }
  return res;
}

async function login(acc) {
  const res = await request(acc, 'POST', '/api/user/login', {
    body: { phone: acc.phone, password: acc.password },
    auth: false,
  });
  if (res.code !== 'SUCCESS') throw new Error(`登录失败: ${res.code} ${res.message || ''}`);
  const data = res.data || {};
  acc.token = data.accessToken || data.token;
  if (!acc.token) throw new Error('登录成功但未返回 token');
  const user = data.userInfo || {};
  log(`登录成功，用户 ${user.userCode || '-'}（${maskPhone(acc.phone)}）`);
}

async function hallProjects(acc, pages = 3) {
  const items = [];
  const seen = new Set();
  for (let page = 1; page <= pages; page++) {
    const res = await api(acc, 'GET', '/api/user/hall/projects', {
      params: { page, pageSize: 20, sortMode: 'all' },
    });
    if (res.code !== 'SUCCESS') {
      log(`列表查询失败: ${res.message}`);
      break;
    }
    const pageItems = (res.data && res.data.items) || [];
    for (const it of pageItems) {
      const pid = it.projectId;
      if (pid && !seen.has(pid)) {
        seen.add(pid);
        items.push(it);
      }
    }
    if (pageItems.length < 20) break;
    await randSleep(1000, 2000);
  }
  return items;
}

async function claim(acc, redPacketId, sessionNo) {
  return api(acc, 'POST', `/api/user/post-red-packets/${redPacketId}/claim`, {
    body: {
      sessionNo,
      idempotencyKey: genKey('post-red-packet-claim'),
    },
  });
}

// 浏览一条带红包的文章并领取，成功返回金额，跳过/失败返回 null
async function claimPacket(acc, item, cfg) {
  const rpId = String(item.redPacketId);
  const projectId = String(item.projectId || '');
  const title = String(item.title || '').slice(0, 30);

  const detail = await api(acc, 'GET', `/api/user/post-red-packets/${rpId}/detail`);
  if (detail.code !== 'SUCCESS') {
    log(`[红包 ${rpId}] 详情查询失败: ${detail.message}`);
    return null;
  }
  const d = detail.data || {};
  if (d.claim) {
    log(`[红包 ${rpId}] 已领取过，跳过（${title}）`);
    return null;
  }
  if (d.status !== 'active') {
    log(`[红包 ${rpId}] 状态 ${d.status}，跳过（${title}）`);
    return null;
  }
  const remain = parseInt(d.remainingCount, 10) || 0;
  if (remain <= 0) {
    log(`[红包 ${rpId}] 剩余 0 份，跳过（${title}）`);
    return null;
  }

  log(`[红包 ${rpId}] 打开文章：${title}`);
  if (projectId) {
    await api(acc, 'GET', `/api/user/hall/projects/${projectId}`, {
      params: { sourceSortMode: 'all' },
    });
    await api(acc, 'POST', `/api/user/hall/projects/${projectId}/detail-view`, {
      body: { sourceSortMode: 'all', viewToken: genKey('hall-detail-view', 11) },
    });
  }
  await randSleep(1000, 2000);

  const sessionNo = genKey('post-red-packet-view');
  const sess = await api(acc, 'POST', `/api/user/post-red-packets/${rpId}/view-sessions`, {
    body: { sessionNo },
  });
  if (sess.code !== 'SUCCESS') {
    log(`[红包 ${rpId}] 创建浏览会话失败: ${sess.message}`);
    return null;
  }
  log(`[红包 ${rpId}] 浏览会话已创建，需停留 ${(sess.data || {}).remainingSeconds}s`);

  // 每 10 秒心跳，累计浏览时长
  let waited = 0;
  while (waited < cfg.sessionSeconds + 10) {
    await sleep(10000);
    waited += 10;
    const hb = await api(acc, 'POST', `/api/user/post-red-packets/${rpId}/view-sessions/heartbeat`, {
      body: { sessionNo },
    });
    if (hb.code !== 'SUCCESS') {
      log(`[红包 ${rpId}] 心跳失败: ${hb.message}`);
      break;
    }
    const hd = hb.data || {};
    log(`[红包 ${rpId}] 已浏览 ${waited}s，剩余 ${hd.remainingSeconds}s，可领取=${hd.eligibleDisplay}`);
    const remaining = Number(hd.remainingSeconds);
    if (Number.isFinite(remaining) && remaining <= 0) break;
  }

  await randSleep(2000, 4000);
  const res = await claim(acc, rpId, sessionNo);
  if (res.code === 'user_real_name_verification_required') {
    log(`[红包 ${rpId}] 领取被拒：账号未实名，请先在 APP 手动完成一次实名认证（脚本不提交实名接口）`);
    return null;
  }
  if (res.code !== 'SUCCESS') {
    log(`[红包 ${rpId}] 领取失败: ${res.code} ${res.message || ''}`);
    return null;
  }

  const amountStr = String((res.data || {}).amount || '0');
  const amount = parseFloat(amountStr) || 0;
  log(`[红包 ${rpId}] 领取成功，金额 ${amountStr} 元（${title}）`);
  return amount;
}

/* ---------------- 运行 ---------------- */

async function runAccount(acc, cfg, index, total) {
  log(`===== 账号 ${index}/${total}: ${maskPhone(acc.phone)} =====`);
  const stats = { account: maskPhone(acc.phone), login: false, claimed: 0, amount: 0 };
  try {
    await login(acc);
  } catch (e) {
    log(`登录失败：${e.message}`);
    return stats;
  }
  stats.login = true;

  const items = await hallProjects(acc, cfg.listPages);
  const packets = items.filter((p) => p && p.hasRedPacket && p.redPacketId);
  log(`列表共 ${items.length} 条，带红包图标 ${packets.length} 条`);

  for (const item of packets) {
    if (stats.claimed >= cfg.maxClaim) break;
    let amount = null;
    try {
      amount = await claimPacket(acc, item, cfg);
    } catch (e) {
      log(`处理红包 ${item.redPacketId} 异常：${e.message}`);
    }
    if (amount !== null) {
      stats.claimed += 1;
      stats.amount += amount;
    }
    await randSleep(2000, 4000);
  }

  log(`账号结束：领取 ${stats.claimed} 个，共 ${stats.amount.toFixed(2)} 元`);
  return stats;
}

async function main() {
  const cfg = loadConfig();
  const accounts = parseAccounts();
  if (!accounts.length) {
    log('未配置账号，请设置 QINGKE_ACCOUNTS（每行 手机号#密码，支持多行或 & 分隔）');
    process.exit(1);
  }

  const lines = [];
  let totalAmount = 0;
  for (let i = 0; i < accounts.length; i++) {
    const acc = createAccount(accounts[i].phone, accounts[i].password, cfg.deviceId);
    let st;
    try {
      st = await runAccount(acc, cfg, i + 1, accounts.length);
    } catch (e) {
      log(`账号 ${i + 1} 运行异常：${e.message}`);
      st = { account: maskPhone(acc.phone), login: false, claimed: 0, amount: 0 };
    }
    totalAmount += st.amount;
    lines.push(`${st.account}：${st.login ? '登录成功' : '登录失败'} ${st.claimed} 个，${st.amount.toFixed(2)} 元`);
    if (i < accounts.length - 1) await randSleep(3000, 6000);
  }

  const summary = `轻客红包 | ${lines.join('；')}；合计 ${totalAmount.toFixed(2)} 元`;
  log(summary);

  try {
    const notify = require('./sendNotify');
    if (notify && typeof notify.sendNotify === 'function') {
      await notify.sendNotify('轻客红包领取结果', summary);
    }
  } catch (e) {
    // 未配置推送时忽略
  }
}

if (require.main === module) {
  main();
}

module.exports = { parseAccounts, createAccount, hallProjects, httpsRequest, loadConfig };


// 当前脚本来自于 http://script.345yun.cn 脚本库下载！
// 当前脚本来自于 http://2.345yun.cn 脚本库下载！
// 当前脚本来自于 http://2.345yun.cc 脚本库下载！
// 脚本库官方QQ群1群: 429274456
// 脚本库官方QQ群2群: 1077801222
// 脚本库官方QQ群3群: 433030897
// 脚本库中的所有脚本文件均来自热心网友上传和互联网收集。
// 脚本库仅提供文件上传和下载服务，不提供脚本文件的审核。
// 您在使用脚本库下载的脚本时自行检查判断风险。
// 所涉及到的 账号安全、数据泄露、设备故障、软件违规封禁、财产损失等问题及法律风险，与脚本库无关！均由开发者、上传者、使用者自行承担。