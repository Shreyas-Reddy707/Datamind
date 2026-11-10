"use client";

import React from "react";

interface MarkdownMessageProps {
  content: string;
}

function renderInline(text: string): React.ReactNode[] {
  const tokens: React.ReactNode[] = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let keyIdx = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      tokens.push(text.slice(lastIndex, match.index));
    }
    const seg = match[0];
    if (seg.startsWith("**") && seg.endsWith("**")) {
      const inner = seg.slice(2, -2).replace(/`([^`]+)`/g, "$1");
      tokens.push(
        <strong key={`b-${keyIdx++}`} className="text-white font-semibold">
          {inner}
        </strong>
      );
    } else if (seg.startsWith("`") && seg.endsWith("`")) {
      tokens.push(
        <code
          key={`c-${keyIdx++}`}
          className="px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-mono text-[11px]"
        >
          {seg.slice(1, -1)}
        </code>
      );
    } else if (seg.startsWith("*") && seg.endsWith("*")) {
      tokens.push(
        <em key={`i-${keyIdx++}`} className="text-zinc-300 italic">
          {seg.slice(1, -1)}
        </em>
      );
    }
    lastIndex = pattern.lastIndex;
  }

  if (lastIndex < text.length) {
    tokens.push(text.slice(lastIndex));
  }
  return tokens;
}

export function MarkdownMessage({ content }: MarkdownMessageProps) {
  const lines = content.split("\n");
  const blocks: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const raw = lines[i];
    const trimmed = raw.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // Markdown Table block
    if (trimmed.startsWith("|") && i + 1 < lines.length && lines[i + 1].trim().startsWith("|")) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) {
        tableLines.push(lines[i].trim());
        i++;
      }
      if (tableLines.length >= 2) {
        const parseRow = (rowStr: string) =>
          rowStr
            .replace(/^\|/, "")
            .replace(/\|$/, "")
            .split("|")
            .map((cell) => cell.trim());

        const headers = parseRow(tableLines[0]);
        const isSep = /^[\s|:-]+$/.test(tableLines[1]);
        const bodyRows = (isSep ? tableLines.slice(2) : tableLines.slice(1)).map(parseRow);

        blocks.push(
          <div key={`tbl-${i}`} className="overflow-x-auto my-2 rounded-lg border border-zinc-800 bg-zinc-950/70">
            <table className="w-full text-left text-[11px] font-mono">
              <thead className="bg-zinc-900/90 border-b border-zinc-800 text-zinc-300">
                <tr>
                  {headers.map((h, hi) => (
                    <th key={hi} className="py-1.5 px-2.5 font-semibold whitespace-nowrap">
                      {renderInline(h)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60">
                {bodyRows.map((row, ri) => (
                  <tr key={ri} className="hover:bg-zinc-900/40">
                    {row.map((cell, ci) => (
                      <td key={ci} className="py-1.5 px-2.5 text-zinc-300">
                        {renderInline(cell)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
        continue;
      }
    }

    // Headings (#, ##, ###)
    const headingMatch = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const titleText = headingMatch[2];
      blocks.push(
        <h4
          key={`h-${i}`}
          className={`font-semibold text-emerald-400 tracking-wide ${
            level === 1 ? "text-sm mt-2 mb-1" : level === 2 ? "text-xs uppercase mt-2 mb-1" : "text-xs mt-1.5 mb-0.5"
          }`}
        >
          {renderInline(titleText)}
        </h4>
      );
      i++;
      continue;
    }

    // Bullet / Numbered list
    if (/^([-*•]|\d+\.)\s+/.test(trimmed)) {
      const listItems: { marker: string; text: string }[] = [];
      while (i < lines.length) {
        const l = lines[i].trim();
        const m = l.match(/^([-*•]|\d+\.)\s+(.+)$/);
        if (!m) break;
        listItems.push({ marker: m[1], text: m[2] });
        i++;
      }
      blocks.push(
        <ul key={`ul-${i}`} className="space-y-1.5 my-1">
          {listItems.map((item, li) => (
            <li key={li} className="flex items-start gap-2 text-zinc-200 leading-relaxed">
              <span className="text-emerald-400 font-bold shrink-0 mt-0.5 text-[10px]">
                {item.marker === "-" || item.marker === "*" ? "•" : item.marker}
              </span>
              <span className="flex-1">{renderInline(item.text)}</span>
            </li>
          ))}
        </ul>
      );
      continue;
    }

    // Paragraph
    blocks.push(
      <p key={`p-${i}`} className="text-zinc-200 leading-relaxed">
        {renderInline(trimmed)}
      </p>
    );
    i++;
  }

  return <div className="space-y-1.5 text-xs font-mono break-words">{blocks}</div>;
}

