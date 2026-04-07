"use client";

export default function ConfidenceDashboard({ confidence, grounding, sources, mode, pipelineLatency, gapAnalysis }) {
  if (confidence === null && !sources?.length) return null;

  const confPct = confidence !== null ? Math.round(confidence * 100) : null;
  const confLevel = confPct > 70 ? "high" : confPct > 40 ? "medium" : "low";

  return (
    <div className="confidence-dashboard">
      {/* Confidence Meter */}
      {confPct !== null && (
        <div className="sidebar-section">
          <div className="sidebar-section-title">📊 Confidence</div>
          <div className="confidence-meter">
            <div className="confidence-bar">
              <div className={`confidence-fill ${confLevel}`} style={{ width: `${confPct}%` }} />
            </div>
            <div className="confidence-label">{confPct}%</div>
          </div>
          <div className="confidence-breakdown">
            {mode && (
              <div className="conf-item">
                <span className="conf-key">Mode</span>
                <span className={`conf-badge mode-${mode}`}>{mode === "debate" ? "🎭 Debate" : "⚡ Simple"}</span>
              </div>
            )}
            {pipelineLatency && (
              <div className="conf-item">
                <span className="conf-key">Latency</span>
                <span className="conf-value">{Math.round(pipelineLatency)}ms</span>
              </div>
            )}
            {grounding && (
              <>
                <div className="conf-item">
                  <span className="conf-key">Grounded</span>
                  <span className={`conf-value ${grounding.is_grounded ? "grounded" : "ungrounded"}`}>
                    {grounding.grounded_citations}/{grounding.total_citations} citations
                  </span>
                </div>
                {grounding.ungrounded_citations?.length > 0 && (
                  <div className="conf-item warn">
                    <span className="conf-key">⚠ Unverified</span>
                    <span className="conf-value">{grounding.ungrounded_citations.join(", ")}</span>
                  </div>
                )}
              </>
            )}
            {gapAnalysis && (
              <div className="conf-item">
                <span className="conf-key">Coverage</span>
                <span className={`conf-badge coverage-${gapAnalysis.recommendation}`}>
                  {gapAnalysis.recommendation === "high_confidence" ? "✅ Strong" :
                   gapAnalysis.recommendation === "moderate_confidence" ? "⚠️ Moderate" : "❌ Low"}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Sources */}
      <div className="sidebar-section">
        <div className="sidebar-section-title">📚 Legal Sources ({sources?.length || 0})</div>
        {sources?.length > 0 ? (
          sources.map((source, i) => (
            <div key={i} className="source-item">
              <div className="source-act">{source.act?.split(",")[0]}</div>
              <div className="source-title">{source.section} — {source.title}</div>
              <div className="source-score">
                <span className={`method-badge method-${source.retrieval_method}`}>
                  {source.retrieval_method}
                </span>
                {(source.relevance_score * 100).toFixed(1)}%
              </div>
            </div>
          ))
        ) : (
          <p style={{ fontSize: "0.8rem", color: "var(--text-tertiary)" }}>
            Sources appear after you ask a question.
          </p>
        )}
      </div>
    </div>
  );
}
