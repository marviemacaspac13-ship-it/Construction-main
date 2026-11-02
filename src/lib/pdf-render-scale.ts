/**
 * How large to draw a PDF page before it is scanned.
 *
 * The backend's local readers are tuned to the pixel size of the sample plans
 * (500-1300 px long side): the column counter accepts 10-40 px squares and symbol
 * matching tries 0.6-1.5x its reference crops. Drawing every page at 4200 px made
 * them miss everything - `01.png` columns 16 -> 3, local electrical devices -> 0.
 *
 * So a page that is mostly one embedded picture (a scan, or a PNG saved as PDF) is
 * drawn at that picture's own resolution, and scans exactly as the picture would
 * uploaded directly. A vector page has no native resolution and gets
 * VECTOR_LONG_SIDE, which is a guess: no vector PDF plan has been tried yet.
 *
 * No imports, so the tests can load it without pdf.js.
 */

/** An image painted on the page: its pixel size and the matrix it was drawn with (PDF points). */
export type PaintedImage = { width: number; height: number; matrix: number[] };

/** The pdf.js operator codes this needs (pass `pdfjs.OPS`). */
export type PaintOps = {
  save: number;
  restore: number;
  transform: number;
  paintFormXObjectBegin: number;
  paintFormXObjectEnd: number;
  paintImageXObject: number;
  paintImageMaskXObject: number;
};

/** The largest size at which `01.png` still counts all 16 columns (2600 px finds 0). */
export const VECTOR_LONG_SIDE = 2000;
/** The backend refuses images above 40 million pixels; stay well under. */
export const MAX_RENDER_PIXELS = 24_000_000;
/** A picture covering at least this share of the page IS the page. */
const IMAGE_PAGE_SHARE = 0.5;

const IDENTITY = [1, 0, 0, 1, 0, 0];

// PDF `cm`: the new matrix applies first, then the current one.
function concat(m: number[], ctm: number[]): number[] {
  return [
    m[0] * ctm[0] + m[1] * ctm[2],
    m[0] * ctm[1] + m[1] * ctm[3],
    m[2] * ctm[0] + m[3] * ctm[2],
    m[2] * ctm[1] + m[3] * ctm[3],
    m[4] * ctm[0] + m[5] * ctm[2] + ctm[4],
    m[4] * ctm[1] + m[5] * ctm[3] + ctm[5],
  ];
}

/** Walk a pdf.js operator list and return every image with the matrix in force when it was drawn. */
export function paintedImages(fnArray: number[], argsArray: unknown[][], ops: PaintOps): PaintedImage[] {
  const images: PaintedImage[] = [];
  const stack: number[][] = [];
  let ctm = IDENTITY;
  for (let i = 0; i < fnArray.length; i++) {
    const fn = fnArray[i];
    const args = argsArray[i] ?? [];
    if (fn === ops.save) {
      stack.push(ctm);
    } else if (fn === ops.restore) {
      ctm = stack.pop() ?? IDENTITY;
    } else if (fn === ops.transform) {
      ctm = concat(args as number[], ctm);
    } else if (fn === ops.paintFormXObjectBegin) {
      stack.push(ctm);
      const matrix = args[0];
      if (Array.isArray(matrix) && matrix.length === 6) ctm = concat(matrix as number[], ctm);
    } else if (fn === ops.paintFormXObjectEnd) {
      ctm = stack.pop() ?? IDENTITY;
    } else if (fn === ops.paintImageXObject) {
      // args: [objId, width, height]
      const [, width, height] = args as [unknown, number, number];
      if (width > 0 && height > 0) images.push({ width, height, matrix: ctm });
    } else if (fn === ops.paintImageMaskXObject) {
      // 1-bit scans are often stencil masks. args: [{ width, height, ... }]
      const img = args[0] as { width?: number; height?: number } | undefined;
      if (img?.width && img?.height) images.push({ width: img.width, height: img.height, matrix: ctm });
    }
  }
  return images;
}

/**
 * Scale (pixels per PDF point) to draw a page of `pageWidth` x `pageHeight` points.
 * `source` says whether it followed an embedded picture or the vector default.
 */
export function renderScale(
  pageWidth: number,
  pageHeight: number,
  images: PaintedImage[],
): { scale: number; source: "image" | "vector" } {
  const pageArea = pageWidth * pageHeight;
  let best: { area: number; scale: number } | null = null;
  for (const { width, height, matrix: [a, b, c, d] } of images) {
    const area = Math.abs(a * d - b * c);
    const drawnW = Math.hypot(a, b);
    const drawnH = Math.hypot(c, d);
    if (!area || !drawnW || !drawnH) continue;
    if (!best || area > best.area) best = { area, scale: Math.max(width / drawnW, height / drawnH) };
  }

  let scale: number;
  let source: "image" | "vector";
  if (best && best.area >= IMAGE_PAGE_SHARE * pageArea) {
    scale = best.scale;
    source = "image";
  } else {
    scale = VECTOR_LONG_SIDE / Math.max(pageWidth, pageHeight);
    source = "vector";
  }
  if (pageArea * scale * scale > MAX_RENDER_PIXELS) scale = Math.sqrt(MAX_RENDER_PIXELS / pageArea);
  return { scale, source };
}
