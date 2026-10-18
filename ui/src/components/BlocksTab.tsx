import { useMemo, useState } from "react";
import type { Block, WorkspaceView } from "../types";
import { sourceTone } from "./BlockInspector";
import { Chip, Diff, Empty, classColour, diffStats } from "./common";

type Filter = "all" | "changed" | "flagged" | "kept";

const FILTERS: { id: Filter; label: string; help: string }[] = [
  { id: "all", label: "all", help: "Every body block on the page." },
  { id: "changed", label: "changed", help: "Blocks where the text in use differs from the Parse text by at least one word." },
  {
    id: "flagged",
    label: "flagged",
    help:
      "Blocks to check by hand. The correct step sets a flag when Super VL returns much more text than Parse " +
      "(expanded beyond Parse), returns no text (emptied), fails, or when the box is too small to send.",
  },
  {
    id: "kept",
    label: "Parse kept",
    help:
      "Blocks that use the Parse text, not the Super VL text: blocks that are not text, boxes too small to send, " +
      "blocks where the Super VL call failed, and all blocks on plate or blank pages.",
  },
];

const matches = (b: Block, filter: Filter) => {
  const s = diffStats(b.diff);
  if (filter === "changed") return s.inserted + s.deleted > 0;
  if (filter === "flagged") return Boolean(b.review_flag);
  if (filter === "kept") return b.text_source === "parse_fallback" || b.text_source === "parse";
  return true;
};

export function BlocksTab({ view, onLocate }: { view: WorkspaceView; onLocate: (index: number) => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const blocks = view.page?.blocks ?? [];
  const corrected = blocks.some((b) => b.text_source);

  const rows = useMemo(() => blocks.filter((b) => matches(b, filter)), [blocks, filter]);

  if (!view.page) return <Empty title="No blocks yet">Run step I to get the layout blocks.</Empty>;
  const totals = blocks.reduce(
    (acc, b) => {
      const s = diffStats(b.diff);
      acc.ins += s.inserted;
      acc.del += s.deleted;
      acc.kept += s.kept;
      return acc;
    },
    { ins: 0, del: 0, kept: 0 },
  );

  return (
    <div className="blocks">
      <div className="blocks__bar">
        <div className="seg" role="tablist" aria-label="Filter blocks">
          {FILTERS.map((f) => (
            <button
              key={f.id}
              role="tab"
              aria-selected={filter === f.id}
              className={filter === f.id ? "is-on" : ""}
              onClick={() => setFilter(f.id)}
              title={f.help}
            >
              {f.label} <span className="seg__n">{blocks.filter((b) => matches(b, f.id)).length}</span>
            </button>
          ))}
        </div>
        {corrected ? (
          <p className="mono small muted">
            Words across blocks: {totals.kept} kept · <span className="ins-c">+{totals.ins}</span> ·{" "}
            <span className="del-c">−{totals.del}</span>. Struck text is Parse output; underlined text is the correction.
          </p>
        ) : (
          <p className="mono small muted">Run step II to see Super VL corrections next to the Parse text.</p>
        )}
      </div>
      {filter !== "all" && <p className="small muted blocks__help">{FILTERS.find((f) => f.id === filter)!.help}</p>}
      <ol className="block-list">
        {rows.map((b) => (
          <li key={b.index} className="block-row">
            <button className="block-row__idx" onClick={() => onLocate(b.index)} title="Show on scan">
              <span className="swatch" style={{ background: classColour(b.cls) }} />
              {b.index}
            </button>
            <div className="block-row__body">
              <div className="badges">
                <Chip>{b.cls}</Chip>
                {b.text_source && <Chip tone={sourceTone(b)}>{b.text_source.replace("_", " ")}</Chip>}
                {b.review_flag && <Chip tone="warn">{b.review_flag.replaceAll("_", " ")}</Chip>}
              </div>
              {b.diff && b.text_source ? <Diff ops={b.diff} /> : <p className="text-source">{b.parse_text || "—"}</p>}
            </div>
            <img
              className="block-row__crop"
              src={view.crop_url.replace("{index}", String(b.index))}
              alt={`Crop of block ${b.index}`}
              loading="lazy"
            />
          </li>
        ))}
      </ol>
      {!rows.length && <Empty title="No blocks match this filter" />}
    </div>
  );
}
