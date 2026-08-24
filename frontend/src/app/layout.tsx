import type { Metadata } from "next";
import { Inter, Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

const plusJakarta = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Hesh Rec — AI Speech & Meeting Intelligence Platform",
  description: "SOC 2 & Executive Meeting Intelligence powered by Groq Whisper & Gemini",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${plusJakarta.variable} dark h-full antialiased`}>
      <body className="min-h-full flex flex-col bg-[#0c0d0e] text-[#f0f2f5] font-sans selection:bg-[#ff5c47]/20 selection:text-[#ff5c47]">
        {children}
      </body>
    </html>
  );
}
