"use client";
import { useState, useEffect } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Scale, LogIn, LogOut, User, Activity, Menu } from "lucide-react";
import { isLoggedIn, getStoredUser, logout } from "@/lib/api";
import { useRouter } from "next/navigation";

export default function Navbar({ onToggleSidebar }) {
  const [user, setUser] = useState(null);
  const router = useRouter();

  useEffect(() => {
    if (isLoggedIn()) {
      setUser(getStoredUser());
    }
  }, []);

  const handleLogout = async () => {
    await logout();
    setUser(null);
    // Reload page to reset state safely
    window.location.reload();
  };

  const handleAuthSuccess = () => {
    setUser(getStoredUser());
  };

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 h-[72px] z-40 premium-glass flex items-center justify-between px-6 border-b border-white/5">
        
        <div className="flex items-center gap-4">
          {onToggleSidebar && (
            <button 
              onClick={onToggleSidebar}
              className="p-2 rounded-lg text-zinc-400 hover:bg-white/5 hover:text-white transition-colors"
            >
              <Menu size={20} />
            </button>
          )}
          
          <Link href="/" className="flex items-center gap-3 decoration-transparent">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
              <Scale className="text-white" size={20} />
            </div>
            <div className="flex flex-col">
              <span className="font-display font-bold text-lg leading-tight tracking-tight text-white">NYAYA-SAATHI</span>
              <span className="text-[0.65rem] font-semibold tracking-widest text-indigo-400 uppercase">Enterprise Mode</span>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-2">
          {/* Status Indicator */}
          <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 mr-4">
            <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-xs font-medium text-emerald-400">System Online</span>
          </div>

          <Link href="/procedures" className="flex flex-center gap-2 text-sm font-medium text-indigo-400 hover:text-indigo-300 underline underline-offset-4 decoration-indigo-500/30 hover:decoration-indigo-400 transition-colors px-2">
            Workflows
          </Link>
          <Link href="/know-your-rights" className="flex flex-center gap-2 text-sm font-medium text-indigo-400 hover:text-indigo-300 underline underline-offset-4 decoration-indigo-500/30 hover:decoration-indigo-400 transition-colors px-2">
            Explore Rights
          </Link>

          <div className="w-px h-6 bg-white/10 mx-2" />

          {user ? (
            <div className="flex items-center gap-3">
              <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10">
                <User size={14} className="text-zinc-400" />
                <span className="text-sm font-medium text-zinc-300">{user.name.split(" ")[0]}</span>
              </div>
              <button 
                onClick={handleLogout}
                className="p-2 rounded-full text-zinc-400 hover:text-white hover:bg-red-500/10 hover:border-red-500/20 transition-all border border-transparent"
                title="Sign Out"
              >
                <LogOut size={16} />
              </button>
            </div>
          ) : (
            <Link 
              href="/auth"
              className="btn-primary"
            >
              <LogIn size={16} />
              Sign In
            </Link>
          )}
        </div>
      </nav>

    </>
  );
}
