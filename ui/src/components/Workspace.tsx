import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { StepName, WorkspaceView } from "../types";
import { STEPS } from "../types";
import { BlockInspector } from "./BlockInspector";
import { BlocksTab } from "./BlocksTab";
import { CompareTab } from "./CompareTab";
import { DocumentTab } from "./DocumentTab";
import { EntriesTab } from "./EntriesTab";
import { Icon } from "./Icon";
import { MatchTab } from "./MatchTab";
import { Pipeline } from "./Pipeline";
import { RawTab } from "./RawTab";
import { ScanViewer } from "./ScanViewer";
import { Chip, Empty, short } from "./common";

type Tab = "scan" | "blocks" | "entries" | "match" | "compare" | "document" | "raw";
const TABS: { id: Tab; label: string; step?: StepName }[] = [
  { id: "scan", label: "Scan & layout", step: "extract" },
  { id: "blocks", label: "Blocks & corrections", step: "correct" },
  { id: "entries", label: "Entries", step: "extract" },
  { id: "match", label: "Matching", step: "match" },
  { id: "compare", label: "Comparison", step: "compare" },
  { id: "document", label: "LaTeX document", step: "document" },
  { id: "raw", label: "Raw evidence" },
];

export function Workspace({
  kind,
  id,
  onChanged,
  onOpenUpload,
}: {
  kind: "upload" | "corpus";
  id: string;
  onChanged: () => void;
  onOpenUpload: (id: string) => void;
}) {
  const [view, setView] = useState<WorkspaceView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("scan");
  const [selected, setSelected] = useState<number | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  const [highlight, setHighlight] = useState<Set<number>>(new Set());
  const [matchFocus, setMatchFocus] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const lastStatus = useRef<string>("");

  const load = useCallback(async () => {
    try {
      const next = kind === "upload" ? await api.uploadView(id) : await api.corpusView(id);
      setView(next);
      setError(null);
      const status = STEPS.map((s) => next.steps[s].status).join(",");
      if (status !== lastStatus.current) {
        lastStatus.current = status;
        onChanged();
      }
      return next;
    } catch (e) {
      setError((e as Error).message);
      return null;
    }
  }, [kind, id, onChanged]);

  useEffect(() => {
    setView(null);
    setSelected(null);
    setHighlight(new Set());
    setTab("scan");
    lastStatus.current = "";
    let stop = false;
    const tick = async () => {
      const next = await load();
      if (stop) return;
      const active = next && STEPS.some((s) => ["running", "queued"].includes(next.steps[s].status));
      timer.current = window.setTimeout(tick, active ? 1200 : 6000);
    };
    tick();
    return () => {
      stop = true;
      window.clearTimeout(timer.current);
    };
  }, [load]);

  const run = (steps: StepName[] | "all") => track(() => api.run(id, steps));

  const runStep = async (step: StepName) => {
    if (kind === "upload") return track(() => api.rerun(id, step));
    setBusy(true);
    try {
      const { id: uploadId } = await api.corpusRerun(Number(id), step);
      onOpenUpload(uploadId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const track = async (call: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await call();
      await load();
      window.clearTimeout(timer.current);
      const poll = async () => {
        const next = await load();
        if (next && STEPS.some((s) => ["running", "queued"].includes(next.steps[s].status))) {
          timer.current = window.setTimeout(poll, 1200);
        }
      };
      timer.current = window.setTimeout(poll, 800);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const copyToWorkbench = async () => {
    setBusy(true);
    try {
      const { id: uploadId } = await api.fromCorpus(Number(id));
      onOpenUpload(uploadId);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (!view)
    return error ? (
      <Empty title="Could not load this scan" icon="alert">
        {error}
      </Empty>
    ) : (
      <div className="skeleton" aria-busy="true" aria-label="Loading" />
    );

  const locate = (indexes: number[]) => {
    setHighlight(new Set(indexes));
    setSelected(indexes[0] ?? null);
    setTab("scan");
  };
  const meta = view.meta;

  return (
    <div className="workspace">
      <header className="ws-head">
        <div className="ws-head__title">
          <p className="eyebrow">
            {view.kind === "upload" ? (meta.source?.kind === "corpus_copy" ? "Workbench copy of a pinned scan" : "Uploaded scan") : "Pinned corpus scan · read-only"}
          </p>
          <h1>{view.title}</h1>
          <p className="mono small muted">
            {view.kind === "corpus" ? `${meta.page_id} · ` : ""}
            image sha256 {short(view.scan.sha256, 12)}
            {view.scan.width ? ` · ${view.scan.width}×${view.scan.height}px` : ""}
            {meta.image?.converted ? ` · converted to JPEG (${meta.image.conversion.reasons.join(", ")})` : ""}
          </p>
        </div>
        <div className="ws-head__actions">
          {view.kind === "upload" && meta.source?.kind === "upload" && <Chip tone="warn">not part of the pinned sample</Chip>}
          {view.kind === "corpus" && (
            <button className="btn btn--ghost" onClick={copyToWorkbench} disabled={busy} title="Copy this scan into the workbench to run the steps live">
              <Icon name="play" size={14} /> Run live in workbench
            </button>
          )}
        </div>
      </header>

      {error && (
        <div className="alert" role="alert">
          <Icon name="alert" size={16} /> {error}
          <button className="link-btn" onClick={() => setError(null)}>
            Dismiss
          </button>
        </div>
      )}

      <Pipeline view={view} busy={busy} onRun={run} onStep={runStep} />

      <div className="tabs" role="tablist" aria-label="Views">
        {TABS.map((t) => {
          const ready = !t.step || view.steps[t.step].status === "done";
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={tab === t.id}
              className={`tab ${tab === t.id ? "is-on" : ""} ${ready ? "" : "is-pending"}`}
              onClick={() => setTab(t.id)}
            >
              {t.label}
              {t.id === "entries" && view.entries.length > 0 && <span className="tab__n">{view.entries.length}</span>}
            </button>
          );
        })}
      </div>

      <div className="panel" role="tabpanel">
        {tab === "scan" && (
          <div className="scan-split">
            <ScanViewer
              imageUrl={view.scan.image_url}
              width={view.scan.width}
              height={view.scan.height}
              page={view.page}
              selected={selected}
              hovered={hovered}
              highlight={highlight}
              onSelect={(i) => {
                setSelected(i);
                if (i === null) setHighlight(new Set());
              }}
              onHover={setHovered}
            />
            {view.page ? (
              <BlockInspector view={view} index={selected} onClose={() => { setSelected(null); setHighlight(new Set()); }} />
            ) : (
              <aside className="inspector">
                <Empty title="No layout yet" icon="layers">
                  {view.kind === "upload"
                    ? "Run step I. Parse 3.5 will draw a box around each block it reads."
                    : "No saved extract run covers this scan. Use “Run live in workbench”."}
                </Empty>
              </aside>
            )}
          </div>
        )}
        {tab === "blocks" && <BlocksTab view={view} onLocate={(i) => locate([i])} />}
        {tab === "entries" && (
          <EntriesTab
            view={view}
            onLocate={locate}
            onOpenMatch={(entryId) => {
              setMatchFocus(entryId);
              setTab("match");
            }}
          />
        )}
        {tab === "match" && (
          <MatchTab
            view={view}
            focus={matchFocus}
            onApplyRule={kind === "upload" ? () => track(() => api.reapplyMatch(id)) : undefined}
            busy={busy || view.running}
          />
        )}
        {tab === "compare" && <CompareTab view={view} />}
        {tab === "document" && <DocumentTab view={view} />}
        {tab === "raw" && <RawTab view={view} />}
      </div>
    </div>
  );
}
