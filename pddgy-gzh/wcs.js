const axios = require("axios");

// ---------------------------------------------------------------------------
// YYB 适配（2026-11-09，pddgy-gzh 入库时加，照 kekoukele/wcs.js 原样抄来）：
// pddgy-gzh.js 原来只走 WeChatCodeServer（POST {serverUrl}/wx/code）。
// 现在 getCode(openid) 优先走自建 yyb-go（环境变量 YYB_SERVER，格式
// “地址@账号ref”，多行多账号，取第一行；协议照抄仓库里已有的实现：
// hongse-huojian/hshj.js 的 yybPost / getSingleCode 和
// shunfeng-suyun/sfsy.py 的 _get_wx_code）。
// 没配 YYB_SERVER 时回落到原来的 WeChatCodeServer 路径。
// 2026-11-10 修正：YYB 的 ref 不再只认 YYB_SERVER 第一行。
// getCode(openid) 传进来的 openid 就是该账号的 YYB ref（pddgy_gzh 里
// 填的 OpenID），按账号取 code；没传 openid 时才回落到第一行。
// 旧写法导致多账号时所有账号都拿第一行旧号取 code，新号永远用不上。
// ---------------------------------------------------------------------------
function parseYybServer() {
    const raw = String(process.env.YYB_SERVER || '');
    for (const line of raw.split(/\r?\n/)) {
        const t = line.trim();
        if (!t) continue;
        const at = t.lastIndexOf('@');
        if (at < 1) continue;
        let server = t.slice(0, at).trim().replace(/\/+$/, '');
        const ref = t.slice(at + 1).trim();
        if (!server || !ref) continue;
        if (!/^https?:\/\//i.test(server)) server = 'http://' + server;
        return { server, ref };
    }
    return null;
}

class WeChatCodeServer {
    constructor(options) {
        this.serverUrl = options.url;
        this.appid = options.appid;
        this.auth = options.auth;
    }
    // YYB 取码：POST {server}/wxapp/getCode，body {ref, app_id}。
    // 成功响应：{"code":0,"msg":"success","data":{"openid":"...",
    // "result":{"code":"<微信code>","errMsg":"login:ok"}}}。
    // 返回值形状与原来一致：resolve 一个 axios 响应形对象
    // {data:{status:true,data:{code}}}，pddgy-gzh.js 里是
    // `const { data } = await wechat.getCode(this.account.openid)`，再取
    // data.data.code || data.code 去登录换 Cookie。
    // 取码失败时不抛错，resolve {status:false}，让 pddgy-gzh.js 把该
    // 账号记为取 code 失败并继续下一个账号（与原来 data.status
    // 为假时的分支一致）；失败原因打在日志里。
    getCodeYyb(openid) {
        const yyb = parseYybServer();
        const ref = String(openid || '').trim() || yyb.ref;
        console.log('等待获取code（YYB），ref=' + ref.slice(0, 8) + '...:');
        const headers = { 'Content-Type': 'application/json' };
        const token = String(process.env.YYB_API_KEY || '').trim()
            || String(process.env.YYB_PROTOCOL_TOKEN || '').trim();
        if (token) headers.Authorization = 'Bearer ' + token;
        return axios.post(yyb.server + '/wxapp/getCode', { ref, app_id: this.appid }, {
            headers,
            timeout: 30 * 1000
        }).then(res => {
            const j = res.data || {};
            let code = '';
            if (j.code === 0 || j.code === '0' || j.code === undefined || j.code === null) {
                const data = j.data || {};
                const result = data.result || {};
                if (result && result.code) code = String(result.code);
                else if (data.code) code = String(data.code);
            }
            if (!code && j.status === 'ok' && j.code && typeof j.code !== 'number') code = String(j.code);
            if (!code) {
                console.log('YYB 取码失败，未返回有效 code：' + JSON.stringify(j).slice(0, 200));
                return { data: { status: false, data: {}, msg: 'YYB 未返回有效 code' } };
            }
            console.log('获取code成功（YYB）:');
            return { data: { status: true, data: { code } } };
        }).catch(err => {
            console.log('YYB 取码失败：' + (err.message || err));
            return { data: { status: false, data: {}, msg: String(err.message || err) } };
        });
    }
    getCode(openid) {
        if (parseYybServer()) return this.getCodeYyb(openid);
        console.log('等待获取code:');
        return new Promise((resolve, reject) => {
            axios.post(this.serverUrl + '/wx/code', { appid: this.appid, openid }, {
                headers: {
                    'auth': this.auth
                },
                timeout: 30 * 1000
            }).then(res => {
                console.log('获取code成功:');
                resolve(res);
            }).catch(err => {
                reject(err);
            });
        });
    }
   
    cloudInit(openid) {
        console.log('等待云函数初始化:');
        return new Promise((resolve, reject) => {
            axios.post(this.serverUrl + '/wx/call/init', { appid: this.appid, openid }, {
                headers: {
                    'auth': this.auth
                },
                timeout: 30 * 1000
            }).then(res => {
                console.log('云函数初始化成功:');
                resolve(res);
            }).catch(err => {
                reject(err);
            });
        });
    }
    cloudCall(openid) {
        console.log('等待云函数调用:');
        return new Promise((resolve, reject) => {
            axios.post(this.serverUrl + '/wx/cloud/call', { appid: this.appid, openid }, {
                headers: {
                    'auth': this.auth
                },
                timeout: 30 * 1000
            }).then(res => {
                console.log('云函数调用成功:');
                resolve(res);
            }).catch(err => {
                reject(err);
            });
        });
    }
}
module.exports = WeChatCodeServer;
