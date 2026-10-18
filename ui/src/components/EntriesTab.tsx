import type { WorkspaceView } from "../types";
import { Icon } from "./Icon";
import { Chip, Empty, SourceLabel, short } from "./common";

export function EntriesTab({
  view,
  onLocate,
  onOpenMatch,
}: {
  view: WorkspaceView;
  onLocate: (indexes: number[]) => void;
  onOpenMatch: (entryId: string) => void;
}) {
  if (!view.page) return <Empty title="No entries yet">Run step I to segment the page into entries.</Empty>;
  if (!view.entries.length)
    return <Empty title="No entries on this page">Parse found no running text, or the page is blank, sparse, or a plate.</Empty>;
  return (
    <div className="entries">
      <p className="mono small muted">
        {view.entries.length} entries · text from{" "}
        {view.entry_text === "correct" ? "the Super VL correction" : "Parse 3.5 (run step II to use corrected text)"}. A
        capitalised headword starts an entry; text before the first headword continues an entry from an earlier page.
      </p>
      {view.entries.map((e) => {
        const decision = e.match?.decision;
        return (
          <article key={e.entry_id} className="entry">
            <header className="entry__head">
              <div>
                <span className="entry__id mono">{e.entry_id}</span>
                <h3 className="entry__headword">{e.headword ?? <em>untitled continuation</em>}</h3>
              </div>
              <div className="badges">
                <Chip tone={e.start_kind === "headword" ? "plain" : "warn"}>{e.start_kind}</Chip>
                {e.pages.length > 1 && <Chip>joined across {e.pages.length} scans</Chip>}
                <Chip>{e.chars.toLocaleString()} chars</Chip>
                {e.skip_reason && <Chip tone="muted">not searched: {e.skip_reason}</Chip>}
                {decision && (
                  <Chip tone={decision.status === "accepted" ? "ok" : decision.status === "error" ? "bad" : "muted"}>
                    match {decision.status}
                    {decision.title ? ` · ${decision.title}` : ""}
                  </Chip>
                )}
              </div>
            </header>
            <SourceLabel kind="britannica">
              {view.entry_text === "correct" ? "Parse 3.5, corrected by Super 3.5 VL" : "Parse 3.5 OCR"} · sha256 {short(e.text_sha256)}
            </SourceLabel>
            <p className="text-source text-source--clamp">{e.text}</p>
            <footer className="entry__foot">
              <button className="link-btn" onClick={() => onLocate(e.block_indexes)}>
                <Icon name="search" size={14} /> Show blocks {e.block_indexes.join(", ")} on scan
              </button>
              {e.match && (
                <button className="link-btn" onClick={() => onOpenMatch(e.entry_id)}>
                  <Icon name="arrow" size={14} /> Matching evidence
                </button>
              )}
            </footer>
          </article>
        );
      })}
    </div>
  );
}
