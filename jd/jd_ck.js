// jd_ck.js - QX 抓京东 CK，点通知复制到剪贴板
// 配合 iOS 快捷指令「复制京东CK」使用
// 抓包规则（QX 重写）：
// ^https://(api\.m\.jd\.com|me-api\.jd\.com)/ url script-request-header <本文件 URL>

const cookie = $request.headers['Cookie'] || $request.headers['cookie'] || '';
const ptKey = (cookie.match(/pt_key=([^;]+)/) || [])[1] || '';
const ptPin = (cookie.match(/pt_pin=([^;]+)/) || [])[1] || '';

if (ptKey && ptPin) {
  const ck = 'pt_key=' + ptKey + ';pt_pin=' + ptPin + ';';
  const now = Date.now();
  const last = parseInt($prefs.valueForKey('jd_ck_last_notify') || '0', 10);
  // 30 秒内只通知一次，避免同一次打开京东连弹多条；
  // 超过 30 秒再打开京东就会再通知（CK 没变也会弹，方便重新复制）。
  if (now - last > 30000) {
    $prefs.setValueForKey(String(now), 'jd_ck_last_notify');
    const url = 'shortcuts://run-shortcut?name=' + encodeURIComponent('复制京东CK') + '&input=' + encodeURIComponent(ck);
    $notify('京东 CK 已抓到', '点一下复制到剪贴板', ck, { 'open-url': url });
  }
}

$done({});
