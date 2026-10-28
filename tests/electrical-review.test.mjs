import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';
const source=(await readFile(new URL('../src/lib/electrical-proposals.ts',import.meta.url),'utf8')).replace("import { authHeaders } from './supabase';",'const authHeaders=async()=>({});');
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText;
const {initialElectricalChoice,electricalChoiceError,applyElectricalGroupDecision}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
const obs={id:'a',assembly_id:'a',box_2d:[1,1,10,10],device_class:'switch',raw_mark:null,adjacent_text:null,socket_configuration:null,gang_count:2,switching_function:'one_way',uncertainty:null};
test('new proposals never preconfirm product or box',()=>{
 const c=initialElectricalChoice(obs);assert.equal(c.selected_sku,null);assert.equal(c.box_compatibility_confirmed,false);assert.ok(electricalChoiceError(c));
});
test('switch count and function must match product before proceeding',()=>{
 const c={...initialElectricalChoice(obs),selected_sku:'SW02',box_item_id:'UTB01',box_compatibility_confirmed:true};
 assert.equal(electricalChoiceError(c),'');
 for(const change of [{selected_sku:'SW03'},{observation:{...obs,switching_function:'three_way'}},{box_compatibility_confirmed:false}])assert.ok(electricalChoiceError({...c,...change}));
});
test('excluded device and omitted box require explicit reasons',()=>{
 const c={...initialElectricalChoice(obs),selected_sku:'SW02'};
 assert.ok(electricalChoiceError(c));assert.equal(electricalChoiceError({...c,box_exclusion_reason:'Compatibility unknown'}),'');
 assert.ok(electricalChoiceError({...c,disposition:'exclude'}));assert.equal(electricalChoiceError({...c,selected_sku:null,disposition:'exclude',exclusion_reason:'Legend'}),'');
});

test('group product decisions affect only selected included devices and preserve evidence',()=>{
 const a=initialElectricalChoice({...obs,device_class:'light_point',gang_count:null});
 const b=initialElectricalChoice({...a.observation,id:'b',assembly_id:'b'});
 const excluded={...b,observation:{...b.observation,id:'excluded'},disposition:'exclude',exclusion_reason:'Legend'};
 const next=applyElectricalGroupDecision([a,b,excluded],['a','excluded'],{kind:'product',sku:'CLR01'});
 assert.equal(next[0].selected_sku,'CLR01');assert.equal(next[0].observation,a.observation);
 assert.equal(next[1],b);assert.equal(next[2],excluded);assert.equal(a.selected_sku,null);
});

test('group decisions reject mixed types, unknown types and conflicting switch specifications',()=>{
 const sw=initialElectricalChoice(obs);
 const light=initialElectricalChoice({...obs,id:'light',device_class:'light_point'});
 assert.throws(()=>applyElectricalGroupDecision([sw,light],['a','light'],{kind:'product',sku:'SW02'}));
 assert.throws(()=>applyElectricalGroupDecision([sw],['a'],{kind:'product',sku:'SW01'}));
 for(const change of [{switching_function:null},{switching_function:'three_way'},{gang_count:null},{device_class:'unknown'}]) {
  assert.throws(()=>applyElectricalGroupDecision([{...sw,observation:{...obs,...change}}],['a'],{kind:'product',sku:'SW02'}));
 }
 assert.equal(applyElectricalGroupDecision([sw],['a'],{kind:'product',sku:'SW02'})[0].selected_sku,'SW02');
});

test('shared box decisions require explicit confirmation or reason and product changes invalidate compatibility',()=>{
 const c={...initialElectricalChoice(obs),selected_sku:'SW02'};
 assert.throws(()=>applyElectricalGroupDecision([c],['a'],{kind:'box',itemId:'UTB01',confirmed:false,reason:''}));
 assert.throws(()=>applyElectricalGroupDecision([c],['a'],{kind:'box',itemId:null,confirmed:false,reason:' '}));
 const boxed=applyElectricalGroupDecision([c],['a'],{kind:'box',itemId:'UTB01',confirmed:true,reason:''});
 assert.equal(electricalChoiceError(boxed[0]),'');
 assert.equal(applyElectricalGroupDecision(boxed,['a'],{kind:'product',sku:'SW02'})[0].box_compatibility_confirmed,false);
 const omitted=applyElectricalGroupDecision([c],['a'],{kind:'box',itemId:null,confirmed:false,reason:'Separate scope'});
 assert.equal(electricalChoiceError(omitted[0]),'');
});

test('shared exclusions retain individual geometry and require a reason',()=>{
 const c=initialElectricalChoice(obs);
 assert.throws(()=>applyElectricalGroupDecision([c],['a'],{kind:'exclude',reason:''}));
 const next=applyElectricalGroupDecision([c],['a'],{kind:'exclude',reason:'Legend symbols'});
 assert.equal(next[0].exclusion_reason,'Legend symbols');assert.equal(next[0].observation,c.observation);
 assert.equal(electricalChoiceError(next[0]),'');
});

test('explicit shared switch confirmation fills unknown specifications without changing raw observations',()=>{
 const original={...obs,gang_count:null,switching_function:null};
 const a=initialElectricalChoice(original);
 const b=initialElectricalChoice({...original,id:'b',assembly_id:'b'});
 assert.throws(()=>applyElectricalGroupDecision([a,b],['a','b'],{kind:'product',sku:'SW03',confirmSwitchSpecs:false}));
 const next=applyElectricalGroupDecision([a,b],['a'],{kind:'product',sku:'SW03',confirmSwitchSpecs:true});
 assert.equal(next[0].selected_sku,'SW03');
 assert.equal(next[0].observation.gang_count,3);assert.equal(next[0].observation.switching_function,'one_way');
 assert.equal(next[0].observation.box_2d,original.box_2d);assert.equal(next[0].observation.assembly_id,original.assembly_id);
 assert.equal(original.gang_count,null);assert.equal(original.switching_function,null);assert.equal(next[1],b);
 assert.equal(next[0].box_compatibility_confirmed,false);
});

test('shared switch confirmation cannot overwrite a conflict or partially apply a group',()=>{
 const a=initialElectricalChoice({...obs,gang_count:null,switching_function:null});
 for(const conflict of [{gang_count:1},{switching_function:'three_way'},{switching_function:'four_way'}]) {
  const b=initialElectricalChoice({...a.observation,id:'b',assembly_id:'b',...conflict});
  assert.throws(()=>applyElectricalGroupDecision([a,b],['a','b'],{kind:'product',sku:'SW03',confirmSwitchSpecs:true}),/Device 2/);
  assert.equal(a.selected_sku,null);assert.equal(a.observation.gang_count,null);
  const next=applyElectricalGroupDecision([a,b],['a'],{kind:'product',sku:'SW03',confirmSwitchSpecs:true});
  assert.equal(next[1],b);
 }
 assert.throws(()=>applyElectricalGroupDecision([a],['a'],{kind:'product',sku:'OT03',confirmSwitchSpecs:true}));
});
