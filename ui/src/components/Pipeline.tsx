import type { StepName, StepState, WorkspaceView } from "../types";
import { STEPS } from "../types";
import { Icon } from "./Icon";
import { STEP_META, StatusTag, seconds } from "./common";

function summaryLine(step: StepName, state: StepState): string | null {
  const s = (state.summary ?? {}) as Record<string, any>;
  if (state.status !== "done" || !state.summary) return null;
  switch (step) {
    case "extract":
      return s.blocks !== undefined
        ? `${s.blocks} blocks · ${s.furniture} furniture · ${s.entries} entries`
        : `${s.parsed ?? "?"} of ${s.scans ?? "?"} scans parsed · ${s.entries ?? "?"} entries`;
    case "correct":
      return s.blocks_requested !== undefined && s.blocks_corrected !== undefined
        ? `${s.blocks_corrected} of ${s.blocks_requested} blocks corrected${s.blocks_failed ? ` · ${s.blocks_failed} failed` : ""}`
        : null;
    case "match":
      return `${s.accepted ?? 0} accepted · ${s.rejected ?? 0} rejected${s.errors ? ` · ${s.errors} errors` : ""} · ${s.mode} mode`;
    case "compare":
      return s.pairs ? `${s.pairs} pairs · mean cosine ${s.mean_frequency_cosine}` : (s.note as string) ?? "no pairs";
    case "document":
      if (s.latex)
        return `${s.latex.compiled} of ${s.scan_pages} PDFs compiled · ${s.entry_pages} entry pages · static site`;
      return `${s.pdf ? "PDF compiled" : ".tex only, no PDF"} · ${s.entries} entries · ${s.entry_text} text`;
  }
}

const NEEDS: Record<StepName, StepName[]> = {
  extract: [],
  correct: ["extract"],
  match: ["extract"],
  compare: ["match"],
  document: ["extract"],
};
const REUSABLE: StepName[] = ["extract", "correct"];

export function rerunPlan(view: WorkspaceView, step: StepName): StepName[] {
  const index = STEPS.indexOf(step);
  const plan = new Set<StepName>([step, ...STEPS.slice(index + 1).filter((s) => ["done", "failed"].includes(view.steps[s].status))]);
  if (view.kind === "corpus") {
    const needed = new Set(plan);
    [...STEPS].reverse().forEach((s) => needed.has(s) && NEEDS[s].forEach((n) => needed.add(n)));
    STEPS.slice(0, index).forEach((s) => {
      if (needed.has(s) && !(REUSABLE.includes(s) && view.steps[s].status === "done")) plan.add(s);
    });
  }
  return STEPS.filter((s) => plan.has(s));
}

export function Pipeline({
  view,
  busy,
  onRun,
  onStep,
}: {
  view: WorkspaceView;
  busy: boolean;
  onRun: (steps: StepName[] | "all") => void;
  onStep: (step: StepName) => void;
}) {
  const editable = view.kind === "upload";
  const anyActive = STEPS.some((s) => ["running", "queued"].includes(view.steps[s].status));
  const remaining = STEPS.filter((s) => view.steps[s].status !== "done");
  const planText = (step: StepName) => rerunPlan(view, step).map((s) => STEP_META[s].title).join(" → ");

  return (
    <section className="pipeline" aria-label="Pipeline steps">
      <div className="pipeline__bar">
        <div>
          <h2 className="eyebrow">The pipeline</h2>
          <p className="pipeline__hint">
            {editable
              ? "Run the whole chain, or run one step at a time and inspect what it did."
              : "Saved stage artifacts for this pinned scan. A re-run copies the scan into the workbench, reuses the saved earlier outputs, and leaves these artifacts unchanged."}
          </p>
        </div>
        {editable && (
          <button
            className="btn btn--primary"
            disabled={busy || anyActive}
            onClick={() => onRun("all")}
            title="Calls Parse 3.5, Super 3.5 VL, the Wikipedia API, and the embedder and reranker"
          >
            <Icon name="play" size={16} />
            {remaining.length === 0 || remaining.length === STEPS.length
              ? "Run all steps"
              : `Run remaining (${remaining.length})`}
          </button>
        )}
      </div>
      <ol className="steps">
        {STEPS.map((step) => {
          const state = view.steps[step];
          const meta = STEP_META[step];
          const progress = state.progress;
          const pct = progress && progress.total ? Math.round((progress.done / progress.total) * 100) : null;
          const blocked = state.blocked_by;
          const active = state.status === "running" || state.status === "queued";
          return (
            <li key={step} className={`step step--${state.status}`}>
              <div className="step__numeral" aria-hidden>
                {meta.numeral}
              </div>
              <div className="step__body">
                <div className="step__head">
                  <h3>{meta.title}</h3>
                  <StatusTag status={state.status} />
                </div>
                <div className="step__models">
                  {state.models.length ? (
                    state.models.map((m) => (
                      <code key={m} className="model">
                        {m.replace("nvidia/", "")}
                      </code>
                    ))
                  ) : (
                    <code className="model model--local">local · no model</code>
                  )}
                </div>
                {state.status === "running" && (
                  <div className="progress" aria-live="polite">
                    <div className="progress__track">
                      <div
                        className={`progress__fill ${pct === null ? "is-indeterminate" : ""}`}
                        style={pct === null ? undefined : { width: `${pct}%` }}
                      />
                    </div>
                    <span className="progress__label">
                      {progress?.label}
                      {progress && progress.total > 0 && ` · ${progress.done}/${progress.total}`}
                    </span>
                  </div>
                )}
                {summaryLine(step, state) && <p className="step__summary">{summaryLine(step, state)}</p>}
                {state.status === "failed" && state.error && <p className="step__error">{state.error}</p>}
                {state.note && state.status !== "done" && <p className="step__note">{state.note}</p>}
                {state.seeded_from && state.status === "done" && (
                  <p className="step__note" title={state.seeded_from.path}>
                    Reused from the saved corpus run{state.seeded_from.saved_at ? ` of ${state.seeded_from.saved_at.slice(0, 16).replace("T", " ")}` : ""}
                  </p>
                )}
                <div className="step__foot">
                  <span className="step__time">
                    {state.elapsed_seconds !== undefined && state.status !== "running" && (
                      <>
                        <Icon name="clock" size={13} /> {seconds(state.elapsed_seconds)}
                      </>
                    )}
                    {view.kind === "corpus" && state.finished_at && <> saved {state.finished_at.slice(0, 16).replace("T", " ")}</>}
                  </span>
                  <button
                    className="btn btn--ghost btn--sm"
                    disabled={busy || anyActive || (editable && Boolean(blocked))}
                    onClick={() => onStep(step)}
                    title={
                      editable && blocked
                        ? `Run ${STEP_META[blocked].title} first`
                        : `${editable ? "Runs" : "Copies the scan into the workbench and runs"}: ${planText(step)}`
                    }
                  >
                    <Icon name={state.status === "done" || state.status === "failed" ? "replay" : "play"} size={14} />
                    {active ? "Working" : state.status === "done" ? "Re-run" : state.status === "failed" ? "Retry" : "Run"}
                    {!active && rerunPlan(view, step).length > 1 && <span className="step__plus">+{rerunPlan(view, step).length - 1}</span>}
                  </button>
                </div>
                {editable && blocked && state.status === "idle" && (
                  <p className="step__blocked">Needs {STEP_META[blocked].title.toLowerCase()} first.</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
