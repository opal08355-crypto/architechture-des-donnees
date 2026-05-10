from __future__ import annotations

import re
from pathlib import Path

from render_report_to_html import markdown_to_html


INPUT_MD = Path("docs/RAPPORT_COMPLET_PROJET.md")
OUTPUT_HTML = Path("docs/RAPPORT_COMPLET_PROJET_ACADEMIQUE.html")


ACADEMIC_CSS = """
@page {
  size: A4;
  margin: 16mm 14mm 16mm 14mm;
}

:root {
  --ink: #162029;
  --muted: #4c5c6c;
  --brand: #0b5cad;
  --brand-deep: #083a6a;
  --soft: #eef5fb;
  --line: #d4dde7;
  --gold: #c6942c;
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

.cover-page {
  min-height: 265mm;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  position: relative;
  padding: 10mm 6mm 8mm;
}

.cover-page::before {
  content: "";
  position: absolute;
  inset: 0;
  border: 2px solid var(--brand);
  pointer-events: none;
}

.cover-page::after {
  content: "";
  position: absolute;
  inset: 6mm;
  border: 1px solid rgba(11, 92, 173, 0.25);
  pointer-events: none;
}

.cover-top {
  text-align: center;
  padding-top: 8mm;
}

.school-badge {
  width: 78px;
  height: 78px;
  margin: 0 auto 14px;
  border-radius: 50%;
  border: 3px solid var(--brand);
  display: grid;
  place-items: center;
  color: var(--brand);
  font-weight: 800;
  letter-spacing: 0.08em;
  font-size: 1.15rem;
  background: radial-gradient(circle at top, #ffffff, #eaf3fb);
}

.school-name {
  margin: 0;
  color: var(--brand-deep);
  font-weight: 800;
  font-size: 1.25rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.school-sub {
  margin: 8px 0 0;
  color: var(--muted);
  font-size: 0.98rem;
}

.cover-middle {
  text-align: center;
  padding: 10mm 0 8mm;
}

.report-kind {
  display: inline-block;
  margin-bottom: 18px;
  padding: 10px 18px;
  border: 1px solid rgba(11, 92, 173, 0.28);
  background: var(--soft);
  color: var(--brand-deep);
  font-weight: 700;
  border-radius: 999px;
}

.report-title {
  margin: 0 auto 18px;
  max-width: 145mm;
  color: var(--brand-deep);
  font-size: 1.7rem;
  line-height: 1.25;
  font-weight: 800;
  text-transform: uppercase;
}

.report-subtitle {
  margin: 0 auto;
  max-width: 145mm;
  color: var(--muted);
  font-size: 1.02rem;
  line-height: 1.75;
}

.cover-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-top: 24px;
  text-align: left;
}

.cover-card {
  border: 1px solid var(--line);
  background: white;
  padding: 14px 16px;
  min-height: 90px;
}

.cover-card h3 {
  margin: 0 0 10px;
  color: var(--brand);
  font-size: 0.95rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.cover-card p,
.cover-card li {
  margin: 0;
  font-size: 0.98rem;
}

.cover-card ul {
  margin: 0;
  padding-left: 20px;
}

.cover-meta {
  display: grid;
  gap: 8px;
  margin-top: 18px;
}

.meta-row {
  display: flex;
  gap: 8px;
  justify-content: center;
  flex-wrap: wrap;
  color: var(--ink);
}

.meta-label {
  color: var(--brand);
  font-weight: 700;
}

.cover-bottom {
  text-align: center;
  color: var(--muted);
  font-size: 0.97rem;
  padding-bottom: 6mm;
}

.page-break {
  break-after: page;
  page-break-after: always;
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
  background: #f7fafc;
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
"""


def strip_intro(md: str) -> str:
    lines = md.splitlines()
    out: list[str] = []
    skip_prefixes = {
        "# Rapport Complet Du Projet",
        "## Medical Big Data Platform",
        "### Realise Par",
        "- Oussama Mennoun",
        "- Mohammed Mekkaoui",
        "- Rayane Ait Ali",
        "Etat du depot analyse le 10 mai 2026.",
    }
    for line in lines:
        if line.strip() in skip_prefixes:
            continue
        out.append(line)
    return "\n".join(out).lstrip()


def extract_main_body(full_html: str) -> str:
    match = re.search(r"<main>(.*)</main>", full_html, re.S)
    if not match:
        return full_html
    return match.group(1).strip()


def build_cover_html() -> str:
    return """
<section class="cover-page">
  <div class="cover-top">
    <div class="school-badge">EMSI</div>
    <p class="school-name">Ecole Marocaine des Sciences de l'Ingenieur</p>
    <p class="school-sub">Annee Universitaire : 2025 / 2026</p>
  </div>

  <div class="cover-middle">
    <div class="report-kind">Projet de Fin d'Annee (PFA)</div>
    <h1 class="report-title">Medical Big Data Platform</h1>
    <p class="report-subtitle">
      Plateforme Big Data medicale pour la collecte, le traitement, l'analyse et
      la valorisation conversationnelle des donnees de sante via un pipeline hybride
      ETL, RAG local, recherche web medicale et assistant intelligent.
    </p>

    <div class="cover-meta">
      <div class="meta-row"><span class="meta-label">Filiere :</span><span>Ingenierie de l'Intelligence Artificielle et de la Data (IADATA)</span></div>
      <div class="meta-row"><span class="meta-label">Module :</span><span>Architecture de Donnees</span></div>
    </div>

    <div class="cover-grid">
      <div class="cover-card">
        <h3>Realise Par</h3>
        <ul>
          <li>Oussama Mennoun</li>
          <li>Mohammed Mekkaoui</li>
          <li>Rayane Ait Ali</li>
        </ul>
      </div>

      <div class="cover-card">
        <h3>Encadre Par</h3>
        <p>A renseigner</p>
      </div>
    </div>
  </div>

  <div class="cover-bottom">
    Rapport academique inspire de la structure de couverture du fichier PDF d'exemple fourni.
  </div>
</section>
<div class="page-break"></div>
"""


def main() -> int:
    md_text = INPUT_MD.read_text(encoding="utf-8")
    body_md = strip_intro(md_text)
    body_html = extract_main_body(markdown_to_html(body_md))
    final_html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Rapport Academique - Medical Big Data Platform</title>
  <style>{ACADEMIC_CSS}</style>
</head>
<body>
  <main>
    {build_cover_html()}
    {body_html}
  </main>
</body>
</html>
"""
    OUTPUT_HTML.write_text(final_html, encoding="utf-8")
    print(f"[OK] Academic HTML generated: {OUTPUT_HTML}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
