import type { PDFDocumentProxy } from "pdfjs-dist";
import { MAX_PLAN_BYTES, planFileError } from "./plan-assets";
import { paintedImages, renderScale } from "./pdf-render-scale";

/**
 * PDF plans.
 *
 * A PDF is checked in the browser. It must have exactly ONE page; anything else
 * is rejected before it is stored or scanned. The single page is then drawn to a
 * PNG and handed to the same upload / scan / review pipeline an image upload uses,
 * so nothing downstream needs to know a PDF was involved.
 *
 * pdf.js is loaded on demand, so it adds nothing to the page until someone picks a PDF.
 */

export type PreparedPlan = {
  /** The file the rest of the app should use (always an image). */
  file: File;
  /** Original PDF name, when `file` was rendered from a PDF. */
  convertedFrom?: string;
};

const PDF_MIME = "application/pdf";

export function isPdfFile(file: Pick<File, "type" | "name">): boolean {
  if (file.type === PDF_MIME) return true;
  const unknownType = file.type === "" || file.type === "application/octet-stream";
  return unknownType && /\.pdf$/i.test(file.name);
}

/** The one-page rule. Returns the message to show, or null when the page count is fine. */
export function pdfPageCountError(pages: number): string | null {
  if (pages === 1) return null;
  if (pages < 1) return "This PDF has no pages. Upload a PDF with one page.";
  return `This PDF has ${pages} pages. Upload a PDF with only one page.`;
}

function pdfReadError(err: unknown): Error {
  const name = (err as { name?: string } | null)?.name;
  if (name === "PasswordException") {
    return new Error("This PDF is password-protected. Remove the password and upload it again.");
  }
  return new Error("This PDF could not be read. Export the plan again and upload the new file.");
}

let pdfjsReady: Promise<typeof import("pdfjs-dist")> | null = null;
function loadPdfjs() {
  if (!pdfjsReady) {
    pdfjsReady = (async () => {
      const [lib, worker] = await Promise.all([
        import("pdfjs-dist"),
        import("pdfjs-dist/build/pdf.worker.min.mjs?url"),
      ]);
      lib.GlobalWorkerOptions.workerSrc = worker.default;
      return lib;
    })().catch((err) => {
      pdfjsReady = null; // allow a retry if the download failed
      throw err;
    });
  }
  return pdfjsReady;
}

async function looksLikePdf(file: File): Promise<boolean> {
  const head = new TextDecoder("latin1").decode(await file.slice(0, 1024).arrayBuffer());
  return head.includes("%PDF-");
}

async function renderFirstPage(doc: PDFDocumentProxy, name: string, lastModified: number): Promise<File> {
  const page = await doc.getPage(1);
  const base = page.getViewport({ scale: 1 });
  // A scanned or picture page is drawn at its picture's own resolution; see pdf-render-scale.ts.
  const { OPS } = await loadPdfjs();
  const ops = await page.getOperatorList();
  let { scale } = renderScale(base.width, base.height, paintedImages(ops.fnArray, ops.argsArray, OPS));

  const stem = name.replace(/\.pdf$/i, "") || "plan";
  const canvas = document.createElement("canvas");
  try {
    // If the PNG comes out over the size limit, draw it again a little smaller.
    for (let attempt = 0; attempt < 4; attempt++) {
      const viewport = page.getViewport({ scale });
      canvas.width = Math.max(1, Math.floor(viewport.width));
      canvas.height = Math.max(1, Math.floor(viewport.height));
      const ctx = canvas.getContext("2d");
      if (!ctx) throw new Error("This browser could not draw the PDF page. Try another browser.");
      ctx.fillStyle = "#ffffff"; // PDF pages are transparent; scans expect dark ink on white
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      await page.render({ canvas, viewport }).promise;

      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("The PDF page could not be converted to an image. Try again.");
      if (blob.size <= MAX_PLAN_BYTES) {
        return new File([blob], `${stem}.png`, { type: "image/png", lastModified });
      }
      scale *= 0.75;
    }
    throw new Error("This PDF page is too detailed to convert within 25 MB. Export a simpler or smaller page.");
  } finally {
    canvas.width = 0; // release the bitmap memory
    canvas.height = 0;
    page.cleanup();
  }
}

async function pdfToImage(file: File): Promise<PreparedPlan> {
  if (file.size <= 0 || file.size > MAX_PLAN_BYTES) {
    throw new Error("Upload a non-empty PDF no larger than 25 MB.");
  }
  if (!(await looksLikePdf(file))) {
    throw new Error("This file is not a valid PDF. Export the plan again and upload the new file.");
  }

  const pdfjs = await loadPdfjs();
  const bytes = new Uint8Array(await file.arrayBuffer());
  const task = pdfjs.getDocument({ data: bytes, enableXfa: false });

  let doc: PDFDocumentProxy;
  try {
    doc = await task.promise;
  } catch (err) {
    throw pdfReadError(err);
  }

  try {
    const pageProblem = pdfPageCountError(doc.numPages);
    if (pageProblem) throw new Error(pageProblem);
    const image = await renderFirstPage(doc, file.name, file.lastModified);
    return { file: image, convertedFrom: file.name };
  } catch (err) {
    if (err instanceof Error) throw err;
    throw pdfReadError(err);
  } finally {
    await doc.destroy();
  }
}

/**
 * The one entry point both upload screens use. Images pass straight through
 * (after the usual type and size check); a PDF is validated and converted.
 * Rejects with an Error whose message is ready to show the user.
 */
export async function preparePlanFile(file: File): Promise<PreparedPlan> {
  if (isPdfFile(file)) return pdfToImage(file);
  const problem = planFileError(file);
  if (problem) throw new Error(problem);
  return { file };
}
