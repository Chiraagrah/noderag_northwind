import { Component } from "react";

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          fontFamily: "JetBrains Mono",
          fontSize:   11,
          color:      "var(--muted)",
          padding:    32,
        }}>
          <div style={{ color: "#E05C5C", marginBottom: 8 }}>render error</div>
          <pre style={{ fontSize: 10, color: "var(--muted)", whiteSpace: "pre-wrap" }}>
            {this.state.error.message}
          </pre>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop:   16,
              fontFamily:  "JetBrains Mono",
              fontSize:    10,
              color:       "var(--primary)",
              background:  "none",
              border:      "1px solid var(--border)",
              padding:     "4px 12px",
              cursor:      "pointer",
            }}
          >
            reload page
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
