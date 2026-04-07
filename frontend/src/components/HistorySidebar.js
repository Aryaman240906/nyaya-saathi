"use client";
import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { MessageSquare, Trash2, Search, X, Loader2, Calendar } from "lucide-react";
import { getSessions, deleteSession, searchHistory, isLoggedIn } from "@/lib/api";

export default function HistorySidebar({ isOpen, onClose, onSelectSession, currentSessionId }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(searchQuery), 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  useEffect(() => {
    if (isOpen) {
      fetchHistory();
    }
  }, [isOpen, debouncedSearch]);

  const fetchHistory = async () => {
    setLoading(true);
    try {
      let data;
      if (debouncedSearch) {
        data = await searchHistory(debouncedSearch);
        setSessions(data.sessions || []);
      } else {
        data = await getSessions(1, 40);
        setSessions(data.items || data.sessions || []);
      }
    } catch (err) {
      console.error("Failed to load history:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    try {
      await deleteSession(id);
      setSessions(sessions.filter(s => s.id !== id));
      if (currentSessionId === id) {
        onSelectSession(null); // Clear active session if deleted
      }
    } catch (err) {
      console.error("Failed to delete:", err);
    }
  };

  const formatDate = (isoString) => {
    const date = new Date(isoString);
    const today = new Date();
    if (date.toDateString() === today.toDateString()) {
      return `Today, ${date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
  };

  const sidebarVariants = {
    closed: { x: "-100%", opacity: 0 },
    open: { x: 0, opacity: 1, transition: { type: "spring", stiffness: 300, damping: 30 } }
  };

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop for mobile */}
      <motion.div 
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/40 z-40 lg:hidden backdrop-blur-sm"
        onClick={onClose}
      />
      
      <motion.div
        variants={sidebarVariants}
        initial="closed"
        animate="open"
        exit="closed"
        className="fixed top-[72px] left-0 bottom-0 w-[320px] bg-[#0A0A0F] border-r border-white/5 z-40 flex flex-col shadow-2xl"
      >
        <div className="p-4 border-b border-white/5">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-zinc-500" size={16} />
            <input
              type="text"
              placeholder="Search history..."
              className="w-full bg-white/5 border border-white/10 rounded-lg py-2 pl-9 pr-8 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-indigo-500/50 transition-colors"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-white"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1 custom-scrollbar">
          {loading ? (
            <div className="flex flex-col flex-center h-40 text-zinc-500">
              <Loader2 className="animate-spin mb-2" size={24} />
              <span className="text-sm">Loading history...</span>
            </div>
          ) : sessions.length === 0 ? (
            <div className="flex flex-col flex-center h-40 text-zinc-500 text-center px-4">
              <MessageSquare className="mb-2 opacity-50" size={24} />
              <span className="text-sm">No conversations found.</span>
            </div>
          ) : (
            <AnimatePresence>
              {sessions.map((session) => (
                <motion.div
                  key={session.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  onClick={() => {
                    onSelectSession(session.id);
                    if (window.innerWidth < 1024) onClose();
                  }}
                  className={`group relative p-3 rounded-xl cursor-pointer transition-all border ${
                    currentSessionId === session.id 
                      ? "bg-indigo-500/10 border-indigo-500/30" 
                      : "bg-transparent border-transparent hover:bg-white/5 hover:border-white/10"
                  }`}
                >
                  <div className="flex justify-between items-start mb-1">
                    <h4 className={`text-sm font-medium truncate pr-6 ${
                      currentSessionId === session.id ? "text-indigo-300" : "text-zinc-200 group-hover:text-white"
                    }`}>
                      {session.title || "New Legal Query"}
                    </h4>
                    <button
                      onClick={(e) => handleDelete(e, session.id)}
                      className="absolute right-3 top-3 opacity-0 group-hover:opacity-100 text-zinc-500 hover:text-red-400 transition-opacity"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                  <div className="flex items-center gap-2 text-[0.7rem] text-zinc-500 font-mono">
                    <Calendar size={12} />
                    {formatDate(session.updated_at)}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          )}
        </div>
      </motion.div>
    </>
  );
}
