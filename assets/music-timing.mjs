// Last sounding segment, including rests. Binary search also handles seeking backwards.
export function eventAt(events,time) {
  let lo=0,hi=events.length-1,result=-1;
  while(lo<=hi){const mid=(lo+hi)>>1;if(events[mid].time<=time){result=mid;lo=mid+1;}else hi=mid-1;}
  return result;
}

// A simple study interpretation: fermatas last 50% longer. Merge simultaneous
// and overlapping marks so multiple voices never multiply the prolongation.
export function fermataClock(fermatas=[]) {
  const spans=[];
  for(const {start,end} of [...fermatas].sort((a,b)=>a.start-b.start)){
    if(!Number.isFinite(start)||!Number.isFinite(end)||start<0||end<=start)continue;
    const previous=spans.at(-1);
    if(previous&&start<=previous.end)previous.end=Math.max(previous.end,end);
    else spans.push({start,end});
  }
  return time=>time+spans.reduce((extra,{start,end})=>extra+Math.max(0,Math.min(time,end)-start)*.5,0);
}
