export type LabChartType =
  | "distribution"
  | "histogram"
  | "bar"
  | "scatter"
  | "line"
  | "heatmap"
  | "correlation"
  | "box";

export type PredictTaskType =
  | "classification"
  | "regression"
  | "clustering"
  | "timeseries"
  | null;

export interface PredictDiagnoseRequest {
  target_col?: string | null;
}

export interface PredictDiagnoseResponse {
  can_proceed: boolean;
  blockers: string[];
  warnings: string[];
  suggested_target: string | null;
  target_info?: Record<string, unknown> | null;
  row_count: number;
  column_count: number;
}

export interface PredictRunRequest {
  target_col?: string | null;
  task_type?: PredictTaskType;
}

export interface PredictionHistory {
  id: string;
  user_file_id: string;
  task_type: string;
  target_column: string | null;
  feature_columns: string[];
  best_model_name: string | null;
  leaderboard_json?: {
    leaderboard?: Array<{
      model: string;
      cv_mean: number;
      cv_std: number;
      train_time_sec?: number;
    }>;
    test_metric?: string;
    test_value?: number;
  } | null;
  feature_importance_json?: Record<string, number> | null;
  diagnostics_json?: Record<string, unknown> | null;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
}

export interface GlobalFile {
  id: string;
  sha256_hash: string;
  parquet_path: string;
  original_format: string;
  file_size_bytes: number;
  row_count: number;
  col_count: number;
  detected_domain: string;
  ref_count: number;
  created_at: string;
}

export interface UserFile {
  id: string;
  user_id: string;
  global_file_id: string;
  display_name: string;
  created_at: string;
  global_file: GlobalFile;
}

export interface User {
  id: string;
  org_id: string;
  email: string;
  role: string;
  is_active: boolean;
}

export interface AnalysisMemory {
  id: string;
  user_file_id: string;
  agent_type: string;
  query_text: string;
  context_text?: string | null;
  finding_text: string;
  evidence_json?: Record<string, unknown> | null;
  implication_text?: string | null;
  plotly_spec_json?: Record<string, unknown> | null;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  tier?: number;
  message_text: string;
  latency_ms?: number;
  created_at: string;
  artifact?: {
    type: "chart" | "forensic" | "diagnostic" | "prediction";
    data: unknown;
  } | null;
}

export interface DataProfile {
  total_rows: number;
  total_columns: number;
  health_score: number;
  numeric_columns: string[];
  categorical_columns: string[];
  columns: Record<
    string,
    {
      null_count: number;
      null_percentage: number;
      distinct_count: number;
      mean?: number;
      std?: number;
      min?: number;
      max?: number;
    }
  >;
  cleaning_recommendations?: Array<{
    column?: string;
    issue: string;
    remediation: string;
  }>;
}

export interface LabOverviewResponse {
  file_id: string;
  filename: string;
  row_count: number;
  column_count: number;
  schema: {
    columns: Record<string, { type: string; nullable: boolean }>;
  };
  profile: DataProfile;
  ref_count: number;
}

