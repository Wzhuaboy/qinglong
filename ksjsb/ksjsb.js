// 快手极速版签到（青龙 Node 脚本）
// 接口来源：1nbeat/kuaishou-check-in（2026-03，Java 版，已读源码核实）
// 签到就是一个 GET 请求，只带 Cookie kuaishou.api_st
// 环境变量：KUAISHOU_API_ST（kuaishou.api_st 的值，多账号用换行或 & 分隔）
// 青龙定时在面板新建，不要改脚本加 cron 行

const https = require('https');

const API_URL = 'https://nebula.kuaishou.com/rest/wd/encourage/unionTask/signIn/report';

function getTokens() {
  const raw = process.env.KUAISHOU_API_ST || '';
  return raw.split(/[\n&]+/).map((s) => s.trim()).filter(Boolean);
}

function checkIn(token) {
  return new Promise((resolve) => {
    const req = https.get(API_URL, { headers: { Cookie: 'kuaishou.api_st=' + token } }, (res) => {
      let body = '';
      res.on('data', (c) => (body += c));
      res.on('end', () => resolve({ status: res.statusCode, body }));
    });
    req.on('error', (e) => resolve({ status: 0, body: '请求失败：' + e.message }));
    req.setTimeout(30000, () => {
      req.destroy();
      resolve({ status: 0, body: '请求超时' });
    });
  });
}

(async () => {
  const tokens = getTokens();
  if (!tokens.length) {
    console.log('未配置 KUAISHOU_API_ST，跳过');
    return;
  }
  for (let i = 0; i < tokens.length; i++) {
    const r = await checkIn(tokens[i]);
    console.log(`账号 ${i + 1} 签到完成，状态码：${r.status}，响应：${r.body}`);
  }
  console.log('快手极速版签到任务执行完成');
})();
