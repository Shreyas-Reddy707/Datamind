import { create } from "zustand";
import { ChatMessage, User, UserFile } from "@/lib/types";

export type LabTab = "overview" | "forensic" | "predict" | "sql";

export interface WorkspaceState {
  user: User | null;
  activeFileId: string | null;
  activeFile: UserFile | null;
  selectedJoinFileIds: string[];
  activeLabTab: LabTab;
  injectedArtifact: {
    type: "chart" | "forensic" | "diagnostic" | "prediction";
    data: unknown;
  } | null;
  chatMessages: ChatMessage[];
  isStreaming: boolean;
  streamBuffer: string;
  currentAgentStep: string | null;
  activeTier: number | null;
  isChatOpen: boolean;

  // Actions
  setUser: (user: User | null) => void;
  setActiveFileId: (fileId: string | null) => void;
  setActiveFile: (file: UserFile | null) => void;
  toggleJoinFileId: (fileId: string) => void;
  clearJoinFileIds: () => void;
  setActiveLabTab: (tab: LabTab) => void;
  setIsChatOpen: (isOpen: boolean) => void;
  toggleChat: () => void;
  injectArtifact: (artifact: {
    type: "chart" | "forensic" | "diagnostic" | "prediction";
    data: unknown;
  }) => void;
  clearInjectedArtifact: () => void;
  setChatMessages: (messages: ChatMessage[]) => void;
  addChatMessage: (message: ChatMessage) => void;
  setIsStreaming: (isStreaming: boolean) => void;
  setStreamBuffer: (buffer: string) => void;
  appendStreamBuffer: (chunk: string) => void;
  setCurrentAgentStep: (step: string | null) => void;
  setActiveTier: (tier: number | null) => void;
  resetWorkspace: () => void;
}

export const useWorkspaceStore = create<WorkspaceState>((set) => ({
  user: null,
  activeFileId: null,
  activeFile: null,
  selectedJoinFileIds: [],
  activeLabTab: "overview",
  injectedArtifact: null,
  chatMessages: [],
  isStreaming: false,
  streamBuffer: "",
  currentAgentStep: null,
  activeTier: null,
  isChatOpen: false,

  setUser: (user) => set({ user }),
  setActiveFileId: (activeFileId) => set({ activeFileId }),
  setActiveFile: (activeFile) => set({ activeFile }),
  toggleJoinFileId: (fileId) =>
    set((state) => ({
      selectedJoinFileIds: state.selectedJoinFileIds.includes(fileId)
        ? state.selectedJoinFileIds.filter((id) => id !== fileId)
        : [...state.selectedJoinFileIds, fileId],
    })),
  clearJoinFileIds: () => set({ selectedJoinFileIds: [] }),
  setActiveLabTab: (activeLabTab) => set({ activeLabTab }),
  setIsChatOpen: (isChatOpen) => set({ isChatOpen }),
  toggleChat: () => set((state) => ({ isChatOpen: !state.isChatOpen })),
  injectArtifact: (injectedArtifact) =>
    set({
      injectedArtifact,
      isChatOpen: false,
      activeLabTab:
        injectedArtifact.type === "chart" || injectedArtifact.type === "forensic"
          ? "forensic"
          : injectedArtifact.type === "prediction"
          ? "predict"
          : "overview",
    }),
  clearInjectedArtifact: () => set({ injectedArtifact: null }),
  setChatMessages: (chatMessages) => set({ chatMessages }),
  addChatMessage: (message) =>
    set((state) => ({ chatMessages: [...state.chatMessages, message] })),
  setIsStreaming: (isStreaming) => set({ isStreaming }),
  setStreamBuffer: (streamBuffer) => set({ streamBuffer }),
  appendStreamBuffer: (chunk) =>
    set((state) => ({ streamBuffer: state.streamBuffer + chunk })),
  setCurrentAgentStep: (currentAgentStep) => set({ currentAgentStep }),
  setActiveTier: (activeTier) => set({ activeTier }),
  resetWorkspace: () =>
    set({
      activeFileId: null,
      activeFile: null,
      selectedJoinFileIds: [],
      activeLabTab: "overview",
      injectedArtifact: null,
      chatMessages: [],
      isStreaming: false,
      streamBuffer: "",
      currentAgentStep: null,
      activeTier: null,
    }),
}));

