from __future__ import annotations

# A single, low-chroma design system shared by every GUI surface.  The warm
# neutrals borrow the calm reading experience of Claude while the compact
# hierarchy and restrained status accents are closer to developer tools such
# as Codex.  Keep semantic colours for meaning, never decoration.
COLORS = {
    "bg": ("#F7F6F2", "#111210"),
    "surface": ("#FFFFFF", "#1A1B18"),
    "surface_alt": ("#F1F0EB", "#23241F"),
    "surface_hover": ("#EAE8E1", "#2C2D27"),
    "sidebar": ("#EFEEE9", "#161714"),
    "sidebar_hover": ("#E5E3DC", "#242520"),
    "sidebar_active": ("#FFFFFF", "#2B2C26"),
    "text": ("#292824", "#F3F1EA"),
    "muted": ("#706E67", "#AAA79D"),
    "subtle": ("#99968D", "#77766F"),
    "border": ("#E3E0D8", "#34352F"),
    "border_strong": ("#D1CEC4", "#494A42"),
    "primary": "#AD5538",
    "primary_hover": "#91452E",
    "primary_text": "#FFFFFF",
    "primary_soft": ("#F3E7E1", "#3B2922"),
    "accent": "#C46643",
    "accent_hover": "#AA5436",
    "accent_soft": ("#F7E8E1", "#41261D"),
    "success": "#3F7D5D",
    "success_soft": ("#E6F1EA", "#1B3326"),
    "warning": "#A76A2B",
    "warning_soft": ("#F7ECD9", "#402E18"),
    "danger": "#B64A45",
    "danger_hover": "#9E3E3A",
    "danger_soft": ("#F6E4E2", "#402321"),
    "code": ("#F5F4F0", "#0E0F0D"),
    "overlay": ("#FFFFFF", "#1F201C"),
}

SIDEBAR_WIDTH = 232
CONTENT_PADX = 34
CARD_RADIUS = 14
CONTROL_RADIUS = 9
INPUT_HEIGHT = 44
BTN_HEIGHT = 44

# Typography uses a 13 px body baseline.  The previous 10–11 px labels were
# technically compact but visibly undersized on a standard 1280 px display.
FONT_CAPTION = 12
FONT_SMALL = 14
FONT_BODY = 15
FONT_SECTION = 18
FONT_PAGE = 30

FORM_PRIMARY_WEIGHT = 3
FORM_SECONDARY_WEIGHT = 2
