import {
  ChatMessage,
  LabChartType,
  LabOverviewResponse,
  PredictionHistory,
  PredictDiagnoseRequest,
  PredictDiagnoseResponse,
  PredictRunRequest,
  User,
  UserFile,
  AnalysisMemory,
} from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

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

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("datamind_token");
}

export function setStoredToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem("datamind_token", token);
  } else {
    localStorage.removeItem("datamind_token");
  }
}

export async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getStoredToken();
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

  if (!response.ok) {
    let errorCode = "UNKNOWN_ERROR";
    let message = `Request failed with status ${response.status}`;
    let requestId = "";

    try {
      const errorJson = await response.json();
      if (errorJson.error_code) errorCode = errorJson.error_code;
      if (errorJson.message) message = errorJson.message;
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

  datasets: {
    async list(): Promise<UserFile[]> {
      return apiFetch<UserFile[]>("/api/v1/datasets");
    },
    async upload(file: File): Promise<UserFile> {
      const token = getStoredToken();
      const formData = new FormData();
      formData.append("file", file);

      const idempotencyKey = `${file.name}-${file.size}-${Date.now()}`;
      const headers: Record<string, string> = {
        "Idempotency-Key": idempotencyKey,
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE_URL}/api/v1/datasets/upload`, {
        method: "POST",
        headers,
        body: formData,
        credentials: "include",
      });

      if (!response.ok) {
        let errorCode = "UPLOAD_FAILED";
        let message = `Upload failed with status ${response.status}`;
        let requestId = "";
        try {
          const err = await response.json();
          if (err.error_code) errorCode = err.error_code;
          if (err.message) message = err.message;
          if (err.request_id) requestId = err.request_id;
        } catch {
          // not json
        }
        throw new ApiError(response.status, errorCode, message, requestId);
      }

      return response.json();
    },
    async get(fileId: string): Promise<UserFile> {
      return apiFetch<UserFile>(`/api/v1/datasets/${fileId}`);
    },
    async delete(fileId: string): Promise<{ ok: boolean }> {
      return apiFetch<{ ok: boolean }>(`/api/v1/datasets/${fileId}`, {
        method: "DELETE",
      });
    },
  },

  lab: {
    async overview(fileId: string): Promise<LabOverviewResponse> {
      return apiFetch<LabOverviewResponse>(`/api/v1/lab/${fileId}/overview`);
    },
    async preview(fileId: string, limit = 50): Promise<{ columns: string[]; data: Record<string, unknown>[] }> {
      return apiFetch<{ columns: string[]; data: Record<string, unknown>[] }>(
        `/api/v1/lab/${fileId}/preview?limit=${limit}`
      );
    },
    async query(
      fileId: string,
      sql: string,
      joinFileIds: string[] = []
    ): Promise<{ columns: string[]; rows: unknown[][]; row_count: number }> {
      return apiFetch<{ columns: string[]; rows: unknown[][]; row_count: number }>(
        `/api/v1/lab/${fileId}/query`,
        {
          method: "POST",
          body: JSON.stringify({ sql, join_file_ids: joinFileIds }),
        }
      );
    },
    async visualize(
      fileId: string,
      chartType: LabChartType,
      xCol?: string,
      yCol?: string,
      colorCol?: string
    ): Promise<{ plotly_spec: Record<string, unknown> }> {
      return apiFetch<{ plotly_spec: Record<string, unknown> }>(
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
  },

  chat: {
    async history(fileId: string): Promise<ChatMessage[]> {
      return apiFetch<ChatMessage[]>(`/api/v1/chat/${fileId}/history`);
    },
    async stream(
      fileId: string,
      message: string,
      callbacks: {
        onToken: (token: string) => void;
        onArtifact?: (artifact: Record<string, unknown>) => void;
        onDone?: () => void;
        onError?: (err: Error) => void;
      }
    ): Promise<void> {
      const token = getStoredToken();
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (token) {
        headers["Authorization"] = `Bearer ${token}`;
      }

      const bodyStr = JSON.stringify({ message });
      headers["Content-Length"] = new TextEncoder().encode(bodyStr).length.toString();

      try {
        const response = await fetch(`${API_BASE_URL}/api/v1/chat/${fileId}/stream`, {
          method: "POST",
          headers,
          body: bodyStr,
          credentials: "include",
        });

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
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const block of lines) {
            const blockLines = block.split("\n");
            let event = "message";
            let data = "";

            for (const line of blockLines) {
              if (line.startsWith("event: ")) {
                event = line.replace("event: ", "").trim();
              } else if (line.startsWith("data: ")) {
                data = line.replace("data: ", "").trim();
              }
            }

            if (event === "token" || event === "message") {
              callbacks.onToken(data);
            } else if (event === "artifact") {
              try {
                const parsed = JSON.parse(data);
                callbacks.onArtifact?.(parsed);
              } catch {
                // ignore
              }
            } else if (event === "done") {
              callbacks.onDone?.();
            } else if (event === "error") {
              callbacks.onError?.(new Error(data));
            }
          }
        }
        callbacks.onDone?.();
      } catch (err) {
        callbacks.onError?.(err instanceof Error ? err : new Error(String(err)));
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

