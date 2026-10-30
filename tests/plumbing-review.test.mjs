import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

const source=(await readFile(new URL('../src/lib/plumbing-proposals.ts',import.meta.url),'utf8')).replace("import { authHeaders } from './supabase';",'const authHeaders=async()=>({});');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.ESNext}}).outputText;
const {fixtureReviewError,placeFixtureBox,moveFixtureBox,resizeFixtureBox,reviewClasses,fixtureSummary,FIXTURE_NAMES,FIXTURE_COLORS}=await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
const fixture=(id,box,cls='WC')=>({id,fixture_class:cls,box_2d:box,uncertainty:null});

test('review rejects same and cross-class overlaps without losing adjacent fixtures',()=>{
  const first=fixture('one',[10,10,40,40]);
  assert.equal(fixtureReviewError([first,fixture('two',[10,42,40,72])]),'');
  assert.match(fixtureReviewError([first,fixture('two',[10,10,40,40])]),/overlap/);
  assert.match(fixtureReviewError([first,fixture('two',[10,10,40,40],'LAV')]),/overlap/);
});
test('image placement and movement stay inside the original image',()=>{
  assert.deepEqual(placeFixtureBox(500,500),[480,485,520,515]);
  assert.deepEqual(placeFixtureBox(0,1000),[0,970,40,1000]);
  const moved=moveFixtureBox([100,100,140,130],-1000,1000);
  assert.deepEqual(moved,[0,970,40,1000]);
  assert.equal(fixtureReviewError([fixture('one',moved)]),'');
});
test('corner resizing preserves valid bounds even when dragged across the opposite edge',()=>{
  assert.deepEqual(resizeFixtureBox([100,100,140,130],0,150,150),[137,127,140,130]);
  assert.deepEqual(resizeFixtureBox([100,100,140,130],3,2000,2000),[100,100,1000,1000]);
});
test('review rejects invalid coordinates and repeated IDs before confirmation',()=>{
  for(const box of [[0,0,NaN,5],[0,0,Infinity,5],[10,10,5,20],[-1,0,5,5],[0,0,1001,5]]) assert.notEqual(fixtureReviewError([fixture('one',box)]),'');
  assert.match(fixtureReviewError([fixture('one',[10,10,40,40]),fixture('one',[50,50,60,60])]),/unique/);
  assert.equal(fixtureReviewError([]),''); // Explicit review may exclude both classes; server guards empty priced plans.
});
test('a tag review covers every priced tag; a model review only the drawn fixtures',()=>{
  assert.deepEqual(reviewClasses('tags'),['WC','LAV','U','FD','CO','KS','SH','BT','WM','HB','DF']);
  assert.deepEqual(reviewClasses('gemini'),['WC','LAV','U','KS','SH','BT','WM']);
  const drain=fixture('one',[10,10,40,40],'FD');
  assert.equal(fixtureReviewError([drain],reviewClasses('tags')),'');
  assert.notEqual(fixtureReviewError([drain],reviewClasses('gemini')),'');
});
test('the confirmation names every reviewed class, including zeros',()=>{
  const fixtures=[fixture('a',[0,0,5,5]),fixture('b',[10,10,15,15],'FD'),fixture('c',[20,20,25,25],'FD')];
  assert.equal(fixtureSummary(fixtures,['WC','LAV','FD']),'1 toilet, 0 lavatories and 2 floor drains');
  assert.equal(fixtureSummary(fixtures.slice(0,1),['WC','LAV']),'1 toilet and 0 lavatories');
});
test('every fixture type has a name and a colour for the review screen',()=>{
  for(const cls of reviewClasses('tags')){
    assert.equal(FIXTURE_NAMES[cls].length,2,cls);
    assert.match(FIXTURE_COLORS[cls],/^#[0-9a-f]{6}$/,cls);
  }
  assert.equal(new Set(reviewClasses('tags').map(c=>FIXTURE_COLORS[c])).size,reviewClasses('tags').length);
});
