import sys
# Force UTF-8 encoding on standard streams to prevent 'charmap' codec errors on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from typing import override
import os
import shutil
import re
import json
import asyncio
import random
from datetime import datetime
from dotenv import load_dotenv
import gradio as gr
from fastapi import FastAPI, Header, HTTPException
import uvicorn

from agents import (
    Agent,
    Runner,
    AsyncOpenAI,
    OpenAIChatCompletionsModel,
    set_tracing_disabled,
)

# Import our custom tools from the tools package
from tools import (
    search_web,
    format_kdp_guide,
    format_kdp_docx,
    save_document,
    upload_to_google_docs,
)

# Import the 44-page publishing specifications & prompt architectures
from prompts_template import (
    PHASE_A_NICHE_ARCHITECT_SYSTEM_PROMPT,
    BOOK_CONTEXT_SYSTEM_PROMPT,
    TABLE_OF_CONTENTS_SYSTEM_PROMPT,
    RESEARCH_DOSSIER_SYSTEM_PROMPT,
    BLUEPRINT_GENERATOR_SYSTEM_PROMPT,
    CHAPTER_WRITER_SYSTEM_PROMPT,
)

# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv(override=True)

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY is not set in .env")

# DeepSeek client initialization (DeepSeek uses an OpenAI-compatible API)
deepseek_client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
    timeout=300.0,
)

# 1. Fast, Direct Model (DeepSeek Chat) for planning, research synthesis, formatting, etc.
DEEPSEEK_FLASH_MODEL = OpenAIChatCompletionsModel(
    model="deepseek-chat",
    openai_client=deepseek_client,
)

# 2. High-Capacity Direct Model (DeepSeek Chat) for writing authoritative book chapters
DEEPSEEK_PRO_MODEL = OpenAIChatCompletionsModel(
    model="deepseek-chat",
    openai_client=deepseek_client,
)

# Disable standard OpenAI tracing
set_tracing_disabled(True)

# ============================================================
# MULTI-AGENT SPECIFICATIONS
# ============================================================

# 1. EBOOK PLANNER AGENT (DeepSeek Flash) - 12-Chapter TOC Architect
research_agent = Agent(
    name="KDP Ebook Planner Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions=TABLE_OF_CONTENTS_SYSTEM_PROMPT,
)

# 2. WEB RESEARCH AGENT (DeepSeek Flash) - 23-Point Author's Research Dossier Engine
web_research_agent = Agent(
    name="Web Research Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions=RESEARCH_DOSSIER_SYSTEM_PROMPT,
    tools=[search_web],
)

# 3. EBOOK WRITER AGENT (DeepSeek Pro) - 5-Part Human Traveler Persona
writer_agent = Agent(
    name="Ebook Writer Agent",
    model=DEEPSEEK_PRO_MODEL,
    instructions=CHAPTER_WRITER_SYSTEM_PROMPT,
)

# 4. NICHE ARCHITECT AGENT (DeepSeek Flash) - PHASE A: STRATEGY & MASTER PROMPT COMPILER
niche_architect_agent = Agent(
    name="Niche Architect Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions=PHASE_A_NICHE_ARCHITECT_SYSTEM_PROMPT,
)

async def run_niche_architect(destinations: str, traveler_profile: str, trip_constraints: str, interest_verticals: str) -> tuple[str, str]:
    prompt = f"""
We are running Phase A of the KDP Travel Guide System.
Input details:
- Destination(s): {destinations}
- Traveler Profile/Identity/Constraints: {traveler_profile}
- Trip Constraints: {trip_constraints}
- Interest Verticals: {interest_verticals}

Please execute Phase A:
1. Conduct the market opportunity analysis, select the winning flagship title formula, and curate the full 12-chapter destination-adaptive outline (plus independent Introduction & Conclusion).
2. Generate the comprehensive MASTER PROMPT for Phase B inside ```master_prompt ... ``` as specified in your instructions.
"""
    result = await Runner.run(niche_architect_agent, prompt, max_turns=30)
    output_text = result.final_output
    
    master_prompt = ""
    strategic_report = output_text
    
    if "```master_prompt" in output_text:
        parts = output_text.split("```master_prompt", 1)
        strategic_report = parts[0].strip()
        after_mp = parts[1]
        last_fence = after_mp.rfind("```")
        if last_fence != -1:
            master_prompt = after_mp[:last_fence].strip()
            after_closing = after_mp[last_fence+3:].strip()
            if after_closing:
                strategic_report += f"\n\n{after_closing}"
        else:
            master_prompt = after_mp.strip()
    elif "PART 2: MASTER PROMPT FOR PHASE B" in output_text:
        parts = output_text.split("PART 2: MASTER PROMPT FOR PHASE B", 1)
        strategic_report = parts[0].strip()
        part2_text = parts[1]
        first_fence = part2_text.find("```")
        if first_fence != -1:
            after_first = part2_text[first_fence+3:]
            newline_idx = after_first.find("\n")
            if newline_idx != -1:
                after_first = after_first[newline_idx+1:]
            last_fence = after_first.rfind("```")
            if last_fence != -1:
                master_prompt = after_first[:last_fence].strip()
            else:
                master_prompt = after_first.strip()
        else:
            master_prompt = part2_text.strip()
    else:
        master_prompt = output_text.strip()

    strategic_report += "\n\n> 📋 *The complete Master Prompt has been extracted into the dedicated copy box above. Click the copy icon in the top right of the box and paste it into Phase B-E.*"

    os.makedirs("output", exist_ok=True)
    with open("output/master_prompt.txt", "w", encoding="utf-8") as f:
        f.write(master_prompt)
    with open("output/niche_series_plan.md", "w", encoding="utf-8") as f:
        f.write(output_text)
        
    plan_path = os.path.abspath("output/niche_series_plan.md").replace("\\", "/")
    mp_path = os.path.abspath("output/master_prompt.txt").replace("\\", "/")
    
    report_footer = (
        f"\n\n---\n📂 **Saved Strategy Artifacts**:\n"
        f"* 📋 [master_prompt.txt](file:///{mp_path}) *(Ready to paste into Phase B)*\n"
        f"* 📊 [niche_series_plan.md](file:///{plan_path}) *(Full Market & Series Architecture)*"
    )
    
    return master_prompt, f"{strategic_report}{report_footer}"

# 5. BOOK CONTEXT AGENT (DeepSeek Flash) - PHASE A
book_context_agent = Agent(
    name="Book Context Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions=BOOK_CONTEXT_SYSTEM_PROMPT,
)

# 6. BLUEPRINT AGENT (DeepSeek Flash) - PHASE A
blueprint_agent = Agent(
    name="Blueprint Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions=BLUEPRINT_GENERATOR_SYSTEM_PROMPT,
)

def create_session_folder(title: str, user_request: str = "") -> tuple[str, str]:
    name_source = title if title else user_request
    clean_name = re.sub(r'[:\-\–—].*', '', name_source)
    if len(clean_name.strip().split()) < 2 and ":" in name_source:
        clean_name = name_source.replace(":", " ")
    
    clean_name = re.sub(r'[^\w\s]', '', clean_name).strip().lower()
    stop_words = {'the', 'a', 'an', 'and', 'for', 'of', 'in', 'to', 'with', 'on', 'at', 'by', 'from', 'is'}
    words = [w for w in clean_name.split() if w not in stop_words]
    if not words:
        words = clean_name.split()
    
    shortname = "_".join(words[:4])
    if not shortname:
        shortname = "kdp_guide"
        
    session_dir = os.path.join("output", shortname)
    os.makedirs(session_dir, exist_ok=True)
    os.makedirs(os.path.join(session_dir, "images"), exist_ok=True)
    return session_dir, shortname

async def generate_ebook(user_request: str):
    progress = []
    def update_progress(msg: str):
        progress.append(msg)
        return "\n\n".join(progress)

    summary_req = user_request.strip().split("\n")[0][:100]
    summary_req = re.sub(r"[^\x20-\x7E\u00A0-\uFFFF]", "", summary_req).strip() or "KDP Travel Guide"

    print(f"[Orchestrator] Starting KDP Guide generation for request: '{summary_req}...'")
    yield update_progress(f"🎬 **Starting KDP Guide generation** for: *\"{summary_req}\"*")
    
    outline = None

    curated_match = re.search(r"```json\s*(.*?)\s*```", user_request, re.DOTALL)
    if curated_match:
        try:
            cand_outline = json.loads(curated_match.group(1))
            if isinstance(cand_outline, dict) and "chapters" in cand_outline and len(cand_outline.get("chapters", [])) >= 5:
                outline = cand_outline
                c_title = outline.get("title", "Curated Guide")
                num_ch = len(outline.get("chapters", []))
                print(f"[Orchestrator] Step 1: Pre-curated outline detected in Master Prompt! Adopting '{c_title[:50]}...' with {num_ch} chapters.")
                yield update_progress(
                    f"🎯 **Step 1: Adopted pre-curated 12-chapter outline directly from Phase A Master Prompt**:\n"
                    f"* **Title**: {c_title}\n"
                    f"* **Subtitle**: {outline.get('subtitle', '')}\n"
                    f"* **Chapters**: {num_ch} curated chapters + Introduction & Conclusion."
                )
        except Exception as e:
            print(f"[Orchestrator] Note on parsing embedded JSON: {e}")

    if not outline:
        print("[Orchestrator] Step 1: Creating destination-adaptive chapter outline (DeepSeek Flash)...")
        yield update_progress("📝 **Step 1: Creating destination-adaptive chapter outline** (12 Chapters + Intro & Conclusion) using `deepseek-v4-flash`...")
        
        outline_prompt = f"""
Create an authoritative, destination-adaptive Amazon KDP Travel Guide Table of Contents and Outline for:
Destination / Topic: {user_request}

Follow the TABLE_OF_CONTENTS_SYSTEM_PROMPT specifications:
1. Adapt the structure naturally to the destination type (city, country, road trip, island, national park, cruise, or regional).
2. Include 12 well-organized chapters, with 3–6 concrete subtopics each.
3. The Introduction and Conclusion MUST stand alone independently from the 12 chapters.
4. Keep the full guide realistic for a print book not exceeding 150 pages (~25,000 to 35,000 words).
5. Provide targeted search queries and editorial documentary image prompts for every section.
6. If the user request already specifies chapter titles or themes, preserve and expand on them!
7. Output ONLY valid JSON wrapped in ```json ... ``` code fence according to the specified schema.
"""
        research_result = await Runner.run(
            research_agent,
            outline_prompt,
            max_turns=30
        )
        
        research_brief = research_result.final_output
        print("[Orchestrator] Outline generation complete. Parsing JSON...")

        match = re.search(r"```json\s*(.*?)\s*```", research_brief, re.DOTALL)
        json_str = match.group(1) if match else research_brief.strip()

        try:
            outline = json.loads(json_str)
        except Exception as e:
            print(f"[Orchestrator] JSON parsing failed: {e}. Falling back to 12-chapter default outline.")
            clean_short = re.sub(r"[^\w\s]", "", user_request.strip().split("\n")[0][:60]).strip() or "Travel Guide"
            outline = {
                "title": f"The Ultimate Field Guide to {clean_short}",
                "subtitle": "A Practical, Destination-Adaptive Handbook",
                "author": "KDP Travel Field Collective",
                "destination_type": "regional",
                "cover_image_prompt": f"Editorial medium format documentary photograph of {clean_short}, dramatic natural lighting, Hasselblad style, authentic scene, no typography",
                "introduction": {
                    "title": "Introduction: Landscape & Planning",
                    "subtitle": "Orientation and How to Use This Field Guide",
                    "subtopics": ["How to Use This Guide", "Destination Landscape & Promise", "Core Logistics Overview", "Navigating Seasons and Etiquette"],
                    "search_queries": [f"{clean_short} travel planning advice 2026", f"{clean_short} seasonal visitor trends"],
                    "image_prompt": f"Scenic orientation view capturing the atmosphere of {clean_short}",
                    "image_caption": f"Orientation to {clean_short}"
                },
                "chapters": [
                    {
                        "chapter_number": i,
                        "title": f"Chapter {i}: Essential Area & Focus {i}",
                        "focus": f"Detailed practical exploration of section {i} for {clean_short}.",
                        "subtopics": [f"Highlight Area {i}.1", f"Practical Route {i}.2", f"Insider Rules {i}.3", f"Dining & Neighborhood Atmosphere {i}.4"],
                        "search_queries": [f"{clean_short} section {i} practical travel guide 2026"],
                        "image_prompt": f"Authentic street or landscape scene in {clean_short}",
                        "image_caption": f"Field study in {clean_short}"
                    } for i in range(1, 13)
                ],
                "conclusion": {
                    "title": "Conclusion: The Final Summit",
                    "subtitle": "Checklists, Transit Summary & Lasting Reflections",
                    "subtopics": ["Essential Pre-Trip Checklist", "Master Transit & Budget Summary", "Final Words of Advice"],
                    "search_queries": [],
                    "image_prompt": f"Quiet, contemplative sunset panoramic view of {clean_short}",
                    "image_caption": f"Final reflections on traveling {clean_short}"
                }
            }

    clean_short_title = re.sub(r"[^\w\s]", "", user_request.strip().split("\n")[0][:60]).strip() or "Travel Guide"
    title = outline.get("title", f"The Ultimate Guide to {clean_short_title}")
    subtitle = outline.get("subtitle", "A Practical KDP Field Guide")
    author = outline.get("author", "KDP Expert Writer")
    destination_type = outline.get("destination_type", "regional")
    clean_title = re.sub(r'[^\w\s-]', '', title).strip()
    clean_title = re.sub(r'[\s-]+', '_', clean_title)

    sections = []
    
    intro_data = outline.get("introduction")
    raw_chapters = outline.get("chapters", [])
    has_intro_in_chapters = False
    if raw_chapters and isinstance(raw_chapters[0], dict):
        if "intro" in raw_chapters[0].get("title", "").lower():
            has_intro_in_chapters = True

    if intro_data and isinstance(intro_data, dict) and not has_intro_in_chapters:
        intro_title = intro_data.get("title", "Introduction")
        if intro_data.get("subtitle"):
            intro_title = f"{intro_title}: {intro_data.get('subtitle')}"
        intro_focus = intro_data.get("focus") or intro_data.get("scope", f"Orientation, core travel logistics, landscape overview, and how to use this guide for {title}.")
        sections.append({
            "section_type": "introduction",
            "number": 0,
            "filename_key": "intro",
            "title": intro_title,
            "focus": intro_focus,
            "subtopics": intro_data.get("subtopics") or intro_data.get("subsections", ["How to Use This Guide", "Destination Landscape & Promise", "Core Logistics Overview", "Navigating Seasons and Etiquette"]),
            "search_queries": intro_data.get("search_queries", [f"{title} travel planning logistics 2026"]),
            "image_prompt": intro_data.get("image_prompt", f"Editorial documentary photograph introducing {title}, authentic atmospheric scene"),
            "image_caption": intro_data.get("image_caption", f"Orientation: Welcome to {title}")
        })

    has_concl_in_chapters = False
    if raw_chapters and isinstance(raw_chapters[-1], dict):
        last_title = raw_chapters[-1].get("title", "").lower()
        if "conclu" in last_title or "epilogue" in last_title:
            has_concl_in_chapters = True

    for i, ch in enumerate(raw_chapters, 1):
        ch_num = ch.get("number") or ch.get("chapter_number", i)
        ch_title = ch.get("title", f"Chapter {i}")
        ch_focus = ch.get("focus") or ch.get("scope", f"Comprehensive, tested field guide for {ch_title}.")
        subtopics = ch.get("subtopics") or ch.get("subsections", [])
        sections.append({
            "section_type": "chapter",
            "number": ch_num,
            "filename_key": f"{ch_num}",
            "title": ch_title,
            "focus": ch_focus,
            "subtopics": subtopics,
            "search_queries": ch.get("search_queries", []),
            "image_prompt": ch.get("image_prompt", f"Authentic documentary scene for {ch_title}"),
            "image_caption": ch.get("image_caption", f"Field perspective: {ch_title}")
        })

    concl_data = outline.get("conclusion")
    if concl_data and isinstance(concl_data, dict) and not has_concl_in_chapters:
        concl_title = concl_data.get("title", "Conclusion")
        if concl_data.get("subtitle"):
            concl_title = f"{concl_title}: {concl_data.get('subtitle')}"
        sections.append({
            "section_type": "conclusion",
            "number": len(sections) + 1,
            "filename_key": "conclusion",
            "title": concl_title,
            "focus": concl_data.get("focus", f"Master pre-trip checklist, transit and budget summary, and final traveler wisdom for {title}."),
            "subtopics": concl_data.get("subtopics") or concl_data.get("subsections", ["Essential Pre-Trip Checklist", "Master Transit & Budget Summary", "Final Words of Advice"]),
            "search_queries": concl_data.get("search_queries", []),
            "image_prompt": concl_data.get("image_prompt", f"Quiet, contemplative view concluding the journey in {title}"),
            "image_caption": concl_data.get("image_caption", f"Final reflections on traveling {title}")
        })

    session_dir, session_shortname = create_session_folder(title, user_request)
    session_images_dir = os.path.join(session_dir, "images")

    print(f"[Orchestrator] Outline parsed successfully: '{title}' by {author}")
    print(f"[Orchestrator] Destination Type: {destination_type}")
    print(f"[Orchestrator] Dedicated session folder: '{session_dir}'")
    print(f"[Orchestrator] Total sections to write: {len(sections)} (Core Chapters: {len(raw_chapters)})")
    yield update_progress(
        f"✅ **Destination-Adaptive Outline planned successfully**:\n"
        f"* **Title**: {title}\n"
        f"* **Subtitle**: {subtitle}\n"
        f"* **Author**: {author}\n"
        f"* **Destination Style**: `{destination_type}`\n"
        f"* **Sections**: {len(sections)} sections ({len(raw_chapters)} core chapters + Intro & Conclusion)\n"
        f"* **Session Subfolder**: `output/{session_shortname}/`"
    )

    print("[Orchestrator] Step 1B: Generating book context...")
    yield update_progress("🎯 **Step 1B: Generating book context** (Positioning, Target Personas, Negative Constraints)...")
    
    context_prompt = f"""
We are planning an authoritative Amazon KDP travel guide following the 44-page professional publishing specification.
Book Details:
- Title: {title}
- Subtitle: {subtitle}
- Author: {author}
- Destination Type: {destination_type}
- Total Sections: {len(sections)} ({len(raw_chapters)} core chapters + Introduction & Conclusion)
- User Idea / Concept: {user_request}

Please generate the complete BOOK CONTEXT according to the BOOK_CONTEXT_SYSTEM_PROMPT:
1. Destination Essence & Positioning Statement
2. Primary & Secondary Reader Personas (travel style, budget level, physical fitness, trip duration)
3. Voice, Tone & Perspective (opinionated, tested authority, first-person lived experience)
4. Editorial Guardrails & Negative Constraints (no tourist clichés, no AI-style transitions, no fluff)
5. Practical Metrics (exact currency rules, transit validation, tipping norms, seasonal warnings)
"""
    context_res = await Runner.run(book_context_agent, context_prompt, max_turns=30)
    book_context = context_res.final_output
    
    context_file = os.path.join(session_dir, "book_context.md")
    with open(context_file, "w", encoding="utf-8") as f:
        f.write(book_context)
        
    yield update_progress(f"📋 **Book Context Generated successfully**:\n\n{book_context}")

    written_chapters = []
    chapter_stats = []

    for idx, sec in enumerate(sections, 1):
        sec_type = sec["section_type"]
        sec_num = sec["number"]
        sec_title = sec["title"]
        sec_focus = sec["focus"]
        sec_subtopics = sec["subtopics"]
        search_queries = sec["search_queries"]
        image_prompt = sec["image_prompt"]
        image_caption = sec["image_caption"]
        key = sec["filename_key"]

        existing_chapter_path = os.path.join(session_dir, f"chapter_{key}.md")
        if os.path.exists(existing_chapter_path):
            try:
                with open(existing_chapter_path, "r", encoding="utf-8") as f:
                    existing_text = f.read()
                existing_word_count = len(existing_text.strip().split())
                if existing_word_count >= 500:
                    print(f"[Orchestrator] Chapter '{sec_title}' already exists ({existing_word_count} words). Resuming from checkpoint...")
                    yield update_progress(f"⏩ **Section {idx}/{len(sections)} ('{sec_title}') already completed** ({existing_word_count} words). Resuming...")
                    written_chapters.append((sec_title, existing_text))
                    chapter_stats.append((sec_title, existing_word_count))
                    continue
            except Exception as e:
                print(f"[Orchestrator Warning] Failed to read checkpoint for section {key}: {e}")

        print(f"\n[Orchestrator] Processing Section {idx}/{len(sections)}: '{sec_title}' ({sec_type})")
        yield update_progress(f"📖 **Writing Section {idx}/{len(sections)}**: *\"{sec_title}\"*")

        research_summary = "No search queries executed."
        if search_queries:
            print(f"[Orchestrator] Running web research for '{sec_title}'...")
            yield update_progress(f"  🔍 Compiling Author's Research Dossier via Tavily for *\"{sec_title}\"*...")
            queries_str = "\n".join(f"- {q}" for q in search_queries)
            research_prompt = f"""
We are writing an Amazon KDP field guide: "{title}: {subtitle}" by {author}.
Section Topic: "{sec_title}"
Section Focus: {sec_focus}
Subtopics to Investigate:
{', '.join(sec_subtopics) if sec_subtopics else 'Core travel intelligence'}

Run web searches for these queries:
{queries_str}

Investigate across the relevant 23 Research Pillars:
- Destination fundamentals, geography, seasons, opening hours, local rules
- Best places, experiences, and things to do with realistic timeframes
- Real-world practical difficulties (crowds, queues, reservations, stairs/hills, weather)
- Transportation, timetables, ticketing & validation rules (airports, trains, metro, buses, car rental)
- Where to stay (neighborhood atmospheres, transit access, pros/cons, costs)
- Food & drink (signature dishes, dining etiquette, reservations, tourist traps)
- Concrete dated costs (categorized into Budget, Mid-Range, Comfortable)
- Safety, health, common mistakes, and tourist traps vs. better alternatives
- Current & upcoming 2026 changes, fare adjustments, new regulations

CRITICAL: Clearly separate findings using the 5-Tier Evidence Labels:
• [OFFICIAL FACT]
• [DOCUMENTED TRAVELER EXPERIENCE]
• [RECURRING TRAVELER PATTERN]
• [EDITORIAL INTERPRETATION]
• [UNVERIFIED / NEEDS RECHECKING]

Conclude your dossier with:
A. What the Book Must Deliver | B. Highest-Value Findings | C. Important Warnings | D. Best Strategic Recommendations | E. Source Bibliography
"""
            research_res = await Runner.run(web_research_agent, research_prompt, max_turns=30)
            research_summary = research_res.final_output

        print(f"[Orchestrator] Generating blueprint for '{sec_title}'...")
        yield update_progress(f"  📋 Generating Section Blueprint (Angles, Target Word Counts, Content Rules)...")
        
        blueprint_prompt = f"""
Book Title: {title}
Book Subtitle: {subtitle}
Author: {author}
Destination Style: {destination_type}

BOOK CONTEXT:
{book_context}

Section Focus:
- Section Name: {sec_title}
- Section Type: {sec_type}
- Focus: {sec_focus}
- Subtopics: {", ".join(sec_subtopics) if sec_subtopics else "Comprehensive field guidance"}

Author's Research Dossier:
{research_summary}

Please generate the CHAPTER WRITING BLUEPRINT following BLUEPRINT_GENERATOR_SYSTEM_PROMPT:
1. Section Purpose & Core Reader Promise
2. Perspective, Angle & Tone
3. Structural Outline with Target Word Counts per subtopic
4. Specific Angles, Arguments & Contrarian Insights
5. Content Rules, Negative Constraints & Practical Warnings
6. 2–3 Concrete Photographic Evidence / Figure Recommendations
7. Gap Analysis (noting any details requiring [NEEDS INPUT] tags)
"""
        blueprint_res = await Runner.run(blueprint_agent, blueprint_prompt, max_turns=30)
        chapter_blueprint = blueprint_res.final_output
        
        blueprint_file = os.path.join(session_dir, f"section_{key}_blueprint.md")
        with open(blueprint_file, "w", encoding="utf-8") as f:
            f.write(chapter_blueprint)
            
        yield update_progress(f"  ✅ Section Blueprint generated and saved.")

        print(f"[Orchestrator] Writing section content using DeepSeek for '{sec_title}'...")
        yield update_progress(f"  ✍️ Drafting calibrated prose (1,200–1,500 words) using `deepseek-chat`...")
        
        context_sections = ""
        if written_chapters:
            context_sections = "\n".join(f"- Completed: {t}" for t, _ in written_chapters)

        writer_prompt = f"""
We are writing an Amazon KDP travel field guide following the 44-page publishing standard.
Book Details:
- Title: {title}
- Subtitle: {subtitle}
- Author: {author}

Completed Sections So Far:
{context_sections if context_sections else "None (This is the opening section)"}

Overall Book Context:
{book_context}

This Section's Writing Blueprint:
{chapter_blueprint}

Author's Research Dossier (Verified Field Intelligence):
{research_summary}

Section Specifications:
- Section Title: {sec_title}
- Section Type: {sec_type}
- Scope & Focus: {sec_focus}
- Subtopics to Cover: {", ".join(sec_subtopics) if sec_subtopics else "Core topic coverage"}

Writing Guidelines (Strictly Enforce):
1. Return ONLY the section markdown content.
   Start directly with the exact header format:
   `## CHAPTER {idx}: {sec_title.upper()}`
2. Follow the 5-Section Chapter Structure (NEVER USE THE WORD "PART"):
   Use EXACTLY `### SECTION X` (three hashtags) for sections, NEVER `## SECTION X`!
   - `### SECTION 1: STRATEGIC ORIENTATION & NARRATIVE HOOK`
   - `### SECTION 2: CORE FIELD GUIDE`
   - `### SECTION 3: LOGISTICS, TIMING & ROUTE REALITIES`
   - `### SECTION 4: HIGH-VALUE INSIDER RULES & MISTAKES TO AVOID`
   - `### SECTION 5: ACTION FRAMEWORK & NOTICES`
3. Exemplar Quick Notices & Specialized Callout Boxes (Include in Every Chapter)
4. Voice & Tone: 70% human-like traveler insider persona ("I", "we", "my") with tested, opinionated authority.
5. ZERO CLOSED VENUES & 100% 2026 FACTUAL ACCURACY
6. WORD COUNT CALIBRATION (Target 1,200–1,500 words)
7. Financial Accuracy: Cite exact actual prices paid with date
8. Figures & Maps: `Figure {sec_num}.Y — Title of Scene...`
9. Conclude with a centered milestone anchor.
"""
        chapter_content = ""
        for attempt in range(1, 3):
            try:
                writer_res = await Runner.run(writer_agent, writer_prompt, max_turns=30)
                cand_content = (writer_res.final_output or "").strip()
                if len(cand_content.split()) >= 500:
                    chapter_content = cand_content
                    break
            except Exception as e:
                print(f"[Orchestrator Warning] Runner turn failed on attempt {attempt}: {e}")
            
            print(f"[Orchestrator Warning] Attempt {attempt} returned low word count. Retrying with direct completion...")
            yield update_progress(f"  ⚠️ Draft attempt {attempt} returned low word count. Retrying with direct completion...")
            try:
                direct_res = await deepseek_client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": CHAPTER_WRITER_SYSTEM_PROMPT},
                        {"role": "user", "content": writer_prompt},
                    ],
                    max_tokens=4000,
                )
                direct_text = (direct_res.choices[0].message.content or "").strip()
                if len(direct_text.split()) >= 500:
                    chapter_content = direct_text
                    break
            except Exception as direct_err:
                print(f"[Orchestrator Warning] Direct retry error: {direct_err}")

        if not chapter_content or len(chapter_content.split()) < 300:
            chapter_content = f"## {sec_title}\n\nFigure {idx}.1 — Landmark Overview: Master perspective depicting the primary site access point, pedestrian flow, and spatial orientation.\n\n### Practical Exploration\n\n{sec_focus}\n\n"

        def clean_figure_line(match):
            prefix = match.group(1)
            f_num = match.group(2)
            f_title = match.group(3).strip()
            f_desc = match.group(4).strip() if match.group(4) else ""
            if f_desc:
                return f"{prefix} {f_num} — {f_title}: {f_desc}"
            return f"{prefix} {f_num} — {f_title}"

        chapter_content = re.sub(
            r"(Figure|Map|FIGURE|MAP)\s+([\dIVX\w\.]+)\s*—\s*([^|\n]+?)(?::\s*([^|\n]+?))?\s*\|\s*\[(?:PHOTO EVIDENCE|PHOTO RECOMMENDATION):[^\]]+?\](?:\s*\|\s*Credit:[^\n]+)?",
            clean_figure_line,
            chapter_content
        )
        chapter_content = re.sub(
            r"\[(?:PHOTO EVIDENCE|PHOTO RECOMMENDATION):\s*([^\]]+?)\]",
            r"Figure \1",
            chapter_content
        )

        save_document(f"chapter_{key}.md", chapter_content, output_dir=session_dir)
        written_chapters.append((sec_title, chapter_content))

        word_count = len(chapter_content.split())
        chapter_stats.append((sec_title, word_count))
        print(f"[Orchestrator] Section '{sec_title}' written successfully ({word_count} words).")
        yield update_progress(f"  ✅ Section {idx} finalized successfully ({word_count} words, visual specifications embedded).")

    print("\n[Orchestrator] Step 3: Compiling manuscript and applying Quebec City benchmark layout...")
    yield update_progress("📁 **Step 3: Formatting and compiling final publication manuscripts (Markdown, DOCX, HTML & PDF)...**")

    full_content = "\n\n".join(content for _, content in written_chapters)

    formatting_status = format_kdp_guide(
        title=title,
        subtitle=subtitle,
        content=full_content,
        author=author,
        output_dir=session_dir
    )
    print(f"[Orchestrator] Formatting status: {formatting_status}")

    yield update_progress("🚀 **Step 4: Generating KDP Backend Metadata & Launch Package** using `deepseek-v4-flash`...")
    print("[Orchestrator] Step 4: Generating launch package...")
    
    metadata_prompt = f"""
We have successfully written and formatted the Amazon KDP Travel Guide:
- Title: {title}
- Subtitle: {subtitle}
- Author: {author}
- Total Sections: {len(sections)} ({len(raw_chapters)} Chapters + Intro & Conclusion)

Here is the Table of Contents:
{"\n".join(f"- {c_title}" for c_title, _ in written_chapters)}

Please generate a comprehensive KDP Launch and Metadata Package (Phase E) containing:
1. **7 KDP Backend Keywords**
2. **KDP Category Recommendations**
3. **High-Converting Book Description (HTML)**
4. **Social Media Companion Posts**
5. **Lead Magnet**
6. **Launch Checklist**

Return ONLY the markdown text for the launch package.
"""
    metadata_res = await Runner.run(research_agent, metadata_prompt, max_turns=30)
    launch_package = metadata_res.final_output
    
    launch_filename = os.path.join(session_dir, f"{clean_title}_launch_package.md")
    with open(launch_filename, "w", encoding="utf-8") as f:
        f.write(launch_package)

    print("\n[Orchestrator] Step 5: Cleaning up raw intermediate files and images...")
    yield update_progress("🧹 **Step 5: Cleaning up raw intermediate files and images...**")

    docx_filename = os.path.join(session_dir, f"{clean_title}.docx")
    keep_files = {
        os.path.abspath(os.path.join(session_dir, f"{clean_title}.pdf")),
        os.path.abspath(docx_filename),
        os.path.abspath(os.path.join(session_dir, f"{clean_title}.html")),
        os.path.abspath(os.path.join(session_dir, f"{clean_title}.md")),
        os.path.abspath(launch_filename),
    }

    if os.path.exists(session_images_dir):
        shutil.rmtree(session_images_dir, ignore_errors=True)

    for root, dirs, files in os.walk(session_dir, topdown=False):
        for fname in files:
            full_fpath = os.path.abspath(os.path.join(root, fname))
            if full_fpath not in keep_files:
                try:
                    os.remove(full_fpath)
                except Exception:
                    pass
        for dname in dirs:
            d_full = os.path.join(root, dname)
            try:
                shutil.rmtree(d_full, ignore_errors=True)
            except Exception:
                pass

    print(f"[Orchestrator] Cleanup complete. Preserved final outputs in '{session_dir}'.")
    yield update_progress(f"✨ **Cleanup complete**: Removed raw intermediate files and images. Preserved final outputs in `output/{session_shortname}/`.")

    gdoc_link = ""
    if os.getenv("GOOGLE_DOCS_WEBHOOK_URL"):
        yield update_progress("☁️ **Syncing manuscript with Google Docs...**")
        gdoc_res = upload_to_google_docs(title=title, content_html=full_content, content_md=full_content)
        if gdoc_res.get("success") and gdoc_res.get("url"):
            gdoc_url = gdoc_res["url"]
            gdoc_link = f"\n* 📑 **[Open Live Google Doc (Editable in Google Drive)]({gdoc_url})**"

    abs_session = os.path.abspath(session_dir)
    md_url = f"/gradio_api/file={os.path.abspath(os.path.join(session_dir, f'{clean_title}.md')).replace('\\', '/')}"
    html_url = f"/gradio_api/file={os.path.abspath(os.path.join(session_dir, f'{clean_title}.html')).replace('\\', '/')}"
    pdf_url = f"/gradio_api/file={os.path.abspath(os.path.join(session_dir, f'{clean_title}.pdf')).replace('\\', '/')}"
    docx_url = f"/gradio_api/file={os.path.abspath(docx_filename).replace('\\', '/')}"
    launch_url = f"/gradio_api/file={os.path.abspath(launch_filename).replace('\\', '/')}"

    stats_list = "\n".join(f"* **{c_title}**: {w_count} words" for c_title, w_count in chapter_stats)
    total_words = sum(w_count for _, w_count in chapter_stats)

    report = f"""# 📖 Amazon KDP Guide Generation Complete!

## **{title}**
### *{subtitle}*
**Author**: {author}

---

### 📥 **Direct Downloads (Click to Download / Open in Browser)**
* 📕 **[Download Manuscript PDF (7"×10" Print-Ready)]({pdf_url})**
* 📝 **[Download Manuscript Word (.docx) (Editable Manuscript)]({docx_url})**
* 🌐 **[Download Kindle Format (.html) (Single-File Upload)]({html_url})**
* 📄 **[Download Markdown Source (.md)]({md_url})**
* 🚀 **[Download KDP Launch Package (.md)]({launch_url})**{gdoc_link}

---

### 📊 **Manuscript Statistics**
* **Total Sections**: {len(sections)} ({len(raw_chapters)} Core Chapters + Independent Intro & Conclusion)
* **Total Word Count**: {total_words} words
{stats_list}
"""
    yield report

async def chat(message, history):
    try:
        async for progress_msg in generate_ebook(message):
            yield progress_msg
    except Exception as e:
        yield f"Error generating ebook:\n\n{str(e)}"

async def resume_chat(message, history):
    os.makedirs("output", exist_ok=True)
    cp_file = os.path.join("output", "checkpoints.json")
    
    try:
        with open(cp_file, "r", encoding="utf-8") as f:
            checkpoints = json.load(f)
    except Exception:
        checkpoints = {}

    msg_clean = message.strip()
    msg_lower = msg_clean.lower()
    matched_key = None

    for key, data in checkpoints.items():
        if data.get("status") == "in_progress" and data.get("content"):
            if (
                msg_lower == key
                or msg_lower in key
                or key in msg_lower
                or msg_lower in ["continue", "resume"]
            ):
                matched_key = key
                break

    if matched_key:
        saved_text = checkpoints[matched_key]["content"]
        orig_prompt = checkpoints[matched_key]["prompt"]
        prompt_to_send = (
            f"{orig_prompt}\n\n"
            f"[SYSTEM RESUME INSTRUCTION: You were disconnected before finishing this book. "
            f"Below is the last section you wrote. DO NOT start over or repeat previous chapters. "
            f"Continue writing immediately from the exact sentence where this stops:]\n\n"
            f"{saved_text[-3000:]}"
        )
        active_key = matched_key
    else:
        saved_text = ""
        prompt_to_send = message
        active_key = msg_lower
        checkpoints[active_key] = {
            "prompt": msg_clean,
            "content": "",
            "status": "in_progress"
        }

    async for chunk in chat(prompt_to_send, history):
        chunk_str = str(chunk)
        combined = f"{saved_text}\n\n{chunk_str}" if saved_text else chunk_str
        if len(chunk_str) > 100:
            checkpoints[active_key]["content"] = combined
            with open(cp_file, "w", encoding="utf-8") as f:
                json.dump(checkpoints, f)
        yield combined

    checkpoints[active_key]["status"] = "completed"
    with open(cp_file, "w", encoding="utf-8") as f:
        json.dump(checkpoints, f)

# Blocks UI
with gr.Blocks(title="KDP Travel Guide System") as demo:
    gr.Markdown("# 📖 KDP Travel Guide System")
    gr.Markdown("Brainstorm niches, research first-hand experiences, write opinionated chapters, and format print-ready publications.")
    
    with gr.Tab("Phase A: Niche & Series Architect"):
        gr.Markdown("### 🧭 Step 1: Market Analysis, Curated 12-Chapter TOC & Master Prompt Compiler")
        gr.Markdown("Input your destination, traveler constraints, and interest verticals. Phase A conducts commercial market analysis, curates a complete 12-chapter table of contents, and compiles a comprehensive **Master Prompt** with a 1-click copy button to paste directly into Phase B.")
        with gr.Row():
            with gr.Column(scale=1):
                dest_input = gr.Textbox(label="Destination(s)", placeholder="e.g. Lisbon, Swiss Alps, Kyoto", value="Swiss Alps")
                profile_input = gr.Textbox(label="Traveler Profile / Identity / Constraints", placeholder="e.g. solo travelers, budget backpackers, active seniors", value="budget backpackers")
                constraints_input = gr.Textbox(label="Trip Constraints", placeholder="e.g. 5-day itinerary, carry-on only, public transit only", value="5-day itinerary")
                interests_input = gr.Textbox(label="Interest Verticals", placeholder="e.g. alpine hiking, hut-to-hut trails, local cheese & bakeries", value="hiking, local food")
                architect_btn = gr.Button("✨ Architect Book & Generate Phase B Master Prompt", variant="primary")
            with gr.Column(scale=1):
                master_prompt_output = gr.Code(
                    label="📋 Generated Master Prompt for Phase B (Click Copy Icon on top-right & Paste into Phase B-E)",
                    language="markdown",
                    lines=14
                )
        
        with gr.Row():
            architect_output = gr.Markdown(label="📊 Strategic Architecture & Market Analysis")
        
        architect_btn.click(
            fn=run_niche_architect,
            inputs=[dest_input, profile_input, constraints_input, interests_input],
            outputs=[master_prompt_output, architect_output]
        )

    with gr.Tab("Phase B-E: Guide Writer & Formatter"):
        gr.ChatInterface(
            fn=resume_chat,
            description=(
                "Paste the **Master Prompt** generated from Phase A (or enter any custom book request). "
                "The system automatically adopts the curated 12-chapter outline, executes 23-pillar field research via Tavily, drafts comprehensive chapters in the first-person lived-experience voice, "
                "acquires verified photographic figures, formats 7\"×10\" Word (.docx) and print-ready PDFs, and compiles the full KDP launch package."
            ),
            examples=[
                "Create a comprehensive KDP travel guide for hiking in the Swiss Alps, covering the Bernese Oberland and Valais regions.",
                "Write a detailed KDP field guide for backpacking through Japan's historic trails, including the Kumano Kodo and Nakasendo.",
            ]
        )

# Create the FastAPI app and mount Gradio
os.environ["GRADIO_ALLOWED_PATHS"] = "output"
app = FastAPI()

@app.post("/api/run-cron")
def run_cron(x_cron_secret: str = Header(None)):
    if x_cron_secret != os.environ.get("CRON_SECRET"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    current_time = datetime.now().strftime("%I:%M %p")
    lucky_number = random.randint(1, 1000)
    print(f"[{current_time}] Task triggered! Random number: {lucky_number}")
    return {"message": f"Task completed. Number: {lucky_number}"}

app = gr.mount_gradio_app(app, demo, path="/")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
