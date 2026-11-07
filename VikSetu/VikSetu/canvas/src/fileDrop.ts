import { createShapeId, type Editor, type TLShapeId } from "@tldraw/editor";
import { DOC_TYPE, FILE_TYPE, SHEET_TYPE, uploadFileWithProgress } from "./embedShapes";

export const MAX_CANVAS_FILE = 50 * 1024 * 1024;

export function formatFileSize(bytes: number): string {
  if (bytes >= 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

export function confirmLargeFile(file: File): boolean {
  return window.confirm(
    `"${file.name}" is ${formatFileSize(file.size)} (over 50 MB).\n\nAdd it to the canvas anyway? Upload may take a while.`
  );
}

export function finalizeUploadedFile(
  editor: Editor,
  shapeId: TLShapeId,
  file: File,
  point: { x: number; y: number },
  saved: { fileId: string; name: string; preview: string; kind?: string }
) {
  const lower = file.name.toLowerCase();
  if (lower.endsWith(".csv")) {
    const lines = saved.preview.split(/\r?\n/).filter(Boolean);
    const columns = (lines[0] ?? "A,B").split(",");
    const rows = lines.slice(1, 40).map((line) => line.split(","));
    editor.deleteShapes([shapeId]);
    editor.createShape({
      type: SHEET_TYPE,
      x: point.x,
      y: point.y,
      props: {
        w: 560,
        h: 300,
        title: saved.name,
        columns: JSON.stringify(columns),
        rows: JSON.stringify(rows.length ? rows : [columns.map(() => "")]),
      },
    });
    return;
  }
  if (lower.endsWith(".md") || lower.endsWith(".txt")) {
    editor.deleteShapes([shapeId]);
    editor.createShape({
      type: DOC_TYPE,
      x: point.x,
      y: point.y,
      props: {
        w: 420,
        h: 340,
        title: saved.name,
        format: lower.endsWith(".md") ? "md" : "text",
        body: saved.preview,
      },
    });
    return;
  }
  const kind = saved.kind ?? (file.type.startsWith("image/") ? "image" : "binary");
  const tall = kind === "image";
  editor.updateShape({
    id: shapeId,
    type: FILE_TYPE,
    props: {
      w: tall ? 320 : 300,
      h: tall ? 280 : 220,
      name: saved.name,
      fileId: saved.fileId,
      preview: saved.preview,
      kind,
      uploadPct: 100,
    },
  });
}

export async function placeDroppedFile(
  editor: Editor,
  file: File,
  point: { x: number; y: number },
  shapeId?: TLShapeId
) {
  if (file.size > MAX_CANVAS_FILE && !confirmLargeFile(file)) return;
  const id = shapeId ?? createShapeId();
  if (!shapeId) {
    editor.createShape({
      id,
      type: FILE_TYPE,
      x: point.x,
      y: point.y,
      props: { w: 300, h: 220, name: file.name, fileId: "", preview: "", uploadPct: 0 },
    });
  } else {
    editor.updateShape({
      id,
      type: FILE_TYPE,
      props: { name: file.name, fileId: "", preview: "", uploadPct: 0 },
    });
  }
  try {
    const saved = await uploadFileWithProgress(file, (pct) => {
      editor.updateShape({ id, type: FILE_TYPE, props: { uploadPct: Math.round(pct) } });
    });
    finalizeUploadedFile(editor, id, file, point, saved);
  } catch (error) {
    editor.updateShape({
      id,
      type: FILE_TYPE,
      props: { uploadPct: -1, preview: String(error) },
    });
  }
}

export async function dropFilesOnCanvas(editor: Editor, files: FileList | File[], clientX: number, clientY: number) {
  const list = Array.from(files);
  const point = editor.screenToPage({ x: clientX, y: clientY });
  for (let index = 0; index < list.length; index += 1) {
    const file = list[index];
    if (file.size > MAX_CANVAS_FILE && !confirmLargeFile(file)) continue;
    const spot = { x: point.x + index * 36, y: point.y + index * 28 };
    const shapeId = createShapeId();
    editor.createShape({
      id: shapeId,
      type: FILE_TYPE,
      x: spot.x,
      y: spot.y,
      props: {
        w: 300,
        h: 220,
        name: file.name,
        fileId: "",
        preview: "",
        uploadPct: 0,
      },
    });
    try {
      const saved = await uploadFileWithProgress(file, (pct) => {
        editor.updateShape({ id: shapeId, type: FILE_TYPE, props: { uploadPct: Math.round(pct) } });
      });
      finalizeUploadedFile(editor, shapeId, file, spot, saved);
    } catch (error) {
      editor.updateShape({
        id: shapeId,
        type: FILE_TYPE,
        props: { uploadPct: -1, preview: String(error) },
      });
    }
  }
}
