import { COLOR } from "./theme";
import Sidebar from "./components/layout/Sidebar";
import TopBar from "./components/layout/TopBar";
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
      style={{
        zoom: 0.88,
        height: "calc(100vh / 0.88)",
        width: "100%",
        background: COLOR.bg,
        fontSize: "14px",
        color: COLOR.textPrimary,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
      className="font-sans"
    >
      <div style={{ flex: 1, minHeight: 0, display: "flex", overflow: "hidden" }}>
        <Sidebar state={state} actions={actions} />

        <div style={{ flex: 1, minWidth: 0, minHeight: 0, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <TopBar
            tab={state.tab}
            llmStatus={state.llmStatus}
            onGo={actions.go}
            onOpenLlm={actions.openLlmConfig}
            docName={state.tab === "docs" ? state.viewingDoc?.name : undefined}
          />

          {state.tab === "chat" && <ChatTab state={state} actions={actions} />}
          {state.tab === "docs" && <DocsTab state={state} actions={actions} />}
          {state.tab === "guide" && <GuideTab state={state} actions={actions} />}
        </div>
      </div>

      {/* overlays */}
      {/* Trong tab Tài liệu, việc xem tài liệu hiển thị NGAY trong khung (DocsTab renders DocViewerPanel) —
          hộp thoại nổi này chỉ dùng khi mở tài liệu gốc từ trích dẫn trong tab Trò chuyện. */}
      <DocViewerModal viewingDoc={state.tab !== "docs" ? state.viewingDoc : null} onClose={actions.closeViewer} />
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
