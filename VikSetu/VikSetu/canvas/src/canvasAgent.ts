import { createShapeId, toRichText, type TLShapeId } from "@tldraw/tlschema";
import type { Editor } from "@tldraw/editor";
import { getCursorPoint } from "./cursor";
import { CUSTOM_TYPE } from "./CustomShape";
import { CHART_TYPE, DOC_TYPE, FILE_TYPE, SHEET_TYPE } from "./embedShapes";
import { MAP_TYPE } from "./MapShape";

export type CanvasShape = {
  id: string;
  type: string;
  x: number;
  y: number;
  w: number;
  h: number;
  text: string;
  detail: string;
  selected: boolean;
  fileId?: string;
  fileKind?: string;
};

export type CanvasAction =
  | {
      op: "geo";
      text: string;
      geo?: string;
      x?: number;
      y?: number;
      w?: number;
      h?: number;
      color?: string;
    }
  | { op: "text"; text: string; x?: number; y?: number; color?: string }
  | { op: "arrow"; from: string; to: string }
  | { op: "map"; x?: number; y?: number; w?: number; h?: number }
  | {
      op: "chart";
      id?: string;
      title?: string;
      chart?: string;
      labels?: string[];
      values?: number[];
      x?: number;
      y?: number;
      w?: number;
      h?: number;
    }
  | {
      op: "doc";
      id?: string;
      title?: string;
      format?: string;
      body?: string;
      x?: number;
      y?: number;
      w?: number;
      h?: number;
    }
  | {
      op: "sheet";
      id?: string;
      title?: string;
      columns?: string[];
      rows?: (string | number)[][];
      x?: number;
      y?: number;
      w?: number;
      h?: number;
    }
  | { op: "file"; x?: number; y?: number; w?: number; h?: number }
  | {
      op: "embed";
      id?: string;
      title?: string;
      html?: string;
      data?: unknown;
      x?: number;
      y?: number;
      w?: number;
      h?: number;
    }
  | { op: "delete"; ids: string[] }
  | { op: "zoom" }
  | { op: "map-layer"; layer: string; visible: boolean }
  | { op: "map-focus"; pinId?: string; lng?: number; lat?: number; zoom?: number }
  | { op: "map-pin"; pinId: string; name?: string; description?: string; agent_summary?: string };

export type PythonNote = { ok?: boolean; stdout?: string; stderr?: string; code?: number; script?: string };

export type FileToolNote = {
  ok?: boolean;
  op?: string;
  mode?: string;
  path?: string;
  error?: string;
  text?: string;
  dump?: string;
  preview?: string;
};

export type SubagentNote = {
  ok?: boolean;
  provider?: string;
  model?: string;
  fileId?: string;
  question?: string;
  answer?: string;
  error?: string;
};

export type WebNote = {
  ok?: boolean;
  url?: string;
  title?: string;
  text?: string;
  error?: string;
};

export type AgentTurn = {
  reply: string;
  actions: CanvasAction[];
  fromModel?: boolean;
  thinking?: string;
  continue?: boolean;
  python?: PythonNote[];
  file_tools?: FileToolNote[];
  subagent?: SubagentNote[];
  web?: WebNote[];
};

const GEOS = new Set(["rectangle", "ellipse", "diamond", "triangle", "hexagon"]);
const COLORS = new Set([
  "black",
  "grey",
  "violet",
  "blue",
  "light-blue",
  "yellow",
  "orange",
  "green",
  "red",
]);

function plainText(shape: { props?: Record<string, unknown> }): string {
  const rich = shape.props?.richText as { content?: { content?: { text?: string }[] }[] } | undefined;
  if (!rich?.content) return "";
  const parts: string[] = [];
  for (const block of rich.content) {
    for (const node of block.content ?? []) {
      if (node.text) parts.push(node.text);
    }
  }
  return parts.join(" ").trim();
}

function clip(value: string, max = 700): string {
  const text = value.replace(/\s+/g, " ").trim();
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function shapeText(shape: { type: string; props: Record<string, unknown> }): string {
  if (shape.type === MAP_TYPE) return "Palghar map";
  if (shape.type === CHART_TYPE) return String(shape.props.title || "Chart");
  if (shape.type === DOC_TYPE) return String(shape.props.title || "Note");
  if (shape.type === SHEET_TYPE) return String(shape.props.title || "Sheet");
  if (shape.type === FILE_TYPE) return String(shape.props.name || "File drop");
  if (shape.type === CUSTOM_TYPE) return String(shape.props.title || "Embed");
  return plainText(shape);
}

function shapeDetail(shape: { type: string; props: Record<string, unknown> }): string {
  const props = shape.props;
  if (shape.type === CHART_TYPE) return clip(`${props.chart} labels ${props.labels} values ${props.values}`);
  if (shape.type === DOC_TYPE) return clip(String(props.body || ""));
  if (shape.type === SHEET_TYPE) return clip(`columns ${props.columns} rows ${props.rows}`, 900);
  if (shape.type === FILE_TYPE) return clip(`file ${props.fileId} kind ${props.kind ?? ""} ${props.preview}`);
  if (shape.type === MAP_TYPE) return "Live Palghar map";
  if (shape.type === CUSTOM_TYPE) return clip(`custom embed data ${props.data} html ${props.html}`, 2500);
  return "";
}

export function snapshotCanvas(editor: Editor): CanvasShape[] {
  const selected = new Set(editor.getSelectedShapeIds());
  return editor.getCurrentPageShapes().map((shape) => {
    const props = shape.props as Record<string, unknown>;
    const bounds = editor.getShapePageBounds(shape);
    const record = { type: shape.type, props };
    return {
      id: shape.id,
      type: shape.type,
      x: Math.round(bounds?.x ?? shape.x),
      y: Math.round(bounds?.y ?? shape.y),
      w: Math.round(bounds?.w ?? Number(props.w ?? 0)),
      h: Math.round(bounds?.h ?? Number(props.h ?? 0)),
      text: shapeText(record),
      detail: shapeDetail(record),
      selected: selected.has(shape.id),
      fileId: shape.type === FILE_TYPE ? String(props.fileId ?? "") : undefined,
      fileKind: shape.type === FILE_TYPE ? String(props.kind ?? "") : undefined,
    };
  });
}

function numeric(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  const text = String(value ?? "")
    .replace(/[₹,\s]/g, "")
    .replace(/(crore|cr|lakh|lac)$/i, "");
  const amount = Number(text);
  return Number.isFinite(amount) ? amount : 0;
}

function asList(value: unknown): unknown[] {
  if (Array.isArray(value)) return value;
  if (typeof value !== "string" || !value.trim()) return [];
  try {
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) return parsed;
  } catch {
    // Fall through to a comma or newline split.
  }
  return value
    .split(/[,|\n]/)
    .map((part) => part.trim())
    .filter(Boolean);
}

function chartSeries(action: CanvasAction): { labels: string[]; values: number[] } {
  const raw = action as CanvasAction & Record<string, unknown>;
  const bundled = asList(raw.series ?? raw.data ?? raw.points ?? raw.items);
  let labels = asList(raw.labels).map((item) => {
    if (item && typeof item === "object") {
      const row = item as Record<string, unknown>;
      return String(row.label ?? row.name ?? row.sector ?? row.category ?? "");
    }
    return String(item ?? "");
  });
  let values = asList(raw.values).map((item) => {
    if (item && typeof item === "object") {
      const row = item as Record<string, unknown>;
      return numeric(row.value ?? row.amount ?? row.y ?? row.actual_spend_inr ?? row.spend);
    }
    return numeric(item);
  });
  const bundledHasNumbers = bundled.some((item) => item && typeof item === "object");
  if (bundledHasNumbers && (!values.some((value) => value !== 0) || labels.length === 0)) {
    labels = bundled.map((item) => {
      const row = (item ?? {}) as Record<string, unknown>;
      return String(row.label ?? row.name ?? row.sector ?? row.category ?? "");
    });
    values = bundled.map((item) => {
      const row = (item ?? {}) as Record<string, unknown>;
      return numeric(row.value ?? row.amount ?? row.y ?? row.actual_spend_inr ?? row.spend);
    });
  }
  const count = Math.max(labels.length, values.length);
  return {
    labels: Array.from({ length: count }, (_, index) => labels[index] || String(index + 1)),
    values: Array.from({ length: count }, (_, index) => values[index] ?? 0),
  };
}

function resolveId(ref: string, created: TLShapeId[], existing: CanvasShape[]): TLShapeId | null {
  if (ref.startsWith("new:")) {
    const index = Number(ref.slice(4));
    return created[index] ?? null;
  }
  const byId = existing.find((shape) => shape.id === ref);
  if (byId) return byId.id as TLShapeId;
  const needle = ref.toLowerCase();
  const byText = existing.find((shape) => shape.text.toLowerCase() === needle);
  return (byText?.id as TLShapeId) ?? null;
}

export function ensureRequested(message: string, actions: CanvasAction[]): CanvasAction[] {
  const lower = message.toLowerCase();
  const updating = /\b(update|change|edit|fix|format|resize|move)\b/.test(lower);
  const placing = /\b(place|add|create|put|make|draw|embed|insert|another|new)\b/.test(lower);
  const asking = /^\s*(what|which|how|why|who|where|when|is|are|does|do|can you (tell|explain))\b/.test(lower);
  if (actions.some((action) => action.op === "embed")) return actions;
  if (updating && !placing) return actions;
  if (asking && !placing) return actions;
  if (!placing && !/\b(chart|graph|sheet|note)\b/.test(lower)) return actions;
  const next = [...actions];
  const want: { test: RegExp; action: CanvasAction }[] = [
    { test: /\b(chart|graph)\b/, action: { op: "chart", title: "Chart", chart: "bar", labels: [], values: [] } },
    { test: /\b(spreadsheet|sheet|table)\b/, action: { op: "sheet", title: "Sheet", columns: ["Item", "Value"], rows: [["", ""]] } },
    { test: /\b(markdown|\.md\b|\bnote\b|document)\b/, action: { op: "doc", title: "Note", format: "md", body: "" } },
    { test: /\b(file drop|file node)\b/, action: { op: "file" } },
  ];
  const satisfiedBy: Record<string, string[]> = {
    chart: ["chart", "embed"],
    sheet: ["sheet", "embed"],
    doc: ["doc", "text", "geo", "embed"],
    file: ["file"],
  };
  for (const item of want) {
    if (!item.test.test(lower)) continue;
    const accepted = satisfiedBy[item.action.op] ?? [item.action.op];
    if (next.some((action) => accepted.includes(action.op))) continue;
    next.push(item.action);
  }
  return next;
}

export function applyActions(
  editor: Editor,
  actions: CanvasAction[],
  existing: CanvasShape[],
  placedBefore = 0
): { created: string[]; placed: number } {
  const created: TLShapeId[] = [];
  const origin = getCursorPoint(editor);
  let placed = placedBefore;
  const mapOnPage = existing.find((shape) => shape.type === MAP_TYPE);
  let usedMapSide = false;
  const dropAt = (kind?: string) => {
    const beside =
      mapOnPage &&
      !usedMapSide &&
      (kind === "chart" || kind === "doc" || kind === "sheet" || kind === "embed");
    if (beside) {
      usedMapSide = true;
      placed += 1;
      return { x: mapOnPage.x + mapOnPage.w + 48, y: mapOnPage.y };
    }
    const point = { x: origin.x + placed * 320, y: origin.y + 28 + placed * 48 };
    placed += 1;
    return point;
  };
  editor.run(() => {
    for (const action of actions) {
      if (action.op === "geo") {
        const id = createShapeId();
        const geo = (GEOS.has(action.geo ?? "") ? action.geo : "rectangle") as
          | "rectangle"
          | "ellipse"
          | "diamond"
          | "triangle"
          | "hexagon";
        const color = (COLORS.has(action.color ?? "") ? action.color : "blue") as
          | "black"
          | "grey"
          | "violet"
          | "blue"
          | "light-blue"
          | "yellow"
          | "orange"
          | "green"
          | "red";
        const spot = dropAt("geo");
        editor.createShape({
          id,
          type: "geo",
          x: spot.x,
          y: spot.y,
          props: {
            geo,
            w: action.w ?? 200,
            h: action.h ?? 96,
            color,
            fill: "solid",
            richText: toRichText(action.text || "Untitled"),
          },
        });
        created.push(id);
      } else if (action.op === "text") {
        const id = createShapeId();
        const color = (COLORS.has(action.color ?? "") ? action.color : "black") as
          | "black"
          | "grey"
          | "violet"
          | "blue"
          | "light-blue"
          | "yellow"
          | "orange"
          | "green"
          | "red";
        const spot = dropAt("text");
        editor.createShape({
          id,
          type: "text",
          x: spot.x,
          y: spot.y,
          props: {
            color,
            richText: toRichText(action.text || ""),
          },
        });
        created.push(id);
      } else if (action.op === "map") {
        const spot = dropAt("map");
        const x = typeof action.x === "number" ? action.x : spot.x;
        const y = typeof action.y === "number" ? action.y : spot.y;
        const id = createShapeId();
        editor.createShape({
          id,
          type: MAP_TYPE,
          x,
          y,
          props: {
            w: action.w ?? 760,
            h: action.h ?? 520,
          },
        });
        created.push(id);
      } else if (action.op === "chart") {
        const series = chartSeries(action);
        const props = {
          w: Math.max(action.w ?? 480, 480),
          h: Math.max(action.h ?? 320, 320),
          title: action.title || "Chart",
          chart: action.chart === "line" || action.chart === "pie" ? action.chart : "bar",
          labels: JSON.stringify(series.labels),
          values: JSON.stringify(series.values),
        };
        const existingId = action.id ? resolveId(action.id, created, existing) : null;
        if (existingId) {
          editor.updateShape({ id: existingId, type: CHART_TYPE, props });
        } else {
          const spot = dropAt("chart");
          const id = createShapeId();
          editor.createShape({ id, type: CHART_TYPE, x: spot.x, y: spot.y, props });
          created.push(id);
        }
      } else if (action.op === "doc") {
        const props = {
          w: action.w ?? 400,
          h: action.h ?? 320,
          title: action.title || "Note",
          format: action.format === "text" ? "text" : "md",
          body: action.body || "",
        };
        const existingId = action.id ? resolveId(action.id, created, existing) : null;
        if (existingId) {
          editor.updateShape({ id: existingId, type: DOC_TYPE, props });
        } else {
          const spot = dropAt("doc");
          const id = createShapeId();
          editor.createShape({ id, type: DOC_TYPE, x: spot.x, y: spot.y, props });
          created.push(id);
        }
      } else if (action.op === "sheet") {
        const columns = (action.columns?.length ? action.columns : ["A", "B"]).map(String);
        const rows = (action.rows?.length ? action.rows : [columns.map(() => "")]).map((row) =>
          columns.map((_, index) => String(row?.[index] ?? ""))
        );
        const props = {
          w: action.w ?? 520,
          h: action.h ?? 280,
          title: action.title || "Sheet",
          columns: JSON.stringify(columns),
          rows: JSON.stringify(rows),
        };
        const existingId = action.id ? resolveId(action.id, created, existing) : null;
        if (existingId) {
          editor.updateShape({ id: existingId, type: SHEET_TYPE, props });
        } else {
          const spot = dropAt("sheet");
          const id = createShapeId();
          editor.createShape({ id, type: SHEET_TYPE, x: spot.x, y: spot.y, props });
          created.push(id);
        }
      } else if (action.op === "embed") {
        const dataText =
          action.data === undefined || action.data === null
            ? ""
            : typeof action.data === "string"
              ? action.data
              : JSON.stringify(action.data);
        const props = {
          w: Math.min(Math.max(action.w ?? 420, 280), 1200),
          h: Math.min(Math.max(action.h ?? 300, 200), 900),
          title: action.title || "Embed",
          html: String(action.html ?? "").slice(0, 60000),
          data: dataText.slice(0, 60000),
        };
        const existingId = action.id ? resolveId(action.id, created, existing) : null;
        if (existingId) {
          const patch: Record<string, unknown> = { ...props };
          if (action.w === undefined) delete patch.w;
          if (action.h === undefined) delete patch.h;
          if (action.title === undefined) delete patch.title;
          if (action.html === undefined) delete patch.html;
          if (action.data === undefined) delete patch.data;
          editor.updateShape({ id: existingId, type: CUSTOM_TYPE, props: patch });
        } else {
          const spot = dropAt("embed");
          const id = createShapeId();
          editor.createShape({ id, type: CUSTOM_TYPE, x: spot.x, y: spot.y, props });
          created.push(id);
        }
      } else if (action.op === "file") {
        const spot = dropAt("file");
        const id = createShapeId();
        editor.createShape({
          id,
          type: FILE_TYPE,
          x: spot.x,
          y: spot.y,
          props: { w: action.w ?? 300, h: action.h ?? 220, name: "", fileId: "", preview: "", uploadPct: 100 },
        });
        created.push(id);
      } else if (action.op === "arrow") {
        const from = resolveId(action.from, created, existing);
        const to = resolveId(action.to, created, existing);
        if (!from || !to) continue;
        const id = createShapeId();
        editor.createShape({ id, type: "arrow" });
        const binding = (terminal: "start" | "end", toId: TLShapeId) => ({
          type: "arrow" as const,
          fromId: id,
          toId,
          props: {
            terminal,
            normalizedAnchor: { x: 0.5, y: 0.5 },
            isExact: false,
            isPrecise: false,
            snap: "none" as const,
          },
        });
        editor.createBindings([binding("start", from), binding("end", to)]);
      } else if (action.op === "delete") {
        const ids = action.ids
          .map((ref) => resolveId(ref, created, existing))
          .filter((id): id is TLShapeId => Boolean(id));
        if (ids.length) editor.deleteShapes(ids);
      } else if (action.op === "zoom") {
        editor.zoomToFit({ animation: { duration: 280 } });
      }
    }
  });
  return {
    created: created.map((id) => `${editor.getShape(id)?.type ?? "shape"} ${id}`),
    placed,
  };
}

export function planLocally(message: string, canvas: CanvasShape[]): AgentTurn {
  const text = message.trim();
  const lower = text.toLowerCase();

  if (/clear|wipe|reset canvas/.test(lower)) {
    const wipeMap = /reset canvas|clear map|wipe/.test(lower);
    return {
      reply: wipeMap ? "Cleared the page, including the map." : "Cleared the other shapes. The Palghar map stayed.",
      actions: [
        {
          op: "delete",
          ids: canvas.filter((shape) => wipeMap || shape.type !== MAP_TYPE).map((shape) => shape.id),
        },
        { op: "zoom" },
      ],
    };
  }

  if (/\bmap\b|embed/.test(lower) && !/connect/.test(lower)) {
    const existing = canvas.find((shape) => shape.type === MAP_TYPE);
    if (existing) {
      return {
        reply: `The Palghar map is already on the canvas at (${existing.x}, ${existing.y}). Drag its title bar to move it. The map itself stays interactive.`,
        actions: [{ op: "zoom" }],
      };
    }
    return {
      reply: "Placed the live Palghar map. Drag the title bar to move it. The map itself pans, zooms, and opens pins.",
      actions: [{ op: "map", x: 80, y: 72, w: 760, h: 520 }, { op: "zoom" }],
    };
  }

  if (/pipeline|pdf|extract|workflow/.test(lower)) {
    const existing = canvas.find((shape) => shape.type === MAP_TYPE);
    return {
      reply: "Laid out a small VikSetu pipeline: source file, extract, then the live map.",
      actions: [
        { op: "geo", text: "PS PDF 2024-25", geo: "rectangle", x: 48, y: 80, color: "blue" },
        { op: "geo", text: "Extract spend", geo: "diamond", x: 48, y: 280, color: "violet" },
        ...(existing
          ? []
          : [{ op: "map" as const, x: 360, y: 48, w: 720, h: 480 }]),
        { op: "arrow", from: "new:0", to: "new:1" },
        { op: "arrow", from: "new:1", to: existing ? existing.id : "new:2" },
        { op: "zoom" },
      ],
    };
  }

  const connect = lower.match(/connect\s+(.+?)\s+to\s+(.+)/);
  if (connect) {
    return {
      reply: `Connecting “${connect[1].trim()}” to “${connect[2].trim()}”.`,
      actions: [
        { op: "arrow", from: connect[1].trim(), to: connect[2].trim() },
        { op: "zoom" },
      ],
    };
  }

  if (/chart|graph/.test(lower)) {
    return {
      reply: "Added a chart object. With the model connected it can fill the series from spend, pins, or a dropped file.",
      actions: [{ op: "chart", title: "Chart", chart: "bar", labels: [], values: [], x: 880, y: 360, w: 420, h: 280 }],
    };
  }

  if (/spreadsheet|sheet|\btable\b/.test(lower)) {
    return {
      reply: "Added a sheet. The agent can read and replace its cells.",
      actions: [{ op: "sheet", title: "Sheet", columns: ["Item", "Value"], rows: [["", ""]], x: 880, y: 360 }],
    };
  }

  if (/markdown|\.md\b|\bnote\b|document/.test(lower)) {
    return {
      reply: "Added a note on the canvas.",
      actions: [{ op: "doc", title: "Note", format: "md", body: "", x: 880, y: 360 }],
    };
  }

  if (/drop file|file node|file drop/.test(lower)) {
    return {
      reply: "Added a file drop. Put a file on it and I can read it from the workspace.",
      actions: [{ op: "file", x: 880, y: 360 }],
    };
  }

  if (/zoom|fit/.test(lower)) {
    return { reply: "Framed everything on the page.", actions: [{ op: "zoom" }] };
  }

  const label = text.replace(/^(add|create|draw|put)\s+/i, "").trim() || "Note";
  const offset = canvas.length * 36;
  return {
    reply: `Added “${label}” on the canvas.`,
    actions: [
      {
        op: "geo",
        text: label,
        geo: "rectangle",
        x: 120 + offset,
        y: 140 + (offset % 180),
        color: "light-blue",
      },
      { op: "zoom" },
    ],
  };
}
