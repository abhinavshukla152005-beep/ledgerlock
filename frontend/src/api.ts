import type { Health, Probe, Run, RunSummary } from "./types";

async function unwrap<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<Health> {
  return fetch("/api/health").then((r) => unwrap<Health>(r));
}

export async function getSample(name: "expenses.csv" | "policy.yaml" | "policy-brief.txt"): Promise<string> {
  const response = await fetch(`/api/samples/${name}`);
  if (!response.ok) throw new Error(`sample ${name} unavailable`);
  return response.text();
}

export async function runAudit(file: File | null, policyText: string): Promise<Run> {
  const expenses =
    file ??
    new File([await getSample("expenses.csv")], "expenses.csv", { type: "text/csv" });
  const form = new FormData();
  form.append("expenses", expenses);
  form.append("policy_text", policyText);
  return fetch("/api/audit", { method: "POST", body: form }).then((r) => unwrap<Run>(r));
}

export function runProbe(): Promise<Probe> {
  return fetch("/api/containment/probe", { method: "POST" }).then((r) => unwrap<Probe>(r));
}

export function listRuns(): Promise<RunSummary[]> {
  return fetch("/api/runs").then((r) => unwrap<RunSummary[]>(r));
}

export function getRun(id: string): Promise<Run> {
  return fetch(`/api/runs/${id}`).then((r) => unwrap<Run>(r));
}
