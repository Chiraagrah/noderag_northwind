import useQueryStore from "../../store/queryStore";
import { useQueryStream } from "../../hooks/useQueryStream";

export default function FollowUpList() {
  const answer      = useQueryStore(s => s.answer);
  const setQuestion = useQueryStore(s => s.setQuestion);
  const { submitQuery } = useQueryStream();

  const followUps = answer?.suggested_follow_ups ?? [];
  if (followUps.length === 0) return null;

  const handleClick = (text) => {
    setQuestion(text);
    submitQuery(text);
  };

  return (
    <div>
      <div style={{
        fontFamily:   "JetBrains Mono",
        fontSize:     10,
        color:        "var(--muted)",
        marginBottom: 6,
      }}>
        related queries
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {followUps.map((q, i) => (
          <button
            key={i}
            onClick={() => handleClick(q)}
            style={{
              background:   "transparent",
              border:       "none",
              borderLeft:   "2px solid var(--border)",
              padding:      "4px 8px",
              color:        "var(--muted)",
              fontFamily:   "JetBrains Mono",
              fontSize:     11,
              textAlign:    "left",
              width:        "100%",
              cursor:       "pointer",
              lineHeight:   1.5,
              transition:   "border-color 150ms, color 150ms",
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderLeftColor = "var(--accent)";
              e.currentTarget.style.color           = "var(--primary)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderLeftColor = "var(--border)";
              e.currentTarget.style.color           = "var(--muted)";
            }}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
