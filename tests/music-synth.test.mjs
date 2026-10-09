import assert from 'node:assert/strict';
import {SynthTransport,formatTime} from '../assets/music-synth.mjs';
let voices=[];
const gain=()=>({gain:{value:1,setValueAtTime(){},exponentialRampToValueAtTime(){},setTargetAtTime(v){this.value=v;}},connect(){},disconnect(){}});
globalThis.AudioContext=class{
  constructor(){this.currentTime=0;this.state='suspended';}
  async resume(){this.state='running';}
  createGain(){return gain();}
  createOscillator(){const node={frequency:{value:0},connect(){},disconnect(){},start(t){this.startTime=t;},stop(t){this.stopTime=t;},addEventListener(){}};voices.push(node);return node;}
};
let ended=0;
const player=new SynthTransport({duration:4,notes:[{time:0,duration:2,midi:69},{time:3,duration:1,midi:72}]},()=>ended++);
await Promise.all([player.play(),player.play()]);
assert.equal(voices.length,1);assert.equal(voices[0].frequency.value,440);
player.context.currentTime=.5;assert.equal(player.currentTime,.5);
player.setMuted(true);assert.equal(player.master.gain.value,0);
player.context.currentTime=1;assert.equal(player.currentTime,1);
player.setRate(.5);assert.equal(player.currentTime,1);
assert.equal(voices.at(-1).frequency.value,440);
player.context.currentTime=2;assert.equal(player.currentTime,1.5);
player.pause();player.context.currentTime=3;assert.equal(player.currentTime,1.5);
player.seek(3);await player.play();assert.equal(voices.at(-1).frequency.value,440*2**(3/12));
player.seek(4);assert.equal(ended,1);assert.equal(player.playing,false);
await player.play();assert.equal(player.currentTime,0);
player.restart();assert.equal(player.currentTime,0);
player.pause();assert.equal(formatTime(104),'1:44');
console.log('Synth: pitch, clock, mute, tempo, pause, seek, ending, replay and concurrent play: OK');

player.setRate(1);player.setEnd(1);voices=[];await player.play();
assert.equal(player.duration,1);assert.equal(voices.length,1);
assert(Math.abs(voices[0].stopTime-player.context.currentTime-1.02)<1e-6);
player.context.currentTime+=1;player.schedule(false);assert.equal(player.playing,false);
player.setEnd(4);assert.equal(player.currentTime,0);assert.equal(player.duration,4);
console.log('Introduction transport clips sounding notes and restores full duration: OK');
