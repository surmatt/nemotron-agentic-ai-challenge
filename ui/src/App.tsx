import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { Icon } from "./components/Icon";
import { Library } from "./components/Library";
import { Overview } from "./components/Overview";
import { Workspace } from "./components/Workspace";
import type { CorpusIndex, ServicesReport, UploadRow } from "./types";

const SERVICE_LABELS = { parse: "Parse 3.5", super: "Super 3.5 VL", retrieval: "Embed + rerank", wikipedia: "Wikipedia API" } as const;

function useHashRoute(): [string, (route: string) => void] {
  const read = () => window.location.hash.replace(/^#\/?/, "");
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const on = () => setRoute(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return [route, (next: string) => (window.location.hash = `/${next}`)];
}

export default function App() {
  const [route, go] = useHashRoute();
  const [uploads, setUploads] = useState<UploadRow[]>([]);
  const [corpus, setCorpus] = useState<CorpusIndex | null>(null);
  const [services, setServices] = useState<ServicesReport | null>(null);
  const [checking, setChecking] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const refreshUploads = useCallback(() => {
    api.uploads().then(setUploads).catch(() => undefined);
  }, []);
  const checkServices = useCallback((live: boolean) => {
    setChecking(live);
    api
      .services(live)
      .then(setServices)
      .catch(() => undefined)
      .finally(() => setChecking(false));
  }, []);

  const refreshCorpus = useCallback(() => {
    api.corpus().then(setCorpus).catch(() => undefined);
  }, []);

  useEffect(() => {
    refreshUploads();
    refreshCorpus();
    checkServices(false);
  }, [refreshUploads, refreshCorpus, checkServices]);

  const upload = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    try {
      const { id } = await api.upload(file);
      refreshUploads();
      go(`upload/${id}`);
    } catch (e) {
      setUploadError((e as Error).message);
    } finally {
      setUploading(false);
    }
  };

  const [kind, id] = route.split("/");
  const open = kind === "upload" || kind === "corpus" ? (kind as "upload" | "corpus") : null;

  return (
    <div className="app">
      <a className="skip" href="#main">
        Skip to content
      </a>
      <header className="masthead">
        <button className="brand" onClick={() => go("")} aria-label="Overview">
          <span className="brand__mark" aria-hidden>
            B<span>⇄</span>W
          </span>
          <span className="brand__text">
            <span className="brand__name">Britannica ⇄ Wikipedia</span>
            <span className="brand__sub">Nemotron pipeline workbench</span>
          </span>
        </button>
        <div className="services" aria-label="Service status">
          {services &&
            (Object.keys(SERVICE_LABELS) as (keyof typeof SERVICE_LABELS)[]).map((key) => {
              const row = services.services[key];
              return (
                <span key={key} className={`svc svc--${row.status}`} title={row.detail ?? row.status.replace("_", " ")}>
                  <i aria-hidden /> {SERVICE_LABELS[key]}
                  <span className="sr-only"> {row.status}</span>
                </span>
              );
            })}
          <button className="btn btn--ghost btn--sm" onClick={() => checkServices(true)} disabled={checking}>
            <Icon name="refresh" size={14} /> {checking ? "Checking…" : services?.checked_at ? "Re-check" : "Check services"}
          </button>
        </div>
      </header>
      <div className="shell">
        <Library
          uploads={uploads}
          corpus={corpus}
          active={route}
          onUpload={upload}
          onOpen={go}
          uploading={uploading}
          uploadError={uploadError}
        />
        <main id="main" className="main">
          {open && id ? (
            <Workspace key={route} kind={open} id={id} onChanged={refreshUploads} onOpenUpload={(u) => go(`upload/${u}`)} />
          ) : (
            <Overview
              corpus={corpus}
              onPickCorpus={() => corpus?.pages[0] && go(`corpus/${corpus.pages[0].row_index}`)}
              onSiteBuilt={refreshCorpus}
            />
          )}
        </main>
      </div>
    </div>
  );
}
