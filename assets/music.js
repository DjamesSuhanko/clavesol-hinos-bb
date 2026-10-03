import {eventAt} from './music-timing.mjs';
import {SynthTransport,formatTime} from './music-synth.mjs';
const get=id=>document.getElementById(id);
const zoom=get('score-zoom'),sheets=[...document.querySelectorAll('.score-sheet')];
const audio=get('score-audio'),player=get('score-player'),cursor=get('score-cursor');
const status=get('playback-status'),followCursor=get('follow-cursor');
const toggle=get('play-toggle'),progress=get('playback-progress');
let timeline,transport,frame,lastIndex=-1,lastMeasure=-1;
const currentTime=()=>transport?transport.currentTime:audio?.currentTime||0;
const playing=()=>transport?transport.playing:audio&&!audio.paused&&!audio.ended;
zoom?.addEventListener('change',()=>{for(const sheet of sheets)sheet.style.width=`${zoom.value}%`;});
function draw(follow=false){
  const time=currentTime();
  if(transport){
    progress.value=1000*time/transport.duration;
    get('playback-time').textContent=`${formatTime(time)} / ${formatTime(transport.duration)}`;
    toggle.textContent=transport.playing?'Pausar':'Reproduzir';
  }
  if(!timeline||!cursor)return;
  const index=eventAt(timeline.events,time);
  cursor.hidden=index<0||time>=timeline.duration;
  if(index<0)return;
  const event=timeline.events[index],sheet=sheets[(event.page??1)-1];
  if(!sheet){cursor.hidden=true;return;}
  if(cursor.parentElement!==sheet)sheet.append(cursor);
  const viewport=sheet.closest('.score-viewport');
  cursor.style.left=`${event.x}%`;cursor.style.top=`${event.y-0.8}%`;
  cursor.style.width=`${Math.max(event.width,.4)}%`;cursor.style.height=`${event.height+1.6}%`;
  if(event.measure!==lastMeasure){get('current-measure').textContent=`Compasso ${event.measure}${Number(player.dataset.measures)?` de ${player.dataset.measures}`:''}`;lastMeasure=event.measure;}
  if(follow&&index!==lastIndex&&followCursor?.checked&&!cursor.hidden){
    const box=cursor.getBoundingClientRect(),view=viewport.getBoundingClientRect();
    if(box.left<view.left+20||box.right>view.right-20)viewport.scrollLeft+=box.left-view.left-viewport.clientWidth*.3;
    if(box.top<0||box.bottom>innerHeight-40)cursor.scrollIntoView({block:'center',inline:'nearest',behavior:'instant'});
  }
  lastIndex=index;
}
function animate(){cancelAnimationFrame(frame);draw(true);if(playing())frame=requestAnimationFrame(animate);}
function ended(){cancelAnimationFrame(frame);draw();if(cursor)cursor.hidden=true;status.textContent='Reprodução concluída';}
async function readJSON(url){const response=await fetch(url);if(!response.ok)throw new Error('Arquivo indisponível');return response.json();}
if(player){
  if(toggle)toggle.disabled=true;
  if(player.dataset.playback==='generated'){
    try{
      const sequence=await readJSON(player.dataset.sequence);
      transport=new SynthTransport(sequence,ended);
      toggle.disabled=false;
      toggle.addEventListener('click',async()=>{
        toggle.disabled=true;
        try{
          if(transport.playing){transport.pause();status.textContent='Pausado';}
          else{await transport.play();status.textContent='Reproduzindo';}
          animate();
        }catch{status.textContent='Não foi possível iniciar o som. Tente reproduzir novamente.';}
        finally{toggle.disabled=false;}
      });
      progress.addEventListener('input',()=>{transport.seek(Number(progress.value)*transport.duration/1000);draw();});
      get('mute-score').addEventListener('change',event=>transport.setMuted(event.target.checked));
      get('playback-speed').addEventListener('change',event=>{
        transport.setRate(Number(event.target.value));
        get('tempo-display').textContent=`Andamento: ${sequence.marking} × ${transport.rate.toLocaleString('pt-BR')}`;
      });
      status.textContent='Pronto para reproduzir';draw();
    }catch{status.textContent='Não foi possível carregar a partitura para reprodução. Recarregue a página.';}
  }else if(audio){
    audio.addEventListener('play',()=>{status.textContent='Reproduzindo';animate();});
    audio.addEventListener('pause',()=>{cancelAnimationFrame(frame);status.textContent=audio.ended?'Reprodução concluída':'Pausado';draw();});
    audio.addEventListener('ended',ended);
    audio.addEventListener('timeupdate',()=>draw());
    audio.addEventListener('seeked',()=>draw(!audio.paused));
    audio.addEventListener('error',()=>{status.textContent='Não foi possível carregar o áudio. Recarregue a página para tentar novamente.';});
    get('playback-speed').addEventListener('change',event=>{audio.playbackRate=Number(event.target.value);});
  }
  get('restart-score').addEventListener('click',()=>{
    if(transport){transport.pause();transport.seek(0);}
    else if(audio){audio.pause();audio.currentTime=0;}
    cancelAnimationFrame(frame);lastIndex=-1;draw();status.textContent='Pronto para reproduzir';
  });
  if(player.dataset.timing)try{
    timeline=await readJSON(player.dataset.timing);draw();
    if(audio)status.textContent='Pronto para reproduzir';
  }catch{if(transport||audio)status.textContent='Som disponível; não foi possível carregar o cursor. Recarregue a página.';}
}
