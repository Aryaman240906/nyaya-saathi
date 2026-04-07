"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { 
  ChevronLeft, 
  Search, 
  Clock, 
  FileText, 
  Briefcase, 
  ShieldAlert, 
  Globe, 
  Phone, 
  CheckCircle2, 
  ArrowRight,
  Gavel,
  ShoppingCart,
  ShieldCheck,
  Building2,
  Users
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { getProcedures, getProcedure } from "@/lib/api";

const FALLBACK_PROCEDURES = [
  { id: "fir_filing", title: "How to File an FIR", title_hi: "एफआईआर कैसे दर्ज करें", description: "Step-by-step guide to filing a First Information Report", category: "criminal" },
  { id: "consumer_complaint", title: "Consumer Complaint", title_hi: "उपभोक्ता शिकायत", description: "File a complaint for defective goods or deficient services", category: "consumer" },
  { id: "cybercrime_report", title: "Report Cybercrime", title_hi: "साइबर अपराध रिपोर्ट", description: "Report online fraud, hacking, and identity theft", category: "cyber" },
  { id: "rti_application", title: "File RTI Application", title_hi: "RTI आवेदन दाखिल करें", description: "Right to Information application process", category: "governance" },
  { id: "bail_application", title: "Apply for Bail", title_hi: "ज़मानत आवेदन", description: "Bail application process for bailable and non-bailable offences", category: "criminal" },
  { id: "labour_dispute", title: "Labour/Employment Complaint", title_hi: "श्रम शिकायत", description: "File complaints for unpaid wages, wrongful termination", category: "labour" },
];

export default function ProceduresPage() {
  const [procedures, setProcedures] = useState(FALLBACK_PROCEDURES);
  const [selectedProcedure, setSelectedProcedure] = useState(null);
  const [procedureDetail, setProcedureDetail] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getProcedures()
      .then(setProcedures)
      .catch(() => setProcedures(FALLBACK_PROCEDURES));
  }, []);

  const handleSelectProcedure = async (procId) => {
    setSelectedProcedure(procId);
    setLoading(true);
    try {
      const data = await getProcedure(procId);
      setProcedureDetail(data);
    } catch {
      setProcedureDetail(null);
    }
    setLoading(false);
  };

  const getCategoryIcon = (cat) => {
    const icons = { 
      criminal: <Gavel className="text-red-400" size={24} />, 
      consumer: <ShoppingCart className="text-amber-400" size={24} />, 
      cyber: <ShieldAlert className="text-cyan-400" size={24} />, 
      governance: <Building2 className="text-indigo-400" size={24} />, 
      labour: <Briefcase className="text-emerald-400" size={24} /> 
    };
    return icons[cat] || <FileText className="text-zinc-400" size={24} />;
  };

  return (
    <div className="min-h-screen bg-[#050508] text-white">
      <Navbar />

      <div className="max-w-7xl mx-auto px-6 pt-32 pb-24">
        <AnimatePresence mode="wait">
          {!selectedProcedure ? (
            <motion.div
              key="list"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
            >
              <div className="mb-12">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-bold uppercase tracking-wider mb-4">
                  <ShieldCheck size={14} />
                  Procedural Intelligence
                </div>
                <h1 className="text-4xl md:text-5xl font-display font-bold mb-4 tracking-tight">
                  Standard Legal <span className="text-indigo-400">Workflows</span>
                </h1>
                <p className="text-zinc-400 text-lg max-w-2xl leading-relaxed">
                  Verified step-by-step guides for navigating the Indian legal system. 
                  Get clarity on requirements, timelines, and jurisdictional authorities.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {procedures.map((proc) => (
                  <motion.div
                    key={proc.id}
                    whileHover={{ y: -5 }}
                    onClick={() => handleSelectProcedure(proc.id)}
                    className="premium-glass-strong p-6 rounded-2xl cursor-pointer group hover:border-indigo-500/30 transition-all border border-white/5 shadow-lg"
                  >
                    <div className="w-12 h-12 bg-white/5 rounded-xl flex items-center justify-center mb-6 group-hover:bg-indigo-500/10 transition-colors">
                      {getCategoryIcon(proc.category)}
                    </div>
                    <div className="space-y-2">
                       <h3 className="text-xl font-bold font-display group-hover:text-indigo-400 transition-colors">
                         {proc.title}
                       </h3>
                       <p className="text-xs text-indigo-400/80 font-mono tracking-wide uppercase">
                         {proc.title_hi}
                       </p>
                       <p className="text-sm text-zinc-400 leading-relaxed pt-2">
                         {proc.description}
                       </p>
                    </div>
                    <div className="mt-6 pt-6 border-t border-white/5 flex items-center justify-between">
                      <span className="text-xs font-bold text-zinc-500 uppercase tracking-widest">{proc.category}</span>
                      <ArrowRight size={18} className="text-zinc-600 group-hover:text-indigo-400 group-hover:translate-x-1 transition-all" />
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="detail"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="max-w-4xl mx-auto"
            >
              <button
                onClick={() => { setSelectedProcedure(null); setProcedureDetail(null); }}
                className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors mb-8 group"
              >
                <ChevronLeft size={20} className="group-hover:-translate-x-1 transition-transform" />
                <span className="font-medium">Back to Workflows</span>
              </button>

              {loading ? (
                <div className="flex flex-col items-center justify-center py-24 gap-4">
                  <div className="spinner w-12 h-12 border-4" />
                  <span className="text-zinc-500 font-mono text-sm animate-pulse">Retrieving Procedure Schema...</span>
                </div>
              ) : procedureDetail ? (
                <div className="space-y-12">
                  <header>
                    <h1 className="text-4xl md:text-5xl font-display font-bold mb-2 tracking-tight">
                      {procedureDetail.title}
                    </h1>
                    <p className="text-lg text-indigo-400 font-medium mb-6">{procedureDetail.title_hi}</p>
                    <div className="p-6 premium-glass rounded-2xl border-l-4 border-indigo-500">
                       <p className="text-zinc-300 leading-relaxed text-lg italic">
                         &ldquo;{procedureDetail.description}&rdquo;
                       </p>
                    </div>
                  </header>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {procedureDetail.estimated_timeline && (
                      <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center gap-4">
                         <div className="w-10 h-10 rounded-lg bg-amber-500/20 flex items-center justify-center">
                            <Clock className="text-amber-400" size={20} />
                         </div>
                         <div>
                            <div className="text-[0.65rem] font-bold text-amber-500/60 uppercase tracking-widest">Est. Timeline</div>
                            <div className="font-semibold text-amber-200">{procedureDetail.estimated_timeline}</div>
                         </div>
                      </div>
                    )}
                    {procedureDetail.category && (
                      <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center gap-4">
                         <div className="w-10 h-10 rounded-lg bg-indigo-500/20 flex items-center justify-center">
                            {getCategoryIcon(procedureDetail.category)}
                         </div>
                         <div>
                            <div className="text-[0.65rem] font-bold text-indigo-500/60 uppercase tracking-widest">Legal Category</div>
                            <div className="font-semibold text-indigo-200 capitalize">{procedureDetail.category}</div>
                         </div>
                      </div>
                    )}
                  </div>

                  <div className="space-y-6 text-zinc-300">
                    <h3 className="text-2xl font-display font-bold flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg bg-indigo-500/20 flex items-center justify-center">
                        <CheckCircle2 className="text-indigo-400" size={18} />
                      </div>
                      Action Steps
                    </h3>
                    
                    <div className="space-y-4">
                      {procedureDetail.steps?.map((step, i) => (
                        <div key={i} className="premium-glass-strong p-6 rounded-2xl border border-white/5 relative overflow-hidden group">
                          <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:opacity-10 transition-opacity">
                            <span className="text-9xl font-black">{step.step_number}</span>
                          </div>
                          <div className="relative flex gap-6">
                            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-indigo-500 flex items-center justify-center text-xs font-bold text-white shadow-lg shadow-indigo-500/40">
                              {step.step_number}
                            </div>
                            <div className="flex-1 space-y-4">
                              <div>
                                <h4 className="text-xl font-bold mb-2 text-white">{step.action}</h4>
                                <p className="text-zinc-400 text-sm leading-relaxed">{step.details}</p>
                              </div>
                              <div className="flex flex-wrap gap-4 pt-2">
                                {step.timeline && (
                                  <div className="flex items-center gap-2 text-xs text-amber-400 px-3 py-1 bg-amber-400/5 border border-amber-400/20 rounded-full">
                                    <Clock size={12} /> {step.timeline}
                                  </div>
                                )}
                                {step.documents_needed?.map((doc, idx) => (
                                  <div key={idx} className="flex items-center gap-2 text-xs text-cyan-400 px-3 py-1 bg-cyan-400/5 border border-cyan-400/20 rounded-full">
                                    <FileText size={12} /> {doc}
                                  </div>
                                ))}
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-12 pt-8">
                    {procedureDetail.relevant_authorities?.length > 0 && (
                      <div className="space-y-6">
                        <h3 className="text-xl font-display font-bold flex items-center gap-3">
                          <Building2 className="text-indigo-400" size={20} />
                          Authorities
                        </h3>
                        {procedureDetail.relevant_authorities.map((auth, i) => (
                          <div key={i} className="p-5 premium-glass border border-white/5 rounded-2xl group hover:border-indigo-500/20 transition-all">
                            <h4 className="font-bold mb-3 group-hover:text-indigo-400 transition-colors uppercase text-sm tracking-wide">{auth.name}</h4>
                            <div className="space-y-2">
                              {auth.contact && (
                                <div className="flex items-center gap-3 text-emerald-400 text-xs font-mono">
                                  <Phone size={12} /> {auth.contact}
                                </div>
                              )}
                              {auth.url && (
                                <div className="flex items-center gap-3 text-indigo-400 text-xs font-mono truncate">
                                  <Globe size={12} /> {auth.url}
                                </div>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}

                    {procedureDetail.helplines?.length > 0 && (
                      <div className="space-y-6">
                        <h3 className="text-xl font-display font-bold flex items-center gap-3">
                          <Users className="text-emerald-400" size={20} />
                          Support Helplines
                        </h3>
                        <div className="grid grid-cols-1 gap-4">
                          {procedureDetail.helplines.map((h, i) => (
                            <div key={i} className="p-5 bg-emerald-500/5 border border-emerald-500/10 rounded-2xl flex flex-col justify-between">
                              <div className="text-[0.65rem] text-emerald-500/60 font-bold uppercase tracking-widest mb-1">{h.name}</div>
                              <div className="text-2xl font-black text-emerald-400 font-mono tracking-tighter">{h.number}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {procedureDetail.tips?.length > 0 && (
                    <div className="p-8 premium-glass-strong border border-emerald-500/20 rounded-3xl bg-emerald-500/5 mt-12">
                      <div className="flex items-center gap-4 mb-6">
                        <div className="w-12 h-12 rounded-2xl bg-emerald-500/20 flex items-center justify-center">
                           <ShieldCheck className="text-emerald-400" size={24} />
                        </div>
                        <div>
                          <h3 className="text-xl font-display font-bold">Expert Compliance Tips</h3>
                          <p className="text-emerald-500/60 text-xs font-bold uppercase tracking-widest">Legal Best Practices</p>
                        </div>
                      </div>
                      <ul className="space-y-4">
                        {procedureDetail.tips.map((tip, i) => (
                          <li key={i} className="flex gap-4 text-zinc-300 leading-relaxed">
                            <span className="text-emerald-500 font-bold mt-1">•</span>
                            {tip}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                </div>
              ) : (
                <div className="text-center py-24 premium-glass border border-white/5 rounded-3xl">
                   <ShieldAlert size={48} className="mx-auto text-zinc-600 mb-6" />
                   <h2 className="text-xl font-bold mb-2">Remote Procedure Not Found</h2>
                   <p className="text-zinc-500">The neural engine is online but the specific procedure trace is missing from our corpus.</p>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
