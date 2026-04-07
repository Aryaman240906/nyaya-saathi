"use client";
import { FileText, ExternalLink } from "lucide-react";

const TEMPLATE_MAP = [
  {
    keywords: [/\bFIR\b/i, /first information report/i, /police complaint/i, /police station/i],
    title: "File an FIR Online",
    description: "National/State Police Portal",
    url: "https://digitalpolice.gov.in",
    icon: "🚔",
  },
  {
    keywords: [/consumer complaint/i, /consumer forum/i, /consumer protection/i, /consumer court/i, /defective product/i, /consumer rights/i],
    title: "Consumer Complaint Form",
    description: "National Consumer Helpline",
    url: "https://consumerhelpline.gov.in",
    icon: "🛒",
  },
  {
    keywords: [/\bRTI\b/, /right to information/i, /information act/i],
    title: "File RTI Application",
    description: "RTI Online Portal",
    url: "https://rtionline.gov.in",
    icon: "📝",
  },
  {
    keywords: [/\bRERA\b/i, /real estate/i, /builder delay/i, /flat possession/i, /property registration/i],
    title: "RERA Complaint Portal",
    description: "Real Estate Regulatory Authority",
    url: "https://rera.gov.in",
    icon: "🏗️",
  },
  {
    keywords: [/cybercrime/i, /cyber fraud/i, /online fraud/i, /\bUPI\b.*fraud/i, /hacking/i, /identity theft/i, /phishing/i],
    title: "Report Cybercrime",
    description: "National Cyber Crime Portal",
    url: "https://cybercrime.gov.in",
    icon: "💻",
  },
  {
    keywords: [/\bbail\b/i, /bail application/i, /anticipatory bail/i],
    title: "Bail Application Guide",
    description: "e-Courts Services",
    url: "https://services.ecourts.gov.in",
    icon: "⚖️",
  },
  {
    keywords: [/labour complaint/i, /unpaid wages/i, /wrongful termination/i, /minimum wages/i, /employment dispute/i],
    title: "Labour Complaint Portal",
    description: "EPFO / Labour Commission",
    url: "https://labour.gov.in",
    icon: "👷",
  },
  {
    keywords: [/domestic violence/i, /protection of women/i, /dowry/i, /sexual harassment/i, /women helpline/i],
    title: "Women Helpline & Support",
    description: "National Commission for Women",
    url: "http://ncw.nic.in/frmComp_Online.aspx",
    icon: "👩",
  },
  {
    keywords: [/legal aid/i, /free lawyer/i, /NALSA/i, /legal services/i],
    title: "Free Legal Aid",
    description: "NALSA — Legal Services Authority",
    url: "https://nalsa.gov.in",
    icon: "🏛️",
  },
];

export default function FormTemplateBar({ content }) {
  if (!content) return null;

  const matches = TEMPLATE_MAP.filter((template) =>
    template.keywords.some((regex) => regex.test(content))
  );

  if (matches.length === 0) return null;

  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {matches.map((template, idx) => (
        <a
          key={idx}
          href={template.url}
          target="_blank"
          rel="noopener noreferrer"
          className="group flex items-center gap-2.5 px-3.5 py-2 rounded-xl bg-white/[0.03] border border-white/10 hover:border-indigo-500/30 hover:bg-indigo-500/5 transition-all text-sm"
        >
          <span className="text-base">{template.icon}</span>
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-zinc-200 group-hover:text-indigo-300 transition-colors leading-tight">
              {template.title}
            </span>
            <span className="text-[0.6rem] text-zinc-500 font-mono tracking-wide">
              {template.description}
            </span>
          </div>
          <ExternalLink size={12} className="text-zinc-600 group-hover:text-indigo-400 transition-colors ml-1" />
        </a>
      ))}
    </div>
  );
}
