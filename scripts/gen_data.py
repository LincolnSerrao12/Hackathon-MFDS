"""Generate a synthetic file tree for benchmarking/demo: python scripts/gen_data.py --count 100000 --out data/synth"""
import argparse
import os
import random
import time
from pathlib import Path

random.seed(7)
TOPICS = {
    "university": ["fee receipt semester {n} tuition payment amount {a} rupees", "lecture notes on {w} chapter {n}",
                   "assignment {n} submission {w} deadline", "exam timetable semester {n} hall ticket"],
    "finance": ["bank statement account ending {n} balance {a}", "invoice {n} payment due {a} gst", "salary slip month {n} net pay {a}",
                "tax return filing acknowledgement assessment year 20{n}"],
    "travel": ["goa beach trip itinerary day {n} hotel booking confirmation", "flight ticket booking reference {n} boarding pass",
               "trip budget {w} expenses {a}"],
    "work": ["meeting notes project {w} action items sprint {n}", "design doc for {w} service architecture", "quarterly report {w} revenue {a}"],
    "personal": ["recipe for {w} curry ingredients", "medical report patient lab results {n}", "insurance policy number {n} premium {a}"],
}
WORDS = "alpha orion neptune delta zephyr falcon atlas nova pixel quartz ember summit harbor lotus cedar".split()
PII = ["Contact: Rahul Sharma, phone +91 98765 43210, email rahul.sharma@example.com", "PAN ABCDE1234F, Aadhaar 1234 5678 9012",
       "Card 4111 1111 1111 1111 exp 09/28", "Account holder Priya Nair, IBAN GB82WEST12345698765432"]
BIN = {"jpg": 3000, "png": 5000, "mp4": 40000, "mp3": 8000, "zip": 20000, "pdf": 4000}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=100_000)
    ap.add_argument("--out", default="data/synth")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    now = time.time()
    t0 = time.time()
    dirs = []
    for topic in TOPICS:
        for y in (2023, 2024, 2025, 2026):
            for k in range(20):
                d = out / topic / str(y) / f"folder_{k:02d}"
                d.mkdir(parents=True, exist_ok=True)
                dirs.append((topic, d))
    dup_blob = b"duplicate content " * 200
    for i in range(a.count):
        topic, d = random.choice(dirs)
        r = random.random()
        if r < 0.55:  # text-like
            ext = random.choice(["txt", "md", "txt", "csv", "py"])
            tmpl = random.choice(TOPICS[topic])
            body = tmpl.format(n=random.randint(1, 9999), a=random.randint(100, 99999), w=random.choice(WORDS))
            body = (body + "\n") * random.randint(1, 6)
            if random.random() < 0.01:
                body += random.choice(PII) + "\n"
            data = body.encode()
            name = f"{random.choice(WORDS)}_{topic}_{i}.{ext}"
        elif r < 0.97:
            ext = random.choice(list(BIN))
            data = os.urandom(random.randint(200, BIN[ext]))
            name = f"{'IMG' if ext in ('jpg','png') else 'file'}_{i:06d}.{ext}"
        else:  # exact duplicates and a few big files
            ext = "bin"
            data = dup_blob if random.random() < 0.7 else os.urandom(2_000_000)
            name = f"copy_{i}.{ext}"
        p = d / name
        p.write_bytes(data)
        age = random.uniform(0, 3 * 365 * 86400)
        os.utime(p, (now - age, now - age))
        if i and i % 20000 == 0:
            print(f"  {i} files...")
    print(f"generated {a.count} files in {time.time() - t0:.1f}s under {out}")


if __name__ == "__main__":
    main()
