import { useEffect, useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";
import { createShapeId, useEditor, type Editor, type TLShapeId } from "@tldraw/editor";
import {
  ArrowDownToolbarItem,
  ArrowLeftToolbarItem,
  ArrowRightToolbarItem,
  ArrowToolbarItem,
  ArrowUpToolbarItem,
  AssetToolbarItem,
  CheckBoxToolbarItem,
  CloudToolbarItem,
  DefaultToolbar,
  DiamondToolbarItem,
  DrawToolbarItem,
  EllipseToolbarItem,
  EraserToolbarItem,
  FrameToolbarItem,
  HandToolbarItem,
  HeartToolbarItem,
  HexagonToolbarItem,
  HighlightToolbarItem,
  LaserToolbarItem,
  LineToolbarItem,
  NoteToolbarItem,
  OvalToolbarItem,
  RectangleToolbarItem,
  RhombusToolbarItem,
  SelectToolbarItem,
  StarToolbarItem,
  TextToolbarItem,
  TriangleToolbarItem,
  XBoxToolbarItem,
} from "tldraw";
import { CHART_TYPE, DOC_TYPE, FILE_TYPE, SHEET_TYPE } from "./embedShapes";
import { MAP_TYPE } from "./MapShape";

type EmbedKind = "viksetu-map" | "viksetu-chart" | "viksetu-doc" | "viksetu-sheet" | "viksetu-file";

type EmbedItem = {
  label: string;
  hint: string;
  w: number;
  h: number;
  type: EmbedKind;
  props: Record<string, unknown>;
  preview: string;
};

const ITEMS: EmbedItem[] = [
  { label: "Map", hint: "Interactive Palghar map", w: 720, h: 480, type: MAP_TYPE, props: {}, preview: "map" },
  {
    label: "Bar chart",
    hint: "Columns from your data",
    w: 420,
    h: 280,
    type: CHART_TYPE,
    props: { title: "Bar chart", chart: "bar", labels: "[]", values: "[]" },
    preview: "bar",
  },
  {
    label: "Line chart",
    hint: "Trend over categories",
    w: 420,
    h: 280,
    type: CHART_TYPE,
    props: { title: "Line chart", chart: "line", labels: "[]", values: "[]" },
    preview: "line",
  },
  {
    label: "Pie chart",
    hint: "Share of a total",
    w: 420,
    h: 280,
    type: CHART_TYPE,
    props: { title: "Pie chart", chart: "pie", labels: "[]", values: "[]" },
    preview: "pie",
  },
  {
    label: "Markdown",
    hint: "Note the agent can edit",
    w: 380,
    h: 320,
    type: DOC_TYPE,
    props: { title: "Note", format: "md", body: "" },
    preview: "md",
  },
  {
    label: "Text",
    hint: "Plain text block",
    w: 380,
    h: 280,
    type: DOC_TYPE,
    props: { title: "Text", format: "text", body: "" },
    preview: "text",
  },
  {
    label: "Sheet",
    hint: "Editable cells",
    w: 520,
    h: 280,
    type: SHEET_TYPE,
    props: { title: "Sheet", columns: '["A","B"]', rows: '[["",""]]' },
    preview: "sheet",
  },
  {
    label: "File drop",
    hint: "Upload for the agent",
    w: 300,
    h: 220,
    type: FILE_TYPE,
    props: { name: "", fileId: "", preview: "" },
    preview: "file",
  },
];

type Ghost = { item: EmbedItem; x: number; y: number };

function EmbedPreview({ kind }: { kind: string }) {
  switch (kind) {
    case "map":
      return (
        <svg viewBox="0 0 64 44" aria-hidden="true">
          <rect x="1" y="1" width="62" height="42" rx="4" fill="#0f172a" stroke="#38bdf8" strokeWidth="1.5" />
          <path d="M8 30c8-10 14-4 20-12 8-10 16 2 24-6 4-3 8-2 12 0v16H8z" fill="#1e3a5f" />
          <circle cx="22" cy="18" r="2.5" fill="#f87171" />
          <circle cx="40" cy="24" r="2.5" fill="#a78bfa" />
        </svg>
      );
    case "bar":
      return (
        <svg viewBox="0 0 64 44" aria-hidden="true">
          <rect x="1" y="1" width="62" height="42" rx="4" fill="#0f172a" stroke="#64748b" strokeWidth="1.5" />
          <rect x="12" y="22" width="8" height="14" rx="1.5" fill="#38bdf8" />
          <rect x="24" y="14" width="8" height="22" rx="1.5" fill="#2563eb" />
          <rect x="36" y="18" width="8" height="18" rx="1.5" fill="#38bdf8" />
          <rect x="48" y="10" width="8" height="26" rx="1.5" fill="#2563eb" />
        </svg>
      );
    case "line":
      return (
        <svg viewBox="0 0 64 44" aria-hidden="true">
          <rect x="1" y="1" width="62" height="42" rx="4" fill="#0f172a" stroke="#64748b" strokeWidth="1.5" />
          <polyline points="10,32 22,20 34,26 46,12 54,16" fill="none" stroke="#38bdf8" strokeWidth="2.5" strokeLinecap="round" />
        </svg>
      );
    case "pie":
      return (
        <svg viewBox="0 0 64 44" aria-hidden="true">
          <rect x="1" y="1" width="62" height="42" rx="4" fill="#0f172a" stroke="#64748b" strokeWidth="1.5" />
          <circle cx="32" cy="22" r="14" fill="#1e293b" />
          <path d="M32 8a14 14 0 0 1 12.1 7H32V8z" fill="#38bdf8" />
          <path d="M44.1 15A14 14 0 0 1 32 36V22h12.1z" fill="#2563eb" />
        </svg>
      );
    case "md":
      return (
        <svg viewBox="0 0 64 44" aria-hidden="true">
          <rect x="1" y="1" width="62" height="42" rx="4" fill="#0f172a" stroke="#64748b" strokeWidth="1.5" />
          <rect x="10" y="10" width="28" height="3" rx="1" fill="#94a3b8" />
          <rect x="10" y="18" width="44" height="2.5" rx="1" fill="#64748b" />
          <rect x="10" y="24" width="36" height="2.5" rx="1" fill="#64748b" />
          <rect x="10" y="30" width="40" height="2.5" rx="1" fill="#64748b" />
        </svg>
      );
    case "text":
      return (
        <svg viewBox="0 0 64 44" aria-hidden="true">
          <rect x="1" y="1" width="62" height="42" rx="4" fill="#0f172a" stroke="#64748b" strokeWidth="1.5" />
          <text x="32" y="28" textAnchor="middle" fill="#e2e8f0" fontSize="16" fontFamily="system-ui,sans-serif" fontWeight="600">
            T
          </text>
        </svg>
      );
    case "sheet":
      return (
        <svg viewBox="0 0 64 44" aria-hidden="true">
          <rect x="1" y="1" width="62" height="42" rx="4" fill="#0f172a" stroke="#64748b" strokeWidth="1.5" />
          <line x1="10" y1="16" x2="54" y2="16" stroke="#334155" />
          <line x1="10" y1="24" x2="54" y2="24" stroke="#334155" />
          <line x1="10" y1="32" x2="54" y2="32" stroke="#334155" />
          <line x1="26" y1="10" x2="26" y2="34" stroke="#334155" />
          <line x1="40" y1="10" x2="40" y2="34" stroke="#334155" />
        </svg>
      );
    case "file":
      return (
        <svg viewBox="0 0 64 44" aria-hidden="true">
          <rect x="1" y="1" width="62" height="42" rx="4" fill="#0f172a" stroke="#64748b" strokeWidth="1.5" />
          <path d="M22 8h14l8 8v20H22V8z" fill="#1e293b" stroke="#38bdf8" strokeWidth="1.5" />
          <path d="M36 8v8h8" fill="none" stroke="#38bdf8" strokeWidth="1.5" />
          <path d="M26 26h16M26 32h12" stroke="#64748b" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      );
    default:
      return null;
  }
}

export function placeEmbedAt(editor: Editor, label: string, clientX: number, clientY: number) {
  const item = ITEMS.find((entry) => entry.label === label);
  if (!item) return false;
  return placeAt(editor, item, clientX, clientY);
}

function placeAt(editor: Editor, item: EmbedItem, clientX: number, clientY: number) {
  const bounds = editor.getContainer().getBoundingClientRect();
  const inside =
    clientX >= bounds.left && clientX <= bounds.right && clientY >= bounds.top && clientY <= bounds.bottom;
  if (!inside) return false;
  const page = editor.screenToPage({ x: clientX, y: clientY });
  const id: TLShapeId = createShapeId();
  editor.createShape({
    id,
    type: item.type,
    x: page.x - item.w / 2,
    y: page.y - item.h / 2,
    props: { w: item.w, h: item.h, ...item.props },
  });
  editor.setSelectedShapes([id]);
  return true;
}

function EmbedMenu() {
  const editor = useEditor();
  const buttonRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);
  const nativeDrag = useRef(false);
  const [open, setOpen] = useState(false);
  const [anchor, setAnchor] = useState<DOMRect | null>(null);
  const [ghost, setGhost] = useState<Ghost | null>(null);

  const clearGhost = () => setGhost(null);

  useEffect(() => {
    const stop = () => {
      draggingRef.current = false;
      nativeDrag.current = false;
      clearGhost();
    };
    window.addEventListener("dragend", stop);
    window.addEventListener("drop", stop);
    window.addEventListener("blur", stop);
    return () => {
      window.removeEventListener("dragend", stop);
      window.removeEventListener("drop", stop);
      window.removeEventListener("blur", stop);
    };
  }, []);

  useEffect(() => {
    if (!open) return;
    const update = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (rect) setAnchor(rect);
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open]);

  const beginDrag = (
    item: EmbedItem,
    event: { button: number; clientX: number; clientY: number; stopPropagation: () => void; preventDefault?: () => void }
  ) => {
    if (event.button !== 0 || draggingRef.current) return;
    draggingRef.current = true;
    nativeDrag.current = false;
    event.stopPropagation();
    event.preventDefault?.();
    const startX = event.clientX;
    const startY = event.clientY;
    let dragging = false;
    let finished = false;
    const finish = (ev: PointerEvent | MouseEvent, place: boolean) => {
      if (finished) return;
      finished = true;
      draggingRef.current = false;
      nativeDrag.current = false;
      window.removeEventListener("pointermove", move, true);
      window.removeEventListener("mousemove", move, true);
      window.removeEventListener("pointerup", finishPointer, true);
      window.removeEventListener("mouseup", finishMouse, true);
      window.removeEventListener("pointercancel", finishPointer, true);
      clearGhost();
      if (!place || !dragging || nativeDrag.current) return;
      const target = document.elementFromPoint(ev.clientX, ev.clientY);
      if (target?.closest(".embed-drawer")) return;
      placeAt(editor, item, ev.clientX, ev.clientY);
    };
    const move = (ev: PointerEvent | MouseEvent) => {
      if (!dragging && Math.hypot(ev.clientX - startX, ev.clientY - startY) < 6) return;
      dragging = true;
      setGhost({ item, x: ev.clientX, y: ev.clientY });
    };
    const finishPointer = (ev: PointerEvent) => finish(ev, true);
    const finishMouse = (ev: MouseEvent) => finish(ev, true);
    window.addEventListener("pointermove", move, true);
    window.addEventListener("mousemove", move, true);
    window.addEventListener("pointerup", finishPointer, true);
    window.addEventListener("mouseup", finishMouse, true);
    window.addEventListener("pointercancel", finishPointer, true);
  };

  const zoom = ghost ? editor.getZoomLevel() : 1;
  const panelStyle: CSSProperties | undefined = anchor
    ? {
        left: Math.max(8, Math.min(anchor.left, window.innerWidth - 280)),
        bottom: Math.max(8, window.innerHeight - anchor.top + 8),
        width: 272,
        maxHeight: Math.max(220, anchor.top - 16),
      }
    : undefined;

  return (
    <>
      <div
        ref={buttonRef}
        className="tlui-button tlui-button__tool embed-launch"
        role="button"
        tabIndex={0}
        aria-pressed={open}
        aria-label="Embeds"
        title="Embeds"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={() => {
          const rect = buttonRef.current?.getBoundingClientRect();
          if (rect) setAnchor(rect);
          setOpen((value) => !value);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            const rect = buttonRef.current?.getBoundingClientRect();
            if (rect) setAnchor(rect);
            setOpen((value) => !value);
          }
        }}
      >
        <svg className="embed-launch__icon" viewBox="0 0 18 18" aria-hidden="true">
          <rect x="2.25" y="2.25" width="13.5" height="13.5" rx="2.25" />
          <path d="M6 12.5V9.25M9 12.5V6.25M12 12.5V8" />
        </svg>
      </div>
      {open &&
        anchor &&
        createPortal(
          <aside className="embed-drawer" style={panelStyle} aria-label="Add an embedding">
            <header>
              <h2>Drag to place</h2>
              <button type="button" onClick={() => setOpen(false)} aria-label="Close embeddings">
                Close
              </button>
            </header>
            <ul>
              {ITEMS.map((item) => (
                <li key={item.label}>
                  <button
                    type="button"
                    draggable
                    onDragStart={(event) => {
                      nativeDrag.current = true;
                      event.dataTransfer.setData("text/plain", `viksetu-embed:${item.label}`);
                      event.dataTransfer.effectAllowed = "copy";
                    }}
                    onDragEnd={() => {
                      nativeDrag.current = false;
                      draggingRef.current = false;
                      clearGhost();
                    }}
                    onPointerDown={(event) => beginDrag(item, event)}
                  >
                    <span className="embed-card__thumb">
                      <EmbedPreview kind={item.preview} />
                    </span>
                    <span className="embed-card__copy">
                      <strong>{item.label}</strong>
                      <span>{item.hint}</span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </aside>,
          document.body
        )}
      {ghost &&
        createPortal(
          <div
            className="embed-ghost"
            style={{ left: ghost.x, top: ghost.y, width: ghost.item.w * zoom, height: ghost.item.h * zoom }}
          >
            <div className="embed-ghost__inner">
              <EmbedPreview kind={ghost.item.preview} />
              <span>{ghost.item.label}</span>
            </div>
          </div>,
          document.body
        )}
    </>
  );
}

export function VikToolbar() {
  return (
    <DefaultToolbar>
      <SelectToolbarItem />
      <EmbedMenu />
      <HandToolbarItem />
      <DrawToolbarItem />
      <EraserToolbarItem />
      <ArrowToolbarItem />
      <TextToolbarItem />
      <NoteToolbarItem />
      <AssetToolbarItem />
      <RectangleToolbarItem />
      <EllipseToolbarItem />
      <TriangleToolbarItem />
      <DiamondToolbarItem />
      <HexagonToolbarItem />
      <OvalToolbarItem />
      <RhombusToolbarItem />
      <StarToolbarItem />
      <CloudToolbarItem />
      <HeartToolbarItem />
      <XBoxToolbarItem />
      <CheckBoxToolbarItem />
      <ArrowLeftToolbarItem />
      <ArrowUpToolbarItem />
      <ArrowDownToolbarItem />
      <ArrowRightToolbarItem />
      <LineToolbarItem />
      <HighlightToolbarItem />
      <LaserToolbarItem />
      <FrameToolbarItem />
    </DefaultToolbar>
  );
}
