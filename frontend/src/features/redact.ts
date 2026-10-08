/** 组 B。按图片真实像素导出涂黑后的图，不发请求。 */

export type Stroke = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export function redactImage(file: File, strokes: Stroke[]): Promise<Blob> {
  throw new Error(`Not implemented: redactImage ${file.name} strokes=${strokes.length}`);
}
