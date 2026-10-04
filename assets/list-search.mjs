export function normalize(value){return String(value).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/(\d+)/g,n=>String(Number(n))).replace(/[^a-z0-9]+/g,' ').trim();}
export function matches(text,query){
 const words=normalize(text).split(' '),tokens=normalize(query).split(' ').filter(Boolean);
 return tokens.every(token=>/^\d+$/.test(token)?words.includes(token):words.some(word=>word.includes(token)));
}
if(typeof document!=='undefined'&&document.querySelector('[data-list-search]')){
 const input=document.getElementById('list-search-input'),cards=[...document.querySelectorAll('main .card, main .score-card')];
 const indexed=cards.map(card=>({card,text:card.dataset.search??card.textContent}));
 function filter(){
  let count=0;
  for(const {card,text} of indexed){card.hidden=!matches(text,input.value);if(!card.hidden)count++;}
  for(const section of document.querySelectorAll('.gem-region'))section.hidden=![...section.querySelectorAll('.card')].some(card=>!card.hidden);
  document.getElementById('list-search-count').textContent=`${count} de ${cards.length} resultados`;
  document.getElementById('list-search-empty').hidden=count>0;
  document.getElementById('list-search-clear').disabled=!input.value;
 }
 input.addEventListener('input',filter);
 document.getElementById('list-search-clear').addEventListener('click',()=>{input.value='';filter();input.focus();});
 document.querySelector('[data-list-search]').hidden=false;filter();
}
