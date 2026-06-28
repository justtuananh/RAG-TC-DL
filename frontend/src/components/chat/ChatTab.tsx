import type { AppState } from "../../types";
import type { Actions } from "../../store/useAppStore";
import HistorySidebar from "./HistorySidebar";
import HistoryRail from "./HistoryRail";
import ChatColumn from "./ChatColumn";
import SourcePanel from "./SourcePanel";

export default function ChatTab({ state, actions }: { state: AppState; actions: Actions }) {
  const showSource = state.liveSources.length > 0;

  return (
    <main className="layout-main" style={{ flex: 1, minHeight: 0, display: "flex" }}>
      {state.sidebarOpen ? <HistorySidebar state={state} actions={actions} /> : <HistoryRail onToggle={actions.toggleSidebar} onNewChat={actions.newChat} />}

      <ChatColumn state={state} actions={actions} />

      {showSource && <SourcePanel state={state} actions={actions} />}
    </main>
  );
}
