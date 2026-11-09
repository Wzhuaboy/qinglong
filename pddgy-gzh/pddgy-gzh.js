/*
------------------------------------------
@Description: 拼多多果园公众号版(多多果园) - 微信小程序 code 静默登录 + 每日签到(+浇水)
cron: 28 9,13 * * *
------------------------------------------
变量名：pddgy
变量值：wx_server 里的 openid/账号标识，多账号用 & 或换行分隔（可加 #备注）

依赖变量：
wx_server_url  默认 http://192.168.31.196:8787
wx_auth        必填，wx_server 鉴权值
------------------------------------------
契约（appid wx839691cce7c102bb，重风控站点）：


登录  GET https://mobile.yangkeduo.com/garden_index_lz_0.html?_pdd_fs=1&_pdd_tc=676666&_pdd_sbs=1&fun_id=wechat_app_home&__wls_rt=1&__wls_lt=1&__wls_fm=b&code=${code}&state=BASE
        Cookie = PDDAccessToken=<access_token>; pdd_user_id=<uid>; pdd_user_uin=<uin>; <Set-Cookie>
        鉴权=纯 Cookie（业务请求无 HMAC/签名），业务 URL 追加 ?pdduid=<uid>
        风控：暂无
首页  POST /proxy/api/api/manor-query/proxy/home/page {..., tubetoken}
        -> tubetoken(签到/浇水必需) / water_amount；error_code 40001 = Cookie 失效
签到  POST /proxy/api/api/manor/common/apply/activity?pdduid=<uid>
        body = {type:201811, params:{ui_id:3,type:2}, fun_id:"wechat_app_home", tubetoken, fun_pl:2}
        -> error_code==0 / success==true 成功；已签常见 error_msg 含「已签/重复/已领取」
浇水  POST /proxy/api/api/manor/water/cost {..., cost_water_amount:10, tubetoken}（附带，非核心，失败不影响签到判定）
app_id=33 / xcx_version / activity type 201811 均为该小程序固定应用常量（原脚本硬编码，非个人凭证）。
业务基址 https://mobile.yangkeduo.com/proxy/api/api ，登录基址 https://api.pinduoduo.com 。
------------------------------------------
*/
// ---------------------------------------------------------------------------
// YYB 适配入仓（2026-11-09）：
// 来源 smallfawn/QLScriptPublic wxapp/pddgy-公众号版.js（311 行），原文件名见 README。
// 业务逻辑（登录换 Cookie / 首页 / 签到 / 浇水）未改，只改三处：
// (1) require env 改成 ./tools/env，env.js 跟脚本在同一拉库目录；
// (2) wcs.js 照 kekoukele/wcs.js 原样抄来，有 YYB_SERVER 就优先走 yyb-go
//     POST /wxapp/getCode，body {ref, app_id}，appid wx839691cce7c102bb 由调用方传入；
//     没配 YYB 才回落 POST /wx/code；
// (3) 删了 login() 里打印 Cookie 的那行 console.log，不把 Cookie 打进日志。
// 多账号注意：YYB 只认 YYB_SERVER 第一行 @ 后面的 ref，pddgy_gzh 里的
// openid 在 YYB 模式下只作计数和缓存 key，见 README。
// ---------------------------------------------------------------------------

const { Env } = require("./tools/env");
const $ = new Env("拼多多果园公众号版");
const axios = require("axios");
const fs = require("fs");
const path = require("path");
const WeChatServer = require("./wcs.js");

const ckName = "pddgy_gzh";
const MINI_APP_ID = "wx839691cce7c102bb";
const XCX_VERSION = "v8.6.21";
const PDD_APP_ID = 33;
const API_BASE = "https://api.pinduoduo.com";
const ORCHARD_BASE = "https://mobile.yangkeduo.com";
const MANOR_BASE = ORCHARD_BASE + "/proxy/api/api";
const CHECKIN_TYPE = 201811;
const MAX_WATER_TIMES = 20; // 附带浇水上限（非核心）
const TOKEN_CACHE_FILE = path.join(__dirname, "pddgy_token_cache.json");
const UA =
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 " +
    "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/19895 miniProgram/wx32540bd863b27570";

const wechat = new WeChatServer({
    url: process.env.wx_server_url || "http://192.168.31.196:8787",
    appid: MINI_APP_ID,
    auth: process.env.wx_auth || "",
});

// 通知用日志尾部：截获 console.log（Env 的 $.log 底层也是 console.log），只保留最近 100 行
const _qlLogTail = [];
const _qlOrigConsoleLog = console.log;
console.log = (...args) => {
    try {
        _qlLogTail.push(args.map((a) => { try { return typeof a === 'string' ? a : JSON.stringify(a); } catch { return String(a); } }).join(' '));
        if (_qlLogTail.length > 100) _qlLogTail.splice(0, _qlLogTail.length - 100);
    } catch {}
    _qlOrigConsoleLog(...args);
};
function _qlLog(m) { console.log(m); }

async function qlNotifyPddgy(results = [], note = '') {
    const ok = results.filter((t) => t.result && t.result.startsWith('✅')).length;
    const fail = results.length - ok;
    const title = results.length ? '拼多多果园公众号版：' + ok + '成功/' + fail + '失败' : '拼多多果园公众号版：未执行';
    const lines = ['拼多多果园公众号版签到', '', '总结：' + ok + ' 成功 / ' + fail + ' 失败'];
    results.forEach((t, i) => {
        lines.push('账号' + (i + 1) + ' ' + (t.result || '未知结果') + (t.water ? '（水滴' + t.water + '）' : ''));
    });
    if (note) lines.push(note);
    const tail = _qlLogTail.slice(-30);
    if (tail.length) lines.push('', '📋 日志尾部（最近30行）:', ...tail);
    let content = lines.join('\n');
    if (content.length > 1800) content = content.slice(0, 1800) + '\n……（内容已截断，完整日志见青龙运行日志）';
    if (await qlPanelNotify(title, content)) return;
    const notifier = loadQinglongNotifier();
    if (!notifier) { console.log('⚠️ 未找到可用的青龙sendNotify模块，账号汇总保留在运行日志'); return; }
    try {
        await notifier.sendNotify(title, content);
        console.log('✅ 通知已提交青龙通知模块（sendNotify.js，仅环境变量渠道有效）');
    } catch (e) { console.log('⚠️ 青龙通知调用失败: ' + (e.code || e.message || '通知模块异常')); }
}

// ---------------------------------------------------------------------------
// 青龙通知（走面板通知设置，例如面板里配的企业微信）
// 背景：sendNotify.js 只读 QYWX_AM 等环境变量，读不到面板数据库里的通知配置，
// 所以只调它时面板里配的企业微信收不到。本函数优先调青龙面板本地接口
// PUT /open/system/notify（带系统 token，见 /ql/data/config/token.json），
// 该接口由面板后端按数据库里的通知配置发出去；失败时在日志里写明原因，
// 再试 sendNotify.js（仅环境变量渠道有效）。通知发不发得出去绝不影响主流程。
// 截断规则：正文先取执行汇总，再加日志尾部最多 30 行，总长截到约 1800 字符
// （企业微信应用消息有长度限制，完整日志会被截断或发失败）。
// ---------------------------------------------------------------------------
function qlPanelToken(forceRegen) {
    const fsMod = require('fs');
    if (!forceRegen) {
        const candidates = [process.env.QL_NOTIFY_TOKEN_FILE || '', '/ql/data/config/token.json', '/ql/config/token.json'];
        for (const p of candidates) {
            if (!p) continue;
            try {
                const data = JSON.parse(fsMod.readFileSync(p, 'utf8'));
                if (data.value && data.expiration * 1000 > Date.now() + 30000) return data.value;
            } catch {}
        }
    }
    for (const cmd of [['node', '/ql/static/build/token.js'], ['node', '/ql/build/token.js']]) {
        try {
            const r = require('child_process').spawnSync(cmd[0], cmd.slice(1), { encoding: 'utf8', timeout: 30000 });
            if (r.status === 0 && r.stdout) {
                const parts = r.stdout.trim().split(/\s+/);
                if (parts.length) return parts[parts.length - 1];
            }
        } catch {}
    }
    return '';
}

async function qlPanelNotify(title, content) {
    const httpMod = require('http');
    const port = (process.env.QL_NOTIFY_PORT || process.env.QlPort || '5700').trim() || '5700';
    let token = qlPanelToken(false);
    if (!token) {
        _qlLog('⚠️ [通知] 面板接口发送失败：读不到青龙系统 token（/ql/data/config/token.json 不存在/已过期，且 node token.js 重新生成失败），尝试 sendNotify.js');
        return false;
    }
    for (let attempt = 0; attempt < 2; attempt++) {
        const result = await new Promise((resolve) => {
            const body = JSON.stringify({ title, content });
            const req = httpMod.request({
                host: '127.0.0.1', port: Number(port),
                path: '/open/system/notify?t=' + Math.floor(Date.now() / 1000),
                method: 'PUT',
                headers: { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json;charset=UTF-8', 'Content-Length': Buffer.byteLength(body) },
                timeout: 15000,
            }, (res) => {
                let raw = '';
                res.on('data', (c) => { raw += c; });
                res.on('end', () => {
                    try {
                        const data = JSON.parse(raw);
                        resolve(data.code === 200 ? true : { code: data.code, message: data.message || '' });
                    } catch { resolve({ code: res.statusCode, message: '非 JSON 响应' }); }
                });
            });
            req.on('timeout', () => { req.destroy(new Error('请求超时')); });
            req.on('error', (e) => { resolve({ code: 0, message: e.message }); });
            req.write(body);
            req.end();
        });
        if (result === true) {
            _qlLog('📨 青龙通知已发（面板通知设置）');
            return true;
        }
        if (result && result.code === 401 && attempt === 0) {
            token = qlPanelToken(true);
            if (!token) {
                _qlLog('⚠️ [通知] 面板接口返回 401 且重新生成 token 失败，尝试 sendNotify.js');
                return false;
            }
            continue;
        }
        _qlLog('⚠️ [通知] 面板接口发送失败：' + (result ? 'code=' + result.code + '：' + (result.message || '') : '未知错误') + '，尝试 sendNotify.js');
        return false;
    }
    return false;
}

function loadQinglongNotifier() {
    // 仅影响本脚本进程，避免青龙通知模块追加随机句子。
    process.env.HITOKOTO = 'false';
    const pathMod = require('path');
    const candidates = [
        '/ql/data/scripts/sendNotify.js', '/ql/data/deps/sendNotify.js', '/ql/scripts/sendNotify.js',
        pathMod.join(__dirname, 'sendNotify.js'), pathMod.join(__dirname, '..', 'sendNotify.js'),
        pathMod.join(__dirname, '..', '..', 'sendNotify.js'), 'sendNotify',
    ];
    for (const filename of candidates) {
        try {
            const notifier = require(filename);
            if (typeof notifier?.sendNotify === 'function') return notifier;
        } catch {}
    }
    return null;
}

function readCache() {
    try { if (!fs.existsSync(TOKEN_CACHE_FILE)) return {}; return JSON.parse(fs.readFileSync(TOKEN_CACHE_FILE, "utf8")) || {}; } catch (e) { return {}; }
}
function writeCache(c) {
    try { fs.writeFileSync(TOKEN_CACHE_FILE, JSON.stringify(c, null, 2), "utf8"); } catch (e) { $.log(`写入缓存失败: ${e.message || e}`); }
}
function parseAccount(raw = "") {
    const [id, remark] = String(raw).split("#").map((s) => (s || "").trim());
    return { openid: id, remark: remark || "" };
}
function short(v, n = 240) {
    const t = typeof v === "string" ? v : JSON.stringify(v);
    return !t ? "" : t.length > n ? `${t.slice(0, n)}...` : t;
}
function asObj(d) {
    if (d && typeof d === "object") return d;
    if (typeof d === "string") { try { return JSON.parse(d); } catch { return {}; } }
    return {};
}
function extractUid(cookieStr) {
    const m = /pdd_user_id=(\d+)/.exec(cookieStr || "");
    return m ? m[1] : "";
}

function okCode(res) {
    if (!res) return false;
    if (res.success === true) return true;
    if (Number(res.error_code) === 0 && (res.error_code === 0 || res.error_code === "0")) return true;
    if (res.code === 0) return true;
    return false;
}
function respMsg(res) {
    if (!res) return "";
    return res.error_msg || res.msg || res.message || res.errorMsg || "";
}

function get_accessToken(cookieStr) {
    const m = /PDDAccessToken=(\d+)/.exec(cookieStr || "");
    return m ? m[1] : "";
}
function get_pdd_user_id(cookieStr) {
    const m = /pdd_user_id=(\d+)/.exec(cookieStr || "");
    return m ? m[1] : "";
}
function get_pdd_user_uin(cookieStr) {
    const m = /pdd_user_uin=(\d+)/.exec(cookieStr || "");
    return m ? m[1] : "";
}

class Task {
    constructor(raw) {
        this.index = $.userIdx++;
        this.account = parseAccount(raw);
        this.cookieStr = "";
        this.pdduid = "";
        this.tubetoken = "";
        this.water = 0;
        this.result = "未开始";
    }
    log(text) {
        $.log(`账号[${this.index}]${this.account.remark ? `[${this.account.remark}]` : ""} ${text}`);
    }
    async getCode() {
        const { data } = await wechat.getCode(this.account.openid);
        if (data && data.status === false) throw new Error(`wx_server 取code失败: ${data.message || short(data)}`);
        const code = data?.data?.code || data?.code;
        if (!code || typeof code !== "string") throw new Error(`wx_server 未返回 code: ${short(data)}`);
        return code;
    }
    async login() {
        const code = await this.getCode();
        this.log(`获取code: ${short(code, 12)}...`);
        const loginBody = {
            code,
            has_auth: false,
            app_id: PDD_APP_ID,
            support_enhance_type: 3,
            xcx_version: XCX_VERSION,
        };
        const res = await axios.request({
            method: "GET",
            url: `https://mobile.yangkeduo.com/garden_index_lz_0.html?_pdd_fs=1&_pdd_tc=676666&_pdd_sbs=1&fun_id=wechat_app_home&__wls_rt=1&__wls_lt=1&__wls_fm=b&code=${code}&state=BASE`,
            //data: JSON.stringify(loginBody),
            headers: {
                "Content-Type": "application/json;charset=UTF-8",
                "User-Agent": UA,
                Accept: "*/*",
                Referer: `https://servicewechat.com/${MINI_APP_ID}/1840/page-frame.html`,
                "x-xcx-queries": `mini_program_name=pdd;mp_theme_version=${XCX_VERSION}`,
                xweb_xhr: "1",
            },
            timeout: 20000,
            validateStatus: () => true,
        });

        let setCookieStr = "";
        const sc = res.headers && res.headers["set-cookie"];
        if (sc) {
            const arr = Array.isArray(sc) ? sc : [sc];
            setCookieStr = arr.map((c) => String(c).split(";")[0]).join("; ");
        }
        // 使用示例
        const accessToken = get_accessToken(setCookieStr);
        const uid = get_pdd_user_id(setCookieStr);
        const uin = get_pdd_user_uin(setCookieStr);
        const acid = "";

        const parts = [`PDDAccessToken=${accessToken}`, `pdd_user_id=${uid}`];
        if (uin) parts.push(`pdd_user_uin=${uin}`);
        if (acid) parts.push(`acid=${acid}`);
        if (setCookieStr) parts.push(setCookieStr);

        this.cookieStr = parts.join("; ");
        this.pdduid = uid;
        const cache = readCache();
        cache[this.account.openid] = { cookieStr: this.cookieStr, uid, updatedAt: new Date().toISOString() };
        writeCache(cache);
        this.log(`登录成功 uid=${uid}`);
    }
    async manorPost(apiPath, body) {
        const url = `${MANOR_BASE}${apiPath}${apiPath.includes("?") ? "&" : "?"}pdduid=${this.pdduid}`;
        const res = await axios.request({
            method: "POST",
            url,
            data: JSON.stringify(body || {}),
            headers: {
                "User-Agent": UA,
                Accept: "application/json, text/plain, */*",
                "Content-Type": "application/json;charset=UTF-8",
                Origin: ORCHARD_BASE,
                Referer: `${ORCHARD_BASE}/garden_index_lz_0.html`,
                Cookie: this.cookieStr,
            },
            timeout: 20000,
            validateStatus: () => true,
        });
        return asObj(res.data);
    }
    // 首页：刷新 tubetoken + 水滴，同时用作 Cookie 有效性探测
    async getHomePage() {
        const body = {
            mission_type: 0, fun_id: "wechat_app_home", message_source: null,
            page_type: "HOME_PAGE", push_source_mission_type: 0, fruit_config_version: "",
            unlock_scene_version: "", app_home_click_icon_type: null, tubetoken: this.tubetoken,
            push_act_source: null, need_show_home_popup: true, fun_pl: 2,
        };
        const result = await this.manorPost("/manor-query/proxy/home/page", body);
        if (!result || !result.user_manor_info) { this.log(`  首页校验失败(40001)，Cookie 可能已过期`); return false; }
        if (result.user_manor_info.tubetoken) this.tubetoken = result.user_manor_info.tubetoken;
        if (result.user_manor_info.water_amount != null) this.water = result.user_manor_info.water_amount;
        return !!this.tubetoken;
    }
    async getWater() {
        const result = await this.manorPost("/manor-gateway/manor/query/user/water?is_back=1", {});
        return (result && result.water_amount) || 0;
    }
    async checkin() {
        const body = {
            type: CHECKIN_TYPE,
            params: { ui_id: 3, type: 2 },
            fun_id: "wechat_app_home",
            tubetoken: this.tubetoken,
            fun_pl: 2,
        };
        const res = await this.manorPost("/manor/common/apply/activity", body);
        if (okCode(res)) {
            const reward = res.water || res.reward_amount || (res.data && (res.data.water || res.data.reward_amount)) || "";
            this.log(`✅ 签到成功${reward ? `，+${reward}水滴` : ""}`);
            return { ok: true };
        }
        const msg = respMsg(res) || short(res);
        if (/已签|签到过|重复|已领取|已完成|already|repeat/i.test(String(msg))) {
            this.log(`✅ 今日已签到（${msg}）`);
            return { ok: true, already: true };
        }
        // 风控类反馈
        if (/验证|风控|拦截|滑块|verify|forbidden/i.test(String(msg)) || Number(res.error_code) === 54002) {
            this.blocked = true;
            this.log(`⛔ 签到被风控拦截: ${msg}`);
            return { ok: false, blocked: true, msg };
        }
        this.log(`❌ 签到失败: ${msg}`);
        return { ok: false, msg };
    }
    // 附带浇水（非核心：失败/风控都不影响签到判定）
    async waterTree() {
        try {
            let water = await this.getWater();
            if (water < 10) { this.log(`  [浇水] 水滴 ${water} 不足10，跳过`); return; }
            const count = Math.min(MAX_WATER_TIMES, Math.floor(water / 10));
            let watered = 0;
            let curr = water;
            for (let i = 0; i < count; i++) {
                const body = {
                    atw: true, location_auth: false, last_stay_time: Math.floor(Math.random() * 40) + 10,
                    can_trigger_random_mission: false, product_scene: 0, minor: false,
                    ext_params: { can_trigger201824: true }, mission_type: 0, cost_water_amount: 10,
                    merge_cost: false, fun_id: "wechat_app_home", lower_end_device: false,
                    cost_water_competition_in_scene_icon: false, is_small_screen: true,
                    tubetoken: this.tubetoken, fun_pl: 2,
                };
                const r = await this.manorPost("/manor/water/cost", body);
                const left = r && r.now_water_amount;
                if (left != null && left < curr) { curr = left; watered++; if (left < 10) break; await $.wait(200, 400); }
                else break;
            }
            this.log(`  [浇水] 完成 ${watered} 次，剩余水滴 ${curr}`);
        } catch (e) {
            this.log(`  [浇水] 跳过: ${e.message || e}`);
        }
    }
    async ensureSession() {
        const cached = readCache()[this.account.openid] || {};
        if (!this.cookieStr && cached.cookieStr) {
            this.cookieStr = cached.cookieStr;
            this.pdduid = cached.uid || extractUid(this.cookieStr);
            this.log("使用缓存Cookie");
            if (await this.getHomePage()) { this.log(`缓存有效，水滴=${this.water}`); return; }
            this.log("缓存失效，重新登录");
            this.cookieStr = ""; this.pdduid = ""; this.tubetoken = "";
        }
        if (!this.cookieStr) {
            await this.login();
            if (!this.pdduid) this.pdduid = extractUid(this.cookieStr);
            if (!(await this.getHomePage())) throw new Error("登录后首页加载失败(可能风控/Cookie无效)");
            this.log(`当前水滴=${this.water}`);
        }
    }
    async run() {
        if (!this.account.openid) { this.result = "❌ 跳过：变量值里没有 openid"; this.log("跳过：变量值里没有 openid"); return; }
        try {
            await this.ensureSession();
            const r = await this.checkin();
            if (r.ok) this.result = r.already ? "✅ 今日已签到" : "✅ 签到成功";
            else if (r.blocked) this.result = "⛔ 签到被风控拦截" + (r.msg ? ": " + r.msg : "");
            else this.result = "❌ 签到失败" + (r.msg ? ": " + r.msg : "");
            await $.wait(500, 1000);
            if (!r.blocked) await this.waterTree();
        } catch (e) {
            const em = String(e.message || e);
            if (em.startsWith("BLOCKED")) {
                this.result = "⛔ " + em.replace(/^BLOCKED:/, "") + "（拼多多重风控，需在小程序内手动过验证，脚本无法绕过）";
                this.log(`⛔ ${em.replace(/^BLOCKED:/, "")}（拼多多重风控，需在小程序内手动过验证，脚本无法绕过）`);
                return;
            }
            this.result = "❌ 执行失败: " + em;
            this.log(`执行失败: ${em}`);
        }
    }
}

!(async () => {
    $.checkEnv(ckName);
    if (!$.userCount) { $.log(`未找到变量 ${ckName}`); await qlNotifyPddgy([], '未找到变量 ' + ckName); return; }
    if (!String(process.env.YYB_SERVER || '').trim() && !(process.env.wx_server_url && process.env.wx_auth)) {
        $.log(`${ckName}未配置微信SERVER配置`);
        await qlNotifyPddgy([], '未配置微信SERVER（YYB_SERVER 或 wx_server_url / wx_auth），配 YYB_SERVER 走 yyb-go 取码，或自建 WeChatCodeServer');
        return;
    }
    const results = [];
    for (let i = 0; i < $.userList.length; i++) {
        const t = new Task($.userList[i]);
        await t.run();
        results.push(t);
        if (i < $.userList.length - 1) await $.wait(1500, 3000);
    }
    await qlNotifyPddgy(results);
})().catch(async (e) => { console.log(e); try { await qlNotifyPddgy([], '脚本异常：' + (e && e.message ? e.message : e)); } catch {} }).finally(() => $.done());
