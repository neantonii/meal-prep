/** Photos for the takeout estimate: shrunk in the browser before upload, so
 * a phone picture becomes a ~100–300 KB JPEG instead of several MB. */

/** Longest side of a shrunk photo, in pixels: enough to read a receipt. */
const MAX_SIDE = 1280;
/** How many photos one estimate takes (the server refuses more). */
export const MAX_PHOTOS = 3;

/** `file` as a JPEG data URL no larger than MAX_SIDE on its longest side. */
export async function shrinkPhoto(file: File): Promise<string> {
  const bitmap = await createImageBitmap(file);
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

/** The image files among dropped, pasted or picked files. */
export const imageFiles = (files: Iterable<File>): File[] =>
  [...files].filter((f) => f.type.startsWith("image/"));
