import { useMemo, useRef, useState } from "react";
import type { CorpusIndex, UploadRow } from "../types";
import { STEPS } from "../types";
import { Icon } from "./Icon";
import { STEP_META } from "./common";

export function Library({
  uploads,
  corpus,
  active,
  onUpload,
  onOpen,
  uploading,
  uploadError,
}: {
  uploads: UploadRow[];
  corpus: CorpusIndex | null;
  active: string;
  onUpload: (file: File) => void;
  onOpen: (route: string) => void;
  uploading: boolean;
  uploadError: string | null;
}) {
  const [tab, setTab] = useState<"workbench" | "corpus">(active.startsWith("corpus") ? "corpus" : "workbench");
  const [drag, setDrag] = useState(false);
  const [filter, setFilter] = useState("all");
  const input = useRef<HTMLInputElement>(null);

  const pages = useMemo(
    () => (corpus?.pages ?? []).filter((p) => (filter === "all" ? true : filter === "matched" ? p.accepted > 0 : p.status === filter)),
    [corpus, filter],
  );
  const pick = (files: FileList | null) => {
    if (files?.[0]) onUpload(files[0]);
  };

  return (
    <aside className="library" aria-label="Scan library">
      <div className="library__tabs" role="tablist">
        <button role="tab" aria-selected={tab === "workbench"} className={tab === "workbench" ? "is-on" : ""} onClick={() => setTab("workbench")}>
          Workbench <span className="tab__n">{uploads.length}</span>
        </button>
        <button role="tab" aria-selected={tab === "corpus"} className={tab === "corpus" ? "is-on" : ""} onClick={() => setTab("corpus")}>
          Corpus <span className="tab__n">{corpus?.pages.length ?? 100}</span>
        </button>
      </div>

      {tab === "workbench" && (
        <>
          <div
            className={`drop ${drag ? "is-drag" : ""} ${uploading ? "is-busy" : ""}`}
            onDragOver={(e) => {
              e.preventDefault();
              setDrag(true);
            }}
            onDragLeave={() => setDrag(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDrag(false);
              pick(e.dataTransfer.files);
            }}
          >
            <input ref={input} type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files)} />
            <Icon name="upload" size={22} />
            <p className="drop__title">{uploading ? "Uploading…" : "Drop a page scan"}</p>
            <p className="drop__hint">JPEG or PNG up to 8 MiB go to Parse as they are. Other images are converted.</p>
            <button className="btn btn--primary btn--sm" onClick={() => input.current?.click()} disabled={uploading}>
              Choose image
            </button>
            {uploadError && (
              <p className="drop__error" role="alert">
                {uploadError}
              </p>
            )}
          </div>
          <ul className="uploads">
            {uploads.map((u) => (
              <li key={u.id}>
                <button className={`upload-item ${active === `upload/${u.id}` ? "is-on" : ""}`} onClick={() => onOpen(`upload/${u.id}`)}>
                  <img src={`/api/uploads/${u.id}/image?w=96`} alt="" loading="lazy" />
                  <span className="upload-item__text">
                    <span className="upload-item__name">{u.filename}</span>
                    <span className="mono small muted">
                      {u.source.kind === "corpus_copy" ? `corpus row ${u.source.row_index}` : "upload"} · {u.uploaded_at.slice(5, 16).replace("T", " ")}
                    </span>
                    <span className="pips" aria-label="Step status">
                      {STEPS.map((s) => (
                        <i key={s} className={`pip pip--${u.steps[s]}`} title={`${STEP_META[s].title}: ${u.steps[s]}`} />
                      ))}
                    </span>
                  </span>
                </button>
              </li>
            ))}
            {!uploads.length && <li className="muted small pad">No uploads yet. Drop a scan, or open a corpus scan and run it live.</li>}
          </ul>
        </>
      )}

      {tab === "corpus" && (
        <>
          <div className="corpus-filter">
            <label className="sr-only" htmlFor="corpus-filter">
              Filter corpus scans
            </label>
            <select id="corpus-filter" value={filter} onChange={(e) => setFilter(e.target.value)}>
              <option value="all">All 100 scans</option>
              <option value="matched">With accepted matches</option>
              <option value="ok">Parsed: ok</option>
              <option value="plate">Plates</option>
              <option value="blank_or_sparse">Blank or sparse</option>
              <option value="parse_failed">Parse failed</option>
              <option value="no_run">No saved run</option>
            </select>
            {!corpus?.has_artifacts && <p className="small muted">No saved stage artifacts. Images only.</p>}
          </div>
          <ul className="corpus-grid">
            {pages.map((p) => (
              <li key={p.row_index}>
                <button
                  className={`corpus-card ${active === `corpus/${p.row_index}` ? "is-on" : ""}`}
                  onClick={() => onOpen(`corpus/${p.row_index}`)}
                  title={p.running_header ?? p.filename}
                >
                  <img src={`/api/corpus/${p.row_index}/image?w=160`} alt={`Scan row ${p.row_index}`} loading="lazy" />
                  <span className="corpus-card__meta">
                    <span className="mono">{p.row_index}</span>
                    <span className={`st st--${p.status}`}>{p.status.replaceAll("_", " ")}</span>
                  </span>
                  {p.entries > 0 && (
                    <span className="corpus-card__counts mono">
                      {p.entries}e · {p.accepted}m
                    </span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </aside>
  );
}
