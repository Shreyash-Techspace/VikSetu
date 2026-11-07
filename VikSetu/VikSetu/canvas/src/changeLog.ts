import { useSyncExternalStore } from "react";
import type { Editor, TLShape } from "tldraw";
import { MAP_TYPE } from "./MapShape";

export type ChangeEntry = {
  id: number;
  at: string;
  kind: "create" | "move" | "resize" | "delete" | "pin" | "point" | "view" | "layer";
  object: string;
  shapeId: string;
  x: number;
  y: number;
  w?: number;
  h?: number;
  lng?: number;
  lat?: number;
  note: string;
};

type ShapeRec = {
  id: string;
  typeName: string;
  type: string;
  x: number;
  y: number;
  props?: {
    w?: number;
    h?: number;
    richText?: { content?: { content?: { text?: string }[] }[] };
  };
};

type Box = { x: number; y: number; w: number; h: number };

let seq = 0;
let entries: ChangeEntry[] = [];
const listeners = new Set<() => void>();
const pending = new Map<string, { first: Box; latest: ShapeRec }>();
let flushTimer = 0;
let activeEditor: Editor | null = null;
let messageListening = false;
let lastView = "";

function clock() {
  return new Date().toLocaleTimeString("en-IN", { hour12: false });
}

function emit(entry: Omit<ChangeEntry, "id" | "at">) {
  entries = [...entries, { ...entry, id: ++seq, at: clock() }].slice(-80);
  listeners.forEach((listener) => listener());
}

export function getChangeLog(): ChangeEntry[] {
  return entries;
}

export function useChangeLog(): ChangeEntry[] {
  return useSyncExternalStore(
    (onStoreChange) => {
      listeners.add(onStoreChange);
      return () => listeners.delete(onStoreChange);
    },
    getChangeLog,
    getChangeLog
  );
}

function richText(shape: ShapeRec): string {
  const blocks = shape.props?.richText?.content ?? [];
  const parts: string[] = [];
  for (const block of blocks) {
    for (const node of block.content ?? []) {
      if (node.text) parts.push(node.text);
    }
  }
  return parts.join(" ").trim();
}

function objectName(shape: ShapeRec): string {
  if (shape.type === MAP_TYPE) return "Palghar map";
  return richText(shape) || shape.type;
}

function boxOf(shape: ShapeRec): Box {
  return {
    x: Math.round(shape.x),
    y: Math.round(shape.y),
    w: Math.round(Number(shape.props?.w ?? 0)),
    h: Math.round(Number(shape.props?.h ?? 0)),
  };
}

function sameBox(a: Box, b: Box) {
  return a.x === b.x && a.y === b.y && a.w === b.w && a.h === b.h;
}

function flushPending() {
  flushTimer = 0;
  for (const [id, change] of pending) {
    const next = boxOf(change.latest);
    if (sameBox(change.first, next)) continue;
    const moved = change.first.x !== next.x || change.first.y !== next.y;
    const resized = change.first.w !== next.w || change.first.h !== next.h;
    emit({
      kind: moved ? "move" : "resize",
      object: objectName(change.latest),
      shapeId: id,
      x: next.x,
      y: next.y,
      w: next.w || undefined,
      h: next.h || undefined,
      note: `from (${change.first.x}, ${change.first.y}) to (${next.x}, ${next.y})${
        resized ? `, size ${next.w}×${next.h}` : ""
      }`,
    });
  }
  pending.clear();
}

function scheduleFlush() {
  window.clearTimeout(flushTimer);
  flushTimer = window.setTimeout(flushPending, 400);
}

function mapObject(editor: Editor | null): TLShape | null {
  if (!editor) return null;
  const editing = editor.getEditingShape();
  if (editing?.type === MAP_TYPE) return editing;
  return editor.getCurrentPageShapes().find((shape) => shape.type === MAP_TYPE) ?? null;
}

function onMapMessage(event: MessageEvent) {
  const data = event.data as {
    source?: string;
    kind?: string;
    name?: string;
    pinId?: string;
    layer?: string;
    visible?: boolean;
    lng?: number;
    lat?: number;
    zoom?: number;
  };
  if (!data || data.source !== "viksetu-map") return;
  const shape = mapObject(activeEditor);
  const pageX = Math.round(shape?.x ?? 0);
  const pageY = Math.round(shape?.y ?? 0);
  const shapeId = shape?.id ?? "";

  if (data.kind === "pin") {
    emit({
      kind: "pin",
      object: data.name || data.pinId || "Pin",
      shapeId,
      x: pageX,
      y: pageY,
      lng: data.lng,
      lat: data.lat,
      note: `${data.layer ?? "pin"} ${data.pinId ?? ""} on Palghar map at page (${pageX}, ${pageY})`.trim(),
    });
    return;
  }

  if (data.kind === "point" && data.lng != null && data.lat != null) {
    emit({
      kind: "point",
      object: "Palghar map",
      shapeId,
      x: pageX,
      y: pageY,
      lng: data.lng,
      lat: data.lat,
      note: `clicked ${data.lng.toFixed(5)}, ${data.lat.toFixed(5)} on Palghar map at page (${pageX}, ${pageY})`,
    });
    return;
  }

  if (data.kind === "view" && data.lng != null && data.lat != null) {
    const key = `${data.lng.toFixed(3)},${data.lat.toFixed(3)},${Number(data.zoom ?? 0).toFixed(1)}`;
    if (key === lastView) return;
    lastView = key;
    emit({
      kind: "view",
      object: "Palghar map",
      shapeId,
      x: pageX,
      y: pageY,
      lng: data.lng,
      lat: data.lat,
      note: `view ${data.lng.toFixed(5)}, ${data.lat.toFixed(5)} zoom ${data.zoom ?? "?"} · object page (${pageX}, ${pageY})`,
    });
    return;
  }

  if (data.kind === "layer") {
    emit({
      kind: "layer",
      object: data.layer || "layer",
      shapeId,
      x: pageX,
      y: pageY,
      note: `${data.layer} ${data.visible ? "shown" : "hidden"} on Palghar map at page (${pageX}, ${pageY})`,
    });
  }
}

const watched = new WeakSet<Editor>();

export function watchCanvas(editor: Editor) {
  activeEditor = editor;
  if (!messageListening) {
    messageListening = true;
    window.addEventListener("message", onMapMessage);
  }
  if (watched.has(editor)) return;
  watched.add(editor);
  editor.store.listen(
    (entry) => {
      const { added, updated, removed } = entry.changes;
      for (const record of Object.values(added)) {
        if (record.typeName !== "shape") continue;
        const shape = record as unknown as ShapeRec;
        const box = boxOf(shape);
        emit({
          kind: "create",
          object: objectName(shape),
          shapeId: shape.id,
          x: box.x,
          y: box.y,
          w: box.w || undefined,
          h: box.h || undefined,
          note: `created at (${box.x}, ${box.y})${box.w ? `, ${box.w}×${box.h}` : ""}`,
        });
      }
      for (const pair of Object.values(updated)) {
        const [from, to] = pair as unknown as [ShapeRec, ShapeRec];
        if (to.typeName !== "shape") continue;
        const before = boxOf(from);
        const after = boxOf(to);
        if (sameBox(before, after)) continue;
        const current = pending.get(to.id);
        pending.set(to.id, { first: current?.first ?? before, latest: to });
        scheduleFlush();
      }
      for (const record of Object.values(removed)) {
        if (record.typeName !== "shape") continue;
        const shape = record as unknown as ShapeRec;
        pending.delete(shape.id);
        const box = boxOf(shape);
        emit({
          kind: "delete",
          object: objectName(shape),
          shapeId: shape.id,
          x: box.x,
          y: box.y,
          note: `removed from (${box.x}, ${box.y})`,
        });
      }
    },
    { source: "user", scope: "document" }
  );
}
