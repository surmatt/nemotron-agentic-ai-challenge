import { useMemo, useState } from "react";
import type { DiffSummary, Pair, TermRow, WorkspaceView } from "../types";
import { Chip, Empty, SourceLabel, num } from "./common";

function Bars({ rows, side, onPick, picked }: { rows: TermRow[]; side: "b" | "w"; onPick: (t: TermRow) => void; picked?: string }) {
  const peak = Math.max(1, ...rows.map((r) => Math.abs(r.z)));
  return (
    <ol className={`bars bars--${side}`}>
      {rows.slice(0, 12).map((r) => (
        <li key={r.term}>
          <button className={`bar ${picked === r.term ? "is-on" : ""}`} onClick={() => onPick(r)} title="Show source snippets">
            <span className="bar__term">{r.term}</span>
            <span className="bar__track">
              <span className="bar__fill" style={{ width: `${(Math.abs(r.z) / peak) * 100}%` }} />
            </span>
            <span className="bar__z mono">{num(r.z, 1)}</span>
            <span className="bar__n mono">
              {r.count_britannica}:{r.count_wikipedia}
            </span>
          </button>
        </li>
      ))}
    </ol>
  );
}

function Highlight({ text, term }: { text: string; term: string }) {
  const parts = text.split(new RegExp(`\\b(${term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})\\b`, "i"));
  return (
    <>
      {parts.map((p, i) => (i % 2 ? <mark key={i}>{p}</mark> : <span key={i}>{p}</span>))}
    </>
  );
}

const SAME_SUBJECT: Record<string, [string, string]> = {
  yes: ["same subject", "ok"],
  partly: ["partly the same subject", "warn"],
  no: ["different subjects", "bad"],
};
const SELECTION: Record<string, string> = {
  whole_article: "the whole article",
  embedder: "the Wikipedia passages closest to the entry by embedder cosine",
  lead: "the first Wikipedia passages (no embedder ranking)",
};

function Check({ ok, what }: { ok: boolean; what: string }) {
  return <span className={`diff-item__check ${ok ? "is-pass" : "is-fail"}`}>{ok ? `quote found in the ${what}` : `quote not found in the ${what}`}</span>;
}

function DiffSummaryPanel({ summary }: { summary: DiffSummary | null | undefined }) {
  if (!summary) return <Empty title="No difference summary">Run step V after the compare step.</Empty>;
  if (summary.status !== "ok")
    return (
      <div className="summary">
        <SourceLabel kind="generated">difference summary · {summary.status}</SourceLabel>
        <div className="summary__body">
          <p className="mono small">{summary.status === "skipped" ? summary.reason : `${summary.error_type}: ${summary.error}`}</p>
          {summary.raw_path && <p className="mono small muted">Raw reply: {summary.raw_path}</p>}
        </div>
      </div>
    );
  const diffs = summary.differences ?? [];
  const same = summary.same_subject ? SAME_SUBJECT[summary.same_subject] : null;
  const ctx = summary.context;
  return (
    <div className="summary">
      <SourceLabel kind="generated">
        key differences by {summary.model} · {summary.differences_with_quotes ?? 0} of {diffs.length} with both quotes found
        {summary.cached ? " · saved reply" : ""}
      </SourceLabel>
      <div className="summary__body">
        <div className="summary__meta">
          {same && <Chip tone={same[1]} title="Model inference, without a citation">{same[0]} (inference)</Chip>}
          {ctx && (
            <span className="mono small muted">
              Read {SELECTION[ctx.selection] ?? ctx.selection}: {ctx.passages.length} passage{ctx.passages.length === 1 ? "" : "s"}, {ctx.chars} characters
              {ctx.selection_detail ? ` · ${ctx.selection_detail}` : ""}
            </span>
          )}
        </div>
        {summary.overview && (
          <p className="summary__overview" title="Model inference, without a citation">
            {summary.overview} <span className="mono small muted">(inference)</span>
          </p>
        )}
        <p className="mono small muted">
          The claims are model inference. A found quote shows that the words occur in the source, not that they support the claim.
        </p>
        {diffs.length === 0 ? (
          <p className="mono small muted">The model reported no differences.</p>
        ) : (
          <ol className="diffs">
            {diffs.map((d, i) => (
              <li key={i} className={`diff-item ${d.quotes_found ? "" : "diff-item--unsupported"}`}>
                <div className="diff-item__head">
                  <h4>{d.aspect}</h4>
                  <Chip tone={d.quotes_found ? "ok" : "bad"}>{d.quotes_found ? "both quotes found" : "quote not found"}</Chip>
                </div>
                <div className="diff-item__sides">
                  <div>
                    <p className="diff-item__claim" title="Model inference"><span className="tint-b">Britannica:</span> {d.britannica}</p>
                    <SourceLabel kind="britannica">quote{d.evidence.britannica.offset !== null ? ` · offset ${d.evidence.britannica.offset}` : ""}</SourceLabel>
                    <p className="diff-item__quote text-source">“{d.evidence.britannica.quote}”</p>
                    <Check ok={d.evidence.britannica.found} what="entry text" />
                  </div>
                  <div>
                    <p className="diff-item__claim" title="Model inference"><span className="tint-w">Wikipedia:</span> {d.wikipedia}</p>
                    <SourceLabel kind="wikipedia">
                      quote{d.evidence.wikipedia.passage_id ? ` · ${d.evidence.wikipedia.passage_id}` : ""}
                      {d.evidence.wikipedia.offset !== null ? ` · offset ${d.evidence.wikipedia.offset}` : ""}
                    </SourceLabel>
                    <p className="diff-item__quote text-wiki">“{d.evidence.wikipedia.quote}”</p>
                    <Check ok={d.evidence.wikipedia.found} what="article text" />
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
      </div>
    </div>
  );
}

export function CompareTab({ view }: { view: WorkspaceView }) {
  const pairs = useMemo(() => view.entries.map((e) => e.pair).filter(Boolean) as Pair[], [view.entries]);
  const [selected, setSelected] = useState<string | null>(null);
  const [term, setTerm] = useState<TermRow | null>(null);

  if (view.steps.compare.status !== "done" && !pairs.length)
    return <Empty title="Not compared yet">Run step IV after the match step accepts at least one pair.</Empty>;
  if (!pairs.length) return <Empty title="No pairs to compare">The match step accepted no Wikipedia article for this page.</Empty>;

  const pair = pairs.find((p) => p.entry_id === selected) ?? pairs[0];

  return (
    <div className="compare">
      {pairs.length > 1 && (
        <div className="seg seg--wrap" role="tablist" aria-label="Pairs">
          {pairs.map((p) => (
            <button key={p.entry_id} role="tab" aria-selected={p.entry_id === pair.entry_id} className={p.entry_id === pair.entry_id ? "is-on" : ""} onClick={() => { setSelected(p.entry_id); setTerm(null); }}>
              {p.headword ?? p.entry_id} ⇄ {p.article.title}
            </button>
          ))}
        </div>
      )}
      <header className="compare__head">
        <h3>
          <span className="tint-b">{pair.headword ?? pair.entry_id}</span> <span className="muted">⇄</span>{" "}
          <span className="tint-w">{pair.article.title}</span>
        </h3>
        <p className="mono small muted">
          {pair.entry_id} · Wikipedia revision{" "}
          <a href={pair.article.revision_url} target="_blank" rel="noreferrer">
            {pair.article.revision_id}
          </a>{" "}
          · matched by {pair.match_method}
        </p>
      </header>
      <DiffSummaryPanel summary={view.entries.find((e) => e.entry_id === pair.entry_id)?.summary} />
      <SourceLabel kind="generated">word-frequency comparison, log-odds z-scores with an informative Dirichlet prior</SourceLabel>
      <div className="metrics">
        <div className="metric">
          <span className="metric__v">{num(pair.frequency_cosine, 3)}</span>
          <span className="metric__k">frequency cosine</span>
        </div>
        <div className="metric">
          <span className="metric__v">{num(pair.top_terms_jaccard, 3)}</span>
          <span className="metric__k">top-100 terms Jaccard</span>
        </div>
        <div className="metric">
          <span className="metric__v">{num(pair.length_ratio_wiki_to_britannica, 1)}×</span>
          <span className="metric__k">Wikipedia / Britannica length</span>
        </div>
        <div className="metric">
          <span className="metric__v">{pair.britannica.unverified_rate === null ? "n/a" : `${(pair.britannica.unverified_rate * 100).toFixed(1)}%`}</span>
          <span className="metric__k">Britannica tokens not in a word list</span>
        </div>
      </div>
      <div className="diverge">
        <div>
          <h4 className="tint-b">More frequent in Britannica</h4>
          <Bars rows={pair.distinctive_britannica} side="b" onPick={setTerm} picked={term?.term} />
        </div>
        <div>
          <h4 className="tint-w">More frequent in Wikipedia</h4>
          <Bars rows={pair.distinctive_wikipedia} side="w" onPick={setTerm} picked={term?.term} />
        </div>
      </div>
      <p className="mono small muted">Bars show z-scores. Counts read Britannica : Wikipedia. Select a term to see it in both sources.</p>
      {term && (
        <div className="snippets">
          <div>
            <SourceLabel kind="britannica">“{term.term}” in the entry</SourceLabel>
            <p className="text-source">{term.britannica_snippet ? <Highlight text={term.britannica_snippet.text} term={term.term} /> : <em className="muted">not in the entry text</em>}</p>
          </div>
          <div>
            <SourceLabel kind="wikipedia">“{term.term}” in the article</SourceLabel>
            <p className="text-wiki">{term.wikipedia_snippet ? <Highlight text={term.wikipedia_snippet.text} term={term.term} /> : <em className="muted">not in the article text</em>}</p>
          </div>
        </div>
      )}
      <div className="shared">
        <span className="eyebrow">Shared terms</span>
        {pair.shared_terms.slice(0, 20).map((s) => (
          <Chip key={s.term} title={`Britannica ${s.count_britannica} · Wikipedia ${s.count_wikipedia}`}>
            {s.term} <span className="muted">{s.count_britannica}:{s.count_wikipedia}</span>
          </Chip>
        ))}
      </div>
      {pair.britannica.unverified_examples.length > 0 && (
        <p className="mono small muted">Unverified Britannica tokens (possible OCR errors): {pair.britannica.unverified_examples.join(", ")}</p>
      )}
    </div>
  );
}
