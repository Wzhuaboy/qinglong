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

/*
 * 哈希玛特 HashMart · 青龙脚本
 * 
 * 项目地址：https://idjdjd.zhuafs.com/app/?invite_code=S763FVH7
 * ============================ 环境变量 ============================
 * HM            必填  账号。支持两种写法，多个用 & 或换行分隔：
 *                      手机号----密码
 *                      eyJhbGci...（token）
 * HM_DEVICE     选填  设备 ID，不填用内置默认值
 * HM_MODE       选填  all | hash | dividend | status  默认 all
 *                      all 全跑 / hash 只领哈希卡 / dividend 只领分红股份 / status 只查状态
 * HM_WORKERS    选填  并发账号数                              默认 1
 * HM_DELAY_MIN  选填  每个广告后的随机延迟下限（秒）          默认 10
 * HM_DELAY_MAX  选填  每个广告后的随机延迟上限（秒）          默认 20
 * HM_DEBUG      选填  1/0 打印每个请求                        默认 0
 *
 * 依赖：Node.js >= 14，零第三方库（原生 https + zlib + crypto）
 * ==================================================================
 *
 * 
 *   ① 哈希卡      /activity/sign/info 查 → /activity/sign/watch 领（每看一个广告 +哈希）
 *   ② 分红股份    /dividend/info 查      → /dividend/watch 领（每看一个广告 +股份）
 *   前置：账号需已实名（/user/realname/info verified=1），未实名自动跳过领取
 * 
 *    项目地址：https://idjdjd.zhuafs.com/app/?invite_code=S763FVH7
 * 
 */

/* ================================================================
 * ★★★★★  账号密码就填在下面这一行  ★★★★★
 *   格式：手机号----密码   （中间是 4 个短横线）
 *   多个账号用 & 或换行分隔
 *   例子：'18930663184----474926&13800000000----abc123'
 *
 *   填了这行就能直接跑，不必再去青龙「环境变量」里配 HM；
 *   如果两处都填了，以青龙环境变量里的 HM 为准。
 * ================================================================ */
const HM_ACCOUNTS_RAW = '';      // ←←← 在这里填，例：'18930663184----474926'

const https = require('https');
const zlib = require('zlib');
const crypto = require('crypto');

/* ============================ 常量 ============================ */
const BASE = 'https://idjdjd.zhuafs.com/api';
const HM_APP = '7d3f9c1a5e8b4026af1c9d2e6b8a4f03';
const UA = 'Mozilla/5.0 (Linux; Android 10; MI 8 Build/QKQ1.190828.002; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/83.0.4103.101 Mobile Safari/537.36 uni-app (Immersed/32.363636) Html5Plus/1.0';
// 设备指纹：App 端按本机 android_id 生成，青龙没有本机环境，默认用固定值，可用 HM_DEVICE 覆盖
const DEFAULT_DEVICE_ID = 'dvmvpblam2hvlgx0nu';

/* ============================ 环境 ============================ */
function env(key, def) {
    const v = process.env[key];
    return (v === undefined || v === '') ? def : v;
}
function envBool(key, def) {
    const v = env(key, '');
    if (v === '') return def;
    return !(v === '0' || v.toLowerCase() === 'false' || v.toLowerCase() === 'no');
}
function envInt(key, def) {
    const n = parseInt(env(key, ''), 10);
    return isNaN(n) ? def : n;
}

const CFG = {
    deviceId: env('HM_DEVICE', DEFAULT_DEVICE_ID),
    mode: env('HM_MODE', 'all').toLowerCase(),
    workers: Math.max(1, envInt('HM_WORKERS', 1)),
    delayMin: Math.max(0, envInt('HM_DELAY_MIN', 10)),
    delayMax: Math.max(0, envInt('HM_DELAY_MAX', 20)),
    debug: envBool('HM_DEBUG', false),
};
if (CFG.delayMax < CFG.delayMin) CFG.delayMax = CFG.delayMin;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ============================ 日志 ============================ */
let LOG_BUFFER = [];

function ts() {
    const d = new Date();
    const p = (n) => (n < 10 ? '0' + n : '' + n);
    return p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
}
function log(msg) {
    console.log('[' + ts() + '] ' + msg);
    LOG_BUFFER.push(msg);
}

/* ============================ 工具 ============================ */
function toInt(v, d) { const n = parseInt(v, 10); return isNaN(n) ? (d || 0) : n; }
function num(v, d) { const n = Number(v); return isNaN(n) ? (d || 0) : n; }
function flag(v) { return v === true || Number(v) === 1; }
function mask(v) {
    v = '' + (v || '');
    return v.length <= 14 ? v : v.substring(0, 8) + '...' + v.substring(v.length - 6);
}
function preview(o, lim) {
    try {
        const s = (typeof o === 'string') ? o : JSON.stringify(o);
        return s ? s.substring(0, lim || 300) : '';
    } catch (e) { return ('' + o).substring(0, lim || 300); }
}
function randInt(lo, hi) { return Math.floor(Math.random() * (hi - lo + 1)) + lo; }
function randomHex(n) { return crypto.randomBytes(Math.ceil(n / 2)).toString('hex').substring(0, n); }

// 随机广告间隔（秒）
function randomDelaySec() {
    if (CFG.delayMax <= CFG.delayMin) return CFG.delayMin;
    return randInt(CFG.delayMin, CFG.delayMax);
}


function formEncode(obj) {
    return Object.keys(obj).map(
        (k) => encodeURIComponent(k) + '=' + encodeURIComponent(obj[k] === null || obj[k] === undefined ? '' : obj[k])
    ).join('&');
}

function request(method, apiPath, formObj, token) {
    const urlStr = apiPath.indexOf('http') === 0 ? apiPath : BASE + apiPath;
    const u = new URL(urlStr);

    const headers = {
        'X-Form-Id-List': '[]',
        'X-Requested-With': 'XMLHttpRequest',
        'X-Hm-App': HM_APP,
        'user-agent': UA,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Encoding': 'gzip',
    };
    if (token) headers['authorization'] = 'Bearer ' + token;

    let bodyStr = null;
    if (formObj !== null && formObj !== undefined && method !== 'GET') {
        bodyStr = (typeof formObj === 'string') ? formObj : formEncode(formObj);
        headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8';
        headers['Content-Length'] = Buffer.byteLength(bodyStr);
    }

    if (CFG.debug) log('    -> ' + method + ' ' + apiPath + (bodyStr ? '  ' + bodyStr : ''));

    return new Promise((resolve) => {
        const req = https.request({
            hostname: u.hostname,
            port: u.port || 443,
            path: u.pathname + u.search,
            method: method,
            headers: headers,
            timeout: 20000,
        }, (res) => {
            const chunks = [];
            res.on('data', (c) => chunks.push(c));
            res.on('end', () => {
                let raw = Buffer.concat(chunks);
                const enc = ('' + (res.headers['content-encoding'] || '')).toLowerCase();
                if (enc.indexOf('gzip') >= 0) {
                    try { raw = zlib.gunzipSync(raw); } catch (e) { }
                } else if (raw.length > 2 && raw[0] === 0x1f && raw[1] === 0x8b) {
                    try { raw = zlib.gunzipSync(raw); } catch (e) { }
                }
                const text = raw.toString('utf8');
                if (CFG.debug) log('    <- ' + res.statusCode + ' ' + preview(text, 600));
                let json = null;
                try { json = JSON.parse(text); } catch (e) { json = null; }
                resolve({ status: res.statusCode, raw: text, json: json });
            });
        });

        req.on('timeout', () => { req.destroy(new Error('TIMEOUT')); });
        req.on('error', (e) => resolve({ status: -1, raw: 'CONN:' + e.message, json: null }));

        if (bodyStr !== null) req.write(bodyStr);
        req.end();
    });
}

const get = (p, token) => request('GET', p, null, token);
const post = (p, body, token) => request('POST', p, body || {}, token);

// 业务成功：HTTP 2xx 且 body.code === 0
function bizOk(res) {
    if (!res || res.status < 200 || res.status >= 300 || !res.json) return false;
    return num(res.json.code, -1) === 0;
}
function msgOf(res) {
    if (!res) return 'null';
    if (res.json) return (res.json.msg || res.json.message || res.json.error || res.json.code || '') + '';
    return preview(res.raw, 200);
}

/* ============================ 账号登录 ============================ */
async function login(phone, password) {
    const r = await post('/user/login/loginByAccount', {
        phone: phone,
        code: '',
        password: password,
        invite_code: '',
    }, null);

    if (bizOk(r) && r.json.data && r.json.data.token) {
        return { ok: true, token: r.json.data.token, msg: r.json.msg || '登录成功' };
    }
    return { ok: false, msg: (r.json && r.json.msg) ? r.json.msg : ('登录失败 ' + r.status) };
}

/* ============================ 实名 ============================ */
// 返回 1 已实名 / 0 未实名 / null 查询失败
async function realnameVerified(token) {
    const r = await get('/user/realname/info', token);
    if (bizOk(r) && r.json.data) return num(r.json.data.verified, 0) === 1 ? 1 : 0;
    return null;
}


async function signInfo(token) {
    const r = await get('/activity/sign/info', token);
    if (!bizOk(r)) return null;
    return r.json.data || {};
}

async function signWatch(token) {
    const r = await post('/activity/sign/watch', { device_id: CFG.deviceId }, token);
    if (bizOk(r) && r.json.data) {
        return { ok: true, gain: num(r.json.data.gain, 0), msg: r.json.data.tip || r.json.msg || '领取成功', data: r.json.data };
    }
    return { ok: false, msg: (r.json && r.json.msg) ? r.json.msg : '领取失败' };
}

async function runHash(token, tag) {
    const info = await signInfo(token);
    if (!info) { log(tag + '读取哈希面板失败'); return; }

    if (num(info.done_today, 0) === 1) { log(tag + '今日哈希卡已完成'); return; }
    if (!flag(info.can_watch)) { log(tag + '哈希卡当前不可领'); return; }

    let times = 0;
    while (times < 6) {
        times++;
        const r = await signWatch(token);
        if (!r.ok) { log(tag + '领哈希失败：' + r.msg); break; }

        const d = r.data || {};
        log(tag + '哈希卡 +' + r.gain + ' · ' + r.msg +
            ' · 今日 ' + num(d.today_ads, 0) + '/' + num(d.need_ads, 0) +
            ' · 共 ' + num(d.cards, 0) + ' 张');

        if (!flag(d.can_watch) || num(d.done_today, 0) === 1) break;

        const wait = randomDelaySec();
        if (wait > 0) { log(tag + '等待 ' + wait + ' 秒'); await sleep(wait * 1000); }
    }
}


async function dividendInfo(token) {
    const r = await get('/dividend/info', token);
    if (!bizOk(r)) return null;
    return r.json.data || {};
}

async function dividendWatch(token) {
    const r = await post('/dividend/watch', { device_id: CFG.deviceId }, token);
    if (bizOk(r)) {
        return { ok: true, msg: r.json.msg || '获得股份', data: r.json.data || {} };
    }
    return { ok: false, msg: (r.json && r.json.msg) ? r.json.msg : '领取失败' };
}

async function runDividend(token, tag) {
    const d0 = await dividendInfo(token);
    if (!d0) { log(tag + '读取分红面板失败'); return; }

    if (num(d0.status, 0) !== 1) { log(tag + '分红活动未开启'); return; }

    const limit = num(d0.daily_ad_limit, 0);
    const done0 = num(d0.today_ads, 0);
    if (limit > 0 && done0 >= limit) { log(tag + '今日股份已领完 ' + done0 + '/' + limit); return; }
    if (!flag(d0.can_watch)) { log(tag + '股份当前不可领'); return; }

    let c = 0;
    while (c < 10) {
        c++;
        const r = await dividendWatch(token);
        if (!r.ok) { log(tag + '领股份失败：' + r.msg); break; }

        const d = r.data || {};
        log(tag + '股份 +' + num(d.shares, 0) + ' · ' + r.msg +
            ' · 今日 ' + num(d.today_ads, 0) + '/' + limit +
            ' · 剩余 ' + num(d.left_ads, 0) + ' 次');

        if (limit > 0 && num(d.today_ads, 0) >= limit) break;
        if (num(d.left_ads, 0) <= 0) break;

        const wait = randomDelaySec();
        if (wait > 0) { log(tag + '等待 ' + wait + ' 秒'); await sleep(wait * 1000); }
    }
}


async function dumpStatus(token, tag) {
    log(tag + '状态总览');
    const v = await realnameVerified(token);
    log(tag + '   实名 ' + (v === null ? '查询失败' : (v === 1 ? '已实名' : '未实名')));

    const s = await signInfo(token);
    if (s) log(tag + '   哈希卡 今日' + num(s.today_ads, 0) + '/' + num(s.need_ads, 0) +
        ' 完成' + num(s.done_today, 0) + ' 可领' + (flag(s.can_watch) ? '1' : '0') + ' 共' + num(s.cards, 0) + '张');
    else log(tag + '   哈希卡 查询失败');

    const d = await dividendInfo(token);
    if (d) log(tag + '   分红 状态' + num(d.status, 0) + ' 今日' + num(d.today_ads, 0) + '/' + num(d.daily_ad_limit, 0) +
        ' 可领' + (flag(d.can_watch) ? '1' : '0'));
    else log(tag + '   分红 查询失败');
}


function modeFlags() {
    const m = CFG.mode;
    if (m === 'hash') return { hash: true, dividend: false };
    if (m === 'dividend') return { hash: false, dividend: true };
    if (m === 'status') return { hash: false, dividend: false };
    return { hash: true, dividend: true };
}


async function runAccount(idx, total, tokenOrAcc) {
    const tag = (total > 1) ? ('[' + idx + '/' + total + '] ') : '';
    log(tag + '开始');

    let token = '';
    if (tokenOrAcc.indexOf('----') > 0) {
        const parts = tokenOrAcc.split('----');
        const phone = parts[0].trim(), pwd = parts[1].trim();
        const lr = await login(phone, pwd);
        if (!lr.ok) { log(tag + '登录失败：' + lr.msg); return false; }
        token = lr.token;
        log(tag + '已登录 ' + phone + '  ' + mask(token));
    } else {
        token = tokenOrAcc;
    }

    const v = await realnameVerified(token);
    if (v === null) { log(tag + 'token 失效或读取实名失败'); return false; }
    if (v === 0) { log(tag + '未实名，跳过领取'); return false; }

    const f = modeFlags();
    if (f.hash) await runHash(token, tag);
    if (f.dividend) await runDividend(token, tag);

    if (CFG.mode === 'status') await dumpStatus(token, tag);

    log(tag + '完成');
    return true;
}


function parseAccounts(text) {
    const arr = [];
    const ls = ('' + text).replace(/\r/g, '').split(/[\n&]+/);
    for (let i = 0; i < ls.length; i++) {
        const v = ls[i].trim();
        if (v) arr.push(v);
    }
    return arr;
}


async function runWithLimit(list, limit, worker) {
    const results = new Array(list.length);
    let cursor = 0;

    async function lane() {
        while (true) {
            const i = cursor++;
            if (i >= list.length) return;
            try {
                results[i] = await worker(i, list[i]);
            } catch (e) {
                log('账号[' + (i + 1) + '] 异常 ' + (e && e.message ? e.message : e));
                results[i] = false;
            }
        }
    }

    const lanes = [];
    const n = Math.min(limit, list.length);
    for (let i = 0; i < n; i++) lanes.push(lane());
    await Promise.all(lanes);
    return results;
}

/* ============================ 通知 ============================ */
async function notify(title, content) {
    try {
        const sendNotify = require('./sendNotify');
        if (typeof sendNotify === 'function') await sendNotify(title, content);
    } catch (e) {
        try {
            const mod = require('./sendNotify.js');
            const fn = mod && (mod.sendNotify || mod.default);
            if (typeof fn === 'function') await fn(title, content);
        } catch (e2) { }
    }
}

/* ============================ 入口 ============================ */
(async () => {
    const raw = env('HM', '') || env('HM_ACCOUNT', '') || HM_ACCOUNTS_RAW;
    const list = parseAccounts(raw);

    log('哈希玛特 HashMart');
    log('账号 ' + list.length + ' 个  并发 ' + CFG.workers + '  模式 ' + CFG.mode);
    log('接口 ' + BASE + '  设备ID ' + CFG.deviceId);

    if (list.length === 0) {
        log('未配置账号：请在青龙环境变量里配 HM，或直接填脚本顶部 HM_ACCOUNTS_RAW');
        return;
    }

    const t0 = Date.now();
    const results = await runWithLimit(list, CFG.workers, (i, acc) =>
        runAccount(i + 1, list.length, acc));

    let s = 0;
    for (let k = 0; k < results.length; k++) if (results[k]) s++;

    const cost = Math.round((Date.now() - t0) / 1000);
    log('全部完成 成功 ' + s + ' / ' + list.length + '  耗时 ' + cost + 's');

    const tail = LOG_BUFFER.slice(-60).join('\n');
    await notify('哈希玛特 成功 ' + s + '/' + list.length, tail);
})().catch((e) => {
    log('运行异常 ' + (e && e.stack ? e.stack : e));
});


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