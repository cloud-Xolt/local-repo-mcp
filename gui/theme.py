from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    bg_app: str
    bg_sidebar: str
    bg_card: str
    bg_input: str
    bg_nav_active: str
    bg_feature_bar: str
    border: str
    text: str
    text_title: str
    text_muted: str
    text_hint: str
    accent: str
    accent_hover: str
    accent_link: str
    success: str
    success_bg: str
    danger: str
    nav_active_text: str
    header_btn: str
    header_btn_active: str


@dataclass(frozen=True)
class Typography:
    page_title: int = 32
    page_subtitle: int = 16
    section: int = 17
    label: int = 16
    body: int = 16
    hint: int = 13
    nav: int = 15
    brand: int = 16
    badge: int = 13
    feature_title: int = 15
    feature_desc: int = 13


TYPO = Typography()

# 布局：侧栏固定；主内容区 = 中间宽表单列 + 右侧窄信息列(固定宽) + 底部全宽区
SIDEBAR_WIDTH = 240
INFO_PANEL_WIDTH = 300
FORM_COL_GAP = 20
CONTENT_PADX = 32
CONTENT_PADY = 24
CARD_RADIUS = 14
INPUT_HEIGHT = 44
BTN_HEIGHT = 48

LIGHT = Theme(
    bg_app="#F5F7FA",
    bg_sidebar="#FFFFFF",
    bg_card="#FFFFFF",
    bg_input="#FFFFFF",
    bg_nav_active="#EFF6FF",
    bg_feature_bar="#EFF6FF",
    border="#E5E7EB",
    text="#111827",
    text_title="#111827",
    text_muted="#6B7280",
    text_hint="#9CA3AF",
    accent="#0066FF",
    accent_hover="#0052CC",
    accent_link="#0066FF",
    success="#16A34A",
    success_bg="#DCFCE7",
    danger="#DC2626",
    nav_active_text="#0066FF",
    header_btn="#6B7280",
    header_btn_active="#0066FF",
)

DARK = Theme(
    bg_app="#0F172A",
    bg_sidebar="#1E293B",
    bg_card="#1E293B",
    bg_input="#334155",
    bg_nav_active="#1E3A5F",
    bg_feature_bar="#1E293B",
    border="#334155",
    text="#F8FAFC",
    text_title="#F8FAFC",
    text_muted="#94A3B8",
    text_hint="#64748B",
    accent="#3B82F6",
    accent_hover="#60A5FA",
    accent_link="#60A5FA",
    success="#4ADE80",
    success_bg="#14532D",
    danger="#F87171",
    nav_active_text="#93C5FD",
    header_btn="#94A3B8",
    header_btn_active="#93C5FD",
)
