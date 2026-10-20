// Pure JavaScript unit check with a DOM stub; does not open a browser.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(process.argv[2],'utf8');
const payload=html.match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/)[1];
const code=html.match(/<\/script><script>([\s\S]*?)<\/script>/)[1];
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{value:'',innerHTML:'',textContent:'',listeners:{},classList:{toggle(){}},addEventListener(k,f){this.listeners[k]=f},click(){}});return elements.get(id)}
element('payload').textContent=payload;
const buttons=['selections','evaluation','market','returns'].map(tab=>({dataset:{tab},setAttribute(){}}));
// A real select defaults to its first option; mimic that for the strategy selector.
element('strategy').value='full_system';
vm.runInNewContext(code,{document:{getElementById:element,querySelectorAll:()=>buttons,createElement:()=>element('link')},Blob,URL:{createObjectURL:()=> 'blob:unit-test',revokeObjectURL(){}},setTimeout:f=>f()});
const report=JSON.parse(payload).report;let count=0;
if(report.window && Object.keys(report.summary||{}).length){
 assert.ok(element('roiScope').textContent.includes(report.window[0]));
 assert.ok(element('roiScope').textContent.includes(report.window[1]));
 assert.equal((element('sources').innerHTML.match(/<li>/g)||[]).length,report.coupons.filter(c=>c.official).length);
}
for(let i=0;i<report.coupons.length;i++){
 element('coupon').value=String(i);element('coupon').listeners.change();
 const market=report.coupons[i].market_comparison;
 assert.equal((element('marketRows').innerHTML.match(/<tr>/g)||[]).length,market?.fixtures?.length||0);
 if(market?.is_example)assert.ok(element('marketScope').textContent.includes('FICTICIAS'));
 for(const [budget,plans] of Object.entries(report.coupons[i].budgets)){
  element('budget').value=budget;
  for(const [strategy,plan] of Object.entries(plans.strategies)){
   element('strategy').value=strategy;element('strategy').listeners.change();
   assert.equal((element('fixtures').innerHTML.match(/<tr>/g)||[]).length,14);
   assert.ok(!/NaN|undefined/.test(element('cards').innerHTML+element('fixtures').innerHTML));
   assert.equal((element('columns').innerHTML.match(/class="column"/g)||[]).length,plan.column_count);
   assert.equal((element('riskRows').innerHTML.match(/<tr>/g)||[]).length,plan.risk?5:0);
   if(plan.risk){
    assert.ok(Math.abs(plan.risk.at_least['14']-plan.coverage)<1e-10);
    assert.ok(!/NaN|undefined/.test(element('riskRows').innerHTML+element('riskNote').textContent));
   }
   count++;
  }
 }
}
buttons.forEach(b=>b.onclick());element('download').onclick();
assert.ok(element('link').download.endsWith('.json'));
console.log(`${count} states, navigation and JSON export passed. Visual layout not assessed.`);
