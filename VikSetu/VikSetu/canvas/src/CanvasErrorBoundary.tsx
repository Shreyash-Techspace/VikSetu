import { Component, type ReactNode } from "react";
import { resetCanvasPersistence } from "./canvasPersistence";

const PERSIST_KEYS = ["viksetu-canvas", "viksetu-canvas-v2"];

type Props = { children: ReactNode };
type State = { error: Error | null; resetting: boolean };

export class CanvasErrorBoundary extends Component<Props, State> {
  state: State = { error: null, resetting: false };

  static getDerivedStateFromError(error: Error): State {
    return { error, resetting: false };
  }

  private reload = async () => {
    this.setState({ resetting: true });
    await resetCanvasPersistence(PERSIST_KEYS);
    for (const key of ["viksetu-canvas-chats", "viksetu-canvas-chat"]) {
      try {
        localStorage.removeItem(key);
      } catch {
        // ignore
      }
    }
    window.location.reload();
  };

  render() {
    if (this.state.error) {
      return (
        <div className="canvas-fatal">
          <h1>Canvas failed to load</h1>
          <p>Often this is outdated saved canvas data after an update.</p>
          <pre>{this.state.error.message}</pre>
          <button type="button" disabled={this.state.resetting} onClick={() => void this.reload()}>
            {this.state.resetting ? "Resetting…" : "Reset canvas data & reload"}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
