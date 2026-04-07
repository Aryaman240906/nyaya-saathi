"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Search, 
  BookOpen, 
  ShieldCheck, 
  UserCircle, 
  Scale, 
  ShoppingCart, 
  Globe, 
  Users, 
  Home, 
  ChevronRight,
  ChevronDown,
  ArrowLeft,
  Loader2,
  FileText,
  AlertCircle
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { getRightsCategories, getRightsByCategory, searchRights } from "@/lib/api";

const FALLBACK_CATEGORIES = [
  { id: "fundamental", title: "Fundamental Rights", title_hi: "मौलिक अधिकार", description: "Constitutional rights guaranteed to every citizen", icon: <Scale size={24} className="text-indigo-400" /> },
  { id: "criminal", title: "Criminal Rights", title_hi: "आपराधिक अधिकार", description: "Rights of accused persons and victims", icon: <ShieldCheck size={24} className="text-red-400" /> },
  { id: "consumer", title: "Consumer Rights", title_hi: "उपभोक्ता अधिकार", description: "Protection against unfair trade practices", icon: <ShoppingCart size={24} className="text-amber-400" /> },
  { id: "cyber", title: "Cyber & Digital Rights", title_hi: "साइबर अधिकार", description: "Online privacy and cybercrime laws", icon: <Globe size={24} className="text-cyan-400" /> },
  { id: "women", title: "Women's Rights", title_hi: "महिला अधिकार", description: "Legal protections against harassment and violence", icon: <UserCircle size={24} className="text-purple-400" /> },
  { id: "labour", title: "Labour & Employment", title_hi: "श्रम अधिकार", description: "Worker rights, wages, and workplace protections", icon: <Users size={24} className="text-emerald-400" /> },
  { id: "property", title: "Property Rights", title_hi: "संपत्ति अधिकार", description: "Land, housing, and property ownership", icon: <Home size={24} className="text-zinc-300" /> },
];

export default function KnowYourRightsPage() {
  const [categories, setCategories] = useState(FALLBACK_CATEGORIES);
  const [selectedCategory, setSelectedCategory] = useState(null);
  const [sections, setSections] = useState([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expandedSection, setExpandedSection] = useState(null);

  useEffect(() => {
    getRightsCategories()
      .then(setCategories)
      .catch(() => setCategories(FALLBACK_CATEGORIES));
  }, []);

  const handleCategoryClick = async (catId) => {
    setSelectedCategory(catId);
    setLoading(true);
    setSearchResults([]);
    setSearchQuery("");
    try {
      const data = await getRightsByCategory(catId);
      setSections(data.sections || []);
    } catch {
      setSections([]);
    }
    setLoading(false);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setSelectedCategory(null);
    try {
      const data = await searchRights(searchQuery);
      setSearchResults(data.results || []);
    } catch {
      setSearchResults([]);
    }
    setLoading(false);
  };

  return (
    <div className="min-h-screen bg-[#050508] text-white">
      <Navbar />

      <div className="max-w-7xl mx-auto px-6 pt-32 pb-24">
        {/* Header Section */}
        <div className="mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold uppercase tracking-wider mb-4">
            <BookOpen size={14} />
            Legal Library
          </div>
          <h1 className="text-4xl md:text-5xl font-display font-bold mb-4 tracking-tight">
            Explore Your <span className="text-indigo-400">Legal Rights</span>
          </h1>
          <p className="text-zinc-400 text-lg max-w-2xl leading-relaxed">
            Every citizen is empowered by the law. Search through 2,000+ provisions 
            of constitutional, criminal, and civil rights in India.
          </p>
        </div>

        {/* Dynamic Search Bar */}
        <div className="max-w-3xl mx-auto mb-16 relative group">
          <div className="absolute inset-0 bg-indigo-500/10 rounded-2xl blur-xl group-focus-within:bg-indigo-500/20 transition-all" />
          <div className="relative premium-glass-strong p-2 rounded-2xl flex items-center gap-2 border border-white/5 transition-all focus-within:border-indigo-500/30">
            <div className="pl-4 text-zinc-500">
              <Search size={20} />
            </div>
            <input
              type="text"
              className="flex-1 bg-transparent border-none outline-none py-3 px-2 text-white placeholder-zinc-500 font-sans"
              placeholder="Search for rights (e.g., 'right to bail', 'fair wages')..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            />
            <button 
              onClick={handleSearch}
              className="btn-primary"
              style={{ padding: '10px 24px' }}
            >
              Search
            </button>
          </div>
        </div>

        <AnimatePresence mode="wait">
          {/* Main Content Areas */}
          {loading ? (
            <motion.div 
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex flex-col items-center justify-center py-24 gap-4"
            >
              <Loader2 className="w-12 h-12 text-indigo-500 animate-spin" />
              <span className="text-zinc-500 font-mono text-sm animate-pulse">Scanning Legal Corpus...</span>
            </motion.div>
          ) : !selectedCategory && searchResults.length === 0 ? (
            <motion.div
              key="categories"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
            >
              {categories.map((cat) => (
                <motion.div
                  key={cat.id}
                  whileHover={{ y: -5, scale: 1.02 }}
                  onClick={() => handleCategoryClick(cat.id)}
                  className="premium-glass p-6 rounded-2xl cursor-pointer group border border-white/5 shadow-lg transition-all hover:bg-white/[0.03]"
                >
                  <div className="w-12 h-12 bg-white/5 rounded-xl flex items-center justify-center mb-6 group-hover:bg-indigo-500/10 transition-colors">
                    {cat.icon || <Scale size={24} className="text-zinc-500" />}
                  </div>
                  <h3 className="text-lg font-bold font-display group-hover:text-indigo-400 transition-colors mb-2">
                    {cat.title}
                  </h3>
                  <div className="text-[0.65rem] text-indigo-400/80 font-bold tracking-widest uppercase mb-3">
                    {cat.title_hi}
                  </div>
                  <p className="text-sm text-zinc-400 leading-relaxed">
                    {cat.description}
                  </p>
                </motion.div>
              ))}
            </motion.div>
          ) : (
            <motion.div
              key="results"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              className="max-w-4xl mx-auto"
            >
              <button
                onClick={() => { setSelectedCategory(null); setSearchResults([]); setSections([]); }}
                className="flex items-center gap-2 text-zinc-400 hover:text-white transition-colors mb-12 group"
              >
                <ArrowLeft size={18} className="group-hover:-translate-x-1 transition-transform" />
                <span className="font-medium">Back to All Categories</span>
              </button>

              <div className="mb-8">
                <h2 className="text-3xl font-display font-bold">
                  {selectedCategory ? categories.find(c => c.id === selectedCategory)?.title : `Search Results for "${searchQuery}"`}
                </h2>
                <div className="h-1 w-20 bg-indigo-500 mt-2 rounded-full" />
              </div>

              {(selectedCategory ? sections : searchResults).length === 0 ? (
                <div className="text-center py-24 premium-glass border border-white/5 rounded-3xl">
                   <AlertCircle size={48} className="mx-auto text-zinc-600 mb-6" />
                   <h2 className="text-xl font-bold mb-2">No matching provisions found</h2>
                   <p className="text-zinc-500">The corpus for this specific query hasn&apos;t been indexed yet.</p>
                </div>
              ) : (
                <div className="space-y-4">
                  {(selectedCategory ? sections : searchResults).map((section, i) => (
                    <motion.div
                      key={i}
                      layout
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      className={`premium-glass-strong rounded-2xl border border-white/5 overflow-hidden transition-all duration-300 ${expandedSection === section.id ? 'ring-2 ring-indigo-500/30' : ''}`}
                    >
                      <div 
                        className="p-6 cursor-pointer flex items-start justify-between gap-4"
                        onClick={() => setExpandedSection(expandedSection === section.id ? null : section.id)}
                      >
                        <div className="flex-1">
                          <div className="flex items-center gap-3 mb-2">
                             <span className="px-2 py-0.5 rounded-md bg-indigo-500 text-[0.65rem] font-black italic uppercase tracking-tighter text-white">
                               {section.short_name || section.act?.split(",")[0] || "LAW"} SEC {section.section_number}
                             </span>
                             {section.score && (
                               <span className="text-[0.65rem] font-mono text-emerald-400 bg-emerald-400/10 px-2 py-0.5 rounded border border-emerald-400/20">
                                 MATCH: {(section.score * 100).toFixed(1)}%
                               </span>
                             )}
                          </div>
                          <h3 className="text-xl font-bold font-display text-white transition-colors group-hover:text-indigo-400">
                            {section.title}
                          </h3>
                          <p className="text-sm text-zinc-400 mt-3 leading-relaxed">
                            {section.simplified}
                          </p>
                        </div>
                        <div className={`mt-2 p-1.5 rounded-lg bg-white/5 text-zinc-500 transition-transform duration-300 ${expandedSection === section.id ? 'rotate-180 bg-indigo-500/20 text-indigo-400' : ''}`}>
                          <ChevronDown size={20} />
                        </div>
                      </div>

                      <AnimatePresence>
                        {expandedSection === section.id && (
                          <motion.div
                            initial={{ height: 0 }}
                            animate={{ height: "auto" }}
                            exit={{ height: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="px-6 pb-6 pt-2 border-t border-white/5 mt-2 bg-indigo-500/[0.02]">
                              <div className="flex items-center gap-3 mb-4 mt-4">
                                <FileText size={16} className="text-indigo-400" />
                                <span className="text-xs font-bold uppercase tracking-widest text-indigo-400/80">Verbatim Legal Text</span>
                              </div>
                              <div className="p-6 bg-[#050508] rounded-xl border border-white/5 font-mono text-[0.85rem] text-zinc-300 leading-relaxed shadow-inner">
                                {section.text}
                              </div>
                              <div className="mt-6 p-4 rounded-xl border border-indigo-500/10 bg-indigo-500/[0.05] flex items-center gap-4">
                                <div className="p-2 rounded-lg bg-indigo-500/20">
                                   <ShieldCheck size={18} className="text-indigo-400" />
                                </div>
                                <div className="text-xs text-zinc-400 leading-tight">
                                  This provision is current as of the latest 2024 penal code revisions. 
                                  Check with legal counsel for active judicial interpretations.
                                </div>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  ))}
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
