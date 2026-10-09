#!/usr/bin/env python3
"""שליפת רעידות אדמה בעוצמה 4.0 ומעלה מהחודש האחרון (30 ימים) מ-USGS,
וכתיבת קבצי נתונים לתיקיית data/.

שימוש:
    python scripts/fetch_quakes.py                         # שליפה חיה
    python scripts/fetch_quakes.py --input f.geojson       # בדיקה מקומית על קובץ GeoJSON

ספריות סטנדרטיות בלבד.
"""

import argparse
import json
import sys
import traceback
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
MIN_MAG = 4.0           # "מעל 4" = 4.0 ומעלה (הנחה מתועדת ב-SPEC.md)
DAYS = 30
USGS_MAX_LIMIT = 20000  # המגבלה המתועדת של USGS לבקשה אחת

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LOG_LINES = []


def log(msg):
    print(msg)
    LOG_LINES.append(msg)


def fetch_json(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "earthquakes-practice-repo/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_usgs(now):
    start = now - timedelta(days=DAYS)
    params = {
        "format": "geojson",
        "starttime": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "endtime": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "minmagnitude": MIN_MAG,
        "orderby": "time",
        "limit": USGS_MAX_LIMIT,
    }
    data = fetch_json(USGS_URL + "?" + urllib.parse.urlencode(params))
    if len(data.get("features", [])) >= USGS_MAX_LIMIT:
        raise RuntimeError("מספר הרשומות הגיע למגבלת USGS; יש לחלק את השליפה לטווחים קצרים יותר.")
    return data


def area_from_place(place):
    """USGS מחזיר מיקום כטקסט חופשי, למשל '103 km ENE of Noda, Japan'.
    לוקחים את החלק שאחרי הפסיק האחרון, בשם המקורי (באנגלית), בלי תרגום ובלי ניחושים.
    כשאין פסיק (למשל 'Mid-Atlantic Ridge') מוחזר הטקסט כולו."""
    if not place:
        return ""
    area = place.rsplit(",", 1)[1].strip() if "," in place else place.strip()
    # "Japan region" -> "Japan": USGS מוסיף "region" לאזורים שאין להם מיקום מדויק
    return area[: -len(" region")] if area.endswith(" region") and len(area) > len(" region") else area


def parse_events(geojson):
    events = []
    for f in geojson.get("features", []):
        p = f.get("properties", {})
        mag = p.get("mag")
        if mag is None or mag < MIN_MAG:
            continue
        lon, lat, depth = (f["geometry"]["coordinates"] + [None])[:3]
        events.append({
            "time": p["time"],  # אלפיות שנייה מאז 1970 (UTC)
            "mag": round(float(mag), 1),
            "place": p.get("place") or "",
            "area": area_from_place(p.get("place")),
            "lat": lat,
            "lon": lon,
            "depth": depth,
        })
    events.sort(key=lambda e: e["time"], reverse=True)
    return events


def summarize(events):
    buckets = {"4.0-4.9": 0, "5.0-5.9": 0, "6.0-6.9": 0, "7.0 ומעלה": 0}
    for e in events:
        m = e["mag"]
        key = "4.0-4.9" if m < 5 else "5.0-5.9" if m < 6 else "6.0-6.9" if m < 7 else "7.0 ומעלה"
        buckets[key] += 1
    strongest = max(events, key=lambda e: e["mag"]) if events else None
    return {"total_4_and_above": len(events), "buckets": buckets, "strongest": strongest}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="קובץ GeoJSON מקומי לבדיקה במקום שליפה מ-USGS")
    args = ap.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    log("התחלה: " + now.isoformat())
    geojson = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else fetch_usgs(now)
    log(f"USGS החזיר {len(geojson.get('features', []))} רשומות")

    events = parse_events(geojson)
    meta = {
        "fetched_at_utc": now.isoformat(),
        "range_start_utc": (now - timedelta(days=DAYS)).isoformat(),
        "range_end_utc": now.isoformat(),
        "min_magnitude": MIN_MAG,
        "source_is_local_test_file": bool(args.input),
    }
    payload = {"meta": meta, "summary": summarize(events), "events": events}

    DATA_DIR.mkdir(exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=1)
    (DATA_DIR / "quakes.json").write_text(text, encoding="utf-8")
    # גרסת JS כדי שהדף יעבוד גם בפתיחה ישירה של הקובץ (בלי שרת)
    (DATA_DIR / "quakes.js").write_text("window.QUAKES_DATA = " + text + ";\n", encoding="utf-8")
    log(f"נשמרו {payload['summary']['total_4_and_above']} רעידות.")


def write_run_log(error_text=None):
    """כותב את מהלך ההרצה לקובץ, כדי שאפשר יהיה לקרוא אותו בריפו גם כשההרצה נכשלת."""
    DATA_DIR.mkdir(exist_ok=True)
    lines = list(LOG_LINES) + (["שגיאה:", error_text] if error_text else ["ההרצה הסתיימה בהצלחה"])
    (DATA_DIR / "last_run.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
        write_run_log()
    except Exception:
        write_run_log(traceback.format_exc())
        sys.exit(1)
