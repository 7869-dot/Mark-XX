import React from "react";

type State = { error: Error | null };

export class RootErrorBoundary extends React.Component<
  { children: React.ReactNode },
  State
> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    // Surface in prod logs; replace with a real client logger when one exists.
    if (typeof window !== "undefined") {
      // eslint-disable-next-line no-console
      console.error("[axolot] unhandled render error", error, info);
    }
  }

  private handleReset = () => {
    this.setState({ error: null });
    window.location.href = "/";
  };

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div
        className="min-h-screen flex items-center justify-center px-6"
        style={{ background: "var(--bg-void)" }}
      >
        <div className="max-w-md text-center space-y-4">
          <div
            className="text-2xl tracking-[0.2em]"
            style={{
              fontFamily: "var(--font-display)",
              color: "var(--text-primary)",
            }}
          >
            SOMETHING SLIPPED
          </div>
          <p
            className="text-sm"
            style={{
              fontFamily: "var(--font-body)",
              color: "var(--text-secondary)",
            }}
          >
            Your agent is still alive — just this view crashed. Reload and we'll
            put you back on the dashboard.
          </p>
          <button
            type="button"
            onClick={this.handleReset}
            className="px-5 py-2.5 transition-all"
            style={{
              background: "var(--bg-elevated)",
              border: "1px solid var(--border-default)",
              borderRadius: 8,
              color: "var(--text-primary)",
              fontFamily: "var(--font-body)",
              fontWeight: 600,
            }}
          >
            Reload Axolot
          </button>
        </div>
      </div>
    );
  }
}
