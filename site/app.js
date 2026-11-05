
const nav=document.getElementById('nav');
const onScroll=()=>nav.classList.toggle('scrolled',scrollY>30);
onScroll();addEventListener('scroll',onScroll,{passive:true});
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
