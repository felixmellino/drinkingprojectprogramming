// Reaction Duel tap board in a fake browser: false starts, guesses, times, missed tries, saved taps.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const cfg=JSON.parse(execFileSync(process.env.SCORING_PYTHON||'.venv/Scripts/python.exe',['-c','import json;from core.reaction_duel import CONFIG;print(json.dumps(CONFIG))'],{encoding:'utf8'}));
const html=fs.readFileSync('components/reaction_duel/index.html','utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const epoch=Date.parse('2026-11-19T20:00:00Z'),iso=ms=>new Date(epoch+ms).toISOString();
function setup(cache=new Map()){
 const elements={},messages=[],listeners={};
 let ms=0,tick;
 function el(){return {hidden:false,disabled:false,textContent:'',style:{},children:[],handlers:{},
  classList:{go:false,toggle(name,value){this[name]=value;}},setAttribute(){},
  appendChild(child){this.children.push(child);},addEventListener(name,handler){this.handlers[name]=handler;}};}
 const document={getElementById:id=>elements[id]??(elements[id]=el()),querySelectorAll:()=>[],createElement:el};
 const parent={postMessage:m=>messages.push(m)};
 const window={parent,innerHeight:844,addEventListener:(name,fn)=>listeners[name]=fn};
 vm.runInNewContext(code,{document,window,Date,performance:{now:()=>ms},
  localStorage:{getItem:k=>cache.get(k)??null,setItem:(k,v)=>cache.set(k,v)},setInterval:fn=>{tick=fn;}});
 return {elements,messages,cache,
  render:a=>listeners.message({source:parent,data:{type:'streamlit:render',args:{attempt:a,tokens:''}}}),
  advance:n=>{ms+=n;tick();},last:()=>messages.filter(m=>m.type==='streamlit:setComponentValue').at(-1)?.value,
  pressReaction:()=>elements.react.handlers.pointerdown({preventDefault(){}})};
}
const attempt=(phase,extra={})=>({id:'duel',revision:1,status:'running',phase,step:0,config:cfg,
 server_now:iso(0),signal_at:iso(1500),deadline:iso(3500),expires_at:iso(180000),reaction_ms:[],...extra});


// Before the signal: red screen, the try repeats; it can be tapped away.
const early=setup();early.render(attempt('reaction'));early.pressReaction();
assert.equal(early.last().action,'false_start');assert.equal(early.elements.falsestart.hidden,false);
early.elements.falsestart.handlers.pointerdown({preventDefault(){}});assert.equal(early.elements.falsestart.hidden,true);
// Faster than 100 ms after the signal is a guess: also a false start.
const guess=setup();guess.render(attempt('reaction'));guess.advance(1550);guess.pressReaction();
assert.equal(guess.last().action,'false_start','Under 100 ms counts as a false start');
// A normal tap: the time is shown a moment and sent once.
const tap=setup();tap.render(attempt('reaction'));tap.advance(1500);
assert.equal(tap.elements.react.textContent,'TAP NOW');tap.advance(240);tap.pressReaction();
assert.equal(tap.last().action,'reaction');assert.equal(tap.last().payload.elapsed_ms,240);
assert.equal(tap.elements.flashTime.textContent,'240 ms');assert.equal(tap.elements.flashTry.textContent,'Try 1 of 3');
const reload=setup(tap.cache);reload.render(attempt('reaction',{server_now:iso(1800)}));
assert.equal(reload.last().payload.elapsed_ms,240,'A reload resends the same saved tap');
// No tap within 2 s: the try is reported as missed.
const slow=setup();slow.render(attempt('reaction'));slow.advance(1500+cfg.reaction_response_ms+1);
assert.equal(slow.last().action,'fail');
// First try starts by itself; after three tries the board shows them and waits.
const ready=setup();ready.render(attempt('reaction_ready'));assert.equal(ready.last().action,'ready');
const done=setup();done.render(attempt('reaction',{status:'done',step:3,reaction_ms:[200,9999,400]}));
assert.equal(done.elements.overview.textContent,'Try 1   200 ms\nTry 2   missed\nTry 3   400 ms\nAverage   300 ms');
assert.equal(done.elements.resultText.textContent,'Waiting for the result…');assert.equal(done.last(),undefined);
console.log('Reaction Duel board checks passed: false start, guess, tap time, reload, miss, auto-start, done view.');
