import type { WorkspaceView } from "../types";
import { Icon } from "./Icon";
import { Empty, SourceLabel, short } from "./common";

export function DocumentTab({ view }: { view: WorkspaceView }) {
  const doc = view.document;
  const state = view.steps.document;
  if (!doc)
    return (
      <Empty title="No LaTeX document yet" icon="book">
        {view.kind === "upload"
          ? "Run step V. It writes one LaTeX document for this scan and compiles it to PDF with tectonic."
          : "The site stage has not written a document for this scan. Build the static site from the overview, or re-run step V."}
      </Empty>
    );
  const summary = (state.summary ?? {}) as Record<string, any>;
  const engine = summary.engine ?? summary.latex?.engine;
  return (
    <div className="document">
      <div className="document__bar">
        <p className="mono small muted">
          {doc.file} · sha256 {short(doc.tex_sha256, 12)}
          {engine ? ` · ${engine}` : ""}
          {doc.pdf_bytes ? ` · PDF ${(doc.pdf_bytes / 1024).toFixed(0)} KiB` : ""}
        </p>
        <div className="document__links">
          {doc.pdf_url && (
            <a className="btn btn--ghost btn--sm" href={doc.pdf_url} target="_blank" rel="noreferrer">
              <Icon name="external" size={14} /> Open PDF
            </a>
          )}
          <a className="btn btn--ghost btn--sm" href={doc.tex_url} target="_blank" rel="noreferrer">
            <Icon name="doc" size={14} /> .tex source
          </a>
        </div>
      </div>
      <div className="document__split">
        <div className="document__pane">
          <SourceLabel kind="britannica">
            Typeset Britannica text <span className="source-label__detail">entries in source order, then the source record</span>
          </SourceLabel>
          {doc.pdf_url ? (
            <iframe className="document__pdf" src={doc.pdf_url} title="Compiled PDF of this scan" />
          ) : (
            <Empty title="No PDF" icon="alert">
              {summary.note ?? "tectonic did not compile this document."} Install tectonic, then re-run step V.
            </Empty>
          )}
        </div>
        <div className="document__pane">
          <SourceLabel kind="raw">LaTeX source</SourceLabel>
          <pre className="raw__pre document__tex">{doc.tex}</pre>
        </div>
      </div>
    </div>
  );
}
