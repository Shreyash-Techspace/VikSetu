import type { Editor } from "@tldraw/editor";

export type PagePoint = { x: number; y: number };

let last: PagePoint | null = null;

export function watchCursor(editor: Editor) {
  const track = (event: PointerEvent) => {
    const target = event.target as HTMLElement | null;
    if (target?.closest(".agent-panel, .embed-drawer, .layer-dock")) return;
    const page = editor.screenToPage({ x: event.clientX, y: event.clientY });
    last = { x: Math.round(page.x), y: Math.round(page.y) };
  };
  window.addEventListener("pointermove", track);
}

export function getCursorPoint(editor: Editor): PagePoint {
  if (last) return last;
  const view = editor.getViewportPageBounds();
  return { x: Math.round(view.x + 48), y: Math.round(view.y + 48) };
}
