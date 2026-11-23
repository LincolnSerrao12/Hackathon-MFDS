"""Create a small demo folder where the right answers share NO keywords with the natural queries.
python scripts/make_demo.py [--out data/demo]
Queries to try: "the fee receipt from last semester", "photos from the Goa beach trip", "mountain pictures", "invoice for laptop"."""
import argparse
import os
import random
import time
from pathlib import Path

from PIL import Image, ImageDraw

random.seed(3)
DAY = 86400
W, H = 640, 480


def pdf_bytes(lines: list[str]) -> bytes:
    """Minimal single-page text PDF (no dependencies)."""
    def esc(s):
        return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    text = "BT /F1 12 Tf 50 750 Td 16 TL " + " ".join(f"({esc(l)}) Tj T*" for l in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(text)} >>\nstream\n{text}\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return out


def sky(d, top, bottom, h):
    for y in range(h):
        t = y / h
        d.line([(0, y), (W, y)], fill=tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))


def beach(i):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    sky(d, (90, 170, 235), (200, 230, 250), 250)
    d.ellipse([480, 40, 560, 120], fill=(255, 220, 80))
    d.rectangle([0, 250, W, 340], fill=(20, 110, 190))
    for _ in range(25):
        x, y = random.randint(0, W), random.randint(255, 335); d.line([(x, y), (x + 30, y)], fill=(230, 245, 255), width=2)
    d.rectangle([0, 340, W, H], fill=(236, 214, 160))
    d.rectangle([110, 230, 124, 380], fill=(110, 70, 30))  # palm tree
    for ang in ((60, 215), (-60, 215), (90, 245), (-90, 245), (40, 200), (-40, 200)):
        d.polygon([(117, 232), (117 + ang[0], ang[1] - 40), (117 + ang[0] // 2, ang[1])], fill=(30, 140, 50))
    return im


def mountain(i):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    sky(d, (120, 170, 230), (210, 225, 245), H)
    for cx, hgt, col in ((160, 300, (110, 115, 125)), (400, 360, (95, 100, 112)), (560, 250, (120, 125, 135))):
        d.polygon([(cx - 220, 420), (cx, 420 - hgt), (cx + 220, 420)], fill=col)
        d.polygon([(cx - 55, 420 - hgt + 90), (cx, 420 - hgt), (cx + 55, 420 - hgt + 90)], fill=(250, 250, 255))
    d.rectangle([0, 420, W, H], fill=(60, 110, 60))
    return im


def forest(i):
    im = Image.new("RGB", (W, H), (190, 220, 190)); d = ImageDraw.Draw(im)
    for _ in range(40):
        x = random.randint(0, W); y = random.randint(150, 440); s = random.randint(40, 90)
        d.rectangle([x - 6, y, x + 6, y + s], fill=(90, 60, 30))
        d.polygon([(x - s // 2, y + 10), (x, y - s), (x + s // 2, y + 10)], fill=(20, random.randint(90, 140), 40))
    return im


def city_night(i):
    im = Image.new("RGB", (W, H), (15, 20, 45)); d = ImageDraw.Draw(im)
    for x in range(0, W, 70):
        hgt = random.randint(150, 380); d.rectangle([x, H - hgt, x + 60, H], fill=(30, 35, 60))
        for wy in range(H - hgt + 10, H - 10, 26):
            for wx in range(x + 8, x + 52, 18):
                if random.random() < 0.6: d.rectangle([wx, wy, wx + 8, wy + 12], fill=(255, 220, 110))
    d.ellipse([540, 40, 590, 90], fill=(240, 240, 220))
    return im


def desert(i):
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im)
    sky(d, (250, 140, 60), (255, 210, 130), 300)
    d.ellipse([260, 190, 380, 310], fill=(255, 240, 160))
    d.polygon([(0, 480), (0, 380), (200, 330), (420, 390), (640, 340), (640, 480)], fill=(205, 150, 80))
    return im


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="data/demo"); a = ap.parse_args()
    out = Path(a.out); now = time.time()
    for d in ("Documents/University", "Documents/Finance", "Pictures/Camera", "Notes"):
        (out / d).mkdir(parents=True, exist_ok=True)

    def put(rel, data, days_ago):
        p = out / rel
        p.write_bytes(data) if isinstance(data, bytes) else p.write_text(data)
        t = now - days_ago * DAY; os.utime(p, (t, t))

    # target for "fee receipt from last semester": NO words 'fee' or 'receipt' inside
    put("Documents/University/scan_0042.pdf", pdf_bytes([
        "Acknowledgement of payment", "Student: A. Student   Roll no: 21CS047",
        "Tuition instalment for Semester 5 credited to the university accounts section",
        "Amount paid: INR 52,000   Mode: UPI   Date: 14 August", "Authorised signatory, Accounts Office"]), 100)
    put("Documents/University/timetable_even_sem.txt", "Even semester class timetable. Monday data structures, Tuesday operating systems lab.", 95)
    put("Documents/University/hostel_rules.txt", "Hostel gate closes at 10pm. Visitors must register at the front desk.", 400)
    put("Documents/Finance/laptop_purchase.pdf", pdf_bytes([
        "TAX INVOICE", "Seller: Digital World Electronics", "Item: ASUS TUF Gaming F15 laptop", "Total payable: INR 89,990 incl. GST"]), 200)
    put("Documents/Finance/bank_statement_march.txt", "Statement for account ending 4471. Closing balance 23,418. Contact: priya.nair@example.com PAN ABCDE1234F", 250)
    put("Notes/ideas.md", "Startup idea: an app that organises family photos by event using on-device AI.", 30)
    put("Notes/recipe_dal.txt", "Dal tadka: boil toor dal with turmeric, temper with cumin, garlic and red chillies.", 60)
    scenes = [(beach, 1), (beach, 2), (mountain, 3), (forest, 4), (city_night, 5), (desert, 6)]
    for n, (fn, k) in enumerate(scenes):
        im = fn(k); path = out / "Pictures/Camera" / f"IMG_{4100 + n * 7}.jpg"
        im.save(path, quality=88)
        t = now - (110 + n * 3) * DAY if fn is beach else now - (20 + n * 40) * DAY
        os.utime(path, (t, t))
    # a duplicate for the cleanup demo + a big file
    put("Pictures/Camera/IMG_4100 (copy).jpg", (out / "Pictures/Camera/IMG_4100.jpg").read_bytes(), 109)
    put("Documents/big_video_export.mp4", os.urandom(60 * 1024 * 1024), 500)
    print(f"demo created in {out}")


if __name__ == "__main__":
    main()
