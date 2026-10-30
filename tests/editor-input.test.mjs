import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=await readFile(new URL('../src/lib/editor-input.ts',import.meta.url),'utf8');
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText;
const {parseEditor,fieldValue,csvEstimate,plumbingLabels}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const fields=[{key:'electrical_counts.OT01',integer:true,original:12},{key:'electrical_counts.OT02',integer:true},{key:'price.OT01',original:100}];
const empty={quantities:{},unit_prices:{},reason:null};
test('unknown count remains unknown; intentional quantity and price zeros survive',()=>{
 const r=parseEditor(fields,{'electrical_counts.OT01':'0','electrical_counts.OT02':'','price.OT01':'0'},empty);
 assert.deepEqual(r.errors,{});assert.equal(r.corrections.quantities.electrical_counts.OT01,0);
 assert.equal(r.corrections.quantities.electrical_counts.OT02,undefined);assert.equal(r.corrections.unit_prices.OT01,0);
 assert.equal(fieldValue(fields[0],r.corrections),'0');assert.deepEqual(empty,{quantities:{},unit_prices:{},reason:null});
});
test('reset removes absolute overrides without dropping unrelated corrections',()=>{
 const prior={quantities:{electrical_counts:{OT01:0,OT02:3,OT03:8}},unit_prices:{OT01:0},reason:'reviewed'};
 const r=parseEditor(fields,{'electrical_counts.OT01':'12','electrical_counts.OT02':'','price.OT01':'100'},prior);
 assert.deepEqual(r.corrections,{quantities:{electrical_counts:{OT03:8}},unit_prices:{},reason:'reviewed'});
 assert.equal(prior.quantities.electrical_counts.OT01,0);
});
test('blank known count, fractions, nonfinite values and negatives cannot silently save',()=>{
 for(const raw of ['', '1.2','Infinity','-1','9007199254740992']){
  assert.ok(parseEditor([fields[0]],{'electrical_counts.OT01':raw},empty).errors['electrical_counts.OT01']);
 }
});
test('CSV preserves decimal amounts and escapes units, commas and quotes',()=>{
 assert.equal(csvEstimate([{item_id:'OT01',item_name:'Outlet, "duplex"',unit:'1/2"',unit_price:1234.56,quantity:2,line_total:2469.12}]),
 'Item ID,Material,Unit,Unit Price,Quantity,Line Total\r\n"OT01","Outlet, ""duplex""","1/2""","1234.56","2","2469.12"');
});
test('the correction editor offers every priced plumbing fixture',()=>{
  assert.deepEqual(Object.keys(plumbingLabels).sort(),['bathtub','cleanout','drinking_fountain','floor_drain','hose_bib',
    'kitchen_sink','lavatory','shower','urinal','washing_machine','water_closet']);
});
