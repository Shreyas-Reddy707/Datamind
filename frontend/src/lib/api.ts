import {
  ChatEngineStatus,
  ChatMessage,
  FileSheetsResponse,
  LabChartType,
  LabOverviewResponse,
  LabQueryPayload,
  LabQueryResponse,
  PredictionHistory,
  PredictDiagnoseRequest,
  PredictDiagnoseResponse,
  PredictRunRequest,
  PredictSimulateRequest,
  PredictSimulateResponse,
  UiActionEvent,
  User,
  UserFile,
  AnalysisMemory,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "";

export class ApiError extends Error {
  errorCode: string;
  requestId: string;
  status: number;

  constructor(status: number, errorCode: string, message: string, requestId: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.errorCode = errorCode;
    this.requestId = requestId;
  }
}

// In-memory access token storage (OWASP: avoid script-readable localStorage)
let inMemoryAccessToken: string | null = null;

export function getStoredToken(): string | null {
  return inMemoryAccessToken;
}

export function setStoredToken(token: string | null) {
  inMemoryAccessToken = token;
}

// Single in-flight refresh promise shared among concurrent 401 callers
let inFlightRefreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (inFlightRefreshPromise) {
    return inFlightRefreshPromise;
  }

  inFlightRefreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        setStoredToken(null);
        return null;
      }
      const data = await res.json();
      if (data.access_token) {
        setStoredToken(data.access_token);
        return data.access_token;
      }
    } catch {
      setStoredToken(null);
    } finally {
      inFlightRefreshPromise = null;
    }
    return null;
  })();

  return inFlightRefreshPromise;
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  isRetry = false
): Promise<T> {
  let token = getStoredToken();
  if (!token && !isRetry && !endpoint.startsWith("/api/v1/auth/")) {
    token = await refreshAccessToken();
  }

  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  if (token && !headers["Authorization"]) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Prevent chunked encoding issues with non-chunked body buffer
  if (
    options.body &&
    typeof options.body === "string" &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
    headers["Content-Length"] = new TextEncoder().encode(options.body).length.toString();
  }

  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
    credentials: "include",
  });

  // Handle rotating refresh cookie flow if access token expired (status 401)
  if (
    response.status === 401 &&
    !isRetry &&
    endpoint !== "/api/v1/auth/refresh" &&
    endpoint !== "/api/v1/auth/login"
  ) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      return apiFetch<T>(endpoint, options, true);
    }
  }

  if (!response.ok) {
    let errorCode = "UNKNOWN_ERROR";
    let message = `Request failed with status ${response.status}`;
    let requestId = "";

    try {
      const errorJson = await response.json();
      if (errorJson.error_code) errorCode = errorJson.error_code;
      if (errorJson.message) {
        message = errorJson.message;
      } else if (errorJson.detail) {
        if (Array.isArray(errorJson.detail)) {
          message = errorJson.detail
            .map((d: { loc?: (string | number)[]; msg?: string }) => {
              const field = d.loc && d.loc.length > 1 ? d.loc.slice(1).join(".") : "field";
              return `${field}: ${d.msg || "Invalid"}`;
            })
            .join("; ");
          errorCode = "VALIDATION_ERROR";
        } else if (typeof errorJson.detail === "string") {
          message = errorJson.detail;
          errorCode = "VALIDATION_ERROR";
        }
      }
      if (errorJson.request_id) requestId = errorJson.request_id;
    } catch {
      // response was not JSON
    }

    throw new ApiError(response.status, errorCode, message, requestId);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

export const api = {
  auth: {
    async login(email: string, password: string): Promise<{ access_token: string; token_type: string }> {
      const res = await apiFetch<{ access_token: string; token_type: string }>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      setStoredToken(res.access_token);
      return res;
    },
    async register(email: string, password: string, org_name?: string): Promise<{ access_token: string; token_type: string }> {
      const res = await apiFetch<{ access_token: string; token_type: string }>("/api/v1/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, org_name: org_name || "Personal" }),
      });
      setStoredToken(res.access_token);
      return res;
    },
    async guest(): Promise<{ access_token: string; token_type: string }> {
      const res = await apiFetch<{ access_token: string; token_type: string }>("/api/v1/auth/guest", {
        method: "POST",
        body: JSON.stringify({}),
      });
      setStoredToken(res.access_token);
      return res;
    },
    async logout(): Promise<void> {
      try {
        await apiFetch("/api/v1/auth/logout", { method: "POST" });
      } finally {
        setStoredToken(null);
      }
    },
    async me(): Promise<User> {
      return apiFetch<User>("/api/v1/auth/me");
    },
  },

  files: {
    async list(): Promise<UserFile[]> {
      const res = await apiFetch<{ items?: UserFile[] } | UserFile[]>("/api/v1/files");
      if (Array.isArray(res)) return res;
      if (res && Array.isArray(res.items)) return res.items;
      return [];
    },
    async upload(file: File): Promise<UserFile> {
      let token = getStoredToken();
      if (!token) {
        token = await refreshAccessToken();
      }

      const sendUpload = async (authToken: string | null) => {
        const formData = new FormData();
        formData.append("file", file);

        const idempotencyKey = `${file.name}-${file.size}-${Date.now()}`;
        const headers: Record<string, string> = {
          "Idempotency-Key": idempotencyKey,
        };
        if (authToken) {
          headers["Authorization"] = `Bearer ${authToken}`;
        }

        return fetch(`${API_BASE_URL}/api/v1/files/upload`, {
          method: "POST",
          headers,
          body: formData,
          credentials: "include",
        });
      };

      let response = await sendUpload(token);

      // Handle 401: Refresh token and retry once
      if (response.status === 401) {
        const freshToken = await refreshAccessToken();
        if (freshToken) {
          response = await sendUpload(freshToken);
        }
      }

      if (!response.ok) {
        let errorCode = "UPLOAD_FAILED";
        let message = `Upload failed with status ${response.status}`;
        let requestId = "";
        try {
          const err = await response.json();
          if (err.error_code) errorCode = err.error_code;
          if (err.message) {
            message = err.message;
          } else if (err.detail) {
            message = Array.isArray(err.detail)
              ? err.detail
                  .map((d: { loc?: (string | number)[]; msg?: string }) => {
                    const field = d.loc && d.loc.length > 1 ? d.loc.slice(1).join(".") : "field";
                    return `${field}: ${d.msg || "Invalid"}`;
                  })
                  .join("; ")
              : String(err.detail);
          }
          if (err.request_id) requestId = err.request_id;
        } catch {
          // not json
        }
        throw new ApiError(response.status, errorCode, message, requestId);
      }

      return response.json();
    },
    async get(fileId: string): Promise<UserFile> {
      return apiFetch<UserFile>(`/api/v1/files/${fileId}`);
    },
    async delete(fileId: string): Promise<{ ok: boolean }> {
      return apiFetch<{ ok: boolean }>(`/api/v1/files/${fileId}`, {
        method: "DELETE",
      });
    },
    async sheets(fileId: string): Promise<FileSheetsResponse> {
      return apiFetch<FileSheetsResponse>(`/api/v1/files/${fileId}/sheets`);
    },
    async switchSheet(fileId: string, sheetName: string): Promise<UserFile> {
      return apiFetch<UserFile>(`/api/v1/files/${fileId}/switch-sheet`, {
        method: "POST",
        body: JSON.stringify({ sheet_name: sheetName }),
      });
    },
  },

  // Alias datasets -> files for backward compatibility
  get datasets() {
    return this.files;
  },

  lab: {
    async overview(fileId: string): Promise<LabOverviewResponse> {
      return apiFetch<LabOverviewResponse>(`/api/v1/lab/${fileId}/overview`);
    },
    async preview(
      fileId: string,
      limit = 50,
      search = ""
    ): Promise<{ columns: string[]; data: Record<string, unknown>[]; total_rows?: number }> {
      const searchParam = search ? `&search=${encodeURIComponent(search)}` : "";
      return apiFetch<{ columns: string[]; data: Record<string, unknown>[]; total_rows?: number }>(
        `/api/v1/lab/${fileId}/preview?limit=${limit}${searchParam}`
      );
    },
    async query(
      fileId: string,
      payloadOrSql: string | LabQueryPayload,
      joinFileIds: string[] = []
    ): Promise<LabQueryResponse> {
      const bodyPayload: LabQueryPayload =
        typeof payloadOrSql === "string"
          ? { sql: payloadOrSql, join_file_ids: joinFileIds }
          : payloadOrSql;
      return apiFetch<LabQueryResponse>(`/api/v1/lab/${fileId}/query`, {
        method: "POST",
        body: JSON.stringify(bodyPayload),
      });
    },
    async visualize(
      fileId: string,
      chartType: LabChartType,
      xCol?: string,
      yCol?: string,
      colorCol?: string
    ): Promise<{
      plotly_spec: Record<string, unknown>;
      spec: Record<string, unknown>;
      data: any[];
      layout: any;
    }> {
      return apiFetch<{
        plotly_spec: Record<string, unknown>;
        spec: Record<string, unknown>;
        data: any[];
        layout: any;
      }>(
        `/api/v1/lab/${fileId}/visualize`,
        {
          method: "POST",
          body: JSON.stringify({
            chart_type: chartType,
            x_col: xCol || null,
            y_col: yCol || null,
            color_col: colorCol || null,
          }),
        }
      );
    },
    async forensic(fileId: string): Promise<{ findings: Array<Record<string, unknown>>; report: string }> {
      return apiFetch<{ findings: Array<Record<string, unknown>>; report: string }>(
        `/api/v1/lab/${fileId}/forensic`
      );
    },
  },

  predict: {
    async diagnose(fileId: string, payload: PredictDiagnoseRequest = {}): Promise<PredictDiagnoseResponse> {
      return apiFetch<PredictDiagnoseResponse>(`/api/v1/predict/${fileId}/diagnose`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    async run(fileId: string, payload: PredictRunRequest = {}): Promise<PredictionHistory> {
      return apiFetch<PredictionHistory>(`/api/v1/predict/${fileId}/run`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    async history(fileId: string): Promise<PredictionHistory[]> {
      return apiFetch<PredictionHistory[]>(`/api/v1/predict/${fileId}/history`);
    },
    async get(predictionId: string): Promise<PredictionHistory> {
      return apiFetch<PredictionHistory>(`/api/v1/predict/${predictionId}`);
    },
    async simulate(
      fileId: string,
      payload: PredictSimulateRequest = {}
    ): Promise<PredictSimulateResponse> {
      return apiFetch<PredictSimulateResponse>(`/api/v1/predict/${fileId}/simulate`, {
        method: "POST",
        body: JSON.stringify(payload),
      });
    },
    async delete(predictionId: string): Promise<{ ok: boolean; deleted_id: string }> {
      return apiFetch<{ ok: boolean; deleted_id: string }>(`/api/v1/predict/${predictionId}`, {
        method: "DELETE",
      });
    },
  },

  chat: {
    async status(): Promise<ChatEngineStatus> {
      return apiFetch<ChatEngineStatus>(`/api/v1/chat/status`);
    },
    async history(fileId: string): Promise<ChatMessage[]> {
      return apiFetch<ChatMessage[]>(`/api/v1/chat/${fileId}/history`);
    },
    async stream(
      fileId: string,
      message: string,
      callbacks: {
        onToken: (token: string) => void;
        onTierDetected?: (info: { tier: number; intent?: string }) => void;
        onArtifact?: (artifact: Record<string, unknown>) => void;
        onUiAction?: (action: UiActionEvent) => void;
        onDone?: () => void;
        onError?: (err: Error) => void;
      }
    ): Promise<void> {
      let token = getStoredToken();
      if (!token) {
        token = await refreshAccessToken();
      }
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const bodyStr = JSON.stringify({ query: message, message });
      headers["Content-Length"] = new TextEncoder().encode(bodyStr).length.toString();

      let isFinished = false;
      let hasError = false;

      try {
        let response = await fetch(`${API_BASE_URL}/api/v1/chat/${fileId}/stream`, {
          method: "POST",
          headers,
          body: bodyStr,
          credentials: "include",
        });

        if (response.status === 401) {
          const refreshed = await refreshAccessToken();
          if (refreshed) {
            headers["Authorization"] = `Bearer ${refreshed}`;
            response = await fetch(`${API_BASE_URL}/api/v1/chat/${fileId}/stream`, {
              method: "POST",
              headers,
              body: bodyStr,
              credentials: "include",
            });
          }
        }

        if (!response.ok) {
          throw new Error(`SSE stream failed with status ${response.status}`);
        }

        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error("Response body is not readable");
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const blocks = buffer.split("\n\n");
          buffer = blocks.pop() || "";

          for (const block of blocks) {
            const blockLines = block.split("\n");
            let event = "message";
            const dataLines: string[] = [];

            for (const line of blockLines) {
              if (line.startsWith("event:")) {
                const raw = line.slice(6);
                event = raw.startsWith(" ") ? raw.slice(1) : raw;
              } else if (line.startsWith("data:")) {
                const raw = line.slice(5);
                dataLines.push(raw.startsWith(" ") ? raw.slice(1) : raw);
              }
            }

            const data = dataLines.join("\n");

            if (event === "token" || event === "message") {
              callbacks.onToken(data);
            } else if (event === "tier_detected") {
              try {
                const parsed = JSON.parse(data) as { tier: number; intent?: string };
                callbacks.onTierDetected?.(parsed);
              } catch {
                // ignore
              }
            } else if (event === "artifact" || event === "lab_artifact") {
              try {
                const parsed = JSON.parse(data);
                callbacks.onArtifact?.(parsed);
              } catch {
                // ignore
              }
            } else if (event === "ui_action") {
              try {
                const parsed = JSON.parse(data) as UiActionEvent;
                callbacks.onUiAction?.(parsed);
              } catch {
                // ignore
              }
            } else if (event === "done") {
              if (!isFinished && !hasError) {
                isFinished = true;
                callbacks.onDone?.();
              }
            } else if (event === "error") {
              hasError = true;
              callbacks.onError?.(new Error(data));
            }
          }
        }

        if (!isFinished && !hasError) {
          isFinished = true;
          callbacks.onDone?.();
        }
      } catch (err) {
        if (!hasError) {
          hasError = true;
          callbacks.onError?.(err instanceof Error ? err : new Error(String(err)));
        }
      }
    },
  },

  memory: {
    async list(fileId: string): Promise<AnalysisMemory[]> {
      return apiFetch<AnalysisMemory[]>(`/api/v1/memory/${fileId}`);
    },
    async delete(memoryId: string): Promise<{ ok: boolean }> {
      return apiFetch<{ ok: boolean }>(`/api/v1/memory/${memoryId}`, {
        method: "DELETE",
      });
    },
  },
};
