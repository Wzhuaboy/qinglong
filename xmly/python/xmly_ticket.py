#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地签发喜马拉雅 XUID ticket —— 彻底不需要真机 / 不需要抓包

原理（全程静态确认 + 实测打通）
------------------------------------------------------------------
App 里 ticket 的生成链路：

    XuidManager.getTicket(attr)
      → com.ximalaya.xuid.d.a(attr)
        → OooO00o.OooO00o.OooO00o.b.b(attr)
          → NativeLib.vDMzsjQFqU(new String[]{attr, xuid})        （libnativelib.so）
            → getTicket(attr, attrlen, xuid, xuidlen, &out, &outlen)         @0x19984
              → xuidcc_parse_xuid(xuid, xuidlen, parsed)                     @0x1f8fc
              → xuidcc_get_ticket(os, end, attr, attrlen, parsed+0x12, ctx)  @0x210ec

关键事实：
  · attr 由 App 自己拼：`b=incentives&s=gold_reward&u=<uid>` —— uid 是调用方给的，
    不是服务端下发的，所以**可以为任意 uid 现签**
  · xuid 就是设备号（deviceId，36 字符 UUID），服务端不校验它的具体值
  · os 只能是 'A'(Android) 或 'I'(iOS)（check_os: (os|8)&0xff == 0x49）
  · 输出 ticket 结构（实测与真 ticket 逐字节对齐）：
        'T' + os + end + base64( data )
        data = BE时间戳(4) + 设备uuid(16) + 随机uuid(16) + 签名(32) + <pkg>!<sv>!<av>!<attr>
    其中 sv=1.3.27（xuid SDK 版本）、av=9.5.13.3（App 版本）

实测：为 uid=608274781（从未抓过 ticket 的新账号）本地签发后连领 4 次全部成功，
余额 188 → 816。

用法：
    python3 python/xmly_ticket.py --uid 608274781            # 打印一条 ticket
    python3 python/xmly_ticket.py --uid 608274781 --save     # 同时落到该账号目录
    from xmly_ticket import mint; mint("608274781")
"""

import argparse
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 默认设备号（服务端不校验；与 cookie 里的 1&_device 保持一致最好）
DEFAULT_DEVICE = "a18bde8f-3964-347a-afc5-9b29fe592465"
# xuid SDK 版本 / App 版本 —— 必须和 libnativelib.so 期望的一致
SDK_VERSION = "1.3.27"
APP_VERSION = "9.5.13.3"
PKG_NAME = "com.ximalaya.ting.android"
OS_CHAR = ord("A")          # 'A'=Android, 'I'=iOS
END_CHAR = ord("C")

_EMU = None


def _emu():
    """加载并初始化模拟器（只做一次）"""
    global _EMU
    if _EMU is not None:
        return _EMU
    try:
        from xmly_native import Emu
    except ImportError:
        sys.path.insert(0, HERE)
        from xmly_native import Emu
    e = Emu()
    e.boot()
    conf = e.alloc(0x40)
    e.write(conf, bytes([OS_CHAR]))
    for off, s in ((0x08, PKG_NAME), (0x18, SDK_VERSION), (0x28, APP_VERSION)):
        p = e.cstr(s)
        e.write(conf + off, struct.pack("<Q", p))
        e.write(conf + off + 8, struct.pack("<I", len(s)))
    rc, err = e.call("init_xuidcc", [conf, 0])
    if rc != 0:
        raise RuntimeError("init_xuidcc 失败: ret=%s err=%s" % (rc, err))
    # init_xuidcc 之后 check_xuidcc_conf 会把 os 归一化，这里强制设回我们要的
    g = e.sym_addr("g_xuidcc_conf")
    e.write(g, bytes([OS_CHAR]))
    e.write(g + 1, bytes([END_CHAR]))
    _EMU = e
    return e


def mint(uid, device=DEFAULT_DEVICE, scope=("incentives", "gold_reward")):
    """为任意 uid 本地签发一条 XUID ticket"""
    attr = "b=%s&s=%s&u=%s" % (scope[0], scope[1], uid)
    e = _emu()
    ap = e.cstr(attr)
    xp = e.cstr(device)
    out = e.alloc(8)
    olen = e.alloc(8)
    rc, err = e.call("getTicket", [ap, len(attr), xp, len(device), out, olen])
    if rc != 0:
        raise RuntimeError("getTicket 失败: ret=%s err=%s" % (rc, err))
    p = struct.unpack("<Q", e.read(out, 8))[0]
    n = struct.unpack("<I", e.read(olen, 4))[0]
    if not p or n < 32:
        raise RuntimeError("getTicket 未产出 ticket (ptr=%#x len=%s)" % (p, n))
    tk = e.read_cstr(p).decode("utf-8", "replace")
    if not tk.startswith("T"):
        raise RuntimeError("ticket 形态异常: %r" % tk[:40])
    return tk


def main():
    ap = argparse.ArgumentParser(description="本地签发 XUID ticket（不需要真机）")
    ap.add_argument("--uid", required=True)
    ap.add_argument("--device", default=DEFAULT_DEVICE)
    ap.add_argument("--scope", default="incentives:gold_reward",
                    help="biz:scene，默认 incentives:gold_reward")
    ap.add_argument("--save", action="store_true", help="写入 work/accounts/<uid>/ticket.txt")
    ap.add_argument("--with-token", action="store_true", help="顺便用该 ticket 领一次水验证")
    a = ap.parse_args()

    biz, _, scene = a.scope.partition(":")
    tk = mint(a.uid, device=a.device, scope=(biz, scene or "gold_reward"))
    print("uid    =", a.uid)
    print("长度   =", len(tk))
    print("ticket =", tk)

    if a.save:
        try:
            import accounts as ACC
            p = ACC.ticket_path(a.uid)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(tk)
            print("已写入 =", p)
        except Exception as ex:
            print("落盘失败:", ex, file=sys.stderr)

    if a.with_token:
        try:
            import xmly_water as W
            W.CUR_UID = str(a.uid)
            print("余额   =", W.balance())
            d = W.drink(ticket=tk)
            print("试领   =", d)
        except Exception as ex:
            print("验证失败:", ex, file=sys.stderr)


if __name__ == "__main__":
    main()
