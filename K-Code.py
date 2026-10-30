#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
K-Code  -  editor multilinguagem com visual inspirado no VS Code.
Linguagens: C, Java, Python, HTML, CSS e JavaScript.

Requisitos
  * Python 3.8+ com Tkinter (Linux: sudo apt install python3-tk)
  * Para executar cada linguagem (a IDE detecta sozinha o que estiver instalado):
      C ........ gcc / clang / tcc
      Java ..... JDK (javac + java)
      Python ... o próprio Python (e, para gerar .exe, o PyInstaller: a IDE instala)
      JS ....... Node.js (sem Node, roda no navegador com console embutido)
      HTML/CSS . navegador padrão (abre a pré-visualização)

Uso
  python k_code.py                  -> abre vazio
  python k_code.py arquivo.ext      -> abre o arquivo
  python k_code.py pasta            -> abre a pasta no explorador
"""

import codecs
import glob
import html as htmlmod
import http.server
import json
import math
import mimetypes
import os
import pathlib
import queue
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import urllib.parse
import webbrowser
from bisect import bisect_right
from tkinter import filedialog, messagebox, simpledialog, ttk
from tkinter import font as tkfont

APP = "K-Code"
VERSION = "1.9.0"
CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".kcode.json")
IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
MOD = "Command" if IS_MAC else "Control"
MOD_LABEL = "Cmd" if IS_MAC else "Ctrl"
NOWIN = subprocess.CREATE_NO_WINDOW if IS_WIN else 0
EXE = ".exe" if IS_WIN else ""

# --------------------------------------------------------------------------- #
#  Tema (Dark+ do VS Code)
# --------------------------------------------------------------------------- #
class TC(str):
    """Cor de tema. Para o Tk é um texto comum ("#rrggbb"), mas lembra de qual papel (chave)
    veio; assim, ao trocar de tema, cada widget é repintado com a cor certa."""

    def __new__(cls, value, key):
        o = super().__new__(cls, value)
        o.key = key
        return o


def _mix(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
    cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#%02x%02x%02x" % tuple(round(x + (y - x) * t) for x, y in zip(ca, cb))


UI_KEYS = tuple("""titlebar activity sidebar editor tab_off border fg fg_dim fg_bright fg_editor
    accent on_accent accent_hover sel sel_off curline hover tree_sel err warn ok info input
    input_txt menu_bg menu_active title_hover caret match errline warnline gutter gutter_cur
    scroll scroll_hover scroll_press logo popup_border tab_unfocus""".split())
SYN_KEYS = tuple("comment string number preproc keyword control type func const tag attr punct "
                 "selector prop".split())


def _theme(ui, syn):
    """Completa as cores que o tema não definiu a partir das principais (fundo, texto, destaque)."""
    u = dict(ui)
    ed, sd, fg = u["editor"], u["sidebar"], u["fg"]
    auto = dict(
        on_accent="#ffffff", accent_hover=_mix(u["accent"], "#ffffff", .18),
        title_hover=_mix(u["titlebar"], fg, .16), caret=u["fg_editor"],
        curline=_mix(ed, fg, .06), match=_mix(ed, u["info"], .30),
        errline=_mix(ed, u["err"], .20), warnline=_mix(ed, u["warn"], .18),
        gutter=_mix(ed, fg, .50), gutter_cur=_mix(ed, u["fg_bright"], .85),
        scroll=_mix(ed, fg, .22), scroll_hover=_mix(ed, fg, .36),
        scroll_press=_mix(ed, fg, .55), logo=_mix(ed, u["accent"], .55),
        popup_border=_mix(sd, fg, .22), tab_unfocus=_mix(ed, fg, .40),
        hover=_mix(sd, fg, .08), tree_sel=_mix(sd, fg, .13), sel_off=_mix(ed, fg, .15),
        input_txt=u["info"], menu_bg=sd)
    for k, v in auto.items():
        u.setdefault(k, v)
    assert set(u) == set(UI_KEYS), set(UI_KEYS) ^ set(u)
    assert set(syn) == set(SYN_KEYS), set(SYN_KEYS) ^ set(syn)
    return u, dict(syn)


DEFAULT_THEME = "Dark+ (padrão)"
THEMES = {
    DEFAULT_THEME: _theme(dict(
        titlebar="#3c3c3c", activity="#333333", sidebar="#252526", editor="#1e1e1e",
        tab_off="#2d2d2d", border="#2b2b2b", fg="#cccccc", fg_dim="#858585",
        fg_bright="#ffffff", fg_editor="#d4d4d4", accent="#007acc", on_accent="#ffffff",
        accent_hover="#1f8ad2", sel="#264f78", sel_off="#3a3d41", curline="#282828",
        hover="#2a2d2e", tree_sel="#37373d", err="#f48771", warn="#cca700", ok="#89d185",
        info="#3794ff", input="#3c3c3c", input_txt="#9cdcfe", menu_bg="#252526",
        menu_active="#04395e", title_hover="#505050", caret="#aeafad", match="#515c6a",
        errline="#3d1f1f", warnline="#38341a", gutter="#6e7681", gutter_cur="#c6c6c6",
        scroll="#424242", scroll_hover="#686868", scroll_press="#979797", logo="#2b5f87",
        popup_border="#454545", tab_unfocus="#6b6b6b"),
        dict(comment="#6a9955", string="#ce9178", number="#b5cea8", preproc="#c586c0",
             keyword="#569cd6", control="#c586c0", type="#4ec9b0", func="#dcdcaa",
             const="#4fc1ff", tag="#569cd6", attr="#9cdcfe", punct="#808080",
             selector="#d7ba7d", prop="#9cdcfe")),
    "Light+ (claro)": _theme(dict(
        titlebar="#dddddd", activity="#ececec", sidebar="#f3f3f3", editor="#ffffff",
        tab_off="#ececec", border="#e0e0e0", fg="#3b3b3b", fg_dim="#767676",
        fg_bright="#000000", fg_editor="#000000", accent="#007acc", sel="#add6ff",
        err="#c72e0f", warn="#946b00", ok="#2f7d32", info="#0b67c7", input="#ffffff",
        menu_active="#cce4f7", curline="#f4f4f4"),
        dict(comment="#008000", string="#a31515", number="#098658", preproc="#af00db",
             keyword="#0000ff", control="#af00db", type="#267f99", func="#795e26",
             const="#0070c1", tag="#800000", attr="#e50000", punct="#808080",
             selector="#800000", prop="#001080")),
    "Monokai": _theme(dict(
        titlebar="#1e1f1c", activity="#171815", sidebar="#1e1f1c", editor="#272822",
        tab_off="#34352f", border="#171815", fg="#cfcfc2", fg_dim="#75715e",
        fg_bright="#f8f8f2", fg_editor="#f8f8f2", accent="#75715e", on_accent="#f8f8f2",
        sel="#49483e", err="#f92672", warn="#e6db74", ok="#a6e22e", info="#66d9ef",
        input="#3e3d32", menu_active="#49483e"),
        dict(comment="#75715e", string="#e6db74", number="#ae81ff", preproc="#f92672",
             keyword="#f92672", control="#f92672", type="#66d9ef", func="#a6e22e",
             const="#ae81ff", tag="#f92672", attr="#a6e22e", punct="#a59f85",
             selector="#a6e22e", prop="#66d9ef")),
    "Dracula": _theme(dict(
        titlebar="#21222c", activity="#191a21", sidebar="#21222c", editor="#282a36",
        tab_off="#21222c", border="#191a21", fg="#f8f8f2", fg_dim="#6272a4",
        fg_bright="#ffffff", fg_editor="#f8f8f2", accent="#bd93f9", on_accent="#282a36",
        sel="#44475a", err="#ff5555", warn="#f1fa8c", ok="#50fa7b", info="#8be9fd",
        input="#343746", menu_active="#44475a"),
        dict(comment="#6272a4", string="#f1fa8c", number="#bd93f9", preproc="#ff79c6",
             keyword="#ff79c6", control="#ff79c6", type="#8be9fd", func="#50fa7b",
             const="#bd93f9", tag="#ff79c6", attr="#50fa7b", punct="#9aa0c4",
             selector="#50fa7b", prop="#8be9fd")),
    "One Dark": _theme(dict(
        titlebar="#21252b", activity="#181a1f", sidebar="#21252b", editor="#282c34",
        tab_off="#21252b", border="#181a1f", fg="#abb2bf", fg_dim="#5c6370",
        fg_bright="#ffffff", fg_editor="#abb2bf", accent="#4d78cc", sel="#3e4451",
        err="#e06c75", warn="#e5c07b", ok="#98c379", info="#61afef", input="#333842",
        menu_active="#3a4150"),
        dict(comment="#5c6370", string="#98c379", number="#d19a66", preproc="#c678dd",
             keyword="#c678dd", control="#c678dd", type="#e5c07b", func="#61afef",
             const="#d19a66", tag="#e06c75", attr="#d19a66", punct="#7f848e",
             selector="#e5c07b", prop="#e06c75")),
    "Nord": _theme(dict(
        titlebar="#272c36", activity="#232831", sidebar="#272c36", editor="#2e3440",
        tab_off="#2b303b", border="#232831", fg="#d8dee9", fg_dim="#7b88a1",
        fg_bright="#eceff4", fg_editor="#d8dee9", accent="#5e81ac", on_accent="#eceff4",
        sel="#434c5e", err="#bf616a", warn="#ebcb8b", ok="#a3be8c", info="#88c0d0",
        input="#3b4252", menu_active="#434c5e"),
        dict(comment="#616e88", string="#a3be8c", number="#b48ead", preproc="#81a1c1",
             keyword="#81a1c1", control="#81a1c1", type="#8fbcbb", func="#88c0d0",
             const="#b48ead", tag="#81a1c1", attr="#8fbcbb", punct="#7b88a1",
             selector="#ebcb8b", prop="#88c0d0")),
    "Solarized Dark": _theme(dict(
        titlebar="#00212b", activity="#00252f", sidebar="#00212b", editor="#002b36",
        tab_off="#00212b", border="#001a22", fg="#93a1a1", fg_dim="#586e75",
        fg_bright="#fdf6e3", fg_editor="#839496", accent="#268bd2", on_accent="#fdf6e3",
        sel="#073642", err="#dc322f", warn="#b58900", ok="#859900", info="#268bd2",
        input="#073642", menu_active="#0a4656"),
        dict(comment="#586e75", string="#2aa198", number="#d33682", preproc="#cb4b16",
             keyword="#859900", control="#cb4b16", type="#b58900", func="#268bd2",
             const="#6c71c4", tag="#268bd2", attr="#93a1a1", punct="#586e75",
             selector="#b58900", prop="#268bd2")),
    "Solarized Light": _theme(dict(
        titlebar="#ddd6c1", activity="#e4ddc8", sidebar="#eee8d5", editor="#fdf6e3",
        tab_off="#e8e1cc", border="#d9d2be", fg="#586e75", fg_dim="#93a1a1",
        fg_bright="#073642", fg_editor="#657b83", accent="#268bd2", on_accent="#fdf6e3",
        sel="#cdd8cf", err="#dc322f", warn="#a67c00", ok="#6f7f00", info="#268bd2",
        input="#fdf6e3", menu_active="#cfdcd5"),
        dict(comment="#93a1a1", string="#2aa198", number="#d33682", preproc="#cb4b16",
             keyword="#859900", control="#cb4b16", type="#b58900", func="#268bd2",
             const="#6c71c4", tag="#268bd2", attr="#586e75", punct="#93a1a1",
             selector="#b58900", prop="#268bd2")),
    "Alto contraste": _theme(dict(
        titlebar="#000000", activity="#000000", sidebar="#000000", editor="#000000",
        tab_off="#0a0a0a", border="#6fc3df", fg="#ffffff", fg_dim="#b3b3b3",
        fg_bright="#ffffff", fg_editor="#ffffff", accent="#005a9e", sel="#1d4a8f",
        err="#ff6b6b", warn="#ffd700", ok="#6bff6b", info="#6fc3df", input="#1a1a1a",
        menu_active="#0f4a85"),
        dict(comment="#7ca668", string="#ce9178", number="#b5cea8", preproc="#c586c0",
             keyword="#569cd6", control="#c586c0", type="#4ec9b0", func="#dcdcaa",
             const="#4fc1ff", tag="#569cd6", attr="#9cdcfe", punct="#d4d4d4",
             selector="#d7ba7d", prop="#9cdcfe")),
}

C = {}      # cores da interface (papel -> TC)
SYN = {}    # cores do realce de sintaxe (tipo de token -> "#rrggbb")


def set_palette(name):
    """Troca a paleta ativa. C e SYN são alterados no lugar, então todo código que lê C[...] já
    pega o tema novo (os widgets existentes são repintados por App.set_theme)."""
    ui, syn = THEMES.get(name) or THEMES[DEFAULT_THEME]
    for k, v in ui.items():
        C[k] = TC(v, k)
    SYN.update(syn)


# Registra o "papel" de cada cor dada a um widget (bg=C["editor"] -> papel "editor"),
# para repintar tudo ao trocar de tema, sem precisar reconstruir a interface.
def _track(w, *dicts):
    for d in dicts:
        if isinstance(d, dict):
            for opt, val in d.items():
                roles = w.__dict__.setdefault("_kc_roles", {})
                if isinstance(val, TC):
                    roles[opt] = val.key
                else:
                    roles.pop(opt, None)


_orig_widget_init = tk.BaseWidget.__init__
_orig_configure = tk.Misc._configure


def _widget_init(self, master, widgetName, cnf={}, kw={}, extra=()):
    _orig_widget_init(self, master, widgetName, cnf, kw, extra)
    _track(self, cnf, kw)


def _configure(self, cmd, cnf, kw):
    res = _orig_configure(self, cmd, cnf, kw)
    if cmd == "configure":
        _track(self, cnf, kw)
    return res


tk.BaseWidget.__init__ = _widget_init
tk.Misc._configure = _configure
set_palette(DEFAULT_THEME)


def update_config(**kw):
    """Atualiza só as chaves dadas em ~/.kcode.json, mantendo as demais."""
    cfg = read_config()
    cfg.update(kw)
    cfg = {k: v for k, v in cfg.items() if v is not None}
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass


def read_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        return cfg if isinstance(cfg, dict) else {}
    except (OSError, ValueError):
        return {}


# --------------------------------------------------------------------------- #
#  Configurações do usuário (salvas em ~/.kcode.json, chave "settings")
# --------------------------------------------------------------------------- #
UI_FONT_PREFS = ["Segoe UI", "SF Pro Text", "Ubuntu", "Noto Sans", "DejaVu Sans", "Helvetica Neue"]
CODE_FONT_PREFS = ["Cascadia Code", "Consolas", "Menlo", "JetBrains Mono", "Fira Code",
                   "DejaVu Sans Mono", "Liberation Mono", "Courier New"]
C_STANDARDS = ("c99", "c11", "c17", "gnu11", "gnu17")
SETTINGS_DEFAULTS = dict(code_font="", code_size=13, out_size=11, ui_font="", ui_size=9,
                         line_spacing=1, indent=0, live_on=True, warn=True, opt=False,
                         noconsole=False, c_std="c11")
SETTINGS_RANGES = dict(code_size=(8, 40), out_size=(8, 24), ui_size=(8, 13), line_spacing=(0, 10))


def load_settings():
    """Lê as configurações salvas, completando o que faltar e corrigindo valores inválidos."""
    raw = read_config().get("settings")
    raw = raw if isinstance(raw, dict) else {}
    s = dict(SETTINGS_DEFAULTS)
    for k, d in SETTINGS_DEFAULTS.items():
        v = raw.get(k, d)
        if isinstance(d, bool):
            s[k] = v if isinstance(v, bool) else d
        elif isinstance(d, int):
            try:
                v = int(v)
            except (TypeError, ValueError):
                v = d
            lo, hi = SETTINGS_RANGES.get(k, (0, 99))
            s[k] = max(lo, min(hi, v))
        else:
            s[k] = v if isinstance(v, str) else d
    if s["indent"] not in (0, 2, 4, 8):
        s["indent"] = 0
    if s["c_std"] not in C_STANDARDS:
        s["c_std"] = SETTINGS_DEFAULTS["c_std"]
    return s


# --------------------------------------------------------------------------- #
#  Palavras-chave
# --------------------------------------------------------------------------- #
def _s(text):
    return set(text.split())


W_C = dict(
    control=_s("if else for while do switch case default break continue return goto"),
    keyword=_s("sizeof typedef struct union enum static extern const volatile register inline "
               "auto restrict _Alignas _Alignof _Atomic _Noreturn _Static_assert _Thread_local"),
    type=_s("int char float double void long short signed unsigned _Bool _Complex bool size_t "
            "ssize_t ptrdiff_t FILE wchar_t int8_t int16_t int32_t int64_t uint8_t uint16_t "
            "uint32_t uint64_t intptr_t uintptr_t time_t clock_t"),
    const=_s("NULL EOF true false stdin stdout stderr INT_MAX INT_MIN UINT_MAX LONG_MAX CHAR_BIT "
             "RAND_MAX EXIT_SUCCESS EXIT_FAILURE BUFSIZ M_PI __FILE__ __LINE__ __func__"),
    cap=False)
W_JAVA = dict(
    control=_s("if else for while do switch case default break continue return throw try catch "
               "finally yield assert"),
    keyword=_s("abstract class enum extends final implements import instanceof interface native "
               "new package private protected public static strictfp super synchronized this "
               "throws transient volatile record sealed permits"),
    type=_s("int long short byte char float double boolean void var"),
    const=_s("true false null"), cap=True)
W_PY = dict(
    control=_s("if elif else for while break continue return try except finally raise with yield "
               "assert pass del"),
    keyword=_s("def class import from as global nonlocal lambda in is not and or async await"),
    type=_s("int str float bool list dict set tuple bytes bytearray object type range frozenset "
            "complex"),
    const=_s("True False None self cls __name__ __main__"), cap=True)
W_JS = dict(
    control=_s("if else for while do switch case default break continue return throw try catch "
               "finally yield await"),
    keyword=_s("var let const function class extends new this super import export from as async "
               "static typeof instanceof in of delete void with debugger"),
    type=set(),
    const=_s("true false null undefined NaN Infinity console document window module require "
             "exports process globalThis"),
    cap=True)

VOID_TAGS = _s("area base br col embed hr img input link meta param source track wbr")

# --------------------------------------------------------------------------- #
#  Tokenizadores (realce de sintaxe)
# --------------------------------------------------------------------------- #
DQ3 = '"' * 3
SQ3 = "'" * 3
NUM = (r"\b(?:0[xX][0-9a-fA-F_]+|0[bB][01_]+|(?:\d[\d_]*\.?\d*|\.\d+)(?:[eE][+-]?\d+)?)"
       r"[uUlLfFjJnN]*\b")
STR_SIMPLE = r"\"(?:\\.|[^\"\\\n])*\"?|'(?:\\.|[^'\\\n])*'?"
FUNC_AFTER = re.compile(r"[ \t]*\(")

C_RE = re.compile(
    r"(?P<comment>//[^\n]*|/\*[\s\S]*?(?:\*/|\Z))"
    r"|(?P<string>" + STR_SIMPLE + r")"
    r"|(?P<include>^[ \t]*\#[ \t]*include\b[ \t]*(?P<hdr><[^>\n]*>)?)"
    r"|(?P<preproc>^[ \t]*\#[ \t]*[A-Za-z_]*)"
    r"|(?P<number>" + NUM + r")"
    r"|(?P<word>[A-Za-z_]\w*)", re.M)
JAVA_RE = re.compile(
    r"(?P<comment>//[^\n]*|/\*[\s\S]*?(?:\*/|\Z))"
    r"|(?P<string>" + DQ3 + r"[\s\S]*?(?:" + DQ3 + r"|\Z)|" + STR_SIMPLE + r")"
    r"|(?P<anno>@[A-Za-z_]\w*)"
    r"|(?P<number>" + NUM + r")"
    r"|(?P<word>[A-Za-z_$][\w$]*)")
PY_RE = re.compile(
    r"(?P<comment>#[^\n]*)"
    r"|(?P<string>(?:[rRbBuUfF]{1,2})?(?:" + DQ3 + r"[\s\S]*?(?:" + DQ3 + r"|\Z)|"
    + SQ3 + r"[\s\S]*?(?:" + SQ3 + r"|\Z)|" + STR_SIMPLE + r"))"
    r"|(?P<deco>^[ \t]*@[\w.]+)"
    r"|(?P<number>" + NUM + r")"
    r"|(?P<word>[A-Za-z_]\w*)", re.M)
JS_RE = re.compile(
    r"(?P<comment>//[^\n]*|/\*[\s\S]*?(?:\*/|\Z))"
    r"|(?P<string>`(?:\\.|[^`\\])*`?|" + STR_SIMPLE + r")"
    r"|(?P<number>" + NUM + r")"
    r"|(?P<word>[A-Za-z_$][\w$]*)")
CSS_RE = re.compile(
    r"(?P<comment>/\*[\s\S]*?(?:\*/|\Z))"
    r"|(?P<string>" + STR_SIMPLE + r")"
    r"|(?P<atrule>@[\w-]+)"
    r"|(?P<num>-?(?:\d+\.?\d*|\.\d+)(?:[a-zA-Z%]+)?)"
    r"|(?P<hash>\#[\w-]+)"
    r"|(?P<cls>\.[A-Za-z_][\w-]*)"
    r"|(?P<ident>-{0,2}[A-Za-z_][\w-]*)")
CSS_TERM = re.compile(r"[^{};]*([{};]?)")
HTML_RE = re.compile(
    r"(?P<comment><!--[\s\S]*?(?:-->|\Z))"
    r"|(?P<doctype><![A-Za-z][^>]*>?)"
    r"|(?P<tag>(?P<lt></?)(?P<name>[A-Za-z][\w:.-]*)"
    r"(?P<attrs>(?:\"[^\"]*\"?|'[^']*'?|[^<>\"'])*)(?P<gt>/?>)?)"
    r"|(?P<entity>&[#\w]+;)")
ATTR_RE = re.compile(r"(?P<str>\"[^\"]*\"?|'[^']*'?)|(?P<attr>[A-Za-z_:@][\w:.@-]*)")


def _word_tag(w, src, end, W):
    if w in W["control"]:
        return "control"
    if w in W["keyword"]:
        return "keyword"
    if w in W["type"]:
        return "type"
    if w in W["const"]:
        return "const"
    if W["cap"] and w[0].isupper() and any(ch.islower() for ch in w):
        return "type"
    if FUNC_AFTER.match(src, end):
        return "func"
    return None


def _tok_generic(src, regex, W):
    for m in regex.finditer(src):
        g = m.lastgroup
        if g in ("comment", "string", "number"):
            yield g, m.start(), m.end()
        elif g == "anno":
            yield "type", m.start(), m.end()
        elif g == "deco":
            yield "func", m.start(), m.end()
        elif g == "word":
            tag = _word_tag(m.group(), src, m.end(), W)
            if tag:
                yield tag, m.start(), m.end()


def tok_c(src):
    for m in C_RE.finditer(src):
        if m.group("comment") is not None:
            yield "comment", m.start(), m.end()
        elif m.group("string") is not None:
            yield "string", m.start(), m.end()
        elif m.group("include") is not None:
            if m.group("hdr") is not None:
                yield "preproc", m.start(), m.start("hdr")
                yield "string", m.start("hdr"), m.end("hdr")
            else:
                yield "preproc", m.start(), m.end()
        elif m.group("preproc") is not None:
            yield "preproc", m.start(), m.end()
        elif m.group("number") is not None:
            yield "number", m.start(), m.end()
        elif m.group("word") is not None:
            tag = _word_tag(m.group("word"), src, m.end(), W_C)
            if tag:
                yield tag, m.start(), m.end()


def tok_java(src):
    return _tok_generic(src, JAVA_RE, W_JAVA)


def tok_py(src):
    return _tok_generic(src, PY_RE, W_PY)


def tok_js(src):
    return _tok_generic(src, JS_RE, W_JS)


def tok_css(src):
    cache = [-1, ""]

    def terminator(pos):
        if pos <= cache[0]:
            return cache[1]
        m = CSS_TERM.match(src, pos)
        cache[0] = m.end() - 1 if m.group(1) else m.end()
        cache[1] = m.group(1)
        return cache[1]

    for m in CSS_RE.finditer(src):
        g = m.lastgroup
        a, b = m.start(), m.end()
        if g in ("comment", "string"):
            yield g, a, b
        elif g == "atrule":
            yield "control", a, b
        elif g == "num":
            yield "number", a, b
        elif g in ("hash", "cls"):
            if terminator(b) == "{":
                yield "selector", a, b
            elif g == "hash":
                yield "number", a, b
        elif g == "ident":
            word = m.group()
            if terminator(b) == "{":
                yield "selector", a, b
            elif word.startswith("--") or re.match(r"[ \t]*:", src[b:b + 20]):
                yield "prop", a, b
            elif FUNC_AFTER.match(src, b):
                yield "func", a, b
            else:
                yield "string", a, b


def tok_html(src):
    pos, n = 0, len(src)
    while True:
        m = HTML_RE.search(src, pos)
        if not m:
            break
        pos = m.end()
        if m.group("comment") is not None:
            yield "comment", m.start(), m.end()
        elif m.group("doctype") is not None:
            yield "preproc", m.start(), m.end()
        elif m.group("entity") is not None:
            yield "const", m.start(), m.end()
        elif m.group("tag") is not None:
            yield "punct", m.start("lt"), m.end("lt")
            yield "tag", m.start("name"), m.end("name")
            base = m.start("attrs")
            for am in ATTR_RE.finditer(m.group("attrs")):
                tag = "string" if am.group("str") is not None else "attr"
                yield tag, base + am.start(), base + am.end()
            if m.group("gt"):
                yield "punct", m.start("gt"), m.end("gt")
            name = m.group("name").lower()
            if m.group("lt") == "<" and m.group("gt") == ">" and name in ("style", "script"):
                em = re.compile(r"</" + name + r"\b", re.I).search(src, pos)
                end = em.start() if em else n
                inner = src[pos:end]
                sub = tok_css if name == "style" else tok_js
                for t, a, b in sub(inner):
                    yield t, pos + a, pos + b
                pos = end


# --------------------------------------------------------------------------- #
#  Linguagens
# --------------------------------------------------------------------------- #
LANGS = {
    "c": dict(name="C", exts=(".c", ".h"), tok=tok_c, indent=4, cmt=("// ", ""),
              icon=("C", "#6fb3e0")),
    "java": dict(name="Java", exts=(".java",), tok=tok_java, indent=4, cmt=("// ", ""),
                 icon=("J", "#e8913a")),
    "python": dict(name="Python", exts=(".py", ".pyw"), tok=tok_py, indent=4, cmt=("# ", ""),
                   icon=("Py", "#ffd43b")),
    "html": dict(name="HTML", exts=(".html", ".htm"), tok=tok_html, indent=2,
                 cmt=("<!-- ", " -->"), icon=("<>", "#e44d26")),
    "css": dict(name="CSS", exts=(".css",), tok=tok_css, indent=2, cmt=("/* ", " */"),
                icon=("#", "#519aba")),
    "js": dict(name="JavaScript", exts=(".js", ".mjs", ".cjs"), tok=tok_js, indent=2,
               cmt=("// ", ""), icon=("JS", "#f1e05a")),
    "text": dict(name="Texto", exts=(".txt",), tok=None, indent=4, cmt=("# ", ""),
                 icon=("•", "#858585")),
}
EXT2LANG = {e: k for k, v in LANGS.items() for e in v["exts"]}
RUNNABLE = ("c", "java", "python", "js", "html", "css")


def lang_for(name):
    return EXT2LANG.get(os.path.splitext(name)[1].lower(), "text")


def all_exts():
    return " ".join("*" + e for k in RUNNABLE for e in LANGS[k]["exts"])


# --------------------------------------------------------------------------- #
#  Modelos / exemplos
# --------------------------------------------------------------------------- #
HTML_SKELETON = ('<!DOCTYPE html>\n<html lang="pt-BR">\n<head>\n  <meta charset="UTF-8">\n'
                 '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
                 '  <title>Documento</title>\n</head>\n<body>\n  ', '\n</body>\n</html>\n')

EXAMPLES = {
    "c": [
        ("Olá, mundo", r'''#include <stdio.h>

int main(void) {
    printf("Olá, mundo!\n");
    return 0;
}
'''),
        ("Entrada e saída (scanf)", r'''#include <stdio.h>

int main(void) {
    char nome[50];
    int idade;

    printf("Qual é o seu nome? ");
    scanf("%49s", nome);
    printf("Quantos anos você tem? ");
    scanf("%d", &idade);

    printf("Olá, %s! Em 10 anos você terá %d anos.\n", nome, idade + 10);
    return 0;
}
'''),
        ("Vetores e ponteiros", r'''#include <stdio.h>

void imprimir(const int *v, int n) {
    for (int i = 0; i < n; i++) printf("%d ", *(v + i));
    printf("\n");
}

int main(void) {
    int v[] = {5, 3, 8, 1, 9, 2};
    int n = sizeof(v) / sizeof(v[0]);

    imprimir(v, n);
    for (int i = 0; i < n - 1; i++)
        for (int j = 0; j < n - i - 1; j++)
            if (v[j] > v[j + 1]) {
                int t = v[j];
                v[j] = v[j + 1];
                v[j + 1] = t;
            }
    imprimir(v, n);
    return 0;
}
'''),
    ],
    "java": [
        ("Olá, mundo", r'''public class Main {
    public static void main(String[] args) {
        System.out.println("Olá, mundo!");
    }
}
'''),
        ("Entrada (Scanner)", r'''import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner in = new Scanner(System.in);

        System.out.print("Qual é o seu nome? ");
        String nome = in.nextLine();
        System.out.print("Quantos anos você tem? ");
        int idade = in.nextInt();

        System.out.println("Olá, " + nome + "! Em 10 anos você terá " + (idade + 10) + " anos.");
    }
}
'''),
        ("Classes e objetos", r'''import java.util.ArrayList;
import java.util.List;

class Produto {
    private final String nome;
    private final double preco;

    Produto(String nome, double preco) {
        this.nome = nome;
        this.preco = preco;
    }

    @Override
    public String toString() {
        return String.format("%s - R$ %.2f", nome, preco);
    }

    double getPreco() { return preco; }
}

public class Main {
    public static void main(String[] args) {
        List<Produto> lista = new ArrayList<>();
        lista.add(new Produto("Rosa vermelha", 7.5));
        lista.add(new Produto("Girassol", 5.0));

        double total = 0;
        for (Produto p : lista) {
            System.out.println(p);
            total += p.getPreco();
        }
        System.out.printf("Total: R$ %.2f%n", total);
    }
}
'''),
    ],
    "python": [
        ("Olá, mundo", '''print("Olá, mundo!")
'''),
        ("Entrada de dados", '''nome = input("Qual é o seu nome? ")
idade = int(input("Quantos anos você tem? "))

print(f"Olá, {nome}! Em 10 anos você terá {idade + 10} anos.")
'''),
        ("Classes e listas", '''class Produto:
    def __init__(self, nome, preco):
        self.nome = nome
        self.preco = preco

    def __str__(self):
        return f"{self.nome} - R$ {self.preco:.2f}"


produtos = [Produto("Rosa vermelha", 7.5), Produto("Girassol", 5.0), Produto("Orquídea", 32.9)]

for p in produtos:
    print(p)

caros = [p.nome for p in produtos if p.preco > 6]
print("Mais caros que R$ 6:", caros)
print("Total:", sum(p.preco for p in produtos))
'''),
    ],
    "html": [
        ("Página básica", r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Minha página</title>
  <style>
    body { font-family: Arial, sans-serif; background: #f3f9f1; color: #2d583a; margin: 0; }
    header { background: #2d583a; color: #fff; padding: 24px; text-align: center; }
    main { max-width: 600px; margin: 24px auto; padding: 0 16px; }
    button { background: #2d583a; color: #fff; border: 0; padding: 10px 18px;
             border-radius: 6px; cursor: pointer; }
    button:hover { opacity: .85; }
  </style>
</head>
<body>
  <header>
    <h1>Olá, mundo!</h1>
  </header>
  <main>
    <p>Esta é uma página HTML criada no K-Code.</p>
    <button id="btn">Clique aqui</button>
    <p id="saida"></p>
  </main>
  <script>
    let cliques = 0;
    document.getElementById("btn").addEventListener("click", () => {
      cliques++;
      document.getElementById("saida").textContent = "Cliques: " + cliques;
    });
  </script>
</body>
</html>
'''),
        ("Formulário", r'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Formulário</title>
</head>
<body>
  <h1>Contato</h1>
  <form onsubmit="event.preventDefault(); alert('Enviado!')">
    <label>Nome: <input type="text" name="nome" required></label><br><br>
    <label>E-mail: <input type="email" name="email" required></label><br><br>
    <label>Mensagem:<br><textarea name="msg" rows="4" cols="40"></textarea></label><br><br>
    <button type="submit">Enviar</button>
  </form>
</body>
</html>
'''),
    ],
    "css": [
        ("Estilo base", r'''/* Variáveis */
:root {
  --verde: #2d583a;
  --fundo: #f3f9f1;
}

body {
  font-family: "Segoe UI", Arial, sans-serif;
  background: var(--fundo);
  color: var(--verde);
  margin: 0;
  line-height: 1.6;
}

header, footer {
  background: var(--verde);
  color: #fff;
  padding: 20px;
  text-align: center;
}

.card {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  padding: 16px;
  margin: 16px auto;
  max-width: 480px;
}

.btn, button {
  background: var(--verde);
  color: #fff;
  border: none;
  padding: 10px 18px;
  border-radius: 6px;
  cursor: pointer;
  transition: opacity 0.2s;
}

.btn:hover, button:hover {
  opacity: 0.85;
}

@media (max-width: 600px) {
  .card { margin: 8px; }
}
'''),
    ],
    "js": [
        ("Olá, console", '''console.log("Olá, mundo!");

const nome = "K-Code";
console.log(`Bem-vindo ao ${nome}`);
'''),
        ("Funções e arrays", '''const produtos = [
  { nome: "Rosa vermelha", preco: 7.5 },
  { nome: "Girassol", preco: 5.0 },
  { nome: "Orquídea", preco: 32.9 },
];

function formatar(p) {
  return `${p.nome} - R$ ${p.preco.toFixed(2)}`;
}

produtos.forEach((p) => console.log(formatar(p)));

const caros = produtos.filter((p) => p.preco > 6).map((p) => p.nome);
console.log("Mais caros que R$ 6:", caros);

const total = produtos.reduce((soma, p) => soma + p.preco, 0);
console.log("Total:", total);
'''),
        ("Entrada (readline)", '''const readline = require("readline");
const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

rl.question("Qual é o seu nome? ", (nome) => {
  console.log(`Olá, ${nome}!`);
  rl.close();
});
'''),
    ],
}
TEMPLATES = {k: v[0][1] for k, v in EXAMPLES.items()}
TEMPLATE_SET = set(TEMPLATES.values())


# --------------------------------------------------------------------------- #
#  Ferramentas (detecção)
# --------------------------------------------------------------------------- #
def works(path, flag="--version"):
    try:
        r = subprocess.run([path, flag], capture_output=True, timeout=10, creationflags=NOWIN)
        return r.returncode == 0
    except Exception:
        return False


def find_cc():
    for name in ("gcc", "cc", "clang", "tcc"):
        p = shutil.which(name)
        if p and works(p):
            return p
    if IS_WIN:
        for p in (r"C:\msys64\ucrt64\bin\gcc.exe", r"C:\msys64\mingw64\bin\gcc.exe",
                  r"C:\MinGW\bin\gcc.exe", r"C:\mingw64\bin\gcc.exe",
                  r"C:\Program Files\CodeBlocks\MinGW\bin\gcc.exe",
                  r"C:\Program Files (x86)\Dev-Cpp\MinGW64\bin\gcc.exe",
                  r"C:\TDM-GCC-64\bin\gcc.exe"):
            if os.path.isfile(p) and works(p):
                return p
    return None


def find_java():
    dirs = []
    jh = os.environ.get("JAVA_HOME")
    if jh:
        dirs.append(os.path.join(jh, "bin"))
    w = shutil.which("javac")
    if w:
        dirs.append(os.path.dirname(w))
    if IS_WIN:
        for pat in (r"C:\Program Files\Java\*\bin", r"C:\Program Files\Eclipse Adoptium\*\bin",
                    r"C:\Program Files\Microsoft\jdk*\bin", r"C:\Program Files\Zulu\*\bin",
                    r"C:\Program Files\Amazon Corretto\*\bin"):
            dirs += sorted(glob.glob(pat), reverse=True)
    for d in dirs:
        javac, java = os.path.join(d, "javac" + EXE), os.path.join(d, "java" + EXE)
        if os.path.isfile(javac) and os.path.isfile(java) and works(javac, "-version"):
            return javac, java
    return None, None


def find_python():
    exe = sys.executable
    if exe and os.path.basename(exe).lower().startswith("pythonw"):
        alt = os.path.join(os.path.dirname(exe), "python.exe")
        if os.path.isfile(alt):
            exe = alt
    if exe and os.path.isfile(exe) and not getattr(sys, "frozen", False):
        return exe
    for n in ("python3", "python", "py"):
        p = shutil.which(n)
        if p and works(p):
            return p
    return None


def find_node():
    for n in ("node", "nodejs"):
        p = shutil.which(n)
        if p and works(p):
            return p
    return None


def detect_tools():
    javac, java = find_java()
    return dict(cc=find_cc(), javac=javac, java=java, python=find_python(), node=find_node())


def describe_exit(rc):
    if rc == 0:
        return "finalizado com código 0", "ok"
    if rc < 0 and not IS_WIN:
        names = {11: "falha de segmentação (SIGSEGV)", 6: "abortado (SIGABRT)",
                 8: "erro aritmético (SIGFPE)", 9: "encerrado (SIGKILL)",
                 15: "terminado (SIGTERM)", 7: "erro de barramento (SIGBUS)"}
        return f"encerrado pelo sinal {-rc}: {names.get(-rc, 'sinal desconhecido')}", "err"
    if IS_WIN:
        u = rc & 0xFFFFFFFF
        known = {0xC0000005: "violação de acesso (segmentation fault)",
                 0xC0000094: "divisão inteira por zero",
                 0xC00000FD: "estouro de pilha (stack overflow)",
                 0xC0000409: "falha de segurança / abort()"}
        if u in known:
            return f"falhou com 0x{u:08X} - {known[u]}", "err"
    return f"finalizado com código {rc}", "err"


def disp(cmd):
    """Versão legível de um comando para mostrar na saída."""
    out, skip = [], False
    for c in cmd:
        if skip:
            skip = False
            continue
        if c in ("-include", "-sourcepath", "-d", "-cp", "-o"):
            skip = True
            continue
        if c.startswith("-J") or c.startswith("-Dfile") or c.startswith("-Dstdout"):
            continue
        if len(c) > 40:
            c = "…"
        elif os.sep in c or "/" in c:
            c = os.path.basename(c)
        out.append(c)
    return " ".join(out)


def java_main_class(src, stem):
    pkg = re.search(r"^\s*package\s+([\w.]+)\s*;", src, re.M)
    cls = None
    mm = re.search(r"static\s+void\s+main\s*\(", src)
    if mm:
        found = list(re.finditer(r"\b(?:class|record|enum)\s+(\w+)", src[:mm.start()]))
        if found:
            cls = found[-1].group(1)
    if not cls:
        pub = re.search(r"public\s+(?:final\s+|abstract\s+)*class\s+(\w+)", src)
        cls = pub.group(1) if pub else stem
    return (pkg.group(1) + "." + cls) if pkg else cls


# --------------------------------------------------------------------------- #
#  Diagnósticos (compilador / erros de execução)
# --------------------------------------------------------------------------- #
DIAG_RE = re.compile(
    r"^(?P<file>.+?):(?P<line>\d+):(?:(?P<col>\d+):)?\s*"
    r"(?P<sev>fatal error|error|erro|warning|aviso|note|nota):\s*(?P<msg>.*)$")
UNDEF_RE = re.compile(r"undefined reference to .*|referência indefinida para .*", re.I)


def parse_diagnostics(text):
    probs = []
    for line in text.splitlines():
        m = DIAG_RE.match(line.strip())
        if m:
            sev = m.group("sev")
            sev = "error" if sev in ("fatal error", "error", "erro") else \
                "warning" if sev in ("warning", "aviso") else "note"
            probs.append(dict(file=m.group("file"), line=int(m.group("line")),
                              col=int(m.group("col") or 1), sev=sev, msg=m.group("msg")))
        elif UNDEF_RE.search(line):
            probs.append(dict(file="", line=0, col=0, sev="error",
                              msg=UNDEF_RE.search(line).group(0)))
    return probs


def parse_runtime(lang, text, cwd):
    probs = []
    cwd = os.path.abspath(cwd or ".")
    if lang == "python":
        frames = [(m.group(1), int(m.group(2)))
                  for m in re.finditer(r'File "(.+?)", line (\d+)', text)]
        if frames:
            user = [f for f in frames if not f[0].startswith("<") and "site-packages" not in f[0]
                    and os.path.abspath(os.path.join(cwd, f[0])).startswith(cwd)]
            f = (user or frames)[-1]
            msg = None
            for line in reversed(text.strip().splitlines()):
                if re.match(r"^[A-Za-z_][\w.]*(?:Error|Exception|Warning|Interrupt|Exit)\b",
                            line.strip()):
                    msg = line.strip()
                    break
            probs.append(dict(file=f[0], line=f[1], col=1, sev="error",
                              msg=msg or "Erro de execução"))
    elif lang == "js":
        col = 1
        m = re.search(r"^(.+?\.(?:m|c)?js):(\d+)\s*$", text, re.M)
        if not m:
            m = re.search(r"\(?((?:[A-Za-z]:)?[^\s():]+\.(?:m|c)?js):(\d+):(\d+)\)?", text)
            if m:
                col = int(m.group(3))
        if m:
            em = re.search(r"^(?:Uncaught\s+)?(\w*(?:Error|Exception)\b[^\n]*)", text, re.M)
            probs.append(dict(file=m.group(1), line=int(m.group(2)), col=col, sev="error",
                              msg=em.group(1) if em else "Erro de execução"))
    elif lang == "java":
        em = re.search(r'Exception in thread "[^"]*" (.+)', text)
        for fr in re.finditer(r"\(([\w$]+\.java):(\d+)\)", text):
            p = os.path.join(cwd, fr.group(1))
            if os.path.isfile(p):
                probs.append(dict(file=p, line=int(fr.group(2)), col=1, sev="error",
                                  msg=em.group(1) if em else "Exceção"))
                break
    return probs


# --------------------------------------------------------------------------- #
#  Páginas auxiliares de pré-visualização
# --------------------------------------------------------------------------- #
JS_RUNNER = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>JS - __NAME__</title>
<style>body{background:#1e1e1e;color:#d4d4d4;font:14px Consolas,Menlo,monospace;padding:18px}
h3{color:#569cd6;font-family:Segoe UI,Arial,sans-serif;margin-top:0}
.err{color:#f48771}.warn{color:#cca700}.row{white-space:pre-wrap;padding:2px 0}</style></head>
<body><h3>Console — __NAME__</h3><div id="o"></div>
<script>
const o=document.getElementById('o');
function fmt(x){try{return typeof x==='object'?JSON.stringify(x,null,2):String(x)}catch(e){return String(x)}}
function add(c,a){const d=document.createElement('div');d.className='row '+c;
d.textContent=Array.from(a).map(fmt).join(' ');o.appendChild(d)}
console.log=function(){add('',arguments)};console.info=console.log;
console.warn=function(){add('warn',arguments)};console.error=function(){add('err',arguments)};
window.onerror=function(m,s,l){add('err',[m+' (linha '+l+')'])};
</script><script src="__SRC__"></script></body></html>"""

CSS_SAMPLE = """<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Pré-visualização - __NAME__</title><link rel="stylesheet" href="__SRC__"></head><body>
<header><h1>Pré-visualização de __NAME__</h1><nav><a href="#">Início</a> <a href="#">Sobre</a>
<a href="#">Contato</a></nav></header>
<main class="container"><div class="card"><h2>Cartão de exemplo</h2>
<p>Parágrafo com <a href="#">um link</a> e <strong>texto em negrito</strong>.</p>
<ul><li>Item um</li><li>Item dois</li><li>Item três</li></ul>
<button class="btn">Botão</button> <a class="btn" href="#">Link como botão</a></div>
<form class="card"><label>Nome <input type="text" placeholder="Digite..."></label><br>
<label>Mensagem <textarea rows="3"></textarea></label><br><button type="submit">Enviar</button></form>
<table class="card" border="1"><tr><th>Produto</th><th>Preço</th></tr>
<tr><td>Rosa</td><td>7,50</td></tr><tr><td>Girassol</td><td>5,00</td></tr></table></main>
<footer><p>Rodapé</p></footer></body></html>"""


# --------------------------------------------------------------------------- #
#  Ícone do programa  ("</>")  -  desenhado por código, sem arquivos externos
# --------------------------------------------------------------------------- #
ICON_BG = (30, 30, 30)
ICON_STROKES = (
    (((21, 19), (6, 32), (21, 45)), (79, 193, 255)),     # <
    (((38, 11), (26, 53)), (255, 255, 255)),             # /
    (((43, 19), (58, 32), (43, 45)), (79, 193, 255)),    # >
)


def _seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def render_icon(size=64):
    """Calcula o ícone: devolve (linhas de cores #rrggbb, pixels transparentes)."""
    s = size / 64.0
    half = size / 2.0
    radius = 12 * s
    width = max(1.6, 5.4 * s) / 2.0
    strokes = [([(x * s, y * s) for x, y in pts], col) for pts, col in ICON_STROKES]
    rows, clear = [], []
    for y in range(size):
        row = []
        for x in range(size):
            px, py = x + 0.5, y + 0.5
            qx = abs(px - half) - (half - radius)
            qy = abs(py - half) - (half - radius)
            out = math.hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - radius
            if out > 0.5:
                clear.append((x, y))
                row.append("#1e1e1e")
                continue
            r, g, b = ICON_BG
            for pts, (cr, cg, cb) in strokes:
                d = min(_seg_dist(px, py, p, q) for p, q in zip(pts, pts[1:]))
                a = max(0.0, min(1.0, width - d + 0.5))
                if a:
                    r, g, b = r + (cr - r) * a, g + (cg - g) * a, b + (cb - b) * a
            row.append("#%02x%02x%02x" % (round(r), round(g), round(b)))
        rows.append(row)
    return rows, clear


def make_app_icon(size=64):
    rows, clear = render_icon(size)
    img = tk.PhotoImage(width=size, height=size)
    for y, row in enumerate(rows):
        img.put("{" + " ".join(row) + "}", to=(0, y))
    try:
        for x, y in clear:
            img.transparency_set(x, y, True)
    except (AttributeError, tk.TclError):
        pass
    return img


# --------------------------------------------------------------------------- #
#  Recolher / expandir blocos (code folding)
# --------------------------------------------------------------------------- #
HTML_TAG_RE = re.compile(r"<(/?)([A-Za-z][\w:-]*)((?:\"[^\"]*\"|'[^']*'|[^'\"<>])*)>")


def compute_folds(lang, src, toks):
    """Acha os blocos que podem ser recolhidos.

    Devolve {linha_inicial: linha_final} (linhas contadas a partir de 1). Ao recolher, as linhas
    depois da inicial até a final somem e a inicial passa a ocupar uma linha só."""
    starts = [0] + [m.end() for m in re.finditer("\n", src)]

    def line_of(o):
        return bisect_right(starts, o)

    folds = {}

    def add(a, b):
        if b > a and b > folds.get(a, 0):
            folds[a] = b

    comments = sorted((a, b) for t, a, b in toks if t == "comment")
    strings = sorted((a, b) for t, a, b in toks if t == "string")

    if lang in ("c", "java", "js", "css", "html"):
        # chaves { } que não estão dentro de texto ou comentário
        skip = sorted(comments + strings)
        skip_a = [a for a, _ in skip]
        stack = []
        for m in re.finditer(r"[{}]", src):
            o = m.start()
            i = bisect_right(skip_a, o) - 1
            if i >= 0 and o < skip[i][1]:
                continue
            if m.group() == "{":
                stack.append(line_of(o))
            elif stack:
                add(stack.pop(), line_of(o))
        for a, b in comments:                       # comentários de várias linhas
            add(line_of(a), line_of(max(a, b - 1)))

    if lang == "html":
        cm_a = [a for a, _ in comments]
        stack = []
        pos = 0
        while True:
            m = HTML_TAG_RE.search(src, pos)
            if not m:
                break
            o = m.start()
            i = bisect_right(cm_a, o) - 1
            if i >= 0 and o < comments[i][1]:
                pos = comments[i][1]
                continue
            pos = m.end()
            closing, name, attrs = m.group(1), m.group(2).lower(), m.group(3)
            if name in VOID_TAGS or attrs.rstrip().endswith("/"):
                continue
            if closing:
                for k in range(len(stack) - 1, -1, -1):
                    if stack[k][0] == name:
                        add(stack[k][1], line_of(o))
                        del stack[k:]
                        break
            else:
                stack.append((name, line_of(o)))
                if name in ("script", "style"):     # o conteúdo é CSS/JS: pula até o fechamento
                    em = re.compile(r"</" + name + r"\b", re.I).search(src, pos)
                    pos = em.start() if em else len(src)

    if lang == "python":
        cont = set()                                # linhas que continuam um texto de várias linhas
        endof = {}                                  # linha onde o texto começa -> onde termina
        for a, b in strings + comments:
            la, lb = line_of(a), line_of(max(a, b - 1))
            if lb > la:
                cont.update(range(la + 1, lb + 1))
                endof[la] = max(endof.get(la, la), lb)
        for a, b in strings:                        # docstrings
            add(line_of(a), line_of(max(a, b - 1)))
        sig = []
        for n, line in enumerate(src.split("\n"), 1):
            text = line.strip()
            if not text or n in cont or text.startswith("#"):
                continue
            ex = line.expandtabs(4)
            sig.append((n, len(ex) - len(ex.lstrip())))
        stack = []
        for k in range(len(sig) + 1):
            ind = sig[k][1] if k < len(sig) else -1
            while stack and stack[-1][1] >= ind:
                head = stack.pop()[0]
                last = sig[k - 1][0]
                if last > head:
                    add(head, endof.get(last, last))
            if k < len(sig):
                stack.append(sig[k])
    return folds


# --------------------------------------------------------------------------- #
#  Consumo do próprio programa (RAM e CPU), sem depender de pacotes externos
# --------------------------------------------------------------------------- #
def fmt_bytes(n):
    mb = n / 1048576.0
    return f"{mb / 1024:.2f} GB" if mb >= 1024 else f"{mb:.1f} MB"


class ProcStats:
    """Mede a RAM (memória residente) e a CPU do K-Code. Usa o psutil se existir; senão o que o
    sistema oferece (/proc no Linux, API do Windows, `ps` no macOS)."""

    def __init__(self):
        self._ps = None
        try:
            import psutil
            self._ps = psutil.Process()
        except Exception:
            self._ps = None
        self._ncpu = os.cpu_count() or 1
        self._t = time.perf_counter()
        self._c = time.process_time()

    def rss(self):
        """RAM usada pelo programa, em bytes."""
        try:
            if self._ps is not None:
                return int(self._ps.memory_info().rss)
        except Exception:
            pass
        if sys.platform.startswith("linux"):
            try:
                with open("/proc/self/statm") as f:
                    return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE")
            except (OSError, ValueError, IndexError):
                pass
        if IS_WIN:
            try:
                import ctypes
                from ctypes import wintypes

                class PMC(ctypes.Structure):
                    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                                ("PeakWorkingSetSize", ctypes.c_size_t),
                                ("WorkingSetSize", ctypes.c_size_t),
                                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                                ("PagefileUsage", ctypes.c_size_t),
                                ("PeakPagefileUsage", ctypes.c_size_t)]

                k32, psapi = ctypes.windll.kernel32, ctypes.windll.psapi
                k32.GetCurrentProcess.restype = wintypes.HANDLE
                psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC),
                                                       wintypes.DWORD]
                pmc = PMC()
                pmc.cb = ctypes.sizeof(pmc)
                if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                    return int(pmc.WorkingSetSize)
            except Exception:
                pass
        try:
            out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                                 capture_output=True, text=True, timeout=2,
                                 creationflags=NOWIN).stdout
            return int(out.strip()) * 1024
        except Exception:
            return 0

    def sample(self):
        """(CPU em %, RAM em bytes). A CPU é a média desde a medição anterior, em relação à
        capacidade de todos os núcleos (como o Gerenciador de Tarefas)."""
        now, cpu = time.perf_counter(), time.process_time()
        dt = now - self._t
        pct = (cpu - self._c) / dt / self._ncpu * 100.0 if dt > 0 else 0.0
        self._t, self._c = now, cpu
        return max(0.0, min(100.0, pct)), self.rss()


# --------------------------------------------------------------------------- #
#  Servidor local com atualização automática (live reload)
# --------------------------------------------------------------------------- #
LIVE_PATH = "/__kcode_live__"
LIVE_JS = ("<script>(function(){var v=null,f=0;function t(){fetch('/__kcode_live__',"
           "{cache:'no-store'}).then(function(r){return r.text()}).then(function(x){f=0;"
           "if(v===null){v=x}else if(x!==v){location.reload();return}setTimeout(t,350)})"
           ".catch(function(){f++;setTimeout(t,f<10?700:3000)})}t()})();</script>")
MIME_FIX = {".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css",
            ".json": "application/json", ".svg": "image/svg+xml", ".webp": "image/webp",
            ".wasm": "application/wasm", ".ico": "image/x-icon"}


class LiveServer:
    """Serve uma pasta em http://127.0.0.1:<porta>/ e avisa o navegador quando algo muda.

    * O que está aberto no editor é servido direto da memória (mesmo sem salvar).
    * Toda página HTML recebe um pequeno script que recarrega quando `version` muda.
    """

    def __init__(self, root):
        self.root = os.path.abspath(root)
        self.version = 1
        self.live = {}       # arquivo aberto no editor -> bytes (texto atual, salvo ou não)
        self.virtual = {}    # páginas geradas pela IDE que não existem no disco
        self.lock = threading.Lock()
        srv = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"

            def log_message(self, *args):
                pass

            def do_GET(self):
                srv.handle(self, True)

            def do_HEAD(self):
                srv.handle(self, False)

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    # ----- estado (chamado pela interface) ------------------------------------ #
    @staticmethod
    def key(path):
        return os.path.normcase(os.path.abspath(path))

    def covers(self, path):
        a, b = self.key(path), os.path.normcase(self.root)
        return a == b or a.startswith(b.rstrip(os.sep) + os.sep)

    def set_live(self, path, data):
        with self.lock:
            self.live[self.key(path)] = data

    def drop_live(self, path):
        with self.lock:
            self.live.pop(self.key(path), None)

    def clear_live(self):
        with self.lock:
            self.live.clear()

    def set_virtual(self, path, data):
        with self.lock:
            self.virtual[self.key(path)] = data

    def bump(self):
        self.version += 1

    # ----- HTTP ---------------------------------------------------------------- #
    @staticmethod
    def _send(h, code, data, ctype, body=True, location=None):
        h.send_response(code)
        h.send_header("Content-Type", ctype)
        h.send_header("Content-Length", str(len(data)))
        h.send_header("Cache-Control", "no-store, max-age=0")
        if location:
            h.send_header("Location", location)
        h.end_headers()
        if body:
            h.wfile.write(data)

    @staticmethod
    def inject(data):
        tag = LIVE_JS.encode("ascii")
        i = data.lower().rfind(b"</body>")
        return data + tag if i < 0 else data[:i] + tag + data[i:]

    def handle(self, h, body):
        try:
            self._handle(h, body)
        except (ConnectionError, OSError, ValueError):
            pass

    def _lookup(self, path):
        with self.lock:
            data = self.virtual.get(self.key(path))
            if data is None:
                data = self.live.get(self.key(path))
        return data

    def _handle(self, h, body):
        text = "text/plain; charset=utf-8"
        url = urllib.parse.urlsplit(h.path)
        if url.path == LIVE_PATH:
            return self._send(h, 200, str(self.version).encode(), text, body)
        rel = urllib.parse.unquote(url.path).lstrip("/")
        path = os.path.normpath(os.path.join(self.root, rel))
        if not self.covers(path):
            return self._send(h, 403, b"403", text, body)
        data = self._lookup(path)
        if data is None and os.path.isdir(path):
            if not url.path.endswith("/"):
                return self._send(h, 301, b"", text, body, location=url.path + "/")
            for idx in ("index.html", "index.htm"):
                cand = os.path.join(path, idx)
                if self._lookup(cand) is not None or os.path.isfile(cand):
                    path, data = cand, self._lookup(cand)
                    break
            else:
                return self._listing(h, path, rel, body)
        if data is None:
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError:
                return self._send(h, 404, "Arquivo não encontrado".encode("utf-8"), text, body)
        ext = os.path.splitext(path)[1].lower()
        ctype = MIME_FIX.get(ext) or mimetypes.guess_type(path)[0] or "application/octet-stream"
        if ext in (".html", ".htm"):
            data = self.inject(data)
            ctype = "text/html"
        if ctype.startswith("text/") or ctype in ("application/json", "image/svg+xml"):
            try:
                data.decode("utf-8")
                ctype += "; charset=utf-8"
            except UnicodeDecodeError:
                pass
        self._send(h, 200, data, ctype, body)

    def _listing(self, h, path, rel, body):
        names = sorted((n for n in os.listdir(path) if not n.startswith(".")), key=str.lower)
        items = "".join(
            '<li><a href="%s%s">%s</a></li>' % (
                urllib.parse.quote(n), "/" if os.path.isdir(os.path.join(path, n)) else "",
                htmlmod.escape(n)) for n in names)
        page = ("<!DOCTYPE html><meta charset=utf-8><title>/%s</title>"
                "<body style='font:15px sans-serif;padding:20px'><h3>/%s</h3><ul>%s</ul></body>"
                % (htmlmod.escape(rel), htmlmod.escape(rel), items))
        self._send(h, 200, self.inject(page.encode("utf-8")), "text/html; charset=utf-8", body)


# --------------------------------------------------------------------------- #
#  Autocompletar (sugestões de código enquanto digita)
# --------------------------------------------------------------------------- #
AC_MAX = 10
DOC_WORD = re.compile(r"[A-Za-z_$][\w$]{2,}")
AC_WORD = re.compile(r"[A-Za-z_$][\w$]*$")
AC_WORD_DASH = re.compile(r"-{0,2}[A-Za-z][\w-]*$")


def _kw(W):
    out = []
    for key, label in (("control", "palavra-chave"), ("keyword", "palavra-chave"),
                       ("type", "tipo"), ("const", "constante")):
        out += [(w, label) for w in sorted(W[key])]
    return out


def _fn(text, kind="função", cap_kind=None):
    return [(w, cap_kind if (cap_kind and w[0].isupper()) else kind) for w in text.split()]


COMPLETIONS = {
    "c": _kw(W_C) + _fn(
        "printf scanf sprintf snprintf fprintf fscanf sscanf puts gets fgets fputs putchar "
        "getchar malloc calloc realloc free memcpy memmove memset memcmp strlen strcpy strncpy "
        "strcat strncat strcmp strncmp strchr strrchr strstr strtok atoi atof atol strtol "
        "strtod abs labs rand srand time clock exit abort system fopen fclose fread fwrite "
        "fseek ftell rewind feof fflush perror sqrt pow sin cos tan atan atan2 floor ceil fabs "
        "fmod log log10 exp toupper tolower isalpha isdigit isspace isalnum isupper islower "
        "qsort bsearch main assert"),
    "java": _kw(W_JAVA) + _fn(
        "System String Integer Double Boolean Character Long Math Object Exception "
        "RuntimeException ArrayList LinkedList HashMap HashSet TreeMap List Map Set Arrays "
        "Collections Scanner Random Thread StringBuilder Optional LocalDate Override "
        "println print printf out in length size equals toString hashCode charAt substring "
        "indexOf contains isEmpty add get put remove parseInt valueOf nextInt nextLine "
        "nextDouble main args", "método", "classe"),
    "python": _kw(W_PY) + _fn(
        "print input len range enumerate zip map filter sorted reversed sum min max abs round "
        "open isinstance issubclass type super getattr setattr hasattr callable iter next "
        "append extend insert remove pop clear index count sort reverse keys values items get "
        "update join split strip lstrip rstrip replace format lower upper title capitalize "
        "startswith endswith find splitlines encode decode __init__ __str__ __repr__ __len__ "
        "__name__ Exception ValueError TypeError KeyError IndexError OSError"),
    "js": _kw(W_JS) + _fn(
        "console log error warn document window getElementById querySelector "
        "querySelectorAll createElement appendChild removeChild addEventListener "
        "removeEventListener setAttribute getAttribute classList innerHTML innerText "
        "textContent style value setTimeout setInterval clearTimeout clearInterval JSON "
        "stringify parse Math random floor ceil round max min abs Array Object Promise fetch "
        "then catch forEach map filter reduce find includes push pop shift unshift splice "
        "slice join split indexOf length parseInt parseFloat isNaN toString toFixed Date "
        "Number String Boolean Set Map localStorage sessionStorage alert prompt confirm "
        "preventDefault stopPropagation target event keys values entries assign",
        "função", "objeto"),
}
C_DIRECTIVES = "include define undef ifdef ifndef if elif else endif pragma error".split()
C_HEADERS = ("stdio.h stdlib.h string.h math.h time.h ctype.h stdbool.h stdint.h limits.h "
             "float.h assert.h errno.h signal.h stddef.h stdarg.h locale.h setjmp.h unistd.h "
             "pthread.h sys/types.h sys/stat.h").split()
HTML_TAGS = ("a abbr address article aside audio b blockquote body br button canvas caption "
             "code col div em footer form h1 h2 h3 h4 h5 h6 head header hr html i iframe img "
             "input label li link main meta nav ol option p pre script section select small "
             "span strong style sub sup svg table tbody td textarea tfoot th thead title tr u "
             "ul video").split()
HTML_ATTRS = ("class id href src alt title style type name value placeholder rel target width "
              "height action method for onclick onchange oninput onsubmit disabled checked "
              "selected required readonly hidden lang charset content colspan rowspan min max "
              "step maxlength autofocus autocomplete data- role tabindex download").split()
CSS_PROPS = (
    "align-items align-content align-self animation animation-delay animation-duration "
    "background background-color background-image background-position background-repeat "
    "background-size border border-bottom border-collapse border-color border-left "
    "border-radius border-right border-style border-top border-width bottom box-shadow "
    "box-sizing color content cursor display flex flex-basis flex-direction flex-grow "
    "flex-shrink flex-wrap float font font-family font-size font-style font-weight gap grid "
    "grid-column grid-gap grid-row grid-template-areas grid-template-columns "
    "grid-template-rows height justify-content justify-items left letter-spacing "
    "line-height list-style margin margin-bottom margin-left margin-right margin-top "
    "max-height max-width min-height min-width object-fit opacity order outline overflow "
    "overflow-x overflow-y padding padding-bottom padding-left padding-right padding-top "
    "pointer-events position right text-align text-decoration text-overflow text-shadow "
    "text-transform top transform transition user-select vertical-align visibility "
    "white-space width word-break z-index").split()
CSS_VALUES = (
    "absolute auto block bold border-box both center column column-reverse content-box "
    "fixed flex flex-end flex-start grid hidden inherit initial inline inline-block "
    "inline-flex italic left none normal nowrap pointer relative right row row-reverse "
    "scroll solid space-around space-between space-evenly stretch sticky transparent "
    "underline uppercase visible wrap red green blue white black gray orange yellow "
    "purple pink currentColor").split()


# --------------------------------------------------------------------------- #
#  Trechos completos (o que você pode continuar escrevendo)
#   $0 = onde o cursor fica no fim · $1, $2... = pontos para onde Tab pula
#   ${1:nome} = igual a $1, mas mostra "nome" na lista de sugestões
# --------------------------------------------------------------------------- #
SNIP_MIN = 2
SNIP_TOK = re.compile(r"\$\{(\d):([^}]*)\}|\$(\d)")

SNIPPETS = {
    "html": [
        "<!DOCTYPE html>",
        '<html lang="pt-BR">\n    $0\n</html>',
        "<ul>\n    <li>$0</li>\n</ul>",
        "<ol>\n    <li>$0</li>\n</ol>",
        "<li>$0</li>",
        '<div class="$0"></div>',
        '<div id="$0"></div>',
        '<span class="$0"></span>',
        "<p>$0</p>",
        "<h1>$0</h1>", "<h2>$0</h2>", "<h3>$0</h3>",
        "<h4>$0</h4>", "<h5>$0</h5>", "<h6>$0</h6>",
        '<a href="$0"></a>',
        '<a href="$1" target="_blank" rel="noopener">$0</a>',
        '<img src="$1" alt="$0">',
        "<strong>$0</strong>", "<em>$0</em>", "<small>$0</small>", "<b>$0</b>",
        "<i>$0</i>", "<u>$0</u>", "<code>$0</code>", "<pre>$0</pre>",
        "<blockquote>$0</blockquote>",
        "<br>", "<hr>",
        "<header>\n    $0\n</header>", "<nav>\n    $0\n</nav>", "<main>\n    $0\n</main>",
        "<section>\n    $0\n</section>", "<article>\n    $0\n</article>",
        "<aside>\n    $0\n</aside>", "<footer>\n    $0\n</footer>",
        '<form action="$1" method="post">\n    $0\n</form>',
        '<label for="$1">$0</label>',
        '<input type="text" name="$1" placeholder="$0">',
        '<input type="email" name="email" placeholder="seu@email.com">',
        '<input type="password" name="senha" placeholder="Senha">',
        '<input type="number" name="$1" min="0" max="100">',
        '<input type="checkbox" name="$1" id="$0">',
        '<input type="radio" name="$1" value="$0">',
        '<input type="date" name="$0">',
        '<input type="file" name="$0">',
        '<input type="submit" value="Enviar">',
        '<button type="button">$0</button>',
        '<button type="submit">$0</button>',
        '<select name="$1">\n    <option value="$2">$0</option>\n</select>',
        '<option value="$1">$0</option>',
        '<textarea name="$1" rows="4" cols="40">$0</textarea>',
        "<table>\n    <thead>\n        <tr>\n            <th>$0</th>\n        </tr>\n"
        "    </thead>\n    <tbody>\n        <tr>\n            <td></td>\n        </tr>\n"
        "    </tbody>\n</table>",
        "<tr>\n    <td>$0</td>\n</tr>", "<td>$0</td>", "<th>$0</th>",
        '<video src="$0" controls></video>',
        '<audio src="$0" controls></audio>',
        '<iframe src="$0" width="560" height="315"></iframe>',
        '<canvas id="$1" width="400" height="300"></canvas>',
        '<svg width="100" height="100" viewBox="0 0 100 100">\n    $0\n</svg>',
        "<!-- $0 -->",
        "<head>\n    $0\n</head>",
        "<body>\n    $0\n</body>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        '<meta name="description" content="$0">',
        "<title>$0</title>",
        '<link rel="stylesheet" href="style.css">',
        '<link rel="icon" href="favicon.ico">',
        '<link rel="preconnect" href="https://fonts.googleapis.com">',
        '<script src="script.js"></script>',
        "<script>\n    $0\n</script>",
        "<style>\n    $0\n</style>",
        "<noscript>$0</noscript>",
    ],
    "html-attr": [
        'rel="stylesheet"', 'rel="noopener"', 'rel="icon"',
        'target="_blank"', 'target="_self"',
        'type="text"', 'type="email"', 'type="password"', 'type="number"',
        'type="submit"', 'type="button"', 'type="checkbox"', 'type="radio"',
        'type="date"', 'type="file"', 'type="text/css"', 'type="module"',
        'method="post"', 'method="get"', 'charset="UTF-8"', 'lang="pt-BR"',
        'name="viewport" content="width=device-width, initial-scale=1.0"',
        'loading="lazy"', 'autocomplete="off"', 'crossorigin="anonymous"',
        'tabindex="0"', 'role="button"', 'aria-label="$0"', 'data-$1="$0"',
        'onclick="$0"', 'onchange="$0"', 'oninput="$0"', 'onsubmit="$0"',
        'href="#"', 'href="style.css"', 'src="script.js"', 'style="$0"',
        'width="100%"', 'height="100%"', 'colspan="2"', 'rowspan="2"',
        'placeholder="$0"', 'maxlength="$0"', 'min="0"', 'max="100"', 'step="1"',
        "defer", "async",
    ],
    "css": [
        "body {\n    $0\n}",
        "html {\n    $0\n}",
        "* {\n    margin: 0;\n    padding: 0;\n    box-sizing: border-box;\n}",
        ":root {\n    --${1:cor}: $0;\n}",
        ".container {\n    max-width: 1200px;\n    margin: 0 auto;\n    padding: 0 16px;\n}",
        "h1 {\n    $0\n}", "h2 {\n    $0\n}", "h3 {\n    $0\n}", "p {\n    $0\n}",
        "a {\n    $0\n}", "a:hover {\n    $0\n}",
        "img {\n    max-width: 100%;\n    height: auto;\n}",
        "ul {\n    $0\n}", "li {\n    $0\n}",
        "button {\n    $0\n}", "button:hover {\n    $0\n}",
        "input {\n    $0\n}", "form {\n    $0\n}", "label {\n    $0\n}",
        "table {\n    border-collapse: collapse;\n    width: 100%;\n}",
        "header {\n    $0\n}", "nav {\n    $0\n}", "main {\n    $0\n}",
        "section {\n    $0\n}", "footer {\n    $0\n}",
        "div {\n    $0\n}", "span {\n    $0\n}",
        "@media (max-width: 768px) {\n    $0\n}",
        "@media (min-width: 768px) {\n    $0\n}",
        "@keyframes ${1:nome} {\n    from {\n        $0\n    }\n    to {\n    }\n}",
        '@import url("$0");',
        '@font-face {\n    font-family: "${1:Nome}";\n    src: url("$0");\n}',
        '@charset "UTF-8";',
    ],
    "css-in": [
        "display: flex;", "display: grid;", "display: block;", "display: inline-block;",
        "display: none;",
        "flex-direction: column;", "flex-wrap: wrap;", "flex: 1;",
        "justify-content: center;", "justify-content: space-between;",
        "align-items: center;", "gap: 1rem;",
        "grid-template-columns: repeat(3, 1fr);",
        "margin: 0 auto;", "margin: 0;", "padding: 0;", "padding: 1rem;",
        "width: 100%;", "height: 100vh;", "max-width: 100%;", "min-height: 100vh;",
        "color: #333333;", "background-color: #ffffff;",
        "background: linear-gradient(to right, #ffffff, #000000);",
        'background-image: url("$0");', "background-size: cover;",
        "background-position: center;", "background-repeat: no-repeat;",
        "font-family: Arial, sans-serif;", "font-size: 16px;", "font-weight: bold;",
        "line-height: 1.5;", "text-align: center;", "text-decoration: none;",
        "text-transform: uppercase;", "letter-spacing: 1px;",
        "border: 1px solid #cccccc;", "border: none;", "border-radius: 4px;",
        "border-radius: 50%;", "outline: none;",
        "box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);",
        "text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);",
        "position: relative;", "position: absolute;", "position: fixed;",
        "position: sticky;", "top: 0;", "left: 0;", "right: 0;", "bottom: 0;",
        "z-index: 10;", "overflow: hidden;", "overflow-y: auto;", "cursor: pointer;",
        "opacity: 0.8;", "transition: all 0.3s ease;",
        "transform: translateX(-50%);", "transform: rotate(45deg);",
        "transform: scale(1.1);", "animation: ${1:nome} 1s ease infinite;",
        "box-sizing: border-box;", "object-fit: cover;", "list-style: none;",
        "white-space: nowrap;", 'content: "";', "visibility: hidden;",
        "pointer-events: none;", "user-select: none;", "vertical-align: middle;",
        "float: left;", "clear: both;",
    ],
    "js": [
        "console.log($0);", "console.error($0);", "console.warn($0);", "console.table($0);",
        "function ${1:nome}(${2:parametros}) {\n    $0\n}",
        "async function ${1:nome}(${2:parametros}) {\n    $0\n}",
        "const ${1:nome} = ${2:valor};", "let ${1:nome} = ${2:valor};",
        "const ${1:nome} = (${2:parametros}) => {\n    $0\n};",
        "if (${1:condicao}) {\n    $0\n}",
        "if (${1:condicao}) {\n    $1\n} else {\n    $0\n}",
        "for (let i = 0; i < ${1:limite}; i++) {\n    $0\n}",
        "for (const ${1:item} of ${2:lista}) {\n    $0\n}",
        "for (const ${1:chave} in ${2:objeto}) {\n    $0\n}",
        "while (${1:condicao}) {\n    $0\n}",
        "switch (${1:valor}) {\n    case ${2:x}:\n        $0\n        break;\n"
        "    default:\n        break;\n}",
        "try {\n    $0\n} catch (erro) {\n    console.error(erro);\n}",
        "class ${1:Nome} {\n    constructor(${2:parametros}) {\n        $0\n    }\n}",
        'document.getElementById("${1:id}")',
        'document.querySelector("${1:seletor}")',
        'document.querySelectorAll("${1:seletor}")',
        'document.createElement("${1:div}")',
        '.addEventListener("${1:click}", () => {\n    $0\n});',
        ".forEach((${1:item}) => {\n    $0\n});",
        ".map((${1:item}) => $0)", ".filter((${1:item}) => $0)",
        ".reduce((${1:acc}, ${2:item}) => $0, ${3:0})", ".find((${1:item}) => $0)",
        ".then((${1:resposta}) => $0)", ".catch((${1:erro}) => $0)",
        '.classList.add("$0")', '.classList.remove("$0")', '.classList.toggle("$0")',
        ".innerHTML = $0;", ".textContent = $0;",
        '.setAttribute("${1:atributo}", "${2:valor}")',
        "setTimeout(() => {\n    $0\n}, ${1:1000});",
        "setInterval(() => {\n    $0\n}, ${1:1000});",
        'fetch("${1:url}")\n    .then((resposta) => resposta.json())\n'
        "    .then((dados) => {\n        $0\n    })\n"
        "    .catch((erro) => console.error(erro));",
        "JSON.stringify($0)", "JSON.parse($0)",
        "Math.floor(Math.random() * ${1:10})",
        'localStorage.setItem("${1:chave}", ${2:valor});',
        'localStorage.getItem("${1:chave}")',
        'import ${1:modulo} from "${2:caminho}";', "export default $0;",
        'alert("$0");', 'prompt("$0")', 'confirm("$0")',
        "return $0;",
    ],
    "python": [
        "print($0)", 'print(f"$0")',
        "def ${1:nome}(${2:parametros}):\n    $0",
        "def __init__(self${1:, parametros}):\n    $0",
        "class ${1:Nome}:\n    def __init__(self${2:, parametros}):\n        $0",
        "if ${1:condicao}:\n    $0",
        "if ${1:condicao}:\n    $1\nelse:\n    $0",
        'if __name__ == "__main__":\n    $0',
        "elif ${1:condicao}:\n    $0",
        "else:\n    $0",
        "for ${1:i} in range(${2:10}):\n    $0",
        "for ${1:item} in ${2:lista}:\n    $0",
        "for ${1:i}, ${2:item} in enumerate(${3:lista}):\n    $0",
        "while ${1:condicao}:\n    $0",
        "try:\n    $0\nexcept Exception as erro:\n    print(erro)",
        'with open("${1:arquivo.txt}", "${2:r}", encoding="utf-8") as ${3:f}:\n    $0',
        "import ${1:modulo}", "from ${1:modulo} import ${2:nome}",
        'input("$0")', 'int(input("$0"))', 'float(input("$0"))',
        "lambda ${1:x}: $0", 'raise ${1:Exception}("$0")',
        "return $0", "len($0)", "range($0)", "pass", "break", "continue",
    ],
    "c": [
        "#include <stdio.h>", "#include <stdlib.h>", "#include <string.h>",
        "#include <math.h>", "#include <stdbool.h>", "#include <time.h>",
        "#include <ctype.h>", "#define ${1:NOME} ${2:valor}",
        "int main(void) {\n    $0\n    return 0;\n}",
        "int main(int argc, char *argv[]) {\n    $0\n    return 0;\n}",
        'printf("$0\\n");', 'printf("%d\\n", $0);', 'printf("%s\\n", $0);',
        'printf("%.2f\\n", $0);',
        'scanf("%d", &$0);', 'scanf("%f", &$0);', 'scanf("%s", $0);',
        "fgets(buffer, sizeof(buffer), stdin);",
        "for (int i = 0; i < ${1:n}; i++) {\n    $0\n}",
        "while (${1:condicao}) {\n    $0\n}",
        "do {\n    $0\n} while (${1:condicao});",
        "if (${1:condicao}) {\n    $0\n}",
        "if (${1:condicao}) {\n    $1\n} else {\n    $0\n}",
        "switch (${1:valor}) {\n    case ${2:1}:\n        $0\n        break;\n"
        "    default:\n        break;\n}",
        "typedef struct {\n    $1\n} ${2:Nome};",
        "struct ${1:Nome} {\n    $0\n};", "enum ${1:Nome} {\n    $0\n};",
        "int ${1:nome}(${2:parametros}) {\n    $0\n}",
        "void ${1:nome}(${2:parametros}) {\n    $0\n}",
        "int *${1:ptr} = malloc(${2:n} * sizeof(int));", "free($0);",
        'FILE *${1:arq} = fopen("${2:arquivo.txt}", "${3:r}");', "fclose($0);",
        'if (arq == NULL) {\n    perror("Erro ao abrir o arquivo");\n    return 1;\n}',
        "return 0;",
    ],
    "java": [
        "public class ${1:Main} {\n    public static void main(String[] args) {\n"
        "        $0\n    }\n}",
        "public static void main(String[] args) {\n    $0\n}",
        "System.out.println($0);", "System.out.print($0);", 'System.out.printf("$0%n");',
        "Scanner ${1:sc} = new Scanner(System.in);",
        "public class ${1:Nome} {\n    $0\n}", "public interface ${1:Nome} {\n    $0\n}",
        "public ${1:tipo} ${2:nome}(${3:parametros}) {\n    $0\n}",
        "public static ${1:void} ${2:nome}(${3:parametros}) {\n    $0\n}",
        "public ${1:Nome}(${2:parametros}) {\n    $0\n}",
        "private ${1:tipo} ${2:nome};",
        "for (int i = 0; i < ${1:n}; i++) {\n    $0\n}",
        "for (${1:Tipo} ${2:item} : ${3:lista}) {\n    $0\n}",
        "while (${1:condicao}) {\n    $0\n}",
        "do {\n    $0\n} while (${1:condicao});",
        "if (${1:condicao}) {\n    $0\n}",
        "if (${1:condicao}) {\n    $1\n} else {\n    $0\n}",
        "switch (${1:valor}) {\n    case ${2:1}:\n        $0\n        break;\n"
        "    default:\n        break;\n}",
        "try {\n    $0\n} catch (${1:Exception} e) {\n    e.printStackTrace();\n}",
        "ArrayList<${1:String}> ${2:lista} = new ArrayList<>();",
        "HashMap<${1:String}, ${2:Integer}> ${3:mapa} = new HashMap<>();",
        "import java.util.Scanner;", "import java.util.ArrayList;",
        "import java.util.HashMap;", "import java.util.List;", "import java.util.*;",
        "@Override\npublic String toString() {\n    return $0;\n}",
        "return $0;",
    ],
}


def _compile_snips(items):
    out = []
    for raw in items:
        plain = SNIP_TOK.sub("", raw)
        shown = SNIP_TOK.sub(lambda m: m.group(2) or "", raw)
        line = shown.split("\n", 1)[0] + (" …" if "\n" in shown else "")
        if len(line) > 72:
            line = line[:71] + "…"
        out.append((plain.split("\n", 1)[0], line, raw))
    return out


SNIP_DB = {k: _compile_snips(v) for k, v in SNIPPETS.items()}
HTML_SNIP_TAGS = set(re.findall(r"(?m)^<([A-Za-z][A-Za-z0-9]*)", "\n".join(SNIPPETS["html"])))
BOOL_ATTRS = set("disabled checked selected required readonly hidden autofocus download".split())


def _pending_closers(frag):
    """Fechamentos que o auto-pareamento do editor deixou depois do cursor."""
    st = []
    for ch in frag:
        if ch in "([{":
            st.append({"(": ")", "[": "]", "{": "}"}[ch])
        elif ch in ")]}":
            if st and st[-1] == ch:
                st.pop()
        elif ch in "\"'":
            if st and st[-1] == ch:
                st.pop()
            else:
                st.append(ch)
    return "".join(reversed(st))


def _snippet_items(lang, before, ctx):
    """Trechos cujo começo é o que já foi digitado no fim da linha."""
    keys, ci = [lang], False
    if lang == "html":
        ci = True
        if ctx.rfind("<") > ctx.rfind(">"):
            keys.append("html-attr")
    elif lang == "css":
        ci = True
        keys = ["css-in" if ctx.rfind("{") > ctx.rfind("}") else "css"]
    tail = before[-90:]
    n = len(tail)
    cmp_tail = tail.lower() if ci else tail
    found, idx = [], 0
    for key in keys:
        for first, line, raw in SNIP_DB.get(key, ()):
            idx += 1
            cf = first.lower() if ci else first
            for i in range(max(0, n - len(cf) + 1), n - SNIP_MIN + 1):
                if not cf.startswith(cmp_tail[i:]):
                    continue
                if i and (tail[i - 1].isalnum() or tail[i - 1] in "_$-") \
                        and tail[i] not in ".<#@:":
                    continue
                if key == "css-in":          # declaração inteira só no começo da declaração
                    left = tail[:i].strip()
                    if left and left[-1] not in ";{}":
                        continue
                found.append((i - n, idx, line, raw, n - i))
                break
    found.sort()
    return [(line, "trecho", raw, nb) for _a, _b, line, raw, nb in found[:AC_MAX]]


def _word_items(lang, before, ctx, text, force, skip, after):
    if lang == "c":
        m = re.search(r'^\s*#\s*include\s*[<"]([\w./]*)$', before)
        if m:
            pre = m.group(1)
            return pre, [(h, "cabeçalho", h, len(pre)) for h in C_HEADERS
                         if h.startswith(pre) and h != pre][:AC_MAX]
    if skip or lang == "text":
        return "", []
    m = (AC_WORD_DASH if lang in ("css", "html") else AC_WORD).search(before)
    if not m:
        return "", []
    pre = m.group(0)
    if len(pre) < (1 if force else 2):
        return pre, []
    if lang == "html":
        lt = ctx.rfind("<")
        if lt <= ctx.rfind(">"):
            return pre, []
        inner = ctx[lt + 1:]
        if inner.count('"') % 2 or inner.count("'") % 2:        # dentro de um valor
            return pre, []
        if re.match(r"/?[A-Za-z][\w-]*$", inner):
            opening = before[:m.start()].endswith("<")
            cands = [(t, "tag") for t in HTML_TAGS if not (opening and t in HTML_SNIP_TAGS)]
        else:
            eq = after.lstrip().startswith("=")
            cands = [(a, "atributo") if (a in BOOL_ATTRS or a.endswith("-") or eq)
                     else (a, "atributo", f'{a}="$0"', f'{a}=""') for a in HTML_ATTRS]
    elif lang == "css":
        lb = ctx.rfind("{")
        if lb > ctx.rfind("}"):
            seg = ctx[max(ctx.rfind(";"), lb) + 1:]
            if ":" in seg:
                cands = [(v, "valor") for v in CSS_VALUES]
            else:
                blank = not after.strip()
                cands = [(p, "propriedade", f"{p}: $0;", f"{p}: …;") if blank
                         else (p, "propriedade") for p in CSS_PROPS]
        elif before[:m.start()][-1:] in (".", "#", ":", "[", "@", "-"):
            return pre, []
        else:
            cands = [(t, "seletor") for t in HTML_TAGS]
    elif lang == "c" and re.search(r"#\s*$", before[:m.start()]):
        cands = [(d, "diretiva") for d in C_DIRECTIVES]
    else:
        cands = list(COMPLETIONS.get(lang, ()))
        cands += [(w, "no arquivo") for w in set(DOC_WORD.findall(text))]
    low = pre.lower()
    seen, hits = set(), []
    for c in cands:
        w, k = c[0], c[1]
        if w in seen or w == pre or not w.lower().startswith(low):
            continue
        seen.add(w)
        ins = c[2] if len(c) > 2 else w
        disp = c[3] if len(c) > 3 else w
        hits.append((0 if w.startswith(pre) else 1, 1 if k == "no arquivo" else 0,
                     len(w), w.lower(), disp, k, ins))
    hits.sort()
    return pre, [(disp, k, ins, len(pre)) for *_x, disp, k, ins in hits[:AC_MAX]]


def complete(lang, before, ctx, text, force=False, skip=False, after=""):
    """Sugestões para o texto antes do cursor.

    before = linha até o cursor; ctx = trecho anterior maior (HTML/CSS); text = arquivo todo;
    after = resto da linha depois do cursor.
    Devolve (prefixo, [(texto mostrado, tipo, texto inserido, nº de caracteres a substituir)]).
    Trechos completos (ex.: <link rel="stylesheet" href="style.css">) vêm antes das palavras.
    """
    snips = []
    if lang != "text" and (not skip or lang == "html"):
        snips = _snippet_items(lang, before, ctx)
    pre, words = _word_items(lang, before, ctx, text, force, skip, after)
    return pre, (snips + words)[:AC_MAX]


# --------------------------------------------------------------------------- #
#  Aba de editor
# --------------------------------------------------------------------------- #
class EditorTab(tk.Frame):
    PAIRS = {"(": ")", "[": "]", "{": "}"}

    def __init__(self, app, group, path=None, content="", name=None):
        super().__init__(group.host, bg=C["editor"])
        self.app = app
        self.group = group
        self.path = path
        self.untitled = name
        self.modified = False
        self.diag = {}
        self._hl_job = None
        self._ac_box = None
        self._ts = []                 # pontos de parada (Tab) do último trecho inserido
        self._ac_on = False
        self._ac_pre = ""
        self._ac_items = []
        self.lang = lang_for(self.name)
        self.indent = app.indent_for(self.lang)
        self.folds = {}               # blocos recolhíveis: linha inicial -> linha final
        self._fold_tags = []          # um tag (com elide) para cada bloco recolhido agora
        self._fold_labels = {}        # tag -> rótulo "⋯" mostrado no fim da linha recolhida
        self._fold_seq = 0
        self._gutter_hover = False

        f = app.code_font
        self.gutter = tk.Canvas(self, width=56, bg=C["editor"], highlightthickness=0, bd=0)
        self.text = tk.Text(
            self, bg=C["editor"], fg=C["fg_editor"], insertbackground=C["caret"],
            selectbackground=C["sel"], selectforeground=C["fg_bright"],
            inactiveselectbackground=C["sel_off"], font=f, undo=True, maxundo=-1,
            wrap="none", bd=0, highlightthickness=0, padx=8, pady=4, insertwidth=2,
            spacing1=app.settings["line_spacing"], spacing3=app.settings["line_spacing"],
            tabs=(f.measure(" " * app.tab_width()),), relief="flat")
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=self._yscroll, xscrollcommand=self._xscroll)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.gutter.grid(row=0, column=0, sticky="ns")
        self.text.grid(row=0, column=1, sticky="nsew")
        self.vbar.grid(row=0, column=2, sticky="ns")
        self.hbar.grid(row=1, column=1, sticky="ew")

        self.config_tags()
        self.text.tag_lower("curline")
        self.text.tag_raise("sel")

        t = self.text
        t.bind("<<Modified>>", self._on_modified)
        t.bind("<KeyRelease>", self._after_cursor)
        t.bind("<ButtonRelease-1>", self._after_cursor)
        t.bind("<Configure>", lambda e: self.redraw_gutter())
        t.bind("<Tab>", self.on_tab)
        t.bind("<ISO_Left_Tab>", self.on_shift_tab)
        t.bind("<Shift-Tab>", self.on_shift_tab)
        t.bind("<Return>", self.on_return)
        t.bind("<KP_Enter>", self.on_return)
        t.bind("<BackSpace>", self.on_backspace)
        t.bind("<Delete>", self.on_delete)
        t.bind("<Button-2>" if IS_MAC else "<Button-3>", lambda e: self.app.text_menu(self, e))
        t.bind("<KeyPress>", self.on_keypress, add="+")
        t.bind(f"<{MOD}-y>", lambda e: (t.event_generate("<<Redo>>"), "break")[1])
        t.bind(f"<{MOD}-a>", lambda e: (t.tag_add("sel", "1.0", "end-1c"), "break")[1])
        t.bind(f"<{MOD}-MouseWheel>", self._zoom_wheel)
        t.bind(f"<{MOD}-Button-4>", lambda e: self._zoom_wheel(e, 1))
        t.bind(f"<{MOD}-Button-5>", lambda e: self._zoom_wheel(e, -1))
        t.bind("<Escape>", self._on_escape)
        t.bind("<KeyRelease>", self._ac_key, add="+")
        t.bind("<Up>", lambda e: self._ac_move(-1))
        t.bind("<Down>", lambda e: self._ac_move(1))
        t.bind("<Control-space>", lambda e: (self._ac_refresh(True), "break")[1])
        t.bind("<Button-1>", self._ac_hide, add="+")
        t.bind("<Button-1>", self._ts_clear, add="+")
        t.bind("<FocusOut>", self._ac_hide, add="+")
        t.bind("<FocusIn>", lambda e: self.app.focus_group(self.group))
        self.gutter.bind("<MouseWheel>", lambda e: self.text.event_generate(
            "<MouseWheel>", delta=e.delta))
        self.gutter.bind("<Button-1>", self._gutter_click)
        self.gutter.bind("<Enter>", lambda e: self._set_hover(True))
        self.gutter.bind("<Leave>", lambda e: self._set_hover(False))
        app.bind_shortcuts(t, local=True)

        self.set_content(content)

    def config_tags(self):
        """(Re)aplica no texto as cores do tema atual: sintaxe, linha atual, buscas e erros."""
        t = self.text
        for tag, color in SYN.items():
            t.tag_configure(tag, foreground=color)
        t.tag_configure("curline", background=C["curline"])
        t.tag_configure("match", background=C["match"])
        t.tag_configure("errline", background=C["errline"])
        t.tag_configure("warnline", background=C["warnline"])

    def apply_theme(self):
        self.config_tags()
        self.redraw_gutter()

    def apply_font_settings(self):
        """Reaplica fonte, Tab, espaçamento e indentação depois de mudar as configurações."""
        app = self.app
        sp = app.settings["line_spacing"]
        self.text.configure(tabs=(app.code_font.measure(" " * app.tab_width()),),
                            spacing1=sp, spacing3=sp)
        self.indent = app.indent_for(self.lang)
        self.redraw_gutter()
        try:
            self.update_fold_labels()
        except tk.TclError:
            pass

    # ----- propriedades ---------------------------------------------------- #
    @property
    def name(self):
        return os.path.basename(self.path) if self.path else (self.untitled or "sem_titulo.txt")

    def destroy(self):
        if self._hl_job:
            try:
                self.after_cancel(self._hl_job)
            except Exception:
                pass
            self._hl_job = None
        super().destroy()

    def set_lang(self, lang):
        self.lang = lang
        self.indent = self.app.indent_for(lang)
        self.highlight()

    def set_path(self, path):
        self.path = path
        self.set_lang(lang_for(path))

    def set_content(self, s):
        self.text.insert("1.0", s)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.mark_set("insert", "1.0")
        self.highlight()
        self.redraw_gutter()

    def get_content(self):
        return self.text.get("1.0", "end-1c")

    def set_modified(self, flag):
        if self.modified != flag:
            self.modified = flag
            self.app.refresh_tabs()
            self.app.update_title()

    # ----- eventos ---------------------------------------------------------- #
    def _yscroll(self, first, last):
        self.vbar.set(first, last)
        self.redraw_gutter()

    def _xscroll(self, first, last):
        self.hbar.set(first, last)
        self.update_fold_labels()

    def _on_modified(self, _e=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.set_modified(True)
            self.app.live_changed(self)
            if self.diag:
                self.clear_diagnostics()
            if self._hl_job:
                self.after_cancel(self._hl_job)
            self._hl_job = self.after(40, self.highlight)
            self.after_idle(self._after_cursor)

    def _after_cursor(self, _e=None):
        self.update_cursor()
        self.redraw_gutter()

    def _zoom_wheel(self, e, direction=None):
        d = direction if direction is not None else (1 if e.delta > 0 else -1)
        self.app.zoom(d)
        return "break"

    def update_cursor(self):
        self._reveal_cursor()
        t = self.text
        line, col = t.index("insert").split(".")
        t.tag_remove("curline", "1.0", "end")
        if not t.tag_ranges("sel"):
            t.tag_add("curline", f"{line}.0", f"{line}.0 lineend+1c")
        if self.app.active is self:
            self.app.set_cursor_status(int(line), int(col) + 1)

    # ----- realce de sintaxe ------------------------------------------------ #
    def highlight(self):
        self._hl_job = None
        t = self.text
        for tag in SYN:
            t.tag_remove(tag, "1.0", "end")
        tok = LANGS[self.lang]["tok"]
        if tok is None:
            self.update_folds("", [])
            return
        src = t.get("1.0", "end-1c")
        starts = [0] + [m.end() for m in re.finditer("\n", src)]

        def pos(o):
            ln = bisect_right(starts, o) - 1
            return f"{ln + 1}.{o - starts[ln]}"

        ranges = {k: [] for k in SYN}
        toks = list(tok(src))
        for tag, a, b in toks:
            ranges[tag].extend((pos(a), pos(b)))
        for tag, rs in ranges.items():
            for i in range(0, len(rs), 800):
                t.tag_add(tag, *rs[i:i + 800])
        self.update_folds(src, toks)

    # ----- margem ------------------------------------------------------------ #
    def redraw_gutter(self):
        g, t = self.gutter, self.text
        g.delete("all")
        last = int(t.index("end-1c").split(".")[0])
        digits = max(3, len(str(last)))
        w = self.app.code_font.measure("0") * digits + 38
        if int(g.cget("width")) != w:
            g.configure(width=w)
        cur = int(t.index("insert").split(".")[0])
        u = max(3, round(self.app.code_font.metrics("linespace") * 0.2))
        heads = {}                                    # linha -> tag, dos blocos recolhidos
        for tag in self._fold_tags:
            rng = t.tag_ranges(tag)
            if rng:
                heads[int(str(rng[0]).split(".")[0])] = tag
        i = t.index("@0,0")
        prev = 0
        while True:
            ln = int(i.split(".")[0])
            if ln == prev:
                break
            d = t.dlineinfo(i)
            if d is None:
                break
            y = d[1] + d[3] // 2
            color = C["gutter_cur"] if ln == cur else C["gutter"]
            g.create_text(w - 24, y, text=str(ln), anchor="e", fill=color,
                          font=self.app.code_font)
            kind = self.diag.get(ln)
            if kind:
                g.create_oval(7, y - 3, 13, y + 3, outline="",
                              fill=C["err"] if kind == "error" else C["warn"])
            if ln in self.folds and (ln in heads or self._gutter_hover):
                cx = w - 11
                if ln in heads:                       # ▸ recolhido
                    pts = (cx - u // 2 - 1, y - u, cx - u // 2 - 1, y + u, cx + u, y)
                else:                                 # ▾ aberto (só ao passar o mouse)
                    pts = (cx - u, y - u // 2 - 1, cx + u, y - u // 2 - 1, cx, y + u)
                g.create_polygon(*pts, fill=C["gutter_cur"] if ln in heads else C["gutter"],
                                 outline="")
            prev = ln
            i = t.index(f"{i} +1 display lines")      # pula as linhas recolhidas
        self.update_fold_labels()

    # ----- recolher / expandir blocos ----------------------------------------- #
    def _tag_lines(self, tag):
        r = self.text.tag_ranges(tag)
        if not r:
            return None
        return int(str(r[0]).split(".")[0]), int(str(r[1]).split(".")[0])

    def _folded_tag(self, ln):
        for tag in self._fold_tags:
            lines = self._tag_lines(tag)
            if lines and lines[0] == ln:
                return tag
        return None

    def is_folded(self, ln):
        return self._folded_tag(ln) is not None

    def fold_line(self, ln):
        end = self.folds.get(ln)
        if not end or self.is_folded(ln):
            return False
        t = self.text
        a, b = f"{ln}.end", f"{end}.end"
        if not t.compare(a, "<", b):
            return False
        tag = f"fold{self._fold_seq}"
        self._fold_seq += 1
        t.tag_configure(tag, elide=True)              # elide = texto escondido, mas ainda existe
        t.tag_add(tag, a, b)
        self._fold_tags.append(tag)
        ins = t.index("insert")
        if t.compare(ins, ">", a) and t.compare(ins, "<", b):
            t.mark_set("insert", a)
        return True

    def unfold_tag(self, tag):
        if tag in self._fold_tags:
            self._fold_tags.remove(tag)
        try:
            self.text.tag_delete(tag)
        except tk.TclError:
            pass
        lab = self._fold_labels.pop(tag, None)
        if lab is not None:
            lab.destroy()

    def unfold_line(self, ln):
        tag = self._folded_tag(ln)
        if tag:
            self.unfold_tag(tag)
            return True
        return False

    def toggle_fold(self, ln):
        if not self.unfold_line(ln):
            self.fold_line(ln)
        self.text.see("insert")
        self.redraw_gutter()
        self.update_cursor()

    def fold_current(self):
        cur = int(self.text.index("insert").split(".")[0])
        for start in sorted((s for s, e in self.folds.items() if s <= cur <= e), reverse=True):
            if not self.is_folded(start):             # o bloco mais interno que ainda está aberto
                self.fold_line(start)
                break
        self.redraw_gutter()
        self.update_cursor()

    def unfold_current(self):
        cur = int(self.text.index("insert").split(".")[0])
        self.unfold_line(cur)
        self.text.see("insert")
        self.redraw_gutter()

    def fold_all(self):
        for start in sorted(self.folds):
            self.fold_line(start)
        self.redraw_gutter()
        self.update_cursor()

    def unfold_all(self):
        for tag in list(self._fold_tags):
            self.unfold_tag(tag)
        self.text.see("insert")
        self.redraw_gutter()

    def reveal_line(self, ln):
        """Abre os blocos recolhidos que escondem a linha ln (erros, buscas, ir para linha)."""
        hit = False
        for tag in list(self._fold_tags):
            lines = self._tag_lines(tag)
            if lines and lines[0] < ln <= lines[1]:
                self.unfold_tag(tag)
                hit = True
        return hit

    def _reveal_cursor(self):
        if not self._fold_tags:
            return
        t = self.text
        ins = t.index("insert")
        hit = False
        for tag in list(self._fold_tags):
            r = t.tag_ranges(tag)
            if r and t.compare(ins, ">", str(r[0])) and t.compare(ins, "<", str(r[1])):
                self.unfold_tag(tag)                  # o cursor entrou num bloco escondido
                hit = True
        if hit:
            t.see("insert")
            self.redraw_gutter()

    def update_folds(self, src, toks):
        """Recalcula os blocos; os recolhidos que deixaram de existir (texto editado) se abrem."""
        t = self.text
        old = self.folds
        self.folds = compute_folds(self.lang, src, toks) if src else {}
        changed = self.folds != old
        for tag in list(self._fold_tags):
            r = t.tag_ranges(tag)
            ok = False
            if r:
                a, b = str(r[0]), str(r[1])
                la, lb = int(a.split(".")[0]), int(b.split(".")[0])
                ok = (self.folds.get(la) == lb and a == t.index(f"{la}.end")
                      and b == t.index(f"{lb}.end"))
            if not ok:
                self.unfold_tag(tag)
                changed = True
        if changed:
            self.redraw_gutter()

    def update_fold_labels(self):
        """Põe o rótulo "⋯" (clicável) no fim de cada linha recolhida."""
        t = self.text
        for tag in list(self._fold_tags):
            r = t.tag_ranges(tag)
            lab = self._fold_labels.get(tag)
            bb = None
            if r:
                a, b = str(r[0]), str(r[1])
                if int(a.split(".")[1]) > 0:
                    bb = t.bbox(f"{a}-1c")            # último caractere visível da linha
            if not bb:
                if lab is not None:
                    lab.place_forget()
                continue
            if lab is None:
                lab = tk.Label(t, bd=0, padx=4, pady=0, cursor="hand2", font=self.app.code_font,
                               bg=C["sel_off"], fg=C["fg_dim"])
                lab.bind("<Button-1>", lambda e, tg=tag: self._label_click(tg))
                self._fold_labels[tag] = lab
            txt = "⋯"
            if self.lang != "python":                 # mostra o que fechava o bloco: } ou </div>
                lb = int(b.split(".")[0])
                tail = t.get(f"{lb}.0", f"{lb}.end").strip()
                if tail:
                    txt += " " + (tail if len(tail) <= 40 else tail[:40] + "…")
            if lab.cget("text") != txt:
                lab.configure(text=txt)
            lab.place(x=bb[0] + bb[2] + 6, y=bb[1] + 1, height=max(8, bb[3] - 2))

    def _label_click(self, tag):
        lines = self._tag_lines(tag)
        self.unfold_tag(tag)
        if lines:
            self.text.mark_set("insert", f"{lines[0]}.end")
        self.text.focus_set()
        self.redraw_gutter()
        self.update_cursor()
        return "break"

    def _gutter_click(self, e):
        if e.x < int(self.gutter.cget("width")) - 22:     # só vale na setinha
            return None
        t = self.text
        idx = t.index(f"@0,{e.y}")
        d = t.dlineinfo(idx)
        if d is None or not (d[1] <= e.y <= d[1] + d[3]):
            return "break"
        ln = int(idx.split(".")[0])
        if ln in self.folds:
            self.toggle_fold(ln)
        return "break"

    def _set_hover(self, flag):
        if self._gutter_hover != flag:
            self._gutter_hover = flag
            self.redraw_gutter()

    def on_delete(self, _e):
        """Delete no fim de uma linha recolhida apagaria texto invisível: abre o bloco antes."""
        t = self.text
        if self._fold_tags and not t.tag_ranges("sel"):
            ins = t.index("insert")
            for tag in list(self._fold_tags):
                r = t.tag_ranges(tag)
                if r and ins == t.index(str(r[0])):
                    self.unfold_tag(tag)
            self.redraw_gutter()
        return None

    # ----- diagnósticos ------------------------------------------------------ #
    def set_diagnostics(self, diag):
        self.clear_diagnostics()
        self.diag = dict(diag)
        for ln, kind in self.diag.items():
            tag = "errline" if kind == "error" else "warnline"
            self.text.tag_add(tag, f"{ln}.0", f"{ln}.0 lineend+1c")
            if kind == "error":
                self.reveal_line(ln)                  # um erro dentro de um bloco recolhido o abre
        self.redraw_gutter()

    def clear_diagnostics(self):
        self.diag = {}
        self.text.tag_remove("errline", "1.0", "end")
        self.text.tag_remove("warnline", "1.0", "end")
        self.redraw_gutter()

    # ----- autocompletar ------------------------------------------------------ #
    def _on_escape(self, _e):
        if self._ac_on:
            self._ac_hide()
            return "break"
        if self._ts:
            self._ts_clear()
            return "break"
        if self.app.find_visible:
            self.app.hide_find()
        return None

    def _ac_key(self, e):
        ks = e.keysym
        if ks == "space":
            if not (e.state & 0x4):
                # com a lista aberta, o espaço continua o trecho; senão, fecha
                self._ac_refresh() if self._ac_on else self._ac_hide()
            return
        if ks in ("Up", "Down", "Return", "KP_Enter", "Tab", "ISO_Left_Tab", "Escape",
                  "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R", "Meta_L",
                  "Meta_R", "Super_L", "Super_R", "Caps_Lock"):
            return
        if ks in ("Left", "Right", "Home", "End", "Prior", "Next"):
            return self._ac_hide()
        if ks in ("BackSpace", "Delete"):
            if self._ac_on:
                self._ac_refresh()
            return
        ch = e.char
        if ch and ch.isprintable() and not (e.state & 0x4):
            # letras, "<", "-" e "_" abrem a lista; com ela aberta, qualquer sinal continua o trecho
            if ch.isalnum() or ch in "_$-<" or self._ac_on:
                self._ac_refresh()
            else:
                self._ac_hide()
        else:
            self._ac_hide()

    def _ac_refresh(self, force=False):
        t = self.text
        tags = t.tag_names("insert-1c") if t.compare("insert", ">", "1.0") else ()
        skip = "comment" in tags or "string" in tags
        before = t.get("insert linestart", "insert")
        wide = self.lang in ("html", "css")
        ctx = t.get("insert-2000c", "insert") if wide else ""
        text = "" if wide else t.get("1.0", "end-1c")
        after = t.get("insert", "insert lineend")
        pre, items = complete(self.lang, before, ctx, text, force, skip and not force, after)
        if items:
            self._ac_show(pre, items)
        else:
            self._ac_hide()

    def _ac_show(self, pre, items):
        t = self.text
        bb = t.bbox(f"insert-{items[0][3]}c")
        if not bb:
            return self._ac_hide()
        if self._ac_box is None:
            lb = tk.Listbox(self, bg=C["sidebar"], fg=C["fg"], selectbackground=C["menu_active"],
                            selectforeground=C["fg_bright"], activestyle="none", bd=0,
                            relief="flat", highlightthickness=1, highlightbackground=C["popup_border"],
                            highlightcolor=C["popup_border"], exportselection=False, takefocus=0,
                            font=self.app.out_font)
            lb.bind("<Button-1>", self._ac_click)
            self._ac_box = lb
        lb = self._ac_box
        wmax = max(len(it[0]) for it in items)
        kmax = max(len(it[1]) for it in items)
        lb.delete(0, "end")
        for it in items:
            lb.insert("end", f" {it[0].ljust(wmax)}   {it[1].ljust(kmax)} ")
        lb.configure(height=len(items), width=wmax + kmax + 6)
        lb.selection_clear(0, "end")
        lb.selection_set(0)
        lb.activate(0)
        self._ac_pre, self._ac_items, self._ac_on = pre, items, True
        x = t.winfo_x() + bb[0]
        y = t.winfo_y() + bb[1] + bb[3] + 2
        lb.place(x=x, y=y)
        lb.update_idletasks()
        w, h = lb.winfo_reqwidth(), lb.winfo_reqheight()
        if y + h > self.winfo_height() - 4:                  # sem espaço embaixo: abre em cima
            y = max(0, t.winfo_y() + bb[1] - h - 2)
        if x + w > self.winfo_width() - 4:
            x = max(0, self.winfo_width() - w - 4)
        lb.place(x=x, y=y)
        lb.lift()

    def _ac_hide(self, _e=None):
        if self._ac_on:
            self._ac_on = False
            self._ac_box.place_forget()

    def _ac_move(self, d):
        if not self._ac_on:
            return None
        lb = self._ac_box
        sel = lb.curselection()
        new = ((sel[0] if sel else 0) + d) % lb.size()
        lb.selection_clear(0, "end")
        lb.selection_set(new)
        lb.activate(new)
        lb.see(new)
        return "break"

    def _ac_click(self, e):
        lb = self._ac_box
        lb.selection_clear(0, "end")
        lb.selection_set(lb.nearest(e.y))
        self._ac_accept()
        self.text.focus_set()
        return "break"

    def _ac_accept(self):
        if not self._ac_on:
            return None
        sel = self._ac_box.curselection()
        _disp, _kind, ins, nback = self._ac_items[sel[0] if sel else 0]
        t = self.text
        t.edit_separator()
        self._snip_insert(nback, ins)
        t.edit_separator()
        self._ac_hide()
        return "break"

    def _snip_insert(self, nback, raw):
        """Troca os `nback` caracteres digitados pelo texto sugerido e posiciona o cursor."""
        t = self.text
        self._ts_clear()
        frag = t.get(f"insert-{nback}c", "insert") if nback else ""
        exp = _pending_closers(frag)
        if nback:
            t.delete(f"insert-{nback}c", "insert")
        if exp and t.get("insert", f"insert+{len(exp)}c") == exp:
            t.delete("insert", f"insert+{len(exp)}c")      # aspas/parênteses automáticos
        ind = re.match(r"[ \t]*", t.get("insert linestart", "insert")).group(0)
        unit = " " * self.indent
        raw = re.sub(r"(?m)^((?: {4})+)", lambda m: unit * (len(m.group(1)) // 4), raw)
        body, stops, pos = "", [], 0
        for m in SNIP_TOK.finditer(raw):
            body += raw[pos:m.start()].replace("\n", "\n" + ind)
            stops.append((int(m.group(1) or m.group(3)), len(body)))
            pos = m.end()
        body += raw[pos:].replace("\n", "\n" + ind)
        start = t.index("insert")
        t.insert("insert", body)
        order = sorted(stops, key=lambda x: (x[0] == 0, x[0]))
        if order:
            t.mark_set("insert", f"{start}+{order[0][1]}c")
            for k, (_n, off) in enumerate(order[1:]):
                name = f"kts{k}"
                t.mark_set(name, f"{start}+{off}c")
                self._ts.append(name)
        t.see("insert")

    def _ts_jump(self):
        """Tab depois de um trecho: pula para o próximo ponto de parada."""
        t = self.text
        while self._ts:
            name = self._ts.pop(0)
            try:
                idx = t.index(name)
                t.mark_unset(name)
            except tk.TclError:
                continue
            t.mark_set("insert", idx)
            t.see("insert")
            return True
        return False

    def _ts_clear(self, _e=None):
        for name in self._ts:
            try:
                self.text.mark_unset(name)
            except tk.TclError:
                pass
        self._ts = []

    # ----- comportamento de editor ------------------------------------------ #
    def sel_lines(self):
        t = self.text
        if t.tag_ranges("sel"):
            a, b = t.index("sel.first"), t.index("sel.last")
            la, lb = int(a.split(".")[0]), int(b.split(".")[0])
            if b.endswith(".0") and lb > la:
                lb -= 1
            return la, lb, True
        ln = int(t.index("insert").split(".")[0])
        return ln, ln, False

    def on_tab(self, _e):
        if self._ac_on:
            return self._ac_accept()
        if self._ts and not self.text.tag_ranges("sel") and self._ts_jump():
            return "break"
        t = self.text
        la, lb, has_sel = self.sel_lines()
        if self.lang == "html" and not has_sel and \
                t.get("insert linestart", "insert").strip() == "!":
            t.delete("insert linestart", "insert")
            t.insert("insert", HTML_SKELETON[0])
            pos = t.index("insert")
            t.insert("insert", HTML_SKELETON[1])
            t.mark_set("insert", pos)
            return "break"
        unit = " " * self.indent
        if has_sel and la != lb:
            t.edit_separator()
            for ln in range(la, lb + 1):
                t.insert(f"{ln}.0", unit)
            t.tag_add("sel", f"{la}.0", f"{lb}.end")
        else:
            if has_sel:
                t.delete("sel.first", "sel.last")
            col = int(t.index("insert").split(".")[1])
            t.insert("insert", " " * (self.indent - col % self.indent))
        return "break"

    def on_shift_tab(self, _e):
        self._ac_hide()
        t = self.text
        la, lb, has_sel = self.sel_lines()
        t.edit_separator()
        for ln in range(la, lb + 1):
            s = t.get(f"{ln}.0", f"{ln}.end")
            n = len(s) - len(s.lstrip(" "))
            if s.startswith("\t"):
                t.delete(f"{ln}.0", f"{ln}.1")
            elif n:
                t.delete(f"{ln}.0", f"{ln}.{min(self.indent, n)}")
        if has_sel:
            t.tag_add("sel", f"{la}.0", f"{lb}.end")
        return "break"

    def on_return(self, _e):
        if self._ac_on:
            return self._ac_accept()
        t = self.text
        if t.tag_ranges("sel"):
            t.delete("sel.first", "sel.last")
        line = t.get("insert linestart", "insert")
        indent = re.match(r"[ \t]*", line).group(0)
        unit = " " * self.indent
        before = line.rstrip()
        after = t.get("insert", "insert+1c")
        lang = self.lang
        extra, closer = False, None
        if before[-1:] in ("{", "[", "(") and lang not in ("html", "text"):
            extra = True
            closer = {"{": "}", "[": "]", "(": ")"}[before[-1]]
        elif lang == "python" and before.endswith(":") and not before.lstrip().startswith("#"):
            extra = True
        elif lang == "html":
            m = re.search(r"<([A-Za-z][\w:-]*)(?:\s[^<>]*)?>$", before)
            if m and m.group(1).lower() not in VOID_TAGS and not before.endswith("/>"):
                extra = True
        if extra:
            split = (closer and after == closer) or \
                    (lang == "html" and t.get("insert", "insert+2c") == "</")
            if split:
                t.insert("insert", "\n" + indent + unit + "\n" + indent)
                t.mark_set("insert", f"insert-{len(indent) + 1}c")
            else:
                t.insert("insert", "\n" + indent + unit)
        else:
            t.insert("insert", "\n" + indent)
        t.see("insert")
        return "break"

    def on_backspace(self, _e):
        t = self.text
        if t.tag_ranges("sel"):
            return None
        if self._fold_tags:                           # apagaria texto invisível: abre o bloco
            ins = t.index("insert")
            for tag in list(self._fold_tags):
                r = t.tag_ranges(tag)
                if r and ins == t.index(str(r[1])):
                    self.unfold_tag(tag)
            self.redraw_gutter()
        prv, nxt = t.get("insert-1c", "insert"), t.get("insert", "insert+1c")
        if prv and ((prv in self.PAIRS and self.PAIRS[prv] == nxt) or
                    (prv in "\"'" and prv == nxt)):
            t.delete("insert-1c", "insert+1c")
            return "break"
        return None

    def on_keypress(self, e):
        ch = e.char
        t = self.text
        if ch == ">" and self.lang == "html" and not t.tag_ranges("sel"):
            before = t.get("insert linestart", "insert")
            m = re.search(r"<([A-Za-z][\w:-]*)(?:\s[^<>]*)?$", before)
            if m and not before.endswith("/") and m.group(1).lower() not in VOID_TAGS:
                name = m.group(1)
                if t.get("insert", f"insert+{len(name) + 3}c") != f"</{name}>":
                    t.insert("insert", ">" + f"</{name}>")
                    t.mark_set("insert", f"insert-{len(name) + 3}c")
                    return "break"
            return None
        if not ch or ch not in "()[]{}\"'":
            return None
        nxt, prv = t.get("insert", "insert+1c"), t.get("insert-1c", "insert")
        if ch in ")]}":
            if nxt == ch:
                t.mark_set("insert", "insert+1c")
                return "break"
            return None
        if t.tag_ranges("sel"):
            return None
        if ch in "\"'":
            if nxt == ch:
                t.mark_set("insert", "insert+1c")
                return "break"
            if prv == ch or prv.isalnum() or prv == "\\":
                return None
            t.insert("insert", ch + ch)
            t.mark_set("insert", "insert-1c")
            return "break"
        if nxt and (nxt.isalnum() or nxt not in " \t)]};,\n"):
            return None
        t.insert("insert", ch + self.PAIRS[ch])
        t.mark_set("insert", "insert-1c")
        return "break"

    def toggle_comment(self):
        t = self.text
        pre, suf = LANGS[self.lang]["cmt"]
        pre_s, suf_s = pre.strip(), suf.strip()
        la, lb, has_sel = self.sel_lines()
        lines = {ln: t.get(f"{ln}.0", f"{ln}.end") for ln in range(la, lb + 1)}
        nonblank = [s for s in lines.values() if s.strip()]
        if not nonblank:
            return

        def is_commented(s):
            s = s.strip()
            return s.startswith(pre_s) and (not suf_s or s.endswith(suf_s))

        uncomment = all(is_commented(s) for s in nonblank)
        ind = min(len(s) - len(s.lstrip()) for s in nonblank)
        t.edit_separator()
        for ln, s in lines.items():
            if not s.strip():
                continue
            if uncomment:
                m = re.match(r"^(\s*)" + re.escape(pre_s) + r" ?", s)
                new = s[m.end():]
                if suf_s:
                    new = re.sub(r" ?" + re.escape(suf_s) + r"\s*$", "", new)
                t.delete(f"{ln}.{len(m.group(1))}", f"{ln}.end")
                t.insert(f"{ln}.{len(m.group(1))}", new)
            else:
                t.insert(f"{ln}.{ind}", pre)
                if suf:
                    t.insert(f"{ln}.end", suf)
        if has_sel:
            t.tag_add("sel", f"{la}.0", f"{lb}.end")


# --------------------------------------------------------------------------- #
#  Aplicação
# --------------------------------------------------------------------------- #
MAX_GROUPS = 4


# --------------------------------------------------------------------------- #
#  Diálogo "Novo arquivo"
# --------------------------------------------------------------------------- #
class NewFileDialog(tk.Toplevel):
    def __init__(self, app, folder, external=False):
        super().__init__(app.root)
        self.app = app
        self.result = None
        self._chips_lang = "__none__"
        self.title("Novo arquivo")
        self.configure(bg=C["sidebar"])
        self.transient(app.root)
        self.resizable(False, False)
        bg = C["sidebar"]

        tk.Label(self, text="Novo arquivo", bg=bg, fg=C["fg_bright"],
                 font=(app.ui_font_name, 13, "bold")).pack(anchor="w", padx=18, pady=(16, 2))
        if external:
            place = ("Arquivo fora da pasta aberta — no próximo passo você escolhe em qual "
                     "pasta do computador ele será criado.")
        elif folder:
            place = f"Pasta: {folder}"
        else:
            place = "Nenhuma pasta aberta — você escolhe onde salvar ao pressionar Ctrl+S."
        tk.Label(self, text=place, bg=bg, fg=C["fg_dim"], font=app.ui_small, anchor="w",
                 justify="left", wraplength=440).pack(fill="x", padx=18, pady=(0, 12))

        row = tk.Frame(self, bg=bg)
        row.pack(fill="x", padx=18)
        col1 = tk.Frame(row, bg=bg)
        col1.pack(side="left", fill="x", expand=True)
        tk.Label(col1, text="Nome do arquivo", bg=bg, fg=C["fg"], font=app.ui_small).pack(
            anchor="w")
        self.name_var = tk.StringVar()
        self.name_entry = self._entry(col1, self.name_var, 28)
        self.name_entry.pack(fill="x", ipady=3, pady=(3, 0))
        col2 = tk.Frame(row, bg=bg)
        col2.pack(side="left", padx=(10, 0))
        tk.Label(col2, text="Extensão", bg=bg, fg=C["fg"], font=app.ui_small).pack(anchor="w")
        self.ext_var = tk.StringVar()
        self.ext_entry = self._entry(col2, self.ext_var, 9)
        self.ext_entry.pack(ipady=3, pady=(3, 0))

        tk.Label(self, text="Linguagem", bg=bg, fg=C["fg"], font=app.ui_small).pack(
            anchor="w", padx=18, pady=(14, 4))
        grid = tk.Frame(self, bg=bg)
        grid.pack(fill="x", padx=18)
        self.cards = {}
        for i, k in enumerate(list(RUNNABLE) + ["text"]):
            icon_txt, icon_col = LANGS[k]["icon"]
            card = tk.Frame(grid, bg=C["input"], highlightthickness=2,
                            highlightbackground=C["input"], cursor="hand2")
            card.grid(row=i // 4, column=i % 4, padx=3, pady=3, sticky="nsew")
            il = tk.Label(card, text=icon_txt, bg=C["input"], fg=icon_col, width=3,
                          font=(app.ui_font_name, 13, "bold"), cursor="hand2")
            il.pack(pady=(8, 0))
            nl = tk.Label(card, text=LANGS[k]["name"], bg=C["input"], fg=C["fg"],
                          font=app.ui_small, cursor="hand2")
            nl.pack(pady=(0, 8), padx=8)
            for w in (card, il, nl):
                w.bind("<Button-1>", lambda e, k=k: self.pick(k))
            self.cards[k] = card
        for c in range(4):
            grid.grid_columnconfigure(c, weight=1, uniform="cards")

        self.chips = tk.Frame(self, bg=bg)
        self.chips.pack(fill="x", padx=18, pady=(6, 0))
        self.preview = tk.Label(self, text="", bg=bg, fg=C["ok"], font=self.app.ui_small,
                                anchor="w")
        self.preview.pack(fill="x", padx=18, pady=(10, 0))
        self.tpl_var = tk.BooleanVar(value=True)
        tk.Checkbutton(self, text="Começar com um código de exemplo (Olá, mundo)",
                       variable=self.tpl_var, bg=bg, fg=C["fg"], selectcolor=C["input"],
                       activebackground=bg, activeforeground=C["fg_bright"], bd=0,
                       highlightthickness=0, font=app.ui_small).pack(anchor="w", padx=14,
                                                                     pady=(4, 0))
        self.msg = tk.Label(self, text="", bg=bg, fg=C["err"], font=app.ui_small, anchor="w",
                            wraplength=440, justify="left")
        self.msg.pack(fill="x", padx=18, pady=(4, 0))

        btns = tk.Frame(self, bg=bg)
        btns.pack(fill="x", padx=18, pady=(8, 16))
        tk.Button(btns, text="Criar", bg=C["accent"], fg=C["on_accent"],
                  activebackground=C["accent_hover"], activeforeground=C["on_accent"],
                  relief="flat",
                  bd=0, padx=22, pady=6, font=app.ui_small, cursor="hand2",
                  command=self.ok).pack(side="right")
        tk.Button(btns, text="Cancelar", bg=C["input"], fg=C["fg"],
                  activebackground=C["title_hover"],
                  activeforeground=C["fg_bright"], relief="flat", bd=0, padx=16, pady=6,
                  font=app.ui_small, cursor="hand2", command=self.destroy).pack(
            side="right", padx=(0, 8))

        self.name_var.trace_add("write", lambda *_: self.refresh())
        self.ext_var.trace_add("write", lambda *_: self.refresh())
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.destroy())

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        r = app.root
        x = r.winfo_rootx() + max(0, (r.winfo_width() - w) // 2)
        y = r.winfo_rooty() + max(40, (r.winfo_height() - h) // 3)
        self.geometry(f"+{x}+{y}")
        self.name_entry.focus_set()
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass

    def _entry(self, parent, var, width):
        return tk.Entry(parent, textvariable=var, width=width, bg=C["input"], fg=C["fg_bright"],
                        insertbackground=C["fg_bright"], selectbackground=C["sel"],
                                    selectforeground=C["fg_bright"], relief="flat", font=self.app.ui,
                        highlightthickness=1, highlightbackground=C["input"],
                        highlightcolor=C["accent"])

    def _ext(self):
        e = self.ext_var.get().strip()
        return ("." + e.lstrip(".")) if e else ""

    def pick(self, k):
        self.ext_var.set(LANGS[k]["exts"][0])
        self.name_entry.focus_set()

    def refresh(self):
        ext = self._ext()
        lang = EXT2LANG.get(ext.lower()) if ext else None
        for k, card in self.cards.items():
            card.configure(highlightbackground=C["accent"] if k == lang else C["input"])
        if lang != self._chips_lang:
            self._chips_lang = lang
            for w in self.chips.winfo_children():
                w.destroy()
            exts = LANGS[lang]["exts"] if lang else ()
            if len(exts) > 1:
                tk.Label(self.chips, text="Extensões:", bg=C["sidebar"], fg=C["fg_dim"],
                         font=self.app.ui_small).pack(side="left", padx=(0, 6))
                for e in exts:
                    l = tk.Label(self.chips, text=e, bg=C["input"], fg=C["fg"],
                                 font=self.app.ui_small, padx=10, pady=2, cursor="hand2")
                    l.pack(side="left", padx=(0, 4))
                    l.bind("<Button-1>", lambda ev, e=e: self.ext_var.set(e))
        name = self.name_var.get().strip()
        self.msg.configure(text="")
        self.preview.configure(text=f"Será criado:  {name}{ext}" if name and ext else "")

    def ok(self):
        name, ext = self.name_var.get().strip(), self._ext()
        if not ext and "." in name:
            stem, e = os.path.splitext(name)
            if e:
                name, ext = stem, e
        if ext and name.lower().endswith(ext.lower()):
            name = name[:-len(ext)]
        if not name:
            return self.msg.configure(text="Digite o nome do arquivo.")
        if re.search(r'[\\/:*?"<>|]', name):
            return self.msg.configure(text='O nome não pode ter  \\ / : * ? " < > |')
        if not ext or not re.match(r"^\.[A-Za-z0-9]+$", ext):
            return self.msg.configure(
                text="Escolha uma linguagem acima ou digite a extensão (ex.: .py).")
        if lang_for(name + ext) == "java" and not re.match(r"^[A-Za-z_]\w*$", name):
            return self.msg.configure(
                text="Em Java o nome do arquivo é o nome da classe: use letras, números e _ "
                     "(sem espaços ou hífen).")
        self.result = (name, ext, self.tpl_var.get())
        self.destroy()


# --------------------------------------------------------------------------- #
#  Grupo de editor (cada coluna do split)
# --------------------------------------------------------------------------- #
class EditorGroup(tk.Frame):
    def __init__(self, app, parent, side=False):
        super().__init__(parent, bg=C["editor"])
        self.app = app
        self.col = parent              # a coluna (PanedWindow vertical) onde este grupo mora
        self.tabs = []
        self.active = None
        self.welcome = None
        self.side = side

        self.bar = tk.Frame(self, bg=C["tab_off"], height=35)
        self.bar.pack(fill="x", side="top")
        self.bar.pack_propagate(False)
        sp = tk.Label(self.bar, text="◫", bg=C["tab_off"], fg=C["fg_dim"], font=app.ui,
                      padx=10, cursor="hand2")
        sp.pack(side="right", fill="y")
        sp.bind("<Button-1>", lambda e: app.split_editor(group=self))
        sp.bind("<Enter>", lambda e: sp.configure(fg=C["fg_bright"]))
        sp.bind("<Leave>", lambda e: sp.configure(fg=C["fg_dim"]))
        self.tabs_frame = tk.Frame(self.bar, bg=C["tab_off"])
        self.tabs_frame.pack(side="left", fill="both", expand=True)

        self.crumb = tk.Label(self, text="", anchor="w", bg=C["editor"], fg=C["fg_dim"],
                              font=app.ui_small, padx=14, pady=3)
        self.crumb.pack(fill="x", side="top")
        self.host = tk.Frame(self, bg=C["editor"])
        self.host.pack(fill="both", expand=True)
        for w in (self.bar, self.tabs_frame, self.crumb):
            w.bind("<Button-1>", self._focus)
        self.show_welcome()

    def _focus(self, _e=None):
        self.app.focus_group(self)
        if self.active:
            self.active.text.focus_set()

    # ----- guias do grupo ---------------------------------------------------- # #
    def refresh_tabs(self):
        for w in self.tabs_frame.winfo_children():
            w.destroy()
        for ed in self.tabs:
            self._make_tab(ed)

    def _make_tab(self, ed):
        app = self.app
        on = ed is self.active
        focused = app.cur_group is self
        bg = C["editor"] if on else C["tab_off"]
        fg = C["fg_bright"] if on else C["fg_dim"]
        top = (C["accent"] if focused else C["tab_unfocus"]) if on else bg
        f = tk.Frame(self.tabs_frame, bg=bg, cursor="hand2")
        f.pack(side="left", fill="y", padx=(0, 1))
        tk.Frame(f, bg=top, height=2).pack(fill="x", side="top")
        inner = tk.Frame(f, bg=bg)
        inner.pack(fill="both", expand=True)
        icon_txt, icon_col = LANGS[ed.lang]["icon"]
        icon = tk.Label(inner, text=icon_txt, bg=bg, fg=icon_col, font=app.ui_bold)
        icon.pack(side="left", padx=(12, 5))
        name = tk.Label(inner, text=ed.name, bg=bg, fg=fg, font=app.ui_small)
        name.pack(side="left")
        close = tk.Label(inner, text="●" if ed.modified else "✕", bg=bg, fg=fg,
                         font=app.ui_small, padx=9)
        close.pack(side="left")
        menu_btn = "<Button-2>" if IS_MAC else "<Button-3>"
        for w in (f, inner, name, icon):
            w.bind("<ButtonPress-1>", lambda e, t=ed: app.tab_press(t, e))
            w.bind("<B1-Motion>", lambda e, t=ed: app.tab_motion(t, e))
            w.bind("<ButtonRelease-1>", lambda e, t=ed: app.tab_release(t, e))
            w.bind(menu_btn, lambda e, t=ed: app.show_tab_menu(t, e))
            if not IS_MAC:
                w.bind("<Button-2>", lambda e, t=ed: app.close_tab(t))
        close.bind("<Button-1>", lambda e, t=ed: app.close_tab(t))
        close.bind("<Enter>", lambda e: close.configure(text="✕", fg=C["fg_bright"]))
        close.bind("<Leave>", lambda e, t=ed: close.configure(
            text="●" if t.modified else "✕", fg=fg))

    def show(self, ed):
        if self.active is not None and self.active is not ed:
            self.active.pack_forget()
        self.hide_welcome()
        self.active = ed
        ed.pack(fill="both", expand=True)
        self.refresh_tabs()
        self.update_crumb()

    def update_crumb(self):
        ed = self.active
        if not ed:
            self.crumb.configure(text="")
            return
        where = os.path.dirname(ed.path) if ed.path else "arquivo não salvo"
        parts = [p for p in re.split(r"[\\/]", where) if p][-3:]
        self.crumb.configure(text="  ›  ".join(parts + [ed.name]))

    # ----- tela vazia -------------------------------------------------------- #
    def show_welcome(self):
        if self.welcome is not None:
            return
        app = self.app
        w = tk.Frame(self.host, bg=C["editor"])
        box = tk.Frame(w, bg=C["editor"])
        box.place(relx=0.5, rely=0.42, anchor="center")
        if self.side:
            tk.Label(box, text="◫", bg=C["editor"], fg=C["logo"],
                     font=(app.ui_font_name, 40, "bold")).pack()
            tk.Label(box, text="Grupo vazio", bg=C["editor"], fg=C["fg"],
                     font=(app.ui_font_name, 14)).pack(pady=(0, 10))
            tk.Label(box, text="Abra ou crie um arquivo: ele aparece aqui.\n"
                               "No explorador, clique com o botão direito › Abrir ao lado.",
                     bg=C["editor"], fg=C["fg_dim"], font=app.ui_small,
                     justify="center").pack()
        else:
            tk.Label(box, text="</>", bg=C["editor"], fg=C["logo"],
                     font=(app.ui_font_name, 54, "bold")).pack()
            tk.Label(box, text=APP, bg=C["editor"], fg=C["fg"],
                     font=(app.ui_font_name, 18)).pack(pady=(0, 4))
            tk.Label(box, text="C · Java · Python · HTML · CSS · JavaScript", bg=C["editor"],
                     fg=C["fg_dim"], font=app.ui_small).pack(pady=(0, 14))
            for k, v in ((f"{MOD_LABEL}+N", "Novo arquivo"), (f"{MOD_LABEL}+O", "Abrir arquivo"),
                         (f"{MOD_LABEL}+Shift+O", "Abrir pasta"),
                         (f"{MOD_LABEL}+\\", "Dividir editor"), ("F5", "Executar")):
                r = tk.Frame(box, bg=C["editor"])
                r.pack(fill="x", pady=2)
                tk.Label(r, text=v, bg=C["editor"], fg=C["fg_dim"], font=app.ui, width=20,
                         anchor="e").pack(side="left")
                tk.Label(r, text=k, bg=C["editor"], fg=C["fg"], font=app.ui, width=18,
                         anchor="w", padx=12).pack(side="left")
        w.pack(fill="both", expand=True)
        w.bind("<Button-1>", self._focus)
        self.welcome = w

    def hide_welcome(self):
        if self.welcome is not None:
            self.welcome.destroy()
            self.welcome = None


class App:
    def __init__(self, root, argv):
        self.root = root
        root.title(APP)
        root.geometry("1240x790")
        root.minsize(800, 520)
        name = read_config().get("theme")
        self.theme_name = name if name in THEMES else DEFAULT_THEME
        set_palette(self.theme_name)
        self.theme_var = tk.StringVar(value=self.theme_name)
        root.configure(bg=C["editor"])
        self.icons = []
        self.set_app_icon()

        self.settings = load_settings()
        s = self.settings
        self.ui_font_name, self.code_font_name = self.pick_fonts()
        self.ui = tkfont.Font(family=self.ui_font_name, size=s["ui_size"] + 1)
        self.ui_small = tkfont.Font(family=self.ui_font_name, size=s["ui_size"])
        self.ui_bold = tkfont.Font(family=self.ui_font_name, size=s["ui_size"], weight="bold")
        self.code_font = tkfont.Font(family=self.code_font_name, size=s["code_size"])
        self.out_font = tkfont.Font(family=self.code_font_name, size=s["out_size"])
        self._settings_win = None
        self._settings_refresh = None
        self._mono_cache = None

        self.groups = []
        self.cur_group = None
        self.folder = None
        self.node_paths = {}
        self.dummies = set()
        self.externals = []           # arquivos fora da pasta aberta (grupo EXTERNOS)
        self.ext_keep = set()         # os que ficam salvos entre uma sessão e outra
        self.ext_node = None
        self.ext_items = set()
        self.ext_open = True
        self.last_ext_dir = None
        self._drag = None
        self._tdrag = None            # arrasto de aba em andamento
        self._dz = None               # molduras que mostram onde a aba vai cair
        self.live = {}                # pasta -> LiveServer
        self.live_on = tk.BooleanVar(value=self.settings["live_on"])
        self.live_pending = set()
        self.live_job = None
        self.load_config()
        self.untitled_count = 0
        self.find_visible = False
        self.sidebar_visible = True
        self.panel_visible = True
        self.panel_name = "output"

        self.tools = None
        self.std = tk.StringVar(value=self.settings["c_std"])
        self.warn_var = tk.BooleanVar(value=self.settings["warn"])
        self.opt_var = tk.BooleanVar(value=self.settings["opt"])
        self.noconsole_var = tk.BooleanVar(value=self.settings["noconsole"])
        for v in (self.live_on, self.std, self.warn_var, self.opt_var, self.noconsole_var):
            v.trace_add("write", lambda *a: self.save_settings())

        self.q = queue.Queue()
        self.run_id = 0
        self.compiling = False
        self.running = False
        self.proc = None
        self.plan = None
        self.pending_run = False
        self.compiled_editor = None
        self.run_cwd = None
        self.run_output = ""
        self.start_time = 0.0
        self.stopped = False
        self.problems = []
        self.build_dir = tempfile.mkdtemp(prefix="kcode_")

        self.setup_style()
        self.build_menubar()
        self.build_statusbar()
        self.build_body()
        self.build_findbar()
        self.update_tool_status()

        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.bind_shortcuts(root)
        self.poll()
        threading.Thread(target=lambda: self.q.put(("tools", 0, detect_tools())),
                         daemon=True).start()

        opened = False
        for a in argv:
            if os.path.isdir(a):
                self.set_folder(os.path.abspath(a))
            elif os.path.isfile(a):
                self.open_file(os.path.abspath(a))
                opened = True
        self.out("Bem-vindo ao K-Code. Detectando compiladores e interpretadores…\n", "dim")

    @staticmethod
    def _pick_font(candidates, fallback):
        available = set(tkfont.families())
        for name in candidates:
            if name in available:
                return name
        return fallback

    # ----- estilo ------------------------------------------------------------ #
    def setup_style(self):
        st = ttk.Style()
        st.theme_use("clam")
        for orient, side in (("Vertical", "ns"), ("Horizontal", "ew")):
            name = f"{orient}.TScrollbar"
            st.configure(name, background=C["scroll"], troughcolor=C["editor"],
                         bordercolor=C["editor"], lightcolor=C["scroll"], darkcolor=C["scroll"],
                         relief="flat", gripcount=0, width=12)
            st.map(name, background=[("active", C["scroll_hover"]), ("pressed", C["scroll_press"])])
            st.layout(name, [(f"{orient}.Scrollbar.trough", {
                "sticky": side, "children": [(f"{orient}.Scrollbar.thumb",
                                              {"expand": "1", "sticky": "nswe"})]})])
        st.configure("Treeview", background=C["sidebar"], fieldbackground=C["sidebar"],
                     foreground=C["fg"], borderwidth=0,
                     rowheight=max(22, self.ui.metrics("linespace") + 6), font=self.ui)
        st.map("Treeview", background=[("selected", C["tree_sel"])],
               foreground=[("selected", C["fg_bright"])])
        st.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        st.configure("TCombobox", fieldbackground=C["input"], background=C["hover"],
                     foreground=C["fg_bright"], arrowcolor=C["fg"], bordercolor=C["popup_border"],
                     lightcolor=C["input"], darkcolor=C["input"], insertcolor=C["fg_bright"],
                     selectbackground=C["input"], selectforeground=C["fg_bright"], padding=3)
        st.map("TCombobox", fieldbackground=[("readonly", C["input"])],
               foreground=[("readonly", C["fg_bright"])],
               selectbackground=[("readonly", C["input"])],
               selectforeground=[("readonly", C["fg_bright"])],
               background=[("active", C["tree_sel"])], arrowcolor=[("active", C["fg_bright"])])
        for opt, key in (("background", "input"), ("foreground", "fg_bright"),
                         ("selectBackground", "accent"), ("selectForeground", "on_accent")):
            self.root.option_add(f"*TCombobox*Listbox.{opt}", str(C[key]))
        self.root.option_add("*TCombobox*Listbox.font", str(self.ui))

    # ----- menus ------------------------------------------------------------- #
    def _menu(self, parent):
        return tk.Menu(parent, tearoff=0, bg=C["menu_bg"], fg=C["fg"], bd=0,
                       activebackground=C["menu_active"], activeforeground=C["fg_bright"],
                       font=self.ui_small, relief="flat", selectcolor=C["fg"])

    def build_menubar(self):
        bar = tk.Frame(self.root, bg=C["titlebar"], height=30)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)
        tk.Label(bar, text="</>", bg=C["titlebar"], fg=C["info"],
                 font=(self.ui_font_name, 10, "bold"), padx=10).pack(side="left")

        def menu(label):
            mb = tk.Menubutton(bar, text=label, bg=C["titlebar"], fg=C["fg"], bd=0,
                               activebackground=C["title_hover"], activeforeground=C["fg_bright"],
                               font=self.ui_small, padx=9, pady=4)
            m = self._menu(mb)
            mb.configure(menu=m)
            mb.pack(side="left")
            return m

        def acc(key):
            return f"{MOD_LABEL}+{key}"

        m = menu("Arquivo")
        m.add_command(label="Novo arquivo...", accelerator=acc("N"), command=self.new_file)
        m.add_command(label="Novo arquivo fora da pasta...", accelerator=acc("Shift+N"),
                      command=self.new_file_external)
        exm = self._menu(m)
        for k in RUNNABLE:
            sub = self._menu(exm)
            for title, code in EXAMPLES[k]:
                sub.add_command(label=title, command=lambda k=k, c=code: self.new_untitled(k, c))
            exm.add_cascade(label=LANGS[k]["name"], menu=sub)
        m.add_cascade(label="Exemplos", menu=exm)
        m.add_separator()
        m.add_command(label="Abrir arquivo...", accelerator=acc("O"), command=self.open_dialog)
        m.add_command(label="Abrir pasta...", accelerator=acc("Shift+O"),
                      command=self.open_folder_dialog)
        m.add_separator()
        m.add_command(label="Salvar", accelerator=acc("S"), command=self.save)
        m.add_command(label="Salvar como...", accelerator=acc("Shift+S"),
                      command=lambda: self.save(as_new=True))
        m.add_separator()
        m.add_command(label="Configurações...", accelerator=acc(","), command=self.open_settings)
        m.add_separator()
        m.add_command(label="Fechar aba", accelerator=acc("W"), command=self.close_active)
        m.add_command(label="Sair", accelerator=acc("Q"), command=self.quit)

        m = menu("Editar")
        m.add_command(label="Desfazer", accelerator=acc("Z"), command=lambda: self.ev("<<Undo>>"))
        m.add_command(label="Refazer", accelerator=acc("Y"), command=lambda: self.ev("<<Redo>>"))
        m.add_separator()
        m.add_command(label="Recortar", accelerator=acc("X"), command=lambda: self.ev("<<Cut>>"))
        m.add_command(label="Copiar", accelerator=acc("C"), command=lambda: self.ev("<<Copy>>"))
        m.add_command(label="Colar", accelerator=acc("V"), command=lambda: self.ev("<<Paste>>"))
        m.add_command(label="Selecionar tudo", accelerator=acc("A"), command=self.select_all)
        m.add_separator()
        m.add_command(label="Localizar", accelerator=acc("F"), command=lambda: self.show_find(False))
        m.add_command(label="Substituir", accelerator=acc("H"), command=lambda: self.show_find(True))
        m.add_command(label="Ir para linha...", accelerator=acc("G"), command=self.goto_line_dialog)
        m.add_command(label="Alternar comentário", accelerator=acc("/"), command=self.toggle_comment)
        m.add_separator()
        m.add_command(label="Recolher bloco", accelerator=acc("Shift+["), command=self.fold_current)
        m.add_command(label="Expandir bloco", accelerator=acc("Shift+]"),
                      command=self.unfold_current)
        m.add_command(label="Recolher todos os blocos", command=self.fold_all)
        m.add_command(label="Expandir todos os blocos", command=self.unfold_all)

        m = menu("Exibir")
        m.add_cascade(label="Tema de cores", menu=self.make_theme_menu(m))
        m.add_separator()
        m.add_command(label="Explorador", accelerator=acc("B"), command=self.toggle_sidebar)
        m.add_command(label="Painel (saída/problemas)", accelerator=acc("J"),
                      command=self.toggle_panel)
        m.add_separator()
        m.add_command(label="Dividir editor", accelerator=acc("\\"), command=self.split_editor)
        m.add_command(label="Focar grupo 1 / 2 / 3", accelerator=acc("1 / 2 / 3"),
                      command=lambda: self.focus_group_n(0))
        m.add_separator()
        m.add_command(label="Aumentar fonte", accelerator=acc("+"), command=lambda: self.zoom(1))
        m.add_command(label="Diminuir fonte", accelerator=acc("-"), command=lambda: self.zoom(-1))
        m.add_command(label="Redefinir fonte", accelerator=acc("0"), command=lambda: self.zoom(0))

        m = menu("Executar")
        m.add_command(label="Executar", accelerator="F5", command=lambda: self.build(True))
        m.add_command(label="Compilar / verificar sintaxe", accelerator="F6",
                      command=lambda: self.build(False))
        m.add_command(label="Gerar .exe (Python)", accelerator="F8", command=self.build_exe)
        m.add_command(label="Parar", accelerator="Shift+F5", command=self.stop)
        m.add_command(label="Abrir no navegador", accelerator="F7", command=self.open_in_browser)
        m.add_checkbutton(label="Atualizar o navegador sozinho ao editar", variable=self.live_on,
                          command=self.live_toggle, selectcolor=C["fg"])
        m.add_separator()
        std = self._menu(m)
        for s in ("c99", "c11", "c17", "gnu11", "gnu17"):
            std.add_radiobutton(label=s, value=s, variable=self.std,
                                command=self.update_tool_status)
        m.add_cascade(label="Padrão da linguagem C", menu=std)
        m.add_checkbutton(label="Mostrar avisos (C: -Wall -Wextra, Java: -Xlint)",
                          variable=self.warn_var, selectcolor=C["fg"])
        m.add_checkbutton(label="Otimizar C (-O2)", variable=self.opt_var, selectcolor=C["fg"])
        m.add_checkbutton(label="Gerar .exe sem janela de console (programas com janela, ex.: Tkinter)",
                          variable=self.noconsole_var, selectcolor=C["fg"])
        m.add_separator()
        m.add_command(label="Escolher compilador/interpretador...", command=self.choose_tool)

        m = menu("Ajuda")
        m.add_command(label="Atalhos de teclado", command=self.show_shortcuts)
        m.add_command(label="Instalar compiladores e interpretadores",
                      command=self.show_install_help)
        m.add_command(label="Ferramentas detectadas", command=self.show_tools)
        m.add_command(label="Sobre", command=self.show_about)

        self.btn_stop = tk.Label(bar, text="■", bg=C["titlebar"], fg=C["fg_dim"],
                                 font=self.ui, padx=10, cursor="hand2")
        self.btn_stop.pack(side="right")
        self.btn_stop.bind("<Button-1>", lambda e: self.stop())
        self.btn_run = tk.Label(bar, text="▶  Executar", bg=C["titlebar"], fg=C["ok"],
                                font=self.ui_small, padx=10, cursor="hand2")
        self.btn_run.pack(side="right")
        self.btn_run.bind("<Button-1>", lambda e: self.build(True))
        for b in (self.btn_run, self.btn_stop):
            b.bind("<Enter>", lambda e, w=b: w.configure(bg=C["title_hover"]))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=C["titlebar"]))

        self.title_lbl = tk.Label(bar, text=APP, bg=C["titlebar"], fg=C["fg_dim"],
                                  font=self.ui_small)
        self.title_lbl.place(relx=0.5, rely=0.5, anchor="center")

    # ----- barra de status --------------------------------------------------- #
    def build_statusbar(self):
        sb = tk.Frame(self.root, bg=C["accent"], height=24)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)

        def lab(text="", side="left", cmd=None):
            l = tk.Label(sb, text=text, bg=C["accent"], fg=C["on_accent"], font=self.ui_small,
                         padx=9)
            l.pack(side=side, fill="y")
            if cmd:
                l.configure(cursor="hand2")
                l.bind("<Button-1>", lambda e: cmd())
                l.bind("<Enter>", lambda e: l.configure(bg=C["accent_hover"]))
                l.bind("<Leave>", lambda e: l.configure(bg=C["accent"]))
            return l

        self.st_state = lab("⏳ Iniciando…")
        self.st_cc = lab("", cmd=self.choose_tool)
        self.st_theme = lab("◐ Tema", "right", cmd=self.popup_theme_menu)
        self.st_lang = lab("", "right", cmd=self.popup_lang_menu)
        self.st_enc = lab("UTF-8", "right")
        self.st_indent = lab("Espaços: 4", "right")
        self.st_cursor = lab("Ln 1, Col 1", "right")

        self.lang_menu = self._menu(self.root)
        for k, v in LANGS.items():
            self.lang_menu.add_command(label=v["name"], command=lambda k=k: self.set_lang(k))

    def make_theme_menu(self, parent):
        m = self._menu(parent)
        for name in THEMES:
            m.add_radiobutton(label=name, value=name, variable=self.theme_var,
                              command=lambda n=name: self.set_theme(n))
        return m

    def popup_theme_menu(self):
        m = self.make_theme_menu(self.root)
        x, y = self.st_theme.winfo_rootx(), self.st_theme.winfo_rooty()
        m.tk_popup(x, y - m.winfo_reqheight())

    def retint(self, w):
        """Repinta w e todos os filhos com as cores do tema atual."""
        roles = w.__dict__.get("_kc_roles")
        if roles:
            for opt, key in list(roles.items()):
                try:
                    w.configure(**{opt: C[key]})
                except tk.TclError:
                    pass
        for ch in w.winfo_children():
            self.retint(ch)

    def set_theme(self, name):
        if name not in THEMES:
            return
        self.theme_name = name
        self.theme_var.set(name)
        set_palette(name)
        self.setup_style()
        self.retint(self.root)
        for ed in self.tabs:
            ed.apply_theme()
        self.tree.tag_configure("dir", foreground=C["fg"])
        self.tree.tag_configure("ext_hdr", foreground=C["fg_dim"])
        self.prob_tree.tag_configure("error", foreground=C["err"])
        self.prob_tree.tag_configure("warning", foreground=C["warn"])
        self.prob_tree.tag_configure("note", foreground=C["fg_dim"])
        for tag, color in (("err", C["err"]), ("warn", C["warn"]), ("ok", C["ok"]),
                           ("info", C["info"]), ("dim", C["fg_dim"]),
                           ("input", C["input_txt"])):
            self.out_text.tag_configure(tag, foreground=color)
        self.show_panel(self.panel_name, ensure_visible=False)
        self.set_problems(self.problems)
        self.ic_explorer.configure(fg=C["fg_bright"] if self.sidebar_visible else C["fg_dim"])
        self.refresh_tabs()
        self.update_title()
        self.save_config()
        self.set_status(f"◐ Tema: {name}")

    def popup_lang_menu(self):
        if not self.active:
            return
        x, y = self.st_lang.winfo_rootx(), self.st_lang.winfo_rooty()
        self.lang_menu.tk_popup(x, y - self.lang_menu.winfo_reqheight())

    def set_lang(self, k):
        if self.active:
            self.active.set_lang(k)
            self.refresh_tabs()
            self.update_title()
            self.update_tool_status()

    def set_status(self, text):
        self.st_state.configure(text=text)

    def set_cursor_status(self, ln, col):
        self.st_cursor.configure(text=f"Ln {ln}, Col {col}")

    def update_tool_status(self):
        ed = self.active
        T = self.tools or {}
        if not ed:
            self.st_cc.configure(text="")
            self.st_lang.configure(text="")
            return
        lang = ed.lang
        self.st_lang.configure(text=LANGS[lang]["name"])
        self.st_indent.configure(text=f"Espaços: {ed.indent}")
        if self.tools is None:
            txt = "detectando…"
        elif lang == "c":
            txt = f"{os.path.basename(T['cc'])} · {self.std.get()}" if T.get("cc") \
                else "⚠ compilador C não encontrado"
        elif lang == "java":
            txt = "javac · java" if T.get("javac") else "⚠ JDK não encontrado"
        elif lang == "python":
            txt = os.path.basename(T["python"]) if T.get("python") else "⚠ Python não encontrado"
        elif lang == "js":
            txt = "node" if T.get("node") else "navegador (Node não encontrado)"
        elif lang in ("html", "css"):
            txt = "navegador"
        else:
            txt = ""
        self.st_cc.configure(text=txt)

    # ----- corpo ------------------------------------------------------------ #
    def build_body(self):
        body = tk.Frame(self.root, bg=C["editor"])
        body.pack(fill="both", expand=True)

        act = tk.Frame(body, bg=C["activity"], width=48)
        act.pack(side="left", fill="y")
        act.pack_propagate(False)

        def icon(text, cmd):
            l = tk.Label(act, text=text, bg=C["activity"], fg=C["fg_dim"], width=3,
                         font=(self.ui_font_name, 16), cursor="hand2", pady=8)
            l.pack(side="top")
            l.on = False
            l.bind("<Button-1>", lambda e: cmd())
            l.bind("<Enter>", lambda e: l.configure(fg=C["fg_bright"]))
            l.bind("<Leave>", lambda e: l.configure(fg=C["fg_bright"] if l.on else C["fg_dim"]))
            return l

        self.ic_explorer = icon("☰", self.toggle_sidebar)
        self.ic_explorer.on = True
        self.ic_explorer.configure(fg=C["fg_bright"])
        icon("▶", lambda: self.build(True))
        icon("⚠", lambda: self.show_panel("problems"))
        gear = icon("⚙", self.open_settings)          # engrenagem no canto de baixo
        gear.pack_forget()
        gear.pack(side="bottom")

        self.hpane = tk.PanedWindow(body, orient="horizontal", bg=C["border"], bd=0,
                                    sashwidth=2, sashrelief="flat", opaqueresize=True)
        self.hpane.pack(side="left", fill="both", expand=True)

        self.build_sidebar()
        self.main = tk.Frame(self.hpane, bg=C["editor"])
        self.hpane.add(self.sidebar, width=250, minsize=140, stretch="never")
        self.hpane.add(self.main, minsize=320, stretch="always")

        self.vpane = tk.PanedWindow(self.main, orient="vertical", bg=C["border"], bd=0,
                                    sashwidth=2, sashrelief="flat", opaqueresize=True)
        self.vpane.pack(fill="both", expand=True)

        self.editor_col = tk.Frame(self.vpane, bg=C["editor"])
        self.editor_pane = tk.PanedWindow(self.editor_col, orient="horizontal", bg=C["border"],
                                          bd=0, sashwidth=3, sashrelief="flat",
                                          opaqueresize=True)
        self.editor_pane.pack(fill="both", expand=True)
        col0 = self._make_col()
        self.editor_pane.add(col0, minsize=240, stretch="always")
        g0 = EditorGroup(self, col0)
        col0.add(g0, minsize=90, stretch="always")
        self.groups.append(g0)
        self.cur_group = g0

        self.build_panel()
        self.vpane.add(self.editor_col, minsize=140, stretch="always")
        self.vpane.add(self.panel, height=230, minsize=70, stretch="never")

    # ----- explorador -------------------------------------------------------- #
    def build_sidebar(self):
        sb = tk.Frame(self.hpane, bg=C["sidebar"])
        self.sidebar = sb
        tk.Label(sb, text="EXPLORADOR", bg=C["sidebar"], fg=C["fg"], font=self.ui_small,
                 anchor="w", padx=20, pady=9).pack(fill="x")
        self.folder_lbl = tk.Label(sb, text="", bg=C["sidebar"], fg=C["fg_bright"],
                                   font=self.ui_bold, anchor="w", padx=8, pady=3)
        self.tree_wrap = tk.Frame(sb, bg=C["sidebar"])
        self.tree = ttk.Treeview(self.tree_wrap, show="tree", selectmode="browse")
        vs = ttk.Scrollbar(self.tree_wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        for k, v in LANGS.items():
            self.tree.tag_configure("lang_" + k, foreground=v["icon"][1])
        self.tree.tag_configure("dir", foreground=C["fg"])
        self.tree.bind("<<TreeviewOpen>>", self.on_tree_open)
        self.tree.bind("<Double-1>", self.on_tree_double)
        self.tree.bind("<Button-3>", self.on_tree_menu)
        if IS_MAC:
            self.tree.bind("<Button-2>", self.on_tree_menu)
        self.tree.tag_configure("ext_hdr", foreground=C["fg_dim"])
        self.tree.bind("<Delete>", self.tree_delete)
        if IS_MAC:
            self.tree.bind("<BackSpace>", self.tree_delete)
        self.tree.bind("<ButtonPress-1>", self.on_drag_start, add="+")
        self.tree.bind("<B1-Motion>", self.on_drag_motion, add="+")
        self.tree.bind("<ButtonRelease-1>", self.on_drag_end, add="+")

        self.empty_frame = tk.Frame(sb, bg=C["sidebar"])
        tk.Label(self.empty_frame, text="Nenhuma pasta aberta.", bg=C["sidebar"], fg=C["fg"],
                 font=self.ui_small, anchor="w", padx=20).pack(fill="x", pady=(6, 8))
        b = tk.Label(self.empty_frame, text="Abrir pasta", bg=C["accent"], fg=C["on_accent"],
                     font=self.ui_small, pady=6, cursor="hand2")
        b.pack(fill="x", padx=20)
        b.bind("<Button-1>", lambda e: self.open_folder_dialog())

        self.tree_menu = self._menu(self.root)
        self.rebuild_tree()

    def set_folder(self, path, keep=()):
        self.folder = path
        self.rebuild_tree(keep)

    def populate(self, node, path, opened=()):
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
        except OSError:
            return
        for e in entries:
            if e.name.startswith(".") or e.name in ("__pycache__", "node_modules"):
                continue
            tag = "dir" if e.is_dir() else "lang_" + lang_for(e.name)
            iid = self.tree.insert(node, "end", text=" " + e.name, tags=(tag,))
            self.node_paths[iid] = e.path
            if e.is_dir():
                if e.path in opened:
                    self.populate(iid, e.path, opened)
                    self.tree.item(iid, open=True)
                else:
                    self.dummies.add(self.tree.insert(iid, "end", text="…"))

    def on_tree_open(self, _e):
        node = self.tree.focus()
        kids = self.tree.get_children(node)
        if len(kids) == 1 and kids[0] in self.dummies:
            self.dummies.discard(kids[0])
            self.tree.delete(kids[0])
            self.populate(node, self.node_paths[node])

    def on_tree_double(self, _e):
        iid = self.tree.focus()
        if self.node_kind(iid) in ("file", "ext"):
            self.open_file(self.node_paths[iid])

    def node_kind(self, iid):
        """'file' | 'dir' | 'ext' (arquivo externo) | 'ext_hdr' (grupo EXTERNOS) | None."""
        if not iid:
            return None
        if iid == self.ext_node:
            return "ext_hdr"
        p = self.node_paths.get(iid)
        if not p:
            return None
        if iid in self.ext_items:
            return "ext"
        return "dir" if os.path.isdir(p) else "file"

    def on_tree_menu(self, e):
        row = self.tree.identify_row(e.y)
        if row:
            self.tree.selection_set(row)
            self.tree.focus(row)
        kind = self.node_kind(row)
        m = self.tree_menu
        m.delete(0, "end")
        if kind in ("file", "ext"):
            m.add_command(label="Abrir", command=lambda: self.on_tree_double(None))
            m.add_command(label="Abrir ao lado", command=self.tree_open_side)
            m.add_separator()
        if kind in ("ext", "ext_hdr"):
            m.add_command(label="Novo arquivo fora da pasta...", command=self.tree_new_file)
            m.add_command(label="Adicionar arquivo existente...",
                          command=self.add_external_dialog)
        else:
            if self.folder:
                m.add_command(label="Novo arquivo...", command=self.tree_new_file)
            m.add_command(label="Novo arquivo fora da pasta...", command=self.new_file_external)
        if kind in ("file", "dir", "ext"):
            m.add_separator()
            if kind == "ext":
                m.add_command(label="Remover da lista (manter no disco)",
                              command=self.tree_unlist)
            m.add_command(label="Excluir", accelerator="Del", command=self.tree_delete)
        m.add_separator()
        m.add_command(label="Atualizar", command=self.refresh_tree)
        m.add_command(label="Abrir outra pasta...", command=self.open_folder_dialog)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def _iter_nodes(self, parent=""):
        for n in self.tree.get_children(parent):
            yield n
            yield from self._iter_nodes(n)

    def _is_open(self, iid):
        return str(self.tree.item(iid, "open")).lower() in ("1", "true", "yes")

    @staticmethod
    def _under(path, root):
        """True se `path` é `root` ou está dentro dele."""
        a = os.path.normcase(os.path.abspath(path))
        b = os.path.normcase(os.path.abspath(root))
        return a == b or a.startswith(b.rstrip(os.sep) + os.sep)

    def _is_external(self, path):
        n = os.path.normcase(os.path.abspath(path))
        return any(os.path.normcase(os.path.abspath(x)) == n for x in self.externals)

    def refresh_tree(self):
        if not self.folder and not self.externals:
            return
        opened = {self.node_paths[i] for i in self._iter_nodes()
                  if i in self.node_paths and i not in self.ext_items and self._is_open(i)}
        self.rebuild_tree(opened)

    def _layout_sidebar(self):
        for w in (self.folder_lbl, self.empty_frame, self.tree_wrap):
            w.pack_forget()
        if self.folder:
            self.folder_lbl.configure(
                text="▾ " + (os.path.basename(self.folder) or self.folder).upper())
            self.folder_lbl.pack(fill="x")
            self.tree_wrap.pack(fill="both", expand=True)
        else:
            self.empty_frame.pack(fill="x")
            if self.externals:
                self.tree_wrap.pack(fill="both", expand=True)

    def rebuild_tree(self, opened=()):
        if self.ext_node and self.tree.exists(self.ext_node):
            self.ext_open = self._is_open(self.ext_node)
        self.externals = [p for p in self.externals if os.path.isfile(p)
                          and not (self.folder and self._under(p, self.folder))]
        before = set(self.ext_keep)
        self.ext_keep &= set(self.externals)
        if self.ext_keep != before:
            self.save_config()
        self.tree.delete(*self.tree.get_children())
        self.node_paths.clear()
        self.dummies.clear()
        self.ext_items.clear()
        self.ext_node = None
        self._layout_sidebar()
        if self.folder:
            self.populate("", self.folder, opened)
        if self.folder or self.externals:
            hdr = "EXTERNOS · fora da pasta" if self.folder else "ARQUIVOS ABERTOS"
            self.ext_node = self.tree.insert("", "end", text=hdr,
                                             open=self.ext_open, tags=("ext_hdr",))
            for p in self.externals:
                iid = self.tree.insert(self.ext_node, "end", text=" " + os.path.basename(p),
                                       tags=("lang_" + lang_for(p),))
                self.node_paths[iid] = p
                self.ext_items.add(iid)

    # ----- arquivos externos (fora da pasta aberta) ------------------------------ #
    def load_config(self):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                cfg = json.load(f)
            items = [p for p in cfg.get("externals", []) if isinstance(p, str)]
        except (OSError, ValueError, AttributeError):
            items = []
        self.externals = [p for p in items if os.path.isfile(p)]
        self.ext_keep = set(self.externals)

    def save_config(self):
        update_config(externals=sorted(self.ext_keep), theme=self.theme_name)

    def add_external(self, path, persist=True):
        """Põe um arquivo no grupo EXTERNOS (ou só atualiza a árvore se ele está na pasta)."""
        path = os.path.abspath(path)
        if self.folder and self._under(path, self.folder):
            return self.refresh_tree()
        if not self._is_external(path):
            self.externals.append(path)
        self.last_ext_dir = os.path.dirname(path)
        if persist:
            self.ext_keep.add(path)
            self.save_config()
        self.refresh_tree()

    def add_external_dialog(self):
        for p in filedialog.askopenfilenames(
                parent=self.root, initialdir=self.last_ext_dir or os.path.expanduser("~")):
            self.add_external(p)

    def new_file_external(self, initialdir=None):
        """Cria um arquivo em qualquer pasta do computador, fora da pasta aberta."""
        dlg = NewFileDialog(self, None, external=True)
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        name, ext, with_tpl = dlg.result
        fname = name + ext
        d = filedialog.askdirectory(
            parent=self.root, title="Em qual pasta criar o arquivo?", mustexist=True,
            initialdir=initialdir or self.last_ext_dir or os.path.expanduser("~"))
        if not d:
            return
        path = os.path.join(d, fname)
        if os.path.exists(path):
            messagebox.showinfo(APP, f"“{fname}” já existe nessa pasta. Vou abri-lo.")
        else:
            try:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(self._new_content(name, ext, with_tpl))
            except OSError as ex:
                messagebox.showerror(APP, f"Não foi possível criar o arquivo:\n{ex}")
                return
        self.add_external(path)
        self.open_file(path)

    def tree_new_file(self):
        iid = self.tree.focus()
        p = self.node_paths.get(iid)
        if self.node_kind(iid) in ("ext", "ext_hdr"):
            return self.new_file_external(os.path.dirname(p) if p else None)
        target = self.folder
        if p:
            target = p if os.path.isdir(p) else os.path.dirname(p)
        self.new_file(target)

    def tree_open_side(self):
        iid = self.tree.focus()
        if self.node_kind(iid) in ("file", "ext"):
            self.open_to_side(self.node_paths[iid])

    def tree_unlist(self):
        iid = self.tree.focus()
        p = self.node_paths.get(iid)
        if self.node_kind(iid) != "ext" or not p:
            return
        n = os.path.normcase(os.path.abspath(p))
        self.externals = [x for x in self.externals if os.path.normcase(os.path.abspath(x)) != n]
        self.ext_keep = {x for x in self.ext_keep if os.path.normcase(os.path.abspath(x)) != n}
        self.save_config()
        self.refresh_tree()

    # ----- excluir ---------------------------------------------------------------- #
    def tree_delete(self, _e=None):
        iid = self.tree.focus()
        p = self.node_paths.get(iid)
        kind = self.node_kind(iid)
        if kind not in ("file", "dir", "ext") or not p:
            return
        name = os.path.basename(p)
        if kind == "dir":
            msg = f"Excluir a pasta “{name}” e tudo o que há dentro dela?"
        else:
            msg = f"Excluir o arquivo “{name}”?"
        if not messagebox.askyesno(APP, msg + "\n\nIsso apaga do disco e não pode ser desfeito.",
                                   icon="warning", parent=self.root):
            return
        for ed in list(self.tabs):
            if ed.path and self._under(ed.path, p):
                ed.modified = False
                self.close_tab(ed)
                self.live_forget(ed.path)
        try:
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
        except OSError as ex:
            messagebox.showerror(APP, f"Não foi possível excluir:\n{ex}")
            return
        self.externals = [x for x in self.externals if not self._under(x, p)]
        self.ext_keep = {x for x in self.ext_keep if not self._under(x, p)}
        self.save_config()
        self.refresh_tree()
        self.set_status(f"🗑 Excluído: {name}")

    # ----- mover / copiar (arrastar e soltar) ----------------------------------- #
    def _retarget(self, old, new):
        """Atualiza as abas abertas depois que `old` virou `new` no disco."""
        for ed in self.tabs:
            if ed.path and self._under(ed.path, old):
                rel = os.path.relpath(ed.path, old)
                ed.set_path(os.path.abspath(new if rel == "." else os.path.join(new, rel)))
        self.refresh_tabs()
        self.update_title()
        self.update_tool_status()

    def _remap_external(self, old, new):
        out, keep = [], set()
        for x in self.externals:
            if self._under(x, old):
                rel = os.path.relpath(x, old)
                x2 = new if rel == "." else os.path.join(new, rel)
                if x in self.ext_keep:
                    keep.add(x2)
                x = x2
            out.append(x)
        self.externals = out
        self.ext_keep = {k for k in self.ext_keep if not self._under(k, old)} | keep
        self.save_config()

    def move_path(self, src, dest_dir, copy=False):
        src, dest_dir = os.path.abspath(src), os.path.abspath(dest_dir)
        name = os.path.basename(src)
        dst = os.path.join(dest_dir, name)
        if not copy and os.path.normcase(os.path.dirname(src)) == os.path.normcase(dest_dir):
            return False                                   # já está nessa pasta
        if os.path.isdir(src) and self._under(dest_dir, src):
            messagebox.showerror(APP, "Não dá para colocar uma pasta dentro dela mesma.")
            return False
        if os.path.exists(dst):
            messagebox.showerror(APP, f"Já existe “{name}” em:\n{dest_dir}")
            return False
        try:
            if copy:
                if os.path.isdir(src):
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            else:
                shutil.move(src, dst)
        except (OSError, shutil.Error) as ex:
            messagebox.showerror(APP, f"Não foi possível {'copiar' if copy else 'mover'}:\n{ex}")
            return False
        if not copy:
            self._retarget(src, dst)
            self._remap_external(src, dst)
        if os.path.isfile(dst) and not (self.folder and self._under(dst, self.folder)):
            self.add_external(dst)                         # saiu da pasta: vai para EXTERNOS
        else:
            self.refresh_tree()
        self.set_status(f"✔ {'Copiado' if copy else 'Movido'}: {name}")
        return True

    def _drop_target(self, e):
        """Onde o item foi solto: ('dir', pasta) | ('ext', None) | None."""
        try:
            w = self.root.winfo_containing(e.x_root, e.y_root)
        except (KeyError, tk.TclError):
            w = None
        if w is self.folder_lbl and self.folder:
            return ("dir", self.folder)
        if w is not self.tree:
            return None
        row = self.tree.identify_row(e.y_root - self.tree.winfo_rooty())
        if not row:                                        # espaço vazio = raiz da pasta
            return ("dir", self.folder) if self.folder else None
        kind = self.node_kind(row)
        if kind in ("ext_hdr", "ext"):
            return ("ext", None)
        p = self.node_paths.get(row)
        if kind == "dir":
            return ("dir", p)
        if kind == "file":
            return ("dir", os.path.dirname(p))
        return None

    def on_drag_start(self, e):
        self._drag = None
        row = self.tree.identify_row(e.y)
        if self.node_kind(row) not in ("file", "dir", "ext"):
            return
        try:
            if "indicator" in self.tree.identify_element(e.x, e.y):
                return
        except tk.TclError:
            pass
        self._drag = {"row": row, "x": e.x_root, "y": e.y_root, "on": False, "lbl": None}

    def on_drag_motion(self, e):
        d = self._drag
        if not d:
            return
        if not d["on"]:
            if abs(e.x_root - d["x"]) + abs(e.y_root - d["y"]) < 8:
                return
            d["on"] = True
            name = os.path.basename(self.node_paths[d["row"]])
            d["lbl"] = tk.Label(self.root, text=f"  {name}  ", bg=C["accent"],
                                fg=C["on_accent"], font=self.ui_small, bd=0)
            self.tree.configure(cursor="hand2")
        d["lbl"].place(x=e.x_root - self.root.winfo_rootx() + 14,
                       y=e.y_root - self.root.winfo_rooty() + 12)
        d["lbl"].lift()
        ty = e.y_root - self.tree.winfo_rooty()
        row = self.tree.identify_row(ty) if 0 <= ty < self.tree.winfo_height() else ""
        if row and row != d["row"]:
            self.tree.selection_set(row)
        if ty < 14:
            self.tree.yview_scroll(-1, "units")
        elif ty > self.tree.winfo_height() - 14:
            self.tree.yview_scroll(1, "units")

    def on_drag_end(self, e):
        d, self._drag = self._drag, None
        if not d or not d["on"]:
            return
        d["lbl"].destroy()
        self.tree.configure(cursor="")
        src = self.node_paths.get(d["row"])
        tgt = self._drop_target(e)
        if not src or not tgt or not os.path.exists(src):
            return
        copy = bool(e.state & 0x4)                         # Ctrl solto = copia em vez de mover
        kind, where = tgt
        if kind == "dir":
            self.move_path(src, where, copy)
        elif d["row"] in self.ext_items:
            return                                         # já é externo
        elif os.path.isdir(src):
            messagebox.showinfo(APP, "Só arquivos podem ser levados para fora da pasta aberta.")
        else:
            dest = filedialog.askdirectory(
                parent=self.root, mustexist=True,
                title=f"Para qual pasta levar “{os.path.basename(src)}”?",
                initialdir=self.last_ext_dir or os.path.expanduser("~"))
            if dest:
                self.move_path(src, dest, copy)

    # ----- painel inferior --------------------------------------------------- #
    def build_panel(self):
        p = tk.Frame(self.vpane, bg=C["editor"])
        self.panel = p
        head = tk.Frame(p, bg=C["editor"], height=34)
        head.pack(fill="x")
        head.pack_propagate(False)
        tk.Frame(p, bg=C["border"], height=1).pack(fill="x")

        self.ptab = {}
        for key, label in (("problems", "PROBLEMAS"), ("output", "SAÍDA")):
            fr = tk.Frame(head, bg=C["editor"], cursor="hand2")
            fr.pack(side="left", padx=(14, 0))
            lb = tk.Label(fr, text=label, bg=C["editor"], fg=C["fg_dim"], font=self.ui_small,
                          cursor="hand2")
            lb.pack(pady=(7, 4))
            ul = tk.Frame(fr, bg=C["editor"], height=1)
            ul.pack(fill="x")
            for w in (fr, lb):
                w.bind("<Button-1>", lambda e, k=key: self.show_panel(k))
            self.ptab[key] = (lb, ul)

        close = tk.Label(head, text="✕", bg=C["editor"], fg=C["fg_dim"], font=self.ui_small,
                         padx=10, cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self.toggle_panel())
        clear = tk.Label(head, text="Limpar", bg=C["editor"], fg=C["fg_dim"], font=self.ui_small,
                         padx=8, cursor="hand2")
        clear.pack(side="right")
        clear.bind("<Button-1>", lambda e: self.clear_panel())

        self.out_frame = tk.Frame(p, bg=C["editor"])
        self.out_text = tk.Text(self.out_frame, bg=C["editor"], fg=C["fg_editor"],
                                font=self.out_font, bd=0, highlightthickness=0, wrap="word",
                                state="disabled", padx=14, pady=6, insertwidth=0,
                                selectbackground=C["sel"], inactiveselectbackground=C["sel_off"])
        osb = ttk.Scrollbar(self.out_frame, orient="vertical", command=self.out_text.yview)
        self.out_text.configure(yscrollcommand=osb.set)
        row = tk.Frame(self.out_frame, bg=C["editor"])
        row.pack(side="bottom", fill="x", padx=10, pady=(0, 8))
        tk.Label(row, text="Entrada ›", bg=C["editor"], fg=C["accent"], font=self.ui_small).pack(
            side="left", padx=(4, 8))
        self.stdin_var = tk.StringVar()
        self.stdin_entry = tk.Entry(row, textvariable=self.stdin_var, bg=C["input"],
                                    fg=C["fg_bright"], insertbackground=C["fg_bright"], selectbackground=C["sel"],
                                    selectforeground=C["fg_bright"],
                                    relief="flat", font=self.out_font, state="disabled",
                                    disabledbackground=C["sidebar"], highlightthickness=1,
                                    highlightbackground=C["border"], highlightcolor=C["accent"])
        self.stdin_entry.pack(side="left", fill="x", expand=True, ipady=3)
        self.stdin_entry.bind("<Return>", self.send_input)
        osb.pack(side="right", fill="y")
        self.out_text.pack(fill="both", expand=True)
        for tag, color in (("err", C["err"]), ("warn", C["warn"]), ("ok", C["ok"]),
                           ("info", C["info"]), ("dim", C["fg_dim"]), ("input", C["input_txt"])):
            self.out_text.tag_configure(tag, foreground=color)

        self.prob_frame = tk.Frame(p, bg=C["editor"])
        self.prob_tree = ttk.Treeview(self.prob_frame, columns=("loc",), show="tree")
        self.prob_tree.column("#0", width=700, stretch=True)
        self.prob_tree.column("loc", width=150, stretch=False, anchor="e")
        psb = ttk.Scrollbar(self.prob_frame, orient="vertical", command=self.prob_tree.yview)
        self.prob_tree.configure(yscrollcommand=psb.set)
        psb.pack(side="right", fill="y")
        self.prob_tree.pack(fill="both", expand=True)
        self.prob_tree.tag_configure("error", foreground=C["err"])
        self.prob_tree.tag_configure("warning", foreground=C["warn"])
        self.prob_tree.tag_configure("note", foreground=C["fg_dim"])
        self.prob_tree.bind("<Double-1>", self.on_problem_click)

        self.show_panel("output", ensure_visible=False)

    def show_panel(self, name, ensure_visible=True):
        if ensure_visible and not self.panel_visible:
            self.toggle_panel()
        self.panel_name = name
        self.out_frame.pack_forget()
        self.prob_frame.pack_forget()
        (self.out_frame if name == "output" else self.prob_frame).pack(fill="both", expand=True)
        for k, (lb, ul) in self.ptab.items():
            on = k == name
            lb.configure(fg=C["fg_bright"] if on else C["fg_dim"])
            ul.configure(bg=C["accent"] if on else C["editor"])

    def toggle_panel(self):
        if self.panel_visible:
            self.vpane.forget(self.panel)
        else:
            self.vpane.add(self.panel, height=230, minsize=70, stretch="never")
        self.panel_visible = not self.panel_visible

    def toggle_sidebar(self):
        if self.sidebar_visible:
            self.hpane.forget(self.sidebar)
        else:
            self.hpane.add(self.sidebar, before=self.main, width=250, minsize=140,
                           stretch="never")
        self.sidebar_visible = not self.sidebar_visible
        self.ic_explorer.on = self.sidebar_visible
        self.ic_explorer.configure(fg=C["fg_bright"] if self.sidebar_visible else C["fg_dim"])

    def clear_panel(self):
        if self.panel_name == "output":
            self.clear_output()
        else:
            self.set_problems([])

    def out(self, text, tag=None):
        w = self.out_text
        w.configure(state="normal")
        w.insert("end", text, (tag,) if tag else ())
        w.see("end")
        w.configure(state="disabled")

    def clear_output(self):
        self.out_text.configure(state="normal")
        self.out_text.delete("1.0", "end")
        self.out_text.configure(state="disabled")

    # ----- problemas --------------------------------------------------------- #
    def set_problems(self, probs):
        self.problems = probs
        self.prob_tree.delete(*self.prob_tree.get_children())
        icons = {"error": "✖", "warning": "⚠", "note": "ℹ"}
        for i, p in enumerate(probs):
            loc = f"{os.path.basename(p['file'])} [{p['line']}:{p['col']}]" if p["line"] else ""
            self.prob_tree.insert("", "end", iid=str(i), text=f" {icons[p['sev']]}  {p['msg']}",
                                  values=(loc,), tags=(p["sev"],))
        errs = sum(1 for p in probs if p["sev"] == "error")
        warns = sum(1 for p in probs if p["sev"] == "warning")
        lb, _ = self.ptab["problems"]
        if probs and self.panel_name != "problems":
            color = C["err"] if errs else C["warn"]
        else:
            color = C["fg_bright"] if self.panel_name == "problems" else C["fg_dim"]
        lb.configure(text=f"PROBLEMAS ({errs + warns})" if probs else "PROBLEMAS", fg=color)

    def on_problem_click(self, _e):
        sel = self.prob_tree.focus()
        if sel == "":
            return
        p = self.problems[int(sel)]
        if p["line"]:
            self.goto(p["file"], p["line"], p["col"])

    def goto(self, path, line, col=1):
        if not os.path.isabs(path):
            path = os.path.join(self.run_cwd or os.getcwd(), path)
        path = os.path.normpath(path)
        ed = next((t for t in self.tabs if t.path and os.path.normcase(t.path) ==
                   os.path.normcase(path)), None)
        if ed is None and os.path.isfile(path):
            ed = self.open_file(path)
        if ed is None:
            return
        self.activate(ed)
        ed.text.mark_set("insert", f"{line}.{max(col - 1, 0)}")
        ed.text.tag_remove("sel", "1.0", "end")
        ed.text.see("insert")
        ed.text.focus_set()
        ed.update_cursor()

    def apply_diagnostics(self, ed, probs):
        if ed is None or ed not in self.tabs or not ed.path:
            return
        diag = {}
        for p in probs:
            if p["line"] and p["sev"] in ("error", "warning") and p["file"]:
                fp = os.path.normcase(os.path.abspath(os.path.join(self.run_cwd or "", p["file"])))
                if fp == os.path.normcase(ed.path) and diag.get(p["line"]) != "error":
                    diag[p["line"]] = p["sev"]
        ed.set_diagnostics(diag)

    # ----- grupos (split) e abas ---------------------------------------------- #
    @property
    def active(self):
        return self.cur_group.active if self.cur_group else None

    @property
    def tabs(self):
        return [t for g in self.groups for t in g.tabs]

    def refresh_tabs(self):
        for g in self.groups:
            g.refresh_tabs()

    def focus_group(self, g):
        if g is self.cur_group or g not in self.groups:
            return
        self.cur_group = g
        self.refresh_tabs()
        if g.active:
            g.active.update_cursor()
        self.update_title()
        self.update_tool_status()
        if self.find_visible:
            self.update_matches()

    def focus_group_n(self, i):
        if i < len(self.groups):
            g = self.groups[i]
            self.focus_group(g)
            if g.active:
                g.active.text.focus_set()

    def _make_col(self):
        """Uma coluna do editor: pode empilhar vários grupos (divisão acima/abaixo)."""
        return tk.PanedWindow(self.editor_pane, orient="vertical", bg=C["border"], bd=0,
                              sashwidth=3, sashrelief="flat", opaqueresize=True)

    def _cols(self):
        return [self.editor_pane.nametowidget(str(c)) for c in self.editor_pane.panes()]

    def _reindex(self):
        """Refaz a lista de grupos na ordem em que aparecem na tela (coluna por coluna)."""
        order = []
        for col in self._cols():
            for p in col.panes():
                order.append(col.nametowidget(str(p)))
        self.groups = order

    def add_group(self, after=None, where="right", force=False):
        """Cria um grupo novo ao lado (left/right) ou acima/abaixo (top/bottom) de `after`."""
        if len(self.groups) >= MAX_GROUPS and not force:
            return None
        after = after or self.cur_group
        col = after.col
        if where in ("left", "right"):
            ncol = self._make_col()
            g = EditorGroup(self, ncol, side=True)
            ncol.add(g, minsize=90, stretch="always")
            if where == "right":
                self.editor_pane.add(ncol, after=col, minsize=240, stretch="always")
            else:
                self.editor_pane.add(ncol, before=col, minsize=240, stretch="always")
        else:
            g = EditorGroup(self, col, side=True)
            if where == "bottom":
                col.add(g, after=after, minsize=90, stretch="always")
            else:
                col.add(g, before=after, minsize=90, stretch="always")
        self._reindex()
        self.root.after(60, self.equalize_groups)
        return g

    def equalize_groups(self):
        self.root.update_idletasks()
        cols = self._cols()
        n = len(cols)
        if n > 1:
            w = self.editor_pane.winfo_width()
            for i in range(n - 1):
                try:
                    self.editor_pane.sash_place(i, (i + 1) * w // n, 0)
                except tk.TclError:
                    pass
        for col in cols:
            m = len(col.panes())
            if m > 1:
                h = col.winfo_height()
                for i in range(m - 1):
                    try:
                        col.sash_place(i, 0, (i + 1) * h // m)
                    except tk.TclError:
                        pass

    def remove_group(self, g):
        if g not in self.groups or len(self.groups) < 2:
            return
        i = self.groups.index(g)
        col = g.col
        col.forget(g)
        g.destroy()
        if not col.panes():
            self.editor_pane.forget(col)
            col.destroy()
        self._reindex()
        if self.cur_group is g:
            self.cur_group = self.groups[min(i, len(self.groups) - 1)]
            tgt = self.cur_group.active
            if tgt:
                self.activate(tgt)
            else:
                self.update_title()
                self.update_tool_status()
        self.refresh_tabs()
        self.root.after(60, self.equalize_groups)

    def split_editor(self, ed=None, group=None, where="right"):
        """Dividir editor: cria um grupo à direita (Ctrl+\\) ou abaixo."""
        src = group or (ed.group if ed else self.cur_group)
        ed = ed or src.active
        g = self.add_group(after=src, where=where)
        if g is None:                      # já está no limite de colunas
            nxt = self.groups[(self.groups.index(src) + 1) % len(self.groups)]
            self.focus_group(nxt)
            if nxt.active:
                nxt.active.text.focus_set()
            return
        if ed and len(src.tabs) > 1:       # leva a aba atual para a nova coluna
            self.move_tab(ed, g)
        else:                              # senão, abre a coluna vazia e foca nela
            self.focus_group(g)

    def move_tab(self, ed, dest):
        src = ed.group
        if src is dest:
            return
        new = EditorTab(self, dest, ed.path, ed.get_content(), name=ed.untitled)
        new.set_lang(ed.lang)
        new.modified = ed.modified
        new.text.mark_set("insert", ed.text.index("insert"))
        dest.tabs.append(new)
        idx = src.tabs.index(ed)
        src.tabs.remove(ed)
        was_active = src.active is ed
        ed.destroy()
        if was_active:
            src.active = None
            if src.tabs:
                src.show(src.tabs[min(idx, len(src.tabs) - 1)])
        self.activate(new)
        new.text.see("insert")
        if not src.tabs:
            self.remove_group(src)
        else:
            src.refresh_tabs()

    # ----- arrastar aba para dividir a tela ------------------------------------------ #
    DROP_TEXT = {"left": "Dividir à esquerda", "right": "Dividir à direita",
                 "top": "Dividir acima", "bottom": "Dividir abaixo",
                 "center": "Mover para este grupo"}

    def tab_press(self, ed, e):
        self._tdrag = {"ed": ed, "x": e.x_root, "y": e.y_root, "on": False}

    def tab_motion(self, ed, e):
        d = self._tdrag
        if not d or d["ed"] is not ed:
            return
        if not d["on"]:
            if abs(e.x_root - d["x"]) + abs(e.y_root - d["y"]) < 8:
                return
            d["on"] = True
        self._show_drop(self._tab_drop_at(e.x_root, e.y_root, ed))

    def tab_release(self, ed, e):
        d, self._tdrag = self._tdrag, None
        self._hide_drop()
        if not d or d["ed"] is not ed:
            return
        if not d["on"]:                     # foi só um clique
            if ed.group.tabs and ed in ed.group.tabs:
                self.activate(ed)
            return
        drop = self._tab_drop_at(e.x_root, e.y_root, ed)
        if drop:
            self._do_drop(ed, *drop)

    def _tab_drop_at(self, xr, yr, ed):
        """Descobre (grupo, zona) sob o mouse. Zonas: left/right/top/bottom/center."""
        target = None
        for g in self.groups:
            gx, gy = g.winfo_rootx(), g.winfo_rooty()
            if gx <= xr < gx + g.winfo_width() and gy <= yr < gy + g.winfo_height():
                target = g
                break
        if target is None:
            return None
        g = target
        gx, gy, gw, gh = g.winfo_rootx(), g.winfo_rooty(), g.winfo_width(), g.winfo_height()
        bar_h = g.bar.winfo_height()
        if yr - gy < bar_h:
            zone = "center"                 # solto sobre a barra de abas
        else:
            rx = (xr - gx) / max(gw, 1)
            ay = (yr - gy - bar_h) / max(gh - bar_h, 1)
            if 0.25 <= rx <= 0.75 and 0.25 <= ay <= 0.75:
                zone = "center"
            else:
                dist = {"left": rx, "right": 1 - rx, "top": ay, "bottom": 1 - ay}
                zone = min(dist, key=dist.get)
        src = ed.group
        if zone == "center":
            return None if g is src else (g, zone)
        if g is src and len(src.tabs) < 2:  # não dá para dividir um grupo com uma aba só
            return None
        if len(self.groups) >= MAX_GROUPS and not (len(src.tabs) == 1 and g is not src):
            return None                     # limite de divisões
        return (g, zone)

    def _do_drop(self, ed, g, zone):
        src = ed.group
        if zone == "center":
            self.move_tab(ed, g)
            return
        force = len(src.tabs) == 1 and src is not g
        new = self.add_group(after=g, where=zone, force=force)
        if new is None:
            self.root.bell()
            return
        self.move_tab(ed, new)

    def _show_drop(self, drop):
        if drop is None:
            return self._hide_drop()
        g, zone = drop
        if self._dz is None:
            self._dz = ([tk.Frame(self.root, bg=C["accent"]) for _ in range(4)],
                        tk.Label(self.root, bg=C["accent"], fg=C["on_accent"],
                                 font=self.ui_bold, padx=10, pady=4))
        frames, lbl = self._dz
        gx, gy, gw, gh = g.winfo_rootx(), g.winfo_rooty(), g.winfo_width(), g.winfo_height()
        bar_h = g.bar.winfo_height()
        if zone == "center":
            x, y, w, h = gx, gy, gw, gh
        else:
            y0, h0 = gy + bar_h, max(gh - bar_h, 1)
            x, y, w, h = {"left": (gx, y0, gw // 2, h0),
                          "right": (gx + gw // 2, y0, gw - gw // 2, h0),
                          "top": (gx, y0, gw, h0 // 2),
                          "bottom": (gx, y0 + h0 // 2, gw, h0 - h0 // 2)}[zone]
        x -= self.root.winfo_rootx()
        y -= self.root.winfo_rooty()
        t = 4
        top, bottom, left, right = frames
        top.place(x=x, y=y, width=w, height=t)
        bottom.place(x=x, y=y + h - t, width=w, height=t)
        left.place(x=x, y=y, width=t, height=h)
        right.place(x=x + w - t, y=y, width=t, height=h)
        lbl.configure(text=self.DROP_TEXT[zone])
        lbl.place(x=x + w // 2, y=y + h // 2, anchor="center")
        for f in frames:
            f.lift()
        lbl.lift()

    def _hide_drop(self):
        if self._dz:
            for f in self._dz[0]:
                f.place_forget()
            self._dz[1].place_forget()

    def move_to_other(self, ed):
        if len(self.groups) < 2:
            return self.split_editor(ed)
        dest = self.groups[(self.groups.index(ed.group) + 1) % len(self.groups)]
        self.move_tab(ed, dest)

    def close_others(self, ed):
        for t in list(ed.group.tabs):
            if t is not ed and not self.close_tab(t):
                break

    def show_tab_menu(self, ed, e):
        m = self._menu(self.root)
        m.add_command(label="Fechar", command=lambda: self.close_tab(ed))
        m.add_command(label="Fechar as outras", command=lambda: self.close_others(ed))
        m.add_separator()
        if len(self.groups) < MAX_GROUPS:
            m.add_command(label="Dividir à direita", command=lambda: self.split_editor(ed))
            m.add_command(label="Dividir abaixo",
                          command=lambda: self.split_editor(ed, where="bottom"))
        if len(self.groups) > 1:
            m.add_command(label="Mover para o outro grupo",
                          command=lambda: self.move_to_other(ed))
        if ed.path:
            m.add_command(label="Copiar caminho", command=lambda: (
                self.root.clipboard_clear(), self.root.clipboard_append(ed.path)))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    def activate(self, ed):
        g = ed.group
        changed = self.cur_group is not g
        self.cur_group = g
        g.show(ed)
        if changed:
            self.refresh_tabs()
        ed.text.focus_set()
        ed.update_cursor()
        ed.redraw_gutter()
        self.update_title()
        self.update_tool_status()
        if self.find_visible:
            self.update_matches()

    def add_tab(self, ed):
        ed.group.tabs.append(ed)
        self.activate(ed)

    # ----- criar / abrir / salvar --------------------------------------------- #
    def new_file(self, target_dir=None):
        """Ctrl+N: abre a janela que pergunta nome, extensão e linguagem."""
        folder = target_dir or self.folder
        dlg = NewFileDialog(self, folder)
        self.root.wait_window(dlg)
        if not dlg.result:
            return
        name, ext, with_tpl = dlg.result
        fname = name + ext
        content = self._new_content(name, ext, with_tpl)
        if folder:
            path = os.path.join(folder, fname)
            if os.path.exists(path):
                messagebox.showinfo(APP, f"“{fname}” já existe nessa pasta. Vou abri-lo.")
                self.open_file(path)
                return
            try:
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(content)
            except OSError as ex:
                messagebox.showerror(APP, f"Não foi possível criar o arquivo:\n{ex}")
                return
            self.refresh_tree()
            self.open_file(path)
        else:
            ed = EditorTab(self, self.cur_group, None, content, name=fname)
            self.add_tab(ed)

    def new_untitled(self, lang, content):
        """Usado pelos Exemplos: abre uma aba sem título com o código de exemplo."""
        self.untitled_count += 1
        ext = LANGS[lang]["exts"][0]
        name = "Main.java" if lang == "java" else f"sem_titulo-{self.untitled_count}{ext}"
        self.add_tab(EditorTab(self, self.cur_group, None, content, name=name))

    def open_dialog(self):
        paths = filedialog.askopenfilenames(
            parent=self.root,
            initialdir=self.folder or self.last_ext_dir or os.path.expanduser("~"),
            filetypes=[("Arquivos de código", all_exts()), ("Todos os arquivos", "*.*")])
        for p in paths:
            self.open_file(p)

    def open_folder_dialog(self):
        d = filedialog.askdirectory(parent=self.root, initialdir=self.folder or
                                    os.path.expanduser("~"))
        if d:
            self.set_folder(d)

    def _find_tab(self, path):
        path = os.path.normcase(os.path.abspath(path))
        return next((t for t in self.tabs if t.path and os.path.normcase(t.path) == path), None)

    def open_file(self, path, group=None):
        path = os.path.abspath(path)
        ex = self._find_tab(path)
        if ex:
            self.activate(ex)
            return ex
        try:
            with open(path, "rb") as f:
                raw = f.read()
        except OSError as e:
            messagebox.showerror(APP, f"Não foi possível abrir o arquivo:\n{e}")
            return None
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = raw.decode("latin-1")
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        ed = EditorTab(self, group or self.cur_group, path, text)
        self.add_tab(ed)
        # Abrir um arquivo NÃO abre a pasta dele: se não está na pasta aberta (ou se não há
        # pasta aberta), ele só aparece sozinho na lista do explorador.
        if not (self.folder and self._under(path, self.folder)) and not self._is_external(path):
            self.add_external(path, persist=False)
        return ed

    def open_to_side(self, path):
        cur = self.cur_group
        i = self.groups.index(cur)
        if i + 1 < len(self.groups):
            tgt = self.groups[i + 1]
        else:
            tgt = self.add_group(after=cur) or self.groups[(i + 1) % len(self.groups)]
        ex = self._find_tab(path)
        if ex is None:
            self.open_file(path, group=tgt)
        elif ex.group is tgt:
            self.activate(ex)
        else:
            self.move_tab(ex, tgt)

    def save(self, ed=None, as_new=False):
        ed = ed or self.active
        if not ed:
            return False
        path = ed.path
        created = False
        if as_new or not path:
            exts = LANGS[ed.lang]["exts"]
            path = filedialog.asksaveasfilename(
                parent=self.root, defaultextension=exts[0], initialfile=ed.name,
                initialdir=os.path.dirname(ed.path) if ed.path else
                (self.folder or os.path.expanduser("~")),
                filetypes=[(LANGS[ed.lang]["name"], " ".join("*" + e for e in exts)),
                           ("Todos", "*.*")])
            if not path:
                return False
            created = True
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(ed.get_content())
        except OSError as e:
            messagebox.showerror(APP, f"Não foi possível salvar:\n{e}")
            return False
        old_lang = ed.lang
        ed.set_path(os.path.abspath(path))
        ed.modified = False
        self.refresh_tabs()
        self.update_title()
        if ed.lang != old_lang:
            self.update_tool_status()
        if created:                    # salvar não abre a pasta: o arquivo entra sozinho na lista
            self.add_external(ed.path, persist=False)
            self.live_changed(ed)
        return True

    def close_active(self):
        if self.active:
            self.close_tab(self.active)

    def close_tab(self, ed):
        was_mod = ed.modified
        if ed.modified:
            ans = messagebox.askyesnocancel(APP, f"Salvar as alterações em “{ed.name}”?",
                                            parent=self.root)
            if ans is None:
                return False
            if ans and not self.save(ed):
                return False
        g = ed.group
        idx = g.tabs.index(ed)
        g.tabs.remove(ed)
        was_active = g.active is ed
        ed.destroy()
        if was_mod and ed.path:
            self.live_forget(ed.path)
        if was_active:
            g.active = None
            if g.tabs:
                self.activate(g.tabs[min(idx, len(g.tabs) - 1)])
            elif len(self.groups) > 1:
                self.remove_group(g)           # coluna vazia some, como no VS Code
            else:
                g.refresh_tabs()
                g.update_crumb()
                g.show_welcome()
                self.update_title()
                self.update_tool_status()
        else:
            g.refresh_tabs()
        return True

    def update_title(self):
        ed = self.active
        if ed:
            t = f"{ed.name}{' ●' if ed.modified else ''}  —  {APP}"
        else:
            t = APP
            self.set_cursor_status(1, 1)
        for g in self.groups:
            g.update_crumb()
        self.title_lbl.configure(text=t)
        self.root.title(t)

    # ----- edição / atalhos -------------------------------------------------- #
    def ev(self, name):
        if self.active:
            self.active.text.focus_set()
            self.active.text.event_generate(name)

    def select_all(self):
        if self.active:
            self.active.text.tag_add("sel", "1.0", "end-1c")

    def toggle_comment(self):
        if self.active:
            self.active.toggle_comment()

    def goto_line_dialog(self):
        if not self.active:
            return
        n = simpledialog.askinteger("Ir para linha", "Número da linha:", parent=self.root,
                                    minvalue=1)
        if n:
            t = self.active.text
            t.mark_set("insert", f"{n}.0")
            t.see("insert")
            self.active.update_cursor()

    def zoom(self, d):
        lo, hi = SETTINGS_RANGES["code_size"]
        s = self.settings
        s["code_size"] = SETTINGS_DEFAULTS["code_size"] if d == 0 \
            else max(lo, min(hi, s["code_size"] + d))
        self.code_font.configure(size=s["code_size"])
        for ed in self.tabs:
            ed.apply_font_settings()
        self.save_settings()
        if self._settings_refresh:
            self._settings_refresh()

    def bind_shortcuts(self, widget, local=False):
        def b(seq, fn):
            if local:
                widget.bind(seq, lambda e: (fn(), "break")[1])
            else:
                widget.bind_all(seq, lambda e: (fn(), "break")[1])

        for k, fn in (("n", self.new_file), ("o", self.open_dialog), ("s", self.save),
                      ("w", self.close_active), ("q", self.quit), ("b", self.toggle_sidebar),
                      ("j", self.toggle_panel), ("f", lambda: self.show_find(False)),
                      ("h", lambda: self.show_find(True)), ("g", self.goto_line_dialog),
                      ("slash", self.toggle_comment)):
            b(f"<{MOD}-{k}>", fn)
        b(f"<{MOD}-Shift-N>", self.new_file_external)
        b(f"<{MOD}-Shift-n>", self.new_file_external)
        b(f"<{MOD}-Shift-S>", lambda: self.save(as_new=True))
        b(f"<{MOD}-Shift-s>", lambda: self.save(as_new=True))
        b(f"<{MOD}-Shift-O>", self.open_folder_dialog)
        b(f"<{MOD}-Shift-o>", self.open_folder_dialog)
        b("<F5>", lambda: self.build(True))
        b("<F6>", lambda: self.build(False))
        b("<F7>", self.open_in_browser)
        b("<F8>", self.build_exe)
        b(f"<{MOD}-comma>", self.open_settings)
        b(f"<{MOD}-backslash>", self.split_editor)
        for n in (1, 2, 3):
            b(f"<{MOD}-Key-{n}>", lambda n=n: self.focus_group_n(n - 1))
        b("<Shift-F5>", self.stop)
        for seq in (f"<{MOD}-equal>", f"<{MOD}-plus>", f"<{MOD}-KP_Add>"):
            b(seq, lambda: self.zoom(1))
        for seq in (f"<{MOD}-minus>", f"<{MOD}-KP_Subtract>"):
            b(seq, lambda: self.zoom(-1))
        b(f"<{MOD}-Key-0>", lambda: self.zoom(0))
        b(f"<{MOD}-Shift-braceleft>", self.fold_current)
        b(f"<{MOD}-Shift-braceright>", self.unfold_current)

    # ----- localizar / substituir ------------------------------------------- #
    def build_findbar(self):
        f = tk.Frame(self.editor_col, bg=C["sidebar"], highlightthickness=1,
                     highlightbackground=C["border"])
        self.findbar = f
        self.find_var = tk.StringVar()
        self.repl_var = tk.StringVar()
        self.case_var = tk.BooleanVar(value=False)

        def entry(var, width):
            e = tk.Entry(f, textvariable=var, width=width, bg=C["input"], fg=C["fg_bright"],
                         insertbackground=C["fg_bright"], selectbackground=C["sel"],
                                    selectforeground=C["fg_bright"], relief="flat", font=self.ui,
                         highlightthickness=1, highlightbackground=C["input"],
                         highlightcolor=C["accent"])
            e.pack(side="left", padx=(8, 0), pady=6, ipady=2)
            return e

        def btn(text, cmd):
            l = tk.Label(f, text=text, bg=C["sidebar"], fg=C["fg"], font=self.ui_small,
                         padx=8, cursor="hand2")
            l.pack(side="left")
            l.bind("<Button-1>", lambda e: cmd())
            l.bind("<Enter>", lambda e: l.configure(bg=C["hover"]))
            l.bind("<Leave>", lambda e: l.configure(bg=C["sidebar"]))
            return l

        self.find_entry = entry(self.find_var, 24)
        btn("↑", lambda: self.find_next(True))
        btn("↓", lambda: self.find_next(False))
        self.find_count = tk.Label(f, text="", bg=C["sidebar"], fg=C["fg_dim"],
                                   font=self.ui_small, width=12)
        self.find_count.pack(side="left")
        tk.Checkbutton(f, text="Aa", variable=self.case_var, bg=C["sidebar"], fg=C["fg"],
                       selectcolor=C["input"], activebackground=C["sidebar"],
                       activeforeground=C["fg_bright"], bd=0, font=self.ui_small,
                       highlightthickness=0, command=self.update_matches).pack(side="left")
        self.repl_entry = entry(self.repl_var, 18)
        btn("Substituir", self.replace_one)
        btn("Todos", self.replace_all)
        x = tk.Label(f, text="✕", bg=C["sidebar"], fg=C["fg_dim"], font=self.ui_small, padx=10,
                     cursor="hand2")
        x.pack(side="right")
        x.bind("<Button-1>", lambda e: self.hide_find())

        self.find_var.trace_add("write", lambda *_: self.update_matches())
        for e in (self.find_entry, self.repl_entry):
            e.bind("<Escape>", lambda ev: self.hide_find())
        self.find_entry.bind("<Return>", lambda e: self.find_next(False))
        self.find_entry.bind("<Shift-Return>", lambda e: self.find_next(True))
        self.repl_entry.bind("<Return>", lambda e: self.replace_one())

    def show_find(self, with_replace=False):
        if not self.active:
            return
        t = self.active.text
        if t.tag_ranges("sel"):
            s = t.get("sel.first", "sel.last")
            if "\n" not in s:
                self.find_var.set(s)
        if not self.find_visible:
            self.findbar.pack(fill="x", before=self.editor_pane)
            self.find_visible = True
        self.update_matches()
        (self.repl_entry if with_replace else self.find_entry).focus_set()
        self.find_entry.selection_range(0, "end")

    def hide_find(self):
        if not self.find_visible:
            return
        self.findbar.pack_forget()
        self.find_visible = False
        for ed in self.tabs:
            ed.text.tag_remove("match", "1.0", "end")
        if self.active:
            self.active.text.focus_set()

    def update_matches(self):
        ed = self.active
        if not ed or not self.find_visible:
            return
        t, q = ed.text, self.find_var.get()
        t.tag_remove("match", "1.0", "end")
        if not q:
            self.find_count.configure(text="")
            return
        nocase = not self.case_var.get()
        start, n = "1.0", 0
        while n < 5000:
            idx = t.search(q, start, stopindex="end", nocase=nocase)
            if not idx:
                break
            end = f"{idx}+{len(q)}c"
            t.tag_add("match", idx, end)
            start = end
            n += 1
        self.find_count.configure(text=f"{n} resultado(s)" if n else "sem resultados",
                                  fg=C["fg_dim"] if n else C["err"])

    def find_next(self, backwards=False):
        ed = self.active
        q = self.find_var.get()
        if not ed or not q:
            return
        t = ed.text
        nocase = not self.case_var.get()
        has_sel = bool(t.tag_ranges("sel"))
        if backwards:
            start = t.index("sel.first") if has_sel else t.index("insert")
            idx = t.search(q, start, stopindex="1.0", backwards=True, nocase=nocase)
            if not idx:
                idx = t.search(q, "end-1c", stopindex="1.0", backwards=True, nocase=nocase)
        else:
            start = t.index("sel.last") if has_sel else t.index("insert")
            idx = t.search(q, start, stopindex="end", nocase=nocase)
            if not idx:
                idx = t.search(q, "1.0", stopindex="end", nocase=nocase)
        if idx:
            end = f"{idx}+{len(q)}c"
            t.tag_remove("sel", "1.0", "end")
            t.tag_add("sel", idx, end)
            t.mark_set("insert", idx if backwards else end)
            t.see(idx)
            ed.update_cursor()

    def replace_one(self):
        ed = self.active
        q, r = self.find_var.get(), self.repl_var.get()
        if not ed or not q:
            return
        t = ed.text
        if t.tag_ranges("sel"):
            cur = t.get("sel.first", "sel.last")
            same = cur == q if self.case_var.get() else cur.lower() == q.lower()
            if same:
                idx = t.index("sel.first")
                t.delete("sel.first", "sel.last")
                t.insert(idx, r)
                t.mark_set("insert", f"{idx}+{len(r)}c")
        self.find_next(False)
        self.update_matches()

    def replace_all(self):
        ed = self.active
        q, r = self.find_var.get(), self.repl_var.get()
        if not ed or not q:
            return
        t = ed.text
        nocase = not self.case_var.get()
        start, n = "1.0", 0
        t.edit_separator()
        while True:
            idx = t.search(q, start, stopindex="end", nocase=nocase)
            if not idx:
                break
            t.delete(idx, f"{idx}+{len(q)}c")
            t.insert(idx, r)
            start = f"{idx}+{len(r)}c"
            n += 1
        t.edit_separator()
        self.update_matches()
        self.find_count.configure(text=f"{n} substituído(s)", fg=C["ok"])

    # ----- ferramentas ------------------------------------------------------- #
    def choose_tool(self):
        ed = self.active
        lang = ed.lang if ed else "c"
        if lang in ("html", "css"):
            return messagebox.showinfo(APP, "HTML e CSS abrem no navegador padrão do sistema.")
        if lang == "text":
            return
        what = {"c": "compilador C (gcc, clang, tcc)", "java": "javac (do JDK)",
                "python": "interpretador Python", "js": "Node.js (node)"}[lang]
        p = filedialog.askopenfilename(
            parent=self.root, title=f"Escolha o executável do {what}",
            filetypes=[("Executáveis", "*.exe" if IS_WIN else "*"), ("Todos", "*.*")])
        if not p:
            return
        T = self.tools if self.tools is not None else {}
        self.tools = T
        if lang == "c":
            T["cc"] = p
        elif lang == "java":
            T["javac"] = p
            java = os.path.join(os.path.dirname(p), "java" + EXE)
            T["java"] = java if os.path.isfile(java) else shutil.which("java")
        elif lang == "python":
            T["python"] = p
        elif lang == "js":
            T["node"] = p
        self.update_tool_status()
        self.out(f"Ferramenta definida: {p}\n", "info")

    def show_tools(self):
        T = self.tools or {}

        def mark(k):
            return f"✔ {T[k]}" if T.get(k) else "✖ não encontrado"

        messagebox.showinfo("Ferramentas detectadas", "\n".join([
            f"C ............ {mark('cc')}", f"Java (javac) . {mark('javac')}",
            f"Java (java) .. {mark('java')}", f"Python ....... {mark('python')}",
            f"Node.js ...... {mark('node')}", "HTML / CSS ... navegador padrão"]))

    def show_install_help(self):
        if IS_WIN:
            msg = ("Windows\n"
                   "  C ........ MSYS2 (msys2.org) e depois, no terminal UCRT64:\n"
                   "             pacman -S mingw-w64-ucrt-x86_64-gcc\n"
                   "  Java ..... JDK Temurin (adoptium.net)\n"
                   "  Node.js .. nodejs.org\n\n"
                   "Dica: marque 'Add to PATH' nos instaladores.")
        elif IS_MAC:
            msg = ("macOS\n  C ........ xcode-select --install\n"
                   "  Java ..... brew install openjdk\n  Node.js .. brew install node")
        else:
            msg = ("Linux (Debian/Ubuntu)\n  C ........ sudo apt install build-essential\n"
                   "  Java ..... sudo apt install default-jdk\n"
                   "  Node.js .. sudo apt install nodejs\n"
                   "  (Fedora: dnf · Arch: pacman)")
        messagebox.showinfo("Instalar ferramentas",
                            msg + "\n\nPython já vem com a própria IDE; HTML e CSS usam o navegador.")

    def fold_current(self):
        if self.active:
            self.active.fold_current()

    def unfold_current(self):
        if self.active:
            self.active.unfold_current()

    def fold_all(self):
        if self.active:
            self.active.fold_all()

    def unfold_all(self):
        if self.active:
            self.active.unfold_all()

    # ----- menu de contexto do editor ------------------------------------------ #
    def text_menu(self, ed, e):
        ed.text.focus_set()
        has = bool(ed.text.tag_ranges("sel"))
        st = "normal" if has else "disabled"
        m = self._menu(self.root)
        m.add_command(label="Recortar", state=st, command=lambda: self.ev("<<Cut>>"))
        m.add_command(label="Copiar", state=st, command=lambda: self.ev("<<Copy>>"))
        m.add_command(label="Colar", command=lambda: self.ev("<<Paste>>"))
        m.add_command(label="Selecionar tudo", command=self.select_all)
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()
        return "break"

    # ----- configurações -------------------------------------------------------- #
    def indent_for(self, lang):
        """Espaços por nível de indentação: o valor das configurações ou o padrão da linguagem."""
        return self.settings["indent"] or LANGS[lang]["indent"]

    def tab_width(self):
        return self.settings["indent"] or 4

    def save_settings(self):
        s = self.settings
        s.update(live_on=bool(self.live_on.get()), c_std=self.std.get(),
                 warn=bool(self.warn_var.get()), opt=bool(self.opt_var.get()),
                 noconsole=bool(self.noconsole_var.get()))
        update_config(settings=dict(s))

    def pick_fonts(self):
        """Fonte da interface e do código: a escolhida nas configurações ou a melhor instalada."""
        s = self.settings
        avail = set(tkfont.families())
        ui = s["ui_font"] if s["ui_font"] in avail else self._pick_font(UI_FONT_PREFS, "Arial")
        code = s["code_font"] if s["code_font"] in avail else \
            self._pick_font(CODE_FONT_PREFS, "Courier")
        return ui, code

    def apply_fonts(self):
        """Aplica ao vivo as fontes e tamanhos das configurações em toda a IDE."""
        s = self.settings
        self.ui_font_name, self.code_font_name = self.pick_fonts()
        self.ui.configure(family=self.ui_font_name, size=s["ui_size"] + 1)
        self.ui_small.configure(family=self.ui_font_name, size=s["ui_size"])
        self.ui_bold.configure(family=self.ui_font_name, size=s["ui_size"])
        self.code_font.configure(family=self.code_font_name, size=s["code_size"])
        self.out_font.configure(family=self.code_font_name, size=s["out_size"])
        self.setup_style()
        for ed in self.tabs:
            ed.apply_font_settings()
        self.update_tool_status()

    def mono_families(self):
        """Fontes de largura fixa instaladas (a conferência é feita uma vez só)."""
        if self._mono_cache is None:
            mono = []
            for n in sorted({n for n in tkfont.families() if not n.startswith("@")},
                            key=str.lower):
                try:
                    if tkfont.Font(family=n, size=10).metrics("fixed"):
                        mono.append(n)
                except tk.TclError:
                    pass
            self._mono_cache = mono
        return self._mono_cache

    def open_settings(self):
        old = self._settings_win
        if old is not None:
            try:
                if old.winfo_exists():
                    old.deiconify()
                    old.lift()
                    old.focus_set()
                    return
            except tk.TclError:
                pass
        s = self.settings
        AUTO = "(automática)"
        IND = {0: "Automático (por linguagem)", 2: "2 espaços", 4: "4 espaços", 8: "8 espaços"}
        win = tk.Toplevel(self.root)
        self._settings_win = win
        win.title("Configurações")
        win.configure(bg=C["sidebar"])
        win.transient(self.root)
        win.minsize(520, 420)
        try:
            win.iconphoto(False, *self.icons)
        except (tk.TclError, TypeError):
            pass

        footer = tk.Frame(win, bg=C["sidebar"])
        footer.pack(side="bottom", fill="x", padx=22, pady=12)
        wrap = tk.Frame(win, bg=C["sidebar"])
        wrap.pack(fill="both", expand=True)
        cv = tk.Canvas(wrap, bg=C["sidebar"], highlightthickness=0, bd=0)
        vs = ttk.Scrollbar(wrap, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        cv.pack(side="left", fill="both", expand=True)
        body = tk.Frame(cv, bg=C["sidebar"])
        cv_win = cv.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>", lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfigure(cv_win, width=e.width))

        def wheel(e):
            if e.num == 4:
                step = -1
            elif e.num == 5:
                step = 1
            else:
                step = -1 if e.delta > 0 else 1
            if body.winfo_reqheight() > cv.winfo_height():
                cv.yview_scroll(step, "units")
            return "break"

        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            win.bind(seq, wheel)

        def lab(parent, text, fg=None, bold=False, **kw):
            return tk.Label(parent, text=text, bg=C["sidebar"], fg=fg or C["fg"], anchor="w",
                            justify="left", font=self.ui_bold if bold else self.ui_small, **kw)

        def section(title):
            lab(body, title, fg=C["fg_bright"], bold=True).pack(fill="x", padx=22, pady=(20, 4))
            tk.Frame(body, bg=C["popup_border"], height=1).pack(fill="x", padx=22)

        def row(title, hint=""):
            fr = tk.Frame(body, bg=C["sidebar"])
            fr.pack(fill="x", padx=22, pady=(12, 0))
            lab(fr, title).pack(fill="x")
            if hint:
                lab(fr, hint, fg=C["fg_dim"], wraplength=500).pack(fill="x")
            return fr

        def combo(fr, values, current, width=40):
            cb = ttk.Combobox(fr, values=values, state="readonly", font=self.ui, width=width)
            cb.set(current)
            cb.pack(anchor="w", pady=(5, 0))
            for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
                cb.bind(seq, wheel)          # a roda rola a janela em vez de trocar o valor
            return cb

        def changed():
            self.apply_fonts()
            self.save_settings()

        spins = {}

        def spin(fr, key):
            lo, hi = SETTINGS_RANGES[key]
            var = tk.StringVar(value=str(s[key]))

            def commit(_e=None):
                try:
                    v = int(var.get())
                except ValueError:
                    v = s[key]
                v = max(lo, min(hi, v))
                var.set(str(v))
                if v != s[key]:
                    s[key] = v
                    changed()

            sp = tk.Spinbox(fr, from_=lo, to=hi, width=6, textvariable=var, font=self.ui,
                            bg=C["input"], fg=C["fg_bright"], insertbackground=C["fg_bright"],
                            buttonbackground=C["hover"], relief="flat", justify="center",
                            highlightthickness=1, highlightbackground=C["input"],
                            highlightcolor=C["accent"], wrap=False, command=commit)
            sp.bind("<Return>", commit)
            sp.bind("<FocusOut>", commit)
            sp.pack(anchor="w", pady=(5, 0))
            spins[key] = var

        def check(text, var, cmd=None):
            tk.Checkbutton(body, text=text, variable=var, command=cmd, bg=C["sidebar"],
                           fg=C["fg"], activebackground=C["sidebar"],
                           activeforeground=C["fg_bright"], selectcolor=C["input"],
                           font=self.ui_small, anchor="w", bd=0, highlightthickness=0,
                           cursor="hand2").pack(fill="x", padx=18, pady=(8, 0))

        section("Aparência")
        theme_cb = combo(row("Tema de cores"), list(THEMES), self.theme_name)
        theme_cb.bind("<<ComboboxSelected>>", lambda e: self.set_theme(theme_cb.get()))

        section("Editor")
        code_cb = combo(row("Fonte do código",
                            "Lista só as fontes de largura fixa instaladas no computador."),
                        [AUTO] + self.mono_families(), s["code_font"] or AUTO)

        def pick_code(_e=None):
            s["code_font"] = "" if code_cb.get() == AUTO else code_cb.get()
            changed()

        code_cb.bind("<<ComboboxSelected>>", pick_code)
        spin(row("Tamanho da fonte do código",
                 f"Também muda com {MOD_LABEL}+ + / − e {MOD_LABEL}+roda do mouse."), "code_size")
        spin(row("Espaçamento entre linhas (pixels)"), "line_spacing")
        ind_cb = combo(row("Indentação (quanto o Tab insere)",
                           "Automático: 4 espaços em C, Java, Python e Texto; 2 em HTML, CSS e "
                           "JavaScript."), list(IND.values()), IND[s["indent"]], width=30)

        def pick_indent(_e=None):
            s["indent"] = {v: k for k, v in IND.items()}.get(ind_cb.get(), 0)
            changed()

        ind_cb.bind("<<ComboboxSelected>>", pick_indent)

        section("Interface")
        families = [AUTO] + sorted({n for n in tkfont.families() if not n.startswith("@")},
                                   key=str.lower)
        ui_cb = combo(row("Fonte da interface (menus, abas, explorador)"), families,
                      s["ui_font"] or AUTO)

        def pick_ui(_e=None):
            s["ui_font"] = "" if ui_cb.get() == AUTO else ui_cb.get()
            changed()

        ui_cb.bind("<<ComboboxSelected>>", pick_ui)
        spin(row("Tamanho da fonte da interface"), "ui_size")
        spin(row("Tamanho da fonte do painel de saída"), "out_size")

        section("Execução")
        check("Atualizar o navegador sozinho ao editar HTML, CSS e JS", self.live_on,
              self.live_toggle)
        check("Mostrar avisos do compilador (C: -Wall -Wextra, Java: -Xlint)", self.warn_var)
        check("Otimizar programas em C (-O2)", self.opt_var)
        check("Gerar .exe sem janela de console (programas com janela, ex.: Tkinter)",
              self.noconsole_var)
        std_cb = combo(row("Padrão da linguagem C"), list(C_STANDARDS), self.std.get(), width=12)
        std_cb.bind("<<ComboboxSelected>>",
                    lambda e: (self.std.set(std_cb.get()), self.update_tool_status()))
        tk.Frame(body, bg=C["sidebar"], height=12).pack()

        def refresh():
            try:
                theme_cb.set(self.theme_name)
                code_cb.set(s["code_font"] or AUTO)
                ui_cb.set(s["ui_font"] or AUTO)
                ind_cb.set(IND[s["indent"]])
                std_cb.set(self.std.get())
                for k, v in spins.items():
                    v.set(str(s[k]))
            except tk.TclError:
                pass

        self._settings_refresh = refresh

        def reset(_e=None):
            if not messagebox.askyesno("Configurações", "Restaurar todas as configurações para "
                                       "o padrão (tema, fontes, tamanhos, indentação e "
                                       "execução)?", parent=win):
                return
            D = SETTINGS_DEFAULTS
            for k in ("code_font", "code_size", "out_size", "ui_font", "ui_size",
                      "line_spacing", "indent"):
                s[k] = D[k]
            self.live_on.set(D["live_on"])
            self.warn_var.set(D["warn"])
            self.opt_var.set(D["opt"])
            self.noconsole_var.set(D["noconsole"])
            self.std.set(D["c_std"])
            self.apply_fonts()
            self.set_theme(DEFAULT_THEME)
            self.save_settings()
            self.live_toggle()
            refresh()

        lab(footer, "As mudanças valem na hora e ficam salvas.", fg=C["fg_dim"]).pack(
            side="left")
        close = tk.Label(footer, text="Fechar", bg=C["accent"], fg=C["on_accent"],
                         font=self.ui_small, padx=16, pady=5, cursor="hand2")
        close.pack(side="right")
        rst = tk.Label(footer, text="Restaurar padrões", bg=C["hover"], fg=C["fg"],
                       font=self.ui_small, padx=14, pady=5, cursor="hand2")
        rst.pack(side="right", padx=(0, 8))
        close.bind("<Button-1>", lambda e: win.destroy())
        rst.bind("<Button-1>", reset)
        win.bind("<Escape>", lambda e: win.destroy())

        def on_destroy(e):
            if e.widget is win:
                self._settings_win = None
                self._settings_refresh = None

        win.bind("<Destroy>", on_destroy)
        win.update_idletasks()
        w = 640
        h = min(720, max(420, self.root.winfo_height() - 80))
        x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - w) // 2)
        win.geometry(f"{w}x{h}+{x}+{self.root.winfo_rooty() + 30}")
        win.focus_set()

    # ----- sobre ------------------------------------------------------------- #
    def show_about(self):
        old = getattr(self, "_about", None)
        if old is not None:
            try:
                if old.winfo_exists():
                    old.deiconify()
                    old.lift()
                    old.focus_set()
                    return
            except tk.TclError:
                pass
        win = tk.Toplevel(self.root)
        self._about = win
        win.title(f"Sobre o {APP}")
        win.configure(bg=C["sidebar"])
        win.resizable(False, False)
        win.transient(self.root)
        try:
            win.iconphoto(False, *self.icons)
        except (tk.TclError, TypeError):
            pass
        win.logo = make_app_icon(112)                 # guarda a imagem para o Tk não apagá-la

        body = tk.Frame(win, bg=C["sidebar"], padx=28, pady=22)
        body.pack(fill="both", expand=True)
        tk.Label(body, image=win.logo, bg=C["sidebar"], bd=0).pack()
        tk.Label(body, text=APP, bg=C["sidebar"], fg=C["fg_bright"],
                 font=(self.ui_font_name, 22, "bold")).pack(pady=(10, 0))
        tk.Label(body, text=f"Versão {VERSION}", bg=C["sidebar"], fg=C["info"],
                 font=(self.ui_font_name, 11)).pack()
        tk.Label(body, text="Mini IDE para: C, Java, Python, HTML, CSS e JavaScript. "
                            "Feito em Python.", bg=C["sidebar"], fg=C["fg_dim"],
                 font=self.ui_small, justify="center").pack(pady=(8, 4))
        tk.Label(body, text="Desenvolvido por Davi Reis", bg=C["sidebar"], fg=C["fg"],
                 font=self.ui_bold).pack(pady=(0, 14))
        tk.Frame(body, bg=C["popup_border"], height=1).pack(fill="x")

        def block(title):
            row = tk.Frame(body, bg=C["sidebar"])
            row.pack(fill="x", pady=(12, 0))
            tk.Label(row, text=title, bg=C["sidebar"], fg=C["fg"], font=self.ui_bold).pack(
                side="left")
            val = tk.Label(row, text="…", bg=C["sidebar"], fg=C["fg_bright"], font=self.ui_bold)
            val.pack(side="right")
            cv = tk.Canvas(body, width=340, height=44, bg=C["editor"], highlightthickness=1,
                           highlightbackground=C["popup_border"])
            cv.pack(fill="x", pady=(4, 0))
            return val, cv

        ram_val, ram_cv = block("Memória RAM")
        cpu_val, cpu_cv = block("Processador (CPU)")
        so = "Windows" if IS_WIN else "macOS" if IS_MAC else "Linux"
        tk.Label(body, text=f"Consumo do próprio {APP}, atualizado a cada segundo.",
                 bg=C["sidebar"], fg=C["fg_dim"], font=self.ui_small).pack(pady=(10, 0))
        tk.Label(body, text=f"Python {sys.version.split()[0]}   •   Tk {tk.TkVersion}   •   {so}",
                 bg=C["sidebar"], fg=C["fg_dim"], font=self.ui_small).pack(pady=(2, 0))
        btn = tk.Label(body, text="Fechar", bg=C["accent"], fg=C["on_accent"], font=self.ui_small,
                       padx=22, pady=5, cursor="hand2")
        btn.pack(pady=(16, 0))
        btn.bind("<Button-1>", lambda e: win.destroy())
        btn.bind("<Enter>", lambda e: btn.configure(bg=C["accent_hover"]))
        btn.bind("<Leave>", lambda e: btn.configure(bg=C["accent"]))
        win.bind("<Escape>", lambda e: win.destroy())

        stats = ProcStats()
        cpu_h = [0.0] * 60
        ram_h = [stats.rss() / 1048576.0] * 60
        ram_val.configure(text=fmt_bytes(ram_h[-1] * 1048576.0))
        cpu_val.configure(text="0.0%")

        def graph(cv, hist, color, top):
            cv.delete("all")
            w, h = max(cv.winfo_width(), 60), max(cv.winfo_height(), 20)
            for k in (1, 2, 3):
                cv.create_line(0, h * k / 4, w, h * k / 4, fill=_mix(C["editor"], C["fg"], .08))
            step = w / (len(hist) - 1)
            pts = [(i * step, h - 2 - (h - 4) * min(v / top, 1.0)) for i, v in enumerate(hist)]
            area = [(0, h)] + pts + [(w, h)]
            cv.create_polygon(*[c for p in area for c in p], fill=_mix(C["editor"], color, .28),
                              outline="")
            cv.create_line(*[c for p in pts for c in p], fill=color, width=2)

        def tick():
            try:
                if not win.winfo_exists():
                    return
                cpu, rss = stats.sample()
                cpu_h.append(cpu)
                del cpu_h[0]
                ram_h.append(rss / 1048576.0)
                del ram_h[0]
                ram_val.configure(text=fmt_bytes(rss))
                cpu_val.configure(text=f"{cpu:.1f}%")
                graph(ram_cv, ram_h, C["info"], max(max(ram_h) * 1.25, 1.0))
                graph(cpu_cv, cpu_h, C["ok"] if cpu < 50 else C["warn"] if cpu < 80 else C["err"],
                      max(10.0, max(cpu_h) * 1.25))
                win._job = win.after(1000, tick)
            except tk.TclError:
                pass

        def on_destroy(e):
            if e.widget is win:
                try:
                    win.after_cancel(getattr(win, "_job", ""))
                except (tk.TclError, ValueError):
                    pass

        win.bind("<Destroy>", on_destroy)
        win._job = win.after(300, tick)
        win.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - win.winfo_reqwidth()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - win.winfo_reqheight()) // 3
        win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        win.focus_set()

    def show_shortcuts(self):
        m = MOD_LABEL
        messagebox.showinfo("Atalhos", "\n".join([
            "F5 .......................... Executar",
            "F6 .......................... Compilar / verificar sintaxe",
            "F7 .......................... Abrir no navegador",
            "Shift+F5 .................... Parar execução",
            "F8 .......................... Gerar .exe (arquivo Python)",
            f"{m}+N / O / S ........... Novo / Abrir / Salvar",
            f"{m}+Shift+S ............... Salvar como",
            f"{m}+Shift+O ............... Abrir pasta",
            f"{m}+W ..................... Fechar aba",
            f"{m}+F / H ................. Localizar / Substituir",
            f"{m}+G ..................... Ir para linha",
            f"{m}+/ ..................... Comentar/descomentar",
            f"{m}+Shift+[ / ] ........... Recolher / expandir o bloco (função, classe, tag...)",
            "Setinha na margem ........... Recolher / expandir o bloco da linha (⋯ também abre)",
            f"{m}+B / J ................. Explorador / Painel",
            f"{m}+, ..................... Configurações",
            f"{m}+ + / - / 0 ............ Zoom da fonte",
            "Tab / Shift+Tab ............. Indentar / Desindentar",
            f"{m}+\\ ..................... Dividir editor (lado a lado)",
            f"{m}+1 / 2 / 3 ............. Focar a coluna 1 / 2 / 3",
            f"{m}+Shift+N ............... Novo arquivo fora da pasta",
            "Ctrl+Espaço ................. Mostrar sugestões de código",
            "Setas / Tab / Enter ......... Escolher / aceitar a sugestão",
            "Arrastar uma aba ............ Soltar na borda do editor = dividir; no meio = mover",
            "Sugestão de trecho + Tab .... Completa a linha toda; Tab pula para o próximo ponto",
            "Explorador: arrastar ........ Mover arquivo (segure Ctrl: copiar)",
            "Explorador: Delete .......... Excluir o item selecionado",
            "HTML: ! + Tab ............... Estrutura básica da página",
            "HTML: digitar > ............. Fecha a tag automaticamente",
        ]))

    # ----- executar ---------------------------------------------------------- #
    def make_plan(self, ed, run):
        T = self.tools or {}
        lang = ed.lang
        cwd = os.path.dirname(ed.path)
        base = os.path.basename(ed.path)
        stem = os.path.splitext(base)[0] or "prog"
        envc = dict(os.environ, LC_ALL="C", LANG="C", LANGUAGE="en")
        envr = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1", PYTHONUNBUFFERED="1")
        plan = dict(lang=lang, cwd=cwd, compile=None, run=None, envc=envc, envr=envr,
                    verb="compilação", ok_msg="Compilado com sucesso")

        def missing(what):
            self.show_panel("output")
            self.out(f"⚠ {what} não encontrado.\n", "warn")
            self.show_install_help()
            return None

        if lang == "c":
            cc = T.get("cc")
            if not cc:
                return missing("Compilador C (gcc/clang/tcc)")
            is_tcc = "tcc" in os.path.basename(cc).lower()
            exe = os.path.join(self.build_dir, f"{stem}_{self.run_id + 1}{EXE}")
            cmd = [cc, ed.path]
            if not is_tcc:
                cmd.append(f"-std={self.std.get()}")
            if self.warn_var.get():
                cmd += ["-Wall", "-Wextra"]
            if self.opt_var.get():
                cmd.append("-O2")
            if not is_tcc:
                prelude = os.path.join(self.build_dir, "_ide_prelude.h")
                with open(prelude, "w") as f:     # stdout sem buffer: prompts aparecem na hora
                    f.write("#include <stdio.h>\n__attribute__((constructor)) static void "
                            "__ide_unbuf(void){setvbuf(stdout,NULL,_IONBF,0);"
                            "setvbuf(stderr,NULL,_IONBF,0);}\n")
                cmd += ["-include", prelude]
            cmd += ["-o", exe, "-lm"]
            plan["compile"] = cmd
            plan["run"] = [exe] if run else None
        elif lang == "java":
            javac, java = T.get("javac"), T.get("java")
            if not (javac and java):
                return missing("JDK (javac/java)")
            outdir = os.path.join(self.build_dir, "java")
            shutil.rmtree(outdir, ignore_errors=True)
            os.makedirs(outdir, exist_ok=True)
            main = java_main_class(ed.get_content(), stem)
            cmd = [javac, "-J-Duser.language=en", "-encoding", "UTF-8", "-sourcepath", cwd,
                   "-d", outdir]
            if self.warn_var.get():
                cmd.append("-Xlint:all")
            cmd.append(ed.path)
            plan["compile"] = cmd
            if run:
                plan["run"] = [java, "-Dfile.encoding=UTF-8", "-Dstdout.encoding=UTF-8",
                               "-cp", outdir + os.pathsep + cwd, main]
        elif lang == "python":
            py = T.get("python")
            if not py:
                return missing("Python")
            if run:
                plan["run"] = [py, "-u", ed.path]
            else:
                plan["compile"] = [py, "-c", "import ast,sys;ast.parse(open(sys.argv[1],"
                                   "encoding='utf-8').read(),sys.argv[1])", ed.path]
                plan["verb"], plan["ok_msg"] = "verificação", "Nenhum erro de sintaxe"
        elif lang == "js":
            node = T.get("node")
            if not node:
                if run:
                    self.out("Node.js não encontrado — executando no navegador "
                             "(o console aparece na página).\n", "warn")
                    self.preview(ed)
                    return None
                return missing("Node.js")
            if run:
                plan["run"] = [node, ed.path]
            else:
                plan["compile"] = [node, "--check", ed.path]
                plan["verb"], plan["ok_msg"] = "verificação", "Nenhum erro de sintaxe"
        return plan

    def build_exe(self):
        """Compila o arquivo Python aberto num executável único (.exe) com o PyInstaller."""
        ed = self.active
        if not ed:
            return
        if ed.lang != "python":
            self.show_panel("output")
            self.out("Gerar .exe funciona só para arquivos Python (.py).\n", "warn")
            return
        self.build(False, exe=True)

    def make_exe_plan(self, ed):
        py = (self.tools or {}).get("python")
        if not py:
            self.show_panel("output")
            self.out("⚠ Python não encontrado.\n", "warn")
            self.show_install_help()
            return None
        cwd = os.path.dirname(ed.path)
        stem = os.path.splitext(os.path.basename(ed.path))[0] or "prog"
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
        plan = dict(lang="python", cwd=cwd, compile=None, run=None, envc=env, envr=env,
                    verb="geração do executável", ok_msg="Executável gerado",
                    busy="⏳ Gerando o executável (pode levar um minuto)…",
                    result=os.path.join(cwd, stem + EXE))
        try:
            have = subprocess.run([py, "-c", "import PyInstaller"], capture_output=True,
                                  creationflags=NOWIN, timeout=60).returncode == 0
        except (OSError, subprocess.SubprocessError):
            have = False
        if not have:
            if not messagebox.askyesno(
                    "Gerar .exe", "Para gerar o executável é preciso o PyInstaller, que ainda "
                    "não está instalado neste Python.\n\nInstalar agora com o pip? "
                    "(precisa de internet)", parent=self.root):
                return None
            plan["pre"] = [py, "-m", "pip", "install", "--upgrade", "pyinstaller"]
        work = os.path.join(self.build_dir, "pyinstaller")
        cmd = [py, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--name", stem,
               "--distpath", cwd, "--workpath", work, "--specpath", work]
        if self.noconsole_var.get():
            cmd.append("--noconsole")
        ico = os.path.join(cwd, stem + ".ico")
        if os.path.isfile(ico):
            cmd += ["--icon", ico]
        plan["compile"] = cmd + [ed.path]
        return plan

    def build(self, run=True, exe=False):
        ed = self.active
        if not ed:
            return
        if ed.lang == "text":
            self.show_panel("output")
            self.out("Este tipo de arquivo não é executável. Use Executar › ou mude a "
                     "linguagem na barra de status.\n", "warn")
            return
        if self.tools is None:
            self.show_panel("output")
            self.out("Aguarde: ainda detectando as ferramentas instaladas…\n", "dim")
            return
        self.stop(silent=True)
        if not ed.path or ed.modified:
            if not self.save(ed):
                return
        if ed.lang in ("html", "css"):
            return self.preview(ed)
        plan = self.make_exe_plan(ed) if exe else self.make_plan(ed, run)
        if plan is None:
            return
        self.run_id += 1
        rid = self.run_id
        self.plan = plan
        self.run_cwd = plan["cwd"]
        self.compiled_editor = ed
        self.pending_run = run
        self.run_output = ""
        self.clear_output()
        self.set_problems([])
        ed.clear_diagnostics()
        self.show_panel("output")
        if plan["compile"]:
            self.compiling = True
            self.out(f"$ {disp(plan['compile'])}\n", "dim")
            self.set_status(plan.get("busy") or ("⏳ Compilando…" if plan["verb"] == "compilação"
                                                 else "⏳ Verificando…"))
            cmd, env, cwd, pre = plan["compile"], plan["envc"], plan["cwd"], plan.get("pre")
            if pre:
                self.out(f"$ {disp(pre)}\n", "dim")

            def work():
                t0 = time.time()
                text = ""
                try:
                    for step in ([pre] if pre else []) + [cmd]:
                        r = subprocess.run(step, capture_output=True, text=True,
                                           encoding="utf-8", errors="replace", cwd=cwd, env=env,
                                           creationflags=NOWIN)
                        text += (r.stdout or "") + (r.stderr or "")
                        if r.returncode != 0:
                            break
                    self.q.put(("compiled", rid, r.returncode, text, time.time() - t0))
                except Exception as ex:      # noqa
                    self.q.put(("compiled", rid, -1, text + f"Falha ao iniciar a ferramenta: {ex}\n",
                                time.time() - t0))

            threading.Thread(target=work, daemon=True).start()
        else:
            self.out(f"$ {disp(plan['run'])}\n", "dim")
            self.start_process()

    def on_compiled(self, rc, output, elapsed):
        self.compiling = False
        plan = self.plan
        for line in output.splitlines():
            low = line.lower()
            tag = None
            if re.search(r"\b(error|erro)\b|undefined reference|ld returned|exception", low):
                tag = "err"
            elif re.search(r"\b(warning|aviso)\b", low):
                tag = "warn"
            elif re.search(r"\b(note|nota)\b:", low):
                tag = "dim"
            self.out(line + "\n", tag)
        probs = parse_diagnostics(output)
        if not probs and rc != 0:
            probs = parse_runtime(plan["lang"], output, plan["cwd"])
        self.set_problems(probs)
        self.apply_diagnostics(self.compiled_editor, probs)
        errs = sum(1 for p in probs if p["sev"] == "error")
        warns = sum(1 for p in probs if p["sev"] == "warning")
        extra = f", {warns} aviso(s)" if warns else ""
        if rc != 0:
            detail = f" ({errs} erro(s){extra})" if errs or extra else ""
            self.out(f"\n✖ Falha na {plan['verb']}{detail}\n", "err")
            self.set_status(f"✖ Erro de {plan['verb']}")
            if errs:
                self.show_panel("problems")
        else:
            self.out(f"\n✔ {plan['ok_msg']} em {elapsed:.2f}s{extra}\n", "ok")
            if plan.get("result"):
                self.out(f"📦 {plan['result']}\n", "info")
                if not IS_WIN:
                    self.out("Obs.: fora do Windows o PyInstaller gera um executável do próprio "
                             "sistema, não um .exe.\n", "dim")
            if self.pending_run and plan["run"]:
                if plan["lang"] == "c":
                    self.start_external()
                else:
                    self.start_process()
            else:
                self.set_status("✔ Pronto")

    def start_external(self):
        """Roda o programa (C) numa janela de terminal separada, com entrada/saída próprias."""
        plan = self.plan
        exe, cwd = plan["run"][0], plan["cwd"]
        name = os.path.basename(plan["run"][0])
        try:
            if IS_WIN:
                cmdline = (f'cmd /c "chcp 65001 >nul & title {APP} - {name} & "{exe}" '
                           f'& echo. & echo [Programa finalizado] & pause"')
                subprocess.Popen(cmdline, cwd=cwd,
                                 creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                script = os.path.join(self.build_dir, f"_run_{self.run_id}"
                                      + (".command" if IS_MAC else ".sh"))
                with open(script, "w", encoding="utf-8", newline="\n") as f:
                    f.write("#!/bin/sh\n"
                            f"cd {shlex.quote(cwd)}\n"
                            f"{shlex.quote(exe)}\n"
                            "rc=$?\n"
                            "echo\n"
                            'echo "[Programa finalizado com código $rc]"\n'
                            'printf "Pressione Enter para fechar..."\n'
                            "read _\n")
                os.chmod(script, 0o755)
                if IS_MAC:
                    subprocess.Popen(["open", "-a", "Terminal", script])
                else:
                    term = None
                    for n, args in (("gnome-terminal", ["--"]), ("kgx", ["-e"]),
                                    ("konsole", ["-e"]), ("xfce4-terminal", ["-x"]),
                                    ("mate-terminal", ["-x"]), ("tilix", ["-e"]),
                                    ("lxterminal", ["-e"]), ("kitty", []),
                                    ("alacritty", ["-e"]), ("x-terminal-emulator", ["-e"]),
                                    ("xterm", ["-e"])):
                        path = shutil.which(n)
                        if path:
                            term = [path] + args + ["sh", script]
                            break
                    if term is None:
                        self.out("Nenhum emulador de terminal encontrado "
                                 "(gnome-terminal, konsole, xterm…).\n", "err")
                        self.set_status("✖ Terminal não encontrado")
                        return
                    subprocess.Popen(term, cwd=cwd)
        except OSError as e:
            self.out(f"Não foi possível abrir o terminal: {e}\n", "err")
            self.set_status("✖ Erro ao executar")
            return
        self.out("🖥 Programa aberto em uma janela de terminal separada.\n", "ok")
        self.set_status("▶ Rodando em outra janela")

    def start_process(self):
        plan = self.plan
        try:
            self.proc = subprocess.Popen(
                plan["run"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, cwd=plan["cwd"], env=plan["envr"], bufsize=0,
                creationflags=NOWIN)
        except OSError as e:
            self.out(f"Não foi possível executar o programa: {e}\n", "err")
            self.set_status("✖ Erro ao executar")
            return
        self.running = True
        self.stopped = False
        self.start_time = time.time()
        self.out("── Executando ──\n", "dim")
        self.set_status("▶ Executando…")
        self.btn_stop.configure(fg=C["err"])
        self.stdin_entry.configure(state="normal")
        self.stdin_entry.focus_set()
        threading.Thread(target=self._reader, args=(self.proc, self.run_id), daemon=True).start()

    def _reader(self, proc, rid):
        fd = proc.stdout.fileno()
        dec = codecs.getincrementaldecoder("utf-8")(errors="replace")
        while True:
            try:
                data = os.read(fd, 4096)
            except OSError:
                break
            if not data:
                break
            self.q.put(("out", rid, dec.decode(data)))
        self.q.put(("exit", rid, proc.wait()))

    def send_input(self, _e=None):
        s = self.stdin_var.get()
        self.stdin_var.set("")
        if not (self.running and self.proc and self.proc.stdin):
            return
        try:
            self.proc.stdin.write((s + "\n").encode("utf-8"))
            self.proc.stdin.flush()
            self.out(s + "\n", "input")
        except (OSError, ValueError):
            pass

    def on_exit(self, rc):
        self.running = False
        dt = time.time() - self.start_time
        msg, tag = describe_exit(rc)
        self.out(f"\n[Processo {msg} em {dt:.2f}s]\n", tag)
        self.stdin_entry.configure(state="disabled")
        self.btn_stop.configure(fg=C["fg_dim"])
        if rc != 0 and self.plan:
            probs = parse_runtime(self.plan["lang"], self.run_output, self.plan["cwd"])
            if probs:
                self.set_problems(probs)
                self.apply_diagnostics(self.compiled_editor, probs)
        self.set_status("✔ Pronto" if rc == 0 else "● Programa terminou com erro")

    def stop(self, silent=False):
        if self.running and self.proc:
            try:
                self.proc.kill()
            except OSError:
                pass
            if not silent:
                self.out("\n[Processo interrompido pelo usuário]\n", "warn")
        if self.running or self.compiling:
            self.run_id += 1
        self.running = False
        self.compiling = False
        self.stdin_entry.configure(state="disabled")
        self.btn_stop.configure(fg=C["fg_dim"])
        if not silent:
            self.set_status("✔ Pronto")

    # ----- navegador (HTML / CSS / JS) --------------------------------------- #
    def open_in_browser(self):
        ed = self.active
        if not ed:
            return
        if ed.lang not in ("html", "css", "js"):
            self.show_panel("output")
            self.out("“Abrir no navegador” funciona para arquivos HTML, CSS e JS.\n", "warn")
            return
        if not ed.path or (ed.modified and not self.live_on.get()):
            if not self.save(ed):
                return
        self.preview(ed)

    def _gen_page(self, kind, src_path):
        """Página auxiliar (console de JS / exemplo de CSS): devolve (caminho virtual, HTML)."""
        name = os.path.basename(src_path)
        tpl = JS_RUNNER if kind == "js" else CSS_SAMPLE
        page = tpl.replace("__NAME__", htmlmod.escape(name)).replace(
            "__SRC__", "./" + urllib.parse.quote(name))
        return os.path.join(os.path.dirname(src_path), f"__kcode_{kind}__.html"), page

    def preview(self, ed):
        lang, target, note, page = ed.lang, None, "", None
        if lang == "html":
            target = ed.path
        elif lang == "css":
            d = os.path.dirname(ed.path)
            cands = [t.path for t in self.tabs if t.lang == "html" and t.path
                     and os.path.dirname(t.path) == d]
            idx = os.path.join(d, "index.html")
            if cands:
                target = cands[0]
            elif os.path.isfile(idx):
                target = idx
            else:
                files = sorted(glob.glob(os.path.join(d, "*.html")))
                target = files[0] if files else None
            if target:
                note = (f"Usando {os.path.basename(target)} — se o estilo não aparecer, confira "
                        "se ele tem <link rel=\"stylesheet\"> apontando para este CSS.")
            else:
                target, page = self._gen_page("css", ed.path)
                note = "Nenhum HTML na pasta: usando uma página de exemplo para testar o CSS."
        elif lang == "js":
            target, page = self._gen_page("js", ed.path)
        self.show_panel("output")
        self.clear_output()
        self.set_problems([])
        try:
            uri = self.live_serve(target, page)
        except OSError as ex:
            if page is not None:
                self.out(f"Não foi possível iniciar o servidor local: {ex}\n", "err")
                return
            uri = pathlib.Path(target).as_uri()
        ok = False
        try:
            ok = webbrowser.open(uri)
        except Exception:      # noqa
            pass
        if ok:
            live = uri.startswith("http") and self.live_on.get()
            self.out(f"🌐 {os.path.basename(ed.path)} aberto no navegador."
                     + (" Ele atualiza sozinho enquanto você edita." if live else "") + "\n", "ok")
            if uri.startswith("http"):
                self.out(uri + "\n", "dim")
            if note:
                self.out(note + "\n", "dim")
            self.set_status("🌐 Aberto no navegador")
        else:
            self.out(f"Não foi possível abrir o navegador. Abra manualmente:\n{uri}\n", "err")

    # ----- ícone ------------------------------------------------------------- #
    def set_app_icon(self):
        try:
            self.icons = [make_app_icon(n) for n in (64, 32, 16)]
            self.root.iconphoto(True, *self.icons)
        except tk.TclError:
            pass

    def _new_content(self, name, ext, with_tpl):
        lang = lang_for(name + ext)
        if not (with_tpl and lang in TEMPLATES):
            return ""
        content = TEMPLATES[lang]
        if lang == "java":
            content = re.sub(r"\bMain\b", name, content)
        return content

    # ----- navegador com atualização automática ---------------------------------- #
    def live_serve(self, path, page=None):
        """Garante um servidor local para `path` e devolve a URL dele.

        `page` (opcional) é um HTML gerado pela IDE que não existe no disco."""
        path = os.path.abspath(path)
        root = self.folder if self.folder and self._under(path, self.folder) \
            else os.path.dirname(path)
        key = os.path.normcase(os.path.abspath(root))
        srv = self.live.get(key)
        if srv is None:
            srv = self.live[key] = LiveServer(root)
        if page is not None:
            srv.set_virtual(path, page.encode("utf-8"))
        if self.live_on.get():
            self.live_sync(srv)
        rel = os.path.relpath(path, srv.root).replace(os.sep, "/")
        return f"http://127.0.0.1:{srv.port}/{urllib.parse.quote(rel)}"

    def live_sync(self, srv):
        """Entrega ao servidor o texto atual de todas as abas que ele cobre."""
        for ed in self.tabs:
            if ed.path and srv.covers(ed.path):
                srv.set_live(ed.path, ed.get_content().encode("utf-8"))

    def live_changed(self, ed):
        """Chamado a cada edição: espera o usuário parar de digitar e recarrega o site."""
        if not self.live or not ed.path or not self.live_on.get():
            return
        self.live_pending.add(ed)
        if self.live_job is not None:
            self.root.after_cancel(self.live_job)
        self.live_job = self.root.after(250, self._live_push)

    def _live_push(self):
        self.live_job = None
        eds, self.live_pending = self.live_pending, set()
        for srv in list(self.live.values()):
            hit = False
            for ed in eds:
                if ed.path and srv.covers(ed.path):
                    try:
                        srv.set_live(ed.path, ed.get_content().encode("utf-8"))
                    except tk.TclError:                    # aba fechada nesse meio tempo
                        continue
                    hit = True
            if hit:
                srv.bump()

    def live_forget(self, path):
        for srv in self.live.values():
            if srv.covers(path):
                srv.drop_live(path)
                if self.live_on.get():
                    srv.bump()

    def live_toggle(self):
        for srv in self.live.values():
            if self.live_on.get():
                self.live_sync(srv)
                srv.bump()
            else:
                srv.clear_live()
        self.set_status("🌐 Atualização automática " +
                        ("ligada" if self.live_on.get() else "desligada"))

    # ----- laço de eventos --------------------------------------------------- #
    def on_tools(self, tools):
        self.tools = tools
        self.update_tool_status()
        self.set_status("✔ Pronto")
        names = [("C", "cc"), ("Java", "javac"), ("Python", "python"), ("Node.js", "node")]
        line = "  ".join(f"{n} {'✔' if tools.get(k) else '✖'}" for n, k in names)
        self.out(f"Ferramentas: {line}  HTML/CSS ✔ (navegador)\n", "info")
        missing = [n for n, k in names if not tools.get(k)]
        if missing:
            self.out(f"Não encontrado: {', '.join(missing)} — veja Ajuda › Instalar "
                     "compiladores e interpretadores.\n", "dim")

    def poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "tools":
                    self.on_tools(msg[2])
                    continue
                if msg[1] != self.run_id:
                    continue
                if msg[0] == "out":
                    self.run_output = (self.run_output + msg[2])[-200000:]
                    self.out(msg[2])
                elif msg[0] == "compiled":
                    self.on_compiled(*msg[2:])
                elif msg[0] == "exit":
                    self.on_exit(msg[2])
        except queue.Empty:
            pass
        self.root.after(30, self.poll)

    # ----- sair -------------------------------------------------------------- #
    def quit(self):
        for ed in list(self.tabs):
            if ed.modified:
                self.activate(ed)
                if not self.close_tab(ed):
                    return
        self.stop(silent=True)
        shutil.rmtree(self.build_dir, ignore_errors=True)
        self.root.destroy()


def main():
    if IS_WIN:
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("KCode.IDE")
        except Exception:
            pass
    if any(k in read_config() for k in ("ai_key", "ai_url", "ai_model")):
        update_config(ai_key=None, ai_url=None, ai_model=None)   # restos da antiga função de IA
    root = tk.Tk()
    try:
        root.tk.call("tk", "scaling", root.winfo_fpixels("1i") / 72.0)
    except tk.TclError:
        pass
    App(root, sys.argv[1:])
    root.mainloop()


if __name__ == "__main__":
    main()