import {
  useEffect,
  useId,
  useState,
  type DragEvent as ReactDragEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import {
  BaseBoxShapeUtil,
  HTMLContainer,
  T,
  stopEventPropagation,
  type Editor,
  type TLShape,
  type TLShapeId,
  type TLShapePartial,
} from "tldraw";

export const CHART_TYPE = "viksetu-chart";
export const DOC_TYPE = "viksetu-doc";
export const SHEET_TYPE = "viksetu-sheet";
export const FILE_TYPE = "viksetu-file";

declare module "@tldraw/tlschema" {
  interface TLGlobalShapePropsMap {
    "viksetu-chart": { w: number; h: number; title: string; chart: string; labels: string; values: string };
    "viksetu-doc": { w: number; h: number; title: string; format: string; body: string };
    "viksetu-sheet": { w: number; h: number; title: string; columns: string; rows: string };
    "viksetu-file": { w: number; h: number; name: string; fileId: string; preview: string; uploadPct: number; kind: string };
  }
}

type ChartShape = TLShape<typeof CHART_TYPE>;
type DocShape = TLShape<typeof DOC_TYPE>;
type SheetShape = TLShape<typeof SHEET_TYPE>;
type FileShape = TLShape<typeof FILE_TYPE>;

export function useAccelHeld() {
  const [held, setHeld] = useState(false);
  useEffect(() => {
    const sync = (event: KeyboardEvent) => setHeld(event.ctrlKey || event.metaKey);
    const clear = () => setHeld(false);
    window.addEventListener("keydown", sync);
    window.addEventListener("keyup", sync);
    window.addEventListener("blur", clear);
    return () => {
      window.removeEventListener("keydown", sync);
      window.removeEventListener("keyup", sync);
      window.removeEventListener("blur", clear);
    };
  }, []);
  return held;
}

export function keepInteractive(event: ReactPointerEvent) {
  if (event.ctrlKey || event.metaKey) return;
  stopEventPropagation(event);
}

export function startShapeDrag(
  editor: Editor,
  shape: { id: TLShapeId; type: string; x: number; y: number },
  event: ReactPointerEvent<HTMLElement>
) {
  if (event.button !== 0 || event.ctrlKey || event.metaKey) return;
  stopEventPropagation(event);
  event.preventDefault();
  const selected = editor.getSelectedShapeIds();
  const group = selected.includes(shape.id) && selected.length > 1;
  const moving = (group ? selected : [shape.id])
    .map((id) => editor.getShape(id))
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
    .map((item) => ({ id: item.id, type: item.type, x: item.x, y: item.y }));
  if (!group) editor.setSelectedShapes([shape.id]);
  const origin = editor.screenToPage({ x: event.clientX, y: event.clientY });
  const move = (ev: PointerEvent | MouseEvent) => {
    const page = editor.screenToPage({ x: ev.clientX, y: ev.clientY });
    const dx = page.x - origin.x;
    const dy = page.y - origin.y;
    editor.updateShapes(
      moving.map((item) => ({
        id: item.id,
        type: item.type,
        x: item.x + dx,
        y: item.y + dy,
      })) as TLShapePartial[]
    );
  };
  const up = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", up);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", up);
}

function parseList(raw: string): string[] {
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value) ? value.map((item) => String(item)) : [];
  } catch {
    return [];
  }
}

function parseNumbers(raw: string): number[] {
  try {
    const value = JSON.parse(raw);
    return Array.isArray(value) ? value.map((item) => Number(item) || 0) : [];
  } catch {
    return [];
  }
}

function parseRows(raw: string): string[][] {
  try {
    const value = JSON.parse(raw);
    if (!Array.isArray(value)) return [];
    return value.map((row) => (Array.isArray(row) ? row.map((cell) => String(cell ?? "")) : []));
  } catch {
    return [];
  }
}

function formatTick(value: number): string {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  const compact = (amount: number) => String(Math.round(amount * 10) / 10);
  if (abs >= 1e7) return `${sign}${compact(abs / 1e7)} Cr`;
  if (abs >= 1e5) return `${sign}${compact(abs / 1e5)} L`;
  if (abs >= 1000) return `${sign}${compact(abs / 1000)}k`;
  if (Number.isInteger(value)) return String(value);
  return `${sign}${compact(abs)}`;
}

function axisTop(max: number): number {
  if (!(max > 0)) return 1;
  const power = 10 ** Math.floor(Math.log10(max));
  const fraction = max / power;
  const nice = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
  return nice * power;
}

function ChartGraphic({ chart, labels, values }: { chart: string; labels: string[]; values: number[] }) {
  const fillId = `vik-bar-${useId().replace(/:/g, "")}`;
  if (!values.length) return <p className="vik-empty">No series yet. Ask the agent to chart data.</p>;
  if (chart === "pie") {
    let cursor = 0;
    const total = values.reduce((sum, value) => sum + Math.max(value, 0), 0) || 1;
    const colors = ["#38bdf8", "#a78bfa", "#34d399", "#fbbf24", "#fb7185", "#94a3b8"];
    const stops = values
      .map((value, index) => {
        const start = cursor;
        cursor += (Math.max(value, 0) / total) * 100;
        return `${colors[index % colors.length]} ${start}% ${cursor}%`;
      })
      .join(", ");
    return (
      <div className="vik-pie-row">
        <div className="vik-pie" style={{ background: `conic-gradient(${stops})` }} />
        <ul>
          {labels.map((label, index) => (
            <li key={label + index}>
              {label} · {values[index] ?? 0}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  const width = 640;
  const height = 400;
  const left = 68;
  const right = 16;
  const top = 16;
  const bottom = 108;
  const plotW = width - left - right;
  const plotH = height - top - bottom;
  const scaleMax = axisTop(Math.max(...values, 0));
  const ticks = [0, 1, 2, 3, 4].map((step) => (scaleMax * step) / 4);
  const baseline = top + plotH;
  const yOf = (value: number) => baseline - (Math.max(value, 0) / scaleMax) * plotH;
  const slot = plotW / Math.max(values.length, 1);

  return (
    <svg className="vik-chart-svg" viewBox={`0 0 ${width} ${height}`} role="img">
      <defs>
        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7dd3fc" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
      </defs>
      {ticks.map((tick) => {
        const y = yOf(tick);
        return (
          <g key={tick}>
            {tick > 0 && <line className="vik-chart-grid" x1={left} x2={left + plotW} y1={y} y2={y} />}
            <text className="vik-chart-tick" x={left - 8} y={y + 4} textAnchor="end">
              {formatTick(tick)}
            </text>
          </g>
        );
      })}
      <line className="vik-chart-axis" x1={left} y1={top} x2={left} y2={baseline} />
      <line className="vik-chart-axis" x1={left} y1={baseline} x2={left + plotW} y2={baseline} />
      {chart === "line" ? (
        <polyline
          fill="none"
          stroke="#38bdf8"
          strokeWidth="2.5"
          strokeLinejoin="round"
          strokeLinecap="round"
          points={values
            .map((value, index) => `${left + slot * index + slot / 2},${yOf(value)}`)
            .join(" ")}
        />
      ) : (
        values.map((value, index) => {
          const barW = Math.min(42, slot * 0.62);
          const x = left + slot * index + (slot - barW) / 2;
          const y = yOf(value);
          return (
            <rect
              key={index}
              x={x}
              y={y}
              width={barW}
              height={Math.max(baseline - y, value > 0 ? 1.5 : 0)}
              rx="3"
              fill={`url(#${fillId})`}
            />
          );
        })
      )}
      {values.map((_, index) => {
        const x = left + slot * index + slot / 2;
        const label = labels[index] ?? String(index + 1);
        const y = baseline + 16;
        return (
          <text
            key={`${label}-${index}`}
            className="vik-chart-label"
            x={x}
            y={y}
            textAnchor="end"
            transform={`rotate(-42 ${x} ${y})`}
          >
            <title>{label}</title>
            {label}
          </text>
        );
      })}
    </svg>
  );
}

function DocBody({ body, onChange }: { body: string; onChange: (value: string) => void }) {
  return (
    <textarea
      className="vik-doc-edit"
      value={body}
      placeholder="Write here. The agent can edit this too."
      onPointerDown={stopEventPropagation}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

function ChartDataEditor({
  labels,
  values,
  onChange,
}: {
  labels: string[];
  values: number[];
  onChange: (labels: string[], values: number[]) => void;
}) {
  const count = Math.max(labels.length, values.length, 1);
  const rows = Array.from({ length: count }, (_, index) => ({
    label: labels[index] ?? "",
    value: values[index] ?? 0,
  }));
  const write = (next: { label: string; value: number }[]) => {
    onChange(
      next.map((row) => row.label),
      next.map((row) => row.value)
    );
  };
  return (
    <div className="vik-chart-edit">
      {rows.map((row, index) => (
        <label key={index}>
          <input
            value={row.label}
            aria-label={`Label ${index + 1}`}
            onPointerDown={stopEventPropagation}
            onChange={(event) => {
              const next = rows.slice();
              next[index] = { ...row, label: event.target.value };
              write(next);
            }}
          />
          <input
            value={String(row.value)}
            aria-label={`Value ${index + 1}`}
            inputMode="decimal"
            onPointerDown={stopEventPropagation}
            onChange={(event) => {
              const next = rows.slice();
              next[index] = { ...row, value: Number(event.target.value) || 0 };
              write(next);
            }}
          />
        </label>
      ))}
      <button type="button" onPointerDown={stopEventPropagation} onClick={() => write([...rows, { label: "", value: 0 }])}>
        Add row
      </button>
    </div>
  );
}

export function Frame({
  title,
  hint,
  onDrag,
  onRename,
  extra,
  className,
  onDragOver,
  onDrop,
  children,
}: {
  title: string;
  hint: string;
  onDrag: (event: ReactPointerEvent<HTMLDivElement>) => void;
  onRename?: (value: string) => void;
  extra?: ReactNode;
  className?: string;
  onDragOver?: (event: ReactDragEvent<HTMLDivElement>) => void;
  onDrop?: (event: ReactDragEvent<HTMLDivElement>) => void;
  children: React.ReactNode;
}) {
  const selecting = useAccelHeld();
  return (
    <div
      className={`vik-embed-frame${selecting ? " is-selecting" : ""}${className ? ` ${className}` : ""}`}
      onDragOver={onDragOver}
      onDrop={onDrop}
    >
      <div className="vik-map-bar" onPointerDown={onDrag}>
        {onRename ? (
          <input
            className="vik-title-input"
            value={title}
            aria-label="Title"
            onPointerDown={stopEventPropagation}
            onChange={(event) => onRename(event.target.value)}
          />
        ) : (
          <span>{title}</span>
        )}
        <span className="vik-map-hint">{hint}</span>
        {extra}
      </div>
      <div className="vik-embed-body" onPointerDown={keepInteractive}>
        {children}
      </div>
    </div>
  );
}

export class ChartShapeUtil extends BaseBoxShapeUtil<ChartShape> {
  static override type = CHART_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
    title: T.string,
    chart: T.string,
    labels: T.string,
    values: T.string,
  };

  override getDefaultProps(): ChartShape["props"] {
    return { w: 420, h: 280, title: "Chart", chart: "bar", labels: "[]", values: "[]" };
  }

  override getText(shape: ChartShape) {
    const labels = parseList(shape.props.labels);
    const values = parseNumbers(shape.props.values);
    const rows = labels.map((label, index) => `${label}\t${values[index] ?? ""}`);
    return [shape.props.title, ...rows].filter((line) => line.trim()).join("\n") || "Chart";
  }

  override getIndicatorPath(shape: ChartShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: ChartShape) {
    return <ChartBody editor={this.editor} shape={shape} />;
  }
}

function ChartBody({ editor, shape }: { editor: Editor; shape: ChartShape }) {
  const [editing, setEditing] = useState(false);
  const labels = parseList(shape.props.labels);
  const values = parseNumbers(shape.props.values);
  return (
    <HTMLContainer>
      <Frame
        title={shape.props.title || "Chart"}
        hint={shape.props.chart}
        onDrag={(event) => startShapeDrag(editor, shape, event)}
        onRename={(title) => editor.updateShape({ id: shape.id, type: CHART_TYPE, props: { title } })}
        extra={
          <button
            type="button"
            className="vik-edit-toggle"
            onPointerDown={stopEventPropagation}
            onClick={() => setEditing((value) => !value)}
          >
            {editing ? "Chart" : "Edit"}
          </button>
        }
      >
        {editing ? (
          <ChartDataEditor
            labels={labels}
            values={values}
            onChange={(nextLabels, nextValues) =>
              editor.updateShape({
                id: shape.id,
                type: CHART_TYPE,
                props: { labels: JSON.stringify(nextLabels), values: JSON.stringify(nextValues) },
              })
            }
          />
        ) : (
          <ChartGraphic chart={shape.props.chart} labels={labels} values={values} />
        )}
      </Frame>
    </HTMLContainer>
  );
}

export class DocShapeUtil extends BaseBoxShapeUtil<DocShape> {
  static override type = DOC_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
    title: T.string,
    format: T.string,
    body: T.string,
  };

  override getDefaultProps(): DocShape["props"] {
    return { w: 380, h: 320, title: "Note", format: "md", body: "" };
  }

  override getText(shape: DocShape) {
    return [shape.props.title, shape.props.body].filter((line) => line.trim()).join("\n\n") || "Note";
  }

  override getIndicatorPath(shape: DocShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: DocShape) {
    const editor = this.editor;
    return (
      <HTMLContainer>
        <Frame
          title={shape.props.title || "Note"}
          hint={shape.props.format === "md" ? "markdown" : "text"}
          onDrag={(event) => startShapeDrag(editor, shape, event)}
          onRename={(title) => editor.updateShape({ id: shape.id, type: DOC_TYPE, props: { title } })}
        >
          <DocBody
            body={shape.props.body}
            onChange={(body) => editor.updateShape({ id: shape.id, type: DOC_TYPE, props: { body } })}
          />
        </Frame>
      </HTMLContainer>
    );
  }
}

export class SheetShapeUtil extends BaseBoxShapeUtil<SheetShape> {
  static override type = SHEET_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
    title: T.string,
    columns: T.string,
    rows: T.string,
  };

  override getDefaultProps(): SheetShape["props"] {
    return { w: 520, h: 280, title: "Sheet", columns: '["A","B"]', rows: '[["",""]]' };
  }

  override getText(shape: SheetShape) {
    const columns = parseList(shape.props.columns);
    const rows = parseRows(shape.props.rows);
    const lines = [columns.join("\t"), ...rows.map((row) => row.join("\t"))].filter((line) => line.trim());
    return [shape.props.title, ...lines].filter((line) => line.trim()).join("\n") || "Sheet";
  }

  override getIndicatorPath(shape: SheetShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: SheetShape) {
    const editor = this.editor;
    const columns = parseList(shape.props.columns);
    const rows = parseRows(shape.props.rows);
    const write = (nextColumns: string[], nextRows: string[][]) => {
      editor.updateShape({
        id: shape.id,
        type: SHEET_TYPE,
        props: { ...shape.props, columns: JSON.stringify(nextColumns), rows: JSON.stringify(nextRows) },
      });
    };
    return (
      <HTMLContainer>
        <Frame
          title={shape.props.title || "Sheet"}
          hint="sheet"
          onDrag={(event) => startShapeDrag(editor, shape, event)}
          onRename={(title) => editor.updateShape({ id: shape.id, type: SHEET_TYPE, props: { title } })}
        >
          <div className="vik-sheet-wrap">
            <table className="vik-sheet">
              <thead>
                <tr>
                  {columns.map((column, index) => (
                    <th key={index}>
                      <input
                        value={column}
                        onPointerDown={stopEventPropagation}
                        onChange={(event) => {
                          const next = columns.slice();
                          next[index] = event.target.value;
                          write(next, rows);
                        }}
                      />
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, rowIndex) => (
                  <tr key={rowIndex}>
                    {columns.map((_, columnIndex) => (
                      <td key={columnIndex}>
                        <input
                          value={row[columnIndex] ?? ""}
                          onPointerDown={stopEventPropagation}
                          onChange={(event) => {
                            const next = rows.map((cells) => cells.slice());
                            next[rowIndex][columnIndex] = event.target.value;
                            write(columns, next);
                          }}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Frame>
      </HTMLContainer>
    );
  }
}

async function uploadFile(file: File): Promise<{ fileId: string; name: string; preview: string; kind?: string }> {
  return uploadFileWithProgress(file, () => {});
}

export function uploadFileWithProgress(
  file: File,
  onProgress: (pct: number) => void
): Promise<{ fileId: string; name: string; preview: string; kind?: string }> {
  return new Promise((resolve, reject) => {
    void (async () => {
      try {
        onProgress(2);
        const bytes = new Uint8Array(await file.arrayBuffer());
        onProgress(8);
        let binary = "";
        const chunk = 0x8000;
        for (let index = 0; index < bytes.length; index += chunk) {
          binary += String.fromCharCode(...bytes.subarray(index, index + chunk));
        }
        onProgress(12);
        const body = JSON.stringify({ name: file.name, data_b64: btoa(binary) });
        const xhr = new XMLHttpRequest();
        xhr.upload.onprogress = (event) => {
          if (!event.lengthComputable) return;
          onProgress(12 + (event.loaded / event.total) * 86);
        };
        xhr.onerror = () => reject(new Error("Upload failed."));
        xhr.onload = () => {
          if (xhr.status < 200 || xhr.status >= 300) {
            reject(new Error(xhr.responseText || `Upload failed (${xhr.status}).`));
            return;
          }
          try {
            onProgress(100);
            resolve(JSON.parse(xhr.responseText));
          } catch {
            reject(new Error("Upload returned invalid JSON."));
          }
        };
        xhr.open("POST", "/api/canvas/files");
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(body);
      } catch (error) {
        reject(error);
      }
    })();
  });
}

function UploadRing({ pct }: { pct: number }) {
  const safe = Math.max(0, Math.min(100, pct));
  const radius = 36;
  const length = 2 * Math.PI * radius;
  return (
    <div className="vik-upload-ring" role="progressbar" aria-valuenow={safe} aria-valuemin={0} aria-valuemax={100}>
      <svg viewBox="0 0 96 96" aria-hidden="true">
        <circle cx="48" cy="48" r={radius} className="vik-upload-ring__track" />
        <circle
          cx="48"
          cy="48"
          r={radius}
          className="vik-upload-ring__bar"
          strokeDasharray={length}
          strokeDashoffset={length * (1 - safe / 100)}
        />
      </svg>
      <span>{safe}%</span>
    </div>
  );
}

export class FileShapeUtil extends BaseBoxShapeUtil<FileShape> {
  static override type = FILE_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
    name: T.string,
    fileId: T.string,
    preview: T.string,
    uploadPct: T.number,
    kind: T.string,
  };

  override getDefaultProps(): FileShape["props"] {
    return { w: 300, h: 220, name: "", fileId: "", preview: "", uploadPct: 100, kind: "" };
  }

  override getText(shape: FileShape) {
    return shape.props.name.trim() || shape.props.preview.trim() || "File";
  }

  override getIndicatorPath(shape: FileShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: FileShape) {
    const editor = this.editor;
    const onDrop = (event: ReactDragEvent<HTMLDivElement>) => {
      const file = event.dataTransfer.files?.[0];
      if (!file) return;
      event.preventDefault();
      event.stopPropagation();
      void import("./fileDrop").then((module) =>
        module.placeDroppedFile(editor, file, { x: shape.x, y: shape.y }, shape.id)
      );
    };
    return (
      <HTMLContainer>
        <Frame
          className="vik-file-frame"
          title={shape.props.name || "Drop a file"}
          hint="file"
          onDrag={(event) => startShapeDrag(editor, shape, event)}
          onDragOver={(event) => event.preventDefault()}
          onDrop={onDrop}
        >
          {shape.props.uploadPct >= 0 && shape.props.uploadPct < 100 ? (
            <>
              <p className="vik-file-path">{shape.props.name || "Uploading…"}</p>
              <UploadRing pct={shape.props.uploadPct} />
            </>
          ) : shape.props.uploadPct < 0 ? (
            <>
              <p className="vik-file-path">{shape.props.name || "Upload failed"}</p>
              <pre className="vik-file-preview">{shape.props.preview || "Could not upload this file."}</pre>
            </>
          ) : shape.props.fileId ? (
            <>
              <p className="vik-file-path">
                inbox/{shape.props.fileId}
                {shape.props.kind ? ` · ${shape.props.kind}` : ""}
              </p>
              {shape.props.kind === "image" ? (
                <img
                  className="vik-file-thumb"
                  alt={shape.props.name || "Image file"}
                  src={`/api/canvas/files/${encodeURIComponent(shape.props.fileId)}/raw`}
                />
              ) : (
                <pre className="vik-file-preview">
                  {shape.props.preview || "Stored. The agent can file-read or use python on it."}
                </pre>
              )}
            </>
          ) : (
            <p className="vik-empty">Drop a file here, or drop one anywhere on the canvas.</p>
          )}
        </Frame>
      </HTMLContainer>
    );
  }
}
