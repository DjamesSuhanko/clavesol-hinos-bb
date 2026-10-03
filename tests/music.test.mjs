import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {eventAt} from '../assets/music-timing.mjs';
const {events,duration}=JSON.parse(readFileSync(new URL('./fixtures/timing.json',import.meta.url)));
assert.equal(events.length,172);assert.equal(duration,104);
assert.equal(eventAt(events,-1),-1);assert.equal(eventAt(events,0),0);
for(let i=0;i<events.length;i++){
 const e=events[i];assert.equal(eventAt(events,e.time),i);
 assert.ok(e.x>=0&&e.x<100&&e.y>=0&&e.y<100);
 if(i)assert.equal(eventAt(events,e.time-.001),i-1);
}
assert.equal(events[eventAt(events,8)].measure,2);
assert.equal(events[eventAt(events,96)].measure,13);
assert.equal(events[eventAt(events,32)].measure,5);
assert.equal(events[eventAt(events,0)].measure,1);
console.log('172 cursor positions, timing boundaries and backwards seeking: OK');
