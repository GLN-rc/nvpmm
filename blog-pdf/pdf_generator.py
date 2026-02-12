"""
PDF Generator v6
Replica-branded 2-page executive brief.

Page 1 — "At a Glance"
  Navy header (title wraps, logo top-right)
  QUICK OVERVIEW label + exec summary (no truncation)
  KEY TAKEAWAYS label + 3 horizontal cards (01/02/03 in cyan, stretch to fill page)

Page 2 — "Deep Dive"
  Narrow navy band
  4 content sections, plain bold headers
  Optional FAQ section (if blog had FAQs)
  Separator line + CTA block
  Full-bleed navy footer band (logo right with hyperlink, page number left)

Brand colors:
  Navy   #21253C
  Cyan   #06C4FF
  Pink   #C6169B
  Grey   #6B769C
  Light  #F6F7FB
"""

import io
import os
import textwrap
from typing import Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ── Brand colors ───────────────────────────────────────────────────────────────
NAVY   = HexColor("#21253C")
PURPLE = HexColor("#4428E8")
CYAN   = HexColor("#06C4FF")
PINK   = HexColor("#C6169B")
GREY   = HexColor("#6B769C")
LIGHT  = HexColor("#F6F7FB")
WHITE  = HexColor("#FFFFFF")

# ── Paths ──────────────────────────────────────────────────────────────────────
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
FONTS_DIR  = os.path.join(ASSETS_DIR, "fonts")
SHARED_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "shared", "assets", "fonts"
)

def _find_font_file(filename: str) -> Optional[str]:
    for d in [FONTS_DIR, SHARED_FONTS_DIR]:
        p = os.path.join(d, filename)
        if os.path.exists(p):
            return p
    return None

_fonts_registered = False

def _register_fonts():
    global _fonts_registered
    if _fonts_registered:
        return
    for name, filename in [
        ("Poppins-Bold",  "Poppins-Bold.ttf"),
        ("Poppins",       "Poppins-Regular.ttf"),
        ("OpenSans",      "OpenSans-Regular.ttf"),
        ("OpenSans-Bold", "OpenSans-Bold.ttf"),
    ]:
        path = _find_font_file(filename)
        if path:
            try:
                pdfmetrics.registerFont(TTFont(name, path))
            except Exception:
                pass
    _fonts_registered = True

def _font(name: str) -> str:
    _register_fonts()
    fallbacks = {
        "Poppins-Bold":  "Helvetica-Bold",
        "Poppins":       "Helvetica",
        "OpenSans":      "Helvetica",
        "OpenSans-Bold": "Helvetica-Bold",
    }
    try:
        pdfmetrics.getFont(name)
        return name
    except Exception:
        return fallbacks.get(name, "Helvetica")

# ── Page constants ─────────────────────────────────────────────────────────────
W, H          = letter           # 612 x 792 pt
MARGIN        = 0.7 * inch
CONTENT_W     = W - 2 * MARGIN
HEADER_H      = 2.0 * inch
FOOTER_H      = 0.5 * inch       # full-bleed navy footer band height
BODY_FONT_SZ  = 11.0
BODY_LEADING  = 16.5
CTA_BLOCK_H   = 2.6 * inch       # tall enough for full elevator pitch boilerplate

# ── Text utilities ─────────────────────────────────────────────────────────────

def _wrap(text: str, max_chars: int) -> list:
    if not text:
        return []
    lines = []
    for para in text.split("\n"):
        if not para.strip():
            lines.append("")
            continue
        lines.extend(textwrap.wrap(para, max_chars, break_long_words=False))
        lines.append("")
    while lines and lines[-1] == "":
        lines.pop()
    return lines

def _line_count(text: str, width: float, size: float) -> int:
    if not text:
        return 0
    max_chars = max(10, int(width / (size * 0.52)))
    return len(_wrap(text, max_chars))

def _draw_text_block(c, x, y, width, text, font, size, leading, color,
                     max_lines=None):
    max_chars = max(10, int(width / (size * 0.52)))
    lines = _wrap(text, max_chars)
    if max_lines and len(lines) > max_lines:
        lines = lines[:max_lines]
        # Walk back to find a line ending on a complete sentence
        for i in range(len(lines) - 1, -1, -1):
            if lines[i].rstrip().endswith((".", "!", "?")):
                lines = lines[:i + 1]
                break
        else:
            # No sentence boundary found — drop the trailing incomplete line
            if len(lines) > 1:
                lines = lines[:-1]
    c.setFont(font, size)
    c.setFillColor(color)
    t = c.beginText(x, y)
    t.setLeading(leading)
    for ln in lines:
        t.textLine(ln)
    c.drawText(t)
    return y - leading * len(lines)

# ── Section label (small grey all-caps) ───────────────────────────────────────

def _draw_section_label(c, x, y, text):
    """Small grey all-caps eyebrow label."""
    c.setFont(_font("OpenSans-Bold"), 8.5)
    c.setFillColor(GREY)
    c.drawString(x, y, text.upper())
    return y - 14

# ── Section header (plain bold) ───────────────────────────────────────────────

def _section_header(c, x, y, text):
    """Plain Poppins-Bold section header, navy."""
    c.setFont(_font("Poppins-Bold"), 11.5)
    c.setFillColor(NAVY)
    c.drawString(x, y, text)
    return y - 20

# ── Takeaway cards ─────────────────────────────────────────────────────────────

def _draw_takeaway_cards(c, takeaways: list, y: float, available_h: float = 0) -> float:
    """
    Draw 3 horizontal takeaway cards with 01/02/03 number labels in cyan.
    available_h: cards stretch to fill this height when provided.
    """
    gap       = 0.12 * inch
    card_w    = (CONTENT_W - 2 * gap) / 3
    card_pad  = 0.18 * inch
    inner_w   = card_w - 2 * card_pad
    text_sz   = 9.5
    text_lead = 14.0
    num_sz    = 22
    num_h     = num_sz * 1.3     # number height + breathing room
    rule_gap  = 16               # gap between cyan rule and text (was 6 — too tight)
    top_pad   = 0.16 * inch
    bot_pad   = 0.18 * inch

    # Card height: compute natural size from text, then add breathing room (capped)
    text_max_chars = max(10, int(inner_w / (text_sz * 0.52)))
    max_lines = max(
        (len(_wrap(t, text_max_chars)) if t.strip() else 1)
        for t in takeaways
    )
    natural_h = top_pad + num_h + rule_gap + text_lead * max_lines + bot_pad
    natural_h = max(natural_h, 1.5 * inch)

    # If available_h is given, allow a little extra breathing room but don't balloon
    if available_h and available_h > 1.5 * inch:
        card_h = min(available_h, natural_h + 0.5 * inch)
    else:
        card_h = natural_h

    card_y = y - card_h

    labels = ["01", "02", "03"]
    for i, (label, takeaway) in enumerate(zip(labels, takeaways)):
        cx = MARGIN + i * (card_w + gap)

        # Card background — flat fill, no stroke
        c.setFillColor(LIGHT)
        c.rect(cx, card_y, card_w, card_h, stroke=0, fill=1)

        # Number label in cyan
        c.setFont(_font("Poppins-Bold"), num_sz)
        c.setFillColor(CYAN)
        num_y = card_y + card_h - top_pad - num_sz * 0.75
        c.drawString(cx + card_pad, num_y, label)

        # Thin cyan rule below number
        rule_y = num_y - num_sz * 0.35
        c.setStrokeColor(CYAN)
        c.setLineWidth(1.5)
        c.line(cx + card_pad, rule_y, cx + card_w - card_pad, rule_y)

        # Takeaway text — rule_gap below the rule line
        text_y = rule_y - rule_gap
        _draw_text_block(c, cx + card_pad, text_y, inner_w,
                         takeaway or "",
                         _font("OpenSans"), text_sz, text_lead, NAVY)

    return card_y - 0.1 * inch

# ── FAQ section ────────────────────────────────────────────────────────────────

def _draw_faq_section(c, faqs: list, y: float, bottom_limit: float) -> float:
    """
    Draw FAQ section: small label + Q/A pairs.
    Only renders pairs that fit above bottom_limit.
    Returns new y after the section.
    """
    if not faqs:
        return y

    q_sz    = 10.0
    q_lead  = 14.0
    a_sz    = 9.5
    a_lead  = 13.5
    indent  = 0.15 * inch
    pair_gap = 10    # pt between Q/A pairs

    # Only skip entirely if there's not room for label + at least 1 pair
    if y - bottom_limit < 80:
        return y

    y = _draw_section_label(c, MARGIN, y, "Frequently Asked Questions")
    y -= 6

    for faq in faqs[:3]:
        question = faq.get("question", "").strip()
        answer   = faq.get("answer", "").strip()
        if not question:
            continue

        if y < bottom_limit + 0.5 * inch:
            break

        # Question — bold navy with cyan Q prefix
        q_max_chars = max(10, int((CONTENT_W - 14) / (q_sz * 0.52)))
        q_lines = _wrap(question, q_max_chars)

        c.setFont(_font("Poppins-Bold"), q_sz)
        c.setFillColor(CYAN)
        c.drawString(MARGIN, y, "Q")
        c.setFillColor(NAVY)
        ty = y
        for ln in q_lines:
            c.drawString(MARGIN + 14, ty, ln)
            ty -= q_lead
        y = ty - 2

        # Answer — grey, indented
        if answer:
            a_max_chars = max(10, int((CONTENT_W - indent) / (a_sz * 0.52)))
            y = _draw_text_block(c, MARGIN + indent, y, CONTENT_W - indent,
                                 answer, _font("OpenSans"), a_sz, a_lead, GREY)

        y -= pair_gap

    return y - 0.1 * inch

# ── Logo ───────────────────────────────────────────────────────────────────────

def _draw_logo(c, logo_path):
    """Draw transparent logo top-right of header, sized to clear title. Linked to replicacyber.com."""
    if not os.path.exists(logo_path):
        c.setFont(_font("Poppins-Bold"), 14)
        c.setFillColor(WHITE)
        link_x = W - MARGIN - 52
        c.drawString(link_x, H - 0.5 * inch, "REPLICA")
        c.linkURL("https://replicacyber.com",
                  (link_x, H - 0.6 * inch, W - MARGIN, H - 0.35 * inch), relative=0)
        return

    logo_w = 1.6 * inch
    logo_h = logo_w * (192 / 908)   # 908:192 aspect ratio
    logo_x = W - MARGIN - logo_w
    logo_y = H - 0.35 * inch - logo_h

    try:
        c.drawImage(logo_path, logo_x, logo_y,
                    width=logo_w, height=logo_h, mask="auto")
        c.linkURL("https://replicacyber.com",
                  (logo_x, logo_y, logo_x + logo_w, logo_y + logo_h), relative=0)
    except Exception:
        c.setFont(_font("Poppins-Bold"), 14)
        c.setFillColor(WHITE)
        link_x = W - MARGIN - 52
        c.drawString(link_x, H - 0.5 * inch, "REPLICA")
        c.linkURL("https://replicacyber.com",
                  (link_x, H - 0.6 * inch, W - MARGIN, H - 0.35 * inch), relative=0)

# ── Header texture ─────────────────────────────────────────────────────────────

def _draw_header_texture(c, header_y):
    c.saveState()
    p = c.beginPath()
    p.rect(0, header_y, W, HEADER_H)
    c.clipPath(p, stroke=0)

    c.setFillColor(Color(0.776, 0.09, 0.604, alpha=0.15))
    c.circle(W - 0.5 * inch, header_y + HEADER_H * 0.5, 1.05 * inch, stroke=0, fill=1)
    c.setFillColor(Color(0.267, 0.157, 0.91, alpha=0.12))
    c.circle(W - 1.35 * inch, header_y + HEADER_H * 0.75, 0.65 * inch, stroke=0, fill=1)
    c.setStrokeColor(Color(0.776, 0.09, 0.604, alpha=0.3))
    c.setLineWidth(1.2)
    for offset in [0, 10, 20]:
        c.line(W - 2.0 * inch + offset, header_y + HEADER_H,
               W - 0.1 * inch + offset, header_y)

    c.restoreState()

# ── Footer — full-bleed navy band ──────────────────────────────────────────────

def _draw_footer(c, logo_path=None):
    """Full-bleed navy band at page bottom. Logo right with hyperlink, no page number."""
    # Navy band — full bleed, 0 to W
    c.setFillColor(NAVY)
    c.rect(0, 0, W, FOOTER_H, stroke=0, fill=1)

    # Logo — right side, small, transparent, with hyperlink to replicacyber.com
    if logo_path and os.path.exists(logo_path):
        f_logo_w = 0.9 * inch
        f_logo_h = f_logo_w * (192 / 908)
        f_logo_x = W - MARGIN - f_logo_w
        f_logo_y = (FOOTER_H - f_logo_h) / 2   # vertically centered in band
        try:
            c.drawImage(logo_path, f_logo_x, f_logo_y,
                        width=f_logo_w, height=f_logo_h, mask="auto")
            # Hyperlink wrapping the logo
            c.linkURL("https://replicacyber.com",
                      (f_logo_x, f_logo_y, f_logo_x + f_logo_w, f_logo_y + f_logo_h),
                      relative=0)
        except Exception:
            # Text fallback
            c.setFont(_font("Poppins-Bold"), 9)
            c.setFillColor(WHITE)
            fx = W - MARGIN - 48
            c.drawString(fx, FOOTER_H * 0.35, "REPLICA")
            c.linkURL("https://replicacyber.com", (fx, 0, W - MARGIN, FOOTER_H), relative=0)
    else:
        # Text fallback with link
        c.setFont(_font("Poppins-Bold"), 9)
        c.setFillColor(WHITE)
        fx = W - MARGIN - 48
        c.drawString(fx, FOOTER_H * 0.35, "REPLICA")
        c.linkURL("https://replicacyber.com", (fx, 0, W - MARGIN, FOOTER_H), relative=0)

# ── CTA block ─────────────────────────────────────────────────────────────────

def _draw_cta_block(c, elev_hdr, elev_body, cta_text, cta_url):
    """CTA / elevator pitch block anchored just above the footer band."""
    block_y = FOOTER_H + 0.18 * inch   # sits just above footer band
    bx = MARGIN

    c.setFillColor(NAVY)
    c.rect(bx, block_y, CONTENT_W, CTA_BLOCK_H, stroke=0, fill=1)

    # Pink left accent
    c.setFillColor(PINK)
    c.rect(bx, block_y, 4, CTA_BLOCK_H, stroke=0, fill=1)

    ix = bx + 0.2 * inch

    # No header label — jump straight into the elevator pitch copy
    body = elev_body or "Replica delivers isolated, policy-controlled workspaces that eliminate endpoint risk without slowing your team down."
    body_w = CONTENT_W - 0.4 * inch

    # Auto-shrink font size to fit elevator pitch body — allow up to 9 lines
    MAX_BODY_LINES = 9
    body_sz   = 10.0
    body_lead = 14.5
    for try_sz in [10.0, 9.5, 9.0, 8.5, 8.0, 7.5]:
        max_chars = max(10, int(body_w / (try_sz * 0.52)))
        n_lines = len(_wrap(body, max_chars))
        body_sz   = try_sz
        body_lead = try_sz * 1.45
        if n_lines <= MAX_BODY_LINES:
            break

    # Body starts near the top of the block (no header above it)
    _draw_text_block(c, ix, block_y + CTA_BLOCK_H - 0.28 * inch,
                     body_w, body,
                     _font("OpenSans"), body_sz, body_lead, WHITE, max_lines=MAX_BODY_LINES)

    # CTA link — show label text; if URL provided, make it a hyperlink
    cta_display = cta_text.strip() if cta_text else ""
    if not cta_display and cta_url:
        cta_display = cta_url[:80]
    if cta_display:
        c.setFont(_font("OpenSans-Bold"), 9.5)
        c.setFillColor(CYAN)
        c.drawString(ix, block_y + 0.22 * inch, cta_display[:100])
        if cta_url:
            link_w = len(cta_display) * 9.5 * 0.55   # rough pixel width
            c.linkURL(cta_url,
                      (ix, block_y + 0.12 * inch, ix + link_w, block_y + 0.34 * inch),
                      relative=0)

# ── Page header ────────────────────────────────────────────────────────────────

def _render_page_header(c, title, subtitle):
    header_y = H - HEADER_H

    c.setFillColor(NAVY)
    c.rect(0, header_y, W, HEADER_H, stroke=0, fill=1)

    _draw_header_texture(c, header_y)

    logo_path = os.path.join(ASSETS_DIR, "logo.png")
    _draw_logo(c, logo_path)

    # Title wraps up to 3 lines at 18pt — width constrained to clear the logo
    title_y         = H - 0.82 * inch
    title_font_sz   = 18
    logo_w_header   = 1.6 * inch
    title_avail_w   = W - MARGIN - logo_w_header - 0.5 * inch  # 0.5in gap before logo
    title_max_chars = max(10, int(title_avail_w / (title_font_sz * 0.58)))
    title_lines     = _wrap(title, title_max_chars)[:3]

    c.setFont(_font("Poppins-Bold"), title_font_sz)
    c.setFillColor(WHITE)
    title_leading = title_font_sz * 1.3
    ty = title_y
    for ln in title_lines:
        c.drawString(MARGIN, ty, ln)
        ty -= title_leading

    # Subtitle — cyan, below title (only if it fits within the header)
    subtitle_y = ty - 4
    header_bottom = H - HEADER_H + 6   # 6pt clearance above header bottom edge
    if subtitle and subtitle_y > header_bottom:
        c.setFont(_font("OpenSans"), 11.5)
        c.setFillColor(CYAN)
        sub_max = max(10, int((W * 0.72) / (11.5 * 0.52)))
        sub_lines = _wrap(subtitle, sub_max)[:1]
        if sub_lines:
            c.drawString(MARGIN, subtitle_y, sub_lines[0])

    return header_y

def _render_narrow_band(c):
    """Thin navy band at the top of page 2."""
    c.setFillColor(NAVY)
    c.rect(0, H - 0.45 * inch, W, 0.45 * inch, stroke=0, fill=1)

# ── Main generate function ─────────────────────────────────────────────────────

def generate_pdf(data: dict, image_paths: Optional[dict] = None) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)

    title        = data.get("title", "Executive Brief")
    subtitle     = data.get("subtitle", "")
    exec_summary = data.get("exec_summary", "")
    takeaways    = [t for t in data.get("takeaways", [])[:3] if t.strip()]
    while len(takeaways) < 3:   # always 3 cards
        takeaways.append("")
    sections     = data.get("sections", [])
    faqs         = [f for f in data.get("faqs", []) if f.get("question", "").strip()]
    elev_hdr     = data.get("elevator_pitch_header", "")
    elev_body    = data.get("elevator_pitch_body", "")
    cta_text     = data.get("cta_text", "")
    cta_url      = data.get("cta_url", "")
    blog_url     = data.get("blog_url", "")
    image_paths  = image_paths or {}
    logo_path    = os.path.join(ASSETS_DIR, "logo.png")

    # ── PAGE 1: At a Glance ───────────────────────────────────────────────────
    _render_page_header(c, title, subtitle)

    y = H - HEADER_H - 0.4 * inch

    # QUICK OVERVIEW label + exec summary
    y = _draw_section_label(c, MARGIN, y, "Quick Overview")
    y -= 4
    y = _draw_text_block(c, MARGIN, y, CONTENT_W, exec_summary,
                         _font("OpenSans"), BODY_FONT_SZ, BODY_LEADING, NAVY)
    y -= 0.32 * inch

    # KEY TAKEAWAYS label + 3 cards stretched to fill remaining page 1 space
    y = _draw_section_label(c, MARGIN, y, "Key Takeaways")
    y -= 6

    page1_bottom = FOOTER_H + 0.25 * inch

    if takeaways:
        available_for_cards = y - page1_bottom
        y = _draw_takeaway_cards(c, takeaways, y, available_for_cards)

    # FAQ section on page 1 — fills the gap below the cards
    if faqs and y - page1_bottom > 0.8 * inch:
        y -= 0.2 * inch
        y = _draw_faq_section(c, faqs, y, page1_bottom)

    _draw_footer(c, logo_path)
    c.showPage()

    # ── PAGE 2: Deep Dive ─────────────────────────────────────────────────────
    _render_narrow_band(c)
    y = H - 0.45 * inch - 0.4 * inch

    # bottom_p2: content must stay above the CTA block + separator
    # No extra reservation for read-more link — it now floats just below content
    bottom_p2 = FOOTER_H + 0.18 * inch + CTA_BLOCK_H + 0.18 * inch

    for idx, section in enumerate(sections):
        hdr  = section.get("header", "")
        body = section.get("body", "")

        if y < bottom_p2 + 0.8 * inch:
            break

        if hdr:
            y = _section_header(c, MARGIN, y, hdr)
            y -= 4

        # Optional embedded image
        if idx in image_paths and image_paths[idx]:
            try:
                from reportlab.lib.utils import ImageReader
                img_r = ImageReader(image_paths[idx])
                iw, ih = img_r.getSize()
                max_img_h = 2.0 * inch
                scale = min(CONTENT_W / iw, max_img_h / ih)
                dw, dh = iw * scale, ih * scale
                dx = MARGIN + (CONTENT_W - dw) / 2
                c.setStrokeColor(HexColor("#E0E0E0"))
                c.setLineWidth(0.5)
                c.rect(dx - 2, y - dh - 2, dw + 4, dh + 4, stroke=1, fill=0)
                c.drawImage(image_paths[idx], dx, y - dh,
                            width=dw, height=dh, mask="auto")
                y -= dh + 10
            except Exception:
                pass

        if body:
            avail = y - bottom_p2
            ml    = max(4, int(avail / BODY_LEADING))
            y = _draw_text_block(c, MARGIN, y, CONTENT_W, body,
                                 _font("OpenSans"), BODY_FONT_SZ, BODY_LEADING, NAVY,
                                 max_lines=ml)
        y -= 0.3 * inch

    # "Read the full article" link — follows immediately below last section content
    sep_y = FOOTER_H + 0.18 * inch + CTA_BLOCK_H + 0.25 * inch
    if blog_url:
        # Float the link just below the last section (y = current position after loop)
        read_y = y - 0.18 * inch
        # Safety clamp: never let it overlap or go below the separator
        min_read_y = sep_y + 0.22 * inch
        if read_y < min_read_y:
            read_y = min_read_y
        c.setFont(_font("OpenSans-Bold"), 9)
        c.setFillColor(CYAN)
        label = "Read the full article \u2192"
        c.drawString(MARGIN, read_y, label)
        c.linkURL(blog_url,
                  (MARGIN, read_y - 3, MARGIN + CONTENT_W, read_y + 11),
                  relative=0)

    # Thin separator line above CTA block (always at fixed position from bottom)
    c.setStrokeColor(HexColor("#DDE1EC"))
    c.setLineWidth(0.75)
    c.line(MARGIN, sep_y, W - MARGIN, sep_y)

    _draw_cta_block(c, elev_hdr, elev_body, cta_text, cta_url)
    _draw_footer(c, logo_path)

    c.save()
    buf.seek(0)
    return buf.read()
