export function formatTime(value){
  const seconds=Math.max(0,Math.floor(value||0));
  return `${Math.floor(seconds/60)}:${String(seconds%60).padStart(2,'0')}`;
}

export class SynthTransport{
  constructor(sequence,onEnded=()=>{}){
    this.sequence=sequence;this.onEnded=onEnded;this.rate=1;this.position=0;
    this.context=null;this.master=null;this.startedAt=0;this.origin=0;this.timer=0;
    this.scheduledUntil=0;this.nodes=[];this.playing=false;this.muted=false;
  }
  get duration(){return this.end ?? this.sequence.duration;}
  setEnd(end){
    this.pause();
    this.end=Number.isFinite(end)&&end>0?Math.min(end,this.sequence.duration):this.sequence.duration;
    this.position=0;
  }
  get currentTime(){
    if(!this.playing||!this.context)return this.position;
    return Math.min(this.duration,this.origin+(this.context.currentTime-this.startedAt)*this.rate);
  }
  async ensureContext(){
    if(!this.context){
      const Audio=globalThis.AudioContext||globalThis.webkitAudioContext;
      if(!Audio)throw new Error('Seu navegador não oferece síntese de áudio.');
      this.context=new Audio();this.master=this.context.createGain();
      this.master.gain.value=this.muted?0:.7;this.master.connect(this.context.destination);
    }
    if(this.context.state==='suspended')await this.context.resume();
  }
  async play(){
    if(this.playing)return;
    await this.ensureContext();
    if(this.playing)return;
    if(this.position>=this.duration)this.position=0;
    this.start();
  }
  start(){
    this.playing=true;this.origin=this.position;this.startedAt=this.context.currentTime;
    this.scheduledUntil=this.position;this.schedule(true);
    if(this.playing)this.timer=setInterval(()=>this.schedule(false),80);
  }
  pause(){
    if(!this.playing)return;
    this.position=this.currentTime;this.playing=false;clearInterval(this.timer);this.stopNodes();
  }
  restart(){
    this.seek(0);
  }
  seek(position){
    const resume=this.playing;this.pause();this.position=Math.max(0,Math.min(this.duration,position));
    if(resume)this.start();
  }
  setRate(rate){
    const resume=this.playing;this.pause();this.rate=Math.max(.1,Math.min(4,Number(rate)||1));
    if(resume)this.start();
  }
  setMuted(muted){
    this.muted=muted;
    if(this.master)this.master.gain.setTargetAtTime(muted?0:.7,this.context.currentTime,.01);
  }
  stopNodes(){
    for(const node of this.nodes)try{node.stop();}catch{}
    this.nodes=[];
  }
  schedule(initial){
    if(!this.playing)return;
    const nowSource=this.currentTime;
    if(nowSource>=this.duration){
      this.position=this.duration;this.playing=false;clearInterval(this.timer);this.stopNodes();this.onEnded();return;
    }
    const horizon=Math.min(this.duration,nowSource+.4*this.rate);
    for(const note of this.sequence.notes){
      const end=Math.min(note.time+note.duration,this.duration);
      const overlaps=initial&&note.time<nowSource&&end>nowSource;
      if(!(overlaps||(note.time>=this.scheduledUntil&&note.time<horizon)))continue;
      const sourceStart=Math.max(note.time,nowSource);
      const when=this.context.currentTime+Math.max(0,(sourceStart-nowSource)/this.rate);
      const length=(end-sourceStart)/this.rate;
      if(length<=.01)continue;
      this.voice(note.midi,when,length);
    }
    this.scheduledUntil=horizon;
  }
  voice(midi,when,length){
    const oscillator=this.context.createOscillator(),gain=this.context.createGain();
    oscillator.type='triangle';oscillator.frequency.value=440*2**((midi-69)/12);
    const peak=.075;gain.gain.setValueAtTime(.0001,when);
    gain.gain.exponentialRampToValueAtTime(peak,when+Math.min(.025,length/3));
    gain.gain.setValueAtTime(peak,when+Math.max(Math.min(.025,length/3),length-.06));
    gain.gain.exponentialRampToValueAtTime(.0001,when+length);
    oscillator.connect(gain);gain.connect(this.master);oscillator.start(when);oscillator.stop(when+length+.02);
    this.nodes.push(oscillator);oscillator.addEventListener('ended',()=>{oscillator.disconnect();gain.disconnect();this.nodes=this.nodes.filter(node=>node!==oscillator);});
  }
}
