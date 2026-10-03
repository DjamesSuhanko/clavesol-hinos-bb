import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {eventAt} from '../assets/music-timing.mjs';
import {formatTime} from '../assets/music-synth.mjs';

const source=readFileSync(new URL('../assets/music.js',import.meta.url),'utf8')
  .replace("import {SynthTransport,formatTime} from './music-synth.mjs';",'')
  .replace("import {eventAt} from './music-timing.mjs';",'');
function element() {
  return {handlers:{},style:{},hidden:false,dataset:{},textContent:'',checked:true,
    addEventListener(name,fn){this.handlers[name]=fn;},
    append(child){child.parentElement=this;},
    getBoundingClientRect(){return {left:40,right:60,top:50,bottom:80};},
    scrollIntoView(){this.scrolled=true;}};
}
async function player({audio=true,timing=true,pages=2,generated=false,fail=false}={}) {
  const ids={};
  for(const id of ['score-player','play-toggle','playback-progress','playback-time','mute-score','tempo-display','score-zoom','score-audio','score-cursor','playback-status','follow-cursor','current-measure','restart-score','playback-speed'])ids[id]=element();
  let fetches=0;
  if(!generated)ids['play-toggle']=null;
  if(!audio&&!generated)ids['score-player']=null;
  else ids['score-player'].dataset={playback:generated?'generated':'recorded',sequence:'/sequence.json',...(timing?{timing:'/timing.json',measures:'2'}:{})};
  const viewport={scrollLeft:0,clientWidth:800,getBoundingClientRect:()=>({left:0,right:800})};
  const sheets=Array.from({length:pages},()=>Object.assign(element(),{closest:()=>viewport}));
  if(!pages)ids['score-zoom']=null;
  if(!timing)ids['score-cursor']=ids['follow-cursor']=ids['current-measure']=null;
  if(!audio)ids['score-audio']=null;
  else Object.assign(ids['score-audio'],{currentTime:0,paused:true,ended:false,
    dataset:timing?{timing:'/timing.json',measures:'2'}:{},pause(){this.paused=true;}});
  const events=[{time:0,page:1,measure:1,x:10,y:10,width:3,height:5},
                {time:5,page:2,measure:2,x:20,y:20,width:3,height:5},
                {time:8,page:1,measure:1,x:10,y:10,width:3,height:5}];
  await runInNewContext(`(async()=>{${source}})()`,{
    document:{getElementById:id=>ids[id],querySelectorAll:()=>sheets},eventAt,formatTime,SynthTransport:FakeSynth,
    fetch:async()=>{fetches++;return {ok:!fail,json:async()=>({duration:10,events,marking:'♩ = 60',notes:[]})};},
    requestAnimationFrame:()=>1,cancelAnimationFrame(){},innerHeight:900,
  });
  return {ids,sheets,fetches};
}
class FakeSynth {
  constructor(sequence,onEnded){this.duration=sequence.duration;this.currentTime=0;this.playing=false;this.onEnded=onEnded;}
  async play(){this.playing=true;}
  pause(){this.playing=false;}
  seek(time){this.currentTime=time;}
  setRate(rate){this.rate=rate;}
  setMuted(muted){this.muted=muted;}
}
const {ids,sheets}=await player();
const audio=ids['score-audio'],cursor=ids['score-cursor'];
assert.equal(cursor.parentElement,sheets[0]);
audio.currentTime=5;audio.handlers.seeked();assert.equal(cursor.parentElement,sheets[1]);
assert.equal(ids['current-measure'].textContent,'Compasso 2 de 2');
audio.currentTime=8;audio.handlers.seeked();assert.equal(cursor.parentElement,sheets[0]);
audio.currentTime=1;audio.handlers.seeked();assert.equal(ids['current-measure'].textContent,'Compasso 1 de 2');
ids['score-zoom'].value='200';ids['score-zoom'].handlers.change();
assert.ok(sheets.every(s=>s.style.width==='200%'));
audio.currentTime=10;audio.handlers.timeupdate();assert.equal(cursor.hidden,true);
ids['restart-score'].handlers.click();assert.equal(audio.currentTime,0);assert.equal(cursor.hidden,false);
ids['playback-speed'].handlers.change({target:{value:'0.75'}});assert.equal(audio.playbackRate,.75);
const silent=await player({audio:false,timing:false});assert.equal(silent.fetches,0);
silent.ids['score-zoom'].value='150';silent.ids['score-zoom'].handlers.change();
assert.equal(silent.sheets[1].style.width,'150%');
const simple=await player({audio:true,timing:false,pages:0});assert.equal(simple.fetches,0);
simple.ids['score-audio'].handlers.ended();assert.equal(simple.ids['playback-status'].textContent,'Reprodução concluída');
console.log('Player: page transitions, repeat/backseek, zoom, speed, restart and optional audio/cursor: OK');

const generated=await player({generated:true,audio:false});
const g=generated.ids;
assert.equal(g['play-toggle'].disabled,false);
assert.equal(g['playback-time'].textContent,'0:00 / 0:10');
await g['play-toggle'].handlers.click();assert.equal(g['play-toggle'].textContent,'Pausar');
g['playback-progress'].value='500';g['playback-progress'].handlers.input();
assert.equal(g['score-cursor'].parentElement,generated.sheets[1]);
g['mute-score'].handlers.change({target:{checked:true}});
g['playback-speed'].handlers.change({target:{value:'0.5'}});
assert.equal(g['tempo-display'].textContent,'Andamento: ♩ = 60 × 0,5');
await g['play-toggle'].handlers.click();assert.equal(g['play-toggle'].textContent,'Reproduzir');
g['restart-score'].handlers.click();assert.equal(g['playback-time'].textContent,'0:00 / 0:10');
const failed=await player({generated:true,audio:false,timing:false,fail:true});
assert.equal(failed.ids['play-toggle'].disabled,true);
assert.match(failed.ids['playback-status'].textContent,/Não foi possível/);
console.log('Generated player: playback, seeking, tempo, mute, restart and loading failure: OK');
