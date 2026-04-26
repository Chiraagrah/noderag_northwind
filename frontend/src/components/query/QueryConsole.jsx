import useQueryStore from "../../store/queryStore";
import RetrievalLog from "./RetrievalLog";
import AnswerPane from "./AnswerPane";
import FollowUpList from "./FollowUpList";
import QueryInput from "./QueryInput";

function EmptyState() {
  return (
    <div style={{
      fontFamily: "JetBrains Mono",
      fontSize:   10,
      color:      "var(--muted)",
      textAlign:  "center",
      padding:    24,
    }}>
      <div>no query run yet</div>
      <div style={{ marginTop: 4 }}>results will appear here</div>
    </div>
  );
}

export default function QueryConsole() {
  const steps      = useQueryStore(s => s.steps);
  const answer     = useQueryStore(s => s.answer);
  const isQuerying = useQueryStore(s => s.isQuerying);
  const clearHistory = useQueryStore(s => s.clearHistory);

  const showEmpty = steps.length === 0 && answer === null && !isQuerying;

  return (
    <div style={{
      display:        "flex",
      flexDirection:  "column",
      height:         "100%",
      background:     "var(--panel)",
      borderLeft:     "1px solid var(--border)",
    }}>
      {/* header */}
      <div style={{
        height:          40,
        borderBottom:    "1px solid var(--border)",
        padding:         "0 16px",
        display:         "flex",
        alignItems:      "center",
        justifyContent:  "space-between",
        flexShrink:      0,
      }}>
        <span style={{
          fontFamily:     "JetBrains Mono",
          fontSize:       10,
          color:          "var(--muted)",
          letterSpacing:  "0.08em",
        }}>
          QUERY CONSOLE
        </span>
        <button
          onClick={clearHistory}
          style={{
            fontFamily:  "JetBrains Mono",
            fontSize:    10,
            color:       "var(--muted)",
            background:  "none",
            border:      "none",
            cursor:      "pointer",
            transition:  "color 150ms",
          }}
          onMouseEnter={e => e.currentTarget.style.color = "var(--primary)"}
          onMouseLeave={e => e.currentTarget.style.color = "var(--muted)"}
        >
          clear
        </button>
      </div>

      {/* scrollable content */}
      <div style={{
        flex:           1,
        overflowY:      "auto",
        padding:        16,
        display:        "flex",
        flexDirection:  "column",
        gap:            16,
      }}>
        {showEmpty ? (
          <EmptyState />
        ) : (
          <>
            <RetrievalLog />
            <AnswerPane />
            <FollowUpList />
          </>
        )}
      </div>

      {/* fixed input at bottom */}
      <QueryInput />
    </div>
  );
}
