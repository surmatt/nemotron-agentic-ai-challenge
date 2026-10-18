import { useMemo, useState } from "react";
import type { BBox, PageView } from "../types";
import { Icon } from "./Icon";
import { classColour } from "./common";

interface Box {
  index: number;
  cls: string;
  bbox: BBox;
  furniture: boolean;
}

export function ScanViewer({
  imageUrl,
  width,
  height,
  page,
  selected,
  hovered,
  highlight,
  onSelect,
  onHover,
}: {
  imageUrl: string;
  width?: number;
  height?: number;
  page: PageView | null;
  selected: number | null;
  hovered: number | null;
  highlight: Set<number>;
  onSelect: (index: number | null) => void;
  onHover: (index: number | null) => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [layers, setLayers] = useState({ text: true, pictures: true, furniture: true, numbers: true });
  const [loaded, setLoaded] = useState(false);

  const boxes: Box[] = useMemo(() => {
    if (!page) return [];
    return [
      ...page.blocks.map((b) => ({ index: b.index, cls: b.cls, bbox: b.bbox, furniture: false })),
      ...page.furniture.map((b) => ({ index: b.index, cls: b.cls, bbox: b.bbox, furniture: true })),
    ].sort((a, b) => a.index - b.index);
  }, [page]);

  const visible = boxes.filter((b) =>
    b.furniture ? layers.furniture : b.cls === "Picture" ? layers.pictures : layers.text,
  );
  const toggle = (key: keyof typeof layers) => setLayers((l) => ({ ...l, [key]: !l[key] }));
  const aspect = width && height ? `${width} / ${height}` : undefined;

  return (
    <div className="viewer">
      <div className="viewer__tools" role="toolbar" aria-label="Scan view controls">
        <div className="seg">
          <button className="icon-btn" onClick={() => setZoom((z) => Math.max(0.5, +(z - 0.25).toFixed(2)))} aria-label="Zoom out">
            <Icon name="minus" size={16} />
          </button>
          <button className="icon-btn icon-btn--text" onClick={() => setZoom(1)} aria-label="Fit to width">
            {Math.round(zoom * 100)}%
          </button>
          <button className="icon-btn" onClick={() => setZoom((z) => Math.min(4, +(z + 0.25).toFixed(2)))} aria-label="Zoom in">
            <Icon name="plus" size={16} />
          </button>
        </div>
        {page && (
          <div className="seg seg--layers" aria-label="Overlay layers">
            <Icon name="layers" size={15} />
            {(["text", "pictures", "furniture", "numbers"] as const).map((key) => (
              <label key={key} className="toggle">
                <input type="checkbox" checked={layers[key]} onChange={() => toggle(key)} />
                <span>{key === "furniture" ? "headers & numbers" : key === "numbers" ? "order" : key}</span>
              </label>
            ))}
          </div>
        )}
      </div>
      <div className="viewer__table">
        <div className="viewer__sheet" style={{ width: `${zoom * 100}%`, aspectRatio: aspect }}>
          {!loaded && <div className="viewer__loading">Loading scan…</div>}
          <img
            src={imageUrl}
            alt="Uploaded or pinned Britannica scan"
            onLoad={() => setLoaded(true)}
            className={loaded ? "is-loaded" : ""}
            draggable={false}
          />
          {page && (
            <svg className="viewer__overlay" viewBox="0 0 1 1" preserveAspectRatio="none" onClick={() => onSelect(null)}>
              {visible.map((b, i) => {
                const [x0, y0, x1, y1] = b.bbox;
                const isSel = selected === b.index;
                const isHover = hovered === b.index;
                const isLit = highlight.has(b.index);
                return (
                  <rect
                    key={b.index}
                    x={x0}
                    y={y0}
                    width={Math.max(0.002, x1 - x0)}
                    height={Math.max(0.002, y1 - y0)}
                    className={`box ${b.furniture ? "box--furniture" : ""} ${isSel ? "is-selected" : ""} ${isHover ? "is-hover" : ""} ${isLit ? "is-lit" : ""} ${highlight.size && !isLit ? "is-dim" : ""}`}
                    style={{ "--c": classColour(b.cls), animationDelay: `${Math.min(i * 25, 900)}ms` } as React.CSSProperties}
                    vectorEffect="non-scaling-stroke"
                    onMouseEnter={() => onHover(b.index)}
                    onMouseLeave={() => onHover(null)}
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelect(b.index);
                    }}
                  >
                    <title>{`#${b.index} ${b.cls}`}</title>
                  </rect>
                );
              })}
            </svg>
          )}
          {page &&
            layers.numbers &&
            visible.map((b) => (
              <span
                key={b.index}
                className={`box-tag ${selected === b.index ? "is-selected" : ""}`}
                style={{ left: `${b.bbox[0] * 100}%`, top: `${b.bbox[1] * 100}%`, "--c": classColour(b.cls) } as React.CSSProperties}
                aria-hidden
              >
                {b.index}
              </span>
            ))}
        </div>
      </div>
      {page && (
        <div className="legend" aria-label="Block class legend">
          {Array.from(new Set(boxes.map((b) => b.cls))).map((cls) => (
            <span key={cls} className="legend__item">
              <i style={{ background: classColour(cls) }} />
              {cls}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
