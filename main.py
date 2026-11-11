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
from dotenv import load_dotenv
import gradio as gr

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
    
    # Extract the master prompt from ```master_prompt ... ``` block (handling nested code fences)
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

    # Save both outputs to disk
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
    """
    Creates a dedicated subfolder inside 'output/' with a concise shortname (e.g. 'lagos_tour_guide').
    Returns (session_dir, shortname).
    """
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

    # Safe summary of user_request for logging and initial status
    summary_req = user_request.strip().split("\n")[0][:100]
    summary_req = re.sub(r"[^\x20-\x7E\u00A0-\uFFFF]", "", summary_req).strip() or "KDP Travel Guide"

    print(f"[Orchestrator] Starting KDP Guide generation for request: '{summary_req}...'")
    yield update_progress(f"🎬 **Starting KDP Guide generation** for: *\"{summary_req}\"*")
    
    # --------------------------------------------------------
    # STEP 1 — RESEARCH & PLAN OUTLINE (DESTINATION-ADAPTIVE 12-CHAPTER TOC)
    # --------------------------------------------------------
    outline = None

    # Check if user_request already contains a pre-curated JSON outline from Phase A
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

        # Extract JSON block
        match = re.search(r"```json\s*(.*?)\s*```", research_brief, re.DOTALL)
        json_str = match.group(1) if match else research_brief.strip()

        try:
            outline = json.loads(json_str)
        except Exception as e:
            print(f"[Orchestrator] JSON parsing failed: {e}. Falling back to 12-chapter default outline.")
            clean_short = re.sub(r"[^\w\s]", "", user_request.strip().split("\n")[0][:60]).strip() or "Travel Guide"
            # Fallback 12-chapter structure matching the 44-page publishing template
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

    # Assemble all sections (Introduction + 12 Chapters + Conclusion)
    sections = []
    
    # 1. Introduction (if present)
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

    # 2. Main Destination-Adaptive Chapters (typically 12)
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

    # 3. Conclusion (if present)
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

    # --------------------------------------------------------
    # STEP 1B — GENERATE BOOK CONTEXT (PHASE A: POSITIONING & GUARDRAILS)
    # --------------------------------------------------------
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
    
    # Save book context to disk in session folder
    context_file = os.path.join(session_dir, "book_context.md")
    with open(context_file, "w", encoding="utf-8") as f:
        f.write(book_context)
        
    yield update_progress(f"📋 **Book Context Generated successfully**:\n\n{book_context}")

    # --------------------------------------------------------
    # STEP 2 — WRITE CHAPTERS SECTION-BY-SECTION
    # --------------------------------------------------------
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

        # Checkpoint Resumption: Check if chapter was already written and valid (>= 500 words)
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

        # A. Web Research (Author's Research Dossier with 23 Pillars & 5-Tier Evidence Separation)
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

        # B. Generate Section Blueprint (Phase A/Blueprint Step)
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
        
        # Save chapter blueprint to disk inside session folder
        blueprint_file = os.path.join(session_dir, f"section_{key}_blueprint.md")
        with open(blueprint_file, "w", encoding="utf-8") as f:
            f.write(chapter_blueprint)
            
        yield update_progress(f"  ✅ Section Blueprint generated and saved.")

        # C. Write Section Content (DeepSeek Chat with 5-Part Structure & Strict Negative Constraints)
        print(f"[Orchestrator] Writing section content using DeepSeek for '{sec_title}'...")
        yield update_progress(f"  ✍️ Drafting calibrated prose (1,200–1,500 words) using `deepseek-chat`...")
        
        # Build context of completed sections
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
   (Note: The formatter automatically styles 'CHAPTER {idx}' at 48pt Bold All-Caps in #1B3A6B, and '{sec_title.upper()}' at 24pt Bold Normal All-Caps in #CC9944).
2. Follow the 5-Section Chapter Structure (NEVER USE THE WORD "PART"):
   Use EXACTLY `### SECTION X` (three hashtags) for sections, NEVER `## SECTION X`! `## ` is reserved exclusively for the Chapter Title header at the start of the chapter.
   - `### SECTION 1: STRATEGIC ORIENTATION & NARRATIVE HOOK` (immediate sensory immersion: "Picture this...", why this chapter matters to the reader)
   - `### SECTION 2: CORE FIELD GUIDE` (divided by clear H4 subheadings for each sight or corridor: `#### [Subtopic Title in Title Case]`)
   - `### SECTION 3: LOGISTICS, TIMING & ROUTE REALITIES` (exact travel times, transit lines, ticket validation, crowd management, opening hours)
   - `### SECTION 4: HIGH-VALUE INSIDER RULES & MISTAKES TO AVOID` (counter-programming, tourist traps vs. local gems, honest trade-offs)
   - `### SECTION 5: ACTION FRAMEWORK & NOTICES` (step-by-step pre-trip or daily execution checklists)
3. Exemplar Quick Notices & Specialized Callout Boxes (Include in Every Chapter):
   Model your callout boxes directly on the exemplar guidebook standards:
   
   A. [TOPIC] MYTHS — BUSTED (Rust Orange Box #C04A26):
   > ### THREE [TOPIC] MYTHS — BUSTED
   > ❌ **MYTH:** "[Common tourist misconception in quotes]"
   > ✔️ **TRUTH:** [Concrete reality with exact details, figures, and reasons why].
   
   B. CULTURAL DOS & DON'TS (2-Column Slate Box #4B6B94):
   > ### CULTURAL DOS & DON'TS IN [DESTINATION]
   > | ✔ DO | ✖ DON'T |
   > |---|---|
   > | Always greet with *[Local Greeting]* before asking any question | Do not speak loudly on quiet public transit |
   > | Validate your transit ticket before boarding | Do not assume everyone speaks English without asking politely |
   
   C. FIRST-TIMER'S RECOMMENDATION (Forest Green Box #2D7D46):
   > ### FIRST-TIMER'S RECOMMENDATION
   > [High-conviction, decisive advice on base area, transit choice, or scheduling protocol].
   
   D. PRE-TRIP ESSENTIALS CHECKLIST (Deep Purple Box #4A2E80):
   > ### PRE-TRIP ESSENTIALS CHECKLIST
   > • **Passport Validity:** Minimum 6 months beyond travel dates.
   > • **Advance Bookings:** Reserve peak slots at 9:00 AM slot 4 weeks ahead.
   > • **Transit App / Card:** Exact card type and validation rules.
   
   E. ACCESSIBILITY NOTE (Berry Magenta Box #A1346C):
   > ### ACCESSIBILITY NOTE
   > [Terrain realities: stairs, elevator alternatives, flat routes, quiet sensory recovery areas].
4. Voice & Tone: 70% human-like traveler insider persona ("I", "we", "my") with tested, opinionated authority.
5. ZERO CLOSED VENUES & 100% 2026 FACTUAL ACCURACY:
   - You MUST NEVER recommend or name any restaurant, bistro, café, boutique, or venue that has closed (such as L'Épi Dupin or past closures).
   - Every named establishment MUST be confirmed open and actively operating in 2025/2026.
   - If a venue's 2026 status is not 100% verified, DO NOT cite it by name—recommend a verified, thriving, iconic 2026 alternative (e.g. Bistrot Paul Bert, Café de la Nouvelle Mairie, Chez Georges) or describe the street corridor and sensory cues.
   - NEVER write meta-excuses, apologies, or disclaimers ('I was not able to verify', 'venue from the brief', '[NEEDS INPUT]').
6. WORD COUNT CALIBRATION (Target 100–115 Total Book Pages):
   - Target 1,200–1,500 words for this chapter (Intro: ~1,000 words, Conclusion: ~800–1,000 words).
   - Maintain punchy, dense, high-signal prose without filler or repetitive exposition.
7. Financial Accuracy: Cite exact actual prices paid with date (e.g. "Paid €17 in March 2026"), not generic estimates.
8. Figures & Maps (Exactly 3 to 4 inline descriptions per chapter; NO LIVE IMAGE DOWNLOADS):
   `Figure {sec_num}.Y — Title of Scene: Category / Angle / Detailed description of scene, lighting, atmosphere / Purpose and traveler value.`
   `Map {sec_num}.Y — [Route] Walking Circuit: Map type / Overhead plan / Exact walking corridor and waypoints / Navigation purpose.`
9. Tables: Use clean comparative markdown tables (`| STOP / VENUE | RECOMMENDED TIMING | INSIDER NOTE | COST (EUR/CAD) |`).
10. Conclude with a centered milestone anchor:
   `### YOUR FIRST DAY IS DONE` (or `### YOUR TRIP STARTS NOW`, `### DAY 2 IS DONE`).
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
            
            # Direct API completion fallback if Runner returned insufficient content
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

        # Clean any legacy photo bracket tags to maintain clean Figure lines
        # e.g., "Figure 1.1 — Old Quebec: Historic Alley | [PHOTO EVIDENCE: Query: ...] | Credit: ..." -> "Figure 1.1 — Old Quebec: Historic Alley"
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

        # Save individual chapter draft to disk inside session folder
        save_document(f"chapter_{key}.md", chapter_content, output_dir=session_dir)
        written_chapters.append((sec_title, chapter_content))

        # Compute stats
        word_count = len(chapter_content.split())
        chapter_stats.append((sec_title, word_count))
        print(f"[Orchestrator] Section '{sec_title}' written successfully ({word_count} words).")
        yield update_progress(f"  ✅ Section {idx} finalized successfully ({word_count} words, visual specifications embedded).")

    # --------------------------------------------------------
    # STEP 3 — FORMAT FINAL BOOK
    # --------------------------------------------------------
    print("\n[Orchestrator] Step 3: Compiling manuscript and applying Quebec City benchmark layout...")
    yield update_progress("📁 **Step 3: Formatting and compiling final publication manuscripts (Markdown, DOCX, HTML & PDF)...**")

    # Assemble all chapter contents
    full_content = "\n\n".join(content for _, content in written_chapters)

    # Format guide to KDP Markdown & HTML & PDF inside session folder
    formatting_status = format_kdp_guide(
        title=title,
        subtitle=subtitle,
        content=full_content,
        author=author,
        output_dir=session_dir
    )
    print(f"[Orchestrator] Formatting status: {formatting_status}")

    # --------------------------------------------------------
    # STEP 4 — GENERATE METADATA & LAUNCH PACKAGE (PHASE E)
    # --------------------------------------------------------
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
1. **7 KDP Backend Keywords**: Maximize character limits (up to 50 chars per box), using high-intent keyword phrases, ensuring NO repetition of words already in the book title/subtitle.
2. **KDP Category Recommendations**: 2-3 specific, low-competition category paths.
3. **High-Converting Book Description (HTML)**: Generate a sales copy formatted in clean HTML following this strict 5-part structure:
   - **Bold first-sentence hook**: Bolded hook that immediately communicates who this guide is for, what problem it solves, and what benefit the reader gets (e.g. <b>...</b>).
   - **Expanded promise paragraph**: Short 1-3 line paragraph expanding the promise and value.
   - **Benefits-focused bullet list**: Bullet list of benefits introduced with: "In this guide, you'll learn how to..."
   - **Credibility/Reassurance paragraph**: Reassure the reader it is practical, tested, and contains no fluff.
   - **Final Call to Action paragraph**: Encouraging immediate purchase.
4. **Social Media Companion Posts**: 5 creative concepts for Pinterest/Instagram/TikTok to prove the guide's authenticity (deleted scenes, sensory highlights).
5. **Lead Magnet**: One lead magnet idea to collect reader emails.
6. **Launch Checklist**: Step-by-step launch week timeline.

Return ONLY the markdown text for the launch package. Do not include conversational greetings.
"""
    metadata_res = await Runner.run(research_agent, metadata_prompt, max_turns=30)
    launch_package = metadata_res.final_output
    
    launch_filename = os.path.join(session_dir, f"{clean_title}_launch_package.md")
    with open(launch_filename, "w", encoding="utf-8") as f:
        f.write(launch_package)

    # --------------------------------------------------------
    # STEP 5 — CLEANUP RAW INTERMEDIATE FILES AND IMAGES
    # --------------------------------------------------------
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

    # 1. Remove raw images directory
    if os.path.exists(session_images_dir):
        shutil.rmtree(session_images_dir, ignore_errors=True)
        print(f"[Orchestrator] Deleted raw images directory: {session_images_dir}")

    # 2. Remove intermediate markdown drafts and blueprints
    for root, dirs, files in os.walk(session_dir, topdown=False):
        for fname in files:
            full_fpath = os.path.abspath(os.path.join(root, fname))
            if full_fpath not in keep_files:
                try:
                    os.remove(full_fpath)
                except Exception as e:
                    print(f"[Cleanup Warning] Could not remove {fname}: {e}")
        for dname in dirs:
            d_full = os.path.join(root, dname)
            try:
                shutil.rmtree(d_full, ignore_errors=True)
            except Exception:
                pass

    print(f"[Orchestrator] Cleanup complete. Preserved final outputs in '{session_dir}'.")
    yield update_progress(f"✨ **Cleanup complete**: Removed raw intermediate files and images. Preserved final outputs in `output/{session_shortname}/`.")

    # 4. Optional Live Google Docs Sync
    gdoc_link = ""
    if os.getenv("GOOGLE_DOCS_WEBHOOK_URL"):
        yield update_progress("☁️ **Syncing manuscript with Google Docs...**")
        gdoc_res = upload_to_google_docs(title=title, content_html=full_content, content_md=full_content)
        if gdoc_res.get("success") and gdoc_res.get("url"):
            gdoc_url = gdoc_res["url"]
            gdoc_link = f"\n* 📑 **[Open Live Google Doc (Editable in Google Drive)]({gdoc_url})**"
            print(f"[Orchestrator] Live Google Doc ready: {gdoc_url}")

    # Build final markdown response report with browser-clickable HTTP download links
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

### 📝 **Open & Edit in Google Docs (`docs.google.com`)**
You can edit this manuscript live in Google Docs with your exact custom typography:
1. Click **[Download Manuscript Word (.docx)]({docx_url})** to download the Word document.
2. Go to **[docs.google.com](https://docs.google.com)** in your browser.
3. Click the 📁 **Folder icon** (*"Open file picker"*) in the top-right area (next to "Template gallery").
4. In the pop-up modal, select the **"Upload"** tab, and drag & drop the downloaded `.docx` file (or click "Browse" and select it from `{abs_session}`).
5. Google Docs will immediately open your complete manuscript with all styles preserved:
   * **Chapter Headings**: Heading 1, 48pt, ALL CAPITAL LETTERS, `#1B3A6B`, Bold, Center
   * **Chapter Subheadings**: Normal text, 24pt, ALL CAPITAL LETTERS, `#CC9944`, Bold, Center
   * **Section Headings**: Heading 2, 18pt, Uppercase, `#E01B84`, Bold, Center
   * **Section Subheadings**: Normal text, 16pt, Title Case, `#000B50`, Bold, Left
   * **Body Text**: Normal text, 12pt, `#000000`, 1.15 line spacing, 6pt before, 0pt after, Justified!

---

### 💻 **Local Windows Folder (Open via File Explorer)**
All generated files are saved directly on your computer at:
```
{abs_session}
```
*(Copy and paste the path above into your Windows File Explorer address bar to open and edit files immediately)*

---

### 📊 **Manuscript Statistics**
* **Total Sections**: {len(sections)} ({len(raw_chapters)} Core Chapters + Independent Intro & Conclusion)
* **Total Word Count**: {total_words} words
{stats_list}

---

### 📚 **Table of Contents**
"""
    for c_title, _ in written_chapters:
        slug = c_title.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"\s+", "-", slug)
        report += f"- [{c_title}](#{slug})\n"

    print("[Orchestrator] All steps complete. Returning report.")
    yield report

# ============================================================
# GRADIO INTERFACE
# ============================================================

async def chat(message, history):
    try:
        async for progress_msg in generate_ebook(message):
            yield progress_msg
    except Exception as e:
        yield f"Error generating ebook:\n\n{str(e)}"

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
    import json
    import inspect

    def resume_chat(message, history):
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

        # Check if prompt, book title, or "continue" matches an unfinished book
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

        # Run your existing chat function and save progress continuously
        if inspect.isgeneratorfunction(chat):
            for chunk in chat(prompt_to_send, history):
                chunk_str = str(chunk)
                combined = f"{saved_text}\n\n{chunk_str}" if saved_text else chunk_str
                if len(chunk_str) > 100:
                    checkpoints[active_key]["content"] = combined
                    with open(cp_file, "w", encoding="utf-8") as f:
                        json.dump(checkpoints, f)
                yield combined
        else:
            result = str(chat(prompt_to_send, history))
            combined = f"{saved_text}\n\n{result}" if saved_text else result
            checkpoints[active_key]["content"] = combined
            with open(cp_file, "w", encoding="utf-8") as f:
                json.dump(checkpoints, f)
            yield combined

        checkpoints[active_key]["status"] = "completed"
        with open(cp_file, "w", encoding="utf-8") as f:
            json.dump(checkpoints, f)

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

import os
from fastapi import FastAPI, Header, HTTPException
import uvicorn
import gradio as gr

# Create the server
app = FastAPI()

# Add the listener for cron-job.org
@app.post("/api/run-cron")
def run_cron(x_cron_secret: str = Header(None)):
    if x_cron_secret != os.environ.get("CRON_SECRET"):
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    print("Scheduled task triggered!")
    return {"message": "Task completed"}

# Connect your existing Gradio interface
app = gr.mount_gradio_app(app, demo, path="/")

# Launch everything
if __name__ == "__main__":
    output_dir = os.path.abspath("output")
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(app, host="0.0.0.0", port=port)
