const SAFE_LINK_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeAttribute(value) {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

function sanitizeUrl(rawUrl) {
  const urlText = String(rawUrl || "").trim();
  if (!urlText) {
    return "";
  }

  try {
    const parsedUrl = new URL(urlText, window.location.origin);
    if (!SAFE_LINK_PROTOCOLS.has(parsedUrl.protocol)) {
      return "";
    }
    return parsedUrl.href;
  } catch (error) {
    return "";
  }
}

function renderInlineMarkdown(text) {
  const inlineCodeParts = [];
  let html = escapeHtml(text).replace(/`([^`]+)`/g, (match, code) => {
    const token = `::INLINECODETOKEN${inlineCodeParts.length}::`;
    inlineCodeParts.push(`<code>${code}</code>`);
    return token;
  });

  html = html
    .replace(/\*\*([^*\n][\s\S]*?)\*\*/g, "<strong>$1</strong>")
    .replace(/__([^_\n][\s\S]*?)__/g, "<strong>$1</strong>")
    .replace(/\*([^*\n]+)\*/g, "<em>$1</em>")
    .replace(/_([^_\n]+)_/g, "<em>$1</em>")
    .replace(/\[([^\]\n]+)\]\(((?:[^\s()]|\([^)]*\))+)\)/g, (match, label, url) => {
      const safeUrl = sanitizeUrl(url);
      if (!safeUrl) {
        return label;
      }
      return `<a href="${escapeAttribute(safeUrl)}" target="_blank" rel="noreferrer noopener">${label}</a>`;
    });

  html = html.replace(/::INLINECODETOKEN(\d+)::/g, (match, indexText) => {
    const index = Number(indexText);
    return inlineCodeParts[index] || "";
  });

  return html;
}

function splitTableRow(line) {
  return line
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function isTableSeparator(line) {
  const cells = splitTableRow(line);
  return cells.length > 1 && cells.every((cell) => /^:?-{3,}:?$/.test(cell));
}

function renderTable(lines, startIndex) {
  if (startIndex + 1 >= lines.length || !isTableSeparator(lines[startIndex + 1])) {
    return null;
  }

  const headerCells = splitTableRow(lines[startIndex]);
  const bodyRows = [];
  let cursor = startIndex + 2;
  while (cursor < lines.length && lines[cursor].includes("|") && lines[cursor].trim()) {
    bodyRows.push(splitTableRow(lines[cursor]));
    cursor += 1;
  }

  const headerHtml = headerCells
    .map((cell) => `<th>${renderInlineMarkdown(cell)}</th>`)
    .join("");
  const bodyHtml = bodyRows
    .map((row) => {
      const cellsHtml = row.map((cell) => `<td>${renderInlineMarkdown(cell)}</td>`).join("");
      return `<tr>${cellsHtml}</tr>`;
    })
    .join("");

  return {
    html: `<div class="markdown-table-wrap"><table><thead><tr>${headerHtml}</tr></thead><tbody>${bodyHtml}</tbody></table></div>`,
    nextIndex: cursor,
  };
}

function renderList(lines, startIndex, ordered) {
  const tagName = ordered ? "ol" : "ul";
  const pattern = ordered ? /^\s*\d+[.)]\s+(.+)$/ : /^\s*[-*+]\s+(.+)$/;
  const items = [];
  let cursor = startIndex;

  while (cursor < lines.length) {
    const match = lines[cursor].match(pattern);
    if (!match) {
      break;
    }
    items.push(`<li>${renderInlineMarkdown(match[1])}</li>`);
    cursor += 1;
  }

  return {
    html: `<${tagName}>${items.join("")}</${tagName}>`,
    nextIndex: cursor,
  };
}

function renderParagraph(lines, startIndex) {
  const paragraphLines = [];
  let cursor = startIndex;

  while (cursor < lines.length) {
    const line = lines[cursor];
    const trimmedLine = line.trim();
    if (
      !trimmedLine ||
      /^#{1,6}\s+/.test(trimmedLine) ||
      /^>\s?/.test(trimmedLine) ||
      /^\s*[-*+]\s+/.test(line) ||
      /^\s*\d+[.)]\s+/.test(line) ||
      /^```/.test(trimmedLine)
    ) {
      break;
    }

    if (line.includes("|") && cursor + 1 < lines.length && isTableSeparator(lines[cursor + 1])) {
      break;
    }

    paragraphLines.push(trimmedLine);
    cursor += 1;
  }

  if (!paragraphLines.length) {
    return {
      html: `<p>${renderInlineMarkdown(lines[startIndex].trim())}</p>`,
      nextIndex: startIndex + 1,
    };
  }

  return {
    html: `<p>${renderInlineMarkdown(paragraphLines.join("\n"))}</p>`,
    nextIndex: cursor,
  };
}

export function renderMarkdown(markdownText) {
  const normalizedText = String(markdownText || "").replace(/\r\n?/g, "\n");
  if (!normalizedText.trim()) {
    return "";
  }

  const lines = normalizedText.split("\n");
  const blocks = [];
  let cursor = 0;

  while (cursor < lines.length) {
    const line = lines[cursor];
    const trimmedLine = line.trim();

    if (!trimmedLine) {
      cursor += 1;
      continue;
    }

    const fenceMatch = trimmedLine.match(/^```\s*([^`]*)\s*$/);
    if (fenceMatch) {
      const codeLines = [];
      cursor += 1;
      while (cursor < lines.length && !lines[cursor].trim().startsWith("```")) {
        codeLines.push(lines[cursor]);
        cursor += 1;
      }
      if (cursor < lines.length) {
        cursor += 1;
      }
      const languageName = fenceMatch[1].trim();
      const language = languageName ? `<span>${escapeHtml(languageName)}</span>` : "";
      blocks.push(`<pre><div class="markdown-code-label">${language}</div><code>${escapeHtml(codeLines.join("\n"))}</code></pre>`);
      continue;
    }

    const headingMatch = trimmedLine.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const level = Math.min(headingMatch[1].length, 4);
      blocks.push(`<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`);
      cursor += 1;
      continue;
    }

    if (/^>\s?/.test(trimmedLine)) {
      const quoteLines = [];
      while (cursor < lines.length && /^>\s?/.test(lines[cursor].trim())) {
        quoteLines.push(lines[cursor].trim().replace(/^>\s?/, ""));
        cursor += 1;
      }
      blocks.push(`<blockquote>${renderMarkdown(quoteLines.join("\n"))}</blockquote>`);
      continue;
    }

    if (line.includes("|")) {
      const table = renderTable(lines, cursor);
      if (table) {
        blocks.push(table.html);
        cursor = table.nextIndex;
        continue;
      }
    }

    if (/^\s*[-*+]\s+/.test(line)) {
      const list = renderList(lines, cursor, false);
      blocks.push(list.html);
      cursor = list.nextIndex;
      continue;
    }

    if (/^\s*\d+[.)]\s+/.test(line)) {
      const list = renderList(lines, cursor, true);
      blocks.push(list.html);
      cursor = list.nextIndex;
      continue;
    }

    const paragraph = renderParagraph(lines, cursor);
    blocks.push(paragraph.html);
    cursor = paragraph.nextIndex > cursor ? paragraph.nextIndex : cursor + 1;
  }

  return blocks.join("");
}
