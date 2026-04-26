import { useRef } from "react";
import useQueryStore from "../../store/queryStore";
import { useQueryStream } from "../../hooks/useQueryStream";

const EXAMPLE_QUERIES = [
  "which UK suppliers provide beverages?",
  "top customers by total order value?",
  "employees who handled germany shipments?",
  "discontinued products still appearing in orders?",
];

export default function QueryInput() {
  const question   = useQueryStore(s => s.question);
  const isQuerying = useQueryStore(s => s.isQuerying);
  const setQuestion = useQueryStore(s => s.setQuestion);
  const textareaRef = useRef(null);

  const { submitQuery } = useQueryStream();

  // expose ref for keyboard shortcut (step 8)
  if (typeof window !== "undefined") {
    window.__queryInputRef = textareaRef;
  }

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submitQuery(question);
    }
  };

  const handleExample = (q) => {
    setQuestion(q);
    submitQuery(q);
    textareaRef.current?.focus();
  };

  return (
    <div style={{
      background:   "var(--panel)",
      borderTop:    "1px solid var(--border)",
      padding:      "12px 16px",
      flexShrink:   0,
    }}>
      {/* example queries */}
      {question === "" && !isQuerying && (
        <div style={{ marginBottom: 8, display: "flex", flexDirection: "column", gap: 2 }}>
          {EXAMPLE_QUERIES.map(q => (
            <button
              key={q}
              onClick={() => handleExample(q)}
              style={{
                color:      "var(--muted)",
                fontFamily: "JetBrains Mono",
                fontSize:   10,
                background: "none",
                border:     "none",
                cursor:     "pointer",
                display:    "block",
                textAlign:  "left",
                padding:    "1px 0",
                transition: "color 150ms",
              }}
              onMouseEnter={e => e.currentTarget.style.color = "var(--primary)"}
              onMouseLeave={e => e.currentTarget.style.color = "var(--muted)"}
            >
              {q}
            </button>
          ))}
        </div>
      )}

      {/* input row */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 8 }}>
        <span
          style={{
            fontFamily:  "JetBrains Mono",
            fontSize:    12,
            color:       "var(--accent)",
            lineHeight:  "20px",
            flexShrink:  0,
            animation:   isQuerying ? "blink 1s step-end infinite" : "none",
          }}
        >
          {isQuerying ? "_" : ">"}
        </span>
        <textarea
          ref={textareaRef}
          rows={1}
          value={question}
          disabled={isQuerying}
          placeholder="query the knowledge graph..."
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          style={{
            flex:        1,
            fontFamily:  "JetBrains Mono",
            fontSize:    12,
            background:  "transparent",
            border:      "none",
            outline:     "none",
            color:       "var(--primary)",
            resize:      "none",
            lineHeight:  "20px",
            caretColor:  "var(--accent)",
            "::placeholder": { color: "var(--muted)" },
          }}
        />
      </div>
    </div>
  );
}
