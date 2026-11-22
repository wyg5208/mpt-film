"""ChangoFilm 品牌主题：定稿商标「霓虹快门 Shutter C」的产品侧生效层。

职责：
- 向页面注入品牌 CSS 变量（明暗模式 / 强调色 / 背景场 / 光晕 / 圆角 / 动效 / 密度）与 brand.css；
- 提供顶栏 h1 的品牌标识 SVG；
- 提供主题控制区（设置对话框与设置页的「品牌主题」TAB），
  控件改动经 session_state["cf_theme"] 立即重渲染生效。

几何常量与 docs/changofilm-logo/build-brand.mjs 保持同源。
"""

from pathlib import Path

import streamlit as st

_CSS_FILE = Path(__file__).with_name("brand.css")
ICON_FILE = Path(__file__).with_name("brand") / "changofilm-mark-192.png"

DEFAULTS = {
    "mode": "dark",
    "accent": "magenta",
    "field": "deep",
    "glow": 45,
    "radius": 12,
    "motion": True,
    "logo": True,
    "density": "cozy",
}

MODES = {"dark": "Theme Mode Dark", "light": "Theme Mode Light"}

# 两套表面调色板：浅色保持品牌紫罗兰底味，等价替换暗色的五组表面变量；
# 阴影变量同步给出暗色硬阴影与浅色软化版本，避免黑阴影压在浅底上。
_DARK_PALETTE = {
    "bg": "#0D0714",
    "bg2": "#140B1F",
    "surface": "#1B1029",
    "surface2": "#241636",
    "line": "#3A2452",
    "line_soft": "#2A1A3C",
    "ink": "#F7F2FA",
    "muted": "#B49CC6",
    "shadow_strong": "0 24px 64px rgba(0, 0, 0, 0.55)",
    "shadow_bar": "0 8px 24px rgba(0, 0, 0, 0.45)",
    "shadow_row": "0 4px 16px rgba(0, 0, 0, 0.4)",
}
_LIGHT_PALETTE = {
    "bg": "#F4F1F8",
    "bg2": "#FBF9FD",
    "surface": "#FFFFFF",
    "surface2": "#F7F4FB",
    "line": "#DCD2EA",
    "line_soft": "#E9E2F4",
    "ink": "#1D1330",
    "muted": "#6F5C88",
    "shadow_strong": "0 24px 64px rgba(29, 19, 48, 0.22)",
    "shadow_bar": "0 8px 24px rgba(29, 19, 48, 0.16)",
    "shadow_row": "0 4px 16px rgba(29, 19, 48, 0.14)",
}

ACCENTS = {
    "magenta": {"a": "#EC4899", "b": "#8B5CF6", "pale": "#F5D0FE", "deep": "#C026D3", "label": "Accent Magenta"},
    "violet": {"a": "#8B5CF6", "b": "#EC4899", "pale": "#DDD6FE", "deep": "#6D28D9", "label": "Accent Violet"},
    "cyan": {"a": "#22D3EE", "b": "#0D9488", "pale": "#CFFAFE", "deep": "#0E7490", "label": "Accent Cyan"},
}
FIELDS = {"deep": "Field Deep", "black": "Field Black", "aurora": "Field Aurora"}
DENSITIES = {"cozy": "Density Cozy", "compact": "Density Compact"}

_BLADE = "M50 10 A40 40 0 0 1 84.64 30 L62 42 A16 16 0 0 0 50 34 Z"
_ROTS = (0, 120, 180, 240, 300)
_TRI = "M62 42 L62 58 L76 50 Z"
_uid = 0


def theme():
    t = st.session_state.get("cf_theme")
    if not isinstance(t, dict):
        t = dict(DEFAULTS)
        st.session_state["cf_theme"] = t
    for key, value in DEFAULTS.items():
        t.setdefault(key, value)
    if t.get("accent") not in ACCENTS:
        t["accent"] = DEFAULTS["accent"]
    if t.get("field") not in FIELDS:
        t["field"] = DEFAULTS["field"]
    if t.get("density") not in DENSITIES:
        t["density"] = DEFAULTS["density"]
    if t.get("mode") not in MODES:
        t["mode"] = DEFAULTS["mode"]
    return t


def _field_bg(field, a, b, mode):
    if mode == "light":
        if field == "black":
            return _LIGHT_PALETTE["bg2"]
        if field == "aurora":
            return (
                f"radial-gradient(circle at 18% 12%, {a}26, transparent 55%), "
                f"radial-gradient(circle at 85% 88%, {b}28, transparent 52%), "
                f"radial-gradient(circle at 60% 40%, {a}12, transparent 60%), "
                f"{_LIGHT_PALETTE['bg']}"
            )
        return (
            f"radial-gradient(circle at 50% 0%, {b}1a, transparent 60%), "
            f"{_LIGHT_PALETTE['bg']}"
        )
    if field == "black":
        return "#000000"
    if field == "aurora":
        return (
            f"radial-gradient(circle at 18% 12%, {a}2e, transparent 55%), "
            f"radial-gradient(circle at 85% 88%, {b}30, transparent 52%), "
            f"radial-gradient(circle at 60% 40%, {a}14, transparent 60%), #0D0714"
        )
    return f"radial-gradient(circle at 50% 0%, {b}1f, transparent 60%), #0D0714"


def variables_css():
    t = theme()
    c = ACCENTS[t["accent"]]
    play = "running" if t["motion"] else "paused"
    pad = "0.5rem" if t["density"] == "cozy" else "0.2rem"
    gap = "1rem" if t["density"] == "cozy" else "0.55rem"
    light = t["mode"] == "light"
    p = _LIGHT_PALETTE if light else _DARK_PALETTE
    # 浅色下以强调深色替代浅粉：链接、悬停、选中文字在白底上保持可读。
    pale = c["deep"] if light else c["pale"]
    scheme = "light" if light else "dark"
    mark_tri = c["deep"] if light else "#F5D0FE"
    # 浅色需同时覆写 Streamlit 基础变量（--st-* 与旧无前缀名双写），
    # 否则未走 --cf-* 的通用文字/输入面仍继承暗色主题的浅色字。
    st_overrides = (
        (
            f"--st-text-color:{p['ink']};--st-background-color:{p['bg']};"
            f"--st-secondary-background-color:{p['surface']};"
            f"--text-color:{p['ink']};--background-color:{p['bg']};"
            f"--secondary-background-color:{p['surface']};"
        )
        if light
        else ""
    )
    return (
        "<style>:root{"
        f"color-scheme:{scheme};"
        f"--cf-accent:{c['a']};--cf-accent-2:{c['b']};--cf-accent-pale:{pale};--cf-accent-deep:{c['deep']};"
        f"--cf-bg:{p['bg']};--cf-bg2:{p['bg2']};--cf-surface:{p['surface']};--cf-surface2:{p['surface2']};"
        f"--cf-line:{p['line']};--cf-line-soft:{p['line_soft']};--cf-ink:{p['ink']};--cf-muted:{p['muted']};"
        f"--cf-link:{pale};--cf-glow:{t['glow']};--cf-radius:{t['radius']}px;"
        f"--cf-play:{play};--cf-pad-top:{pad};--cf-gap:{gap};"
        f"--cf-mark-tri:{mark_tri};"
        f"--cf-shadow-strong:{p['shadow_strong']};"
        f"--cf-shadow-bar:{p['shadow_bar']};"
        f"--cf-shadow-row:{p['shadow_row']};"
        f"--cf-field-bg:{_field_bg(t['field'], c['a'], c['b'], t['mode'])};"
        f"--st-primary-color:{c['a']};--st-link-color:{pale};"
        f"{st_overrides}"
        "}</style>"
    )


def inject():
    """在 styles.css 之后注入：变量层 + 品牌结构层（后者覆盖前者与站内旧色）。"""
    st.markdown(variables_css(), unsafe_allow_html=True)
    st.markdown(f"<style>{_CSS_FILE.read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)


def _mark_inner(grad_id):
    blades = "".join(
        f'<path d="{_BLADE}" transform="rotate({r} 50 50)" fill="url(#{grad_id})"/>'
        for r in _ROTS
    )
    return (
        f'<defs><linearGradient id="{grad_id}" gradientUnits="userSpaceOnUse" x1="50" y1="10" x2="84" y2="42">'
        f'<stop offset="0" stop-color="#EC4899"/><stop offset="1" stop-color="#8B5CF6"/>'
        f"</linearGradient></defs>{blades}"
        f'<path d="{_TRI}" fill="#F5D0FE"/>'
    )


def mark_svg():
    global _uid
    _uid += 1
    return (
        f'<svg class="cf-mark" viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="ChangoFilm">{_mark_inner(f"cfm{_uid}")}</svg>'
    )


_FIELDS = ("mode", "accent", "field", "glow", "radius", "motion", "logo", "density")


def _sync(prefix):
    t = theme()
    for field in _FIELDS:
        t[field] = st.session_state[f"{prefix}_{field}"]
    # 设置对话框是 fragment：内部控件改动默认只重跑 dialog，
    # 页面顶部的变量注入不会刷新；强制整页重跑让主题即时生效。
    st.rerun(scope="app")


def _reset():
    st.session_state["cf_theme"] = dict(DEFAULTS)
    # 不能 pop 控件键：前端控件状态会在下次 rerun 时把旧值写回，
    # 显式赋默认值才能让两处控制区与主题真正回到默认。
    # 设置页与设置弹窗两处控制区的前缀都要复位；旧 cfnav 前键随左导航撤场废弃。
    for prefix in ("cfset", "cfpage"):
        for field in _FIELDS:
            st.session_state[f"{prefix}_{field}"] = DEFAULTS[field]
    st.rerun(scope="app")


def render_controls(prefix, tr):
    """主题控制区：9 项工具（明暗模式等），改动即生效（on_change 同步会话主题）。"""
    t = theme()
    # 会话主题是唯一事实源：渲染前把控件键对齐到主题，
    # 避免前端旧控件状态回写造成控件与主题漂移。
    for field in _FIELDS:
        st.session_state[f"{prefix}_{field}"] = t[field]
    # format_func 必须是纯闭包：标签在渲染时预算，避免 AppTest 在 run 间
    # 重新求值 format_func 时 tr() 回退语言与已渲染 options 不一致。
    accent_labels = {key: tr(ACCENTS[key]["label"]) for key in ACCENTS}
    field_labels = {key: tr(FIELDS[key]) for key in FIELDS}
    density_labels = {key: tr(DENSITIES[key]) for key in DENSITIES}
    mode_labels = {key: tr(MODES[key]) for key in MODES}
    st.markdown(
        f'<div class="cf-theme-title">{tr("Theme Panel Title")}</div>',
        unsafe_allow_html=True,
    )
    st.selectbox(
        tr("Theme Mode"), list(MODES), index=list(MODES).index(t["mode"]),
        format_func=mode_labels.__getitem__,
        key=f"{prefix}_mode", on_change=_sync, args=(prefix,),
    )
    st.selectbox(
        tr("Theme Accent"), list(ACCENTS), index=list(ACCENTS).index(t["accent"]),
        format_func=accent_labels.__getitem__,
        key=f"{prefix}_accent", on_change=_sync, args=(prefix,),
    )
    st.selectbox(
        tr("Theme Field"), list(FIELDS), index=list(FIELDS).index(t["field"]),
        format_func=field_labels.__getitem__,
        key=f"{prefix}_field", on_change=_sync, args=(prefix,),
    )
    st.slider(
        tr("Theme Glow"), 0, 100, t["glow"],
        key=f"{prefix}_glow", on_change=_sync, args=(prefix,),
    )
    st.slider(
        tr("Theme Radius"), 4, 20, t["radius"],
        key=f"{prefix}_radius", on_change=_sync, args=(prefix,),
    )
    st.toggle(
        tr("Theme Motion"), value=t["motion"],
        key=f"{prefix}_motion", on_change=_sync, args=(prefix,),
    )
    st.toggle(
        tr("Theme Logo"), value=t["logo"],
        key=f"{prefix}_logo", on_change=_sync, args=(prefix,),
    )
    st.selectbox(
        tr("Theme Density"), list(DENSITIES), index=list(DENSITIES).index(t["density"]),
        format_func=density_labels.__getitem__,
        key=f"{prefix}_density", on_change=_sync, args=(prefix,),
    )
    st.button(
        tr("Theme Reset"), key=f"{prefix}_reset", on_click=_reset,
        icon=":material/restart_alt:", width="stretch",
    )