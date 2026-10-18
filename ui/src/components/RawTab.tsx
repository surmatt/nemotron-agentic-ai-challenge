import { useEffect, useState } from "react";
import { api } from "../api";
import type { StepName, WorkspaceView } from "../types";
import { STEPS } from "../types";
import { Icon } from "./Icon";
import { Empty, STEP_META, SourceLabel } from "./common";

const DESCRIPTION: Record<StepName, string> = {
  extract: "The unchanged Parse 3.5 reply with its request settings and timing.",
  correct: "One unchanged Super 3.5 VL reply per block, with prompt, usage, and finish reason.",
  match: "Candidates per entry: BM25 hits, embedder cosines, reranker logits, and the decision.",
  compare: "The generated comparison records for the accepted pairs.",
  summarize: "One unchanged Super 3.5 VL reply per pair, with the prompt, the passage IDs, usage, and finish reason.",
  document: "The LaTeX source of the scan document and whether a PDF exists.",
};

export function RawTab({ view }: { view: WorkspaceView }) {
  const [step, setStep] = useState<StepName>("extract");
  const [data, setData] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const done = view.steps[step].status === "done";

  useEffect(() => {
    setData(null);
    setError(null);
    if (!done) return;
    api
      .raw(view.raw_url.replace("{step}", step))
      .then((value) => setData(JSON.stringify(value, null, 2)))
      .catch((e: Error) => setError(e.message));
  }, [step, done, view.raw_url, view.steps[step].finished_at]);

  return (
    <div className="raw">
      <div className="seg" role="tablist" aria-label="Evidence by step">
        {STEPS.map((s) => (
          <button key={s} role="tab" aria-selected={s === step} className={s === step ? "is-on" : ""} onClick={() => setStep(s)}>
            {STEP_META[s].numeral} · {STEP_META[s].verb}
          </button>
        ))}
      </div>
      <SourceLabel kind="raw">{DESCRIPTION[step]}</SourceLabel>
      {!done && <Empty title="No saved output for this step" />}
      {error && <p className="step__error">{error}</p>}
      {data && (
        <>
          <div className="raw__tools">
            <span className="mono small muted">{(data.length / 1024).toFixed(1)} KiB</span>
            <button className="btn btn--ghost btn--sm" onClick={() => navigator.clipboard?.writeText(data)}>
              <Icon name="copy" size={14} /> Copy
            </button>
          </div>
          <pre className="raw__pre">{data.length > 400_000 ? data.slice(0, 400_000) + "\n… (truncated in the view)" : data}</pre>
        </>
      )}
      {view.failures.length > 0 && (
        <div className="failures">
          <h4>Recorded failures</h4>
          <ul>
            {view.failures.map((f, i) => (
              <li key={i} className="mono small">
                {f.at} · {f.stage}
                {f.block_index !== undefined ? ` · block ${f.block_index}` : ""}
                {f.entry_id ? ` · ${f.entry_id}` : ""} · {f.error_type}: {f.error}
              </li>
            ))}
          </ul>
        </div>
      )}
      {view.history.length > 0 && (
        <p className="mono small muted">Earlier outputs kept in history/: {view.history.join(", ")}</p>
      )}
    </div>
  );
}
