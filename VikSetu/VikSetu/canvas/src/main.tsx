import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import type { Editor } from "@tldraw/editor";
import { Tldraw } from "tldraw";
import "tldraw/tldraw.css";
import { AgentPanel } from "./AgentPanel";
import { CanvasErrorBoundary } from "./CanvasErrorBoundary";
import { placeEmbedAt, VikToolbar } from "./EmbedMenu";
import { watchCanvas } from "./changeLog";
import { watchCursor } from "./cursor";
import { LayerDock } from "./LayerDock";
import { CustomShapeUtil } from "./CustomShape";
import { ChartShapeUtil, DocShapeUtil, FILE_TYPE, FileShapeUtil, SheetShapeUtil } from "./embedShapes";
import { dropFilesOnCanvas } from "./fileDrop";
import { watchMapContext } from "./mapContext";
import { MAP_TYPE, MapShapeUtil } from "./MapShape";
import "./agent.css";

export const PERSISTENCE_KEY = "viksetu-canvas-v2";

function App() {
  const [editor, setEditor] = useState<Editor | null>(null);
  const stageRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // tldraw's copy handler replaces the clipboard with a space when a shape is selected.
    // A highlighted passage, or a field that has focus, should keep the browser copy.
    const keepTextCopy = (event: ClipboardEvent) => {
      const target = event.target;
      if (target instanceof Element && target.closest("input, textarea, select, [contenteditable='true']")) {
        event.stopImmediatePropagation();
        return;
      }
      if ((window.getSelection()?.toString() ?? "").length > 0) event.stopImmediatePropagation();
    };
    document.addEventListener("copy", keepTextCopy, true);
    document.addEventListener("cut", keepTextCopy, true);
    return () => {
      document.removeEventListener("copy", keepTextCopy, true);
      document.removeEventListener("cut", keepTextCopy, true);
    };
  }, []);

  return (
    <div className="canvas-shell">
      <div className="canvas-stage" ref={stageRef}>
        <Tldraw
          persistenceKey={PERSISTENCE_KEY}
          shapeUtils={[MapShapeUtil, ChartShapeUtil, DocShapeUtil, SheetShapeUtil, FileShapeUtil, CustomShapeUtil]}
          components={{ StylePanel: () => null, Toolbar: VikToolbar }}
          onMount={(instance) => {
            instance.user.updateUserPreferences({ colorScheme: "dark" });
            watchCanvas(instance);
            watchMapContext();
            watchCursor(instance);
            for (const shape of instance.getCurrentPageShapes()) {
              if (shape.type === FILE_TYPE && !(shape.props as { kind?: string }).kind) {
                instance.updateShape({
                  id: shape.id,
                  type: FILE_TYPE,
                  props: { kind: "" },
                });
              }
            }
            const shapes = instance.getCurrentPageShapes();
            const fresh = shapes.length === 0;
            if (!shapes.some((shape) => shape.type === MAP_TYPE)) {
              instance.createShape({
                type: MAP_TYPE,
                x: 48,
                y: 48,
                props: { w: 760, h: 520 },
              });
            }
            if (!shapes.some((shape) => shape.type === FILE_TYPE)) {
              instance.createShape({
                type: FILE_TYPE,
                x: 840,
                y: 48,
                props: { w: 300, h: 220, name: "", fileId: "", preview: "", uploadPct: 100, kind: "" },
              });
            }
            if (fresh) instance.zoomToFit({ animation: { duration: 280 } });
            const container = instance.getContainer();
            const allowDrop = (event: DragEvent) => {
              const types = event.dataTransfer?.types;
              if (types?.includes("Files") || types?.includes("text/plain")) event.preventDefault();
            };
            const onDrop = (event: DragEvent) => {
              const embed = event.dataTransfer?.getData("text/plain") ?? "";
              if (embed.startsWith("viksetu-embed:")) {
                event.preventDefault();
                event.stopPropagation();
                placeEmbedAt(instance, embed.slice("viksetu-embed:".length), event.clientX, event.clientY);
                return;
              }
              const files = event.dataTransfer?.files;
              if (!files?.length) return;
              const target = event.target as HTMLElement | null;
              if (target?.closest(".vik-file-frame")) return;
              event.preventDefault();
              event.stopPropagation();
              void dropFilesOnCanvas(instance, files, event.clientX, event.clientY);
            };
            container.addEventListener("dragover", allowDrop);
            container.addEventListener("drop", onDrop, true);
            setEditor(instance);
          }}
        />
        <LayerDock editor={editor} stage={stageRef} />
      </div>
      <AgentPanel editor={editor} />
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <CanvasErrorBoundary>
    <App />
  </CanvasErrorBoundary>
);
