"use client";
import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";

const COMMANDS = [
  { id: "chat", label: "💬 Go to Chat", shortcut: "C", action: "navigate", path: "/chat" },
  { id: "rights", label: "📚 Know Your Rights", shortcut: "R", action: "navigate", path: "/know-your-rights" },
  { id: "procedures", label: "📋 Legal Procedures", shortcut: "P", action: "navigate", path: "/procedures" },
  { id: "home", label: "🏠 Home", shortcut: "H", action: "navigate", path: "/" },
  { id: "new-chat", label: "➕ New Chat", shortcut: "N", action: "new-chat" },
  { id: "fir", label: "🚔 How to File FIR", action: "navigate", path: "/procedures" },
  { id: "consumer", label: "🛒 Consumer Complaint", action: "navigate", path: "/procedures" },
  { id: "cybercrime", label: "💻 Report Cybercrime", action: "navigate", path: "/procedures" },
  { id: "helplines", label: "📞 Emergency Helplines", action: "show-helplines" },
  { id: "search-rights", label: "🔍 Search Legal Rights...", action: "navigate", path: "/know-your-rights" },
];

const HELPLINES = [
  { name: "Emergency", number: "112" },
  { name: "Women Helpline", number: "181" },
  { name: "Cybercrime", number: "1930" },
  { name: "Child Safety", number: "1098" },
  { name: "Legal Aid (NALSA)", number: "15100" },
  { name: "Consumer", number: "1800-11-4000" },
];

export default function CommandPalette() {
  const [isOpen, setIsOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(0);
  const [showHelplines, setShowHelplines] = useState(false);
  const inputRef = useRef(null);
  const router = useRouter();

  const filtered = COMMANDS.filter((cmd) =>
    cmd.label.toLowerCase().includes(query.toLowerCase())
  );

  // Keyboard shortcut to open
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setIsOpen((v) => !v);
        setQuery("");
        setSelected(0);
        setShowHelplines(false);
      }
      if (e.key === "Escape") {
        setIsOpen(false);
        setShowHelplines(false);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  useEffect(() => {
    if (isOpen) inputRef.current?.focus();
  }, [isOpen]);

  const executeCommand = useCallback((cmd) => {
    if (cmd.action === "navigate") {
      router.push(cmd.path);
    } else if (cmd.action === "show-helplines") {
      setShowHelplines(true);
      return; // Don't close
    } else if (cmd.action === "new-chat") {
      router.push("/chat");
      // Could emit event to clear chat state
    }
    setIsOpen(false);
    setQuery("");
  }, [router]);

  const handleKeyDown = (e) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelected((s) => Math.min(s + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelected((s) => Math.max(s - 1, 0));
    } else if (e.key === "Enter" && filtered[selected]) {
      executeCommand(filtered[selected]);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="cmd-overlay" onClick={() => setIsOpen(false)}>
      <div className="cmd-palette" onClick={(e) => e.stopPropagation()}>
        <div className="cmd-input-wrapper">
          <span className="cmd-icon">⌘</span>
          <input
            ref={inputRef}
            className="cmd-input"
            placeholder="Type a command or search..."
            value={query}
            onChange={(e) => { setQuery(e.target.value); setSelected(0); setShowHelplines(false); }}
            onKeyDown={handleKeyDown}
          />
          <kbd className="cmd-kbd">ESC</kbd>
        </div>

        {showHelplines ? (
          <div className="cmd-results">
            <div className="cmd-group-label">📞 Emergency Helplines</div>
            {HELPLINES.map((h) => (
              <div key={h.number} className="cmd-item helpline-cmd">
                <span>{h.name}</span>
                <a href={`tel:${h.number}`} className="helpline-number">{h.number}</a>
              </div>
            ))}
            <button className="cmd-back" onClick={() => setShowHelplines(false)}>← Back</button>
          </div>
        ) : (
          <div className="cmd-results">
            <div className="cmd-group-label">Actions</div>
            {filtered.map((cmd, i) => (
              <div
                key={cmd.id}
                className={`cmd-item ${i === selected ? "selected" : ""}`}
                onClick={() => executeCommand(cmd)}
                onMouseEnter={() => setSelected(i)}
              >
                <span>{cmd.label}</span>
                {cmd.shortcut && <kbd className="cmd-shortcut">{cmd.shortcut}</kbd>}
              </div>
            ))}
            {filtered.length === 0 && (
              <div className="cmd-empty">No matching commands</div>
            )}
          </div>
        )}

        <div className="cmd-footer">
          <span>↑↓ Navigate</span>
          <span>↵ Select</span>
          <span>ESC Close</span>
        </div>
      </div>
    </div>
  );
}
