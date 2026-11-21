// jd_ck.js - QX 抓京东 CK，点通知复制到剪贴板
// 配合 iOS 快捷指令「复制京东CK」使用
// 抓包规则（QX 重写），两条都要加：
// ^https://(api\.m\.jd\.com|me-api\.jd\.com)/ url script-request-header <本文件 URL>
// ^https://(api\.m\.jd\.com|me-api\.jd\.com)/ url script-response-header <本文件 URL>
//
// 原理：App 发请求时带的 Cookie 可能是旧的（已过期）；
// 服务器会在响应里用 Set-Cookie 发新的 pt_key/pt_pin，App 收到后才更新，
// 所以 App 还能登录，但只抓请求头就只能抓到旧 CK。
// 这版同时抓请求头和响应头，优先取响应 Set-Cookie 里的新 CK。

function pick(str) {
  if (!str) return null;
  const k = (str.match(/pt_key=([^;]+)/) || [])[1] || '';
  const p = (str.match(/pt_pin=([^;]+)/) || [])[1] || '';
  if (k && p) return 'pt_key=' + k + ';pt_pin=' + p + ';';
  return null;
}

let ck = '';
// 1. 优先从响应 Set-Cookie 取新 CK
try {
  if (typeof $response !== 'undefined' && $response && $response.headers) {
    const h = $response.headers;
    let sc = h['Set-Cookie'] || h['set-cookie'] || '';
    if (Array.isArray(sc)) sc = sc.join('; ');
    ck = pick(sc) || '';
  }
} catch (e) {}
// 2. 没有新 CK 时，从请求 Cookie 取当前 CK
if (!ck) {
  try {
    if (typeof $request !== 'undefined' && $request && $request.headers) {
      const c = $request.headers['Cookie'] || $request.headers['cookie'] || '';
      ck = pick(c) || '';
    }
  } catch (e) {}
}

if (ck) {
  const now = Date.now();
  const lastTime = parseInt($prefs.valueForKey('jd_ck_last_notify') || '0', 10);
  const lastCk = $prefs.valueForKey('jd_ck_last_value') || '';
  // CK 变了立即通知（不被 30 秒节流挡住）；CK 没变则 30 秒内只通知一次。
  if (ck !== lastCk || now - lastTime > 30000) {
    $prefs.setValueForKey(String(now), 'jd_ck_last_notify');
    $prefs.setValueForKey(ck, 'jd_ck_last_value');
    const url = 'shortcuts://run-shortcut?name=' + encodeURIComponent('复制京东CK') + '&input=' + encodeURIComponent(ck);
    $notify('京东 CK 已抓到', '点一下复制到剪贴板', ck, { 'open-url': url });
  }
}

$done({});
