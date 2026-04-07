"use client";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Scale, ShieldCheck, Sword, CheckCircle2, ChevronRight, XCircle, AlertTriangle, Fingerprint, SearchCheck } from "lucide-react";

export default function DebateViewer({ prosecutorOutput, defenseOutput, validatorOutput, isStreaming }) {
  const [activeTab, setActiveTab] = useState("prosecutor");

  const tabs = [
    { id: "prosecutor", label: "Legal Context", icon: <SearchCheck size={16} />, status: prosecutorOutput ? "ready" : isStreaming ? "loading" : "waiting" },
    { id: "defense", label: "Counter-Defense", icon: <ShieldCheck size={16} />, status: defenseOutput ? "ready" : (prosecutorOutput && isStreaming) ? "loading" : "waiting" },
    { id: "validator", label: "Final Ruling", icon: <Scale size={16} />, status: validatorOutput ? "ready" : (defenseOutput && isStreaming) ? "loading" : "waiting" }
  ];

  return (
    <div className="flex flex-col h-full text-white">
      <div className="flex items-center gap-3 mb-6 pb-6 border-b border-white/10">
        <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/10 border border-indigo-500/30 flex items-center justify-center">
          <Fingerprint className="text-indigo-400" size={24} />
        </div>
        <div>
          <h2 className="text-xl font-display font-medium">Neural Reasoning Engine</h2>
          <p className="text-sm text-zinc-400">Tri-Modal Multi-Agent Debate</p>
        </div>
      </div>

      <div className="flex gap-2 mb-6 p-1 bg-white/5 rounded-xl border border-white/10">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 flex items-center justify-center gap-2 py-2 px-3 rounded-lg text-sm font-medium transition-all relative ${
              activeTab === tab.id ? "text-white" : "text-zinc-500 hover:text-zinc-300"
            }`}
          >
            {activeTab === tab.id && (
              <motion.div 
                layoutId="activeTabBadge" 
                className="absolute inset-0 bg-indigo-500/20 border border-indigo-500/50 rounded-lg shadow-glow"
              />
            )}
            <span className="relative z-10 flex items-center gap-2">
              {tab.icon}
              {tab.label}
              {tab.status === "loading" && <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse ml-1" />}
            </span>
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto custom-scrollbar relative">
        <AnimatePresence mode="wait">
          
          {/* PROSECUTOR */}
          {activeTab === "prosecutor" && (
            <motion.div
              key="prosecutor"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              className="space-y-6"
            >
              {!prosecutorOutput && isStreaming && (
                <div className="flex items-center gap-3 text-indigo-400 p-4 premium-glass-strong rounded-xl">
                  <span className="spinner" /> Retrieving cross-referenced documents...
                </div>
              )}
              
              {prosecutorOutput && (
                <>
                  <div className="premium-glass-strong rounded-xl p-5 border-l-4 border-l-indigo-500">
                    <h3 className="text-md font-semibold text-indigo-300 mb-3 flex items-center gap-2">
                      <SearchCheck size={18} /> Initial Legal Stance
                    </h3>
                    <p className="text-sm text-zinc-300 leading-relaxed">{prosecutorOutput.legal_analysis}</p>
                  </div>

                  {prosecutorOutput.applicable_sections && (
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Cited Acts & Sections</h4>
                      {prosecutorOutput.applicable_sections.map((sec, i) => (
                        <motion.div 
                          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }}
                          key={i} className="premium-glass rounded-xl p-4 hover:border-indigo-500/30 transition-colors"
                        >
                          <div className="text-xs font-mono text-indigo-400 mb-1">{sec.act} — {sec.section}</div>
                          <div className="font-medium text-white mb-2">{sec.title}</div>
                          <p className="text-xs text-zinc-400 line-clamp-2">{sec.relevance}</p>
                          {sec.punishment && (
                            <div className="mt-3 pt-3 border-t border-white/5 text-xs text-red-400 font-mono flex items-center gap-1">
                              <AlertTriangle size={12} /> {sec.punishment}
                            </div>
                          )}
                        </motion.div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </motion.div>
          )}

          {/* DEFENSE */}
          {activeTab === "defense" && (
            <motion.div
              key="defense"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              className="space-y-6"
            >
              {!defenseOutput && isStreaming && (
                <div className="flex items-center gap-3 text-emerald-400 p-4 premium-glass-strong rounded-xl">
                  <span className="spinner border-t-emerald-400" /> Formulating counter-arguments & technicalities...
                </div>
              )}

              {defenseOutput && (
                <>
                  <div className="flex items-center justify-between p-4 premium-glass rounded-xl border border-white/5">
                    <div className="text-sm font-medium text-zinc-300">Defense Stance:</div>
                    <div className={`px-3 py-1 rounded-full text-xs font-bold font-mono tracking-wide ${
                      defenseOutput.overall_assessment === "agree" ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30" :
                      defenseOutput.overall_assessment === "disagree" ? "bg-red-500/20 text-red-400 border border-red-500/30" :
                      "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                    }`}>
                      {defenseOutput.overall_assessment.toUpperCase()}
                    </div>
                  </div>

                  {defenseOutput.challenges?.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Procedural Challenges</h4>
                      {defenseOutput.challenges.map((ch, i) => (
                        <div key={i} className="premium-glass-strong rounded-xl p-4 border-l-2 border-l-amber-500">
                          <div className="text-sm font-semibold text-amber-400 mb-2">{ch.point}</div>
                          <p className="text-xs text-zinc-300">{ch.challenge}</p>
                        </div>
                      ))}
                    </div>
                  )}

                  {defenseOutput.agreement_points?.length > 0 && (
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold text-zinc-500 uppercase tracking-widest">Conceded Points</h4>
                      {defenseOutput.agreement_points.map((p, i) => (
                        <div key={i} className="flex gap-3 text-sm text-zinc-300 p-3 bg-white/5 rounded-lg">
                          <CheckCircle2 size={16} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                          <p>{p}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </motion.div>
          )}

          {/* VALIDATOR */}
          {activeTab === "validator" && (
            <motion.div
              key="validator"
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 10 }}
              className="space-y-6"
            >
              {!validatorOutput && isStreaming && (
                <div className="flex items-center gap-3 text-purple-400 p-4 premium-glass-strong rounded-xl">
                  <span className="spinner border-t-purple-400" /> Synthesizing final judgment...
                </div>
              )}

              {validatorOutput && (
                <>
                  <div className="flex flex-col items-center justify-center p-8 premium-glass-strong rounded-xl border border-white/10 text-center relative overflow-hidden">
                    <div className="absolute inset-0 bg-gradient-to-t from-purple-500/10 to-transparent pointer-events-none" />
                    <Scale size={48} className="text-purple-400 mb-4" />
                    <div className="text-3xl font-display font-bold text-white mb-2">{validatorOutput.confidence}%</div>
                    <div className="text-sm text-zinc-400 font-mono tracking-widest uppercase">System Confidence</div>
                  </div>

                  {validatorOutput.debate_summary && (
                    <div className="space-y-4">
                      {validatorOutput.debate_summary.prosecutor_accepted?.length > 0 && (
                        <div>
                          <div className="text-xs font-semibold text-indigo-400 mb-2 pl-2">Accepted Legal Premises</div>
                          <ul className="space-y-2">
                            {validatorOutput.debate_summary.prosecutor_accepted.map((v, i) => (
                              <li key={i} className="flex gap-2 text-sm text-zinc-300 bg-white/5 p-3 rounded-lg border border-white/5">
                                <ChevronRight size={16} className="text-indigo-500 flex-shrink-0 mt-0.5" />
                                {v}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {validatorOutput.debate_summary.defense_accepted?.length > 0 && (
                        <div>
                          <div className="text-xs font-semibold text-emerald-400 mb-2 pl-2">Accepted Defenses</div>
                          <ul className="space-y-2">
                            {validatorOutput.debate_summary.defense_accepted.map((v, i) => (
                              <li key={i} className="flex gap-2 text-sm text-zinc-300 bg-white/5 p-3 rounded-lg border border-white/5">
                                <ChevronRight size={16} className="text-emerald-500 flex-shrink-0 mt-0.5" />
                                {v}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
