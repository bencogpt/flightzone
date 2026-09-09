#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===============================================================================
File: tools/fixtures/make_fixture.py
Purpose: מייצר נתוני בדיקה סינתטיים בפורמט Esri-JSON — עיירה קטנה ברשת ישראל
         החדשה (wkid 2039) — כדי לבדוק את arcgis2noizz.py מקצה לקצה בלי גישה
         לשרת ArcGIS אמיתי.
Output:  buildings.json · roads.json · spots.json באותה תיקייה.
Notes:   ה-seed קבוע, ולכן אותם נתונים נוצרים בכל הרצה.
Author: Claude Code · 2026-09-09
===============================================================================
"""

import json                                   # כתיבת קבצי JSON
import math                                   # סינוס וקוסינוס לסיבוב מלבנים
import os                                     # בניית נתיבי הפלט
import random                                 # מחולל אקראי עם seed קבוע

random.seed(26126)                            # seed קבוע — נתונים זהים בכל הרצה
HERE = os.path.dirname(os.path.abspath(__file__))   # תיקיית הקובץ הנוכחי

X0, Y0 = 178000.0, 664600.0                   # פינת העיירה ברשת ישראל, במטרים
SPAN = 1100.0                                 # גודל העיירה במטרים
LANES = 6                                     # מספר הצירים בכל כיוון


def esri(features, geom_type):
    """עטיפת רשומות במעטפת Esri-JSON, כפי שהיא מגיעה משרת ArcGIS אמיתי."""
    return {
        "geometryType": geom_type,            # סוג הגאומטריה של השכבה
        "spatialReference": {"wkid": 2039},   # רשת ישראל החדשה
        "fields": [],                          # לא נדרש לצורך הבדיקה
        "features": features                   # הרשומות עצמן
    }


def rect(cx, cy, w, h, angle):
    """מלבן מסובב סביב מרכזו — מחזיר טבעת בכיוון השעון."""
    ca, sa = math.cos(angle), math.sin(angle)  # רכיבי הסיבוב
    pts = []                                   # הטבעת
    for dx, dy in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)):
        pts.append([cx + dx * ca - dy * sa, cy + dx * sa + dy * ca])   # קודקוד מסובב
    pts.append(pts[0])                         # Esri סוגר את הטבעת
    return pts


def lshape(cx, cy, w, h, angle):
    """צורת L — כדי לוודא שהרנדרר מטפל במצולעים שאינם מלבנים."""
    ca, sa = math.cos(angle), math.sin(angle)  # רכיבי הסיבוב
    raw = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, 0), (0, 0), (0, h / 2), (-w / 2, h / 2)]
    pts = [[cx + dx * ca - dy * sa, cy + dx * sa + dy * ca] for dx, dy in raw]   # סיבוב
    pts.append(pts[0])                         # סגירת הטבעת
    return pts


# --- כבישים: צירים עם ג'יטר וכיפוף קל, כדי שהרשת לא תהיה מושלמת ---
roads = []                                     # רשומות הכבישים
lane_x, lane_y = [], []                        # מיקומי הצירים, לשימוש חוזר
for i in range(LANES):                         # מעבר על הצירים
    base = SPAN * (i + 0.5) / LANES            # מיקום בסיסי בתוך העיירה
    lane_x.append(base + random.uniform(-25, 25))   # ג'יטר אופקי
    lane_y.append(base + random.uniform(-25, 25))   # ג'יטר אנכי

for i, x in enumerate(lane_x):                 # שדרות אנכיות
    path = [[X0 + x + random.uniform(-8, 8), Y0 + t] for t in (0, SPAN / 2, SPAN)]
    roads.append({"attributes": {"WIDTH": 14 if i == 2 else 9, "NAME": "Avenue %d" % i},
                  "geometry": {"paths": [path]}})
for i, y in enumerate(lane_y):                 # רחובות אופקיים
    path = [[X0 + t, Y0 + y + random.uniform(-8, 8)] for t in (0, SPAN / 2, SPAN)]
    roads.append({"attributes": {"WIDTH": 12 if i == 2 else 8, "NAME": "Street %d" % i},
                  "geometry": {"paths": [path]}})
roads.append({"attributes": {"WIDTH": 10, "NAME": "Diagonal"},          # אלכסון
              "geometry": {"paths": [[[X0 + 55, Y0 + 55], [X0 + 480, Y0 + 440],
                                      [X0 + 1030, Y0 + 1045]]]}})

# --- בניינים: 2 עד 5 בכל מבנן, בגדלים, בזוויות ובייעודים משתנים ---
buildings = []                                 # רשומות הבניינים
uses = ["commercial", "industrial", "residential", "public"]   # ערכי שדה הייעוד
for ix in range(LANES - 1):                    # מבננים בציר X
    for iy in range(LANES - 1):                # ובציר Y
        x_lo, x_hi = lane_x[ix] + 22, lane_x[ix + 1] - 22      # גבולות המבנן
        y_lo, y_hi = lane_y[iy] + 22, lane_y[iy + 1] - 22
        if x_hi - x_lo < 50 or y_hi - y_lo < 50:               # מבנן צר מדי
            continue
        use = uses[(ix + iy) % len(uses)]                      # ייעוד מחזורי
        for _ in range(random.randint(3, 6)):                  # כמה בניינים במבנן
            w = random.uniform(22, min(70, x_hi - x_lo))       # מידות הבניין
            h = random.uniform(22, min(70, y_hi - y_lo))
            cx = X0 + random.uniform(x_lo + w / 2, x_hi - w / 2)   # מרכז בתוך המבנן
            cy = Y0 + random.uniform(y_lo + h / 2, y_hi - h / 2)
            angle = random.uniform(-0.14, 0.14)                # סטייה קלה מהצירים
            ring = lshape(cx, cy, w, h, angle) if random.random() < 0.3 else rect(cx, cy, w, h, angle)
            floors = random.randint(2, 9) if use == "commercial" else random.randint(1, 5)
            buildings.append({"attributes": {"FLOORS": floors, "LANDUSE": use},
                              "geometry": {"rings": [ring]}})

# --- שאריות זעירות ומצולע מנוון, כדי לבדוק שהסינון עובד ---
buildings.append({"attributes": {"FLOORS": 2, "LANDUSE": "residential"},
                  "geometry": {"rings": [rect(X0 + 600, Y0 + 600, 2, 2, 0)]}})   # 4 מ"ר
buildings.append({"attributes": {"FLOORS": 2, "LANDUSE": "residential"},
                  "geometry": {"rings": [[[X0, Y0], [X0 + 1, Y0], [X0, Y0]]]}})  # קו, לא שטח

# --- נקודות איסוף לאורך הצירים ---
spots = []                                     # רשומות הנקודות
for i in range(12):                            # שתים עשרה נקודות
    if i % 2 == 0:                             # לסירוגין על ציר אנכי ואופקי
        x, y = lane_x[i % LANES], random.uniform(60, SPAN - 60)
    else:
        x, y = random.uniform(60, SPAN - 60), lane_y[i % LANES]
    spots.append({"attributes": {"NAME": "עמדה %d" % (i + 1)},
                  "geometry": {"x": X0 + x, "y": Y0 + y}})

# --- כתיבה לקבצים ---
for name, payload in (("buildings", esri(buildings, "esriGeometryPolygon")),
                      ("roads", esri(roads, "esriGeometryPolyline")),
                      ("spots", esri(spots, "esriGeometryPoint"))):
    path = os.path.join(HERE, name + ".json")   # נתיב הפלט
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False)
    print("נכתב %s — %d רשומות" % (path, len(payload["features"])))
