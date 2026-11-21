// jd_ck.js - QX 抓京东 CK，点通知复制到剪贴板
// 配合 iOS 快捷指令「复制京东CK」使用
// 抓包规则（QX 重写）：
// ^https://(api\.m\.jd\.com|me-api\.jd\.com)/ url script-request-header <本文件 URL>

const cookie = $request.headers['Cookie'] || $request.headers['cookie'] || '';
const ptKey = (cookie.match(/pt_key=([^;]+)/) || [])[1] || '';
const ptPin = (cookie.match(/pt_pin=([^;]+)/) || [])[1] || '';

if (ptKey && ptPin) {
  const ck = 'pt_key=' + ptKey + ';pt_pin=' + ptPin + ';';
  const last = $prefs.valueForKey('jd_ck_last') || '';
  // 只有 CK 变了才通知，避免每次请求都弹
  if (ck !== last) {
    $prefs.setValueForKey(ck, 'jd_ck_last');
    const url = 'shortcuts://run-shortcut?name=' + encodeURIComponent('复制京东CK') + '&input=' + encodeURIComponent(ck);
    $notify('京东 CK 已抓到', '点一下复制到剪贴板', ck, { 'open-url': url });
  }
}

$done({});
