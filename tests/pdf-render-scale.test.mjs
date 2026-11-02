import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

async function load(path) {
  const source = await readFile(new URL(path, import.meta.url), 'utf8');
  const code = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.ESNext}}).outputText;
  return import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`);
}

const {paintedImages, renderScale, VECTOR_LONG_SIDE, MAX_RENDER_PIXELS} = await load('../src/lib/pdf-render-scale.ts');

// The codes pdf.js 5 uses; the module takes them as a parameter.
const OPS = {save: 10, restore: 11, transform: 12, paintFormXObjectBegin: 74, paintFormXObjectEnd: 75,
  paintImageMaskXObject: 83, paintImageXObject: 85};

// 01.png saved as a PDF at 150 dpi: 1312 x 1024 px on a 629.76 x 491.52 pt page.
const PAGE = [629.76, 491.52];
const fullPage = (w, h) => ({fn: [OPS.save, OPS.transform, OPS.paintImageXObject, OPS.restore],
  args: [[], [PAGE[0], 0, 0, PAGE[1], 0, 0], ['img_1', w, h], []]});

test('a picture saved as a PDF is drawn at its own resolution, not enlarged', () => {
  const {fn, args} = fullPage(1312, 1024);
  const images = paintedImages(fn, args, OPS);
  assert.deepEqual(images.map(({width, height}) => [width, height]), [[1312, 1024]]);
  const {scale, source} = renderScale(...PAGE, images);
  assert.equal(source, 'image');
  assert.equal(Math.round(PAGE[0] * scale), 1312);
  assert.equal(Math.round(PAGE[1] * scale), 1024);
});

test('a vector page gets the vector size', () => {
  const {scale, source} = renderScale(1190.55, 841.89, []); // A3 landscape, no pictures
  assert.equal(source, 'vector');
  assert.equal(Math.round(1190.55 * scale), VECTOR_LONG_SIDE);
});

test('a small logo in the title block does not decide the size', () => {
  const fn = [OPS.save, OPS.transform, OPS.paintImageXObject, OPS.restore];
  const args = [[], [60, 0, 0, 30, 1100, 20], ['logo', 600, 300], []];
  const {source} = renderScale(1190.55, 841.89, paintedImages(fn, args, OPS));
  assert.equal(source, 'vector');
});

test('nested transforms and form XObjects are followed, and restore undoes them', () => {
  // A scan placed inside a form scaled by 0.5: its 2000 px span 300 pt on the page.
  const fn = [OPS.transform, OPS.paintFormXObjectBegin, OPS.save, OPS.transform, OPS.paintImageMaskXObject,
    OPS.restore, OPS.paintFormXObjectEnd, OPS.paintImageXObject];
  const args = [[1, 0, 0, 1, 10, 10], [[0.5, 0, 0, 0.5, 0, 0], [0, 0, 600, 400]], [], [600, 0, 0, 400, 0, 0],
    [{width: 2000, height: 1333}], [], [], ['after', 100, 100]];
  const [scan, after] = paintedImages(fn, args, OPS);
  assert.deepEqual(scan.matrix.slice(0, 4), [300, 0, 0, 200]);
  assert.deepEqual(after.matrix, [1, 0, 0, 1, 10, 10]); // form matrix popped, outer transform kept
  const {scale, source} = renderScale(300, 200, [scan]);
  assert.equal(source, 'image');
  assert.equal(Math.round(300 * scale), 2000);
});

test('a rotated scan uses the length of each drawn side', () => {
  const fn = [OPS.save, OPS.transform, OPS.paintImageXObject, OPS.restore];
  const args = [[], [0, 400, -600, 0, 600, 0], ['scan', 1200, 800], []]; // turned 90 degrees
  const {scale} = renderScale(600, 400, paintedImages(fn, args, OPS));
  assert.equal(scale, 3);
});

test('a huge scan is capped below the backend pixel limit', () => {
  const {fn, args} = fullPage(12000, 9366);
  const {scale} = renderScale(...PAGE, paintedImages(fn, args, OPS));
  assert.ok(PAGE[0] * PAGE[1] * scale * scale <= MAX_RENDER_PIXELS + 1);
});
