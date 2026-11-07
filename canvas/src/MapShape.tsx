import { BaseBoxShapeUtil, HTMLContainer, T, type TLShape } from "tldraw";
import { keepInteractive, startShapeDrag, useAccelHeld } from "./embedShapes";
import { replayMapLayerState } from "./mapBridge";

export const MAP_TYPE = "viksetu-map";
export const MAP_URL = import.meta.env.VITE_MAP_URL ?? "http://127.0.0.1:5173/?embed=1";

declare module "@tldraw/tlschema" {
  interface TLGlobalShapePropsMap {
    "viksetu-map": { w: number; h: number };
  }
}

export type VikMapShape = TLShape<"viksetu-map">;

export class MapShapeUtil extends BaseBoxShapeUtil<VikMapShape> {
  static override type = MAP_TYPE;
  static override props = {
    w: T.number,
    h: T.number,
  };

  override getDefaultProps(): VikMapShape["props"] {
    return { w: 760, h: 520 };
  }

  override getText(_shape: VikMapShape) {
    return "Palghar map";
  }

  override canEdit() {
    return true;
  }

  override getIndicatorPath(shape: VikMapShape) {
    const path = new Path2D();
    path.rect(0, 0, shape.props.w, shape.props.h);
    return path;
  }

  override component(shape: VikMapShape) {
    return <MapBody editor={this.editor} shape={shape} />;
  }
}

function MapBody({ editor, shape }: { editor: MapShapeUtil["editor"]; shape: VikMapShape }) {
  const selecting = useAccelHeld();
  return (
    <HTMLContainer id={shape.id} className="vik-map-shape">
      <div className={`vik-map-frame is-live${selecting ? " is-selecting" : ""}`}>
        <div
          className="vik-map-bar"
          tabIndex={0}
          aria-label="Drag Palghar map"
          draggable={false}
          onPointerDown={(event) => startShapeDrag(editor, shape, event)}
        >
          <span>Palghar map</span>
          <span className="vik-map-hint">drag this bar to move</span>
        </div>
        <div className="vik-map-stage" onPointerDown={keepInteractive}>
          <iframe
            title="Palghar district map"
            src={MAP_URL}
            draggable={false}
            onLoad={(event) => {
              const win = event.currentTarget.contentWindow;
              win?.postMessage({ source: "viksetu-canvas", kind: "resize" }, "*");
              window.setTimeout(() => replayMapLayerState(), 50);
            }}
          />
        </div>
      </div>
    </HTMLContainer>
  );
}
