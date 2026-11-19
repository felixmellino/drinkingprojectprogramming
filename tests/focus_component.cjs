const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const cfg=JSON.parse(execFileSync(process.env.SCORING_PYTHON||'.venv/Scripts/python.exe',['-c','import json;from core.focus_challenge import new_focus_rules;print(json.dumps(new_focus_rules()))'],{encoding:'utf8'}));
const html=fs.readFileSync('components/focus_challenge/index.html','utf8');
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
const attempt=(phase,extra={})=>({id:'attempt',revision:1,status:'running',phase,step:0,config:cfg,
 server_now:iso(0),signal_at:iso(1500),deadline:iso(3500),expires_at:iso(180000),reaction_ms:[],...extra});

// Only the reaction tries remain: three tries, no countdown clock, no Memory/Precision.
assert.equal(cfg.reaction_trials,3,'New seasons play three reaction tries');
assert(!html.includes('role="timer"')&&!html.includes('id="timer"'),'The countdown clock is gone');
assert(!/memory|precision/i.test(html.replace(/older version \(memory\/precision\)/,'')),'Memory and Precision are gone from the board');

// A false start (tap before the signal) is a red screen and ends the attempt.
const early=setup();early.render(attempt('reaction'));early.pressReaction();
assert.equal(early.last().action,'fail');assert.equal(early.elements.falsestart.hidden,false,'Early tap: red false-start screen');
assert(html.includes('FALSE START')&&html.includes('#D92D20'));
const reopened=setup(early.cache);reopened.render(attempt('reaction',{status:'failed',reason:'miss'}));
assert.equal(reopened.elements.falsestart.hidden,false,'Reopening a false-started attempt still shows the red screen');
assert.equal(reopened.elements.resultText.textContent,'');

// A normal tap records the time and shows it for a moment, then the next try waits.
const reaction=setup();reaction.render(attempt('reaction'));reaction.advance(1500);
assert.equal(reaction.elements.react.textContent,'TAP NOW');reaction.advance(250);reaction.pressReaction();
assert.equal(reaction.last().payload.elapsed_ms,250);
assert.equal(reaction.elements.falsestart.hidden,true,'A normal tap is no false start');
assert.equal(reaction.elements.flash.hidden,false);assert.equal(reaction.elements.flashTime.textContent,'250 ms');
assert.equal(reaction.elements.flashTry.textContent,'Try 1 of 3');
reaction.advance(1500);assert.equal(reaction.elements.flash.hidden,true,'The time stays a moment, then the next try waits');
const before=JSON.stringify(reaction.last());reaction.render(attempt('reaction',{server_now:iso(1750)}));
assert.equal(JSON.stringify(reaction.last()),before,'Rerenders retain pending evidence');
const resumed=setup(reaction.cache);resumed.render(attempt('reaction',{server_now:iso(1900)}));
assert.equal(resumed.last().payload.elapsed_ms,250,'Reload retries the same saved event, not a new trial');
const waiting=setup();waiting.render(attempt('reaction'));waiting.advance(1000);
waiting.render(attempt('reaction',{server_now:iso(1000)}));waiting.advance(600);
assert.equal(waiting.elements.react.textContent,'TAP NOW','Polling never resets the signal countdown');

// No second start button: the first try begins at once.
const ready=setup();ready.render(attempt('reaction_ready'));
assert.equal(ready.last().action,'ready');assert.equal(ready.elements.ready.hidden,false);

// Too late for the response window ends the attempt.
const slowTap=setup();slowTap.render(attempt('reaction',{signal_at:iso(100),deadline:iso(2100)}));
slowTap.advance(100+cfg.reaction_response_ms+1);assert.equal(slowTap.last().action,'fail');

// Result screens: every try plus the average; reason texts are short.
const slow=setup();slow.render(attempt('reaction',{status:'failed',reason:'reaction_slow',reaction_ms:[310,420,380]}));
assert.equal(slow.elements.overview.textContent,'Try 1   310 ms\nTry 2   420 ms\nTry 3   380 ms\nAverage   370 ms','Mini overview with average');
assert(slow.elements.resultText.textContent.startsWith('Too slow'));assert.equal(slow.elements.falsestart.hidden,true);
const won=setup();won.render(attempt('reaction',{status:'passed',reaction_ms:[200,240,220],boost_ends_at:iso(3600000)}));
assert.equal(won.elements.resultTitle.textContent,'×1.5 earned');
assert.equal(won.elements.overview.textContent,'Try 1   200 ms\nTry 2   240 ms\nTry 3   220 ms\nAverage   220 ms');
assert.equal(won.last(),undefined,'Rendering a win never requests another reward');
const qaWin=setup();qaWin.render(attempt('reaction',{status:'passed',test_mode:true,reaction_ms:[200]}));
assert(qaWin.elements.resultText.textContent.includes('play again'));
const timedOut=setup();timedOut.render(attempt('reaction',{status:'failed',reason:'timeout'}));
assert.equal(timedOut.elements.resultText.textContent,'Time ran out.');

// An attempt left over from the old three-stage game ends instead of hanging.
const legacy=setup();legacy.render(attempt('memory'));
assert.equal(legacy.last().action,'fail');assert(legacy.elements.resultText.textContent.includes('older version'));

console.log('Focus component checks passed: no clock, time after every try, false start screen, auto-start, summary and average, stable rerender/reload, old attempts end.');
