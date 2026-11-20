// The phone location component in a fake browser: no surprise prompts, the switch asks on a tap.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('components/phone_location/index.html','utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];

function setup({stored=null,permission='prompt',storageBlocked=false,geo='ok'}={}){
 const store=new Map(stored?[['wegopub-location',stored]]:[]),messages=[],listeners={},calls={get:0,watch:0,clear:0},elements={};
 const el=()=>({textContent:'',className:'',disabled:false,offsetHeight:64,attrs:{},handlers:{},
  classList:{add(){},contains(){return false;}},setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k];},
  addEventListener(name,fn){this.handlers[name]=fn;}});
 const bodyClasses=new Set();
 const document={getElementById:id=>elements[id]??(elements[id]=el()),body:{classList:{add:c=>bodyClasses.add(c)}}};
 const parent={postMessage:m=>messages.push(m)};
 const position={coords:{latitude:38.7,longitude:-9.1,accuracy:12},timestamp:Date.now()};
 const navigator={geolocation:{
   getCurrentPosition:(ok,err)=>{calls.get++;geo==='ok'?ok(position):err({code:geo==='denied'?1:3});},
   watchPosition:()=>{calls.watch++;return 7;},clearWatch:()=>{calls.clear++;}},
  permissions:permission==='none'?undefined:{query:async()=>({state:permission})}};
 const localStorage=storageBlocked?{getItem(){throw new Error('blocked');},setItem(){throw new Error('blocked');}}
  :{getItem:k=>store.get(k)??null,setItem:(k,v)=>store.set(k,v)};
 const window={parent,addEventListener:(name,fn)=>listeners[name]=fn};
 vm.runInNewContext(code,{document,window,navigator,localStorage,Date,Math,setInterval(){return 1;},clearInterval(){}});
 const values=()=>JSON.parse(JSON.stringify(messages.filter(m=>m.type==='streamlit:setComponentValue').map(m=>m.value)));
 return {elements,calls,store,values,bodyClasses,listeners,
  render:async(mode,extra={})=>{listeners.message({source:parent,data:{type:'streamlit:render',args:{mode,tokens:':root{}',...extra}}});await new Promise(r=>setTimeout(r,5));}};
}

(async()=>{
 // Follower: never chosen -> off, no browser location call at all.
 let f=setup();await f.render();
 assert.deepEqual(f.values(),[{error:'off'}]);assert.equal(f.calls.watch+f.calls.get,0,'No prompt when Location was never turned on');

 // Chosen "off" stays off.
 f=setup({stored:'off',permission:'granted'});await f.render();
 assert.deepEqual(f.values(),[{error:'off'}]);assert.equal(f.calls.watch,0);

 // Turned on but the browser forgot its answer (Safari asks per visit): probe; a quick fix means follow.
 f=setup({stored:'on',permission:'prompt'});await f.render();
 assert.equal(f.calls.get,1,'One quick probe');assert.equal(f.calls.watch,1,'The probe worked, so it follows');
 assert.equal(f.values().at(-1).accuracy_m,12);
 // Probe answered with no fix (the invisible frame cannot show the question): tell the player to tap the switch.
 f=setup({stored:'on',permission:'prompt',geo:'denied'});await f.render();
 assert.deepEqual(f.values(),[{error:'off'}]);assert.equal(f.calls.watch,0);
 f=setup({stored:'on',permission:'prompt',geo:'timeout'});await f.render();
 assert.deepEqual(f.values(),[{error:'off'}]);assert.equal(f.calls.watch,0);
 // Never turned on: not even a probe.
 f=setup({permission:'prompt'});await f.render();assert.equal(f.calls.get+f.calls.watch,0);

 // Turned on and allowed: follow silently. Blocked in the browser: say so.
 f=setup({stored:'on',permission:'granted'});await f.render();assert.equal(f.calls.watch,1);assert.deepEqual(f.values(),[]);
 f=setup({stored:'on',permission:'denied'});await f.render();assert.deepEqual(f.values(),[{error:'denied'}]);
 // Browsers that cannot report permissions state still follow once the player turned it on.
 f=setup({stored:'on',permission:'none'});await f.render();assert.equal(f.calls.watch,1);
 // A browser that blocks storage cannot remember the choice: old behaviour (follow) instead of a dead end.
 f=setup({storageBlocked:true,permission:'granted'});await f.render();assert.equal(f.calls.watch,1);

 // Switch: shows Off, asks only when tapped, then stores ON and reports the fix.
 f=setup({permission:'prompt'});await f.render('switch');
 assert.equal(f.elements.switch.attrs['aria-checked'],'false');assert.equal(f.calls.get,0,'Showing the switch asks nothing');
 f.elements.switch.handlers.click();
 assert.equal(f.calls.get,1,'The tap asks the browser');assert.equal(f.store.get('wegopub-location'),'on');
 assert.equal(f.elements.switch.attrs['aria-checked'],'true');
 assert(f.elements.status.textContent.includes('accurate to about 12 m'));
 const fix=f.values().at(-1);assert.equal(fix.lat,38.7);assert.equal(fix.accuracy_m,12);
 // Tap again: off, remembered, reported.
 f.elements.switch.handlers.click();
 assert.equal(f.store.get('wegopub-location'),'off');assert.deepEqual(f.values().at(-1),{error:'off'});
 assert.equal(f.calls.get,1,'Turning it off asks nothing');

 // Denied in the prompt: the switch falls back to off with a clear message.
 f=setup({permission:'prompt',geo:'denied'});await f.render('switch');f.elements.switch.handlers.click();
 assert.equal(f.store.get('wegopub-location'),'off');assert.equal(f.elements.switch.attrs['aria-checked'],'false');
 assert(f.elements.status.textContent.startsWith('Blocked'));assert.deepEqual(f.values().at(-1),{error:'denied'});
 // Already blocked in the browser settings: the switch says so before any tap.
 f=setup({stored:'on',permission:'denied'});await f.render('switch');
 assert.equal(f.elements.switch.attrs['aria-checked'],'false');assert(f.elements.status.textContent.startsWith('Blocked'));
 f.elements.switch.handlers.click();assert.equal(f.calls.get,1,'Tapping a blocked switch asks again');
 // No fix yet (timeout): stays on and tells the player what to do.
 f=setup({permission:'prompt',geo:'timeout'});await f.render('switch');f.elements.switch.handlers.click();
 assert.equal(f.elements.switch.attrs['aria-checked'],'true');assert.deepEqual(f.values().at(-1),{error:'timeout'});
 // Map pill (compact + follow): compact look, follows while on, tap-to-turn-on when the browser forgot its answer.
 f=setup({stored:'on',permission:'granted'});await f.render('switch',{compact:true,follow:true});
 assert(f.bodyClasses.has('compact'));assert.equal(f.elements.switch.attrs['aria-checked'],'true');assert.equal(f.calls.watch,1,'The Map switch follows while on');
 f=setup({stored:'on',permission:'prompt'});await f.render('switch',{compact:true,follow:true});
 assert.equal(f.calls.watch,1,'A quick probe works, so it follows');assert.equal(f.elements.switch.attrs['aria-checked'],'true');
 f=setup({stored:'on',permission:'prompt',geo:'timeout'});await f.render('switch',{compact:true,follow:true});
 assert.equal(f.calls.watch,0);assert.equal(f.elements.switch.attrs['aria-checked'],'false','Probe failed: the switch asks for a tap');
 assert(f.elements.status.textContent.startsWith('Tap to turn on'));assert.deepEqual(f.values().at(-1),{error:'off'});
 f=setup({permission:'prompt'});await f.render('switch',{compact:true,follow:true});
 assert.equal(f.calls.get+f.calls.watch,0,'Never turned on: asks nothing');assert.deepEqual(f.values(),[{error:'off'}]);
 f.elements.switch.handlers.click();   // tap: asks, then follows
 assert.equal(f.store.get('wegopub-location'),'on');assert.equal(f.calls.watch,1);
 f.elements.switch.handlers.click();   // tap again: stops following
 assert.equal(f.store.get('wegopub-location'),'off');assert.equal(f.calls.clear,1);assert.deepEqual(f.values().at(-1),{error:'off'});
 // Same choice in another tab / the other switch: the storage event updates this one.
 f=setup({permission:'granted'});await f.render('switch',{compact:true,follow:true});
 f.store.set('wegopub-location','on');f.listeners.storage({key:'wegopub-location'});
 assert.equal(f.elements.switch.attrs['aria-checked'],'true');assert.equal(f.calls.watch,1);
 f.store.set('wegopub-location','off');f.listeners.storage({key:'wegopub-location'});
 assert.equal(f.elements.switch.attrs['aria-checked'],'false');assert.equal(f.calls.clear,1);
 f=setup({stored:'on',permission:'denied'});await f.render('switch',{compact:true,follow:true});
 assert.deepEqual(f.values(),[{error:'denied'}],'The Map learns that the browser blocks location');assert.equal(f.calls.watch,0);
 console.log('Location component checks passed: no prompt before opting in, probe after, switch asks on tap, on/off remembered, denied and timeout handled.');
})().catch(e=>{console.error(e);process.exit(1);});
