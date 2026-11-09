
/*
------------------------------------------
@Author: sm
@Date: 2024.06.07 19:15
@Description:  
cron: 30 9 * * 1
------------------------------------------
#Notice:   
可口可乐 微信小程序 签到得积分 
WeChatCodeServer 填写wx_server_url wx_auth 用于获取code 
变量名称：kekoukele
⚠️【免责声明】
------------------------------------------
1、此脚本仅用于学习研究，不保证其合法性、准确性、有效性，请根据情况自行判断，本人对此不承担任何保证责任。
2、由于此脚本仅用于学习研究，您必须在下载后 24 小时内将所有内容从您的计算机或手机或任何存储设备中完全删除，若违反规定引起任何事件本人对此均不负责。
3、请勿将此脚本用于任何商业或非法目的，若违反规定请自行对此负责。
4、此脚本涉及应用与本人无关，本人对因此引起的任何隐私泄漏或其他后果不承担任何责任。
5、本人对任何脚本引发的问题概不负责，包括但不限于由脚本错误引起的任何损失和损害。
6、如果任何单位或个人认为此脚本可能涉嫌侵犯其权利，应及时通知并提供身份证明，所有权证明，我们将在收到认证文件确认后删除此脚本。
7、所有直接或间接使用、查看此脚本的人均应该仔细阅读此声明。本人保留随时更改或补充此声明的权利。一旦您使用或复制了此脚本，即视为您已接受此免责声明。
*/

const {
    Env
} = require("../tools/env")
const $ = new Env("可口可乐小程序");
const WeChatServer = require("./wcs.js");
let ckName = `kekoukele`;
const strSplitor = "#";
const axios = require("axios");
const defaultUserAgent = "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.31(0x18001e31) NetType/WIFI Language/zh_CN miniProgram"
let wechat = new WeChatServer({
    url: process.env.wx_server_url || 'http://192.168.31.196:12081',
    appid: 'wxa5811e0426a94686',
    auth: process.env.wx_auth || "your-api-key",

}
);

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

async function qlNotifyKekoukele(results = [], note = '') {
    const ok = results.filter((t) => t.result && t.result.startsWith('✅')).length;
    const fail = results.length - ok;
    const title = results.length ? '可口可乐小程序：' + ok + '成功/' + fail + '失败' : '可口可乐小程序：未执行';
    const lines = ['可口可乐小程序签到', '', '总结：' + ok + ' 成功 / ' + fail + ' 失败'];
    results.forEach((t, i) => {
        lines.push('账号' + (i + 1) + ' ' + (t.result || '未知结果') + (t.points !== null && t.points !== undefined ? '（剩余' + t.points + '瓶）' : ''));
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

class Task {
    constructor(env) {
        this.index = $.userIdx++
        this.user = env.split(strSplitor);
        this.token = null
        this.wcsid = this.user[0]
        this.isSign = false
        this.result = '未开始'
        this.signPoint = null
        this.points = null
    }

    async run() {
            //随机延迟5-30s 模拟人工操作
       await $.wait(Math.floor(Math.random() * 20 + 5) * 1000);
        let { data: codeRes } = await wechat.getCode(this.wcsid)
        if (codeRes.status) {
            await this.getUserToken(codeRes.data.code)
        }
        if (!this.token) {
            this.result = '❌ 获取用户Token失败';
            $.log(`账号[${this.index}] 获取用户Token失败❌`)
            return
        }
        await this.userInfo()
        await this.addSign()
    }
    async getUserToken(code) {
        let options = {
            method: 'GET',
            url: 'https://member-api.icoke.cn/api/sp-portal/store/icoke/wechat/loginNoCache/' + code,
            headers: {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781 NetType/WIFI MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/50249',
                'Accept': 'application/json, text/plain, */*',
                'xweb_xhr': '1',
                'Content-Type': 'application/json',
                'Sec-Fetch-Site': 'cross-site',
                'Sec-Fetch-Mode': 'cors',
                'Sec-Fetch-Dest': 'empty',
                'Referer': 'https://servicewechat.com/wxa5811e0426a94686/496/page-frame.html',
                'Accept-Language': 'zh-CN,zh;q=0.9'
            }
        };

        let {
            data: result
        } = await axios.request(options);

        if (result?.jwtString) {
            this.token = result?.jwtString
            $.log(`🌸账号[${this.index}] 获取用户Token成功:${this.token}`)
        } else {
            $.log(`🌸账号[${this.index}] 获取用户Token-失败:${result.message}❌`)
        }
    }
    async addSign() {
        let options = {
            method: "GET",
            url: "https://member-api.icoke.cn/api/icoke-sign/icoke/mini/sign/main/sign",
            headers: {
                "accept": "application/json, text/plain, */*",
                "accept-language": "zh-CN,zh;q=0.9",
                "authorization": "" + this.token,
                "content-type": "application/json",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "cross-site",
                "xweb_xhr": "1",
                "Referer": "https://servicewechat.com/wxa5811e0426a94686/421/page-frame.html",
                "Referrer-Policy": "unsafe-url"
            },

        }
        try {
            let { data: res } = await axios.request(options);
            if (res.success == true) {
                this.result = `✅ 签到成功 +${res.point}快乐瓶`;
                this.signPoint = res.point;
                $.log(`签到成功 获得【${res.point}】快乐瓶`)
            } else {
                this.result = '❌ 签到失败';
                $.log(`签到失败`)
                console.log(res);
            }
        } catch (e) {
            this.result = '❌ 签到异常';
            console.log(e);

        }
    }
    async userInfo() {
        let options = {
            method: "GET",
            url: "https://member-api.icoke.cn/api/icoke-customer/icoke/mini/customer/main/points",
            headers: {
                "accept": "application/json, text/plain, */*",
                "accept-language": "zh-CN,zh;q=0.9",
                "authorization": "" + this.token,
                "content-type": "application/json",
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "cross-site",
                "xweb_xhr": "1",
                "Referer": "https://servicewechat.com/wxa5811e0426a94686/421/page-frame.html",
                "Referrer-Policy": "unsafe-url"
            },

        }
        try {
            let { data: res } = await axios.request(options);
            this.points = res.point;
            $.log(`目前还剩【${res.point}】瓶 `)

        } catch (e) {
            console.log(e);

        }
    }








}

!(async () => {
    await getNotice()
    $.checkEnv(ckName);
    if (process.env['wx_server_url'] && process.env['wx_auth']) {
        const results = [];
        for (let user of $.userList) {
            const t = new Task(user);
            await t.run();
            results.push(t);
        }
        await qlNotifyKekoukele(results);
    } else {
        
        $.log(`${ckName}未配置微信SERVER配置 搭建可看仓库目录下的readme.md❌`)
        await qlNotifyKekoukele([], '未配置微信SERVER（wx_server_url / wx_auth），需自建 WeChatCodeServer');
        return
    }

})()
    .catch(async (e) => { console.log(e); await qlNotifyKekoukele([], '脚本异常：' + (e && e.message ? e.message : e)); })
    .finally(() => $.done());

async function getNotice() {
    try {
        let options = {
            url: `https://ghproxy.net/https://raw.githubusercontent.com/smallfawn/Note/refs/heads/main/Notice.json`,
            headers: {
                "User-Agent": defaultUserAgent,
            },
            timeout: 3000
        }
        let {
            data: res
        } = await axios.request(options);
        $.log(res)
        return res
    } catch (e) { }

}
