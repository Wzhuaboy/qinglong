#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
libnativelib.so 的 Unicorn 模拟器 —— 本地签发 XUID ticket

原理（已静态确认）：
    Java_..._vDMzsjQFqU(attr, xuid)
      → getTicket(attr, attrlen, xuid, xuidlen, &out, &outlen)      @0x19984
          → xuidcc_parse_xuid(xuid, xuidlen, parsed)                @0x1f8fc
          → xuidcc_get_ticket(os, end, attr, attrlen, parsed+0x12, out) @0x210ec

    配置（g_xuidcc_conf @0x6e2c0, 336B）由 init_xuidcc(conf, extra) @0x193b4 写入：
        conf+0x00 u8    os 字符
        conf+0x08 char* str1 / +0x10 u32 len1
        conf+0x18 char* str2 / +0x20 u32 len2
        conf+0x28 char* str3 / +0x30 u32 len3
    三个字符串写进内部时会把 '!' 换成 '_'（strings_replace @PLT 0x16dd0）。

    ticket 结构（用真 ticket 解出来验证过）：
        base64 后 = 67 字节二进制头 + `!` 分隔的明文
        头部 +0x04..0x13 = deviceId 的 16 字节（uuid）
        明文 = <os> + pkg + '!' + sv + '!' + av + '!' + attr
"""

import os
import struct
import sys

from elftools.elf.elffile import ELFFile
from unicorn import *
from unicorn.arm64_const import *

BASE = 0x10000000
STACK = 0x30000000
STACK_SIZE = 0x40000
TRAMP = 0x40000000          # 桩函数蹦床页
HEAP = 0x50000000
HEAP_SIZE = 0x4000000
RET_MAGIC = 0x70000000      # 假的返回地址，用来判定函数返回

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SO = os.path.join(ROOT, "work", "so", "libnativelib.so")


def _ensure_so():
    """仓库里只存 .b64 文本；.so 缺失或内容不对时自己解码出来，省去手动还原步骤。"""
    b64_path = SO + ".b64"
    if not os.path.exists(b64_path):
        return
    import base64
    with open(b64_path, "rb") as f:
        data = base64.b64decode(f.read())
    if os.path.exists(SO):
        with open(SO, "rb") as f:
            if f.read() == data:
                return
    with open(SO, "wb") as f:
        f.write(data)


_ensure_so()


class Emu:
    def __init__(self, path=SO, verbose=False):
        self.path = path
        self.f = open(path, "rb")
        self.e = ELFFile(self.f)
        self.raw = open(path, "rb").read()
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.verbose = verbose
        self.hooks = {}          # name -> trampoline addr
        self.by_addr = {}        # trampoline addr -> name
        self.misses = {}
        self._calls = 0

    # ------------------------------------------------------------ 内存
    def _readva(self, va, n):
        for sg in self.e.iter_segments():
            if sg["p_type"] != "PT_LOAD":
                continue
            if sg["p_vaddr"] <= va < sg["p_vaddr"] + sg["p_filesz"]:
                off = sg["p_offset"] + (va - sg["p_vaddr"])
                return self.raw[off:off + n]
        return None

    def map(self):
        for p in self.e.iter_segments():
            if p["p_type"] != "PT_LOAD":
                continue
            va, vs, fs = p["p_vaddr"], p["p_memsz"], p["p_filesz"]
            start = (BASE + va) & ~0xfff
            end = (BASE + va + max(vs, fs) + 0xfff) & ~0xfff
            self.uc.mem_map(start, end - start, UC_PROT_ALL)
        for p in self.e.iter_segments():
            if p["p_type"] != "PT_LOAD" or p["p_filesz"] == 0:
                continue
            self.uc.mem_write(BASE + p["p_vaddr"],
                              self.raw[p["p_offset"]:p["p_offset"] + p["p_filesz"]])
        self.uc.mem_map(TRAMP, 0x1000, UC_PROT_ALL)
        self.uc.mem_map(HEAP, HEAP_SIZE, UC_PROT_ALL)
        self.uc.mem_map(STACK - STACK_SIZE, STACK_SIZE, UC_PROT_ALL)
        self.uc.mem_map(RET_MAGIC, 0x1000, UC_PROT_ALL)
        self.heap_ptr = HEAP + 0x1000
        self.uc.reg_write(UC_ARM64_REG_SP, STACK - STACK_SIZE // 2)

    # ------------------------------------------------------------ 符号
    def dynsym(self):
        return self.e.get_section_by_name(".dynsym")

    def sym_addr(self, name):
        """本地定义（st_shndx != 0）的符号 → 真实地址"""
        d = self.dynsym()
        for s in d.iter_symbols():
            if s.name == name and s["st_shndx"] != 0 and s["st_value"]:
                return BASE + s["st_value"]
        for secname in (".symtab",):
            sec = self.e.get_section_by_name(secname)
            if not sec:
                continue
            for s in sec.iter_symbols():
                if s.name == name and s["st_shndx"] != "SHN_UNDEF" and s["st_value"]:
                    return BASE + s["st_value"]
        return None

    # ------------------------------------------------------------ 桩
    def stub(self, name):
        if name in self.hooks:
            return self.hooks[name]
        a = TRAMP + len(self.hooks) * 4
        self.hooks[name] = a
        self.by_addr[a] = name
        # ret
        self.uc.mem_write(a, bytes([0xC0, 0x03, 0x5F, 0xD6]))
        return a

    def reloc(self):
        d = self.dynsym()
        for secname in (".rela.dyn", ".rela.plt"):
            sec = self.e.get_section_by_name(secname)
            if not sec:
                continue
            for r in sec.iter_relocations():
                off = BASE + r["r_offset"]
                typ = r["r_info"] & 0xFFFFFFFF
                symidx = r["r_info"] >> 32
                add = r["r_addend"] if r.is_RELA() else 0
                if typ == 1027:                       # R_AARCH64_RELATIVE
                    self.uc.mem_write(off, struct.pack("<Q", BASE + add))
                    continue
                sym = d.get_symbol(symidx) if symidx < d.num_symbols() else None
                name = sym.name if sym else None
                local = (sym is not None and sym["st_shndx"] != 0 and sym["st_value"])
                if local:
                    addr = BASE + sym["st_value"] + add
                elif name:
                    addr = self.stub(name) + add
                else:
                    addr = 0
                if typ in (1025, 1026, 257, 1024):
                    self.uc.mem_write(off, struct.pack("<Q", addr))

    # ------------------------------------------------------------ 调用
    def rd(self, reg):
        return self.uc.reg_read(reg)

    def wr(self, reg, v):
        self.uc.reg_write(reg, v & 0xFFFFFFFFFFFFFFFF)

    def read(self, addr, n):
        return bytes(self.uc.mem_read(addr, n))

    def write(self, addr, data):
        self.uc.mem_write(addr, data)

    def alloc(self, n, zero=True):
        n = (n + 15) & ~15
        a = self.heap_ptr
        self.heap_ptr += n
        if self.heap_ptr > HEAP + HEAP_SIZE:
            raise RuntimeError("heap exhausted")
        if zero:
            self.write(a, b"\x00" * n)
        return a

    def cstr(self, s):
        b = s.encode() if isinstance(s, str) else s
        a = self.alloc(len(b) + 1)
        self.write(a, b + b"\x00")
        return a

    def read_cstr(self, addr, maxlen=8192):
        out = b""
        while len(out) < maxlen:
            c = self.read(addr + len(out), 1)
            if c == b"\x00":
                break
            out += c
        return out

    def call(self, target, args, timeout=60):
        """调用一个函数（名字或地址），最多 6 个参数"""
        if isinstance(target, str):
            addr = self.sym_addr(target)
            if addr is None:
                raise RuntimeError("找不到符号 %s" % target)
        else:
            addr = target
        sp = STACK - STACK_SIZE // 2 - 0x1000
        self.write(sp, b"\x00" * 0x1000)
        self.uc.reg_write(UC_ARM64_REG_SP, sp)
        self.uc.reg_write(UC_ARM64_REG_LR, RET_MAGIC)
        for i, a in enumerate(args[:8]):
            self.wr(UC_ARM64_REG_X0 + i, a if isinstance(a, int) else 0)
        skip = None
        try:
            self.uc.emu_start(addr, RET_MAGIC, timeout=timeout * 1000000,
                              count=200000000)
        except UcError as ex:
            skip = str(ex)
        return self.rd(UC_ARM64_REG_X0), skip

    # ------------------------------------------------------------ libc 桩
    def hook(self):
        uc = self.uc

        def on_code(uc, address, size, user):
            name = self.by_addr.get(address)
            if name is None:
                return
            self.impl(name)
            lr = uc.reg_read(UC_ARM64_REG_LR)
            uc.reg_write(UC_ARM64_REG_PC, lr)

        uc.hook_add(UC_HOOK_CODE, on_code)

    def impl(self, name):
        uc = self.uc
        g = lambda i: uc.reg_read(UC_ARM64_REG_X0 + i)
        ret = lambda v: uc.reg_write(UC_ARM64_REG_X0, v & 0xFFFFFFFFFFFFFFFF)
        self._calls += 1
        self.misses[name] = self.misses.get(name, 0) + 1

        if name in ("malloc", "realloc"):
            n = g(0) or 16
            if name == "realloc" and g(0):
                n = g(1) or 16
            return ret(self.alloc(n))
        if name == "calloc":
            n = (g(0) or 1) * (g(1) or 1)
            return ret(self.alloc(n or 16))
        if name == "free":
            return ret(0)
        if name == "posix_memalign":
            p = g(0)
            self.write(p, struct.pack("<Q", self.alloc(g(2) or 16)))
            return ret(0)
        if name in ("memcpy", "memmove"):
            d, s, n = g(0), g(1), g(2)
            if n:
                self.write(d, self.read(s, n))
            return ret(d)
        if name == "memset":
            d, v, n = g(0), g(1) & 0xFF, g(2)
            if n:
                self.write(d, bytes([v]) * n)
            return ret(d)
        if name == "memcmp":
            a, b, n = self.read(g(0), g(2)), self.read(g(1), g(2))
            return ret(0 if a == b else (-1 if a < b else 1))
        if name == "memchr":
            hay, ch, n = self.read(g(0), g(2)), g(1) & 0xFF, g(2)
            i = hay.find(bytes([ch]))
            return ret(g(0) + i if i >= 0 else 0)
        if name == "strlen":
            return ret(len(self.read_cstr(g(0))))
        if name in ("strcmp", "strcasecmp"):
            a, b = self.read_cstr(g(0)), self.read_cstr(g(1))
            if name == "strcasecmp":
                a, b = a.lower(), b.lower()
            return ret(0 if a == b else (1 if a > b else -1))
        if name == "strncmp":
            n = g(2)
            a, b = self.read_cstr(g(0))[:n], self.read_cstr(g(1))[:n]
            return ret(0 if a == b else (1 if a > b else -1))
        if name in ("strcpy", "stpcpy"):
            s = self.read_cstr(g(1))
            self.write(g(0), s + b"\x00")
            return ret(g(0) + (len(s) if name == "stpcpy" else 0))
        if name == "strncpy":
            s = self.read_cstr(g(1))[:g(2)]
            self.write(g(0), s + b"\x00" * (g(2) - len(s)))
            return ret(g(0))
        if name == "strcat":
            d = self.read_cstr(g(0))
            s = self.read_cstr(g(1))
            self.write(g(0), d + s + b"\x00")
            return ret(g(0))
        if name == "strdup":
            s = self.read_cstr(g(0))
            return ret(self.cstr(s))
        if name == "strndup":
            s = self.read_cstr(g(0))[:g(1)]
            return ret(self.cstr(s))
        if name == "strchr":
            s, c = self.read_cstr(g(0)), g(1) & 0xFF
            i = s.find(bytes([c]))
            return ret(g(0) + i if i >= 0 else 0)
        if name == "strrchr":
            s, c = self.read_cstr(g(0)), g(1) & 0xFF
            i = s.rfind(bytes([c]))
            return ret(g(0) + i if i >= 0 else 0)
        if name == "strstr":
            h, n = self.read_cstr(g(0)), self.read_cstr(g(1))
            i = h.find(n)
            return ret(g(0) + i if i >= 0 else 0)
        if name in ("snprintf", "sprintf", "vsnprintf"):
            # 只处理最简形式：把格式串原样拷进去（够日志用）
            if name == "vsnprintf":
                dst, sz, fmt = g(0), g(1), g(2)
            elif name == "snprintf":
                dst, sz, fmt = g(0), g(1), g(2)
            else:
                dst, sz, fmt = g(0), 1 << 20, g(1)
            f = self.read_cstr(fmt)
            out = f.split(b"%")[0]
            out = out[:max(0, sz - 1)] if sz else out
            self.write(dst, out + b"\x00")
            return ret(len(out))
        if name in ("__android_log_print", "syslog", "printx", "xuidcc_log",
                    "openlog", "closelog"):
            return ret(0)
        if name == "__system_property_get":
            self.write(g(1), b"\x00" * 92)
            return ret(0)
        if name in ("time",):
            import time as _t
            v = int(_t.time())
            if g(0):
                self.write(g(0), struct.pack("<q", v))
            return ret(v)
        if name in ("gettimeofday",):
            import time as _t
            v = _t.time()
            if g(0):
                self.write(g(0), struct.pack("<qq", int(v), int((v % 1) * 1e6)))
            return ret(0)
        if name == "clock_gettime":
            import time as _t
            if g(1):
                self.write(g(1), struct.pack("<qq", int(_t.time()), 0))
            return ret(0)
        if name in ("srand", "srandom"):
            return ret(0)
        if name == "rand":
            import random
            return ret(random.randint(0, 0x7FFFFFFF))
        if name == "random":
            import random
            return ret(random.randint(0, 0x7FFFFFFF))
        if name in ("pthread_mutex_lock", "pthread_mutex_unlock",
                    "pthread_mutex_init", "pthread_once", "pthread_create",
                    "pthread_key_create", "pthread_setspecific"):
            return ret(0)
        if name == "pthread_getspecific":
            return ret(0)
        if name in ("__stack_chk_fail", "abort", "android_set_abort_message"):
            uc.emu_stop()
            return
        if name in ("open", "open64"):
            return ret(-1)
        if name == "read":
            return ret(0)
        if name in ("close", "fclose", "pclose"):
            return ret(0)
        if name in ("fopen", "popen"):
            return ret(0)
        if name in ("fread", "fgets"):
            return ret(0)
        if name in ("islower", "isupper", "isdigit", "isxdigit", "isalpha", "isalnum"):
            c = g(0) & 0xFF
            ok = (0x61 <= c <= 0x7A) if name == "islower" else \
                 (0x41 <= c <= 0x5A) if name == "isupper" else \
                 (0x30 <= c <= 0x39) if name == "isdigit" else \
                 chr(c).isalnum() if False else 0
            if name == "isxdigit":
                ok = chr(c) in "0123456789abcdefABCDEF"
            if name == "isalpha":
                ok = chr(c).isalpha()
            if name == "isalnum":
                ok = chr(c).isalnum()
            return ret(1 if ok else 0)
        if name == "tolower":
            c = g(0) & 0xFF
            return ret(c + 32 if 0x41 <= c <= 0x5A else c)
        if name == "toupper":
            c = g(0) & 0xFF
            return ret(c - 32 if 0x61 <= c <= 0x7A else c)
        if name in ("strtoul", "strtoull", "strtol", "strtoll"):
            s = self.read_cstr(g(0)).strip()
            try:
                v = int(s.split(b"\x00")[0].split(b" ")[0] or b"0", 0)
            except Exception:
                v = 0
            if g(1):
                self.write(g(1), struct.pack("<Q", g(0)))
            return ret(v)
        # 未知 → 返回 0，并记下来
        return ret(0)

    # ------------------------------------------------------------ 启动
    def boot(self):
        self.map()
        self.reloc()
        self.hook()

    def report(self):
        if self.verbose and self.misses:
            print("  调用的外部函数:", file=sys.stderr)
            for k in sorted(self.misses):
                print("    %-28s x%d" % (k, self.misses[k]), file=sys.stderr)
