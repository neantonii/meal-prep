/** Photos for the takeout estimate: shrunk in the browser before upload, so
 * a phone picture becomes a ~100–300 KB JPEG instead of several MB.
 *
 * HEIC/HEIF (iPhone photos) can only be shrunk where the browser can decode
 * them (Safari; an iPhone's own picker converts to JPEG anyway). Elsewhere,
 * e.g. desktop Chrome or Firefox, the original file is sent as is: the
 * estimate service reads HEIC itself. */

/** Longest side of a shrunk photo, in pixels: enough to read a receipt. */
const MAX_SIDE = 1280;
/** How many photos one estimate takes (the server refuses more). */
export const MAX_PHOTOS = 3;
/** Largest original HEIC sent unshrunk (the server's limit, in bytes). */
const MAX_ORIGINAL = 12 * 1024 * 1024;

const HEIC = /\.(heic|heif)$/i;

const isHeic = (file: File) => /^image\/hei[cf]$/.test(file.type) || HEIC.test(file.name);

/** `file` as a data URL to send: a JPEG no larger than MAX_SIDE on its
 * longest side, or the original HEIC when this browser can't read it. */
export async function shrinkPhoto(file: File): Promise<string> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch (e) {
    if (isHeic(file)) return original(file);
    throw e;
  }
  try {
    const scale = Math.min(1, MAX_SIDE / Math.max(bitmap.width, bitmap.height));
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    const context = canvas.getContext("2d");
    if (!context) throw new Error("This browser can't resize photos");
    context.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL("image/jpeg", 0.82);
  } finally {
    bitmap.close();
  }
}

/** A HEIC file as a data URL, unchanged (typed image/heic even when the
 * browser reports no type). */
async function original(file: File): Promise<string> {
  if (file.size > MAX_ORIGINAL) throw new Error("That photo is over 12 MB");
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  const type = /^image\/heif$/.test(file.type) ? "image/heif" : "image/heic";
  return `data:${type};base64,${btoa(binary)}`;
}

/** The image files among dropped, pasted or picked files (HEIC included,
 * which some browsers report with no type). */
export const imageFiles = (files: Iterable<File>): File[] =>
  [...files].filter((f) => f.type.startsWith("image/") || HEIC.test(f.name));
