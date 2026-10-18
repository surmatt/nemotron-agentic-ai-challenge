import type { ReactNode } from "react";
import type { DiffOp, StepName, StepStatus } from "../types";
import { Icon } from "./Icon";

export const STEP_META: Record<StepName, { numeral: string; title: string; verb: string; method: string; module: string }> = {
  extract: {
    numeral: "I",
    title: "Parse & segment",
    verb: "Parse",
    method:
      "Parse 3.5 reads the page into boxed layout blocks. Headers, footers, and page numbers move out of the text. A capitalised headword starts an entry.",
    module: "extract.py",
  },
  correct: {
    numeral: "II",
    title: "Correct OCR",
    verb: "Correct",
    method:
      "Super 3.5 VL reads an enlarged crop of each text block with the Parse text and returns corrected text. A dictionary long-s rule follows.",
    module: "correct.py",
  },
  match: {
    numeral: "III",
    title: "Match Wikipedia",
    verb: "Match",
    method:
      "BM25 search gives candidate articles. The embedder and reranker score them. Calibrated thresholds accept or reject the top candidate.",
    module: "match.py",
  },
  compare: {
    numeral: "IV",
    title: "Compare vocabulary",
    verb: "Compare",
    method:
      "Word frequencies with long-s and historical spelling normalised. Log-odds z-scores with an informative Dirichlet prior show distinctive terms.",
    module: "compare.py",
  },
  summarize: {
    numeral: "V",
    title: "Summarize differences",
    verb: "Summarize",
    method:
      "Super 3.5 VL reads the entry and the closest Wikipedia passages and lists the key differences. Each difference quotes both sources, and the code checks each quote.",
    module: "summarize.py",
  },
  document: {
    numeral: "VI",
    title: "LaTeX document",
    verb: "Typeset",
    method:
      "One LaTeX document per scan: the entry text in source order, then the source record with checksums. tectonic compiles the PDF.",
    module: "site.py",
  },
};

export const CLASS_COLOURS: Record<string, string> = {
  Text: "#e7b75f",
  "Section-header": "#ef8a62",
  Title: "#e0607e",
  "List-item": "#8cc084",
  Footnote: "#74a9cf",
  Caption: "#b9a3e3",
  Formula: "#5fc4b8",
  Table: "#d4c06a",
  Picture: "#9aa5b1",
  "Page-header": "#8f8a83",
  "Page-footer": "#8f8a83",
};

export const classColour = (cls: string) => CLASS_COLOURS[cls] ?? "#c9c2b6";

const STATUS_TEXT: Record<StepStatus, string> = {
  idle: "Not run",
  queued: "Queued",
  running: "Running",
  done: "Done",
  failed: "Failed",
};

export function StatusTag({ status }: { status: StepStatus }) {
  const icon = { idle: "dot", queued: "clock", running: "spark", done: "check", failed: "alert" }[status];
  return (
    <span className={`status status--${status}`}>
      <Icon name={icon} size={14} />
      {STATUS_TEXT[status]}
    </span>
  );
}

export function Chip({ children, tone = "plain", title }: { children: ReactNode; tone?: string; title?: string }) {
  return (
    <span className={`chip chip--${tone}`} title={title}>
      {children}
    </span>
  );
}

/** Labels that keep source text and generated analysis apart, as the static site does. */
export function SourceLabel({ kind, children }: { kind: "britannica" | "wikipedia" | "generated" | "raw"; children: ReactNode }) {
  const name = { britannica: "Source · Britannica", wikipedia: "Source · Wikipedia", generated: "Generated", raw: "Raw model output" }[kind];
  return (
    <div className={`source-label source-label--${kind}`}>
      <span>{name}</span>
      <span className="source-label__detail">{children}</span>
    </div>
  );
}

export function Diff({ ops }: { ops: DiffOp[] }) {
  return (
    <p className="diff">
      {ops.map((op, i) => {
        const text = (i ? " " : "") + op.text;
        if (op.op === "insert") return <ins key={i}>{text}</ins>;
        if (op.op === "delete") return <del key={i}>{text}</del>;
        return <span key={i}>{text}</span>;
      })}
    </p>
  );
}

export function diffStats(ops: DiffOp[] = []) {
  const words = (s: string) => (s ? s.split(" ").length : 0);
  return ops.reduce(
    (acc, op) => {
      if (op.op === "insert") acc.inserted += words(op.text);
      else if (op.op === "delete") acc.deleted += words(op.text);
      else acc.kept += words(op.text);
      return acc;
    },
    { kept: 0, inserted: 0, deleted: 0 },
  );
}

/** A value on a scale, with a tick for the acceptance threshold. */
export function Gauge({
  label,
  value,
  threshold,
  min,
  max,
  format = (v) => v.toFixed(2),
}: {
  label: string;
  value: number | null | undefined;
  threshold?: number;
  min: number;
  max: number;
  format?: (v: number) => string;
}) {
  const pos = (v: number) => `${Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100))}%`;
  const has = value !== null && value !== undefined && Number.isFinite(value);
  const passes = has && (threshold === undefined || (value as number) >= threshold);
  return (
    <div className="gauge">
      <div className="gauge__head">
        <span>{label}</span>
        <span className={`gauge__value ${has ? (passes ? "is-pass" : "is-fail") : ""}`}>
          {has ? format(value as number) : "n/a"}
          {threshold !== undefined && <span className="gauge__thr"> / ≥ {format(threshold)}</span>}
        </span>
      </div>
      <div className="gauge__track" role="img" aria-label={`${label} ${has ? format(value as number) : "not available"}`}>
        {has && <div className={`gauge__fill ${passes ? "is-pass" : "is-fail"}`} style={{ width: pos(value as number) }} />}
        {threshold !== undefined && <div className="gauge__tick" style={{ left: pos(threshold) }} />}
      </div>
    </div>
  );
}

export function Empty({ title, children, icon = "doc" }: { title: string; children?: ReactNode; icon?: string }) {
  return (
    <div className="empty">
      <Icon name={icon} size={28} />
      <h3>{title}</h3>
      {children && <div className="empty__body">{children}</div>}
    </div>
  );
}

export const short = (hash?: string, n = 10) => (hash ? `${hash.slice(0, n)}…` : "");
export const num = (v: unknown, digits = 2) => (typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "n/a");
export const seconds = (v?: number) => (v === undefined ? "" : v < 60 ? `${v.toFixed(1)} s` : `${Math.floor(v / 60)} min ${Math.round(v % 60)} s`);
