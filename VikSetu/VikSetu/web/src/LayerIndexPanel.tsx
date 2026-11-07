import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import type { RegionsManifest } from "./api";

type Props = {
  open: boolean;
  onToggleOpen: () => void;
  layers: Record<string, boolean>;
  regions: RegionsManifest | null;
  layerIds: readonly string[];
  categoryColors: Record<string, string>;
  onToggleLayer: (id: string) => void;
  boundsRef: RefObject<HTMLElement | null>;
  allowDetach?: boolean;
  onPull?: (phase: "start" | "move" | "end", x: number, y: number) => void;
};

const DEFAULT = { x: 12, y: 12 };
const DRAG_THRESHOLD = 4;

export function LayerIndexPanel({
  open,
  onToggleOpen,
  layers,
  regions,
  layerIds,
  categoryColors,
  onToggleLayer,
  boundsRef,
  allowDetach = false,
  onPull,
}: Props) {
  const activeCount = Object.values(layers).filter(Boolean).length;
  const panelRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState(DEFAULT);
  const [isDragging, setIsDragging] = useState(false);
  const [handed, setHanded] = useState(false);
  const drag = useRef({
    active: false,
    pointerId: -1,
    startX: 0,
    startY: 0,
    originX: 0,
    originY: 0,
    moved: false,
    handed: false,
  });

  const clampPosition = useCallback((x: number, y: number) => {
    const bounds = boundsRef.current;
    const panel = panelRef.current;
    if (!bounds || !panel) return { x, y };
    const bw = bounds.clientWidth;
    const bh = bounds.clientHeight;
    const pw = panel.offsetWidth;
    const ph = panel.offsetHeight;
    return {
      x: Math.max(0, Math.min(x, bw - pw)),
      y: Math.max(0, Math.min(y, bh - ph)),
    };
  }, [boundsRef]);

  useEffect(() => {
    const bounds = boundsRef.current;
    if (!bounds) return;
    const ro = new ResizeObserver(() => {
      setPos((p) => clampPosition(p.x, p.y));
    });
    ro.observe(bounds);
    return () => ro.disconnect();
  }, [boundsRef, clampPosition]);

  const onDragPointerDown = (e: React.PointerEvent) => {
    if (e.button !== 0) return;
    e.preventDefault();
    drag.current = {
      active: true,
      pointerId: e.pointerId,
      startX: e.clientX,
      startY: e.clientY,
      originX: pos.x,
      originY: pos.y,
      moved: false,
      handed: false,
    };
    setHanded(false);
    setIsDragging(true);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
  };

  const onDragPointerMove = (e: React.PointerEvent) => {
    if (!drag.current.active || e.pointerId !== drag.current.pointerId) return;
    const dx = e.clientX - drag.current.startX;
    const dy = e.clientY - drag.current.startY;
    if (Math.abs(dx) > DRAG_THRESHOLD || Math.abs(dy) > DRAG_THRESHOLD) {
      drag.current.moved = true;
    }
    if (!drag.current.moved) return;
    const bounds = boundsRef.current?.getBoundingClientRect();
    const outside =
      allowDetach &&
      bounds &&
      (e.clientX < bounds.left || e.clientY < bounds.top || e.clientX > bounds.right || e.clientY > bounds.bottom);
    if (outside) {
      if (!drag.current.handed) {
        drag.current.handed = true;
        setHanded(true);
        onPull?.("start", e.clientX, e.clientY);
      } else {
        onPull?.("move", e.clientX, e.clientY);
      }
      return;
    }
    if (drag.current.handed) {
      onPull?.("move", e.clientX, e.clientY);
      return;
    }
    const next = clampPosition(drag.current.originX + dx, drag.current.originY + dy);
    setPos(next);
  };

  const onDragPointerUp = (e: React.PointerEvent) => {
    if (e.pointerId !== drag.current.pointerId) return;
    const wasHanded = drag.current.handed;
    drag.current.active = false;
    drag.current.handed = false;
    setIsDragging(false);
    if (wasHanded) onPull?.("end", e.clientX, e.clientY);
    try {
      (e.currentTarget as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  };

  const onHeaderClick = () => {
    if (drag.current.moved) {
      drag.current.moved = false;
      return;
    }
    onToggleOpen();
  };

  return (
    <div
      ref={panelRef}
      className={`layer-float ${open ? "layer-float--open" : "layer-float--collapsed"} ${
        isDragging ? "layer-float--dragging" : ""
      } ${handed ? "layer-float--handed" : ""}`}
      style={{ left: pos.x, top: pos.y }}
    >
      <div className="layer-float-head">
        <div
          className="layer-float-drag"
          title="Drag to move"
          onPointerDown={onDragPointerDown}
          onPointerMove={onDragPointerMove}
          onPointerUp={onDragPointerUp}
          onPointerCancel={onDragPointerUp}
        >
          ⠿
        </div>
        <button
          type="button"
          className="layer-float-toggle"
          onClick={onHeaderClick}
          aria-expanded={open}
        >
          <span className="layer-float-title">Map layers</span>
          <span className="layer-float-badge">{activeCount}</span>
          <span className="layer-float-chevron">{open ? "▾" : "▸"}</span>
        </button>
      </div>

      <div className="layer-float-body">
        <p className="layer-float-hint">
          {allowDetach ? "Drag ⠿ off the map · toggles still work" : "Drag ⠿ to move · toggle layers below"}
        </p>
        <label className="layer-row layer-row--anim">
          <input
            type="checkbox"
            checked={!!layers.taluka_regions}
            onChange={() => onToggleLayer("taluka_regions")}
          />
          <span className="dot dot--glow" style={{ background: "#94a3b8" }} />
          Taluka regions (8)
        </label>
        {layerIds.map((id, i) => (
          <label
            key={id}
            className="layer-row layer-row--anim"
            style={{ animationDelay: `${i * 40}ms` }}
          >
            <input type="checkbox" checked={!!layers[id]} onChange={() => onToggleLayer(id)} />
            <span className="dot dot--glow" style={{ background: categoryColors[id] }} />
            {id === "development"
              ? "Development / works"
              : regions?.layers[id]?.label ?? id}
          </label>
        ))}
      </div>
    </div>
  );
}
