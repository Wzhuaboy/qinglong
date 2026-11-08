/**
 * 同程旅行小程序 里程签到 + 任务领里程（yyb-go 版）
 *
 * 依据 2026-10-25 的同程旅行小程序 HAR（appid wx336dcaf6a1ecf632）还原：
 *   取码  POST {yyb_go_url}/wxapp/getCode {ref, app_id}
 *   登录  POST https://wx.17u.cn/wechatappapi/wxUser/login {code, scene:1001}
 *         -> content.{openId, unionId, memberId, sectoken}
 *   鉴权  wxmpsign 系列要 TC-MALL-USER-TOKEN；任务接口要 secToken（两个都发）
 *   余额  POST /wxmpsign/home/top {} -> data.remainCoin
 *   签到  POST /wxmpsign/sign/signCalendar {beginDate,endDate}
 *         POST /wxmpsign/sign/getSignInfo {}
 *         POST /wxmpsign/sign/saveSignInfo {}（已签到返回 false 不再提交）
 *   任务  POST /qiushiinnerapi/task/detailList {detailGuid:"",pageNum:1,pageSize:999,schemeGuid}
 *         POST /qiushiinnerapi/task/startTask {detailGuid,schemeGuid[,channel]}
 *         POST /qiushiinnerapi/task/finishTask {detailGuid,schemeGuid}
 *         POST /qiushiinnerapi/task/sendTaskPrize {detailGuid,schemeGuid}
 *         任务状态 status：0 未开始 / 1 进行中 / 2 待领奖 / 3 已完成
 *         taskType：0 浏览页、1 限时浏览（countDown 秒）、3 小游戏（要真玩，跳过）
 *         客服任务（taskType=5，detailGuid taskDetail-2026-bljzbtxt）：「回复花签」服务端认真实对话，
 *         finishTask 回 3901「该类型任务不支持通过API操作」，status 只能靠真聊变 2；
 *         变 2 之后 sendTaskPrize 能直接领（→3），脚本已自动领
 *   花神  GET  /platformflowpool/flowerGod/home -> data.remainDrawCount / cardList / taskList
 *         POST /platformflowpool/flowerGod/drawCard {usage:"common"} -> 抽一张卡（state=6 待翻）
 *         GET  /platformflowpool/flowerGod/cardList -> 卡列表，state 6=待翻 1=已翻，rewardName 就是里程
 *         POST /platformflowpool/flowerGod/flipCard {cardId} -> 翻卡，里程直接到账（实测 2628→2633）
 *   短剧  POST /platformflowpool/drama/getBaseData {refid}         -> 短剧页访问登记，返回 extInfo 归因票据
 *         POST /platformflowpool/drama/recVisitReward {}           -> 领访问里程，实测 +2（data.visitMileageReward）
 *         POST /platformflowpool/drama/getWatchTaskStatus {refid}  -> 每日首次看剧 +10
 *               taskStatus 0 未看够 / 1 可领 / 2 今日已领，watchSeconds 是要看满的秒数
 *         POST /platformflowpool/drama/recWatchTaskReward {}       -> 领看剧里程；已领过回 120003
 *         POST /platformflowpool/drama/getMileageIncome {}         -> 今日 / 累计短剧里程
 *         时长由微信短剧平台服务端统计后回传同程，客户端伪造不了（2026-10-25 复核 短剧.har）：
 *         看剧在微信短剧流量位小程序 wx404dde55fb12df78（官方播放器插件 wx94a6522b1d640c3b）里，
 *         同程把 extInfo 当 _wxExtInfo 启动参数带过去；视频是 vodpreview 一次性防盗链签名 URL，
 *         看剧期间短剧小程序没有任何业务 API，同程侧明文+云托管加密通道(/__wx__/call)零调用，
 *         回程 taskStatus 直接 0->1、todayWatchSeconds 0->188（实际播放 186+2 秒）。
 *         「拿剧集小程序 code 登录再调观看上报」这条路不存在——上报这个动作不在客户端；
 *         领奖侧（+2 / +10）脚本已全自动。
 *   抽奖  POST /qiushiinnerapi/fission/lottery/list {schGuid} -> lotteryCount / maxLotteryCount
 *         只播报剩余次数，不替用户抽（奖池里有现金和免单额度，规则要好友助力）
 *   分享  GET  /wxmpsign/share/mileage/getShareMileageConfig -> 打卡挑战要先付 100 里程，不参与
 *   platformflowpool 系列额外要 TC-OS-TYPE / TC-PLATFORM-CODE / TC-USER-TOKEN 三个头，
 *   而且网关认头名大小写（urllib 之类会自动改大小写，axios 不会）
 *
 * 环境变量：
 *   tclx          必填，yyb-go 账号标识（ref），多账号 & 或换行分隔，可写 ref#备注
 *   yyb_go_url    选填，yyb-go 地址，默认 http://192.168.31.217:8000
 *   tclx_schemes  选填，任务方案列表 guid[:channel]，逗号分隔
 *                 默认 task-2025-nflygijg:qiandao,task-2026-rjokxmqw:miandan,task-2025-oqrnzumj
 *                      + task-2026-gtfdfdit、task-2026-bxmhbrik（这两个只能手动，脚本只播报）
 *   tclx_drama_refid 选填，短剧活动 refid，逗号分隔，默认 2000615847,2000642046,2001086637
 *   tclx_dry      选填，true = 只登录/查余额/查签到与任务，不签到不领奖
 *   tclx_help     选填，false = 关闭多账号互助；默认开启（配 2 个以上账号才生效）
 *   tclx_pub      周周打卡领现金要「公众号 openid」，按 tclx 账号顺序用 & 分隔（没有的留空）
 *                 互助内容：fission/lottery/help 抽奖助力 + flowerGod/grantCard 互赠卡
 *
 * cron: 30 7 * * *
 */

'use strict';

const axios = require('axios');
const fs = require('fs');
const path = require('path');

const SCRIPT_NAME = '同程旅行里程(yyb)';
const CK_NAME = 'tclx';
const APP = { appid: 'wx336dcaf6a1ecf632', version: '955' };
const BASE = 'https://wx.17u.cn';
const TOKEN_CACHE_FILE = path.join(__dirname, 'tclx_token_cache.json');

const YYB_URL = String(process.env.yyb_go_url || process.env.YYB_GO_URL || 'http://192.168.31.217:8000')
    .trim()
    .replace(/\/+$/, '');
const DRY_RUN = String(process.env.tclx_dry || '').trim().toLowerCase() === 'true';
// tclx_only=checkin：只核对「打卡挑战」结算（15:00 后到账），签到/任务/抽奖/互助全部跳过
const ONLY = String(process.env.tclx_only || '')
    .trim()
    .toLowerCase();

const UA =
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) ' +
    'Chrome/144.0.0.0 Safari/537.36 MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI ' +
    'MiniProgramEnv/Windows WindowsWechat/WMPF XWEB/26042';

// 方案 guid/channel 全部来自抓包；reportOnly = 任务只能在小程序里手动做，脚本只播报不硬领
const DEFAULT_SCHEMES = [
    { guid: 'task-2025-nflygijg', channel: 'qiandao', name: '签到页任务' },
    { guid: 'task-2026-rjokxmqw', channel: 'miandan', name: '会员中心任务' },
    { guid: 'task-2025-oqrnzumj', channel: '', name: '浏览活动任务' },
    {
        guid: 'task-2026-gtfdfdit',
        channel: '',
        name: '下拉奖励任务',
        reportOnly: '要真机下拉/添加我的小程序',
    },
    {
        guid: 'task-2026-bxmhbrik',
        channel: '',
        name: '客服任务',
        reportOnly: '要和小程序客服对话（回复“花签”）',
    },
];

const FLOWER_BASE = '/platformflowpool/flowerGod';
// 花神签 = 卡池里的 type 0：摇签抽不出来（四个号 cardCount 恒为 0），只能靠送卡/邀好友拿。
// 集卡只差花神签的号再投助力次数也只会摇出重复卡，默认跳过，把次数让给还能出卡的号。
// tclx_flower_skip_last=false 恢复旧行为；tclx_flower_last_type 可改判定类型
const FLOWER_LAST_TYPE = Number(process.env.tclx_flower_last_type ?? 0);
const FLOWER_SKIP_LAST = String(process.env.tclx_flower_skip_last || 'true').trim().toLowerCase() !== 'false';
// tclx_flower_first：把「邀好友必得花神签」的助力排到钞级省/好友签到助力之前。
// 每号每天的助力额度是共享的，先到先得；排在后面只会回「您助力过其他活动，没有助力次数啦~」
// 默认关：集齐 6 种只兑 0.11-0.88 元，而这些额度投给钞级省每天能换 5 元上下的现金，不划算。
// 想验证配额到底怎么分，可以设 tclx_flower_first=true 跑一天看首跑结果。
const FLOWER_HELP_FIRST =
    String(process.env.tclx_flower_first || 'false').trim().toLowerCase() === 'true';
// 花神总开关，默认关：2026-11-02 起本期摇签全被服务端拒（4 个号翻卡 0 张，当期规则已过
// 11-01 23:59:59），每天白跑几十次请求还占互助额度。tclx_flower=true 恢复整块花神
// （摇签/翻卡/分享补充/赠卡/花神互助/集齐兑换）。
const FLOWER_ENABLED = String(process.env.tclx_flower || 'false').trim().toLowerCase() === 'true';

// ── 花神能不能自动跨期，全看下面这几项不写死 ─────────────────────────────
// 每期几张签（本期 6 = 1 张花神签 + 5 张祝福签）：用 home.cardList 下发的种类数，拿不到才退回 6
let FG_KINDS_TOTAL = 6;
// 花神签不可转赠，但它的 cardType 不一定永远是 0（换期可能变）：
// tclx_fg_godcard 可预置，运行时按「转赠被拒」自动学习
const FG_GOD_TYPES = new Set(
    String(process.env.tclx_fg_godcard || '')
        .split(/[,&\s]+/)
        .map((x) => x.trim())
        .filter((x) => x !== '')
        .map(Number)
);
// 本期清零时间：从活动规则正文（userRule/getById/<ruleId>）解析，一次运行只查一次
let FG_DEADLINE = null;
const FG_RULE_ID = process.env.tclx_fg_ruleid || '55';

/**
 * 本期截止时间 —— 规则里的「本期集签周期：…起—…止」
 * 解析失败就退到 tclx_fg_deadline；再没有就空串（只影响日志提示，不影响领奖）
 */
async function flowerDeadline(sess) {
    if (FG_DEADLINE !== null) return FG_DEADLINE;
    FG_DEADLINE = process.env.tclx_fg_deadline || '';
    try {
        const r = await wxApi(sess, `/qiushiinnerapi/userRule/getById/${FG_RULE_ID}`, null, 'GET');
        const desc = String((r.data || {}).ruleDesc || '')
            .replace(/<[^>]+>/g, ' ')
            .replace(/&nbsp;/g, ' ');
        const m = /本期[^：:]{0,6}[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日[^—\-~至]{0,12}[—\-~至]+(\d{4})年(\d{1,2})月(\d{1,2})日\s*([\d:]{5,8})/.exec(desc);
        if (m) {
            const p2 = (n) => String(n).padStart(2, '0');
            FG_DEADLINE = `${m[4]}-${p2(m[5])}-${p2(m[6])} ${m[7]}`;
        }
    } catch (_) {
        /* 规则拿不到就只少一句提示 */
    }
    return FG_DEADLINE;
}

/**
 * 花神「联系客服」任务（taskType 4）：detailGuid / schemeGuid 每期都可能换，
 * 所以从 home.taskList 动态取，只用数字 taskType 定位，不写死 guid。
 * status 2 = 已完成待领取 -> sendTaskPrize 直接领（实测 2→3）；
 * status 0 = 还没真聊过，这一步服务端认真实对话（finishTask 回 3901 该类型任务不支持通过API操作）
 */
async function flowerCustomerTask(sess, home) {
    const t = ((home || {}).taskList || []).find((x) => Number(x.taskType) === 4) || {};
    const detailGuid = t.customerDetailGuid || '';
    if (!detailGuid) return null;
    const schemeGuid = t.customerSchemeGuid || '';
    const detail = await wxApi(sess, '/qiushiinnerapi/task/detail', { detailGuid, schemeGuid });
    const task = (((detail.data || {}).taskDetails) || [])[0] || {};
    const status = Number(task.status) || 0;
    if (status !== 2) return { status, claimed: false, title: task.title || '' };
    const claim = await wxApi(sess, '/qiushiinnerapi/task/sendTaskPrize', { detailGuid, schemeGuid });
    const ok = Number(claim.code) === 0;
    return { status: ok ? 3 : status, claimed: ok, title: task.title || '', msg: ok ? '' : resMsg(claim) };
}
const DRAMA_BASE = '/platformflowpool/drama';
// 短剧（看剧）活动的 refid：抓包里出现过这三个，任务状态按 refid 各自算，逐个查
const DRAMA_REFID = '2000615847,2000642046,2001086637';
const LOTTERY_SCH = 'fission-sch-2025-dxneldyh';
// 闲置券回收（m.17u.cn/activity/sspa/cashout/recycleCoupon?refid=2000615910）的助力活动，
// 和钞级省同一套 fission 接口。注意：2026-10-25 实测服务端回 code 3000「券回收小程序下线了」，
// 拉不到 blockList 就静默跳过；活动恢复后这里自动生效
const RECYCLE_SCH = process.env.tclx_recycle_sch || 'fission-sch-2025-fsdnbqzl';
const FISSION_SCHS = [LOTTERY_SCH, RECYCLE_SCH];
// 周周打卡领现金（H5 活动 20260819dailyCheckIn / signInCash）：打卡 5 天抽现金，浏览任务攒萌力值兑换
// 鉴权要「公众号 openid + unionId」，用 tclx_pub 按 tclx 账号顺序配（& 分隔，没有就留空）
const WEEK_API = 'https://cvg.17usoft.com/activity/signInCash';
const WEEK_ACT = 'c60c3ca52ec79260203998db4578c913';

const $ = {
    log(msg) {
        console.log(String(msg));
    },
    wait(min, max) {
        const ms = max == null ? min : Math.floor(Math.random() * (max - min + 1) + min);
        return new Promise((r) => setTimeout(r, ms));
    },
};

function short(value, max = 240) {
    if (value === undefined || value === null) return '';
    const text = typeof value === 'string' ? value : JSON.stringify(value);
    return text.length > max ? `${text.slice(0, max)}...` : text;
}

function splitAccounts(raw) {
    return String(raw || '')
        .split(/[\n&]+/)
        .map((s) => s.trim())
        .filter(Boolean);
}

function parseAccount(raw) {
    const [ref, remark] = String(raw).split('#').map((s) => (s || '').trim());
    return { ref, remark: remark || '' };
}

function parseSchemes(raw) {
    const text = String(raw || '').trim();
    if (!text) return DEFAULT_SCHEMES;
    return text
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean)
        .map((item) => {
            const [guid, channel] = item.split(':').map((s) => (s || '').trim());
            return { guid, channel: channel || '', name: guid };
        })
        .filter((s) => s.guid);
}

function todayString(offsetDays = 0) {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    const p = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function readCache() {
    try {
        if (!fs.existsSync(TOKEN_CACHE_FILE)) return {};
        return JSON.parse(fs.readFileSync(TOKEN_CACHE_FILE, 'utf8')) || {};
    } catch (_) {
        return {};
    }
}

function writeCache(cache) {
    try {
        fs.writeFileSync(TOKEN_CACHE_FILE, JSON.stringify(cache, null, 2), 'utf8');
    } catch (e) {
        $.log(`  写 token 缓存失败: ${e.message || e}`);
    }
}

function apiHeaders(sess, extra = {}) {
    const sectoken = sess.sectoken || '';
    const d = new Date();
    const p = (n) => String(n).padStart(2, '0');
    const apmat = `${sess.openId}|${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}${p(d.getHours())}${p(d.getMinutes())}|${String(Math.floor(Math.random() * 1000000)).padStart(6, '0')}`;
    return {
        'User-Agent': UA,
        Accept: '*/*',
        'Content-Type': 'application/json',
        Referer: `https://servicewechat.com/${APP.appid}/${APP.version}/page-frame.html`,
        xweb_xhr: '1',
        apmat,
        platform: 'WX_MP',
        osType: '0',
        TCxcxVersion: '8.3.8',
        TCReferer: 'page%2Fhome%2Fmall%2Fmall',
        TCPrivacy: '1',
        'TC-MALL-PLATFORM-CODE': 'WX_MP',
        // platformflowpool（花神/看剧）还要这三件，且网关认头名大小写
        'TC-PLATFORM-CODE': 'WX_MP',
        'TC-OS-TYPE': '0',
        'TC-USER-TOKEN': sectoken,
        'TC-MALL-USER-TOKEN': sectoken,
        secToken: sectoken,
        TCSecTk: sectoken,
        ...extra,
    };
}

async function request(url, data, headers, method = 'POST') {
    const res = await axios.request({
        method,
        url,
        data,
        headers,
        timeout: 20000,
        validateStatus: () => true,
    });
    return { status: res.status, body: res.data };
}

// yyb-go 取 code：熔断/限流/服务没起来时别立刻丢掉整个号，
// 等 30~60 秒再要一次（默认最多 3 次机会），拿到就继续。
const YYB_CODE_TRIES = 3;
const YYB_CODE_RETRY_WAIT = [30000, 60000];

async function getWxCodeOnce(ref) {
    const { status, body } = await request(
        `${YYB_URL}/wxapp/getCode`,
        { ref, app_id: APP.appid },
        { 'content-type': 'application/json' }
    );
    const code =
        (body && body.data && body.data.result && body.data.result.code) ||
        (body && body.data && body.data.code) ||
        '';
    if (status !== 200 || !code || code === '0' || typeof code !== 'string') {
        throw new Error(`yyb-go 取 code 失败 HTTP ${status}: ${short(body)}`);
    }
    return code;
}

async function getWxCode(ref) {
    let lastErr = null;
    for (let attempt = 1; attempt <= YYB_CODE_TRIES; attempt++) {
        try {
            return await getWxCodeOnce(ref);
        } catch (e) {
            lastErr = e;
            if (attempt >= YYB_CODE_TRIES) break;
            $.log(
                `   yyb-go 取 code 失败（${(e && e.message) || e}），` +
                `${YYB_CODE_RETRY_WAIT[0] / 1000}~${YYB_CODE_RETRY_WAIT[1] / 1000} 秒后重试` +
                `（第 ${attempt}/${YYB_CODE_TRIES - 1} 次）`
            );
            await $.wait(YYB_CODE_RETRY_WAIT[0], YYB_CODE_RETRY_WAIT[1]);
        }
    }
    throw lastErr || new Error('yyb-go 取 code 失败');
}

async function loginByCode(code) {
    const { status, body } = await request(
        `${BASE}/wechatappapi/wxUser/login`,
        { code, scene: 1001 },
        {
            'User-Agent': UA,
            'Content-Type': 'application/json',
            Referer: `https://servicewechat.com/${APP.appid}/${APP.version}/page-frame.html`,
        }
    );
    const content = (body && (body.content || body.data)) || {};
    if (status !== 200 || !content.openId || !content.sectoken) {
        throw new Error(`登录失败 HTTP ${status}: ${short(body)}`);
    }
    return {
        openId: content.openId,
        unionId: content.unionId || '',
        memberId: content.memberId || '',
        sectoken: content.sectoken,
    };
}

async function checkSession(sess) {
    const { status, body } = await request(`${BASE}/appapi/wxuser/checkstatus`, {}, apiHeaders(sess));
    return status === 200 && !!(body && body.data && body.data.check === true);
}

async function wxApi(sess, apiPath, body, method = 'POST') {
    const isGet = method === 'GET';
    const { status, body: data } = await request(
        `${BASE}${apiPath}`,
        isGet ? undefined : body || {},
        apiHeaders(sess),
        method
    );
    if (status !== 200) throw new Error(`${apiPath} HTTP ${status}`);
    return data || {};
}

function okRes(res) {
    return !!res && (Number(res.code) === 0 || res.isSucceed === true);
}

function resMsg(res) {
    return (res && (res.msg || res.message || res.retMsg)) || short(res, 160);
}

async function queryBalance(sess) {
    const res = await wxApi(sess, '/wxmpsign/home/top', {});
    if (Number(res.code) !== 200) return null;
    const data = res.data || {};
    const n = Number(data.remainCoin != null ? data.remainCoin : data.showCoin);
    return Number.isFinite(n) ? n : null;
}

async function signIn(sess) {
    const calendar = await wxApi(sess, '/wxmpsign/sign/signCalendar', {
        beginDate: todayString(-2),
        endDate: todayString(2),
    });
    if (Number(calendar.code) !== 200) return { ok: false, msg: `签到日历失败: ${resMsg(calendar)}` };

    const infoRes = await wxApi(sess, '/wxmpsign/sign/getSignInfo', {});
    if (Number(infoRes.code) !== 200) return { ok: false, msg: `签到状态失败: ${resMsg(infoRes)}` };

    const info = infoRes.data || {};
    const cal = calendar.data || {};
    const today = cal.today || todayString();
    const todayInfo = (cal.dateInfo || []).find((x) => x.date === today) || {};
    const streak = info.periodContinuedSignDays ?? info.signDays ?? '未知';

    if (Number(info.todaySigned) === 1 || Number(cal.todaySigned) === 1 || todayInfo.isSigned === 1) {
        return {
            ok: true,
            already: true,
            mileage: todayInfo.mileage ?? info.signMileage ?? 0,
            streak,
            msg: `今日已签到，连签 ${streak} 天，今日签到里程 ${todayInfo.mileage ?? info.signMileage ?? '未知'}`,
        };
    }
    if (Number(info.canSign) === 0 || Number(cal.canSign) === 0) {
        return { ok: false, msg: '当前不可签到(canSign=0)' };
    }

    const save = await wxApi(sess, '/wxmpsign/sign/saveSignInfo', {});
    if (Number(save.code) !== 200) return { ok: false, msg: `签到失败: ${resMsg(save)}` };

    await $.wait(1000, 1800);
    const afterRes = await wxApi(sess, '/wxmpsign/sign/getSignInfo', {});
    const after = afterRes.data || {};
    if (Number(afterRes.code) !== 200 || Number(after.todaySigned) !== 1) {
        return { ok: false, msg: `签到接口成功但状态未更新: ${short(afterRes)}` };
    }
    return {
        ok: true,
        mileage: after.signMileage ?? todayInfo.mileage ?? 0,
        streak: after.periodContinuedSignDays ?? streak,
        tomorrow: after.tomorrowMileage,
        msg: `签到成功，今日 +${after.signMileage ?? todayInfo.mileage ?? '?'} 里程，连签 ${after.periodContinuedSignDays ?? streak} 天，明日 +${after.tomorrowMileage ?? '?'}`,
    };
}

function skipTask(task) {
    if (Number(task.status) === 3) return '已完成';
    if (Number(task.taskType) === 3) return '小游戏需真玩';
    if (Number(task.taskType) === 5) return '客服对话类，只能手动';
    if (/下拉/.test(task.title || '')) return '需真机添加到下拉';
    if (/客服|分享|邀好友|助力/.test(task.title || '')) return '社交类，只能手动';
    return '';
}

async function refreshTaskStatus(sess, schemeGuid, detailGuid) {
    const res = await wxApi(sess, '/qiushiinnerapi/task/detail', { detailGuid, schemeGuid });
    const tasks = (res.data && res.data.taskDetails) || [];
    const task = tasks.find((x) => x.detailGuid === detailGuid) || tasks[0];
    return task ? Number(task.status) : null;
}

async function runScheme(sess, scheme) {
    const list = await wxApi(sess, '/qiushiinnerapi/task/detailList', {
        detailGuid: '',
        pageNum: 1,
        pageSize: 999,
        schemeGuid: scheme.guid,
    });
    if (Number(list.code) !== 0) {
        $.log(`  [${scheme.name}] 任务列表失败: ${resMsg(list)}`);
        return { claimed: [], failed: 1 };
    }
    const tasks = (list.data && list.data.taskDetails) || [];
    const autoSend = Number((list.data && list.data.taskScheme && list.data.taskScheme.isAutoSend) || 0) === 1;
    const claimed = [];
    let failed = 0;

    if (scheme.reportOnly) {
        const todo = tasks.filter((t) => Number(t.status) !== 3);
        $.log(
            `  [${scheme.name}] ${scheme.reportOnly}；共 ${tasks.length} 个，未完成 ${todo.length} 个` +
                `${todo.length ? `：${todo.map((t) => `${t.title}${t.prizeTitle ? `(+${t.prizeTitle})` : ''}`).join('、')}` : ''}`
        );
        // status 2 = 已完成待领取：这类任务的手工环节（客服对话 / 真机下拉）省不了，
        // 但奖励本身能脚本领——客服任务实测 finishTask 回 3901「该类型任务不支持通过API操作」，
        // 聊过之后 status 变 2，sendTaskPrize 直接成功并跳到 3
        if (!FLOWER_ENABLED && /客服/.test(scheme.name)) {
            $.log(`  [${scheme.name}] 花神已关闭，跳过「摇签机会」类待领奖励`);
        }
        for (const t of FLOWER_ENABLED ? tasks.filter((x) => Number(x.status) === 2) : []) {
            const title = t.title || t.detailGuid;
            const claim = await wxApi(sess, '/qiushiinnerapi/task/sendTaskPrize', {
                detailGuid: t.detailGuid,
                schemeGuid: scheme.guid,
            });
            if (okRes(claim)) {
                claimed.push({ title, reward: t.prizeTitle || '' });
                $.log(`  [${scheme.name}] 领取「${title}」成功（任务已完成待领取）`);
            } else {
                $.log(`  [${scheme.name}] 领取「${title}」失败：${resMsg(claim)}`);
            }
            await $.wait(500, 1200);
        }
        return { claimed, failed };
    }

    for (const task of tasks) {
        const title = task.title || task.detailGuid;
        const why = skipTask(task);
        if (why) {
            $.log(`  [${scheme.name}] 跳过「${title}」：${why}`);
            continue;
        }
        const reward = task.buttonText || (task.prizeTitle ? `${task.prizeTitle}里程` : '');
        let status = Number(task.status) || 0;

        if (status === 0) {
            const start = await wxApi(sess, '/qiushiinnerapi/task/startTask', {
                detailGuid: task.detailGuid,
                schemeGuid: scheme.guid,
                ...(scheme.channel ? { channel: scheme.channel } : {}),
            });
            if (!okRes(start)) {
                status = await refreshTaskStatus(sess, scheme.guid, task.detailGuid);
                if (!status) {
                    $.log(`  [${scheme.name}] 「${title}」开始失败: ${resMsg(start)}`);
                    failed++;
                    continue;
                }
                $.log(`  [${scheme.name}] 「${title}」开始返回「${resMsg(start)}」，但任务已在进行(state=${status})`);
            } else {
                status = 1;
            }
            const countDown = Number(task.countDown) || 0;
            await $.wait(countDown > 0 ? (countDown + 1) * 1000 : 500, countDown > 0 ? (countDown + 2) * 1000 : 1100);
        }

        if (status === 3) {
            // finish 对部分任务（taskType=1）会直接发奖，状态直接跳到已完成
            claimed.push({ title, reward });
            $.log(`  [${scheme.name}] 「${title}」已完成（奖励已到账）`);
            continue;
        }

        if (status <= 1) {
            const finish = await wxApi(sess, '/qiushiinnerapi/task/finishTask', {
                detailGuid: task.detailGuid,
                schemeGuid: scheme.guid,
            });
            if (!okRes(finish)) {
                status = await refreshTaskStatus(sess, scheme.guid, task.detailGuid);
                if (!status || status < 2) {
                    const whyMsg = resMsg(finish);
                    if (Number(finish.code) === 3901 || /不支持通过API操作/.test(whyMsg)) {
                        // 服务端明确不许 API 完成（如「看短剧」要客户端回传观看时长）：只播报，不计失败
                        $.log(`  [${scheme.name}] 跳过「${title}」：服务端不支持 API 完成（${whyMsg}），需真机操作`);
                    } else {
                        $.log(`  [${scheme.name}] 「${title}」完成失败: ${whyMsg}`);
                        failed++;
                    }
                    continue;
                }
                $.log(`  [${scheme.name}] 「${title}」完成返回「${resMsg(finish)}」，但任务状态已推进(state=${status})`);
            } else {
                status = 2;
                await $.wait(700, 1500);
            }
        }

        if (autoSend) {
            // 方案开了自动发奖（isAutoSend=1），finish 之后不调领奖。
            // 只有服务端确认 state=3 才算到账；仍停在 2 或查询失败都不能计入领取
            const st = await refreshTaskStatus(sess, scheme.guid, task.detailGuid);
            if (st === 3) {
                claimed.push({ title, reward });
                $.log(`  [${scheme.name}] 「${title}」完成即自动发奖${reward ? ` +${reward}` : ''}（state=3）`);
            } else {
                $.log(
                    `  [${scheme.name}] 「${title}」完成后未确认到账` +
                        `${st ? `（state=${st}）` : '（状态查询失败）'}，未计入领取`
                );
            }
            continue;
        }

        const claim = await wxApi(sess, '/qiushiinnerapi/task/sendTaskPrize', {
            detailGuid: task.detailGuid,
            schemeGuid: scheme.guid,
        });
        if (!okRes(claim)) {
            const st = await refreshTaskStatus(sess, scheme.guid, task.detailGuid);
            if (st === 3) {
                claimed.push({ title, reward });
                $.log(`  [${scheme.name}] 「${title}」领奖返回「${resMsg(claim)}」，任务已完成（奖励已自动到账）`);
                continue;
            }
            $.log(`  [${scheme.name}] 「${title}」领奖失败: ${resMsg(claim)}`);
            failed++;
            continue;
        }
        claimed.push({ title, reward });
        await $.wait(500, 1200);
    }

    // 逐条领取不再刷屏，按方案汇总一行；完整清单在账号末尾「领到：」
    if (claimed.length || failed) {
        $.log(`  [${scheme.name}] 领取 ${claimed.length} 个` + (failed ? `，失败 ${failed} 个` : ''));
    }

    return { claimed, failed };
}

/**
 * 花神祈福：摇签（drawCard）抽卡 → 翻卡（flipCard）领里程
 * 摇签次数来自分享好友 / 赠花签 / 邀助力 / 客服对话，脚本不刷，只把手上次数和待翻卡用掉
 */
/**
 * 花神补充动作（2026-10-25 从 flowerGod H5 bundle 挖出来的）：
 *   POST /platformflowpool/flowerGod/receiveSharingReward {} -> 每日分享奖励（摇签次数 +1）
 *   POST /platformflowpool/flowerGod/helperAssist {sponsorEncryptUserKey} -> 帮别人助力（对方「邀好友必得花神签」+1）
 *        注意：助力方自己必须参与过该活动，否则回 100001 你还没有参与该活动
 *   GET  /platformflowpool/flowerGod/prizeList?pageNum=0&pageSize=100&type=1 -> 已得奖品
 *   POST /platformflowpool/flowerGod/exchangeCash {} -> 集齐 6 种卡后兑换现金（未集齐回 100001 集齐才可兑换哦~）
 */
async function flowerExtras(sess, dryRun, acc) {
    const out = { shareReward: false, prizes: [], exchanged: '', msg: '' };

    if (!dryRun) {
        const r = await wxApi(sess, `${FLOWER_BASE}/receiveSharingReward`, {});
        if (Number(r.code) === 0) {
            out.shareReward = true;
            // 分享奖励发的是「摇签次数 +1」，当场摇掉并翻卡，别留着过期
            await flowerRedraw(acc || { sess, log: (m) => $.log(m) });
        }
    }

    // 一次 home 拿全：签种类数（服务端下发几张就集几张）+ 客服任务 guid（每期可能换）
    let home = null;
    try {
        const h = await wxApi(sess, `${FLOWER_BASE}/home`, null, 'GET');
        home = h.data || null;
        const kindsTotal = home && Array.isArray(home.cardList) ? home.cardList.length : 0;
        if (kindsTotal > 0) FG_KINDS_TOTAL = kindsTotal;
    } catch (_) {
        /* 拿不到就沿用默认/上次的 */
    }

    // 客服任务：guid 动态取，status 2（已完成待领取）脚本直接领，不写死 detailGuid
    if (home && !dryRun) {
        try {
            const ct = await flowerCustomerTask(sess, home);
            const st = ct ? ct.status : -1;
            if (ct && ct.claimed) out.customer = `${ct.title || '客服任务'} 已领（status 2→3）`;
            else if (st === 2) out.customer = `客服任务领奖失败：${ct.msg}`;
            else if (st === 0) out.customer = '客服任务未完成（要真去回一句“花签”）';
            else if (st === 3) out.customer = '客服任务今日已完成（若明天又变 0 就是每日任务）';
            else if (ct) out.customer = `客服任务 status=${st}`;
        } catch (e) {
            $.log(`  花神客服任务异常: ${e.message || e}`);
        }
    }

    try {
        const pl = await wxApi(sess, `${FLOWER_BASE}/prizeList?pageNum=0&pageSize=100&type=1`, null, 'GET');
        out.prizes = ((pl.data || {}).list || []).map((x) => x.prizeSubTitle || x.rewardName || '').filter(Boolean).slice(0, 5);
    } catch (_) {
        /* 查不到奖品不影响主流程 */
    }

    // 集齐一整期才去兑，避免白发请求（种类数来自 home.cardList，不写死 6）
    try {
        const cl = await wxApi(sess, `${FLOWER_BASE}/cardList`, null, 'GET');
        const kinds = new Set((Array.isArray(cl.data) ? cl.data : []).map((c) => Number(c.cardType))).size;
        if (kinds >= FG_KINDS_TOTAL) {
            if (dryRun) {
                out.msg = `集齐 ${FG_KINDS_TOTAL} 种（演练模式没兑换）`;
            } else {
                const r = await wxApi(sess, `${FLOWER_BASE}/exchangeCash`, {});
                out.exchanged = Number(r.code) === 0 ? '兑换成功' : resMsg(r);
            }
        } else {
            out.kinds = kinds;
            out.deadline = await flowerDeadline(sess);
        }
    } catch (_) {
        /* ignore */
    }

    if (home) {
        const hg = (home.taskList || []).find((t) => Number(t.taskType) === 3) || null;
        if (hg && Number(hg.targetHelpCount) > 0) {
            out.helpTask = `${Number(hg.helpTaskCompletedCount) || 0}/${Number(hg.targetHelpCount)}`;
        }
    }

    const parts = [];
    if (out.shareReward) parts.push('分享奖励已领（摇签 +1）');
    if (out.helpTask) parts.push(`邀好友花神签 ${out.helpTask}`);
    if (out.customer) parts.push(out.customer);
    if (out.kinds != null) parts.push(`集齐 ${out.kinds}/${FG_KINDS_TOTAL} 种${out.deadline ? `（本期 ${out.deadline} 清零，集齐即兑）` : ''}`);
    if (out.exchanged) parts.push(`集齐兑换：${out.exchanged}`);
    if (out.prizes.length) parts.push(`已得奖品 ${out.prizes.join('、')}`);
    out.msg = `花神补充：${parts.join('，') || '无动作'}`;
    return out;
}

async function flowerGod(sess, dryRun) {
    const home = await wxApi(sess, `${FLOWER_BASE}/home`, null, 'GET');
    if (Number(home.code) !== 0) return { ok: false, msg: `花神首页失败: ${resMsg(home)}`, got: [], remain: 0 };
    const data = home.data || {};
    const remain = Number(data.remainDrawCount) || 0;

    const pendingCards = async () => {
        const list = await wxApi(sess, `${FLOWER_BASE}/cardList`, null, 'GET');
        if (Number(list.code) !== 0) {
            $.log(`  花神卡列表失败: ${resMsg(list)}`);
            return [];
        }
        return (Array.isArray(list.data) ? list.data : []).filter((c) => Number(c.state) === 6);
    };

    if (!dryRun) {
        for (let i = 0; i < Math.min(remain, 10); i++) {
            const draw = await wxApi(sess, `${FLOWER_BASE}/drawCard`, { usage: 'common' });
            if (Number(draw.code) !== 0) {
                $.log(`  花神摇签失败: ${resMsg(draw)}`);
                break;
            }
            $.log(`  花神摇签 ${i + 1}/${remain}：${(draw.data && draw.data.cardName) || '抽到一张'}`);
            await $.wait(800, 1600);
        }
    }

    const cards = await pendingCards();
    const got = [];
    for (const card of cards) {
        const name = card.cardName || `cardId=${card.cardId}`;
        // 别人赠的卡翻不了（接口回「赠送的卡片不允许翻卡」），只算集齐种类
        if (Number(card.cardSource) === 5) continue;
        if (dryRun) {
            got.push({ name, reward: '待翻' });
            $.log(`  花神待翻卡「${name}」`);
            continue;
        }
        const flip = await wxApi(sess, `${FLOWER_BASE}/flipCard`, { cardId: card.cardId });
        if (Number(flip.code) !== 0) {
            $.log(`  花神翻卡「${name}」失败: ${resMsg(flip)}`);
            continue;
        }
        const d = flip.data || {};
        const reward = d.rewardName || d.qsPrizeName || '无奖励';
        got.push({ name: d.cardName || name, reward });
        $.log(`  花神翻卡「${d.cardName || name}」→ ${reward}`);
        await $.wait(600, 1200);
    }

    return {
        ok: true,
        remain,
        got,
        msg: `花神：抽卡前摇签次数 ${remain}，翻卡 ${got.length} 张${got.length ? `（${got.map((x) => x.reward).join('、')}）` : ''}`,
    };
}

/**
 * 短剧（看剧）里程：
 *   访问  POST /platformflowpool/drama/getBaseData {refid}    —— 短剧页加载时就有，登记访问，返回 extInfo
 *   领访问奖 POST /platformflowpool/drama/recVisitReward {}    —— 实测 +2 里程，响应 data.visitMileageReward
 *   看剧任务 POST /platformflowpool/drama/getWatchTaskStatus {refid}
 *            taskStatus：0 未看够 / 1 可领 / 2 今日已领，watchSeconds 是要看满的秒数（5）
 *   领看剧奖 POST /platformflowpool/drama/recWatchTaskReward {} —— +10 里程；已领过回 120003
 * 机制（2026-10-25 复核 短剧.har，别再试图伪造时长上报）：
 *   - 看剧在微信短剧流量位小程序 wx404dde55fb12df78（官方播放器插件 wx94a6522b1d640c3b 的
 *     playlet 页）里，同程把 getBaseData 的 extInfo 作为 _wxExtInfo 启动参数带过去做归因；
 *   - 视频是 vodpreview 一次性防盗链签名 URL（t/us/sign），观看时长由微信短剧平台服务端统计后
 *     回传同程——上报这个动作不在客户端；
 *   - 看剧期间短剧小程序只有微信统计埋点（SdkReport/zhiyan），没有任何业务 API 可登录可调；
 *     同程侧明文与云托管加密通道（/__wx__/call，转发目标可在 wxa-qbase/report 日志里核对）
 *     两条路都零调用，回程状态直接翻转（taskStatus 0->1，todayWatchSeconds 0->188 = 播放 186+2 秒）。
 *   - 所以 watchSeconds 攒不够只能真看；领奖侧（+2/+10）与时长收益（自动到账）脚本已全自动。
 */
async function dramaMileage(sess, dryRun) {
    const refids = String(process.env.tclx_drama_refid || DRAMA_REFID)
        .split(/[,&\s]+/)
        .map((s) => s.trim())
        .filter(Boolean);
    const result = { visitReward: 0, watchReward: 0, state: 'unknown', need: 5, amount: 10, msg: '' };

    try {
        await wxApi(sess, `${DRAMA_BASE}/getBaseData`, { refid: refids[0] });
    } catch (_) {
        /* 访问登记失败不影响后面领奖 */
    }

    if (!dryRun) {
        const visit = await wxApi(sess, `${DRAMA_BASE}/recVisitReward`, {});
        if (Number(visit.code) === 0) result.visitReward = Number((visit.data && visit.data.visitMileageReward) || 0);
        else $.log(`  短剧访问奖励领取失败: ${resMsg(visit)}`);
    }

    let claimableRefid = '';
    let sawNotWatched = false;
    for (const refid of refids) {
        const st = await wxApi(sess, `${DRAMA_BASE}/getWatchTaskStatus`, { refid });
        if (Number(st.code) !== 0) continue;
        const d = st.data || {};
        result.need = Number(d.watchSeconds) || result.need;
        result.amount = Number(d.amount) || result.amount;
        const status = Number(d.taskStatus);
        if (status === 1) {
            claimableRefid = refid;
            result.state = 'claimable';
            break;
        }
        if (status === 0) {
            sawNotWatched = true;
            result.state = 'not-watched';
        } else if (status === 2 && result.state !== 'not-watched') {
            result.state = 'claimed';
        }
    }

    if (claimableRefid && !dryRun) {
        const rec = await wxApi(sess, `${DRAMA_BASE}/recWatchTaskReward`, {});
        if (Number(rec.code) === 0) result.watchReward = result.amount;
        else if (Number(rec.code) === 120003) {
            result.state = 'claimed';
            result.msg = resMsg(rec);
        } else $.log(`  短剧看剧奖励领取失败: ${resMsg(rec)}`);
    }

    const income = await wxApi(sess, `${DRAMA_BASE}/getMileageIncome`, {});
    if (Number(income.code) === 0) {
        const d = income.data || {};
        result.todayIncome = d.todayMileageIncome;
        result.balance = d.mileageBalance;
        result.estimated = d.todayEstimatedMileage;
    }

    // 看剧本身按时长结算里程：抓包里看 186 秒 => incomeMileage 10，余额 2633->2643 没发任何请求，
    // 说明是剧集侧回传后自动到账的，没有领奖接口，脚本只能统计 + 提示还差多少额度
    try {
        const hist = await wxApi(sess, `${DRAMA_BASE}/getHistoryWatch`, { pageIndex: 1, pageSize: 10 });
        if (Number(hist.code) === 0) {
            const watched = ((hist.data && hist.data.list) || []).filter((x) => Number(x.watchTime) > 0);
            result.watchSeconds = watched.reduce((s, x) => s + (Number(x.watchTime) || 0), 0);
            result.watchIncome = watched.reduce((s, x) => s + (Number(x.incomeMileage) || 0), 0);
            result.dramas = watched
                .sort((a, b) => (Number(b.incomeMileage) || 0) - (Number(a.incomeMileage) || 0))
                .slice(0, 3)
                .map((x) => `${x.dramaName}（${x.watchTime}s/+${x.incomeMileage || 0}）`);
        }
    } catch (e) {
        $.log(`  看剧记录查询失败: ${e.message || e}`);
    }

    const parts = [];
    if (result.visitReward) parts.push(`访问 +${result.visitReward}`);
    if (result.watchReward) parts.push(`看剧任务 +${result.watchReward}`);
    if (result.state === 'not-watched') parts.push(`看剧任务还差时长（需看满 ${result.need} 秒，剧集侧回传，脚本伪造不了）`);
    if (result.state === 'claimed') parts.push('看剧任务今日已领');
    if (result.state === 'unknown') parts.push('看剧任务状态未知（查询失败，未计入）');
    if (result.state === 'claimable' && dryRun) parts.push(`看剧任务可领 +${result.amount}（演练模式没领）`);
    if (result.watchIncome) parts.push(`看剧时长收益 +${result.watchIncome}（${result.watchSeconds} 秒）`);

    const rest =
        result.estimated != null && result.todayIncome != null
            ? Math.max(0, Number(result.estimated) - Number(result.todayIncome))
            : null;
    result.msg =
        `短剧：${parts.join('，') || '无可领'}` +
        `${result.todayIncome != null ? `；今日短剧里程 ${result.todayIncome}/${result.estimated ?? '?'}` : ''}` +
        `${rest ? `，还剩 ${rest} 额度（看得越久给越多，需真看）` : ''}` +
        `${result.dramas && result.dramas.length ? `；最近：${result.dramas.join('、')}` : ''}`;
    return result;
}

/**
 * 打卡挑战（里程版）—— 活动规则（getShareMileageConfig.rule 原文）：
 *   今天付 100 里程报名 → 次日 00:00-14:00 在「同程小程序-优惠/福利中心-每日签到」签到
 *   即打卡成功 → 当日 15:00 按奖池瓜分（池子 = 报名人数 ×(100 + 系统 10)）
 *   次日没打卡 = 100 里程没收，分给别人
 * 关键：报名是「为明天打卡付费」，打卡动作就是脚本每天都在做的 saveSignInfo，
 *      所以只要定时任务落在 00:00-14:00 窗口内，这条链路可以全自动闭环。
 * 默认不报名（花里程要显式同意）：tclx_checkin=1 才报，tclx_checkin_reserve 保留余量（默认 200）
 *   GET  /wxmpsign/share/mileage/getShareMileageConfig                  配置
 *   GET  /wxmpsign/share/mileage/getTodayTotalShareMileage             今日奖池
 *   POST /wxmpsign/share/mileage/getUserParticipationInfo               {startDate,limitAmount,endDate}
 *   POST /wxmpsign/share/mileage/participateInShareMileage {}           报名（扣 payMileageAmount）
 *   GET  /wxmpsign/share/mileage/yesterdayParticipateInShareMileage     昨日是否参与
 * 记录字段：payMileageAmount 投入 / getMileageAmount 分到的 / finishStatus -1 未打卡 / sendMileageStatus 0 未发放
 */
async function checkinChallenge(sess, dryRun, balance) {
    const out = { msg: '', joined: false, gain: 0 };
    const dayStr = (offset) => {
        const d = new Date(Date.now() + offset * 86400000);
        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    };
    const recOf = async (date) => {
        const r = await wxApi(sess, '/wxmpsign/share/mileage/getUserParticipationInfo', {
            startDate: `${date} 00:00:00`,
            endDate: `${date} 23:59:59`,
            limitAmount: 1,
        });
        // 只有真的拿到列表才算「确实没报名」；接口异常/业务错误一律返回 ok:false，
        // 否则会被当成「今天没报名」→ 重复扣 100 里程
        if (!Array.isArray(r.data)) return { ok: false, rec: null, msg: resMsg(r) };
        return { ok: true, rec: r.data[0] || null };
    };

    let cfg = {};
    try {
        const c = await wxApi(sess, '/wxmpsign/share/mileage/getShareMileageConfig', null, 'GET');
        cfg = c.data || {};
    } catch (_) {
        /* 配置拿不到就按默认值 */
    }
    const pay = Number(cfg.payMileageAmount) || 100;
    const lastest = cfg.lastestSignTime || '14:00:00';
    const settle = cfg.sendMileageTime || '15:00';

    const parts = [];
    try {
        const p = await wxApi(sess, '/wxmpsign/share/mileage/getTodayTotalShareMileage', null, 'GET');
        const d = p.data || {};
        if (Number(d.participateCount) > 0) {
            const avg = Math.round(Number(d.totalMileage) / Number(d.participateCount));
            parts.push(`今日奖池 ${d.totalMileage} 里程 / ${d.participateCount} 人（人均 ~${avg}）`);
        }
    } catch (_) {
        /* 池子拿不到不影响报名判断 */
    }

    // 昨天的结算结果（这是判断这套玩法值不值得继续的唯一实证）
    try {
        const y = (await recOf(dayStr(-1))).rec;
        if (y) {
            const got = Number(y.getMileageAmount) || 0;
            const put = Number(y.payMileageAmount) || pay;
            // 打卡收益 15:00 后才结算，07:30 读到 finishStatus=-1 只是"待结算"，不能判成没收
            const beforeSettle = new Date().toTimeString().slice(0, 5) < String(settle).slice(0, 5);
            if (Number(y.finishStatus) === -1) {
                parts.push(
                    beforeSettle
                        ? `昨日投入 ${put} 里程，结算未出（${settle} 后到账），打卡结果待确认`
                        : `昨日投入 ${put} 里程但未打卡（已没收）`
                );
            } else if (got > 0) {
                out.gain = got - put;
                parts.push(`昨日分到 ${got} 里程（投入 ${put}，净 ${out.gain >= 0 ? '+' : ''}${out.gain}）`);
            } else {
                parts.push(`昨日已打卡，${settle} 结算中`);
            }
        }
    } catch (_) {
        /* ignore */
    }

    let todayRes = { ok: false, rec: null, msg: '' };
    try {
        todayRes = await recOf(dayStr(0));
    } catch (e) {
        todayRes = { ok: false, rec: null, msg: e.message || String(e) };
    }
    const today = todayRes.rec;

    if (today) {
        out.joined = true;
        parts.push(`今日已报名（投入 ${today.payMileageAmount} 里程），明天 00:00-${lastest} 要签到才算打卡`);
    } else if (dryRun) {
        parts.push(`今日未报名（演练模式不报名，报名花 ${pay} 里程）`);
    } else if (String(process.env.tclx_checkin || '').toLowerCase() !== '1') {
        parts.push(`今日未报名（tclx_checkin=1 才自动报名，报名花 ${pay} 里程）`);
    } else if (!todayRes.ok) {
        // 查询失败时状态未知，既可能已报名也可能没报：宁可少赚一次，也不重复扣里程
        parts.push(`查不到今日报名记录（${todayRes.msg || '接口异常'}），为避免重复扣里程，本次不自动报名`);
    } else if (balance == null) {
        parts.push(`余额未知，无法确认报名后是否还有余量，本次不自动报名`);
    } else {
        const reserve = Number(process.env.tclx_checkin_reserve || 200);
        if (Number(balance) < pay + reserve) {
            parts.push(`里程不够（${balance} < ${pay}+${reserve} 余量），今天不报名`);
        } else {
            const r = await wxApi(sess, '/wxmpsign/share/mileage/participateInShareMileage', {});
            if (Number(r.code) === 200 || Number(r.code) === 0) {
                out.joined = true;
                parts.push(`已报名（花 ${pay} 里程）→ 明天 00:00-${lastest} 必须签到，否则 ${pay} 里程没收`);
            } else {
                parts.push(`报名失败：${resMsg(r)}`);
            }
        }
    }

    out.msg = `打卡挑战：${parts.join('，') || '无数据'}`;
    return out;
}

/**
 * 其余赚里程入口只能在页面里手动完成，这里只播报
 */
async function reportExtraSources(sess, balance) {
    const read = async (fn) => {
        try {
            return await fn();
        } catch (e) {
            return { __error: e.message || String(e) };
        }
    };

    const lottery = await read(() => wxApi(sess, '/qiushiinnerapi/fission/lottery/list', { schGuid: LOTTERY_SCH }));
    if (lottery && !lottery.__error && okRes(lottery)) {
        const d = lottery.data || {};
        $.log(
            `  同程钞级省抽奖：今日剩余 ${d.lotteryCount ?? 0}/${d.maxLotteryCount ?? 0} 次` +
                `${Number(d.lotteryCount) > 0 ? '（脚本会在下面自动抽）' : ''}`
        );
    }

    // 打卡挑战：花里程的活动，但闭环能全自动（签到=打卡），详见 checkinChallenge
    try {
        const ck = await checkinChallenge(sess, DRY_RUN, balance);
        if (ck && ck.msg) $.log(`  ${ck.msg}`);
    } catch (e) {
        $.log(`  打卡挑战异常: ${e.message || e}`);
    }
}


/**
 * 互助：多账号之间互相刷「邀好友 / 赠送」类任务（tclx 里配 2 个以上账号才跑）
 *   抽奖助力  POST /qiushiinnerapi/fission/lottery/help {schGuid, shareGuid}
 *             shareGuid 用「被助力方」lottery/list 里的 share.currentShareId；成功回 data.helpStatus=1
 *   花神赠卡  POST /platformflowpool/flowerGod/grantCard {sponsorEncryptUserKey, cardId}
 *             sponsorEncryptUserKey 填**接收方** flowerGod/home 返回的 key，卡直接进对方账号（不用对方领）；
 *             赠送方「每日赠花签」任务 +1、摇签次数 +1（实测 by 送 1 张后 give=1/3、remainDrawCount 0→1）
 *             receiveCard 是「好友索要卡片」那条线才用，互助用不上
 */
/**
 * 花神赠卡选卡 —— 赠卡要坚持每天完成，按实价算的账：
 *   集齐一套 6 种只换 0.11-0.88 元现金（里程抵现 100≈10.51 元，折 1-8 里程），
 *   而赠出 1 张 = +1 次抽签（抽一张翻卡 2-666 里程），连续 3 天赠签还必得花神签
 *   （花神签正常抽中率只有 6%）。所以「保住集齐」不如「每天送一张」。
 * 优先顺序：
 *   ① 重复种类 + 对方缺（自己不掉种类，对方补齐）—— 最优
 *   ② 重复种类（对方已有，纯换抽签次数）
 *   ③ 唯一种类 + 对方缺（自己 -1 种、对方 +1 种，两边都把赠卡任务做完）
 *   ④ 唯一种类 + 对方也有：只在 tclx_fg_giftmode=daily 时送（纯换次数，对方无收益）
 * 不可转赠：收到的卡（cardSource 5，实测 flipCard 也回「赠送的卡片不允许翻卡」）、花神签
 */
function pickGiftCard(host, helper) {
    const byType = {};
    for (const c of host.cards || []) {
        // 花神签不可转赠：编号不写死（换期可能变），用 FG_GOD_TYPES（预置 + 被拒自动学习）
        if (Number(c.cardSource) === 5 || FG_GOD_TYPES.has(Number(c.cardType))) continue;
        const t = Number(c.cardType);
        (byType[t] = byType[t] || []).push(c);
    }
    const types = Object.keys(byType);
    if (!types.length) return null;
    const helperHas = new Set((helper.cards || []).map((c) => Number(c.cardType)));
    const dupLack = types.filter((t) => byType[t].length > 1 && !helperHas.has(Number(t)));
    const dup = types.filter((t) => byType[t].length > 1);
    const soloLack = types.filter((t) => byType[t].length === 1 && !helperHas.has(Number(t)));
    const greedy = String(process.env.tclx_fg_giftmode || '').toLowerCase() === 'daily';
    const pick = dupLack[0] ?? dup[0] ?? soloLack[0] ?? (greedy ? types[0] : null);
    if (pick == null) return null;
    const list = byType[pick];
    return list[list.length - 1];
}


// 赠卡每天每号只送 1 张（任务按天算），一天跑多次别把卡送光。
// 接口没有「今天是否已送」的字段（buttonState 不可靠），本地记个当日状态文件。
const GIFT_STATE_FILE =
    process.env.tclx_gift_state || require('path').join(__dirname, '.tclx_gift_state.json');

function markGiftSent(accKey) {
    try {
        const fs = require('fs');
        const day = todayString();
        let j = {};
        try {
            j = JSON.parse(fs.readFileSync(GIFT_STATE_FILE, 'utf8')) || {};
        } catch (_) {
            j = {};
        }
        // 只保留当天，跨天自动清零
        const sent = j.date === day && Array.isArray(j.sent) ? j.sent : [];
        if (!sent.includes(String(accKey))) sent.push(String(accKey));
        fs.writeFileSync(GIFT_STATE_FILE, JSON.stringify({ date: day, sent }));
    } catch (_) {
        /* 写不了就算了，最多多送一张 */
    }
}

function sentGiftToday(accKey) {
    try {
        const fs = require('fs');
        const j = JSON.parse(fs.readFileSync(GIFT_STATE_FILE, 'utf8')) || {};
        return j.date === todayString() && Array.isArray(j.sent) && j.sent.includes(String(accKey));
    } catch (_) {
        return false;
    }
}
/**
 * 赠卡换来的抽签机会立刻用掉（规则：好友成功领取后，赠卡方可额外获得 1 次抽取花签的机会）
 * 抽到的卡照常翻卡拿里程；收到别人送的卡（cardSource 5）不能翻，跳过
 */
async function flowerRedraw(acc) {
    for (let i = 0; i < 2; i++) {
        let remain = 0;
        try {
            const home = await wxApi(acc.sess, `${FLOWER_BASE}/home`, null, 'GET');
            remain = Number((home.data || {}).remainDrawCount) || 0;
        } catch (_) {
            return;
        }
        if (remain <= 0) break;
        const draw = await wxApi(acc.sess, `${FLOWER_BASE}/drawCard`, { usage: 'common' });
        if (Number(draw.code) !== 0) {
            acc.log(`  花神补摇失败: ${resMsg(draw)}`);
            break;
        }
        acc.log(`  花神补摇（赠卡奖励）：${(draw.data && draw.data.cardName) || '抽到一张'}`);
        await $.wait(800, 1500);
    }
    try {
        const cl = await wxApi(acc.sess, `${FLOWER_BASE}/cardList`, null, 'GET');
        for (const c of Array.isArray(cl.data) ? cl.data : []) {
            if (Number(c.state) !== 6 || Number(c.cardSource) === 5) continue;
            const fl = await wxApi(acc.sess, `${FLOWER_BASE}/flipCard`, { cardId: c.cardId });
            if (Number(fl.code) === 0) {
                const d = fl.data || {};
                acc.log(`  花神翻卡「${c.cardName || c.cardId}」→ ${d.rewardName || d.qsPrizeName || '无奖励'}`);
            }
            await $.wait(600, 1200);
        }
    } catch (_) {
        /* 补翻失败不影响主流程 */
    }
}

async function mutualHelp(accounts) {
    if (accounts.length < 2) {
        $.log('🤝 互助：账号少于 2 个，跳过');
        return;
    }
    const tagOf = (acc) => `账号[${acc.index}]${acc.account.remark ? `[${acc.account.remark}]` : ''}`;
    const state = [];

    for (const acc of accounts) {
        const info = { acc, key: '', cards: [], shareId: '', giveLeft: 3, remain: 0, helped: 0, given: 0,
                       helpTarget: 0, helpDone: 0, signMileage: 0, signHelped: 0 };
        try {
            const home = FLOWER_ENABLED
                ? await wxApi(acc.sess, `${FLOWER_BASE}/home`, null, 'GET')
                : { code: 0, data: {} };
            const d = home.data || {};
            info.key = d.sponsorEncryptUserKey || '';
            info.remain = Number(d.remainDrawCount) || 0;
            const give = (d.taskList || []).find((t) => Number(t.taskType) === 2) || {};
            // 连续赠签天数/总天数都用服务端下发的（规则：连续 N 天必得花神签），不写死 3
            const need = Number(give.giveTaskTotalDays) || 3;
            info.giveLeft = Math.max(0, need - (Number(give.giveTaskConsecutiveDays) || 0));
            // 「邀好友必得花神签」（taskType 3）：targetHelpCount 人助力后直接发花神签
            const hg = (d.taskList || []).find((t) => Number(t.taskType) === 3) || {};
            info.helpTarget = Number(hg.targetHelpCount) || 0;
            info.helpDone = Number(hg.helpTaskCompletedCount) || 0;
        } catch (e) {
            acc.log(`互助：花神首页失败 ${e.message || e}`);
        }
        try {
            const cl = FLOWER_ENABLED
                ? await wxApi(acc.sess, `${FLOWER_BASE}/cardList`, null, 'GET')
                : { code: 0, data: [] };
            info.cards = (Array.isArray(cl.data) ? cl.data : []).filter((c) => c && c.cardId);
        } catch (_) {
            /* 没卡就不送 */
        }
        try {
            const lot = await wxApi(acc.sess, '/qiushiinnerapi/fission/lottery/list', { schGuid: LOTTERY_SCH });
            const share = (lot.data || {}).share || {};
            info.shareId = share.currentShareId || share.newShareId || '';
        } catch (_) {
            /* 没 shareId 就不助力 */
        }
        try {
            // 限时翻倍：签到分享玩法，好友帮签到一次我给 +2 里程（每号每天 1 次）
            const sd = await wxApi(acc.sess, '/qiushiinnerapi/fission/sign/detail', { shareGuid: '' });
            const sdData = sd.data || {};
            info.signShare = sdData.shareGuid || '';
            // 邀好友限时翻倍签到：todaySignMileageCount = 今天这条分享累计拿到的里程（实测一次 +20）
            info.signMileage = Number(sdData.todaySignMileageCount) || 0;
        } catch (_) {
            /* 没 signShare 就跳过 */
        }
        state.push(info);
    }

    // 集卡缺口：决定花神助力次数投给谁
    for (const s of state) {
        const types = new Set((s.cards || []).map((c) => Number(c.cardType)));
        s.kinds = types.size;
        s.missing = [];
        for (let t = 0; t < FG_KINDS_TOTAL; t++) if (!types.has(t)) s.missing.push(t);
        // 只差花神签但「邀好友必得花神签」还没满的号，照样该吃助力——那是唯一能直接补花神签的入口
        s.worthGod = s.missing.some((t) => t !== FLOWER_LAST_TYPE) || s.helpTarget > s.helpDone;
    }

    // 互助顺序：钞级省奖品格助力（直接解锁现金奖品）排最前，先给指定号凑满
    // tclx_help_priority 逗号分隔，按 tclx 里的 #备注 匹配，默认 huang,by
    const helpPrio = String(process.env.tclx_help_priority || 'huang,by')
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean);
    const prioRank = (s) => {
        const i = helpPrio.indexOf(String((s.acc.account && s.acc.account.remark) || '').trim());
        return i === -1 ? helpPrio.length : i;
    };
    const hostsByPriority = [...state].sort((a, b) => prioRank(a) - prioRank(b));
    $.log(`  互助顺序（钞级省奖品格优先）：${hostsByPriority.map((s) => tagOf(s.acc)).join(' → ')}`);

    // ① 花神签优先：只缺花神签、且「邀好友必得花神签」未满的号，先拿助力次数把它补齐。
    //    助力额度每天共享，投给钞级省就用不上了，所以这一步必须排在 fission 助力前面。
    if (FLOWER_HELP_FIRST) {
        const godNeed = state.filter(
            (s) =>
                s.key &&
                s.helpTarget > s.helpDone &&
                s.missing.length > 0 &&
                s.missing.every((t) => t === FLOWER_LAST_TYPE)
        );
        for (const host of godNeed) {
            let need = host.helpTarget - host.helpDone;
            $.log(
                `  花神签优先：${tagOf(host.acc)} 集卡 ${host.kinds}/${FG_KINDS_TOTAL}（只缺花神签），` +
                    `邀好友 ${host.helpDone}/${host.helpTarget}，先用助力补 ${need} 次`
            );
            let streak = 0;
            for (const helper of state) {
                if (need <= 0 || streak >= 3) break;
                if (helper === host) continue;
                const r = await wxApi(helper.acc.sess, `${FLOWER_BASE}/helperAssist`, {
                    sponsorEncryptUserKey: host.key,
                });
                if (Number(r.code) === 0) {
                    need -= 1;
                    streak = 0;
                    host.assisted = (host.assisted || 0) + 1;
                    $.log(
                        `  互助：${tagOf(helper.acc)} 助力 ${tagOf(host.acc)} 的「邀好友必得花神签」成功` +
                            `（${host.helpTarget - need}/${host.helpTarget}）`
                    );
                } else {
                    streak += 1;
                    $.log(`  互助：${tagOf(helper.acc)} 助力 ${tagOf(host.acc)} 的花神签失败：${resMsg(r)}`);
                }
                await $.wait(600, 1400);
            }
        }
    }

    // 助力解锁：钞级省 + 闲置券回收走同一套 fission 接口（每格 helpCount/maxHelpCount + 自己的 shareId），
    // 满 maxHelpCount 后由本人调 lottery/rec 领现金（实测 helpStatus 2=解锁成功，7=今日已帮过该用户）
    // 闲置券回收可能临时下线（回 code 3000），拉不到 blockList 就静默跳过
    for (const host of hostsByPriority) {
        for (const helper of state) {
            if (host === helper) continue;
            for (const sch of FISSION_SCHS) {
                let blocks = [];
                try {
                    const list = await wxApi(host.acc.sess, '/qiushiinnerapi/fission/lottery/list', { schGuid: sch });
                    if (Number(list.code) !== 0) continue;
                    blocks = ((list.data || {}).blockList || []).filter((b) => {
                        const d = b.lotteryDto || {};
                        return (
                            Number(b.isOccupy) === 1 &&
                            d.currentShareId &&
                            Number(d.helpCount) < Number(d.maxHelpCount)
                        );
                    });
                } catch (e) {
                    $.log(`  互助：${tagOf(host.acc)} 查奖品格失败 ${e.message || e}`);
                    continue;
                }
                for (const b of blocks) {
                    const d = b.lotteryDto || {};
                    const prize = d.resSubtitle || d.resTitle || '奖品';
                    const r = await wxApi(helper.acc.sess, '/qiushiinnerapi/fission/lottery/help', {
                        schGuid: sch,
                        shareGuid: d.currentShareId,
                    });
                    const hs = Number((r.data || {}).helpStatus);
                    if (Number(r.code) === 0 && hs === 1) {
                        host.helped += 1;
                        $.log(
                            `  互助：${tagOf(helper.acc)} 给 ${tagOf(host.acc)} 的「${prize}」助力` +
                                `（${d.helpCount}/${d.maxHelpCount} → helpStatus ${hs}）`
                        );
                    } else if (Number(r.code) === 0) {
                        $.log(
                            `  互助：${tagOf(helper.acc)} 给 ${tagOf(host.acc)} 的「${prize}」未计入` +
                                `（helpStatus ${hs}，不是新增助力）`
                        );
                    }
                    await $.wait(600, 1400);
                }
            }
        }

        // 助力满额就把自己的奖品领掉
        for (const sch of FISSION_SCHS) {
            try {
                const list2 = await wxApi(host.acc.sess, '/qiushiinnerapi/fission/lottery/list', { schGuid: sch });
                if (Number(list2.code) !== 0) continue;
                for (const b of ((list2.data || {}).blockList || [])) {
                    const d = b.lotteryDto || {};
                    if (Number(b.isOccupy) !== 1 || !d.currentShareId) continue;
                    if (Number(d.helpCount) < Number(d.maxHelpCount)) continue;
                    const prize = d.resSubtitle || d.resTitle || '奖品';
                    const r = await wxApi(host.acc.sess, '/qiushiinnerapi/fission/lottery/rec', {
                        schGuid: sch,
                        shareGuid: d.currentShareId,
                    });
                    if (Number(r.code) === 0) {
                        host.claimed = (host.claimed || 0) + 1;
                        $.log(`  互助：${tagOf(host.acc)} 领取「${prize}」成功`);
                    } else {
                        $.log(`  互助：${tagOf(host.acc)} 领取「${prize}」失败：${resMsg(r)}`);
                    }
                    await $.wait(600, 1400);
                }
            } catch (e) {
                $.log(`  互助：${tagOf(host.acc)} 领奖失败 ${e.message || e}`);
            }
        }
    }


    for (const host of state) {
        for (const helper of state) {
            if (host === helper) continue;

            if (host.shareId) {
                const r = await wxApi(helper.acc.sess, '/qiushiinnerapi/fission/lottery/help', {
                    schGuid: LOTTERY_SCH,
                    shareGuid: host.shareId,
                });
                const hs2 = Number((r.data || {}).helpStatus);
                if (Number(r.code) === 0 && (hs2 === 1 || hs2 === 0)) {
                    host.helped += 1;
                    $.log(`  互助：${tagOf(helper.acc)} 帮 ${tagOf(host.acc)} 抽奖助力成功`);
                } else if (Number(r.code) === 0) {
                    $.log(`  互助：${tagOf(helper.acc)} 帮 ${tagOf(host.acc)} 助力未计入（helpStatus ${hs2}）`);
                } else {
                    $.log(`  互助：${tagOf(helper.acc)} 帮 ${tagOf(host.acc)} 助力失败：${resMsg(r)}`);
                }
                await $.wait(600, 1400);
            } else {
                $.log(`  互助：${tagOf(host.acc)} 没有可助力的分享（share 为空），跳过`);
            }

            if (host.signShare && !host.signHelped) {
                const before = Number(host.signMileage) || 0;
                const r = await wxApi(helper.acc.sess, '/qiushiinnerapi/fission/sign/help', { shareGuid: host.signShare });
                if (Number(r.code) === 0) {
                    host.signHelped = 1;
                    // 邀好友限时翻倍签到（规则见 wxmpsign/home/top）：A 每天只有 1 次分享、只拿 1 次奖励，
                    // 实测一次 +20 里程；B 对同一个好友每天只能帮 1 次。第一个号帮成功后就不让其它号白帮，
                    // 真实到账用 sign/detail 的 todaySignMileageCount 回查，别再写死里程数。
                    let got = '';
                    try {
                        const sd2 = await wxApi(host.acc.sess, '/qiushiinnerapi/fission/sign/detail', { shareGuid: host.signShare });
                        const now = Number((sd2.data || {}).todaySignMileageCount);
                        if (Number.isFinite(now)) {
                            host.signMileage = now;
                            got = now > before
                                ? `，到账 +${now - before}（今日分享累计 ${now} 里程）`
                                : `，未新增（今日分享累计 ${now}，今日奖励已领过）`;
                        }
                    } catch (_) {
                        /* 回查失败不影响主流程 */
                    }
                    $.log(`  互助：${tagOf(helper.acc)} 帮 ${tagOf(host.acc)} 完成「好友签到」助力${got}`);
                } else {
                    $.log(`  互助：${tagOf(helper.acc)} 帮 ${tagOf(host.acc)} 签到助力未成功：${resMsg(r)}`);
                }
                await $.wait(600, 1400);
            } else if (host.signShare && host.signHelped && !host.signSkipLogged) {
                host.signSkipLogged = 1;
                $.log(`  互助：${tagOf(host.acc)} 的「好友签到」助力已完成，其余号跳过（每天仅 1 次奖励）`);
            }

            if (host.key && helper.key) {
                if (FLOWER_SKIP_LAST && !host.worthGod) {
                    // 只差花神签：投助力次数只会摇出重复卡，留给别的号
                    if (!host.godSkipLogged) {
                        host.godSkipLogged = true;
                        $.log(
                            `  互助：${tagOf(host.acc)} 花神已集 ${host.kinds}/${FG_KINDS_TOTAL} 种（只差花神签），` +
                                `跳过助力，次数留给还能出卡的号`
                        );
                    }
                } else {
                    const r = await wxApi(helper.acc.sess, `${FLOWER_BASE}/helperAssist`, {
                        sponsorEncryptUserKey: host.key,
                    });
                    if (Number(r.code) === 0) {
                        host.assisted = (host.assisted || 0) + 1;
                        $.log(`  互助：${tagOf(helper.acc)} 助力 ${tagOf(host.acc)} 的「邀好友必得花神签」`);
                    } else {
                        $.log(`  互助：${tagOf(helper.acc)} 助力 ${tagOf(host.acc)} 的花神签失败：${resMsg(r)}`);
                    }
                    await $.wait(600, 1400);
                }
            }

            // 赠卡：每天每号送 1 张就够完成「每日赠花签」，别跟集齐死磕（见 pickGiftCard 注释的账）
            const gift = pickGiftCard(host, helper);
            if (gift && host.key && helper.key && host.giveLeft > 0 && host.given < 1 && !sentGiftToday(host.acc.account.ref)) {
                const card = gift;
                // 先翻卡拿里程，再送：cardSource 5 是收到的赠卡（不能翻，只算集齐种类）
                if (Number(card.state) === 6 && Number(card.cardSource) !== 5) {
                    const fl = await wxApi(host.acc.sess, `${FLOWER_BASE}/flipCard`, { cardId: card.cardId });
                    if (Number(fl.code) === 0) {
                        const rw = (fl.data || {}).rewardName || '奖励';
                        $.log(`  互助：${tagOf(host.acc)} 先翻卡「${card.cardName}」→ ${rw}，再送`);
                    } else {
                        $.log(`  互助：${tagOf(host.acc)} 翻卡「${card.cardName}」失败：${resMsg(fl)}`);
                    }
                    await $.wait(600, 1400);
                }
                const r = await wxApi(host.acc.sess, `${FLOWER_BASE}/grantCard`, {
                    sponsorEncryptUserKey: helper.key,
                    cardId: card.cardId,
                });
                if (Number(r.code) === 0) {
                    const sameKind = host.cards.filter(
                        (c) => Number(c.cardType) === Number(card.cardType) && Number(c.cardSource) !== 5
                    ).length;
                    host.given += 1;
                    host.giveLeft -= 1;
                    host.cards = host.cards.filter((c) => c.cardId !== card.cardId);
                    helper.cards.push({ cardId: r.data, cardType: card.cardType, cardName: card.cardName });
                    $.log(`  互助：${tagOf(host.acc)} 送「${card.cardName}」给 ${tagOf(helper.acc)}（赠卡任务 +1${sameKind > 1 ? '，重复卡' : '，唯一卡→自己少 1 种'}）`);
                    markGiftSent(host.acc.account.ref);
                    // 规则①：好友成功领取后，赠卡方可额外获得 1 次抽签机会 —— 立刻用掉
                    await flowerRedraw(host.acc);
                } else {
                    $.log(`  互助：${tagOf(host.acc)} 送卡给 ${tagOf(helper.acc)} 失败：${resMsg(r)}`);
                    // 换期可能换花神签编号：转赠被拒就把它记下来，本次运行不再试
                    if (/花神|转赠|不可|不允许/.test(resMsg(r))) {
                        FG_GOD_TYPES.add(Number(card.cardType));
                        $.log(`  互助：${card.cardType} 号签不可转赠（记下，本次运行不再送）`);
                    }
                }
                await $.wait(600, 1400);
            } else if (host.given >= 1 || sentGiftToday(host.acc.account.ref)) {
                // 今天已经送过一张，赠卡任务当天只算一次，别把卡白白送光
            } else if (host.cards.length && host.giveLeft > 0) {
                const sendable = host.cards.filter((c) => Number(c.cardSource) !== 5 && !FG_GOD_TYPES.has(Number(c.cardType))).length;
                $.log(
                    `  互助：${tagOf(host.acc)} 没有可送出的卡（可转赠 ${sendable} 张，` +
                        `其余 ${host.cards.length - sendable} 张是别人送的、不可二次转赠），今日赠卡任务跳过`
                );
            }
        }
    }

    // 花神：流程中途查集齐时往往还没拿到赠卡/花神卡，互助结束后再查一次，满 6 种直接兑现金
    for (const s of FLOWER_ENABLED ? state : []) {
        try {
            const cl = await wxApi(s.acc.sess, `${FLOWER_BASE}/cardList`, null, 'GET');
            if (Number(cl.code) !== 0) continue;
            const types = new Set((Array.isArray(cl.data) ? cl.data : []).map((c) => Number(c.cardType)));
            if (types.size < FG_KINDS_TOTAL) {
                if (types.size > (s.kinds || 0)) {
                    $.log(
                        `  互助：${tagOf(s.acc)} 花神已集 ${types.size}/${FG_KINDS_TOTAL} 种，还差 ${FG_KINDS_TOTAL - types.size} 种`
                    );
                }
                continue;
            }
            const r = await wxApi(s.acc.sess, `${FLOWER_BASE}/exchangeCash`, {});
            $.log(
                `  互助：${tagOf(s.acc)} 花神集齐 ${types.size}/${FG_KINDS_TOTAL} 种 → 兑换${Number(r.code) === 0 ? '成功' : `失败：${resMsg(r)}`}`
            );
            await $.wait(800, 1600);
        } catch (e) {
            $.log(`  互助：${tagOf(s.acc)} 花神集齐检查异常：${e.message || e}`);
        }
    }

    for (const s of state) {
        const kinds = new Set((s.cards || []).map((c) => Number(c.cardType))).size;
        s.acc.log(
            `互助：被助力 ${s.helped} 次，送出 ${s.given} 张卡，领到 ${s.claimed || 0} 个钞级省奖品${FLOWER_ENABLED ? `，花神集齐 ${kinds}/6 种` : ''}`
        );
    }
}

/**
 * 同程钞级省抽奖：lottery/list 给出 lotteryCount（当日剩余次）和 blockList（isOccupy 0=空格），
 * 每次 lottery/lottery {schGuid, blockIndex} 抽一格，实测出「0.5元现金」这类奖品，次数 -1
 */
async function lotteryDraw(sess, dryRun) {
    const list = await wxApi(sess, '/qiushiinnerapi/fission/lottery/list', { schGuid: LOTTERY_SCH });
    if (Number(list.code) !== 0) return { prizes: [], msg: `钞级省查询失败: ${resMsg(list)}` };
    const d = list.data || {};
    let count = Number(d.lotteryCount) || 0;
    const free = (d.blockList || [])
        .filter((b) => Number(b.isOccupy) === 0)
        .map((b) => Number(b.index));
    const prizes = [];

    if (dryRun) {
        return { prizes, msg: `钞级省：可抽 ${count} 次，空闲格子 ${free.length} 个（演练模式没抽）` };
    }

    let i = 0;
    while (count > 0 && i < free.length) {
        const idx = free[i++];
        const r = await wxApi(sess, '/qiushiinnerapi/fission/lottery/lottery', {
            schGuid: LOTTERY_SCH,
            blockIndex: idx,
        });
        if (Number(r.code) !== 0) {
            $.log(`  钞级省抽奖失败（格 ${idx}）: ${resMsg(r)}`);
            break;
        }
        const dd = r.data || {};
        const prize = dd.resSubtitle || dd.resTitle || '奖励';
        prizes.push(prize);
        count -= 1;
        $.log(`  钞级省抽奖：格 ${idx} → ${prize}`);
        await $.wait(800, 1600);
    }

    return {
        prizes,
        msg: `钞级省：抽 ${prizes.length} 次${prizes.length ? `（${prizes.join('、')}）` : ''}，剩 ${count} 次`,
    };
}

/**
 * 周周打卡领现金（H5 活动 signInCash，萌力值体系）
 *   POST {WEEK_API}/getIndexInfo {actId, unionId, idenId(公众号 openid)} -> pointsBalance / signedDays / qualified
 *   POST /signIn {}                       -> 每日打卡（5 天达标；窗口关闭回 1009 当前时间不可签到）
 *   POST /getTaskInfo {}                  -> taskList（completionMode=BROWSE 可自动做，rewardPoints 是萌力值）
 *   POST /completeTask {taskType}         -> 返 taskRecordId
 *   POST /claimTaskReward {taskRecordId}  -> 领萌力值（实测 3 个浏览任务 0->15）
 *   POST /getExchangeInfo {} / exchangePrize {prizeId} -> 萌力值兑现金
 *   POST /getDrawInfo {}                  -> 达标后抽现金
 * idenId 必须是**公众号 openid**（用小程序 openid 回 2018 客户端信息不存在）
 */
async function weekApi(path, body) {
    const res = await axios.request({
        method: 'POST',
        url: `${WEEK_API}${path}`,
        data: body,
        headers: {
            'Content-Type': 'application/json',
            'User-Agent': UA,
            Referer: 'https://wx.17u.cn/cvgzt/20260819dailyCheckIn/index/',
        },
        timeout: 20000,
        validateStatus: () => true,
    });
    return res.data || {};
}

async function weekCheckIn(pubOpenid, unionId, dryRun) {
    const base = { actId: WEEK_ACT, unionId, idenId: pubOpenid };
    const idx = await weekApi('/getIndexInfo', base);
    if (Number(idx.code) !== 1000) {
        return { gain: 0, msg: `周周打卡：取不到用户（需要公众号 openid）${idx.message || idx.code || ''}` };
    }
    const d = idx.data || {};
    const parts = [`萌力值 ${d.pointsBalance ?? 0}`, `本周打卡 ${d.signedDays ?? 0}/${d.requiredSignedDays ?? 5}`];
    if (d.qualified) parts.push('已达标');
    let gain = 0;

    if (dryRun) {
        const tinfo = await weekApi('/getTaskInfo', base);
        const todo = ((tinfo.data || {}).taskList || []).filter((t) => !t.completed && t.couldComplete);
        parts.push(`待做任务 ${todo.length} 个（演练模式没做）`);
        return { gain, msg: `周周打卡：${parts.join('，')}` };
    }

    const sign = await weekApi('/signIn', base);
    if (Number(sign.code) === 1000) parts.push('今日打卡 +1');
    else if (sign.message && /已签|已打卡/.test(sign.message)) parts.push('今日已打卡');
    else parts.push(`打卡失败 ${sign.message || sign.code || ''}`);
    await $.wait(600, 1200);

    const tinfo = await weekApi('/getTaskInfo', base);
    for (const t of (tinfo.data || {}).taskList || []) {
        if (t.completed || !t.couldComplete || t.completionMode !== 'BROWSE') continue;
        const done = await weekApi('/completeTask', { ...base, taskType: t.type });
        if (Number(done.code) !== 1000 || !done.data) {
            $.log(`  周周打卡：任务「${t.title}」完成失败 ${done.message || done.code || ''}`);
            continue;
        }
        const claim = await weekApi('/claimTaskReward', { ...base, taskRecordId: done.data });
        if (Number(claim.code) === 1000) {
            const add = Number((claim.data || {}).rewardPoints) || Number(t.rewardPoints) || 0;
            gain += add;
            parts.push(`「${t.title}」+${add}萌力`);
        } else {
            $.log(`  周周打卡：任务「${t.title}」领奖失败 ${claim.message || claim.code || ''}`);
        }
        await $.wait(700, 1500);
    }

    const ex = await weekApi('/getExchangeInfo', base);
    for (const p of ((ex.data || {}).prizeList || [])) {
        if (!p.couldExchange) continue;
        const r = await weekApi('/exchangePrize', { ...base, prizeId: p.prizeId });
        if (Number(r.code) === 1000) parts.push(`兑换「${p.prizeName}」`);
        else $.log(`  周周打卡：兑换「${p.prizeName}」失败 ${r.message || r.code || ''}`);
        await $.wait(700, 1500);
    }

    const draw = await weekApi('/getDrawInfo', base);
    const dd = draw.data || {};
    if (dd.qualified && dd.status && String(dd.status).indexOf('DRAW') >= 0 && dd.status !== 'DRAWED') {
        const r = await weekApi('/drawPrize', base);
        if (Number(r.code) === 1000) parts.push(`达标抽奖：${(r.data || {}).amount ?? '已抽'}`);
        else parts.push(`达标但抽奖失败 ${r.message || r.code || ''}`);
    } else if (dd.status) {
        parts.push(`抽奖状态 ${dd.status}`);
    }

    return { gain, msg: `周周打卡：${parts.join('，')}` };
}

class Account {
    constructor(raw, index, pub = '') {
        this.index = index;
        this.account = parseAccount(raw);
        this.pub = String(pub || '').trim();
        this.sess = null;
    }

    log(msg) {
        const tag = this.account.remark ? `[${this.account.remark}]` : '';
        $.log(`账号[${this.index}]${tag} ${msg}`);
    }

    async ensureSession() {
        const cache = readCache();
        const cached = cache[this.account.ref];
        if (cached && cached.sectoken) {
            if (await checkSession(cached)) {
                this.log('token 缓存有效');
                return cached;
            }
            this.log('token 缓存失效，重新登录');
        }
        const code = await getWxCode(this.account.ref);
        const sess = await loginByCode(code);
        if (!(await checkSession(sess))) throw new Error('登录成功但 checkstatus 未通过');
        cache[this.account.ref] = { ...sess, updatedAt: new Date().toISOString() };
        writeCache(cache);
        this.log(`登录成功 openId=${sess.openId}`);
        return sess;
    }

    async run() {
        if (!this.account.ref) {
            this.log('跳过：变量里没有账号标识');
            return { ok: false };
        }
        try {
            this.sess = await this.ensureSession();
        } catch (e) {
            this.log(`登录失败: ${e.message || e}`);
            return { ok: false };
        }

        const before = await queryBalance(this.sess);
        this.log(`签到前里程=${before == null ? '未知' : before}${DRY_RUN ? '  [演练模式]' : ''}`);

        if (ONLY === 'checkin') {
            try {
                // 核对模式只读：dryRun=true 会跳过「替明天报名」，避免一条核对任务动到里程
                const ck = await checkinChallenge(this.sess, true, before);
                this.log(ck.msg);
            } catch (e) {
                this.log(`打卡挑战异常: ${e.message || e}`);
            }
            const settled = await queryBalance(this.sess);
            $.log(`账号[${this.index}] 里程 ${before == null ? '?' : before} -> ${settled == null ? '?' : settled}`);
            return { ok: true, only: 'checkin' };
        }

        let signMileage = 0;
        if (DRY_RUN) {
            const cal = await wxApi(this.sess, '/wxmpsign/sign/signCalendar', {
                beginDate: todayString(-2),
                endDate: todayString(2),
            });
            const today = (cal.data && cal.data.dateInfo || []).find((x) => x.date === todayString()) || {};
            this.log(`签到状态：${today.isSigned ? '今日已签' : '今日未签'}，今日里程=${today.mileage ?? '未知'}`);
        } else {
            const sign = await signIn(this.sess);
            this.log(`签到：${sign.msg}`);
            if (sign.ok && !sign.already) signMileage = Number(sign.mileage) || 0;
        }

        let flowerMileage = 0;
        const flowerRewards = [];
        try {
            const flower = FLOWER_ENABLED
                ? await flowerGod(this.sess, DRY_RUN)
                : { msg: '花神：已关闭（tclx_flower=false）', got: [] };
            this.log(flower.msg);
            flowerRewards.push(...flower.got);
            flowerMileage = flower.got.reduce((sum, x) => {
                const m = /(\d+)/.exec(x.reward || '');
                return sum + (m ? Number(m[1]) : 0);
            }, 0);

        } catch (e) {
            this.log(`花神异常: ${e.message || e}`);
        }

        try {
            const fx = FLOWER_ENABLED
                ? await flowerExtras(this.sess, DRY_RUN, this)
                : { msg: '花神补充：已关闭' };
            this.log(fx.msg);
        } catch (e) {
            this.log(`花神补充异常: ${e.message || e}`);
        }

        let dramaMileageGot = 0;
        try {
            const drama = await dramaMileage(this.sess, DRY_RUN);
            this.log(drama.msg);
            dramaMileageGot = (Number(drama.visitReward) || 0) + (Number(drama.watchReward) || 0);
        } catch (e) {
            this.log(`短剧异常: ${e.message || e}`);
        }

        let lotteryPrizes = [];
        try {
            const lot = await lotteryDraw(this.sess, DRY_RUN);
            this.log(lot.msg);
            lotteryPrizes = lot.prizes || [];
        } catch (e) {
            this.log(`钞级省异常: ${e.message || e}`);
        }

        if (this.pub) {
            try {
                const wk = await weekCheckIn(this.pub, this.sess.unionId, DRY_RUN);
                this.log(wk.msg);
            } catch (e) {
                this.log(`周周打卡异常: ${e.message || e}`);
            }
        }
        const schemes = parseSchemes(process.env.tclx_schemes);
        const allClaimed = [];
        let failed = 0;
        for (const scheme of schemes) {
            if (DRY_RUN) {
                const list = await wxApi(this.sess, '/qiushiinnerapi/task/detailList', {
                    detailGuid: '',
                    pageNum: 1,
                    pageSize: 999,
                    schemeGuid: scheme.guid,
                });
                const tasks = (list.data && list.data.taskDetails) || [];
                const todo = tasks.filter((t) => Number(t.status) !== 3);
                this.log(`任务[${scheme.name}] 共 ${tasks.length} 个，未完成 ${todo.length} 个：${todo.map((t) => t.title).join('、') || '无'}`);
                continue;
            }
            const result = await runScheme(this.sess, scheme);
            allClaimed.push(...result.claimed);
            failed += result.failed;
        }

        await reportExtraSources(this.sess, before);

        const after = await queryBalance(this.sess);
        const delta = before != null && after != null ? after - before : null;
        const claimedMileage = allClaimed.reduce((sum, x) => {
            const m = /(\d+)/.exec(x.reward || '');
            return sum + (m ? Number(m[1]) : 0);
        }, 0);

        $.log(`账号[${this.index}] 结果：签到 +${signMileage}，${FLOWER_ENABLED ? `花神 +${flowerMileage}，` : ''}短剧 +${dramaMileageGot}，任务领取 ${allClaimed.length} 个` +
            `${claimedMileage ? `（约 +${claimedMileage}）` : ''}` +
            `${failed ? `，失败 ${failed}` : ''}`);
        $.log(`账号[${this.index}] 里程 ${before == null ? '?' : before} -> ${after == null ? '?' : after}` +
            `${delta != null ? `（${delta >= 0 ? '+' : ''}${delta}）` : ''}`);
        if (allClaimed.length) {
            $.log(`账号[${this.index}] 领到：${allClaimed.map((x) => `${x.reward || '奖励'}·${x.title}`).join('；')}`);
        }
        if (flowerRewards.length) {
            $.log(`账号[${this.index}] 花神：${flowerRewards.map((x) => `${x.reward}·${x.name}`).join('；')}`);
        }
        if (lotteryPrizes.length) {
            $.log(`账号[${this.index}] 钞级省抽到：${lotteryPrizes.join('、')}`);
        }

        return { ok: true, signMileage, flowerMileage, claimed: allClaimed.length, delta };
    }
}

(async () => {
    const raw = (process.env[CK_NAME] || process.env.tclx_lc || process.env.wx_openid || '').trim();
    const accounts = splitAccounts(raw);
    $.log(`🔔 ${SCRIPT_NAME} 开始${DRY_RUN ? '  [演练模式]' : ''}`);
    $.log(`   yyb-go: ${YYB_URL}`);
    if (!accounts.length) {
        $.log(`未配置 ${CK_NAME}（yyb-go 账号标识，& 或换行分隔）`);
        return;
    }
    $.log(`   共 ${accounts.length} 个账号`);
    const pubs = String(process.env.tclx_pub || '').split('&').map((s) => s.trim());

    const runners = [];
    for (let i = 0; i < accounts.length; i++) {
        const runner = new Account(accounts[i], i + 1, pubs[i]);
        try {
            await runner.run();
        } catch (e) {
            runner.log(`执行异常: ${e.message || e}`);
        }
        runners.push(runner);
        if (i < accounts.length - 1) await $.wait(1500, 3000);
    }

    const helpEnabled = ONLY !== 'checkin' && String(process.env.tclx_help || '').trim().toLowerCase() !== 'false';
    const ready = runners.filter((r) => r.sess);
    if (helpEnabled && ready.length >= 2) {
        if (DRY_RUN) {
            $.log(`🤝 互助阶段：演练模式跳过（${ready.length} 个账号）`);
        } else {
            $.log(`🤝 互助阶段：${ready.length} 个账号互相助力 / 赠卡`);
            try {
                await mutualHelp(ready);
            } catch (e) {
                $.log(`互助异常：${e.message || e}`);
            }
        }
    }
    const okCount = runners.filter((r) => r.sess).length;
    if (!okCount) {
        $.log(`❌ ${runners.length} 个账号全部失败（登录或会话异常），本次没有任何账号跑通`);
        process.exitCode = 1;
    } else if (okCount < runners.length) {
        $.log(`⚠️ ${runners.length - okCount} 个账号失败，${okCount} 个跑通`);
    }
    $.log(`🔔 ${SCRIPT_NAME} 结束`);
})().catch((e) => {
    $.log(`❌ 脚本异常：${e && e.stack ? e.stack : e}`);
    process.exit(1);
});
