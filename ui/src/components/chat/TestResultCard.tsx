import React from "react";
import type { TestResultPayload } from "../../hooks/useWebSocket";

type Props = {
  result: TestResultPayload;
};

function ResultIcon({ result }: { result?: string }) {
  if (result === "pass") return <span className="chat-test-icon chat-test-icon-pass">✓</span>;
  if (result === "fail") return <span className="chat-test-icon chat-test-icon-fail">✗</span>;
  if (result === "error") return <span className="chat-test-icon chat-test-icon-error">!</span>;
  return <span className="chat-test-icon chat-test-icon-running">●</span>;
}

export function TestResultCard({ result }: Props) {
  const cardCls =
    result.result === "pass"
      ? "chat-test-card chat-test-card-pass"
      : result.result === "fail" || result.result === "error"
        ? "chat-test-card chat-test-card-fail"
        : result.status === "complete"
          ? "chat-test-card chat-test-card-complete"
          : "chat-test-card chat-test-card-running";

  return (
    <div className={cardCls}>
      <div className="chat-test-header">
        <ResultIcon result={result.result} />
        <span className="chat-test-name">{result.testName}</span>
        {result.status === "running" && <span className="chat-test-running-label">Running...</span>}
      </div>

      {result.assertion && (
        <div className="chat-test-assertion">Assert: {result.assertion}</div>
      )}

      {result.errorMessage && (
        <div className="chat-test-error">{result.errorMessage}</div>
      )}

      {result.screenshotBase64 && (
        <img
          className="chat-test-screenshot"
          src={`data:image/png;base64,${result.screenshotBase64}`}
          alt="Test failure screenshot"
        />
      )}

      {result.summary && (
        <div className="chat-test-summary">
          <span className="chat-test-sum-total">{result.summary.total} tests</span>
          <span className="chat-test-sum-pass">{result.summary.passed} passed</span>
          {result.summary.failed > 0 && (
            <span className="chat-test-sum-fail">{result.summary.failed} failed</span>
          )}
        </div>
      )}
    </div>
  );
}
