import { useEffect, useState } from "react";
import { api } from "../api";
import type { CorpusIndex, SiteStatus } from "../types";
import { STEPS } from "../types";
import { Icon } from "./Icon";
import { STEP_META } from "./common";

const MODELS: Record<string, string> = {
  extract: "nemotron-3.5-parse · shared endpoint",
  correct: "Nemotron-3.5-Super-VL · Token Factory",
  match: "BM25 + embed-vl-1b-v2 + rerank-vl-1b-v2",
  compare: "local statistics",
  summarize: "Nemotron-3.5-Super-VL + embed-vl-1b-v2",
  document: "LaTeX · tectonic",
};

function SitePanel({ onBuilt }: { onBuilt: () => void }) {
  const [site, setSite] = useState<SiteStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stop = false;
    let timer: number | undefined;
    let wasRunning = false;
    const tick = async () => {
      const next = await api.site().catch(() => null);
      if (stop || !next) return;
      setSite(next);
      if (wasRunning && !next.running) onBuilt();
      wasRunning = next.running;
      timer = window.setTimeout(tick, next.running ? 2000 : 15000);
    };
    tick();
    return () => {
      stop = true;
      window.clearTimeout(timer);
    };
  }, [onBuilt]);

  const build = async () => {
    setError(null);
    try {
      setSite(await api.buildSite());
      window.setTimeout(async () => setSite(await api.site()), 1500);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const sum = site?.summary;
  return (
    <section className="site-panel" aria-label="Static site and LaTeX">
      <div className="site-panel__text">
        <h2 className="eyebrow">Static site and LaTeX · site.py</h2>
        <h3>One document per scan</h3>
        <p className="small">
          The site stage writes one HTML page per scan and per entry, and one LaTeX document per scan. tectonic compiles the
          PDFs. Brown sections hold Britannica text, blue sections hold Wikipedia text, and grey sections hold generated
          analysis.
        </p>
        {site?.running ? (
          <p className="mono small site-panel__busy" aria-live="polite">
            <Icon name="refresh" size={13} /> Building since {site.started_at?.slice(11, 19)} UTC. The first build downloads
            the LaTeX packages for tectonic.
          </p>
        ) : sum ? (
          <p className="mono small muted">
            Built {sum.finished_at.slice(0, 16).replace("T", " ")} · {sum.scan_pages} scan pages · {sum.entry_pages} entry
            pages · {sum.latex.compiled} of {sum.scan_pages} PDFs compiled
            {sum.latex.failed.length ? ` · ${sum.latex.failed.length} LaTeX failures` : ""} ·{" "}
            {sum.latex.engine ?? sum.latex.note}
          </p>
        ) : (
          <p className="mono small muted">The site stage has not run yet.</p>
        )}
        {(site?.error || error) && (
          <p className="step__error" role="alert">
            {site?.error || error}
          </p>
        )}
      </div>
      <div className="site-panel__actions">
        {site?.built && (
          <a className="btn btn--primary" href={site.url} target="_blank" rel="noreferrer">
            <Icon name="external" size={15} /> Open static site
          </a>
        )}
        <button className="btn btn--ghost" onClick={build} disabled={!site || site.running}>
          <Icon name={site?.built ? "replay" : "play"} size={15} /> {site?.running ? "Building…" : site?.built ? "Rebuild site" : "Build site"}
        </button>
      </div>
    </section>
  );
}

export function Overview({
  corpus,
  onPickCorpus,
  onSiteBuilt,
}: {
  corpus: CorpusIndex | null;
  onPickCorpus: () => void;
  onSiteBuilt: () => void;
}) {
  const s = corpus?.summaries ?? {};
  const ext = s.extract as Record<string, any> | null | undefined;
  const cor = s.correct as Record<string, any> | null | undefined;
  const mat = s.match as Record<string, any> | null | undefined;
  const com = s.compare as Record<string, any> | null | undefined;
  const sum = s.summarize as Record<string, any> | null | undefined;
  const sit = s.site as Record<string, any> | null | undefined;
  const stats: [string, string | number, string][] = [
    ["Scans parsed", ext ? `${ext.parsed}/${ext.scans}` : "—", ext ? `${(ext.failed_scans ?? []).length} Parse failures` : "no saved run"],
    ["Entries", ext?.entries ?? "—", ext ? `${ext.headword_entries} with a headword` : "no saved run"],
    ["Blocks corrected", cor ? cor.blocks_corrected : "—", cor ? `of ${cor.blocks_requested} sent to Super VL` : "no saved run"],
    ["Accepted matches", mat ? mat.accepted : "—", mat ? `${mat.searched} searched · ${mat.mode} mode` : "no saved run"],
    ["Compared pairs", com ? com.pairs : "—", com ? `mean cosine ${com.mean_frequency_cosine}` : "no saved run"],
    ["Summarized pairs", sum ? sum.ok : "—", sum ? `${sum.differences_with_quotes} of ${sum.differences} differences with both quotes found` : "no saved run"],
    ["LaTeX PDFs", sit ? sit.latex.compiled : "—", sit ? `of ${sit.scan_pages} scan documents` : "no saved run"],
  ];
  return (
    <div className="overview">
      <section className="hero">
        <p className="eyebrow">Historical Britannica scans ⇄ English Wikipedia</p>
        <h1>
          Follow a page <em>from ink to evidence.</em>
        </h1>
        <p className="hero__lede">
          Drop a scan into the workbench and run the six stages one at a time, or all at once. Every step keeps its raw model
          output, so you can check each box, correction, match, and term against the source.
        </p>
        <div className="hero__cta">
          <button className="btn btn--ghost" onClick={onPickCorpus}>
            <Icon name="book" size={16} /> Browse the 100 pinned scans
          </button>
        </div>
      </section>

      <ol className="flow" aria-label="Pipeline stages">
        {STEPS.map((step, i) => (
          <li key={step} className="flow__step" style={{ animationDelay: `${i * 90}ms` }}>
            <span className="flow__numeral">{STEP_META[step].numeral}</span>
            <h3>{STEP_META[step].title}</h3>
            <p>{STEP_META[step].method}</p>
            <code className="model">{MODELS[step]}</code>
            <span className="flow__module mono">{STEP_META[step].module}</span>
          </li>
        ))}
      </ol>

      <section className="ledger" aria-label="Saved corpus run">
        <h2 className="eyebrow">Saved corpus run · artifacts/</h2>
        <div className="ledger__grid">
          {stats.map(([label, value, note]) => (
            <div key={label} className="ledger__cell">
              <span className="ledger__v">{value}</span>
              <span className="ledger__k">{label}</span>
              <span className="ledger__n mono">{note}</span>
            </div>
          ))}
        </div>
        {!corpus?.has_artifacts && (
          <p className="small muted">
            No stage artifacts found. Run <code>uv run nemotron-challenge run extract</code> (and the later stages) to fill this
            ledger. The workbench runs uploads without them.
          </p>
        )}
      </section>

      <SitePanel onBuilt={onSiteBuilt} />
    </div>
  );
}
