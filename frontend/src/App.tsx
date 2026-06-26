import Header from "./components/Header";
import ChatTab from "./components/chat/ChatTab";
import DocsTab from "./components/docs/DocsTab";
import GuideTab from "./components/guide/GuideTab";
import ConfirmDialog from "./components/modals/ConfirmDialog";
import DocViewerModal from "./components/modals/DocViewerModal";
import LlmConfigModal from "./components/modals/LlmConfigModal";
import Toast from "./components/common/Toast";
import { useAppStore } from "./store/useAppStore";

export default function App() {
  const { state, actions } = useAppStore();

  return (
    <div
      style={{ zoom: 0.88, height: "calc(100vh / 0.88)", width: "100%", background: "#ECF1EE", fontSize: "14px", color: "#0F172A", overflow: "hidden", display: "flex", flexDirection: "column" }}
      className="font-sans"
    >
      <Header tab={state.tab} llmStatus={state.llmStatus} onGo={actions.go} onOpenLlm={actions.openLlmConfig} />

      {state.tab === "chat" && <ChatTab state={state} actions={actions} />}
      {state.tab === "docs" && <DocsTab state={state} actions={actions} />}
      {state.tab === "guide" && <GuideTab state={state} actions={actions} />}

      {/* overlays */}
      <DocViewerModal viewingDoc={state.viewingDoc} onClose={actions.closeViewer} />
      <LlmConfigModal
        open={state.llmConfigOpen}
        llm={state.llm}
        testing={state.llmTesting}
        result={state.llmTestResult}
        onClose={actions.closeLlmConfig}
        onChange={actions.setLlm}
        onTest={actions.testLlm}
        onSave={actions.saveLlm}
      />
      <ConfirmDialog conv={state.confirmDelete} onYes={actions.confirmDeleteYes} onNo={actions.confirmDeleteNo} />
      <Toast message={state.toast} />
    </div>
  );
}
