// Last sounding segment, including rests. Binary search also handles seeking backwards.
export function eventAt(events,time) {
  let lo=0,hi=events.length-1,result=-1;
  while(lo<=hi){const mid=(lo+hi)>>1;if(events[mid].time<=time){result=mid;lo=mid+1;}else hi=mid-1;}
  return result;
}
