const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const logic=require('../components/focus_challenge/logic.js');
const {execFileSync}=require('node:child_process');
const cfg=JSON.parse(execFileSync(process.env.SCORING_PYTHON||'.venv/Scripts/python.exe',['-c','import json;from core.focus_challenge import new_focus_rules;print(json.dumps(new_focus_rules()))'],{encoding:'utf8'}));
const code=fs.readFileSync('components/focus_challenge/index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const epoch=Date.parse('2026-11-19T20:00:00Z'),iso=ms=>new Date(epoch+ms).toISOString();
function setup(cache=new Map()){
 const elements={},messages=[],listeners={},bars=Array.from({length:3},()=>({classList:{toggle(){}}}));
 let ms=0,tick;
 function el(){return {hidden:false,disabled:false,textContent:'',style:{},children:[],handlers:{},
  classList:{flash:false,toggle(name,value){this[name]=value;}},setAttribute(){},
  appendChild(child){this.children.push(child);},addEventListener(name,handler){this.handlers[name]=handler;}};}
 const document={getElementById:id=>elements[id]??(elements[id]=el()),querySelectorAll:()=>bars,createElement:el};
 const parent={postMessage:m=>messages.push(m)};
 const window={parent,innerHeight:844,addEventListener:(name,fn)=>listeners[name]=fn};
 vm.runInNewContext(code,{document,window,FocusLogic:logic,Date,performance:{now:()=>ms},
  localStorage:{getItem:k=>cache.get(k)??null,setItem:(k,v)=>cache.set(k,v)},setInterval:fn=>{tick=fn;}});
 return {elements,messages,cache,
  render:a=>listeners.message({source:parent,data:{type:'streamlit:render',args:{attempt:a,tokens:''}}}),
  advance:n=>{ms+=n;tick();},last:()=>messages.filter(m=>m.type==='streamlit:setComponentValue').at(-1)?.value,
  pressReaction:()=>elements.react.handlers.pointerdown({preventDefault(){}})};
}
const attempt=(phase,extra={})=>({id:'attempt',revision:1,status:'running',phase,step:0,config:cfg,
 server_now:iso(0),signal_at:iso(1500),deadline:iso(3500),expires_at:iso(180000),reaction_ms:[],precision_taps:[],...extra});
const early=setup();early.render(attempt('reaction'));early.pressReaction();assert.equal(early.last().action,'fail');
const reaction=setup();reaction.render(attempt('reaction'));reaction.advance(1500);
assert.equal(reaction.elements.react.textContent,'TAP NOW');reaction.advance(250);reaction.pressReaction();
assert.equal(reaction.last().payload.elapsed_ms,250);
const before=JSON.stringify(reaction.last());reaction.render(attempt('reaction',{server_now:iso(1750)}));
assert.equal(JSON.stringify(reaction.last()),before,'Rerenders retain pending evidence');
const resumed=setup(reaction.cache);resumed.render(attempt('reaction',{server_now:iso(1900)}));
assert.equal(resumed.last().payload.elapsed_ms,250,'Reload retries the same saved event, not a new trial');
const waiting=setup();waiting.render(attempt('reaction'));waiting.advance(1000);
waiting.render(attempt('reaction',{server_now:iso(1000)}));waiting.advance(600);
assert.equal(waiting.elements.react.textContent,'TAP NOW','Polling never resets the signal countdown');
const memory=[0,2,4,6,8,1,3],span=cfg.memory_flash_ms+cfg.memory_gap_ms;
const mem=setup();mem.render(attempt('memory',{memory,signal_at:iso(7*span),deadline:iso(7*span+15000)}));
assert.equal(mem.elements.grid.children[0].classList.flash,true);
mem.advance(span);assert.equal(mem.elements.grid.children[2].classList.flash,true);
mem.advance(6*span);assert(mem.elements.grid.children.every(b=>!b.disabled));
mem.elements.grid.children[0].onclick();assert.equal(mem.last().action,'memory');assert.equal(mem.last().payload.cell,0);
assert.equal(logic.memoryFrame(attempt('memory',{memory,signal_at:iso(7*span)}),7*span),null);
const positions=Array.from({length:12},(_,i)=>({x:120+i*60,y:880-i*60}));
const precise=setup();precise.render(attempt('precision',{positions,signal_at:iso(0),deadline:iso(12000)}));
for(let i=0;i<12;i++){precise.advance(300);precise.elements.target.onclick({stopPropagation(){}});}
assert.equal(precise.last().payload.taps.length,12);assert.equal(precise.last().payload.taps[11],3600);
assert.equal(precise.elements.target.hidden,true);
const cached=setup(precise.cache);cached.render(attempt('precision',{positions,server_now:iso(4000),signal_at:iso(0),deadline:iso(12000)}));
assert.equal(cached.last().payload.taps.length,12,'Reload recovers the final precision checkpoint');
const miss=setup();miss.render(attempt('precision',{positions,signal_at:iso(0),deadline:iso(12000)}));
miss.elements.arena.onclick({target:miss.elements.arena});assert.equal(miss.last().action,'fail');
const timeout=setup();timeout.render(attempt('precision',{positions,signal_at:iso(0),deadline:iso(12000)}));
timeout.advance(12001);assert.equal(timeout.last().action,'fail');
const saved=setup();saved.render(attempt('precision',{status:'passed',boost_ends_at:iso(3600000)}));
assert.equal(saved.elements.resultTitle.textContent,'×1.5 earned');
assert.equal(saved.last(),undefined,'Rendering a win never requests another reward');
const qaFail=setup();qaFail.render(attempt('reaction',{status:'failed',reason:'timeout',test_mode:true}));
const qaWin=setup();qaWin.render(attempt('precision',{status:'passed',test_mode:true}));
assert(qaWin.elements.resultText.textContent.includes('play again'));
const normalFail=setup();normalFail.render(attempt('reaction',{status:'failed',reason:'timeout',test_mode:false}));
assert.equal(normalFail.elements.resultText.textContent,'Time ran out.');
assert.deepEqual(logic.mergeTaps([100,200],[100,201,300],cfg),[100,200]);

// --- Reaction rework: no clock, time after every try, summary + average, red false start ---
const html=fs.readFileSync('components/focus_challenge/index.html','utf8');
assert(!html.includes('id="timer"')&&!html.includes('role="timer"'),'The countdown clock is gone');
const run=setup();run.render(attempt('reaction',{config:{...cfg,reaction_trials:3}}));run.advance(1500+231);run.pressReaction();
assert.equal(run.last().payload.elapsed_ms,231);
assert.equal(run.elements.flash.hidden,false,'The time of every try is shown');
assert.equal(run.elements.flashTime.textContent,'231 ms');assert.equal(run.elements.flashTry.textContent,'Try 1 of 3');
assert.equal(run.elements.falsestart.hidden,true,'A normal tap is no false start');
run.advance(1500);assert.equal(run.elements.flash.hidden,true,'The time stays only a moment, then the next try waits');
const fs1=setup();fs1.render(attempt('reaction'));fs1.advance(400);fs1.pressReaction();
assert.equal(fs1.last().action,'fail');assert.equal(fs1.elements.falsestart.hidden,false,'Early tap: red false-start screen');
assert(html.includes('FALSE START')&&html.includes('#D92D20'));
const reopened=setup(fs1.cache);reopened.render(attempt('reaction',{status:'failed',reason:'miss'}));
assert.equal(reopened.elements.falsestart.hidden,false,'Reopening a false-started attempt still shows the red screen');
assert.equal(reopened.elements.resultText.textContent,'');
const slow=setup();slow.render(attempt('reaction',{status:'failed',reason:'reaction_slow',reaction_ms:[310,420,380],config:{...cfg,reaction_trials:3}}));
assert.equal(slow.elements.overview.textContent,'Try 1   310 ms\nTry 2   420 ms\nTry 3   380 ms\nAverage   370 ms','Mini overview with average');
assert.equal(slow.elements.falsestart.hidden,true);
const mid=setup();mid.render(attempt('memory',{reaction_ms:[200,240,220],memory:[0,2,4,6,8,1,3],signal_at:iso(5950),deadline:iso(21000)}));
assert.equal(mid.elements.strip.hidden,false);assert.equal(mid.elements.strip.textContent,'Reaction · 200 · 240 · 220 ms · average 220 ms');
assert.equal(cfg.reaction_trials,3,'New seasons play three reaction tries');
console.log('Focus component checks passed: reaction timing/early tap, stable rerender/reload, memory presentation, precision prefixes/misses/timeout, and saved results.');
