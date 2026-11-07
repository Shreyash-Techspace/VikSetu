import type { PoiCard } from "./poiTypes";

type Props = {
  card: PoiCard | null;
  loading: boolean;
  visible: boolean;
  onClose: () => void;
};

export function PinDetailPanel({ card, loading, visible, onClose }: Props) {
  const show = visible && (loading || card);

  return (
    <aside
      className={`detail-panel ${show ? "detail-panel--visible" : ""}`}
      aria-hidden={!show}
    >
      {loading && (
        <div className="detail-inner detail-inner--loading">
          <div className="shimmer-line wide" />
          <div className="shimmer-line" />
          <div className="shimmer-line short" />
          <p className="detail-empty">Loading place…</p>
        </div>
      )}

      {!loading && card && (
        <div className="detail-inner detail-inner--enter">
          <div className="detail-header">
            <h2>{card.name}</h2>
            <button type="button" className="detail-close" onClick={onClose} aria-label="Close">
              ×
            </button>
          </div>
          <p className="detail-category">{card.category.replace(/_/g, " ")}</p>
          {card.taluka_id && <p className="detail-meta">Taluka: {card.taluka_id}</p>}
          <p className="detail-desc">{card.description}</p>

          <div className="detail-actions">
            <a
              className="btn-maps btn-maps--pulse"
              href={card.google_maps_directions_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Directions in Google Maps
            </a>
            <a
              className="btn-maps secondary"
              href={card.google_maps_place_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Open place
            </a>
          </div>

          <h3>FY history</h3>
          <ul className="fy-cards">
            {card.fy_history.map((row, i) => (
              <li key={row.fy} className="fy-card" style={{ animationDelay: `${i * 60}ms` }}>
                <div className="fy-card-head">
                  <strong>{row.fy}</strong>
                  <span>{row.status}</span>
                </div>
                {row.spend_inr != null && (
                  <p className="fy-spend">₹{Number(row.spend_inr).toLocaleString("en-IN")}</p>
                )}
                {row.notes && <p>{row.notes}</p>}
                {row.source_doc && <p className="fy-source">Source: {row.source_doc}</p>}
              </li>
            ))}
          </ul>

          <h3>Agent reference</h3>
          <p className="agent-summary">{card.agent_summary}</p>
          <p className="detail-id">pin_id: {card.pin_id}</p>
        </div>
      )}
    </aside>
  );
}
