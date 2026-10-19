/* Exercise the actual display script against every saved scenario. */
const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');const page=fs.readFileSync(path.join(root,'docs/index.html'),'utf8');
const evidence=JSON.parse(page.match(/<script id="evidence" type="application\/json">([\s\S]*?)<\/script>/)[1]);
const source=page.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
const ids=[...page.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);assert.equal(new Set(ids).size,ids.length);
const nodes=Object.fromEntries(ids.map(id=>[id,{value:'',textContent:'',innerHTML:'',hidden:false,className:'',
 children:[],listeners:{},appendChild(x){this.children.push(x)},addEventListener(k,f){this.listeners[k]=f}}]));
nodes.evidence.textContent=JSON.stringify(evidence);nodes.method.value='covariance';
nodes.force.value='1';nodes.haircut.value='0.02';nodes.cash.value='0';
const document={getElementById:id=>{assert.ok(nodes[id],id);return nodes[id]},createElement:()=>({value:'',textContent:''})};
const context=vm.createContext({document,Intl,console});vm.runInContext(source,context);
const money=v=>new Intl.NumberFormat('en-US',{minimumFractionDigits:2,maximumFractionDigits:2}).format(Math.abs(v)<.005?0:v);
let stresses=0,runoffs=0;
for(const row of evidence.case.instantaneous_scenarios){
 nodes.method.value=row.method;nodes.shock.value=row.scenario;nodes.shock.listeners.change();
 assert.equal(nodes.stressA.textContent,money(row.assets_usd));assert.equal(nodes.stressL.textContent,money(row.liability_usd));
 assert.equal(nodes.stressS.textContent,money(row.surplus_usd));
 assert.equal(nodes.stressFraction.textContent,(row.surplus_fraction_initial_liability*100).toFixed(4)+'% of base liability PV');
 assert.equal(nodes.error.hidden,true);stresses++;
}
for(const row of evidence.case.runoff_scenarios){
 nodes.method.value=row.method;nodes.force.value=String(row.mortality_force);nodes.haircut.value=String(row.haircut);nodes.cash.value=String(row.cash_rate_shift_decimal);
 nodes.method.listeners.change();assert.equal(nodes.runoffSurplus.textContent,money(row.final.surplus_after_unpaid_usd));
 assert.equal(nodes.runoffSales.textContent,money(row.gross_bond_sales_usd));assert.equal(nodes.runoffCost.textContent,money(row.haircut_cost_usd));
 assert.equal((nodes.annualRows.innerHTML.match(/<tr>/g)||[]).length,10);
 const years=evidence.annual.filter(x=>x.case_id===row.case_id).sort((a,b)=>a.year-b.year);
 assert.equal(years.length,10);
 for(const year of years)assert.ok(nodes.annualRows.innerHTML.includes(money(year.surplus_after_unpaid_usd)));
 assert.equal(nodes.error.hidden,true);runoffs++;
}
nodes.force.value='2';assert.throws(()=>nodes.force.listeners.change(),/does not resolve uniquely/);
assert.equal(nodes.error.hidden,false);nodes.force.value='1';nodes.force.listeners.change();assert.equal(nodes.error.hidden,true);
for(const id of ['method','shock','force','haircut','cash'])assert.ok(page.includes('for="'+id+'"'));
for(const match of page.matchAll(/(?:href|src)="([^"]+)"/g)){
 const target=match[1];if(target.startsWith('http')||target.startsWith('#'))continue;
 assert.ok(fs.statSync(path.join(root,'docs',target)).isFile(),target);
}
const expected=JSON.parse(fs.readFileSync(path.join(root,'reports/current_case_20261019/current_case.json')));
assert.deepEqual(evidence.case,expected);
const record={status:'passed',actual_page_script_executed:true,all_saved_stresses:stresses,all_runoff_combinations:runoffs,
 annual_rows_checked:1080,invalid_selection_fails_visibly:true,all_local_links_exist:true,controls_labelled:true,
 browser_render_keyboard_and_live_site_verified:false};
fs.writeFileSync(path.join(root,'reports/integrated_20261019/explorer_script_verification.json'),JSON.stringify(record,null,2)+'\n');
console.log(JSON.stringify(record));
