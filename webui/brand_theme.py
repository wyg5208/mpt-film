"""ChangoFilm 品牌主题：定稿商标「霓虹快门 Shutter C」的产品侧生效层。

职责：
- 向页面注入品牌 CSS 变量（强调色 / 背景场 / 光晕 / 圆角 / 动效 / 密度）与 brand.css；
- 提供顶栏 h1 与左导航的品牌标识 SVG；
- 提供常驻主题控制区（左导航展开态 + 设置对话框「品牌主题」TAB），
  控件改动经 session_state["cf_theme"] 立即重渲染生效。

几何常量与 docs/changofilm-logo/build-brand.mjs 保持同源。
"""

from pathlib import Path

import streamlit as st

_CSS_FILE = Path(__file__).with_name("brand.css")
ICON_FILE = Path(__file__).with_name("brand") / "changofilm-mark-192.png"

DEFAULTS = {
    "accent": "magenta",
    "field": "deep",
    "glow": 45,
    "radius": 12,
    "motion": True,
    "logo": True,
    "density": "cozy",
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
    return t


def _field_bg(field, a, b):
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
    return (
        "<style>:root{"
        f"--cf-accent:{c['a']};--cf-accent-2:{c['b']};--cf-accent-pale:{c['pale']};--cf-accent-deep:{c['deep']};"
        "--cf-bg:#0D0714;--cf-bg2:#140B1F;--cf-surface:#1B1029;--cf-surface2:#241636;"
        "--cf-line:#3A2452;--cf-line-soft:#2A1A3C;--cf-ink:#F7F2FA;--cf-muted:#B49CC6;"
        f"--cf-link:{c['pale']};--cf-glow:{t['glow']};--cf-radius:{t['radius']}px;"
        f"--cf-play:{play};--cf-pad-top:{pad};--cf-gap:{gap};"
        f"--cf-field-bg:{_field_bg(t['field'], c['a'], c['b'])};"
        f"--st-primary-color:{c['a']};--st-link-color:{c['pale']};"
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


def lockup_svg():
    global _uid
    _uid += 1
    gid = f"cfl{_uid}"
    return (
        f'<svg viewBox="0 0 340 100" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="ChangoFilm">'
        f'<defs><linearGradient id="{gid}t" gradientUnits="userSpaceOnUse" x1="228" y1="50" x2="334" y2="50">'
        f'<stop offset="0" stop-color="#EC4899"/><stop offset="1" stop-color="#8B5CF6"/></linearGradient></defs>'
        f'<g transform="translate(4 4) scale(0.92)">{_mark_inner(gid)}</g>'
        f'<text x="112" y="64" font-family="Inter,\'Segoe UI\',\'Microsoft YaHei\',sans-serif" font-size="37" '
        f'font-weight="600" fill="#F7F2FA">Chango<tspan font-weight="800" fill="url(#{gid}t)">Film</tspan></text></svg>'
    )


def render_nav_brand(collapsed):
    if not theme()["logo"]:
        return
    if collapsed:
        st.markdown(f'<div class="cf-nav-mark">{mark_svg()}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="cf-nav-lockup">{lockup_svg()}</div>', unsafe_allow_html=True)


_FIELDS = ("accent", "field", "glow", "radius", "motion", "logo", "density")


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
    for prefix in ("cfnav", "cfset"):
        for field in _FIELDS:
            st.session_state[f"{prefix}_{field}"] = DEFAULTS[field]
    st.rerun(scope="app")


def render_controls(prefix, tr):
    """常驻主题控制区：8 项工具，改动即生效（on_change 同步会话主题）。"""
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
    st.markdown(
        f'<div class="cf-theme-title">{tr("Theme Panel Title")}</div>',
        unsafe_allow_html=True,
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