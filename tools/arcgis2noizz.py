#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File: tools/arcgis2noizz.py
Purpose: ממיר נתוני GIS (מצולעי בניינים, צירי כבישים ונקודות עניין) לפורמט
         העולם של משחק NOIZZ26, כך שהמשחק יציג את הרחובות והבניינים האמיתיים
         של אזור נתון בסגנון GTA2 במקום עיר פרוצדורלית.

Inputs:  שני מצבים, נבחרים בקובץ ההגדרות:
         "url"   — שליפה ישירה מ-ArcGIS REST (FeatureServer / MapServer)
         "files" — קבצי GeoJSON או Esri-JSON שיוצאו מראש (QGIS / ArcGIS Pro)

Output:  קובץ JSON יחיד + בלוק JavaScript מוכן להדבקה בתוך noizz26.html.

Dependencies:
         אין. ספריית התקן של Python 3.8+ בלבד (urllib, json, math, base64).
         נכתב כך במכוון כדי שירוץ ברשת פנימית ללא pip install.

Security:
         • ה-token נקרא מהמשתנה הסביבתי NOIZZ_ARCGIS_TOKEN. אפשר גם לשים אותו
           בקובץ ההגדרות, אך הכלי יתריע — קובץ הגדרות נוטה להגיע ל-git.
         • ה-token לעולם אינו מודפס, גם לא בהודעות שגיאה או ב-URL שבדוח.
         • מותרות רק כתובות http/https, עם timeout, ותקרה למספר הרשומות.
         • כל הקלט הגאומטרי נבדק: טיפוסים, ערכים סופיים, מספר קודקודים.

Author: Claude Code · 2026-09-09
===============================================================================
"""

import argparse                      # ניתוח ארגומנטים משורת הפקודה
import json                          # קריאה וכתיבה של JSON
import math                          # פונקציות מתמטיות לגאומטריה
import os                            # גישה למשתני סביבה ולנתיבים
import ssl                           # הקשר TLS לבקשות https
import sys                           # יציאה עם קוד שגיאה והדפסה ל-stderr
import urllib.parse                  # בניית מחרוזות שאילתה מקודדות
import urllib.request                # ביצוע בקשות HTTP
import urllib.error                  # טיפול בשגיאות HTTP

# מגבלות קשיחות — מגן מפני שכבה ענקית שתתקע את הכלי או תנפח את הפלט
MAX_FEATURES = 200000                # תקרת רשומות לכל שכבה
MAX_RING_POINTS = 5000               # תקרת קודקודים לטבעת בודדת לפני פישוט
PAGE_SIZE = 1000                     # כמה רשומות לבקש בכל עמוד מ-ArcGIS
HTTP_TIMEOUT = 60                    # שניות עד ויתור על בקשה


# =============================================================================
# חלק 1 — קריאת ההגדרות
# =============================================================================

DEFAULT_WORLD = {
    "pixelsPerMeter": 1.2,           # כמה פיקסלים במשחק שווים מטר בשטח
    "maxWorldPx": 3500,              # תקרת גודל העולם — מעליה הרצפה כבדה מדי לזיכרון
    "cellPx": 8,                     # גודל תא ברשת ההתנגשות, בפיקסלים
    "simplifyMeters": 1.5,           # סף פישוט מצולעים (Douglas-Peucker)
    "minAreaSqM": 25.0,              # מצולע קטן מזה נחשב שארית ונזרק
    "maxBuildings": 4000,            # תקרת בניינים בפלט
    "marginMeters": 40.0             # שוליים סביב הנתונים, כדי שלא ייגעו בקצה
}

DEFAULT_FIELDS = {
    "floors": None,                  # שם שדה מספר הקומות
    "heightMeters": None,            # שם שדה הגובה במטרים (חלופה לקומות)
    "metersPerFloor": 3.2,           # להמרת גובה לקומות
    "defaultFloors": 3,              # כשאין נתון גובה כלל
    "minFloors": 1,                  # תחום סביר, מונע בניינים מעוותים
    "maxFloors": 12,
    "district": None,                # שם שדה ייעוד/אזור
    "districtMap": {},               # מיפוי ערך השדה לאינדקס שכונה 0..3
    "districtFallback": "byFloors",  # "byFloors" או "fixed"
    "districtFixed": 0,              # השכונה שתשמש כשהמיפוי לא חל
    "roadWidth": None,               # שם שדה רוחב הכביש במטרים
    "defaultRoadWidthMeters": 9.0,   # רוחב ברירת מחדל
    "roadWidthScale": 1.3,           # הרחבה לצורכי משחקיות — הכביש מצויר רחב מהמציאות
    "spotName": None                 # שם שדה לכיתוב נקודת האיסוף
}


def load_config(path):
    """קריאת קובץ ההגדרות והשלמת ברירות מחדל לכל מפתח חסר."""
    with open(path, "r", encoding="utf-8") as fh:          # פתיחה בקידוד מפורש
        cfg = json.load(fh)                                # פענוח
    if not isinstance(cfg, dict):                          # ולידציה בסיסית
        raise ValueError("קובץ ההגדרות אינו אובייקט JSON")
    cfg.setdefault("source", {})                           # בלוק המקור
    cfg.setdefault("files", {})                            # בלוק הקבצים
    fields = dict(DEFAULT_FIELDS)                          # עותק של ברירות המחדל
    fields.update(cfg.get("fields") or {})                 # דריסה במה שהוגדר
    cfg["fields"] = fields                                 # החזרה לקונפיג
    world = dict(DEFAULT_WORLD)                            # אותו דבר לבלוק העולם
    world.update(cfg.get("world") or {})
    cfg["world"] = world
    base = os.path.dirname(os.path.abspath(path))          # תיקיית קובץ ההגדרות
    files = cfg.get("files") or {}                         # נתיבי הקבצים המיוצאים
    for key, value in list(files.items()):                 # מעבר על כל שכבה
        if isinstance(value, str) and not os.path.isabs(value):
            files[key] = os.path.join(base, value)         # נתיב יחסי לקובץ ההגדרות
    cfg["files"] = files                                   # החזרה לקונפיג
    return cfg                                             # ההגדרות המלאות


def get_token(cfg):
    """שליפת ה-token: קודם מהסביבה, ורק אחר כך מקובץ ההגדרות (עם אזהרה)."""
    token = os.environ.get("NOIZZ_ARCGIS_TOKEN")           # המקור המועדף
    if token:
        return token                                       # נמצא בסביבה
    token = (cfg.get("source") or {}).get("token")         # חלופה בקובץ
    if token:
        warn("ה-token נמצא בקובץ ההגדרות. עדיף להעביר אותו דרך NOIZZ_ARCGIS_TOKEN "
             "כדי שלא ייכנס ל-git.")
    return token                                           # ייתכן None — שרת פתוח


# =============================================================================
# חלק 2 — קריאת נתונים מ-ArcGIS או מקבצים
# =============================================================================

def http_get_json(url, params, token):
    """בקשת GET שמחזירה JSON. ה-token נוסף לפרמטרים אך לעולם אינו מודפס."""
    if not url.lower().startswith(("http://", "https://")):    # רק פרוטוקולי רשת
        raise ValueError("כתובת חייבת להתחיל ב-http:// או https://")
    query = dict(params)                                        # עותק לעבודה
    if token:
        query["token"] = token                                  # הוספת האימות
    full = url.rstrip("/") + "?" + urllib.parse.urlencode(query, doseq=True)
    safe = full.split("&token=")[0]                             # גרסה בטוחה להדפסה
    ctx = ssl.create_default_context()                          # אימות תעודות כרגיל
    req = urllib.request.Request(full, headers={"User-Agent": "arcgis2noizz/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT, context=ctx) as resp:
            raw = resp.read()                                   # גוף התשובה
    except urllib.error.HTTPError as exc:                       # שגיאת HTTP מהשרת
        raise RuntimeError("השרת החזיר %s עבור %s" % (exc.code, safe))
    except Exception as exc:                                    # רשת, DNS, TLS
        raise RuntimeError("הבקשה נכשלה (%s) עבור %s" % (type(exc).__name__, safe))
    try:
        data = json.loads(raw.decode("utf-8"))                  # פענוח
    except Exception:
        raise RuntimeError("התשובה מ-%s אינה JSON תקין" % safe)
    if isinstance(data, dict) and "error" in data:              # ArcGIS מחזיר שגיאות ב-200
        msg = (data["error"] or {}).get("message", "שגיאה לא מפורטת")
        raise RuntimeError("ArcGIS: %s (%s)" % (msg, safe))
    return data                                                 # התשובה המפוענחת


def query_layer(layer_cfg, out_sr, bbox, token):
    """שליפת כל הרשומות משכבת ArcGIS, עם עימוד עד שהשרת מסיים."""
    url = layer_cfg["url"].rstrip("/")                          # כתובת השכבה
    if not url.endswith("/query"):                              # נוחות: מותר לתת את השכבה
        url += "/query"
    features = []                                               # אוסף הרשומות
    offset = 0                                                  # מיקום בעימוד
    while True:
        params = {
            "where": layer_cfg.get("where") or "1=1",           # סינון, ברירת מחדל הכול
            "outFields": "*",                                   # כל השדות
            "outSR": out_sr,                                    # השרת מבצע את ההיטל
            "returnGeometry": "true",                           # אנחנו צריכים גאומטריה
            "f": "json",                                        # פורמט Esri-JSON
            "resultOffset": offset,                             # תחילת העמוד
            "resultRecordCount": PAGE_SIZE                      # גודל העמוד
        }
        if bbox:                                                # חיתוך מרחבי אם הוגדר
            params.update({
                "geometry": "%f,%f,%f,%f" % tuple(bbox),
                "geometryType": "esriGeometryEnvelope",
                "inSR": out_sr,
                "spatialRel": "esriSpatialRelIntersects"
            })
        data = http_get_json(url, params, token)                 # הבקשה עצמה
        page = data.get("features") or []                        # רשומות העמוד
        features.extend(page)                                    # צירוף לאוסף
        if len(features) >= MAX_FEATURES:                        # תקרת ביטחון
            warn("השכבה חרגה מ-%d רשומות — נעצר." % MAX_FEATURES)
            break
        if not data.get("exceededTransferLimit") or not page:    # אין עוד עמודים
            break
        offset += len(page)                                      # לעמוד הבא
    return features                                              # כל הרשומות


def read_feature_file(path):
    """קריאת קובץ GeoJSON או Esri-JSON והחזרת רשימת הרשומות הגולמיות."""
    with open(path, "r", encoding="utf-8") as fh:                # פתיחה
        data = json.load(fh)                                     # פענוח
    if isinstance(data, dict) and "features" in data:            # שני הפורמטים משתמשים ב-features
        return data["features"]
    raise ValueError("הקובץ %s אינו מכיל מערך features" % path)


def warn(msg):
    """הדפסת אזהרה ל-stderr, כדי שלא תתערבב בפלט הנתונים."""
    print("⚠️  " + msg, file=sys.stderr)


# =============================================================================
# חלק 3 — נירמול גאומטריה: Esri-JSON ו-GeoJSON לאותו מבנה פנימי
# =============================================================================

def finite_pair(pt):
    """המרת קודקוד לזוג מספרים סופיים, או None אם הקלט פגום."""
    try:
        x = float(pt[0])                                     # קואורדינטת X
        y = float(pt[1])                                     # קואורדינטת Y
    except (TypeError, ValueError, IndexError):
        return None                                          # קלט שאינו זוג מספרים
    if not (math.isfinite(x) and math.isfinite(y)):          # NaN או אינסוף
        return None
    return (x, y)                                            # קודקוד תקין


def clean_ring(raw):
    """ניקוי טבעת: קודקודים תקינים בלבד, ללא כפילויות עוקבות, ללא סגירה כפולה."""
    out = []                                                 # הטבעת הנקייה
    for pt in raw[:MAX_RING_POINTS]:                         # תקרת קודקודים
        p = finite_pair(pt)                                  # ולידציה
        if p is None:
            continue                                         # דילוג על קודקוד פגום
        if out and abs(p[0] - out[-1][0]) < 1e-9 and abs(p[1] - out[-1][1]) < 1e-9:
            continue                                         # כפילות עוקבת
        out.append(p)                                        # הוספה
    while len(out) > 1 and abs(out[0][0] - out[-1][0]) < 1e-9 and abs(out[0][1] - out[-1][1]) < 1e-9:
        out.pop()                                            # הסרת הסגירה — נשמור טבעת פתוחה
    return out                                               # הטבעת


def extract_polygons(feature):
    """החזרת הטבעות החיצוניות של רשומה, משני הפורמטים. חורים פנימיים מדולגים."""
    geom = feature.get("geometry")                           # הגאומטריה הגולמית
    if not isinstance(geom, dict):
        return []                                            # ללא גאומטריה
    rings = []                                               # הטבעות שנאספו
    if "rings" in geom:                                      # Esri-JSON
        for ring in geom.get("rings") or []:                 # מעבר על הטבעות
            r = clean_ring(ring)                             # ניקוי
            if len(r) >= 3:
                rings.append(r)                              # טבעת שמישה
    elif geom.get("type") in ("Polygon", "MultiPolygon"):    # GeoJSON
        coords = geom.get("coordinates") or []               # מבנה הקואורדינטות
        groups = [coords] if geom["type"] == "Polygon" else coords  # איחוד המקרים
        for poly in groups:                                  # כל מצולע
            if poly:                                         # האיבר הראשון הוא הטבעת החיצונית
                r = clean_ring(poly[0])                      # חורים פנימיים מדולגים במכוון
                if len(r) >= 3:
                    rings.append(r)
    return rings                                             # רק טבעות חיצוניות


def extract_paths(feature):
    """החזרת הצירים של רשומת קו, משני הפורמטים."""
    geom = feature.get("geometry")                           # הגאומטריה
    if not isinstance(geom, dict):
        return []
    paths = []                                               # הצירים שנאספו
    if "paths" in geom:                                      # Esri-JSON
        for path in geom.get("paths") or []:
            p = clean_ring(path)                             # אותו ניקוי
            if len(p) >= 2:
                paths.append(p)
    elif geom.get("type") in ("LineString", "MultiLineString"):   # GeoJSON
        coords = geom.get("coordinates") or []
        groups = [coords] if geom["type"] == "LineString" else coords
        for line in groups:
            p = clean_ring(line)
            if len(p) >= 2:
                paths.append(p)
    return paths                                             # הצירים


def extract_point(feature):
    """החזרת נקודה בודדת מרשומה, משני הפורמטים."""
    geom = feature.get("geometry")                           # הגאומטריה
    if not isinstance(geom, dict):
        return None
    if "x" in geom and "y" in geom:                          # Esri-JSON
        return finite_pair((geom["x"], geom["y"]))
    if geom.get("type") == "Point":                          # GeoJSON
        return finite_pair(geom.get("coordinates") or [])
    return None                                              # לא נקודה


def attrs_of(feature):
    """שליפת מילון התכונות, משני הפורמטים."""
    a = feature.get("attributes")                            # Esri-JSON
    if isinstance(a, dict):
        return a
    p = feature.get("properties")                            # GeoJSON
    return p if isinstance(p, dict) else {}                  # תמיד מילון


# =============================================================================
# חלק 4 — פעולות גאומטריות
# =============================================================================

def signed_area(ring):
    """שטח מסומן (נוסחת שרוכי הנעל). הסימן מעיד על כיוון הקיפוף."""
    total = 0.0                                              # הצובר
    n = len(ring)                                            # מספר הקודקודים
    for i in range(n):                                       # מעבר על הצלעות
        x1, y1 = ring[i]                                     # קודקוד נוכחי
        x2, y2 = ring[(i + 1) % n]                           # הקודקוד הבא, מעגלי
        total += x1 * y2 - x2 * y1                           # תרומת הצלע
    return total / 2.0                                       # השטח המסומן


def ensure_clockwise(ring):
    """נירמול כיוון הטבעת לשעון במערכת המסך (Y יורד) — שטח מסומן חיובי.
       זה קריטי: הרנדרר מחשב נורמל יוצא כ-(dy,-dx), וזה נכון רק בכיוון אחד."""
    return ring if signed_area(ring) > 0 else ring[::-1]     # היפוך אם צריך


def simplify(points, tol, closed):
    """פישוט Douglas-Peucker — מוריד קודקודים מבלי לשנות את הצורה מעבר לסף."""
    if tol <= 0 or len(points) < 3:                          # אין מה לפשט
        return points
    pts = points + [points[0]] if closed else points         # טבעת נסגרת זמנית
    keep = _dp(pts, 0, len(pts) - 1, tol)                    # הרקורסיה
    result = [pts[i] for i in sorted(keep)]                  # הקודקודים ששרדו
    if closed and len(result) > 1 and result[0] == result[-1]:
        result.pop()                                         # פתיחת הטבעת בחזרה
    return result                                            # הצורה המפושטת


def _dp(pts, first, last, tol):
    """עזר רקורסיבי ל-Douglas-Peucker: מחזיר את קבוצת האינדקסים לשמירה."""
    keep = {first, last}                                     # הקצוות תמיד נשמרים
    if last <= first + 1:                                    # אין נקודות באמצע
        return keep
    x1, y1 = pts[first]                                      # קצה א'
    x2, y2 = pts[last]                                       # קצה ב'
    dx, dy = x2 - x1, y2 - y1                                # וקטור המיתר
    norm = math.hypot(dx, dy)                                # אורכו
    worst, worst_i = -1.0, first                             # המרחק הגדול ביותר
    for i in range(first + 1, last):                         # כל נקודת ביניים
        px, py = pts[i]                                      # הנקודה
        if norm < 1e-12:                                     # מיתר מנוון — מרחק ישיר
            dist = math.hypot(px - x1, py - y1)
        else:                                                # מרחק מהישר
            dist = abs(dy * px - dx * py + x2 * y1 - y2 * x1) / norm
        if dist > worst:                                     # שיא חדש
            worst, worst_i = dist, i
    if worst <= tol:                                         # הכול בתוך הסף
        return keep
    keep |= _dp(pts, first, worst_i, tol)                    # פיצול משמאל
    keep |= _dp(pts, worst_i, last, tol)                     # ומימין
    return keep                                              # האינדקסים לשמירה


def bbox_of(points):
    """תיבה חוסמת של רשימת קודקודים."""
    xs = [p[0] for p in points]                              # כל ה-X
    ys = [p[1] for p in points]                              # כל ה-Y
    return (min(xs), min(ys), max(xs), max(ys))              # xmin,ymin,xmax,ymax


def rasterize(ring, grid, grid_w, grid_h, cell):
    """מילוי מצולע לרשת ההתנגשות בסריקת שורות. כל תא שמרכזו בתוך המצולע נחסם."""
    xs = [p[0] for p in ring]                                # קואורדינטות X
    ys = [p[1] for p in ring]                                # קואורדינטות Y
    row0 = max(0, int(min(ys) // cell))                      # שורת ההתחלה ברשת
    row1 = min(grid_h - 1, int(max(ys) // cell))             # שורת הסיום
    n = len(ring)                                            # מספר הקודקודים
    for row in range(row0, row1 + 1):                        # מעבר על השורות
        yc = (row + 0.5) * cell                              # מרכז השורה
        crossings = []                                       # חיתוכים עם הצלעות
        for i in range(n):                                   # כל צלע
            x1, y1 = ring[i]                                 # קצה א'
            x2, y2 = ring[(i + 1) % n]                       # קצה ב'
            if (y1 <= yc < y2) or (y2 <= yc < y1):           # הצלע חוצה את השורה
                t = (yc - y1) / (y2 - y1)                    # מיקום יחסי על הצלע
                crossings.append(x1 + t * (x2 - x1))         # ה-X של החיתוך
        if len(crossings) < 2:                               # אין זוג — אין מה למלא
            continue
        crossings.sort()                                     # מיון משמאל לימין
        base = row * grid_w                                  # תחילת השורה במערך
        for k in range(0, len(crossings) - 1, 2):            # זוגות: כניסה ויציאה
            col0 = max(0, int(math.floor(crossings[k] / cell)))         # תא ראשון
            col1 = min(grid_w - 1, int(math.ceil(crossings[k + 1] / cell)) - 1)  # אחרון
            for col in range(col0, col1 + 1):                # מילוי הקטע
                grid[base + col] = 1                         # התא חסום


def encode_rle(grid):
    """דחיסת רשת ההתנגשות ל-RLE בבסיס 36: אורכי רצפים לסירוגין, החל ברצף פנוי."""
    runs = []                                                # אורכי הרצפים
    current = 0                                              # הערך של הרצף הנוכחי
    count = 0                                                # אורכו
    for value in grid:                                       # מעבר על כל התאים
        if value == current:                                 # ממשיכים באותו רצף
            count += 1
        else:                                                # רצף חדש
            runs.append(count)                               # סגירת הקודם
            current = value                                  # החלפת הערך
            count = 1                                        # התחלה מחדש
    runs.append(count)                                       # הרצף האחרון
    return ",".join(_b36(r) for r in runs)                   # מחרוזת קומפקטית


def _b36(num):
    """המרת מספר שלם אי-שלילי לבסיס 36 — מקצר את מחרוזת ה-RLE משמעותית."""
    if num == 0:
        return "0"                                           # מקרה קצה
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"          # ספרות הבסיס
    out = ""                                                 # המחרוזת הנבנית
    while num:                                               # חילוץ ספרה בכל סיבוב
        out = digits[num % 36] + out                         # הוספה מלפנים
        num //= 36                                           # קידום
    return out                                               # התוצאה


# =============================================================================
# חלק 5 — בניית עולם המשחק
# =============================================================================

def pick_floors(attrs, fields):
    """קביעת מספר הקומות של בניין: שדה קומות, אחרת גובה במטרים, אחרת ברירת מחדל."""
    floors = None                                            # התוצאה
    name = fields.get("floors")                              # שם שדה הקומות
    if name and attrs.get(name) is not None:                 # קיים ערך
        try:
            floors = int(round(float(attrs[name])))          # המרה בטוחה
        except (TypeError, ValueError):
            floors = None                                    # ערך לא מספרי — מתעלמים
    if floors is None:                                       # ניסיון שני: גובה במטרים
        hname = fields.get("heightMeters")
        if hname and attrs.get(hname) is not None:
            try:
                meters = float(attrs[hname])                 # הגובה
                per = float(fields.get("metersPerFloor") or 3.2)   # מטרים לקומה
                if per > 0:
                    floors = int(round(meters / per))        # המרה לקומות
            except (TypeError, ValueError):
                floors = None
    if floors is None:                                       # אין נתון בכלל
        floors = int(fields.get("defaultFloors") or 3)
    lo = int(fields.get("minFloors") or 1)                   # גבולות סבירים
    hi = int(fields.get("maxFloors") or 12)
    return max(lo, min(hi, floors))                          # הגבלה לתחום


def pick_district(attrs, fields, floors):
    """קביעת אינדקס השכונה: משדה ייעוד אם קיים, אחרת לפי גובה הבניין."""
    name = fields.get("district")                            # שם שדה הייעוד
    mapping = fields.get("districtMap") or {}                # מיפוי ערך לאינדקס
    if name and attrs.get(name) is not None:                 # יש ערך בשדה
        key = str(attrs[name]).strip()                       # נירמול למחרוזת
        if key in mapping:                                   # קיים במיפוי
            try:
                return max(0, min(3, int(mapping[key])))     # אינדקס בתחום 0..3
            except (TypeError, ValueError):
                pass                                         # מיפוי פגום — ממשיכים לגיבוי
    if (fields.get("districtFallback") or "byFloors") == "byFloors":
        if floors >= 5:                                      # גבוה — מרכז עסקים
            return 0
        if floors >= 3:                                      # בינוני — מגורים
            return 2
        return 1                                             # נמוך — תעשייה
    return max(0, min(3, int(fields.get("districtFixed") or 0)))   # שכונה קבועה


def build_world(buildings_raw, roads_raw, spots_raw, cfg, report):
    """הלב: המרת הגאומטריה ממטרים לפיקסלים, רסטור החסימות ובניית מבנה הפלט."""
    fields = cfg["fields"]                                   # מיפוי השדות
    wcfg = cfg["world"]                                      # הגדרות העולם

    # --- איסוף כל הגאומטריה במטרים, לצורך חישוב התיבה החוסמת ---
    polys_m = []                                             # מצולעי בניינים במטרים
    for feat in buildings_raw:                               # מעבר על רשומות הבניינים
        attrs = attrs_of(feat)                               # התכונות
        for ring in extract_polygons(feat):                  # כל טבעת חיצונית
            area = abs(signed_area(ring))                    # שטח במ"ר
            if area < float(wcfg["minAreaSqM"]):             # שארית זעירה
                report["skipped_small"] += 1
                continue
            polys_m.append((ring, attrs))                    # נשמר לעיבוד

    paths_m = []                                             # צירי כבישים במטרים
    for feat in roads_raw:                                   # מעבר על רשומות הכבישים
        attrs = attrs_of(feat)                               # התכונות
        width = float(fields.get("defaultRoadWidthMeters") or 9.0)   # רוחב ברירת מחדל
        wname = fields.get("roadWidth")                      # שדה רוחב, אם הוגדר
        if wname and attrs.get(wname) is not None:
            try:
                width = max(3.0, min(60.0, float(attrs[wname])))     # תחום סביר
            except (TypeError, ValueError):
                pass                                         # ערך פגום — ברירת המחדל
        for path in extract_paths(feat):                     # כל ציר
            paths_m.append((path, width))                    # נשמר

    points_m = []                                            # נקודות עניין במטרים
    for feat in spots_raw:                                   # מעבר על הנקודות
        pt = extract_point(feat)                             # הגאומטריה
        if pt is None:
            continue                                         # לא נקודה
        label = ""                                           # כיתוב אופציונלי
        sname = fields.get("spotName")                       # שדה השם
        if sname and attrs_of(feat).get(sname) is not None:
            label = str(attrs_of(feat)[sname])[:60]          # חיתוך אורך
        points_m.append((pt, label))                         # נשמר

    if not polys_m and not paths_m:                          # אין ממה לבנות עולם
        raise RuntimeError("לא נמצאה גאומטריה שמישה — בדקו את הכתובות, ה-where וה-outSR")

    # --- תיבה חוסמת של כל הנתונים ---
    all_pts = []                                             # כל הקודקודים יחד
    for ring, _ in polys_m:
        all_pts.extend(ring)
    for path, _ in paths_m:
        all_pts.extend(path)
    for pt, _ in points_m:
        all_pts.append(pt)
    xmin, ymin, xmax, ymax = bbox_of(all_pts)                # הגבולות במטרים
    margin = float(wcfg["marginMeters"])                     # שוליים
    xmin -= margin; ymin -= margin                           # הרחבת התיבה
    xmax += margin; ymax += margin
    span = max(xmax - xmin, ymax - ymin)                     # הצלע הארוכה, במטרים

    # --- קנה מידה, עם הגבלה לגודל עולם שהזיכרון יכול לשאת ---
    ppm = float(wcfg["pixelsPerMeter"])                      # פיקסלים למטר מבוקש
    max_px = int(wcfg["maxWorldPx"])                         # תקרת גודל
    if span * ppm > max_px:                                  # חורגים מהתקרה
        new_ppm = max_px / span                              # הקטנת קנה המידה
        warn("קנה המידה הוקטן מ-%.3f ל-%.3f פיקסל/מטר כדי לא לחרוג מ-%d פיקסלים."
             % (ppm, new_ppm, max_px))
        ppm = new_ppm
    world_px = int(math.ceil(span * ppm))                    # גודל העולם בפיקסלים
    cell = int(wcfg["cellPx"])                               # גודל תא ההתנגשות
    grid_w = int(math.ceil(world_px / cell))                 # רוחב הרשת בתאים
    grid_h = grid_w                                          # העולם ריבועי
    world_px = grid_w * cell                                 # יישור לגבול תא שלם

    origin_x = xmin                                          # המטרים של פיקסל (0,0)
    origin_y = ymax                                          # הציר האנכי מתהפך

    def to_px(pt):
        """המרת קודקוד ממטרים לפיקסלים של המשחק, כולל היפוך ציר Y."""
        return ((pt[0] - origin_x) * ppm, (origin_y - pt[1]) * ppm)

    # --- בניינים: המרה, פישוט, נירמול כיוון ורסטור ---
    grid = bytearray(grid_w * grid_h)                        # רשת ההתנגשות, אפס = פנוי
    tol_px = float(wcfg["simplifyMeters"]) * ppm             # סף הפישוט בפיקסלים
    buildings = []                                           # רשומות הפלט
    for ring, attrs in polys_m:                              # מעבר על המצולעים
        if len(buildings) >= int(wcfg["maxBuildings"]):      # תקרת בניינים
            report["skipped_cap"] += 1
            continue
        px_ring = [to_px(p) for p in ring]                   # המרה לפיקסלים
        px_ring = simplify(px_ring, tol_px, True)            # פישוט
        if len(px_ring) < 3:                                 # התמוטט לקו — נזרק
            report["skipped_degenerate"] += 1
            continue
        px_ring = ensure_clockwise(px_ring)                  # נירמול כיוון הקיפוף
        rasterize(px_ring, grid, grid_w, grid_h, cell)       # חסימה ברשת
        floors = pick_floors(attrs, fields)                  # גובה
        flat = []                                            # מערך שטוח של קואורדינטות
        for x, y in px_ring:                                 # עיגול לשלמים — חוסך מקום
            flat.append(int(round(x)))
            flat.append(int(round(y)))
        buildings.append({"p": flat, "f": floors, "d": pick_district(attrs, fields, floors)})
        report["vertices"] += len(px_ring)                   # לצורך הדוח

    # --- כבישים ---
    roads = []                                               # רשומות הכבישים
    for path, width_m in paths_m:                            # מעבר על הצירים
        px_path = [to_px(p) for p in path]                   # המרה
        px_path = simplify(px_path, tol_px, False)           # פישוט
        if len(px_path) < 2:                                 # התמוטט לנקודה
            continue
        flat = []                                            # מערך שטוח
        for x, y in px_path:
            flat.append(int(round(x)))
            flat.append(int(round(y)))
        scale = float(fields.get("roadWidthScale") or 1.0)   # הרחבה לצורכי משחקיות
        roads.append({"p": flat, "w": max(6, int(round(width_m * ppm * scale)))})   # רוחב בפיקסלים

    # --- נקודות איסוף ---
    spots = []                                               # רשומות הנקודות
    for pt, label in points_m:                               # מעבר על הנקודות
        x, y = to_px(pt)                                     # המרה
        if not (0 <= x < world_px and 0 <= y < world_px):    # מחוץ לעולם
            continue
        entry = {"x": int(round(x)), "y": int(round(y))}     # רשומה
        if label:
            entry["name"] = label                            # כיתוב אם קיים
        spots.append(entry)

    # --- נקודת פתיחה: קודקוד הכביש הקרוב ביותר למרכז העולם ---
    center = world_px / 2.0                                  # מרכז העולם
    spawn = [int(center), int(center)]                       # ברירת מחדל
    best = None                                              # המרחק הקטן ביותר
    for road in roads:                                       # מעבר על הכבישים
        pts = road["p"]                                      # המערך השטוח
        for i in range(0, len(pts), 2):                      # כל קודקוד
            x, y = pts[i], pts[i + 1]                        # הקואורדינטות
            gx, gy = int(x // cell), int(y // cell)          # התא ברשת
            if not (0 <= gx < grid_w and 0 <= gy < grid_h):  # מחוץ לרשת
                continue
            if grid[gy * grid_w + gx]:                       # קודקוד בתוך בניין — לא מתאים
                continue
            d = (x - center) ** 2 + (y - center) ** 2        # מרחק ריבועי מהמרכז
            if best is None or d < best:                     # קרוב יותר
                best, spawn = d, [int(x), int(y)]            # עדכון

    return {
        "meta": {
            "generator": "arcgis2noizz.py 1.0",              # מזהה הכלי
            "wkid": cfg["source"].get("outSR", 2039),        # מערכת הקואורדינטות המקורית
            "originX": round(origin_x, 3),                   # המטרים של פיקסל (0,0)
            "originY": round(origin_y, 3),
            "pixelsPerMeter": round(ppm, 6),                 # קנה המידה בפועל
            "world": world_px,                               # גודל העולם בפיקסלים
            "cell": cell,                                    # גודל תא ההתנגשות
            "grid": grid_w,                                  # מספר התאים בכל ציר
            "spawn": spawn                                   # נקודת הפתיחה
        },
        "cells": encode_rle(grid),                           # רשת ההתנגשות, דחוסה
        "buildings": buildings,                              # המצולעים
        "roads": roads,                                      # הצירים
        "spots": spots                                       # נקודות האיסוף
    }


# =============================================================================
# חלק 6 — פלט והזרקה לקובץ המשחק
# =============================================================================

MARK_START = "/* >>> NOIZZ26-WORLD-DATA >>> */"              # תחילת הבלוק בקובץ המשחק
MARK_END = "/* <<< NOIZZ26-WORLD-DATA <<< */"                # סופו


def world_block(world):
    """בניית בלוק ה-JavaScript המוכן להדבקה, כולל סימני התחום."""
    payload = json.dumps(world, ensure_ascii=False, separators=(",", ":"))  # JSON קומפקטי
    return (MARK_START + "\n"                                # פתיחת התחום
            + "var WORLD_DATA = " + payload + ";\n"          # ההשמה עצמה
            + MARK_END)                                      # סגירת התחום


def inject(html_path, block):
    """החלפת הבלוק בתוך קובץ המשחק, בין שני סימני התחום."""
    with open(html_path, "r", encoding="utf-8") as fh:       # קריאת הקובץ
        html = fh.read()
    start = html.find(MARK_START)                            # איתור התחום
    end = html.find(MARK_END)
    if start < 0 or end < 0 or end < start:                  # התחום חסר או פגום
        raise RuntimeError("לא נמצאו סימני התחום בקובץ %s" % html_path)
    updated = html[:start] + block + html[end + len(MARK_END):]   # הרכבה מחדש
    with open(html_path, "w", encoding="utf-8") as fh:       # כתיבה חזרה
        fh.write(updated)


def collect(cfg, key, token, report):
    """שליפת רשומות שכבה אחת, לפי מצב המקור שנבחר בהגדרות."""
    mode = (cfg["source"].get("mode") or "url").lower()      # "url" או "files"
    if mode == "files":                                      # קריאה מקבצים מיוצאים
        path = (cfg.get("files") or {}).get(key)             # נתיב הקובץ
        if not path:
            return []                                        # שכבה אופציונלית שלא הוגדרה
        feats = read_feature_file(path)                      # קריאה
    else:                                                    # שליפה ישירה מ-ArcGIS
        layer = (cfg["source"].get(key) or {})               # הגדרות השכבה
        if not layer.get("url"):
            return []                                        # שכבה שלא הוגדרה
        feats = query_layer(layer, cfg["source"].get("outSR", 2039),
                            cfg["source"].get("bbox"), token)
    report["read_" + key] = len(feats)                       # לדוח
    return feats                                             # הרשומות


def main():
    """נקודת הכניסה: ניתוח ארגומנטים, הרצת הצינור והדפסת הדוח."""
    ap = argparse.ArgumentParser(description="ממיר נתוני GIS לעולם המשחק NOIZZ26")
    ap.add_argument("--config", required=True, help="נתיב לקובץ ההגדרות")
    ap.add_argument("--out", default="noizz26-world.json", help="נתיב קובץ הפלט")
    ap.add_argument("--block", default=None, help="נתיב לכתיבת בלוק ה-JavaScript להדבקה")
    ap.add_argument("--inject", default=None, help="נתיב ל-noizz26.html להזרקה אוטומטית")
    args = ap.parse_args()                                   # ניתוח השורה

    report = {"read_buildings": 0, "read_roads": 0, "read_spots": 0,
              "skipped_small": 0, "skipped_degenerate": 0, "skipped_cap": 0,
              "vertices": 0}                                 # מוני הדוח

    try:
        cfg = load_config(args.config)                       # ההגדרות
        token = get_token(cfg)                               # אימות, אם נדרש
        buildings_raw = collect(cfg, "buildings", token, report)   # שכבת הבניינים
        roads_raw = collect(cfg, "roads", token, report)           # שכבת הכבישים
        spots_raw = collect(cfg, "spots", token, report)           # שכבת הנקודות
        world = build_world(buildings_raw, roads_raw, spots_raw, cfg, report)  # הבנייה
    except Exception as exc:                                 # כשל — הודעה ברורה, בלי stack
        print("שגיאה: %s" % exc, file=sys.stderr)
        return 1                                             # קוד יציאה שגוי

    with open(args.out, "w", encoding="utf-8") as fh:        # כתיבת קובץ העולם
        json.dump(world, fh, ensure_ascii=False, separators=(",", ":"))

    block = world_block(world)                               # בלוק ה-JavaScript
    if args.block:                                           # כתיבה לקובץ נפרד
        with open(args.block, "w", encoding="utf-8") as fh:
            fh.write(block + "\n")
    if args.inject:                                          # הזרקה ישירה למשחק
        inject(args.inject, block)

    meta = world["meta"]                                     # לקיצור בדוח
    size_kb = len(block.encode("utf-8")) / 1024.0            # גודל הבלוק
    print("─" * 62)
    print("נקראו:      %d בניינים · %d כבישים · %d נקודות"
          % (report["read_buildings"], report["read_roads"], report["read_spots"]))
    print("נכנסו:      %d בניינים (%d קודקודים) · %d צירים · %d נקודות איסוף"
          % (len(world["buildings"]), report["vertices"],
             len(world["roads"]), len(world["spots"])))
    print("נפסלו:      %d קטנים מדי · %d מנוונים · %d מעל התקרה"
          % (report["skipped_small"], report["skipped_degenerate"], report["skipped_cap"]))
    print("עולם:       %d×%d פיקסלים · %.3f פיקסל/מטר · תא %d · רשת %d×%d"
          % (meta["world"], meta["world"], meta["pixelsPerMeter"],
             meta["cell"], meta["grid"], meta["grid"]))
    print("נקודת פתיחה: %s" % meta["spawn"])
    print("פלט:        %s · בלוק %.1f KB" % (args.out, size_kb))
    if size_kb > 900:                                        # אזהרת גודל
        warn("הבלוק גדול מ-900KB. שקלו pixelsPerMeter נמוך יותר, "
             "simplifyMeters גבוה יותר, או bbox קטן יותר.")
    print("─" * 62)
    return 0                                                 # הצלחה


if __name__ == "__main__":                                   # הרצה כתסריט
    sys.exit(main())                                         # קוד היציאה לסביבה
