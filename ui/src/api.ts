import type { CorpusIndex, ServicesReport, SiteStatus, StepName, UploadRow, WorkspaceView } from "./types";

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail)) detail = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {
      /* the body is not JSON */
    }
    throw new ApiError(detail, response.status);
  }
  return response.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  services: (live: boolean) => request<ServicesReport>(`/api/services?live=${live}`),
  uploads: () => request<UploadRow[]>("/api/uploads"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<{ id: string }>("/api/uploads", { method: "POST", body: form });
  },
  fromCorpus: (row: number) => request<{ id: string }>(`/api/uploads/from-corpus/${row}`, { method: "POST" }),
  uploadView: (id: string) => request<WorkspaceView>(`/api/uploads/${id}`),
  run: (id: string, steps: StepName[] | "all") =>
    request<{ started: StepName[] }>(`/api/uploads/${id}/run`, json(steps === "all" ? { all: true } : { steps })),
  rerun: (id: string, step: StepName) => request<{ started: StepName[] }>(`/api/uploads/${id}/rerun`, json({ step })),
  corpusRerun: (row: number, step: StepName) =>
    request<{ id: string; seeded: StepName[]; started: StepName[] }>(`/api/corpus/${row}/rerun`, json({ step })),
  corpus: () => request<CorpusIndex>("/api/corpus"),
  corpusView: (row: string) => request<WorkspaceView>(`/api/corpus/${row}`),
  raw: (url: string) => request<unknown>(url),
  site: () => request<SiteStatus>("/api/site"),
  buildSite: () => request<SiteStatus>("/api/site/build", { method: "POST" }),
};
