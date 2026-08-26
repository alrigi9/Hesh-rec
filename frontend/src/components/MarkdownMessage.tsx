"use client";

import React, { memo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownMessageProps {
  content: string;
  isUser?: boolean;
}

export const MarkdownMessage = memo(function MarkdownMessage({
  content,
  isUser = false,
}: MarkdownMessageProps) {
  if (!content) return null;

  // Auto-detect primary language direction (Arabic vs English)
  const isArabic = /[\u0600-\u06FF]/.test(content);

  if (isUser) {
    return (
      <div
        dir={isArabic ? "rtl" : "ltr"}
        className="whitespace-pre-wrap font-sans break-words text-white select-text text-xs leading-relaxed"
      >
        {content}
      </div>
    );
  }

  return (
    <div
      dir={isArabic ? "rtl" : "ltr"}
      className="markdown-content text-xs leading-relaxed text-[#f0f2f5] break-words select-text font-sans space-y-2.5"
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="text-sm sm:text-base font-bold text-[#f0f2f5] font-heading mt-3.5 mb-1.5 pb-1 border-b border-[#232529]/60">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-xs sm:text-sm font-bold text-[#f0f2f5] font-heading mt-3 mb-1.5 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#ff5c47] shrink-0" />
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-xs sm:text-xs font-semibold text-[#f0f2f5] font-heading mt-2.5 mb-1 text-[#ff8d7e]">
              {children}
            </h3>
          ),
          p: ({ children }) => (
            <p className="text-xs text-[#d1d5db] leading-relaxed mb-2 last:mb-0">
              {children}
            </p>
          ),
          strong: ({ children }) => (
            <strong className="font-semibold text-white">
              {children}
            </strong>
          ),
          em: ({ children }) => (
            <em className="italic text-[#cbd5e1]">
              {children}
            </em>
          ),
          ul: ({ children }) => (
            <ul className="space-y-1.5 my-2 pl-4 rtl:pr-4 rtl:pl-0 list-disc marker:text-[#ff5c47]/80">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="space-y-1.5 my-2 pl-4 rtl:pr-4 rtl:pl-0 list-decimal marker:text-[#ff5c47]/80 marker:font-mono">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="text-xs text-[#d1d5db] leading-relaxed">
              {children}
            </li>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2.5 p-2.5 px-3.5 bg-[#1f2126]/60 border-l-2 rtl:border-l-0 rtl:border-r-2 border-[#ff5c47] rounded-r-lg rtl:rounded-r-none rtl:rounded-l-lg text-xs text-[#cbd5e1] italic">
              {children}
            </blockquote>
          ),
          code: ({ className, children, ...props }) => {
            const isBlock = Boolean(className) || String(children).includes("\n");
            if (isBlock) {
              return (
                <div className="my-2.5 rounded-xl bg-[#0e0f11] border border-[#232529] overflow-hidden">
                  <pre className="p-3 text-[11px] font-mono text-[#f0f2f5] overflow-x-auto leading-relaxed">
                    <code>{children}</code>
                  </pre>
                </div>
              );
            }
            return (
              <code
                className="px-1.5 py-0.5 rounded-md bg-[#232529] font-mono text-[11px] text-[#ff8d7e] font-medium border border-[#2e3238]"
                {...props}
              >
                {children}
              </code>
            );
          },
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-xl border border-[#2e3238] bg-[#141517]/80 shadow-md">
              <table className="w-full text-left rtl:text-right border-collapse text-[11px]">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-[#1e2024] text-[#f0f2f5] font-semibold border-b border-[#2e3238]">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-[#232529]/60">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="hover:bg-white/[0.02] transition-colors">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="p-2.5 px-3 font-semibold text-[#f0f2f5] text-[11px] whitespace-nowrap">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="p-2.5 px-3 text-[#cbd5e1] text-[11px] leading-relaxed align-top">
              {children}
            </td>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#ff5c47] hover:underline underline-offset-2 font-medium"
            >
              {children}
            </a>
          ),
          hr: () => <hr className="my-3 border-[#232529]" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
});
