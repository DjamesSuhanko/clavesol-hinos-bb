import assert from 'node:assert/strict';
import {normalize,matches} from '../assets/list-search.mjs';
assert.equal(normalize('001 — Ó, Cristão!'),'1 o cristao');
const text='1 Hino 001 — Ó, Cristão!';
for(const query of ['','1','001','cristao','Ó cristão','Hino 001','   '])assert(matches(text,query),query);
for(const query of ['10','101','inexistente','hino 002'])assert(!matches(text,query),query);
assert(!matches('Hino 110 — Louvor','10'));
console.log('Busca: acentos, números exatos, zeros e múltiplas palavras validados.');
