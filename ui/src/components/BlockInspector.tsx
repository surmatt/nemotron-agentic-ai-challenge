import { useState } from "react";
import type { Block, Furniture, WorkspaceView } from "../types";
import { Chip, Diff, SourceLabel, classColour, diffStats, num, seconds } from "./common";

const SOURCE_TEXT: Record<string, string> = {
  super_vl: "Super VL correction",
  parse: "Parse text (not sent for correction)",
  parse_fallback: "Parse text kept (fallback)",
};

export function sourceTone(block: Block) {
  if (block.review_flag) return "warn";
  if (block.text_source === "super_vl") return "ok";
  if (block.text_source === "parse_fallback") return "warn";
  return "plain";
}

export function BlockInspector({
  view,
  index,
  onClose,
}: {
  view: WorkspaceView;
  index: number | null;
  onClose: () => void;
}) {
  const page = view.page;
  const [mode, setMode] = useState<"diff" | "parse" | "used">("diff");
  if (!page) return null;
  const block: Block | undefined = page.blocks.find((b) => b.index === index);
  const furniture: Furniture | undefined = page.furniture.find((b) => b.index === index);

  if (index === null || (!block && !furniture)) {
    const counts = page.blocks.reduce<Record<string, number>>((acc, b) => ((acc[b.cls] = (acc[b.cls] ?? 0) + 1), acc), {});
    return (
      <aside className="inspector">
        <h3 className="inspector__title">Page record</h3>
        <dl className="facts">
          <dt>Page status</dt>
          <dd>
            <Chip tone={page.status === "ok" ? "ok" : "warn"}>{page.status}</Chip>
          </dd>
          <dt>Parse finish</dt>
          <dd>{page.finish_reason}</dd>
          <dt>Running header</dt>
          <dd>{page.running_header || "none"} <span className="muted">({page.header_kind})</span></dd>
          <dt>Body characters</dt>
          <dd>{page.body_chars.toLocaleString()}</dd>
          <dt>Blocks</dt>
          <dd>
            {Object.entries(counts).map(([cls, n]) => (
              <span key={cls} className="cls-count">
                <i style={{ background: classColour(cls) }} /> {cls} {n}
              </span>
            ))}
          </dd>
          <dt>Removed furniture</dt>
          <dd>{page.furniture.length ? page.furniture.map((f) => `${f.cls}: “${f.text}”`).join(" · ") : "none"}</dd>
          <dt>Entry text</dt>
          <dd>{view.entry_text === "correct" ? "Super VL corrected text" : "Parse text"}</dd>
        </dl>
        <p className="hint">Select a box on the scan to inspect its crop, text, and correction.</p>
      </aside>
    );
  }

  const item = (block ?? furniture)!;
  const cropUrl = view.crop_url.replace("{index}", String(item.index));
  const stats = block?.diff ? diffStats(block.diff) : null;

  return (
    <aside className="inspector" aria-live="polite">
      <div className="inspector__head">
        <h3 className="inspector__title">
          <span className="swatch" style={{ background: classColour(item.cls) }} />
          Block {item.index} · {item.cls}
        </h3>
        <button className="link-btn" onClick={onClose}>
          Page record
        </button>
      </div>
      <p className="mono muted small">
        box x {num(item.bbox[0], 3)}–{num(item.bbox[2], 3)} · y {num(item.bbox[1], 3)}–{num(item.bbox[3], 3)}
      </p>
      <figure className="crop">
        <img src={cropUrl} alt={`Enlarged crop of block ${item.index}`} loading="lazy" />
        <figcaption>3× crop, as sent to Super 3.5 VL</figcaption>
      </figure>
      {furniture && (
        <>
          <SourceLabel kind="britannica">page furniture, removed from entry text</SourceLabel>
          <p className="text-source">{furniture.text}</p>
        </>
      )}
      {block && (
        <>
          <div className="badges">
            {block.text_source && <Chip tone={sourceTone(block)}>{SOURCE_TEXT[block.text_source] ?? block.text_source}</Chip>}
            {block.review_flag && <Chip tone="warn">review: {block.review_flag.replaceAll("_", " ")}</Chip>}
            {block.long_s_rule_changed && <Chip tone="plain">long-s rule changed text</Chip>}
            {!block.eligible_for_correction && <Chip tone="plain">not eligible for correction</Chip>}
          </div>
          {block.diff && block.text_source ? (
            <>
              <div className="seg seg--text" role="tablist" aria-label="Text view">
                {(["diff", "parse", "used"] as const).map((m) => (
                  <button key={m} role="tab" aria-selected={mode === m} className={mode === m ? "is-on" : ""} onClick={() => setMode(m)}>
                    {m === "diff" ? "Changes" : m === "parse" ? "Parse 3.5" : "Text in use"}
                  </button>
                ))}
              </div>
              <SourceLabel kind="britannica">
                {mode === "parse" ? "Parse 3.5 OCR" : mode === "used" ? SOURCE_TEXT[block.text_source] : "Parse → text in use"}
              </SourceLabel>
              {mode === "diff" && <Diff ops={block.diff} />}
              {mode === "parse" && <p className="text-source">{block.parse_text}</p>}
              {mode === "used" && <p className="text-source">{block.text}</p>}
              {stats && (
                <p className="mono small muted">
                  {stats.kept} words kept · <span className="ins-c">+{stats.inserted}</span> ·{" "}
                  <span className="del-c">−{stats.deleted}</span>
                </p>
              )}
            </>
          ) : (
            <>
              <SourceLabel kind="britannica">Parse 3.5 OCR</SourceLabel>
              <p className="text-source">{block.parse_text || <em className="muted">no text</em>}</p>
            </>
          )}
          {block.correction && (
            <p className="mono small muted">
              {block.correction.model?.replace("nvidia/", "")} · {seconds(block.correction.elapsed_seconds)} ·{" "}
              {block.correction.completion_tokens ?? "?"} tokens · finish {block.correction.finish_reason}
            </p>
          )}
        </>
      )}
    </aside>
  );
}
