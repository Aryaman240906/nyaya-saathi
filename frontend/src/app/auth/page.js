"use client";
import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Lock, Mail, User, ArrowRight, ShieldCheck, Scale, ChevronLeft } from "lucide-react";
import { login, signup, isLoggedIn } from "@/lib/api";
import { useRouter } from "next/navigation";
import Link from "next/link";

export default function AuthPage() {
  const router = useRouter();
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [mounted, setMounted] = useState(false);

  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: ""
  });

  useEffect(() => {
    setMounted(true);
    if (isLoggedIn()) {
      router.push("/");
    }
  }, [router]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    // Client-side validation
    const email = formData.email.trim();
    const password = formData.password;
    const name = formData.name.trim();

    if (!email) { setError("Please enter your email address."); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { setError("Please enter a valid email address."); return; }
    if (!password || password.length < 6) { setError("Password must be at least 6 characters."); return; }
    if (!isLogin && !name) { setError("Please enter your name."); return; }

    setLoading(true);

    try {
      if (isLogin) {
        // Clear any stale tokens before login to prevent state conflicts
        if (typeof window !== "undefined") {
          localStorage.removeItem("ns_access_token");
          localStorage.removeItem("ns_refresh_token");
          localStorage.removeItem("ns_user");
          localStorage.removeItem("ns_current_session");
        }
        await login(email, password);
      } else {
        await signup(email, password, name);
      }
      // On success, forcefully redirect to root.
      window.location.href = "/";
    } catch (err) {
      const msg = err.message || "";
      // Translate common backend errors to friendly messages
      if (msg.includes("409") || msg.includes("already registered")) {
        setError("This email is already registered. Try signing in instead.");
      } else if (msg.includes("401") || msg.includes("Invalid")) {
        setError("Invalid email or password. If you previously created an account, the server may have been restarted. Please create a new account.");
      } else if (msg.includes("422") || msg.includes("validation")) {
        setError("Please check your input. Email must be valid and password at least 6 characters.");
      } else if (msg.includes("fetch") || msg.includes("Failed") || msg.includes("NetworkError")) {
        setError("Cannot connect to server. Please ensure the backend is running.");
      } else {
        setError(msg || "Authentication failed. Please try again.");
      }
      setLoading(false);
    }
  };

  if (!mounted) return null;

  const fadeUp = {
    hidden: { opacity: 0, y: 15 },
    visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: "easeOut" } },
    exit: { opacity: 0, y: -15, transition: { duration: 0.3 } }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-[#08080C]">
      {/* Decorative Left Side */}
      <div className="hidden lg:flex w-1/2 relative bg-[#030305] overflow-hidden flex-col justify-between p-12">
        <div className="absolute inset-0 bg-gradient-to-br from-indigo-600/10 via-purple-600/5 to-transparent z-0" />
        <div className="absolute top-[20%] left-[10%] w-[30vw] h-[30vw] rounded-full bg-indigo-500/20 blur-[120px] pointer-events-none" />
        <div className="absolute bottom-[20%] right-[10%] w-[20vw] h-[20vw] rounded-full bg-cyan-500/10 blur-[100px] pointer-events-none" />
        
        <div className="relative z-10 flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20 group-hover:scale-105 transition-transform">
              <Scale className="text-white" size={20} />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-lg leading-tight tracking-tight text-white">NYAYA-SAATHI</span>
              <span className="text-[0.65rem] font-semibold tracking-widest text-indigo-400 uppercase">Enterprise Mode</span>
            </div>
          </Link>
        </div>

        <div className="relative z-10 max-w-md">
          <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.2 }}>
            <h1 className="font-display text-5xl font-light leading-tight mb-6 text-white tracking-tight">
              Secure access to your <span className="font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-400 to-cyan-400">digital workspace.</span>
            </h1>
            <p className="text-zinc-400 text-lg leading-relaxed">
              Nyaya-Saathi protects your consultation history with enterprise-grade encryption. All data is localized securely.
            </p>
          </motion.div>
        </div>
        
        <div className="relative z-10">
          <div className="flex items-center gap-3 bg-white/5 border border-white/10 w-max px-4 py-3 rounded-2xl backdrop-blur-md">
            <ShieldCheck className="text-emerald-400" size={20} />
            <span className="text-sm font-medium text-zinc-300">End-to-End Encrypted Session</span>
          </div>
        </div>
      </div>

      {/* Auth Form Right Side */}
      <div className="w-full lg:w-1/2 flex items-center justify-center relative bg-[#08080C] px-6 py-12">
        <Link href="/" className="absolute top-8 left-8 lg:hidden flex items-center text-zinc-400 hover:text-white transition-colors text-sm font-medium gap-1">
          <ChevronLeft size={16} /> Back to App
        </Link>
        
        <div className="w-full max-w-sm">
          <AnimatePresence mode="wait">
            <motion.div
              key={isLogin ? "login" : "signup"}
              variants={fadeUp}
              initial="hidden"
              animate="visible"
              exit="exit"
            >
              <div className="mb-8">
                <h2 className="text-3xl font-display font-bold text-white mb-2">
                  {isLogin ? "Welcome back" : "Create an account"}
                </h2>
                <p className="text-zinc-400 text-sm">
                  {isLogin 
                    ? "Enter your credentials to continue." 
                    : "Join Nyaya-Saathi to save your sessions permanently."}
                </p>
              </div>

              <form onSubmit={handleSubmit} className="space-y-5">
                {!isLogin && (
                  <div className="group">
                    <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-1.5 transition-colors group-focus-within:text-indigo-400">Full Name</label>
                    <div className="relative">
                      <User className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500 group-focus-within:text-indigo-400 transition-colors" size={18} />
                      <input
                        type="text"
                        required
                        placeholder="John Doe"
                        autoComplete="name"
                        minLength={1}
                        className="input-field !pl-11 py-3 text-[15px] bg-zinc-900/50 border-zinc-800 focus:bg-zinc-900 focus:border-indigo-500/50"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                      />
                    </div>
                  </div>
                )}

                <div className="group">
                  <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-1.5 transition-colors group-focus-within:text-indigo-400">Email Address</label>
                  <div className="relative">
                    <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500 group-focus-within:text-indigo-400 transition-colors" size={18} />
                    <input
                      type="email"
                      required
                      placeholder="you@example.com"
                      autoComplete="email"
                      className="input-field !pl-11 py-3 text-[15px] bg-zinc-900/50 border-zinc-800 focus:bg-zinc-900 focus:border-indigo-500/50"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
                  </div>
                </div>

                <div className="group">
                  <label className="block text-xs font-semibold text-zinc-400 uppercase tracking-widest mb-1.5 transition-colors group-focus-within:text-indigo-400">Password</label>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 text-zinc-500 group-focus-within:text-indigo-400 transition-colors" size={18} />
                    <input
                      type="password"
                      required
                      placeholder="••••••••"
                      autoComplete={isLogin ? "current-password" : "new-password"}
                      minLength={6}
                      className="input-field !pl-11 py-3 text-[15px] bg-zinc-900/50 border-zinc-800 focus:bg-zinc-900 focus:border-indigo-500/50"
                      value={formData.password}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    />
                  </div>
                </div>

                {error && (
                  <motion.div 
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="p-3.5 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-start gap-2"
                  >
                    <div className="mt-0.5">⚠️</div>
                    <div className="leading-tight">{error}</div>
                  </motion.div>
                )}

                <button 
                  type="submit" 
                  disabled={loading}
                  className="w-full btn-primary justify-center mt-6 py-3.5 mt-8 shadow-indigo-500/25 hover:shadow-indigo-500/40 text-[15px] group relative overflow-hidden"
                >
                  <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out" />
                  <span className="relative z-10 flex items-center gap-2">
                    {loading ? (
                      <div className="spinner" />
                    ) : (
                      <>
                        {isLogin ? "Sign In" : "Create Account"}
                        <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                      </>
                    )}
                  </span>
                </button>
              </form>

              <div className="mt-8 pt-8 border-t border-white/5 text-center text-sm text-zinc-400">
                {isLogin ? "Don't have an account? " : "Already have an account? "}
                <button 
                  onClick={() => { setIsLogin(!isLogin); setError(""); setFormData({ name: "", email: "", password: "" }); }}
                  className="text-white hover:text-indigo-400 font-medium transition-colors"
                >
                  {isLogin ? "Sign up" : "Sign in"}
                </button>
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
}
