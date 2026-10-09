# מקורות

| מקור | שימוש | כתובת | מפתח |
|---|---|---|---|
| USGS Earthquake Catalog (FDSN Event) | רשימת הרעידות: זמן, עוצמה, מיקום, קואורדינטות | https://earthquake.usgs.gov/fdsnws/event/1/ | לא נדרש |
| REST Countries | שם המדינה בעברית | https://restcountries.com/ | לא נדרש |
| Chart.js 4.4.1 | גרף | https://www.chartjs.org/ | לא רלוונטי |
| Leaflet 1.9.4 | מפה | https://leafletjs.com/ | לא רלוונטי |
| OpenStreetMap | אריחי המפה | https://www.openstreetmap.org/copyright | לא נדרש |

## הערות
- תאריך השליפה והטווח נשמרים בשדה `meta` בקובץ `data/quakes.json`.
- USGS מחזיר מיקום כטקסט חופשי, ולכן זיהוי המדינה הוא הערכה ולא נתון מקורי. רעידות שלא זוהו מסומנות "לא זוהתה מדינה".
- לפני שימוש חוזר בנתונים, יש לבדוק את תנאי השימוש של כל מקור.
