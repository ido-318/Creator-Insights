import * as webllm from 'https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm@0.2.79/+esm';

const MODEL = 'Qwen2.5-3B-Instruct-q4f16_1-MLC';
const REFUSAL = 'אני עונה רק על שאלות על הפרויקט Creator Insights: הנתונים, הצוותים, התוצאות, המגבלות, ההרצה והאבטחה. נסו לנסח שאלה בנושא.';
const ROUTER = 'אתה מסווג שאלות על פרויקט Creator Insights. קיבלת רשימה ממוספרת של שאלות מוכרות. החזר מספר אחד בלבד: מספר השאלה שמתאימה ביותר לשאלת המשתמש, או 1 אם אינך בטוח. אל תכתוב שום דבר מלבד המספר.';

const $ = id => document.getElementById(id);
const gateMsg = $('gate-msg'), prog = $('prog'), log = $('log');
let engine = null, kb = [], busy = false;

const norm = s => s.toLowerCase().replace(/[^֐-׿a-z0-9\s-]/g, ' ');
function candidates(q) {
  const n = norm(q);
  return kb.map((e, i) => ({ i, s: e.k.reduce((t, w) => t + (n.includes(w) ? w.length : 0), 0) }))
    .filter(x => x.s > 0).sort((a, b) => b.s - a.s).slice(0, 3).map(x => x.i);
}
function add(text, who) {
  const d = document.createElement('div');
  d.className = 'msg ' + who; d.textContent = text;
  log.appendChild(d); log.scrollTop = log.scrollHeight; return d;
}
function fail(t) { gateMsg.textContent = t; gateMsg.classList.add('err'); $('start').disabled = false; prog.hidden = true; }

$('start').addEventListener('click', async () => {
  $('start').disabled = true; gateMsg.classList.remove('err');
  if (!('gpu' in navigator)) return fail('הדפדפן הזה אינו תומך ב-WebGPU. אפשר לנסות Chrome או Edge עדכניים במחשב, או להשתמש בצ\'אט התשובות המוכנות באתר.');
  try {
    kb = await (await fetch('/kb.json')).json();
    prog.hidden = false; gateMsg.textContent = 'טוען את המודל…';
    engine = await webllm.CreateMLCEngine(MODEL, {
      initProgressCallback: r => { prog.value = Math.round((r.progress || 0) * 100); gateMsg.textContent = r.text; }
    });
    $('gate').hidden = true; $('chat').hidden = false;
    add('שלום! אפשר לשאול אותי על הנתונים, הצוותים, התוצאות, המגבלות, ההרצה או האבטחה של הפרויקט.', 'bot');
    $('input').focus();
  } catch (err) {
    console.error(err);
    fail('טעינת המודל נכשלה. בדקו את החיבור ונסו שוב, או השתמשו בצ\'אט התשובות המוכנות באתר.');
  }
});

$('form').addEventListener('submit', async e => {
  e.preventDefault();
  const q = $('input').value.trim();
  if (!q || busy) return;
  $('input').value = ''; add(q, 'me');
  busy = true; $('send').disabled = true;
  const out = add('…', 'bot');
  try {
    const cand = candidates(q);
    let pick = -1;
    if (cand.length === 1) pick = cand[0];
    else if (cand.length > 1) {
      const list = cand.map((idx, j) => (j + 1) + '. ' + kb[idx].q).join('\n');
      const res = await engine.chat.completions.create({
        temperature: 0, max_tokens: 4,
        messages: [
          { role: 'system', content: ROUTER },
          { role: 'user', content: 'רשימת השאלות:\n' + list + '\n\nשאלת המשתמש: ' + q + '\n\nהמספר:' }
        ]
      });
      const n = parseInt((res.choices[0]?.message?.content || '').replace(/\D/g, ''), 10);
      pick = n >= 1 && n <= cand.length ? cand[n - 1] : cand[0];
    }
    out.textContent = pick >= 0 ? kb[pick].a : REFUSAL;
  } catch (err) {
    console.error(err);
    out.textContent = 'אירעה שגיאה בהפעלת המודל. נסו שוב או רעננו את הדף.';
  } finally { busy = false; $('send').disabled = false; $('input').focus(); log.scrollTop = log.scrollHeight; }
});
