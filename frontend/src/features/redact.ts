/** 组 B。按图片真实像素导出涂黑后的图，不发请求。 */

export type Stroke = {
  x: number;
  y: number;
  width: number;
  height: number;
};

const OUTPUT_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

function outputType(file: File): string {
  return OUTPUT_TYPES.has(file.type) ? file.type : "image/png";
}

export async function redactImage(file: File, strokes: Stroke[]): Promise<Blob> {
  const bitmap = await createImageBitmap(file);
  try {
    const canvas = document.createElement("canvas");
    canvas.width = bitmap.width;
    canvas.height = bitmap.height;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("Canvas is not available.");
    }

    context.drawImage(bitmap, 0, 0);
    context.fillStyle = "#000000";
    for (const stroke of strokes) {
      context.fillRect(stroke.x, stroke.y, stroke.width, stroke.height);
    }

    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, outputType(file));
    });
    if (!blob) {
      throw new Error("Failed to export the redacted image.");
    }
    return blob;
  } finally {
    bitmap.close();
  }
}
