import { Inter, JetBrains_Mono } from "next/font/google";
import CommandPalette from "@/components/CommandPalette";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const jetbrains = JetBrains_Mono({ subsets: ["latin"], variable: "--font-jetbrains" });

export const metadata = {
  title: "NYAYA-SAATHI 2.0 | AI Legal Engine for India",
  description: "AI-native multilingual legal assistance system with multi-agent debate architecture. Get instant legal awareness on Indian law, know your rights, and navigate legal procedures.",
  keywords: "legal aid, Indian law, IPC, BNS, consumer rights, FIR, cybercrime, legal assistant, AI legal",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrains.variable}`}>
      <body>
        <CommandPalette />
        {children}
      </body>
    </html>
  );
}
