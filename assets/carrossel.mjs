// Rotação automática a cada 5 segundos, com navegação manual.
export function mountCarousel(root){
  const slides=[...root.querySelector('.carousel-slides').children];
  const controls=root.querySelector('.carousel-controls');
  if(slides.length<2||!controls)return;
  let index=0, timer, hovered=false, paused=false;
  const count=root.querySelector('[data-count]');
  const toggle=document.createElement('button');
  toggle.type='button';toggle.textContent='Pausar';
  toggle.setAttribute('aria-label','Pausar troca automática');
  controls.append(toggle);
  function show(next){index=(next+slides.length)%slides.length;slides.forEach((slide,i)=>{slide.hidden=i!==index;});count.textContent=`${index+1} de ${slides.length}`;}
  function schedule(){
    clearTimeout(timer);
    const active=!paused&&!hovered&&!document.hidden&&!root.contains(document.activeElement);
    count.setAttribute('aria-live',active?'off':'polite');
    if(active)timer=setTimeout(()=>{show(index+1);schedule();},5000);
  }
  function move(step){show(index+step);schedule();}
  root.querySelector('[data-prev]').addEventListener('click',()=>move(-1));
  root.querySelector('[data-next]').addEventListener('click',()=>move(1));
  toggle.addEventListener('click',()=>{
    paused=!paused;toggle.textContent=paused?'Retomar':'Pausar';
    toggle.setAttribute('aria-label',paused?'Retomar troca automática':'Pausar troca automática');
    schedule();
  });
  root.addEventListener('keydown',event=>{if(event.key==='ArrowLeft'||event.key==='ArrowRight'){event.preventDefault();move(event.key==='ArrowRight'?1:-1);}});
  root.addEventListener('mouseenter',()=>{hovered=true;schedule();});
  root.addEventListener('mouseleave',()=>{hovered=false;schedule();});
  root.addEventListener('focusin',schedule);
  root.addEventListener('focusout',()=>queueMicrotask(schedule));
  document.addEventListener('visibilitychange',schedule);
  controls.hidden=false;show(0);schedule();
}
if(typeof document!=='undefined')document.querySelectorAll('.collection-carousel').forEach(mountCarousel);
