import { useMemo, useState } from "react";
import { BaseBoxShapeUtil, HTMLContainer, T, stopEventPropagation, type Editor, type TLShape } from "tldraw";
import { Frame, startShapeDrag } from "./embedShapes";

export const CUSTOM_TYPE = "viksetu-custom";

declare module "@tldraw/tlschema" {
  interface TLGlobalShapePropsMap {
    "viksetu-custom": { w: number; h: number; title: string; html: string; data: string };
  }
}

type CustomShape = TLShape<typeof CUSTOM_TYPE>;

// The frame can run script but has no network, no parent access, and no storage.
const POLICY =
  "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data:";

function safeJson(raw: string): string {
  let value: unknown = null;
  if (raw.trim()) {
    try {
      value = JSON.parse(raw);
    } catch {
      value = raw;
    }
  }
  return JSON.stringify(value ?? null).replace(/</g, "\\u003c").replace(/\u2028|\u2029/g, " ");
}

export function buildCustomDoc(html: string, data: string): string {
  return [
    "<!doctype html><html><head><meta charset=\"utf-8\">",
    `<meta http-equiv="Content-Security-Policy" content="${POLICY}">`,
    "<style>html,body{margin:0;min-height:100%;background:#0f172a;color:#e2e8f0;font:14px/1.45 system-ui,sans-serif}",
    "body{padding:10px;box-sizing:border-box}table{border-collapse:collapse}</style>",
    `<script>window.DATA=${safeJson(data)};</script></head><body>`,
    html,
    "</body></html>",
  ].join("");
}

function CustomBody({ editor, shape }: { editor: Editor; shape: CustomShape }) {
  const [editing, setEditing] = useState(false);
  const srcDoc = useMemo(
    () => buildCustomDoc(shape.props.html, shape.props.data),
    [shape.props.html, shape.props.data]
  );
  return (
    <HTMLContainer>
      <Frame
        className="vik-custom-frame"
        title={shape.props.title || "Embed"}
        hint="custom"
        onDrag={(event) => startShapeDrag(editor, shape, event)}
        onRename={(title) => editor.updateShape({ id: shape.id, type: CUSTOM_TYPE, props: { title } })}
        extra={
          <button
            type="button"
            className="vik-edit-toggle"
            onPointerDown={stopEventPropagation}
            onClick={() => setEditing((value) => !value)}
          >
            {editing ? "View" : "Code"}
          </button>
        }
      >
        {editing ? (
          <textarea
            className="vik-doc-edit vik-code-edit"
            spellCheck={false}
            value={shape.props.html}
            aria-label="Embed HTML"
            onPointerDown={stopEventPropagation}
            onChange={(event) =>
              editor.updateShape({ id: shape.id, type: CUSTOM_TYPE, props: { html: event.target.value } })
            }
          />
        ) : (
          <iframe className="vik-custom-frame__view" title={shape.props.title || "Embed"} sandbox="allow-scripts" srcDoc={srcDoc} />
        )}
      </Frame>
    </HTMLContainer>
  );
}

export class CustomShapeUtil extends BaseBoxShapeUtil<CustomShape> {
  static override type = CUSTOM_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
    title: T.string,
    html: T.string,
    data: T.string,
  };

  override getDefaultProps(): CustomShape["props"] {
    return { w: 420, h: 300, title: "Embed", html: "", data: "" };
  }

  override getText(shape: CustomShape) {
    const plain = shape.props.html.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    return [shape.props.title, plain].filter((line) => line.trim()).join("\n") || "Embed";
  }

  override getIndicatorPath(shape: CustomShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: CustomShape) {
    return <CustomBody editor={this.editor} shape={shape} />;
  }
}
