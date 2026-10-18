import { useEffect, useMemo, useState } from "react";
import type { Entry, WorkspaceView } from "../types";
import { Icon } from "./Icon";
import { Chip, Empty, Gauge, SourceLabel, num } from "./common";

const NOT_SCORED = "The models score the first 32 candidates in BM25 rank order. This page came later.";
const tone = (status?: string) => (status === "accepted" ? "ok" : status === "error" ? "bad" : "muted");

export function MatchTab({ view, focus, onApplyRule, busy = false }: {
  view: WorkspaceView;
  focus: string | null;
  onApplyRule?: () => void;
  busy?: boolean;
}) {
  const searched = useMemo(() => view.entries.filter((e) => e.match), [view.entries]);
  const [selected, setSelected] = useState<string | null>(focus);
  useEffect(() => {
    if (focus) setSelected(focus);
  }, [focus]);

  if (view.steps.match.status !== "done" && !searched.length)
    return <Empty title="Not matched yet">Run step III to search Wikipedia and score the candidates.</Empty>;
  if (!searched.length)
    return <Empty title="No searched entries">Every entry on this page was too short or had no headword.</Empty>;

  const current: Entry = searched.find((e) => e.entry_id === selected) ?? searched[0];
  const m = current.match!;
  const d = m.decision;
  const t = d.thresholds ?? {};
  const maxLogit = Math.max(...m.candidates.map((c) => c.rerank_logit ?? -Infinity));
  const minLogit = Math.min(...m.candidates.map((c) => c.rerank_logit ?? Infinity));

  return (
    <div className="match">
      <nav className="match__list" aria-label="Searched entries">
        {searched.map((e) => (
          <button
            key={e.entry_id}
            className={`match__item ${e.entry_id === current.entry_id ? "is-on" : ""}`}
            onClick={() => setSelected(e.entry_id)}
          >
            <span className={`dot dot--${tone(e.match?.decision.status)}`} aria-hidden />
            <span className="match__item-name">{e.headword ?? e.entry_id}</span>
            <span className="mono small muted">{e.match?.decision.status}</span>
          </button>
        ))}
      </nav>
      <section className="match__detail">
        <header className={`verdict verdict--${tone(d.status)}`}>
          <div>
            <p className="eyebrow">
              {current.entry_id} · {m.mode === "model" ? "embedder + reranker" : "provisional lexical rule"}
            </p>
            <h3>
              {current.headword ?? "untitled"} <Icon name="arrow" size={18} /> {d.title ?? "no article"}
            </h3>
            <p className="verdict__reason">
              {d.status === "accepted"
                ? `Accepted by ${d.method}.`
                : d.status === "error"
                  ? `${d.error_type}: ${d.error}`
                  : d.reason}
            </p>
          </div>
          <Chip tone={tone(d.status)}>{d.status}</Chip>
        </header>

        {m.mode === "model" && d.status !== "error" && (
          <div className="gauges">
            <Gauge label="Reranker logit" value={d.rerank_logit} threshold={t.rerank_logit} min={-12} max={4} />
            <Gauge label="Embedder cosine" value={d.cosine} threshold={t.cosine} min={-0.1} max={0.7} format={(v) => num(v, 4)} />
            <Gauge label="Title similarity" value={d.title_similarity} threshold={t.title_similarity || undefined} min={0} max={1} />
          </div>
        )}
        {m.mode === "model" && d.status !== "error" && (
          <p className="small muted flowstep__lede">
            The top reranked page must pass the logit, cosine, and title-similarity thresholds.
            A close second candidate does not cause rejection.
            {t.margin !== undefined && (
              onApplyRule
                ? " This saved decision used the previous margin rule. Apply the current rule below to update it."
                : " This saved decision used the previous margin rule. Re-run Match to apply the current rule."
            )}
          </p>
        )}
        {m.mode === "model" && onApplyRule && (
          <button
            className="btn btn--ghost"
            onClick={onApplyRule}
            disabled={busy}
            title="Recheck this scan's saved scores, fetch accepted articles, and rebuild later outputs. No model calls."
          >
            <Icon name="refresh" size={14} /> Apply current rule (reuse scores)
          </button>
        )}
        {m.mode === "lexical" && d.status !== "error" && (
          <div className="gauges">
            <Gauge label="Title similarity" value={d.title_similarity} threshold={0.85} min={0} max={1} />
            <Gauge label="Context overlap" value={d.context_overlap} min={0} max={1} />
          </div>
        )}

        <section className="flowstep" aria-label="Wikipedia search">
          <h4 className="flowstep__title">
            <span className="flowstep__n">1</span> Sent to the Wikipedia search API (BM25)
          </h4>
          <p className="small muted flowstep__lede">
            One search per query. The pages of all searches merge into one candidate list. Disambiguation and list pages
            leave the list.
          </p>
          {m.search_terms && (
            <div>
              <p className="small muted">Frequency words · whole entry + headers</p>
              <p className="badges">
                {m.search_terms.frequency.map((w) => (
                  <Chip key={w}>{w}</Chip>
                ))}
              </p>
              {m.search_terms.llm.status === "ok" ? (
                <>
                  <SourceLabel kind="generated">
                    {m.search_terms.llm.model ?? "Super VL"} · title guess and search terms
                  </SourceLabel>
                  <p className="badges">
                    {m.search_terms.llm.title && <Chip tone="ok">{m.search_terms.llm.title}</Chip>}
                    {(m.search_terms.llm.terms ?? []).map((w) => (
                      <Chip key={w}>{w}</Chip>
                    ))}
                  </p>
                </>
              ) : (
                <p className="small muted">
                  {m.search_terms.llm.error ?? m.search_terms.llm.reason ?? "no Super VL terms"}
                </p>
              )}
            </div>
          )}
          <div className="search-grid">
            {m.searches.map((s) => (
              <article key={s.id} className="search">
                <header className="search__head">
                  <span className="mono small">{s.id}</span>
                  <Chip>{s.kind}</Chip>
                  <span className="mono small muted">{s.hits.length} pages</span>
                </header>
                <code className="search__query">{s.query}</code>
                {s.top_k && (
                  <p className="mono small muted search__params">
                    top_k {s.top_k} · excerpt {s.excerpt_chars?.toLocaleString()} chars
                  </p>
                )}
                <ol className="hits">
                  {s.hits.map((h) => (
                    <li
                      key={h.page_id}
                      className={`hit hit--${h.status} ${h.page_id === d.page_id ? "hit--chosen" : ""}`}
                      title={h.removed ? `Removed: ${h.removed}` : h.status === "not_scored" ? NOT_SCORED : undefined}
                    >
                      <span className="hit__rank mono">{h.rank}</span>
                      <a className="hit__title" href={h.url ?? undefined} target="_blank" rel="noreferrer">
                        {h.title}
                      </a>
                      <span className="hit__score mono">{h.bm25.toFixed(2)}</span>
                      {h.page_id === d.page_id ? (
                        <Chip tone="ok">chosen</Chip>
                      ) : h.removed ? (
                        <Chip tone="warn">{h.removed}</Chip>
                      ) : h.status === "not_scored" ? (
                        <Chip tone="muted">not scored</Chip>
                      ) : null}
                    </li>
                  ))}
                  {!s.hits.length && <li className="small muted">No pages returned.</li>}
                </ol>
              </article>
            ))}
          </div>
          {m.headword_variant && <Chip>OCR headword variant: {m.headword_variant}</Chip>}
          {!m.searches_complete && (
            <p className="small muted">
              This run saved only the pages that stayed in the candidate list, so removed pages are missing. Re-run match
              to record every page that each search returned.
            </p>
          )}
        </section>

        {m.model_query && (
          <section className="flowstep" aria-label="Model query">
            <h4 className="flowstep__title">
              <span className="flowstep__n">2</span> Sent to the embedder and the reranker
            </h4>
            <p className="small muted flowstep__lede">
              The query is the headword and the entry text, cut to {m.model_query.chars.toLocaleString()} characters. Each of
              the {m.model_query.documents} candidates goes in as one document: {m.model_query.document_format}.
            </p>
            {m.model_query.text ? (
              <>
                <SourceLabel kind="britannica">query · {m.model_query.chars.toLocaleString()} characters</SourceLabel>
                <p className="text-source text-source--clamp">{m.model_query.text}</p>
              </>
            ) : (
              <p className="small muted">The query text is not shown: {m.model_query.note}.</p>
            )}
          </section>
        )}

        {m.candidates.length > 0 && (
          <h4 className="flowstep__title">
            <span className="flowstep__n">{m.model_query ? 3 : 2}</span> Scored candidates ({m.candidates.length})
          </h4>
        )}
        {m.candidates.length > 0 && (
          <div className="table-wrap">
            <table className="cands">
              <caption className="sr-only">Wikipedia candidates for {current.headword}</caption>
              <thead>
                <tr>
                  <th scope="col">#</th>
                  <th scope="col">Article</th>
                  <th scope="col">BM25 rank</th>
                  <th scope="col">Title sim.</th>
                  <th scope="col">Cosine</th>
                  <th scope="col">Reranker logit</th>
                </tr>
              </thead>
              <tbody>
                {m.candidates.map((c) => {
                  const chosen = c.page_id === d.page_id;
                  const span = maxLogit - minLogit || 1;
                  const w = c.rerank_logit === undefined ? 0 : ((c.rerank_logit - minLogit) / span) * 100;
                  return (
                    <tr key={c.page_id} className={chosen ? "is-chosen" : ""}>
                      <td className="mono">{c.rerank_position ?? c.best_rank}</td>
                      <td>
                        <a href={c.url} target="_blank" rel="noreferrer">
                          {c.title}
                        </a>
                        <span className="cand-excerpt">{c.excerpt.slice(0, 160)}…</span>
                      </td>
                      <td className="mono">{c.best_rank}</td>
                      <td className="mono">{num(c.title_similarity)}</td>
                      <td className="mono">{num(c.cosine, 3)}</td>
                      <td>
                        <div className="logit">
                          <div className="logit__bar" style={{ width: `${Math.max(2, w)}%` }} />
                          <span className="mono">{num(c.rerank_logit)}</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {m.article && (
          <div className="article">
            <SourceLabel kind="wikipedia">
              {m.article.title} · revision{" "}
              <a href={m.article.revision_url} target="_blank" rel="noreferrer">
                {m.article.revision_id}
              </a>{" "}
              · first {m.article.excerpt.length.toLocaleString()} of {m.article.chars.toLocaleString()} characters
            </SourceLabel>
            <p className="text-wiki text-source--clamp">{m.article.excerpt}</p>
          </div>
        )}
        <p className="mono small muted">
          Scores are model relevance signals, not proof of factual agreement. Read both sources before you rely on a match.
        </p>
      </section>
    </div>
  );
}
