import { useEffect, useRef, useState, type RefObject } from "react";
import { createPortal } from "react-dom";
import type { Editor, TLShapeId } from "@tldraw/editor";
import { MAP_TYPE } from "./MapShape";

type LayerItem = { id: string; label: string; color: string };

type Dock = {
  pageX: number;
  pageY: number;
  open: boolean;
  dragging: boolean;
  layers: Record<string, boolean>;
  items: LayerItem[];
  mapShapeId: TLShapeId | null;
};

type Props = {
  editor: Editor | null;
  stage: RefObject<HTMLDivElement | null>;
};

function mapShapeForFrame(frame: HTMLIFrameElement): TLShapeId | null {
  const host = frame.closest(".vik-map-shape") as HTMLElement | null;
  const id = host?.id;
  return id && id.startsWith("shape:") ? (id as TLShapeId) : null;
}

export function LayerDock({ editor, stage }: Props) {
  const [dock, setDock] = useState<Dock | null>(null);
  const [, bump] = useState(0);
  const source = useRef<Window | null>(null);
  const drag = useRef<{ pageX: number; pageY: number; startX: number; startY: number } | null>(null);

  useEffect(() => {
    if (!editor || !dock) return;
    let frame = 0;
    let prev = "";
    const loop = () => {
      const camera = editor.getCamera();
      const key = `${camera.x},${camera.y},${camera.z}`;
      if (key !== prev) {
        prev = key;
        bump((value) => value + 1);
      }
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, [editor, dock]);

  useEffect(() => {
    if (!editor) return;
    return editor.store.listen(() => {
      const maps = editor.getCurrentPageShapes().filter((shape) => shape.type === MAP_TYPE);
      setDock((current) => {
        if (!current) return current;
        if (!maps.length) {
          source.current = null;
          return null;
        }
        if (current.mapShapeId && !maps.some((shape) => shape.id === current.mapShapeId)) {
          source.current = null;
          return null;
        }
        return current;
      });
    });
  }, [editor]);

  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      const data = event.data as {
        source?: string;
        kind?: string;
        phase?: string;
        x?: number;
        y?: number;
        open?: boolean;
        layers?: Record<string, boolean>;
        items?: LayerItem[];
      };
      if (!data || data.source !== "viksetu-map" || !editor) return;
      const frame = [...document.querySelectorAll("iframe")].find((item) => item.contentWindow === event.source);
      if (data.kind === "layers-drag" && frame) {
        source.current = event.source as Window;
        const screenX = Number(data.x ?? 0) - 18;
        const screenY = Number(data.y ?? 0) - 22;
        const page = editor.screenToPage({ x: screenX, y: screenY });
        setDock((current) => ({
          pageX: page.x,
          pageY: page.y,
          open: data.open ?? current?.open ?? true,
          dragging: data.phase !== "end",
          layers: data.layers ?? current?.layers ?? {},
          items: data.items?.length ? data.items : current?.items ?? [],
          mapShapeId: mapShapeForFrame(frame) ?? current?.mapShapeId ?? null,
        }));
      }
      if (data.kind === "state" && event.source === source.current && data.layers) {
        setDock((current) => (current ? { ...current, layers: data.layers ?? current.layers } : current));
      }
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [editor]);

  useEffect(() => {
    const move = (event: PointerEvent) => {
      if (!drag.current || !editor) return;
      const page = editor.screenToPage({ x: event.clientX, y: event.clientY });
      setDock((current) =>
        current
          ? {
              ...current,
              dragging: true,
              pageX: drag.current!.pageX + (page.x - drag.current!.startX),
              pageY: drag.current!.pageY + (page.y - drag.current!.startY),
            }
          : current
      );
    };
    const up = () => {
      drag.current = null;
      setDock((current) => (current ? { ...current, dragging: false } : current));
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
  }, [editor]);

  if (!dock || !editor) return null;
  const host = stage.current;
  if (!host) return null;

  const hostRect = host.getBoundingClientRect();
  const screen = editor.pageToScreen({ x: dock.pageX, y: dock.pageY });
  const left = screen.x - hostRect.left;
  const top = screen.y - hostRect.top;

  const toggle = (id: string) => {
    const visible = !dock.layers[id];
    source.current?.postMessage({ source: "viksetu-canvas", kind: "set-layer", layer: id, visible }, "*");
    setDock((current) => (current ? { ...current, layers: { ...current.layers, [id]: visible } } : current));
  };

  return createPortal(
    <div
      className={`layer-dock${dock.open ? "" : " is-collapsed"}${dock.dragging ? " is-dragging" : ""}`}
      style={{ left, top }}
    >
      <div className="layer-dock-head">
        <div
          className="layer-dock-handle"
          title="Drag anywhere on the canvas"
          onPointerDown={(event) => {
            if (event.button !== 0 || !editor) return;
            const page = editor.screenToPage({ x: event.clientX, y: event.clientY });
            drag.current = { pageX: dock.pageX, pageY: dock.pageY, startX: page.x, startY: page.y };
          }}
        >
          ⠿
        </div>
        <button type="button" onClick={() => setDock((current) => (current ? { ...current, open: !current.open } : current))}>
          <span>Map layers</span>
          <span>{Object.values(dock.layers).filter(Boolean).length}</span>
        </button>
      </div>
      {dock.open && (
        <ul>
          {dock.items.map((item) => (
            <li key={item.id}>
              <label>
                <input type="checkbox" checked={!!dock.layers[item.id]} onChange={() => toggle(item.id)} />
                <i style={{ background: item.color }} />
                {item.label}
              </label>
            </li>
          ))}
        </ul>
      )}
    </div>,
    host
  );
}
