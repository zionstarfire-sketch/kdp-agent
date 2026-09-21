# 📖 Autonomous Amazon KDP Travel Guide Agent

An autonomous multi-agent publishing system that researches, writes, illustrates, formats, and packages print-ready, professional Amazon KDP travel field guides.

---

## 🌟 Key Features

* **Phase A: Niche & Series Architect**: Discovers and validates underserved destination sub-niches, reader constraints, brand series formulas, and high-intent backend keywords.
* **Phase B: Grounded Deep Research**: Gathers boots-on-the-ground facts, precise transit lines, ticket prices, opening hours, local cultural nuances, and logistics using live search (Tavily).
* **Phase C: Opinionated Long-Form Writing**: Authors comprehensive, high-word-count chapters in a lived-experience first-person field guide persona. Generates structured cost tables, time estimates, step-free access notes, and practical field tips.
* **Phase D: Photographic Evidence & Visual Suite**:
  * **Public Photo Discovery**: Queries Wikimedia Commons for authentic, publicly available field photographs (ticket machines, entrance signs, transit platforms, food portions, street layouts) with full provenance attribution (photographer, date, license).
  * **Documentary AI Fallback**: Generates hyper-realistic field visuals via Google Antigravity CLI (Priority 1) with honest simulation attribution.
  * **Book Covers**: Editorial medium-format aesthetic (Hasselblad H6D-100c / National Geographic Traveler style) with strict negative constraints against CGI and typography slop.
* **Phase E: Multi-Format Publication Engine**:
  * 📕 **Print-Ready PDF**: KDP standard 7" × 10" trim size, two-pass headless Edge rendering, exact dot-leader Table of Contents page numbering, and interactive PDF bookmark outlines (PyMuPDF).
  * 📝 **Editable Word Document (`.docx`)**: 7" × 10" editable manuscript with embedded images, styled headings, and custom tables.
  * 🌐 **Self-Contained Kindle HTML**: Standalone HTML with base64 embedded images.
  * 📄 **Clean Markdown**: Complete master manuscript.
  * 🚀 **KDP Launch & Metadata Package**: 7 backend search keyword phrases, category recommendations, 5-part HTML sales copy, and social media promotion concepts.
* **Clean Session Management**: Automatically organizes each project into dedicated session directories (`output/{shortname}/`) and cleans up intermediate drafts and raw image directories upon final compilation.

---

## 🏗️ Architecture

```
[User Request / Topic Prompt]
            │
            ▼
┌─────────────────────────┐
│ 1. Blueprint & Outliner │ ── (DeepSeek Flash) Plans chapter structure & photo queries
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 2. Deep Research Agent  │ ── (Tavily API) Gathers real-world transit, costs & hours
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 3. Chapter Writer Agent │ ── (DeepSeek Pro) Writes dense, practical chapters
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 4. Visual Coordinator   │ ── Wikimedia Commons Search ➔ Antigravity CLI Fallback
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 5. Formatting Pipeline  │ ── Generates PDF (7x10), DOCX (7x10), HTML & Markdown
└───────────┬─────────────┘
            ▼
┌─────────────────────────┐
│ 6. Launch & Cleanup     │ ── KDP launch package + intermediate artifact cleanup
└─────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Prerequisites
* Python 3.12+ (managed via `uv` or `venv`)
* Microsoft Edge (for headless print-to-pdf generation on Windows)
* Google Antigravity CLI (for local AI image generation)

### 2. Installation

Clone the repository and install dependencies with `uv`:

```bash
# Clone the repository
git clone <your-repo-url>
cd ebook_agent

# Create virtual environment and install dependencies
uv venv
uv pip install -e .
```

### 3. Environment Setup

Copy `.env.example` to `.env` and fill in your API credentials:

```bash
cp .env.example .env
```

| Key | Description | Required? |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek API key (uses OpenAI-compatible endpoint) | **Yes** |
| `TAVILY_API_KEY` | Tavily Search API key for deep field research | **Yes** |
| `HF_TOKEN` | Hugging Face token for SD3 image fallback | Optional |
| `GROQ_API_KEY` | Groq API key for fast inference | Optional |

### 4. Launch the Web Interface

Launch the interactive Gradio dashboard:

```bash
uv run python main.py
```

Open your browser at `http://localhost:7860` to:
1. **Phase A Tab**: Brainstorm niches, traveler profiles, and series angles.
2. **Phase B–E Tab**: Provide your prompt and generate full publications.

---

## 📁 Repository Structure

```
ebook_agent/
├── main.py                  # Orchestrator agent & Gradio interface
├── pyproject.toml           # Project dependencies & package configuration
├── uv.lock                  # Pinned dependency lockfile
├── .env.example             # Template for API keys
├── .gitignore               # Comprehensive Git exclusion rules
├── README.md                # Project documentation
├── PDF_BENCHMARK_COMPARISON_AND_PLAN.md # Design & layout specification
├── tools/
│   ├── __init__.py          # Tool exports
│   ├── web_search.py        # Tavily search tool
│   ├── image_generator.py   # Wikimedia Commons photo finder & AI prompts
│   ├── guide_formatter.py   # PDF (two-pass PyMuPDF/Edge), DOCX & HTML compiler
│   └── docs_output.py       # Manuscript document saver
└── output/                  # (Ignored) Session folders for generated publications
```

---

## 📄 Output Deliverables

Each generated guide produces the following deliverables inside `output/{guide_slug}/`:
1. `[Title].pdf` — 7" × 10" print-ready interior with exact TOC page numbers.
2. `[Title].docx` — 7" × 10" editable Microsoft Word manuscript with embedded images.
3. `[Title].html` — Kindle Direct Publishing standalone HTML with base64 embedded graphics.
4. `[Title].md` — Clean master Markdown text.
5. `[Title]_launch_package.md` — 7 KDP backend search boxes, categories, and HTML sales description.

---

## ⚖️ License & Attribution

This tool strictly adheres to honest photographic attribution:
* Public photographs sourced from Wikimedia Commons preserve true author, date, and license metadata.
* Visual reconstructions generated by AI are clearly designated as simulations.
