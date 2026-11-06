import type { AppState } from "../../types";
import type { Actions } from "../../store/useAppStore";
import ChatColumn from "./ChatColumn";
import SourcePanel from "./SourcePanel";

export default function ChatTab({ state, actions }: { state: AppState; actions: Actions }) {
  // Nguồn ẩn mặc định; chỉ hiện khi người dùng bấm [n] hoặc chip nguồn (actions.openCite).
  const showSource = state.sourceOpen && state.liveSources.length > 0;

  return (
    <main className="layout-main" style={{ flex: 1, minHeight: 0, display: "flex" }}>
      <ChatColumn state={state} actions={actions} />

      {showSource && <SourcePanel state={state} actions={actions} />}
    </main>
  );
}
