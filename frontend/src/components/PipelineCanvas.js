"use client";
import { useState, useEffect, useRef } from "react";

const NODE_CONFIGS = {
  safety:      { x: 80,  y: 40,  label: "Safety Gate",    color: "#EF4444", icon: "🛡️" },
  query_engine:{ x: 250, y: 40,  label: "Query Engine",   color: "#8B5CF6", icon: "🔍" },
  language:    { x: 420, y: 40,  label: "Language",        color: "#06B6D4", icon: "🌐" },
  bm25:        { x: 170, y: 140, label: "BM25",            color: "#6366F1", icon: "📝" },
  dense:       { x: 330, y: 140, label: "Dense Vec",       color: "#6366F1", icon: "🧠" },
  structured:  { x: 490, y: 140, label: "Struct Nav",      color: "#6366F1", icon: "🏗️" },
  cross_ref:   { x: 650, y: 140, label: "Cross-Ref",       color: "#6366F1", icon: "🔗" },
  fusion:      { x: 400, y: 240, label: "RRF Fusion",      color: "#F59E0B", icon: "⚡" },
  prosecutor:  { x: 200, y: 340, label: "Prosecutor",      color: "#10B981", icon: "🏛️" },
  defense:     { x: 400, y: 340, label: "Defense",          color: "#8B5CF6", icon: "🛡️" },
  validator:   { x: 600, y: 340, label: "Validator",        color: "#F59E0B", icon: "⚖️" },
  grounding:   { x: 400, y: 440, label: "Grounding",        color: "#EF4444", icon: "✅" },
};

const EDGES = [
  ["safety", "query_engine"], ["query_engine", "language"],
  ["language", "bm25"], ["language", "dense"], ["language", "structured"], ["language", "cross_ref"],
  ["bm25", "fusion"], ["dense", "fusion"], ["structured", "fusion"], ["cross_ref", "fusion"],
  ["fusion", "prosecutor"], ["prosecutor", "defense"], ["defense", "validator"],
  ["validator", "grounding"],
];

export default function PipelineCanvas({ nodeStates, collapsed, onToggle }) {
  const canvasRef = useRef(null);
  const [hoveredNode, setHoveredNode] = useState(null);

  const getNodeStatus = (nodeId) => {
    if (!nodeStates) return "idle";
    const state = nodeStates[nodeId];
    return state?.status || "idle";
  };

  if (collapsed) {
    return (
      <div className="pipeline-collapsed" onClick={onToggle}>
        <div className="pipeline-status-bar">
          <span className="pipeline-label">⚡ Pipeline</span>
          <div className="pipeline-mini-nodes">
            {Object.entries(NODE_CONFIGS).map(([id, cfg]) => {
              const status = getNodeStatus(id);
              return (
                <div
                  key={id}
                  className={`mini-node status-${status}`}
                  style={{ background: status === "done" ? cfg.color : undefined }}
                  title={cfg.label}
                />
              );
            })}
          </div>
          <span className="pipeline-expand">▼</span>
        </div>
      </div>
    );
  }

  return (
    <div className="pipeline-canvas">
      <div className="pipeline-canvas-header">
        <h3>⚡ Processing Pipeline</h3>
        <button className="btn btn-ghost btn-sm" onClick={onToggle}>Collapse ▲</button>
      </div>
      <div className="pipeline-canvas-body">
        <svg width="800" height="500" viewBox="0 0 800 500" className="pipeline-svg">
          {/* Edges */}
          {EDGES.map(([from, to], i) => {
            const f = NODE_CONFIGS[from];
            const t = NODE_CONFIGS[to];
            if (!f || !t) return null;
            const fromStatus = getNodeStatus(from);
            const toStatus = getNodeStatus(to);
            const isActive = fromStatus === "done" && (toStatus === "running" || toStatus === "done");
            return (
              <line
                key={i}
                x1={f.x + 50} y1={f.y + 32}
                x2={t.x + 50} y2={t.y + 32}
                className={`pipeline-edge ${isActive ? "active" : ""}`}
                stroke={isActive ? "#6366F1" : "rgba(255,255,255,0.08)"}
                strokeWidth={isActive ? 2 : 1}
              />
            );
          })}

          {/* Nodes */}
          {Object.entries(NODE_CONFIGS).map(([id, cfg]) => {
            const status = getNodeStatus(id);
            const isHovered = hoveredNode === id;
            return (
              <g
                key={id}
                transform={`translate(${cfg.x}, ${cfg.y})`}
                className={`pipeline-node status-${status}`}
                onMouseEnter={() => setHoveredNode(id)}
                onMouseLeave={() => setHoveredNode(null)}
              >
                <rect
                  width="100" height="64" rx="12"
                  fill={status === "running" ? cfg.color + "30" : status === "done" ? cfg.color + "20" : "#1A1A24"}
                  stroke={status === "running" ? cfg.color : status === "done" ? cfg.color + "80" : "rgba(255,255,255,0.08)"}
                  strokeWidth={status === "running" ? 2 : 1}
                  className={status === "running" ? "node-pulse" : ""}
                />
                <text x="50" y="28" textAnchor="middle" fontSize="18">{cfg.icon}</text>
                <text x="50" y="50" textAnchor="middle" fontSize="10" fill={status === "done" ? "#F0F0F5" : "#6B6B80"} fontFamily="Inter, sans-serif">
                  {cfg.label}
                </text>
                {status === "done" && (
                  <circle cx="90" cy="10" r="6" fill="#10B981">
                    <animate attributeName="opacity" values="0;1" dur="0.3s" fill="freeze" />
                  </circle>
                )}
                {status === "running" && (
                  <circle cx="90" cy="10" r="6" fill={cfg.color}>
                    <animate attributeName="r" values="4;7;4" dur="1s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="1;0.5;1" dur="1s" repeatCount="indefinite" />
                  </circle>
                )}
                {status === "error" && (
                  <circle cx="90" cy="10" r="6" fill="#EF4444" />
                )}
              </g>
            );
          })}

          {/* Tooltip */}
          {hoveredNode && NODE_CONFIGS[hoveredNode] && (
            <g transform={`translate(${NODE_CONFIGS[hoveredNode].x - 20}, ${NODE_CONFIGS[hoveredNode].y - 30})`}>
              <rect width="140" height="24" rx="6" fill="#222233" stroke="rgba(255,255,255,0.1)" />
              <text x="70" y="16" textAnchor="middle" fontSize="10" fill="#A0A0B8" fontFamily="Inter, sans-serif">
                {getNodeStatus(hoveredNode).toUpperCase()} • {nodeStates?.[hoveredNode]?.latency_ms ? `${Math.round(nodeStates[hoveredNode].latency_ms)}ms` : "—"}
              </text>
            </g>
          )}
        </svg>
      </div>
    </div>
  );
}
