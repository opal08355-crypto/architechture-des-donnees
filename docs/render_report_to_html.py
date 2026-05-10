from __future__ import annotations

import html
import re
import sys
from pathlib import Path


PAGE_CSS = """
@page {
  size: A4;
  margin: 18mm 16mm 18mm 16mm;
}

:root {
  --ink: #1f2937;
  --muted: #4b5563;
  --brand: #0f766e;
  --line: #d1d5db;
  --panel: #f8fafc;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  color: var(--ink);
  font-family: "Segoe UI", Arial, sans-serif;
  font-size: 11pt;
  line-height: 1.6;
  background: white;
}

main {
  max-width: 190mm;
  margin: 0 auto;
}

h1, h2, h3, h4, h5, h6 {
  color: #0b3b36;
  margin: 0 0 10px;
  line-height: 1.25;
  break-after: avoid-page;
}

h1 {
  margin-top: 0;
  text-align: center;
  font-size: 24pt;
  color: var(--brand);
}

h2 {
  font-size: 16pt;
  border-bottom: 2px solid var(--brand);
  padding-bottom: 4px;
  margin-top: 24px;
}

h3 {
  font-size: 13pt;
  margin-top: 18px;
}

p {
  margin: 0 0 10px;
  text-align: justify;
}

ul, ol {
  margin: 0 0 12px 20px;
  padding: 0;
}

li {
  margin: 0 0 4px;
}

pre {
  margin: 0 0 12px;
  padding: 12px;
  overflow: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--panel);
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 9.5pt;
  white-space: pre-wrap;
}

code {
  padding: 1px 4px;
  border-radius: 4px;
  background: #eef2f7;
  font-family: "Cascadia Code", Consolas, monospace;
  font-size: 0.96em;
}

pre code {
  padding: 0;
  background: transparent;
}

a {
  color: #0b5cad;
  text-decoration: none;
}

hr {
  border: none;
  border-top: 1px solid var(--line);
  margin: 18px 0;
}

blockquote {
  margin: 0 0 12px;
  padding: 0 0 0 14px;
  border-left: 4px solid var(--line);
  color: var(--muted);
}

.cover-meta {
  margin: 0 0 18px;
  padding: 14px 18px;
  border: 1px solid var(--line);
  border-radius: 10px;
  background: #f7fbfb;
}

.cover-meta ul {
  margin-bottom: 0;
}

.cover-subtitle {
  text-align: center;
  font-size: 16pt;
  font-weight: 700;
  color: #0b3b36;
  margin: 4px 0 16px;
}

.date-line {
  text-align: center;
  color: var(--muted);
  margin-bottom: 22px;
}
"""


def apply_inline_markup(text: str) -> str:
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


def close_list(parts: list[str], current_list: list[str] | None, list_type: str | None) -> tuple[list[str] | None, str | None]:
    if current_list and list_type:
        parts.append(f"<{list_type}>")
        parts.extend(current_list)
        parts.append(f"</{list_type}>")
    return None, None


def flush_paragraph(parts: list[str], paragraph_lines: list[str]) -> None:
    if not paragraph_lines:
        return
    content = " ".join(line.strip() for line in paragraph_lines if line.strip())
    if content:
        css_class = ""
        if content.startswith("Etat du depot analyse le "):
            css_class = ' class="date-line"'
        parts.append(f"<p{css_class}>{apply_inline_markup(content)}</p>")
    paragraph_lines.clear()


def markdown_to_html(markdown_text: str) -> str:
    parts: list[str] = []
    paragraph_lines: list[str] = []
    current_list: list[str] | None = None
    list_type: str | None = None
    in_code_block = False
    code_lines: list[str] = []

    for raw_line in markdown_text.splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.strip()

        if stripped.startswith("```"):
            flush_paragraph(parts, paragraph_lines)
            current_list, list_type = close_list(parts, current_list, list_type)
            if in_code_block:
                code_html = html.escape("\n".join(code_lines))
                parts.append(f"<pre><code>{code_html}</code></pre>")
                code_lines.clear()
                in_code_block = False
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        heading_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        bullet_match = re.match(r"^-\s+(.*)$", stripped)
        ordered_match = re.match(r"^\d+\.\s+(.*)$", stripped)
        blockquote_match = re.match(r"^>\s+(.*)$", stripped)

        if not stripped:
            flush_paragraph(parts, paragraph_lines)
            current_list, list_type = close_list(parts, current_list, list_type)
            continue

        if heading_match:
            flush_paragraph(parts, paragraph_lines)
            current_list, list_type = close_list(parts, current_list, list_type)
            level = len(heading_match.group(1))
            title = apply_inline_markup(heading_match.group(2).strip())
            if level == 2 and heading_match.group(2).strip() == "Medical Big Data Platform":
                parts.append(f'<div class="cover-subtitle">{title}</div>')
            else:
                parts.append(f"<h{level}>{title}</h{level}>")
            continue

        if bullet_match:
            flush_paragraph(parts, paragraph_lines)
            if list_type != "ul":
                current_list, list_type = close_list(parts, current_list, list_type)
                current_list = []
                list_type = "ul"
            item = apply_inline_markup(bullet_match.group(1).strip())
            current_list.append(f"<li>{item}</li>")
            continue

        if ordered_match:
            flush_paragraph(parts, paragraph_lines)
            if list_type != "ol":
                current_list, list_type = close_list(parts, current_list, list_type)
                current_list = []
                list_type = "ol"
            item = apply_inline_markup(ordered_match.group(1).strip())
            current_list.append(f"<li>{item}</li>")
            continue

        if blockquote_match:
            flush_paragraph(parts, paragraph_lines)
            current_list, list_type = close_list(parts, current_list, list_type)
            quote = apply_inline_markup(blockquote_match.group(1).strip())
            parts.append(f"<blockquote>{quote}</blockquote>")
            continue

        if stripped == "---":
            flush_paragraph(parts, paragraph_lines)
            current_list, list_type = close_list(parts, current_list, list_type)
            parts.append("<hr>")
            continue

        paragraph_lines.append(stripped)

    flush_paragraph(parts, paragraph_lines)
    current_list, list_type = close_list(parts, current_list, list_type)

    html_body = "\n".join(parts)
    html_body = html_body.replace(
        "<h3>Realise Par</h3>\n<ul>",
        '<div class="cover-meta"><h3>Realise Par</h3>\n<ul>',
        1,
    ).replace("</ul>", "</ul></div>", 1)

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rapport Complet Du Projet</title>
  <style>{PAGE_CSS}</style>
</head>
<body>
  <main>
    {html_body}
  </main>
</body>
</html>
"""


def main() -> int:
    input_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/RAPPORT_COMPLET_PROJET.md")
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else input_path.with_suffix(".html")

    markdown_text = input_path.read_text(encoding="utf-8")
    html_text = markdown_to_html(markdown_text)
    output_path.write_text(html_text, encoding="utf-8")
    print(f"[OK] HTML generated: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
