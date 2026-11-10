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
  allow_leakage?: boolean;
}

export interface PredictDiagnoseResponse {
  can_proceed: boolean;
  blockers: string[];
  warnings: string[];
  suggested_target: string | null;
  dropped_leakage_columns?: string[];
  target_info?: Record<string, unknown> | null;
  row_count?: number;
  column_count?: number;
}

export interface PredictRunRequest {
  target_col?: string | null;
  task_type?: PredictTaskType;
  allow_leakage?: boolean;
}

export interface PredictSimulateRequest {
  prediction_id?: string | null;
  target_col?: string | null;
  inputs?: Record<string, string | number>;
  allow_leakage?: boolean;
}

export interface SimulationControl {
  name: string;
  type: "numeric" | "categorical";
  weight: number;
  min?: number;
  max?: number;
  step?: number;
  options?: string[];
  baseline_value: string | number;
  current_value: string | number;
  summary_hint?: string;
}

export interface SimulationContribution {
  feature: string;
  current_value: string | number;
  baseline_value: string | number;
  delta: number;
  direction: "increases" | "decreases" | "neutral";
  weight: number;
}

export interface SimulationPreset {
  id: string;
  label: string;
  inputs: Record<string, string | number>;
}

export interface PredictSimulateResponse {
  target_column: string;
  task_type: string;
  top_drivers: string[];
  quarantined_leakage: string[];
  feature_controls: SimulationControl[];
  baseline_prediction: {
    scalar: number;
    predicted_class?: string;
    probability_pct?: number;
    positive_class?: string;
    positive_probability_pct?: number;
    predicted_value?: number;
    confidence_band?: number;
  };
  simulated_prediction: {
    scalar: number;
    predicted_class?: string;
    probability_pct?: number;
    positive_class?: string;
    positive_probability_pct?: number;
    predicted_value?: number;
    confidence_band?: number;
  };
  delta: number;
  unit: string;
  factor_contributions: SimulationContribution[];
  presets: SimulationPreset[];
  executive_summary: {
    what_is_predicted: string;
    primary_drivers: string[];
    actionable_levers: string[];
  };
}

export interface LeaderboardItem {
  model?: string;
  model_name?: string;
  metric?: string;
  metric_name?: string;
  cv_mean?: number | null;
  cv_std?: number | null;
  mean_cv_score?: number | null;
  std_cv_score?: number | null;
  score?: number | null;
  std?: number | null;
  train_time_sec?: number | null;
  optimal_k?: number | null;
  inertia?: number | null;
}

export interface FeatureImportanceItem {
  feature?: string;
  name?: string;
  importance?: number | null;
  score?: number | null;
}

export interface PredictionHistory {
  id: string;
  user_file_id: string;
  task_type: string;
  target_column: string | null;
  feature_columns: string[];
  best_model_name: string | null;
  leaderboard_json?:
    | {
        leaderboard?: LeaderboardItem[];
        test_metric?: string;
        test_value?: number;
      }
    | LeaderboardItem[]
    | null;
  feature_importance_json?: Record<string, number> | FeatureImportanceItem[] | null;
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

export interface UiActionEvent {
  type: "ui_action";
  action: "switch_tab" | "switch_file" | "switch_sheet" | "update_chart" | "run_automl";
  payload: Record<string, unknown>;
  label?: string;
}

export interface ChatEngineStatus {
  online: boolean;
  provider: "ollama" | "minimal";
  model: string;
  available_models: string[];
  mode_label: string;
}

export interface FileSheetsResponse {
  file_id: string;
  active_sheet: string | null;
  sheets: Array<{ name: string; row_count: number; col_count: number }>;
  related_datasets: Array<{
    id: string;
    display_name: string;
    row_count: number;
    col_count: number;
    detected_domain: string;
  }>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  tier?: number;
  message_text: string;
  latency_ms?: number;
  created_at: string;
  actions?: UiActionEvent[];
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

