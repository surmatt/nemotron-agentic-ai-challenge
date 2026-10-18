import { useMemo, useState } from "react";
import type { Pair, TermRow, WorkspaceView } from "../types";
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
