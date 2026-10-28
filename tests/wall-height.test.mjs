import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

test('wall height accepts finite metric values and rejects empty/out-of-range input', async () => {
  const source = await readFile(new URL('../src/lib/wall-height.ts', import.meta.url), 'utf8');
  const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext}}).outputText;
  const {parseWallHeight, DEFAULT_WALL_HEIGHT_M} = await import(`data:text/javascript;base64,${Buffer.from(compiled).toString('base64')}`);
  assert.equal(DEFAULT_WALL_HEIGHT_M, 2.7);
  for (const [raw, expected] of [['2.70', 2.7], ['3.2', 3.2], ['10', 10], ['0.5', .5]]) assert.equal(parseWallHeight(raw), expected);
  for (const raw of ['', ' ', '0', '-1', '10.001', 'NaN', 'Infinity', '2,7', 'not a number']) assert.equal(parseWallHeight(raw), null);
});
