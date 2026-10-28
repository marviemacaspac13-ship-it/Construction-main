import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

async function load(path, replacements) {
  let source = await readFile(new URL(path, import.meta.url), 'utf8');
  for (const [from, to] of replacements) source = source.replace(from, to);
  const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext}}).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
}

const {messageFrom} = await load('../src/lib/estimate.ts', [
  ['import { authHeaders } from "./supabase";', 'const authHeaders=async()=>({});'],
  ['import.meta.env.VITE_SCAN_API_URL', 'undefined'],
]);
const {uploadTips, ORIGINAL_EXPORT_TIP} = await load('../src/lib/upload-guidance.ts', []);
const {emptyProposalHint} = await load('../src/lib/electrical-proposals.ts', [
  ["import { authHeaders } from './supabase';", 'const authHeaders=async()=>({});'],
]);

test('a refusal shows its message, not the reader diagnostics behind it', () => {
  const detail = {message: 'Only 2 plumbing fixtures could be read on this plan.',
    warnings: ["read: {'water_closet': 1}", '2 fixtures imply materials, 3 is the minimum to price']};
  assert.equal(messageFrom({detail}, 422), 'Only 2 plumbing fixtures could be read on this plan.');
  assert.equal(messageFrom({detail: 'Upload an image no larger than 25 MB.'}, 413), 'Upload an image no larger than 25 MB.');
  assert.equal(messageFrom(null, 500), 'Estimate failed (500)');
});

test('every plan type tells the user to upload the original export', () => {
  for (const planType of ['Floor Plan', 'Electrical Plan', 'Plumbing Plan']) {
    const tips = uploadTips(planType);
    assert.ok(tips.length >= 3, planType);
    assert.ok(tips.includes(ORIGINAL_EXPORT_TIP), planType);
  }
  assert.match(ORIGINAL_EXPORT_TIP, /original/i);
  assert.match(ORIGINAL_EXPORT_TIP, /enlarg/i);
});

test('an electrical review with nothing proposed says why and what to do', () => {
  assert.match(emptyProposalHint({proposed: []}), /clearer export/);
  assert.match(emptyProposalHint({proposed: []}), /add/i);
  assert.equal(emptyProposalHint({proposed: [{id: 'a'}]}), '');
});
