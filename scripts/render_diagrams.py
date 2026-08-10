"""
Renders the two diagrams used in docs/:
  1. docs/architecture.png  - system components and data flow
  2. docs/workflow.png      - call conversation state machine

Run with: python3 scripts/render_diagrams.py
Requires: Pillow (already in requirements.txt)
"""
from PIL import Image, ImageDraw, ImageFont
import os

FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
F_BOLD = FONT_DIR + "DejaVuSans-Bold.ttf"
F_REG = FONT_DIR + "DejaVuSans.ttf"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "docs")
os.makedirs(OUT_DIR, exist_ok=True)

# ---------- palette ----------
BG = (255, 255, 255)
NAVY = (17, 26, 46)
BLUE = (30, 95, 234)
GREEN = (74, 163, 60)
GRAY = (110, 120, 140)
LIGHT = (240, 243, 248)
BLACK = (10, 10, 10)


def font(path, size):
    return ImageFont.truetype(path, size)


def text_w(draw, text, f):
    bbox = draw.textbbox((0, 0), text, font=f)
    return bbox[2] - bbox[0]


def wrap_text(draw, text, f, max_w):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if text_w(draw, trial, f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def rounded_box(draw, xy, radius, fill, outline, width_):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width_)


def box_with_text(draw, x, y, w, h, title, subtitle_lines, accent, title_size=17, sub_size=12):
    rounded_box(draw, [x, y, x + w, y + h], 10, LIGHT, accent, 3)
    f_title = font(F_BOLD, title_size)
    f_sub = font(F_REG, sub_size)
    tw = text_w(draw, title, f_title)
    draw.text((x + w / 2 - tw / 2, y + 14), title, font=f_title, fill=NAVY)
    ty = y + 14 + title_size + 10
    for line in subtitle_lines:
        lw = text_w(draw, line, f_sub)
        draw.text((x + w / 2 - lw / 2, ty), line, font=f_sub, fill=GRAY)
        ty += sub_size + 6


def arrow(draw, x1, y1, x2, y2, color=GRAY, width_=3):
    draw.line([x1, y1, x2, y2], fill=color, width=width_)
    # arrow head
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    hl = 10
    for da in (0.5, -0.5):
        hx = x2 - hl * math.cos(ang - da)
        hy = y2 - hl * math.sin(ang - da)
        draw.line([x2, y2, hx, hy], fill=color, width=width_)


# ============================================================
# DIAGRAM 1 — ARCHITECTURE
# ============================================================
W, H = 1780, 720
img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)

f_h1 = font(F_BOLD, 30)
d.text((40, 30), "Saathi — System Architecture", font=f_h1, fill=NAVY)
f_h2 = font(F_REG, 15)
d.text((40, 72), "VoxForge Track  ·  Rime + Qdrant  ·  High-Trust Escalation Workflow", font=f_h2, fill=GRAY)

box_w, box_h = 230, 130
gap = 34
y0 = 190
boxes = [
    ("PATIENT", ["Speaks, listens,", "interrupts, returns"], GRAY),
    ("ORCHESTRATION", ["FastAPI call logic,", "confirmation parsing,", "session state"], BLUE),
    ("QDRANT", ["Adherence memory,", "case similarity search", "payload-filtered"], GREEN),
    ("TOOLS", ["Escalation engine,", "caregiver alert log"], BLUE),
    ("RIME", ["Coda model speaks", "the response"], GREEN),
]
xs = []
x = 40
for i, (title, subs, accent) in enumerate(boxes):
    box_with_text(d, x, y0, box_w, box_h, title, subs, accent)
    xs.append(x)
    if i < len(boxes) - 1:
        arrow(d, x + box_w, y0 + box_h / 2, x + box_w + gap, y0 + box_h / 2)
    x += box_w + gap

# outcome box
ox = x
box_with_text(d, ox, y0 - 20, 230, box_h + 40, "OUTCOME", ["Dose logged", "Memory updated", "Caregiver alerted", "if pattern crosses", "threshold"], GREEN)
arrow(d, x, y0 + box_h / 2, ox, y0 + box_h / 2)

# Qdrant payload detail callout
py = y0 + box_h + 50
px = xs[2]
rounded_box(d, [px - 20, py, px + box_w + 20, py + 170], 10, (14, 26, 18), GREEN, 2)
f_pt = font(F_BOLD, 14)
d.text((px, py + 14), "Qdrant payload / patient", font=f_pt, fill=(255, 255, 255))
f_pl = font(F_REG, 12)
fields = ["patient_id  ·  language", "risk_level  ·  voice_pref", "last_confirmed", "missed_count", "escalation_history"]
fy = py + 44
for line in fields:
    d.text((px, fy), line, font=f_pl, fill=(180, 230, 160))
    fy += 20
arrow(d, px + box_w / 2, y0 + box_h, px + box_w / 2, py, color=GREEN, width_=2)

f_note = font(F_REG, 15)
note = "The next call starts with context, not from zero."
d.text((40, H - 50), note, font=ImageFont.truetype(FONT_DIR + "DejaVuSans-Oblique.ttf", 16), fill=GRAY)

img.save(os.path.join(OUT_DIR, "architecture.png"))
print("Saved architecture.png")

# ============================================================
# DIAGRAM 2 — CALL WORKFLOW / STATE MACHINE
# ============================================================
W2, H2 = 1780, 900
img2 = Image.new("RGB", (W2, H2), BG)
d2 = ImageDraw.Draw(img2)

d2.text((40, 30), "Saathi — Call Conversation Workflow", font=f_h1, fill=NAVY)
d2.text((40, 72), "One scheduled check-in call, from greeting to escalation decision", font=f_h2, fill=GRAY)

def state_box(draw, x, y, w, h, title, sub, accent, big=False):
    rounded_box(draw, [x, y, x + w, y + h], 12, LIGHT, accent, 3)
    ft = font(F_BOLD, 16 if not big else 18)
    tw = text_w(draw, title, ft)
    draw.text((x + w / 2 - tw / 2, y + 12), title, font=ft, fill=NAVY)
    if sub:
        fs = font(F_REG, 11)
        lines = wrap_text(draw, sub, fs, w - 20)
        sy = y + 12 + 22
        for line in lines:
            lw = text_w(draw, line, fs)
            draw.text((x + w / 2 - lw / 2, sy), line, font=fs, fill=GRAY)
            sy += 15

bw, bh = 260, 90
CX = W2 / 2  # canvas center — everything below is centered on this

# Row 1: Greeting -> Await confirmation, centered as a pair around CX
row1_total = bw + 60 + bw
row1_start = CX - row1_total / 2
state_box(d2, row1_start, 150, bw, bh, "1. GREETING", "Qdrant lookup decides tone & wording based on history", BLUE)
arrow(d2, row1_start + bw, 150 + bh / 2, row1_start + bw + 60, 150 + bh / 2)
state_box(d2, row1_start + bw + 60, 150, bw, bh, "2. AWAIT CONFIRMATION", "Rime speaks the check-in; patient responds by voice", GREEN)
branch_origin_x = row1_start + bw + 60 + bw / 2

# Branches down to 4 outcomes, centered on CX
branch_y = 150 + bh + 70
labels = [
    ("TAKEN", "Missed-count resets. Memory updated. Call closes warmly.", GRAY),
    ("MISSED", "Missed-count +1. Escalation check runs.", BLUE),
    ("LATER / INTERRUPTED", "No count change. State saved for recovery on next call.", GREEN),
    ("UNCLEAR", "One bounded clarifying re-ask.", GRAY),
]
bw2 = 340
n = len(labels)
total_w = n * bw2 + (n - 1) * 40
start = CX - total_w / 2
xs2 = []
for i, (title, sub, accent) in enumerate(labels):
    x = start + i * (bw2 + 40)
    xs2.append(x)
    arrow(d2, branch_origin_x, 150 + bh, x + bw2 / 2, branch_y, color=GRAY, width_=2)
    state_box(d2, x, branch_y, bw2, 110, title, sub, accent)

# Escalation check below MISSED branch
esc_y = branch_y + 110 + 70
esc_x = xs2[1]
arrow(d2, esc_x + bw2 / 2, branch_y + 110, esc_x + bw2 / 2, esc_y, color=BLUE, width_=2)
state_box(d2, esc_x - 40, esc_y, bw2 + 80, 110, "3. ESCALATION THRESHOLD CHECK",
          "Only fires after repeated misses in Qdrant history, not a single miss", BLUE, big=True)

esc2_y = esc_y + 110 + 60
lab2 = [
    ("BELOW THRESHOLD", "Logged only. Next scheduled call checks again.", GRAY),
    ("THRESHOLD CROSSED", "Caregiver alert created. Escalation logged in Qdrant case memory.", GREEN),
]
total_w2 = 2 * bw2 + 40
start2 = (esc_x + bw2 / 2) - total_w2 / 2
for i, (title, sub, accent) in enumerate(lab2):
    x = start2 + i * (bw2 + 40)
    arrow(d2, esc_x + bw2 / 2, esc_y + 110, x + bw2 / 2, esc2_y, color=BLUE, width_=2)
    state_box(d2, x, esc2_y, bw2, 110, title, sub, accent)

d2.text((40, H2 - 45), "Recovery guarantee: an interruption or correction updates state from what the patient actually said — never duplicated, never lost.",
         font=font(F_REG, 14), fill=GRAY)

img2.save(os.path.join(OUT_DIR, "workflow.png"))
print("Saved workflow.png")
