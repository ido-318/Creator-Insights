# Supabase — תמונות מצב של Creator Insights

## מצב ההקמה

הקוד, המיגרציה וחיבור הממשק מוכנים. **עדיין לא הוקם פרויקט Supabase עבור Creator Insights ולא בוצע סנכרון חי.** בעת הבדיקה נמצא בחשבון פרויקט CRM לא פעיל; הוא לא שונה. בחירת הארגון לפרויקט החדש ממתינה לתשובת בעל הפרויקט.

## למה תמונת מצב אחת?

הפרויקט מנתח מאגר קטן של 499 פוסטים. `creator_snapshots` שומרת יחד את הפוסטים, תוצאות האימון וארבעת דוחות המחקר. השימוש ב־JSONB מאפשר לשמור את התוצרים כפי שנוצרו, בלי לאבד מידע ובלי להציג מודל ודוח מתמונות מצב שונות.

זו שכבת ארכיון וקריאה לדשבורד. היא אינה מחליפה את תיקיית `artifacts`, והסוכנים ממשיכים לעבוד על קבצים מקומיים. קובץ המודל הבינארי, נתוני המקור, יומני API ומפתחות אינם נשלחים לענן.

| עמודה | תפקיד |
|---|---|
| `id` | SHA-256 של התוכן; מונע כפילויות בסנכרון חוזר |
| `captured_at` | מועד קליטת תמונת המצב לפי שעון המסד |
| `row_count` | מספר הפוסטים, נבדק מול אורך המערך |
| `posts` | נתוני הפוסטים הנקיים, שבע עמודות לכל פוסט |
| `training` | סיכום האימון, אימות צולב ותוצאות הבדיקה |
| `reports` | דוחות התובנות, ההערכה, כרטיס המודל והביקורת |

הפונקציה `save_creator_snapshot` שומרת רשומה אחת בעסקה אחת. תוכן זהה אינו מוחלף ואינו מקבל תאריך חדש. הקריאה לדשבורד ממיינת לפי מועד הקליטה ומציגה את התמונה האחרונה.

## התקנה

1. בחרו ארגון וצרו פרויקט ייעודי בשם `creator-insights` ב־Supabase. עלויות תלויות בתוכנית הארגון.
2. ב־SQL Editor של הפרויקט הפעילו פעם אחת את הקובץ `supabase/migrations/20261016062319_creator_insights_workspace.sql`.
3. הגדירו בקובץ `.env` המקומי:

```dotenv
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SECRET_KEY=YOUR_SERVER_SECRET_KEY
```

אפשר להגדיר אותם שמות גם ב־`.streamlit/secrets.toml` עבור הממשק. קובץ זה מוחרג מ־Git. ב־CLI יש להשתמש ב־`.env` או במשתני סביבה. מפתח `service_role` ישן נתמך בשם `SUPABASE_SERVICE_ROLE_KEY`. מפתח `publishable` אינו מתאים להרשאות הפרטיות של הסכמה הזו.

4. בדקו את החיבור בלי לכתוב נתונים:

```bash
python sync_supabase.py --check
```

5. סנכרנו את התוצרים:

```bash
python sync_supabase.py
```

אפשר לבצע את אותן פעולות מתוך **מערכת → Supabase**. הסנכרון בודק את טביעות המסירה ואת מדדי ההערכה מול התחזיות השמורות. ריצה אחרונה שלא הושלמה חוסמת סנכרון. אין להריץ את תהליך הסוכנים וסנכרון במקביל.

6. בחרו **Supabase** במקור הנתונים בתפריט הצד. כפתור **רענון נתונים** מביא שוב את תמונת המצב האחרונה. הבחירה בענן אינה עוברת בשקט לנתונים מקומיים אם החיבור נכשל.

## הרשאות

RLS מופעל על הטבלה. אין גישה ל־`anon`, ל־`authenticated` או ל־`PUBLIC`. רק שרת האפליקציה עם תפקיד `service_role` יכול לקרוא ולהוסיף רשומות ולהפעיל את פונקציית השמירה. הפונקציה היא `SECURITY INVOKER`, עם `search_path` ריק. מפתחות אינם מוצגים בממשק או בשגיאות החיבור.

היישום מיועד כרגע למפעיל מקומי יחיד וקשור ל־`127.0.0.1` כברירת מחדל. אין בו מערכת משתמשים. לפני פרסום לציבור יש להוסיף אימות והרשאות לממשק ולפעולות הניהול; RLS אינו תחליף להגנה על אפליקציה שמשתמשת במפתח שרת.

## בדיקה לאחר התקנה

```sql
select id, captured_at, row_count, jsonb_array_length(posts) as actual_rows
from public.creator_snapshots
order by captured_at desc;

select relrowsecurity
from pg_class
where oid = 'public.creator_snapshots'::regclass;

select has_table_privilege('anon', 'public.creator_snapshots', 'select') as anon_select,
       has_table_privilege('authenticated', 'public.creator_snapshots', 'insert') as user_insert;
```

אחרי סנכרון התוצרים הנוכחיים צפויים 499 פוסטים; RLS אמור להיות `true` ושתי בדיקות ההרשאה `false`. הריצו סנכרון נוסף וודאו שכמות תמונות המצב לא גדלה. לאחר מכן בדקו את מסך הענן ואת Security Advisors של Supabase. בדיקות אלו טרם בוצעו מול מסד חי בסשן הנוכחי.

## מקורות

- [Supabase API keys](https://supabase.com/docs/guides/getting-started/api-keys)
- [Securing the Data API](https://supabase.com/docs/guides/api/securing-your-api)
- [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Streamlit secrets](https://docs.streamlit.io/develop/concepts/connections/secrets-management)
