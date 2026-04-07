"use client";
const API_URL = process.env.NEXT_PUBLIC_API_URL;
import { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Loader2, Sparkles, AlertCircle, FileText, Bot, Shield, Scale, Mic, Zap, Paperclip, Download, X } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";

import Navbar from "@/components/Navbar";
import HistorySidebar from "@/components/HistorySidebar";
import DebateViewer from "@/components/DebateViewer";
import FormTemplateBar from "@/components/FormTemplateBar";
import { sendChatMessage, getSession, isLoggedIn } from "@/lib/api";

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [language, setLanguage] = useState("en");
  const [isRecording, setIsRecording] = useState(false);
  const [reasoningMode, setReasoningMode] = useState("debate");

  // V4: Document Upload
  const [attachedFile, setAttachedFile] = useState(null);
  const [filePreview, setFilePreview] = useState(null);
  const fileInputRef = useRef(null);



  // V4: Voice Recognition
  const recognitionRef = useRef(null);

  // App State
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [isDesktop, setIsDesktop] = useState(false); // Default to false so SSR yields 0px marginLeft, avoiding hydration mismatch. Then effect corrects it.

  useEffect(() => {
    const handleResize = () => setIsDesktop(window.innerWidth >= 1024);
    handleResize(); // set initially
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Debate engine real-time state
  const [debateVisible, setDebateVisible] = useState(false);
  const [prosecutorOutput, setProsecutorOutput] = useState(null);
  const [defenseOutput, setDefenseOutput] = useState(null);
  const [validatorOutput, setValidatorOutput] = useState(null);
  const [finalResponse, setFinalResponse] = useState(null);

  const messagesEndRef = useRef(null);
  const messageRefs = useRef({});

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, debateVisible, prosecutorOutput, defenseOutput, validatorOutput]);

  // ── V4: Initialize Web Speech API ──────────────────────────────────
  useEffect(() => {
    if (typeof window === "undefined") return;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      let finalTranscript = "";
      let interimTranscript = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcript;
        } else {
          interimTranscript += transcript;
        }
      }
      if (finalTranscript) {
        setInput(prev => prev + finalTranscript);
      } else if (interimTranscript) {
        // Show interim in a non-destructive way
      }
    };

    recognition.onend = () => {
      setIsRecording(false);
    };

    recognition.onerror = (event) => {
      console.error("Speech recognition error:", event.error);
      setIsRecording(false);
    };

    recognitionRef.current = recognition;
  }, []);

  // Update recognition language when language selector changes
  useEffect(() => {
    if (recognitionRef.current) {
      const langMap = { en: "en-IN", hi: "hi-IN", hinglish: "hi-IN" };
      recognitionRef.current.lang = langMap[language] || "en-IN";
    }
  }, [language]);

  // ── V4: Voice start/stop ────────────────────────────────────────────
  const toggleRecording = useCallback(() => {
    if (!recognitionRef.current) {
      setError("Voice recognition is not supported in this browser. Please use Chrome.");
      return;
    }
    if (isRecording) {
      recognitionRef.current.stop();
      setIsRecording(false);
    } else {
      recognitionRef.current.start();
      setIsRecording(true);
    }
  }, [isRecording]);

  // ── V4: File Upload Handler ─────────────────────────────────────────
  const handleFileSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setAttachedFile(file);
    if (file.type.startsWith("image/")) {
      const reader = new FileReader();
      reader.onload = (ev) => setFilePreview(ev.target.result);
      reader.readAsDataURL(file);
    } else {
      setFilePreview(null);
    }
  };

  const clearAttachment = () => {
    setAttachedFile(null);
    setFilePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };



  // ── V4: PDF Export ──────────────────────────────────────────────────
  const handleExportPDF = async (idx) => {
    const element = messageRefs.current[idx];
    if (!element) return;
    const html2pdf = (await import("html2pdf.js")).default;
    const opt = {
      margin: [15, 15, 20, 15],
      filename: `Nyaya-Saathi-Legal-Plan-${Date.now()}.pdf`,
      image: { type: "jpeg", quality: 0.98 },
      html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff" },
      jsPDF: { unit: "mm", format: "a4", orientation: "portrait" },
    };
    // Clone element and apply print-friendly styles
    const clone = element.cloneNode(true);
    clone.style.cssText = "color: #1a1a1a; background: #ffffff; padding: 24px; font-family: system-ui, sans-serif; font-size: 14px; line-height: 1.7; max-width: 100%;";
    clone.querySelectorAll("*").forEach(el => {
      el.style.color = el.style.color || "#1a1a1a";
      el.style.background = "transparent";
      el.style.border = el.style.border ? "1px solid #e0e0e0" : "";
    });
    // Add header
    const header = document.createElement("div");
    header.innerHTML = `<div style="border-bottom: 2px solid #4f46e5; padding-bottom: 12px; margin-bottom: 20px;"><h1 style="font-size:20px; font-weight:bold; color:#4f46e5; margin:0;">⚖️ NYAYA-SAATHI — Legal Action Plan</h1><p style="font-size:11px; color:#888; margin:4px 0 0 0;">Generated on ${new Date().toLocaleString("en-IN")} • This is AI-generated legal information, not professional legal advice.</p></div>`;
    clone.insertBefore(header, clone.firstChild);
    html2pdf().set(opt).from(clone).save();
  };

  const loadSession = async (sessionId) => {
    if (!sessionId) {
      // Clear for new chat
      setCurrentSessionId(null);
      setMessages([]);
      resetDebateState();
      return;
    }

    try {
      setIsLoading(true);
      const data = await getSession(sessionId);
      setCurrentSessionId(sessionId);
      setMessages(data.messages || []);
      resetDebateState();
    } catch (err) {
      console.error("Failed to load session:", err);
      setError("Failed to load conversation history.");
    } finally {
      setIsLoading(false);
    }
  };

  const resetDebateState = () => {
    setProsecutorOutput(null);
    setDefenseOutput(null);
    setValidatorOutput(null);
    setFinalResponse(null);
  };

  const handleSend = async (e) => {
    if (e) e.preventDefault();
    if (!input.trim() && !attachedFile) return;
    if (isLoading) return;

    const userQuery = input.trim();
    setInput("");
    setError(null);
    resetDebateState();

    // ── V4: If file is attached, route to document analysis ──────────
    if (attachedFile) {
      const fileName = attachedFile.name;
      setMessages(prev => [...prev, { role: "user", content: `📎 Uploaded: ${fileName}${userQuery ? `\n\n${userQuery}` : ""}` }]);
      setIsLoading(true);
      setDebateVisible(false);
      clearAttachment();

      try {
        const formData = new FormData();
        formData.append("file", attachedFile);
        if (userQuery) formData.append("text", userQuery);
        formData.append("language", language);

        const headers = {};
        if (typeof window !== "undefined") {
          const token = localStorage.getItem("ns_access_token");
          if (token) headers["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch(`${API_URL}/api/documents/analyze`, {
          method: "POST",
          headers,
          body: formData,
        });
        const data = await res.json();
        const analysis = data.analysis || data.error || "Could not analyze the document.";
        setMessages(prev => [...prev, { role: "assistant", content: analysis }]);
      } catch (err) {
        console.error(err);
        setError("Failed to analyze document.");
      } finally {
        setIsLoading(false);
      }
      return;
    }
    
    // Add user message instantly
    setMessages(prev => [...prev, { role: "user", content: userQuery }]);
    setIsLoading(true);
    setDebateVisible(reasoningMode === "debate"); // Show the reasoning panel only if in exact debate mode

    try {
      const { fetchEventSource } = await import('@microsoft/fetch-event-source');
      let responseText = "";

      const headers = { "Content-Type": "application/json" };
      if (typeof window !== "undefined") {
        const token = localStorage.getItem("ns_access_token");
        if (token) headers["Authorization"] = `Bearer ${token}`;
      }

      await fetchEventSource(`${API_URL}/api/chat`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          message: userQuery,
          session_id: currentSessionId,
          language: language,
          mode: reasoningMode
        }),
        onmessage(ev) {
          const chunk = JSON.parse(ev.data);

          switch (chunk.type) {
            case "debate_prosecutor":
              if (chunk.data.result) setProsecutorOutput(chunk.data.result);
              break;
            case "debate_defense":
              if (chunk.data.result) setDefenseOutput(chunk.data.result);
              break;
            case "debate_validator":
              if (chunk.data.confidence) setValidatorOutput(chunk.data);
              break;
            case "response":
              if (chunk.data.text) {
                responseText += chunk.data.text;
                // Add an artificial typing feel by updating the message buffer
                setFinalResponse(responseText); 
              }
              break;
            case "debate_complete":
              // Backend finishes. If brand new session, update URL/ID behind scenes
              if (chunk.data.session_id && !currentSessionId) {
                setCurrentSessionId(chunk.data.session_id);
              }
              break;
            case "error":
              setError(chunk.data.message);
              break;
          }
        },
        onerror(err) {
          console.error("SSE Error:", err);
          setError("Connection lost. Please try again.");
          throw err; // Stop retrying
        }
      });

      // After streaming finishes, commit to standard messages array
      if (responseText) {
        setMessages(prev => [...prev, { role: "assistant", content: responseText }]);
      }

    } catch (err) {
      console.error(err);
      setError("Failed to communicate with the reasoning engine.");
    } finally {
      setIsLoading(false);
      // We leave setDebateVisible(true) so the user can inspect the final graph
    }
  };

  const handleSuggestionClick = (msg) => {
    setInput(msg);
  };

  const formatLegalContent = (content) => {
    if (!content) return "";
    let formatted = content;
    
    // Clean up snake_case labels from DB to readable text
    formatted = formatted.replace(/act_?(\d+[A-Z]?)/gi, 'Act $1');
    formatted = formatted.replace(/section_?(\d+[A-Z]?)/gi, 'Section $1');

    // Detect raw Section format from fallback mode: [ACT Section X] Title
    formatted = formatted.replace(/\[([A-Z0-9 ]+ Section [0-9A-Z_]+)\] ([^\n]+)/g, '### 🏛️ $1\n**$2**');
    
    // Turn legacy unparsed tags into clean headers instead of > [!NOTE] which might not render easily without css
    formatted = formatted.replace(/\[!NOTE\]/gi, '### 📝');
    formatted = formatted.replace(/\[!TIP\]/gi, '### 💡');
    formatted = formatted.replace(/Legal Text:/gi, '**Legal Text:**');
    formatted = formatted.replace(/Simplified Summary:/gi, '**Analysis:**');
    formatted = formatted.replace(/Simplified:/gi, '**Simplified Summary:**');
    
    return formatted;
  };

  return (
    <div className="app-layout">
      <Navbar onToggleSidebar={() => setSidebarOpen(!sidebarOpen)} />
      
      <HistorySidebar 
        isOpen={sidebarOpen} 
        onClose={() => setSidebarOpen(false)} 
        onSelectSession={loadSession}
        currentSessionId={currentSessionId}
      />

      <main 
        className="app-main-pane"
        style={{ marginLeft: sidebarOpen && isDesktop ? '320px' : '0', transition: 'margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1)' }}
      >
        {/* Core Chat Console */}
        <div className={`flex-1 flex flex-col relative transition-all duration-300 ${debateVisible ? 'lg:w-[50%]' : 'w-full'}`}>
          <div className="flex-1 overflow-y-auto p-4 md:p-6 pb-40 space-y-6 scrollbar-hide">
            <div className="max-w-3xl mx-auto w-full flex flex-col gap-8 pb-32">
              
              {messages.length === 0 && !debateVisible ? (
                <motion.div 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex flex-col items-center justify-center pt-20"
                >
                  <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-purple-500/10 border border-indigo-500/20 flex flex-center mb-6 shadow-glow">
                    <Scale size={32} className="text-indigo-400" />
                  </div>
                  <h1 className="text-4xl md:text-5xl font-display font-light text-transparent bg-clip-text bg-gradient-to-r from-white to-zinc-400 mb-4 text-center">
                    Legal intelligence, <span className="font-bold text-indigo-400">clarified.</span>
                  </h1>
                  <p className="text-zinc-400 text-lg max-w-xl text-center mb-12">
                    Tri-modal retrieval cross-referenced across 16 constitutional and penal acts. Start by describing your situation or asking a specific legal query.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4 w-full max-w-2xl">
                    {[
                      { icon: <Shield size={18} className="text-indigo-400"/>, text: "I bought a defective product and the seller refuses to refund. What are my rights?" },
                      { icon: <FileText size={18} className="text-emerald-400"/>, text: "My employer fired me without notice after 2 years of work. Is this legal?" },
                      { icon: <AlertCircle size={18} className="text-amber-400"/>, text: "A builder is delaying possession of my flat by 2 years. How do I file a RERA complaint?" },
                      { icon: <Bot size={18} className="text-cyan-400"/>, text: "Someone is sharing my private pictures online without consent under IT Act." }
                    ].map((suggestion, idx) => (
                      <motion.button
                        key={idx}
                        whileHover={{ scale: 1.02, y: -2 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => handleSuggestionClick(suggestion.text)}
                        className="p-4 premium-glass-strong text-left hover:border-indigo-500/30 transition-all flex flex-col gap-3 group"
                      >
                        <div className="w-8 h-8 rounded-full bg-white/5 flex flex-center group-hover:bg-white/10 transition-colors">
                          {suggestion.icon}
                        </div>
                        <span className="text-sm text-zinc-300 leading-relaxed">
                          {suggestion.text}
                        </span>
                      </motion.button>
                    ))}
                  </div>
                </motion.div>
              ) : (
                <div className="space-y-8">
                  <AnimatePresence>
                    {messages.map((msg, idx) => (
                      <motion.div 
                        key={idx}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div className={`max-w-[85%] rounded-2xl p-5 ${
                          msg.role === 'user' 
                            ? 'bg-gradient-to-br from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-500/20 rounded-tr-sm' 
                            : 'premium-glass-strong rounded-tl-sm legal-text'
                        }`}>
                          {msg.role === 'user' ? (
                            <p className="text-[0.95rem]">{msg.content}</p>
                          ) : (
                            <>
                              <div ref={el => messageRefs.current[idx] = el}>
                                <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                                  {formatLegalContent(msg.content)}
                                </ReactMarkdown>
                              </div>
                              <FormTemplateBar content={msg.content} />
                              <div className="flex items-center gap-1 mt-3 pt-3 border-t border-white/5">
                                <button
                                  onClick={() => handleExportPDF(idx)}
                                  className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-300 hover:bg-white/5 transition-all text-xs flex items-center gap-1.5"
                                  title="Export as PDF"
                                >
                                  <Download size={14} />
                                  <span>Download PDF</span>
                                </button>
                              </div>
                            </>
                          )}
                        </div>
                      </motion.div>
                    ))}
                    
                    {/* Streaming Response Handle */}
                    {finalResponse && isLoading && (
                       <motion.div 
                         initial={{ opacity: 0 }}
                         animate={{ opacity: 1 }}
                         className="flex w-full justify-start"
                       >
                         <div className="max-w-[85%] rounded-2xl p-5 premium-glass-strong rounded-tl-sm legal-text relative">
                           <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
                             {finalResponse}
                           </ReactMarkdown>
                           <motion.div 
                             className="w-2 h-4 bg-indigo-400 absolute bottom-6 right-6 inline-block"
                             animate={{ opacity: [1, 0, 1] }}
                             transition={{ duration: 0.8, repeat: Infinity }}
                           />
                         </div>
                       </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Input Area */}
          <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-[#050508] via-[#050508]/80 to-transparent pt-12 pointer-events-none">
            <div className="max-w-3xl mx-auto w-full pointer-events-auto">
              
              {error && (
                <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/20 flex flex-center gap-2 text-red-400 text-sm">
                  <AlertCircle size={16} />
                  {error}
                  <button onClick={() => setError(null)} className="ml-auto underline">Dismiss</button>
                </div>
              )}

              <form onSubmit={handleSend} className="relative group mx-2">
                <div className="absolute inset-0 bg-gradient-to-r from-indigo-500/20 to-purple-500/20 rounded-2xl blur-xl group-focus-within:opacity-100 opacity-0 transition-opacity duration-500" />
                <div className="relative premium-glass-strong rounded-2xl flex items-end p-1.5 md:p-2 transition-all">

                  {/* Siri-like Blob Overlay during Recording */}
                  <AnimatePresence>
                    {isRecording && (
                      <motion.div 
                        initial={{ opacity: 0 }} 
                        animate={{ opacity: 1 }} 
                        exit={{ opacity: 0 }}
                        className="absolute inset-0 overflow-hidden rounded-2xl flex items-center justify-center bg-[#050508]/80 backdrop-blur-md z-10"
                      >
                        <motion.div
                          animate={{ 
                            scale: [1, 1.25, 0.9, 1.15, 1],
                            rotate: [0, 90, 180, 270, 360],
                            borderRadius: ["50%", "40% 60% 70% 30%", "60% 40% 30% 70%", "50%"]
                          }}
                          transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
                          className="w-full h-full absolute top-0 bg-gradient-to-r from-[#ff2a85] via-[#8a2be2] to-[#4169e1] opacity-40 blur-2xl"
                        />
                        <div className="flex flex-row items-center gap-3 z-20">
                           <Mic className="text-white animate-pulse" size={20} />
                           <span className="text-white font-medium text-sm tracking-wide">Listening...</span>
                           <button type="button" onClick={() => { recognitionRef.current?.stop(); setIsRecording(false); }} className="px-3 py-1 bg-white/10 rounded-full text-xs text-white hover:bg-white/20 transition-all font-medium border border-white/5">Cancel</button>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                  
                  <div className="px-2 pb-2 flex gap-2">
                    <select 
                      value={language} 
                      onChange={e => setLanguage(e.target.value)}
                      className="bg-zinc-800/50 border border-white/10 text-xs font-mono text-zinc-400 rounded-md py-1 px-2 hover:bg-zinc-800 transition-colors focus:outline-none appearance-none cursor-pointer"
                    >
                      <option value="en">EN</option>
                      <option value="hi">HI</option>
                      <option value="hinglish">HI-EN</option>
                    </select>
                    
                    <div className="flex bg-zinc-800/50 rounded-lg p-0.5 border border-white/5">
                      <button
                        type="button"
                        onClick={() => setReasoningMode("debate")}
                        title="Maximum accuracy via 4-agent verification (Slower)"
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all text-xs font-medium ${
                          reasoningMode === "debate" 
                            ? "bg-indigo-500/30 text-indigo-300 shadow-sm" 
                            : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        <Scale size={13} />
                        Debate
                      </button>
                      <button
                        type="button"
                        onClick={() => setReasoningMode("simple")}
                        title="Bypass multi-agent pipeline for rapid answers (Faster)"
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all text-xs font-medium ${
                          reasoningMode === "simple" 
                            ? "bg-emerald-500/20 text-emerald-400 shadow-sm" 
                            : "text-zinc-500 hover:text-zinc-300"
                        }`}
                      >
                        <Zap size={13} />
                        Instant
                      </button>
                    </div>
                  </div>

                  <textarea
                    rows={1}
                    value={input}
                    onChange={(e) => {
                      setInput(e.target.value);
                      e.target.style.height = 'auto';
                      e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px';
                    }}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        handleSend();
                      }
                    }}
                    placeholder="Describe your legal issue..."
                    className="flex-1 bg-transparent border-none outline-none resize-none py-3 px-2 text-white placeholder-zinc-500 max-h-[120px] font-sans"
                    dir="auto"
                  />

                  {/* V4: Hidden file input */}
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    accept="image/*,.pdf,.txt,.doc,.docx"
                    className="hidden"
                  />
                  
                  {/* V4: Paperclip Upload Button */}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="ml-1 p-2 md:p-3 rounded-xl transition-all flex flex-center flex-shrink-0 z-20 bg-white/5 text-zinc-500 hover:text-white hover:bg-white/10"
                    title="Upload a legal document or image"
                  >
                    <Paperclip size={18} />
                  </button>

                  <button
                    type="button"
                    onClick={toggleRecording}
                    className={`ml-1 p-2 md:p-3 rounded-xl transition-all flex flex-center flex-shrink-0 z-20 ${
                      isRecording 
                        ? 'bg-red-500 text-white shadow-lg shadow-red-500/25 hover:bg-red-400' 
                        : 'bg-white/5 text-zinc-500 hover:text-white hover:bg-white/10'
                    }`}
                    title={isRecording ? 'Stop recording' : 'Voice input'}
                  >
                    <Mic size={18} />
                  </button>

                  <button
                    type="submit"
                    disabled={isLoading || (!input.trim() && !attachedFile)}
                    className={`ml-1 p-2 md:p-3 rounded-xl transition-all flex flex-center flex-shrink-0 z-20 ${
                      (input.trim() || attachedFile) && !isLoading 
                        ? 'bg-indigo-500 text-white shadow-lg shadow-indigo-500/25 hover:bg-indigo-400 hover:scale-105' 
                        : 'bg-white/5 text-zinc-500 cursor-not-allowed'
                    }`}
                  >
                    {isLoading ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
                  </button>
                </div>

                {/* V4: File Attachment Preview */}
                {attachedFile && (
                  <div className="mx-2 mt-2 p-2 rounded-xl bg-white/5 border border-white/10 flex items-center gap-3">
                    {filePreview ? (
                      <img src={filePreview} alt="Preview" className="w-10 h-10 rounded-lg object-cover" />
                    ) : (
                      <div className="w-10 h-10 rounded-lg bg-indigo-500/10 flex items-center justify-center">
                        <FileText size={18} className="text-indigo-400" />
                      </div>
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-zinc-300 font-medium truncate">{attachedFile.name}</p>
                      <p className="text-[0.65rem] text-zinc-500">{(attachedFile.size / 1024).toFixed(1)} KB</p>
                    </div>
                    <button onClick={clearAttachment} className="p-1 rounded-full hover:bg-white/10 text-zinc-500 hover:text-white transition-all">
                      <X size={14} />
                    </button>
                  </div>
                )}
              </form>
              <div className="text-center mt-3 flex flex-center gap-2 text-xs text-zinc-600 font-mono">
                <Sparkles size={12} />
                Nyaya-Saathi 4.0 provides AI assistance. It is not professional legal advice.
              </div>
            </div>
          </div>
        </div>

        {/* Reasoning Visualizer Graph (Right Panel) */}
        <AnimatePresence>
          {debateVisible && (
            <motion.div 
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: "50%", opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              className="hidden lg:flex border-l border-white/5 bg-[#050508]/50"
            >
              <div className="w-[1000px] h-full overflow-y-auto custom-scrollbar p-6">
                <DebateViewer 
                  prosecutorOutput={prosecutorOutput}
                  defenseOutput={defenseOutput}
                  validatorOutput={validatorOutput}
                  isStreaming={isLoading}
                />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </main>
    </div>
  );
}
