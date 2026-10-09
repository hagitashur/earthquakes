#!/usr/bin/env python3
"""שליפת רעידות אדמה בעוצמה 4.0 ומעלה מהחודש האחרון (30 ימים) מ-USGS,
הוספת שם מדינה בעברית מ-REST Countries, וכתיבת קבצי נתונים לתיקיית data/.

שימוש:
    python scripts/fetch_quakes.py                 # שליפה חיה
    python scripts/fetch_quakes.py --input f.geojson --skip-countries   # בדיקה מקומית

ספריות סטנדרטיות בלבד.
"""

import argparse
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

USGS_URL = "https://earthquake.usgs.gov/fdsnws/event/1/query"
COUNTRIES_URL = "https://restcountries.com/v3.1/all?fields=name,cca2,translations,altSpellings"
MIN_MAG = 4.0          # "מעל 4" = 4.0 ומעלה (הנחה מתועדת ב-SPEC.md)
DAYS = 30
USGS_MAX_LIMIT = 20000  # המגבלה המתועדת של USGS לבקשה אחת
OTHER = "לא זוהתה מדינה"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
    "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
    "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
    "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
    "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
    "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
    "virginia", "washington", "west virginia", "wisconsin", "wyoming",
}
ALIASES = {
    "burma (myanmar)": "myanmar",
    "democratic republic of the congo": "dr congo",
    "republic of the congo": "republic of the congo",
    "south korea": "south korea",
    "taiwan": "taiwan",
    "kosovo": "kosovo",
}


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


def build_country_index(countries):
    """מילון: שם באנגלית (אותיות קטנות) -> שם בעברית."""
    index = {}
    for c in countries:
        he = c.get("translations", {}).get("heb", {}).get("common")
        if not he:
            continue
        names = {c["name"]["common"], c["name"]["official"], *c.get("altSpellings", [])}
        for n in names:
            if len(n) > 2:  # מדלגים על קודים קצרים שעלולים להתנגש
                index.setdefault(n.lower(), he)
    return index


def country_from_place(place, index):
    """USGS מחזיר טקסט חופשי כמו '103 km ENE of Noda, Japan'. לוקחים את החלק שאחרי הפסיק האחרון."""
    if not place:
        return OTHER
    tail = place.rsplit(",", 1)[1].strip() if "," in place else place.strip()
    key = tail.lower()
    if key in US_STATES:
        key = "united states"
    key = ALIASES.get(key, key)
    return index.get(key, OTHER)


def parse_events(geojson, index):
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
            "lat": lat,
            "lon": lon,
            "depth": depth,
            "country": country_from_place(p.get("place"), index) if index else OTHER,
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
    countries = {}
    for e in events:
        if e["country"] != OTHER:
            countries[e["country"]] = countries.get(e["country"], 0) + 1
    top = sorted(countries.items(), key=lambda kv: -kv[1])[:10]
    return {
        "total_4_and_above": len(events),
        "buckets": buckets,
        "strongest": strongest,
        "country_identified": sum(countries.values()),
        "country_unidentified": len(events) - sum(countries.values()),
        "top_countries": [{"country": k, "count": v} for k, v in top],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", help="קובץ GeoJSON מקומי לבדיקה במקום שליפה מ-USGS")
    ap.add_argument("--skip-countries", action="store_true", help="לא לפנות ל-REST Countries")
    args = ap.parse_args()

    now = datetime.now(timezone.utc).replace(microsecond=0)
    geojson = json.loads(Path(args.input).read_text(encoding="utf-8")) if args.input else fetch_usgs(now)
    index = {} if args.skip_countries else build_country_index(fetch_json(COUNTRIES_URL))

    events = parse_events(geojson, index)
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
    s = payload["summary"]
    print(f"נשמרו {s['total_4_and_above']} רעידות; מדינה זוהתה ב-{s['country_identified']}.")


if __name__ == "__main__":
    main()
