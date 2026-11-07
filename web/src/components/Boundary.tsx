import { Component, type ErrorInfo, type ReactNode } from 'react';

type Props = { what: string; children: ReactNode };
type State = { error: Error | null };

/** If one section throws while rendering, only that section is replaced. */
export class Boundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`[${this.props.what}] failed to render`, error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="later" role="status">
        <p className="later-title">Couldn't show {this.props.what}</p>
        <p>The rest of the page still works. Details: {this.state.error.message}</p>
      </div>
    );
  }
}
