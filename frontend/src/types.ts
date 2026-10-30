export type Severity = "high" | "medium" | "low";

export interface Finding {
  rule: string;
  severity: Severity;
  txn_ids: string[];
  amount: number;
  message: string;
}

export interface QuarantinedRow {
  txn_id: string;
  vendor: string;
  amount: number;
  reason: string;
  matched_patterns: string[];
}

export interface Step {
  name: string;
  status: string;
  detail: string;
  duration_ms: number;
}

export interface Run {
  id: string;
  status: "verified" | "unverified" | "error";
  verified: boolean;
  findings: Finding[];
  quarantined: QuarantinedRow[];
  steps: Step[];
  memo: string;
  llm_source: string | null;
  codegen_source: string | null;
  policy_source: string | null;
  currency: string | null;
  row_count: number;
  quarantined_count: number;
  finding_count: number;
  containment: string | null;
  backend: string | null;
  duration_ms: number;
  error: string | null;
}

export interface Health {
  status: string;
  sandbox_backend: string;
  containment: string;
  inference: string;
  model: string;
}

export interface RunSummary {
  id: string;
  created_at: string;
  status: string;
  finding_count: number;
  quarantined_count: number;
  verified: boolean;
  duration_ms: number;
}

export interface ProbePayload {
  network_egress?: string;
  root_write?: string;
  tmp_write?: string;
  secret_env_keys?: string[];
  uid?: number | null;
  cwd?: string;
  child_processes_started?: number;
  fork_error?: string;
}

export interface Probe {
  backend: string;
  containment: string;
  ok: boolean;
  timed_out: boolean;
  duration_ms: number;
  payload: ProbePayload;
  stderr: string;
  error: string | null;
}
