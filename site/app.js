
const nav=document.getElementById('nav');
const onScroll=()=>nav.classList.toggle('scrolled',scrollY>30);
onScroll();addEventListener('scroll',onScroll,{passive:true});
const mb=document.getElementById('menu-btn');if(mb)mb.addEventListener('click',()=>nav.classList.toggle('open'));
document.querySelectorAll('.links a').forEach(a=>a.addEventListener('click',()=>nav.classList.remove('open')));

const count=el=>{
  const to=+el.dataset.n,t0=performance.now(),d=1600;
  const f=t=>{const p=Math.min((t-t0)/d,1);el.textContent=Math.round(to*(1-Math.pow(1-p,3)));if(p<1)requestAnimationFrame(f)};
  requestAnimationFrame(f);
};
const io=new IntersectionObserver(es=>es.forEach(e=>{
  if(!e.isIntersecting)return;
  e.target.classList.add('in');
  e.target.querySelectorAll('[data-n]').forEach(count);
  io.unobserve(e.target);
}),{threshold:.18});
document.querySelectorAll('.rv').forEach(el=>io.observe(el));

/* chatbot: תשובות מוכנות בצד הלקוח, בלי רשת ובלי איסוף מידע */
(()=>{
const GH='https://github.com/ido-318/Creator-Insights';
const KB=[
{q:'מה זה הפרויקט?',k:['פרויקט','מה זה','מהו','על מה','מטרה','creator','insights'],a:'Creator Insights הוא פרויקט לימודי לניתוח ביצועי תוכן, להשוואת מודלים ולהערכה כנה של מגבלות החיזוי. הוא בנוי משני צוותי CrewAI, מחוזה נתונים שנבדק בקוד ומדשבורד בעברית.'},
{q:'איזה נתונים משמשים?',k:['נתונים','דאטה','דאטא','מאגר','פוסטים','מקור','uci','פייסבוק','facebook','שורות'],a:'הנתונים הם 500 פוסטים היסטוריים מעמוד Facebook של מותג קוסמטיקה (UCI Facebook Metrics). אחרי הסרת שורה אחת עם ערך Paid חסר נשארות 499 שורות ושבע עמודות. קובץ המקור אינו כלול במאגר, וצריך להוריד אותו בנפרד.'},
{q:'איך הצוותים עובדים?',k:['צוות','צוותים','סוכנ','crew','crewai','אנליסט','מדען','מדעני'],a:'יש שני צוותים, ובכל אחד שלושה סוכנים. צוות האנליסטים מנקה נתונים, יוצר גרפים ודוח תובנות ומפרסם את חוזה הנתונים. צוות מדעני הנתונים משווה קו בסיס ושתי גרסאות CatBoost ומאמת את המדדים. החישובים עצמם רצים בקוד Python, והסוכנים משתמשים בכלים ומסבירים את התוצאות.'},
{q:'מה התוצאות של המודל?',k:['תוצאות','תוצאה','מודל','מודלים','catboost','mae','דיוק','שגיאה','בסיס','ניצח','חיזוי','תחזית'],a:'בבדיקה על 100 פוסטים, ה-MAE של CatBoost עומק 4 היה כ-125.5 ושל קו הבסיס (חציון קבוע) כ-120.5, כלומר קו הבסיס ניצח. באימות הצולב CatBoost היה טוב מעט יותר (146.6 מול 152.4). הפרויקט אומר זאת במפורש: הצלחת התהליך אינה מעידה על איכות תחזית מספקת לשימוש עסקי.'},
{q:'מה המגבלות?',k:['מגבל','חולש','בעיה','בעיות','ביקורת','כנות','אמין','מוגבל'],a:'המאגר קטן ומגיע מעמוד יחיד, עם שבעה סרטונים בלבד. הפיצול אקראי ולכן לא בודק חיזוי של תקופות עתידיות. קבוצת הבדיקה נצפתה בזמן הפיתוח, לא נבדקה הכללה לאינסטגרם או לחשבונות אחרים, ולא בוצעה בדיקת כפילויות. טביעות האצבע מזהות שינוי אבל אינן חתימה דיגיטלית.'},
{q:'מה זה חוזה נתונים?',k:['חוזה','שלמות','מסירה','sha','טביע','manifest','מניפסט','בדיקת מעבר','בדיקות מעבר'],a:'קובץ החוזה מגדיר עמודות, סוגים, ערכים מותרים ויחידות, והצד המקבל בודק התאמה לגרסה הנתמכת. בנוסף נשמרות טביעות SHA-256 של הנתונים הנקיים והחוזה, וכל שינוי בהם אחרי הפרסום נחסם. רק אם בדיקת המעבר עוברת מופעל צוות המידול.'},
{q:'מה יש בדשבורד?',k:['דשבורד','ממשק','streamlit','תצוגה','תצוגות','סינון','גרף','גרפים','csv','כהה','צבעים'],a:'דשבורד Streamlit בעברית ובאנגלית, עם ניווט בין חמש תצוגות ועיצוב כהה. בדף הבית יש בדיקה מהירה: בוחרים סוג תוכן, שעה וקידום ורואים איך פוסטים דומים הצליחו בעבר. אפשר לסנן לפי סוג פוסט, חודש פרסום וקידום, להוריד CSV מסונן ולבחור דוחות להורדה.'},
{q:'איך מחברים חשבון?',k:['חיבור', 'לחבר', 'להתחבר', 'חשבון', 'אינסטגרם', 'instagram', 'טיקטוק', 'tiktok', 'oauth', 'סרטון', 'סרטונים'],a:'במסך "חיבור חשבון" בוחרים Instagram או TikTok, מאשרים גישה בפלטפורמה, בוחרים סרטון והאפליקציה מנתחת אותו: אינטראקציות, דירוג מול הסרטונים האחרונים בחשבון והשוואה לנתוני המחקר. החיבור הוא OAuth בצד השרת, הטוקן נשמר רק בזמן הביקור ואין פרסום בשמכם.'},
{q:'איך מריצים?',k:['להריץ','הרצה','מריצים','התקנה','להתקין','install','pip','python','פייתון','הפעל','להפעיל'],a:'צריך Python 3.13. יוצרים סביבה וירטואלית, מתקינים את requirements.txt, מניחים את dataset_Facebook.csv בתיקיית data, ומריצים `python -m streamlit run app.py`. ההוראות המלאות נמצאות ב-README במאגר.',link:true},
{q:'צריך מפתח API?',k:['api','מפתח','claude','anthropic','עלות','עולה','כסף','יתרה','תשלום'],a:'פתיחת הדשבורד אינה מפעילה קריאות API. הפעלת הסוכנים דורשת מפתח Anthropic ויתרה, והקריאות למודל מחויבות לפי שימוש. אפשר גם להריץ את פעולות הנתונים והמידול מקומית בלי קריאות למודל שפה.'},
{q:'מה עם Supabase?',k:['supabase','סופאבייס','ענן','cloud','סנכרון'],a:'Supabase היא הרחבה אופציונלית לשמירת תמונות מצב של הנתונים, המדדים והדוחות. הקוד והמיגרציה מוכנים, אבל הפרויקט בענן טרם הוקם והחיבור החי לא נבדק. כל הדשבורד עובד גם במצב מקומי.'},
{q:'איך זה מאובטח?',k:['אבטח','אבטחה','בטוח','פרטיות','עוגי','cookie','קוד גישה','סיסמה','מידע אישי'],a:'הדשבורד דורש קוד גישה, רץ רק על המחשב המקומי והריצה נחסמת אם הכתובת אינה loopback. האתר הזה אינו משתמש בעוגיות, לא אוסף מידע אישי ואינו טוען משאבים משירותי צד שלישי. גם הצ\'אט הזה עובד כולו בדפדפן שלכם ולא שולח את השאלות לשום מקום.'},
{q:'אילו בדיקות יש?',k:['בדיק','test','בדיקות','טסט','תקינות','unittest'],a:'יש בדיקות לאימות נתונים, לחוזה, לשלמות המסירה, לכשל ב-Flow, להערכת המודלים, לדשבורד ולאבטחה. 27 בדיקות ממשק ואבטחה עברו לצד הבדיקות הקיימות. הבדיקות אינן דורשות קריאות לקלוד.'},
{q:'באילו טכנולוגיות?',k:['טכנולוג','כלים','ספרי','מה משתמש','נבנה','python','pandas','scikit','altair'],a:'Python, CrewAI, Anthropic Claude, Pandas, Scikit-learn, CatBoost, Matplotlib, Altair, Streamlit, Supabase (אופציונלי), Obsidian ו-Git.'},
{q:'איפה הקוד?',k:['קוד','גיטהאב','github','מאגר','repo','קישור','לינק','git'],a:'הקוד, התיעוד והבדיקות פתוחים במאגר ב-GitHub.',link:true}
];
const GREET=['שלום','היי','הי','אהלן','hello','hi'];
const norm=s=>s.toLowerCase().replace(/[^֐-׿a-z0-9\s-]/g,' ');
const $=id=>document.getElementById(id);
const open=$('cb-open'),box=$('cb'),log=$('cb-log'),chips=$('cb-chips'),form=$('cb-form'),input=$('cb-input');
if(!open||!box)return;
function add(text,who,link){
  const d=document.createElement('div');d.className='cb-msg '+who;
  d.textContent=text;
  if(link){d.appendChild(document.createTextNode(' '));const a=document.createElement('a');a.href=GH;a.target='_blank';a.rel='noopener noreferrer';a.textContent='למאגר ב-GitHub';d.appendChild(a)}
  log.appendChild(d);log.scrollTop=log.scrollHeight;
}
function answer(t){
  const n=norm(t);let best=null,score=0;
  for(const e of KB){let s=0;for(const w of e.k)if(n.includes(w))s+=w.length>3?2:1;if(s>score){score=s;best=e}}
  if(best&&score>0)return add(best.a,'bot',best.link);
  if(GREET.some(g=>n.trim()===g))return add('שלום! אפשר לשאול על הנתונים, הצוותים, התוצאות, המגבלות, ההרצה או האבטחה.','bot');
  add('לא מצאתי תשובה לזה. אפשר לנסות את אחת השאלות למטה, או לעיין ב-README במאגר.','bot',true);
}
function ask(t){t=t.trim();if(!t)return;add(t,'me');answer(t)}
const ai=document.createElement('a');ai.href='/ask';ai.textContent='מודל שפה מקומי (ניסיוני)';ai.style.cssText='flex:none;white-space:nowrap;font-size:13px;padding:6px 14px;border-radius:100px;background:var(--navy);color:#fff';chips.appendChild(ai);
KB.slice(0,8).forEach(e=>{const b=document.createElement('button');b.type='button';b.textContent=e.q;b.addEventListener('click',()=>ask(e.q));chips.appendChild(b)});
let started=false;
function toggle(show){
  box.hidden=!show;open.setAttribute('aria-expanded',String(show));
  if(show){if(!started){started=true;add('שלום! אני עונה על שאלות על הפרויקט. בחרו שאלה או כתבו משלכם.','bot')}input.focus()}else open.focus();
}
open.addEventListener('click',()=>toggle(box.hidden));
$('cb-close').addEventListener('click',()=>toggle(false));
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!box.hidden)toggle(false)});
form.addEventListener('submit',e=>{e.preventDefault();ask(input.value);input.value=''});
})();
