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
    generate_image_tool,
    acquire_photographic_evidence,
    enhance_cover_prompt,
    enhance_chapter_illustration_prompt,
    enhance_evidence_prompt,
    format_kdp_guide,
    format_kdp_docx,
    save_document,
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
)

# 1. Cheaper Model (DeepSeek Flash) for planning, research synthesis, formatting, etc.
DEEPSEEK_FLASH_MODEL = OpenAIChatCompletionsModel(
    model="deepseek-v4-flash",
    openai_client=deepseek_client,
)

# 2. Demanding Model (DeepSeek Pro) for writing the final comprehensive book chapters
DEEPSEEK_PRO_MODEL = OpenAIChatCompletionsModel(
    model="deepseek-v4-pro",
    openai_client=deepseek_client,
)

# Disable standard OpenAI tracing
set_tracing_disabled(True)

# ============================================================
# MULTI-AGENT SPECIFICATIONS
# ============================================================

# 1. EBOOK PLANNER AGENT (DeepSeek Flash)
research_agent = Agent(
    name="KDP Ebook Planner Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions="""
You are the Amazon KDP Ebook Planner. Your job is to transform an ebook idea into a highly structured chapter outline specifically optimized for the Amazon KDP Guide format.

KDP guides must be comprehensive, logical, and highly structured to provide maximum value to Kindle readers, similar to a premium travel/hiking field guide.

Given the ebook idea, generate a structured outline in JSON format.
Ensure you return ONLY the JSON block inside markdown triple backticks (```json ... ```).

When generating the outline, enforce these strict Table of Contents structure rules:
- Include a "How to Use This Book" section inside the Introduction chapter.
- Design at least one situational or constraint-specific chapter (e.g. rainy days, tight on time, traveling with kids, last-minute logistics, budget alternatives, or accessibility routing).
- Add pull-out / printable bonus sections in the final chapter or appendix (e.g. a packing list, cheat sheet, route map blueprint, or expense tracker).
- Ensure niche constraints (e.g. step-free paths for wheelchair users, allergy-safe food cards, sober nightlife spots) have dedicated, highly specific sections in relevant chapters.
- The total length of the guide must fit within a 150-page KDP printing limit, so plan between 5 to 7 highly focused chapters.

JSON Schema:
{
  "title": "A compelling, keyword-rich title for the Amazon KDP Guide",
  "subtitle": "An action-oriented subtitle that promises a specific outcome",
  "author": "An appropriate author name or pen name",
  "cover_image_prompt": "A detailed, high-quality prompt for generating the book cover image. Style should be professional, suitable for a KDP guide.",
  "chapters": [
    {
      "title": "Introduction: [Subtitle]",
      "focus": "Introduce the topic, explain why it matters, target reader profile, and the transformation promised by this guide.",
      "subsections": ["How to Use This Book", "Overview of topic", "Relevance in 2026", "Key objectives / structure of guide"],
      "search_queries": ["query about the general trend or relevance of this topic"],
      "image_prompt": "An illustration prompt representing the beginning of the journey, matching the cover/book style.",
      "image_caption": "Italicized caption text for the introductory illustration."
    },
    {
      "title": "Chapter 1: [Title]",
      "focus": "Specific concepts, definitions, and foundations. Detailed sub-topics.",
      "subsections": ["Subsection A Title", "Subsection B Title", "Subsection C Title"],
      "search_queries": ["query for specific facts/data", "query for recent statistics"],
      "image_prompt": "A descriptive illustration prompt for Chapter 1.",
      "image_caption": "Italicized caption text for the Chapter 1 illustration."
    },
    ...
    {
      "title": "Conclusion: [Subtitle]",
      "focus": "Summary of key takeaways, actionable next steps, checklist, and a call to action.",
      "subsections": ["Key Takeaways Summary", "Actionable Checklist / Framework / Bonus Sheets", "Final Inspirational Closing Thoughts"],
      "search_queries": [],
      "image_prompt": "An illustration prompt representing completion or success.",
      "image_caption": "Italicized caption text for the conclusion illustration."
    }
  ]
}
""",
)

# 2. WEB RESEARCH AGENT (DeepSeek Flash) - FIELD RESEARCH ENGINE
web_research_agent = Agent(
    name="Web Research Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions="""
You are the Web Research Agent, acting as an investigative travel researcher and evidence compiler for the KDP Travel Guide System.

Your job is NOT to write a generic travel guide, but to conduct deep web research and extract specific, first-hand, human-reported experiences about the destination and chapter focus.

Evidence Philosophy:
- Do not report what a generic travel website says tourists should do. Find out what actually happened to real people when they did it.
- Look for the messy details: actual prices paid, waiting times, mistakes, disappointments, scams, queue lengths, confusing signs, pickpockets, sensory details (smell, noise, physical experience), and public bathroom availability.
- Prioritize:
  * LEVEL A (Direct First-Hand Experience): "I went there...", "We paid €17...", "I waited 45 minutes...".
  * LEVEL B (Multiple Independent Reports): Recurring patterns observed across multiple sources.
  * LEVEL C (Local / Expat Insights): Advice on what is overrated, where residents eat, safety tips.
  * LEVEL D (Official Info): Current prices, hours, rules, ticketing requirements.

Do not write the ebook chapter text itself. Provide only the structured research synthesis.

CRITICAL RULES FOR RESPONSE FORMAT:
- The only tool you can call is `search_web`. You do NOT have any tool called `summary_of_findings` or similar.
- During the search phase, output ONLY the tool calls. Do NOT write any conversational text, markdown headers, or greetings before or alongside your tool calls.
- Once all search queries have been executed and you are ready to write your final research synthesis, present it as standard plain markdown text. Start your final response directly with "### Research Brief for [Chapter Title]".
- Never output your final synthesis as a function call, tool call, or in JSON format.
- Structuring your final output: Organize your synthesis using these sections:
  1. High-Confidence Findings (Findings, Evidence, Dates, Sources, Confidence score 1-5, Practical implication)
  2. Best First-Hand Stories (Location, Who experienced it, Date, What happened, What they paid, What went wrong, Lessons learned, Source URL)
  3. Failures & Mistakes (Mistake → Consequence → Lesson)
  4. Real Prices (Markdown table showing: Item, Advertised Price, Actual Price Paid, Date, Location, Source)
  5. Waiting Times (Markdown table showing: Place, Reported Wait, Date, Time of Day, Circumstances, Source)
  6. Transportation & Walking Reality (Metro/Bus experience, card/cash/contactless, pedestrian quality, confusing signage, taxi scams)
  7. Food & Dining Intelligence (Place, order details, actual price, waiting queue, best/worst dishes, service/hygiene perception)
  8. Bathroom Intelligence (Location, free/paid, cleanliness, accessibility, hours)
  9. Overrated / Underrated / Contradictions (Tourist traps, opposing reports)
  10. Claims Requiring Verification (Mandatory section: list claims requiring checking)
  11. Photo Opportunities (List photo opportunities the author should personally capture at the location)
""",
    tools=[search_web],
)

# 3. EBOOK WRITER AGENT (DeepSeek Pro - Paid/Demanding) - FIRST-PERSON TRAVELER PERSONA
writer_agent = Agent(
    name="Ebook Writer Agent",
    model=DEEPSEEK_PRO_MODEL,
    instructions="""
You are the Ebook Writer Agent, specializing in writing high-converting, professional, and comprehensive Amazon KDP Guides, mirroring premium travel and outdoor field guides.

Your goal is to write a single, complete chapter of the ebook.

Writing requirements:
- Tone/Style: Write in an engaging, opinionated, first-person traveler perspective (using "I", "we", "my"). You are sharing your lived experience of this destination. It must read as if you personally walked the streets, paid the entry fees, and encountered the challenges. Avoid sterile encyclopedia descriptions and generic AI filler phrases (e.g., "In today's fast-paced digital world", "delineate", "testament").
- Structure: Start directly with the main chapter header `## [Chapter Title]`. Below this header, immediately embed the chapter illustration using this exact markdown code: `![{Planned Image Caption}](chapter_{idx}.png)`. Do NOT include any intro/outro talk (e.g., "Sure, here is...").
- Content Depth: Write at least 1500-2500 words of comprehensive, thorough content. Never summarize or truncate. Cover all subsections specified in the chapter plan using H3 subheadings (`### [Subsection Title]`). Explain concepts with clear analogies, real-world examples, or step-by-step instructions.
- Lived Realities & Failures: Integrate the real-world experiences, waiting times, and dining/transit realities from the Web Research Brief. Actively document failures and warnings using the `Mistake → Consequence → Lesson` layout to help the reader avoid traps.
- Grounding & No Hallucinations: EVERY specific concrete detail — prices, named accommodations/restaurants/bars, named people, quotes, wait times, exact dates — MUST come directly from the Web Research Brief. Do NOT invent, generalize, or infer details that are not in the notes. If the blueprint/outline requires a specific detail that is missing from the research, do NOT invent it. Instead, insert a clearly marked placeholder: `[NEEDS INPUT: description of missing detail]` and compile a list in a `### ⚠️ Gaps to Fill` section at the very end of your chapter draft.
- Financial Accuracy: Cite exact actual prices paid rather than generic estimates, including the date of the cost (e.g., "Paid €17 in March 2026").
- Photo Suggestions: Embed 2-3 specific photo recommendations spaced evenly throughout the chapter at the exact place where they belong in the narrative using this strict figure caption format:
  `Figure X.X — Title of Image: Caption: Explanation of what the reader is seeing and why it matters. | [PHOTO RECOMMENDATION: Clear descriptive prompt of the scene to photograph] | Credit: Author's own`
- Maps Integration: If the section involves route directions or geography, add map recommendations using this format:
  `Map X.X — [Route] Overview | Caption: Description of map route details | Source: OpenStreetMap`
- Tables and Lists: Use clean markdown tables (e.g., `| Column 1 | Column 2 |`) for compiling comparative data, actual pricing logs, or transit schedules for maximum scannability.
- End with a summary checklist or action framework.
- "3 Things" Callout: Conclude the chapter (before the Gaps to Fill section) with a structured markdown blockquote box:
  > ### 📍 If You Only Have Time for 3 Things:
  > 1. **[Key Highlight 1]** - [Brief practical context]
  > 2. **[Key Highlight 2]** - [Brief practical context]
  > 3. **[Key Highlight 3]** - [Brief practical context]
""",
)

# 4. NICHE ARCHITECT AGENT (DeepSeek Flash) - PHASE A
niche_architect_agent = Agent(
    name="Niche Architect Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions="""
You are the KDP Travel Guide Niche Architect. Your goal is to guide the author through Phase A: Niche Discovery, Series Brand Identity, and SEO Title Planning (Modules 1, 2, and 3).

When given:
- Destination(s)
- Traveler Profile/Identity/Constraints
- Trip Constraints
- Interest Verticals

You must generate:
1. Sellable Niche Angles (Module 1): 5-8 niche combinations with exact phrases, underserved analysis, and Gut-Check demand validation. Rank the top 3.
2. Series Naming & Brand Identity (Module 2): 5 series names and a launch lineup of 5-8 books with title formulas.
3. Title, Subtitle & Keyword Plan (Module 3): 5 SEO title+subtitle combinations for the flagship book, a ranked list of high-intent search keywords, 7 backend KDP keywords (no duplicates of title/subtitle), and specific low-competition categories.

Format the output cleanly in Markdown. Do not include introductory conversational banter or greetings. Start directly with `# Phase A: Niche & Series Architecture Plan`.
""",
)

async def run_niche_architect(destinations: str, traveler_profile: str, trip_constraints: str, interest_verticals: str) -> str:
    prompt = f"""
We are running Phase A of the KDP Travel Guide System.
Input details:
- Destination(s): {destinations}
- Traveler Profile/Identity/Constraints: {traveler_profile}
- Trip Constraints: {trip_constraints}
- Interest Verticals: {interest_verticals}

Please generate the niche discovery, series naming, and book title keyword plan.
"""
    result = await Runner.run(niche_architect_agent, prompt, max_turns=30)
    report = result.final_output
    
    # Save plan to output/niche_series_plan.md
    os.makedirs("output", exist_ok=True)
    with open("output/niche_series_plan.md", "w", encoding="utf-8") as f:
        f.write(report)
        
    plan_path = os.path.abspath("output/niche_series_plan.md").replace("\\", "/")
    return f"{report}\n\n---\n📂 **Saved Plan**: [niche_series_plan.md](file:///{plan_path})"

# 5. BOOK CONTEXT AGENT (DeepSeek Flash) - PHASE A
book_context_agent = Agent(
    name="Book Context Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions="""
You are a professional nonfiction publishing strategist and book editor.
Your task is to generate the Book Context information required for writing a professionally structured travel guide.

Given the book outline and KDP planning request, you must produce the target audience, secondary audience, tone, and depth level analysis.

Output format:
Return the result exactly in this format:

BOOK CONTEXT
Book Title: [Title]
Primary Audience: [Detailed description (experience level, age range, goals/motivations, typical problems)]
Secondary Audience: [Description of additional readers who may benefit]
Tone: [Chosen tone + explanation of why it fits]
Depth Level: [Chosen depth level + explanation of why it is appropriate]

Do not include any other markdown text or introductory greetings. Start directly with "BOOK CONTEXT".
""",
)

# 6. BLUEPRINT AGENT (DeepSeek Flash) - PHASE A
blueprint_agent = Agent(
    name="Blueprint Agent",
    model=DEEPSEEK_FLASH_MODEL,
    instructions="""
You are a professional KDP travel guide architect and publisher.
Your task is to transform the provided chapter focus and research summary into a detailed, execution-ready chapter writing blueprint that the Ebook Writer can use to generate a high-quality, publishable chapter.

You must generate:
1. CHAPTER-LEVEL OVERVIEW (Purpose, What reader should feel, Target word count)
2. CHAPTER-LEVEL BLUEPRINT (Chapter Title, Target word count, Primary Angle, Primary Job)
3. DETAILED CONTENT BREAKDOWN (Required subsections, Key points that MUST be covered, Common reader fears/mistakes to address, What the chapter MUST explicitly AVOID like fluff, generic AI text, etc.)
4. TONE & DEPTH GUIDANCE (Adaptation of overall Book Context to this specific chapter, Formatting guidance)
5. VISUAL & FIGURE BLUEPRINT (PHOTOGRAPHIC EVIDENCE):
   Specify 2-3 essential photographic verification opportunities across the chapter that verify practical field reality:
   • Entrances & exterior signage
   • Ticket vending machines, validation terminals & fare gates
   • Queues & menus (ordering counters, printed price boards)
   • Street layouts, crosswalks & wayfinding landmarks
   • Bathrooms & restroom accessibility features
   • Transportation infrastructure (station platforms, bus shelters, boarding gates)
   • Food portions & authentic dishes served
   • Storefronts & architectural facades
   For each figure, specify:
   - Figure Title (e.g. "Pincetto Minimetro Ticket Validation Terminal")
   - Verification Category (e.g. "ticket machines", "entrances signs", "queues menus", "street layouts", "bathrooms", "transportation infrastructure", "food portions", "storefronts landmarks")
   - Public Photo Search Query (e.g. "Perugia Minimetro ticket machine", "Pincetto station entrance sign")
   - Fallback Scene Description (concrete, authentic physical details for photographic reconstruction if no public photo is found)

Before you write, make sure to consider:
- Do not write actual manuscript prose or sample paragraphs.
- Be explicit, directive, and exhaustive.
- Emphasize safety, Leave No Trace, permits, and crowd avoidance.
- Manage layout constraints (keep chapters focused to fit overall book size limit).

Do not include introductory greetings or banter. Start directly with "# CHAPTER WRITING BLUEPRINT: [Chapter Title]".
""",
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

    print(f"[Orchestrator] Starting KDP Guide generation for request: '{user_request}'")
    yield update_progress(f"🎬 **Starting KDP Guide generation** for: *\"{user_request}\"*")
    
    # --------------------------------------------------------
    # STEP 1 — RESEARCH & PLAN OUTLINE
    # --------------------------------------------------------
    print("[Orchestrator] Step 1: Creating chapter outline (DeepSeek Flash)...")
    yield update_progress("📝 **Step 1: Creating chapter outline** using `deepseek-v4-flash`...")
    research_result = await Runner.run(
        research_agent,
        f"Create a detailed Amazon KDP Guide outline for this topic/idea: {user_request}",
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
        print(f"[Orchestrator] JSON parsing failed: {e}. Falling back to default outline.")
        # Fallback structure if JSON parse fails
        outline = {
            "title": f"The Ultimate Guide to {user_request}",
            "subtitle": "A Comprehensive KDP Field Guide",
            "author": "KDP Expert Writer",
            "cover_image_prompt": f"A clean, elegant book cover for a guide about {user_request}, flat design style, vector artwork",
            "chapters": [
                {
                    "title": "Introduction",
                    "focus": f"Introduce the concept of {user_request}, why it matters, and reader objectives.",
                    "subsections": ["Overview", "Relevance", "Guide Structure"],
                    "search_queries": [user_request],
                    "image_prompt": f"A starting line vector icon representing {user_request}",
                    "image_caption": f"Introduction to {user_request}"
                },
                {
                    "title": "Chapter 1: Core Fundamentals",
                    "focus": f"Review key foundational principles and components of {user_request}.",
                    "subsections": ["Foundational Elements", "Key Components", "Best Practices"],
                    "search_queries": [f"foundations of {user_request}"],
                    "image_prompt": f"Core principles flat design icon",
                    "image_caption": "Core Fundamentals Diagram"
                },
                {
                    "title": "Conclusion",
                    "focus": "Provide actionable takeaways and next steps.",
                    "subsections": ["Key Takeaways", "Actionable Next Steps", "Final Thoughts"],
                    "search_queries": [],
                    "image_prompt": "Success checklist icon",
                    "image_caption": "Action checklist representing completion"
                }
            ]
        }

    title = outline.get("title", f"The Ultimate Guide to {user_request}")
    subtitle = outline.get("subtitle", "A Comprehensive KDP Field Guide")
    author = outline.get("author", "KDP Expert Writer")
    chapters = outline.get("chapters", [])
    clean_title = re.sub(r'[^\w\s-]', '', title).strip()
    clean_title = re.sub(r'[\s-]+', '_', clean_title)

    session_dir, session_shortname = create_session_folder(title, user_request)
    session_images_dir = os.path.join(session_dir, "images")

    print(f"[Orchestrator] Outline parsed successfully: '{title}' by {author}")
    print(f"[Orchestrator] Dedicated session folder: '{session_dir}'")
    print(f"[Orchestrator] Total chapters to write: {len(chapters)}")
    yield update_progress(f"✅ **Outline planned successfully**:\n* **Title**: {title}\n* **Subtitle**: {subtitle}\n* **Author**: {author}\n* **Chapters**: {len(chapters)} chapters planned.\n* **Session Subfolder**: `output/{session_shortname}/`")

    # --------------------------------------------------------
    # STEP 1B — GENERATE BOOK CONTEXT (PHASE A)
    # --------------------------------------------------------
    print("[Orchestrator] Step 1B: Generating book context...")
    yield update_progress("🎯 **Step 1B: Generating book context (Primary/Secondary Audience, Tone, Depth)**...")
    
    context_prompt = f"""
We are planning a KDP guide.
Book Details:
- Title: {title}
- Subtitle: {subtitle}
- Author: {author}
- Total Chapters: {len(chapters)}
- Request Concept: {user_request}

Please generate the BOOK CONTEXT following Prompt 5 requirements.
"""
    context_res = await Runner.run(book_context_agent, context_prompt, max_turns=30)
    book_context = context_res.final_output
    
    # Save book context to disk in session folder
    context_file = os.path.join(session_dir, "book_context.md")
    with open(context_file, "w", encoding="utf-8") as f:
        f.write(book_context)
        
    yield update_progress(f"📋 **Book Context Generated successfully**:\n\n{book_context}")

    # --------------------------------------------------------
    # STEP 2 — WRITE CHAPTERS CHAPTER-BY-CHAPTER
    # --------------------------------------------------------
    written_chapters = []
    chapter_stats = []

    for idx, chapter in enumerate(chapters, 1):
        chapter_title = chapter.get("title", f"Chapter {idx}")
        chapter_focus = chapter.get("focus", "Explore key concepts.")
        search_queries = chapter.get("search_queries", [])
        image_prompt = chapter.get("image_prompt", f"Illustration for {chapter_title}")

        print(f"\n[Orchestrator] Processing Chapter {idx}/{len(chapters)}: '{chapter_title}'")
        yield update_progress(f"📖 **Writing Chapter {idx}/{len(chapters)}**: *\"{chapter_title}\"*")

        # A. Web Research (DeepSeek Flash + Tavily)
        research_summary = "No search queries executed."
        if search_queries:
            print(f"[Orchestrator] Running web research for '{chapter_title}'...")
            yield update_progress(f"  🔍 Running web research via Tavily for *\"{chapter_title}\"*...")
            queries_str = "\n".join(f"- {q}" for q in search_queries)
            research_prompt = f"""
We are writing a KDP guide: "{title}: {subtitle}" by {author}.
Research the web for the chapter: "{chapter_title}".
Focus of this chapter: {chapter_focus}

Run searches for these queries:
{queries_str}

Summarize your findings into a comprehensive research brief with key facts, statistics, and source URLs.
"""
            research_res = await Runner.run(web_research_agent, research_prompt, max_turns=30)
            research_summary = research_res.final_output

        # B. Generate Chapter Blueprint (Phase A/Blueprint Step)
        print(f"[Orchestrator] Generating chapter blueprint for '{chapter_title}'...")
        yield update_progress(f"  📋 Generating chapter blueprint (Purpose, Angles, Content rules)...")
        
        blueprint_prompt = f"""
Book Title: {title}
Book Subtitle: {subtitle}
Author: {author}

BOOK CONTEXT:
{book_context}

Chapter Focus:
- Chapter Number: {idx}
- Title: {chapter_title}
- Focus: {chapter_focus}
- Subsections: {", ".join(chapter.get("subsections", []))}

Web Research Brief:
{research_summary}

Please generate the CHAPTER WRITING BLUEPRINT following Prompt 6 requirements.
"""
        blueprint_res = await Runner.run(blueprint_agent, blueprint_prompt, max_turns=30)
        chapter_blueprint = blueprint_res.final_output
        
        # Save chapter blueprint to disk inside session folder
        blueprint_file = os.path.join(session_dir, f"chapter_{idx}_blueprint.md")
        with open(blueprint_file, "w", encoding="utf-8") as f:
            f.write(chapter_blueprint)
            
        yield update_progress(f"  ✅ Chapter Blueprint generated and saved.")

        # C. Write Chapter Content (DeepSeek)
        print(f"[Orchestrator] Writing chapter content using DeepSeek for '{chapter_title}'...")
        yield update_progress(f"  ✍️ Drafting prose content (1500–2500 words) using `deepseek-v4-pro`...")
        
        # Build context of completed chapters
        context_chapters = ""
        if written_chapters:
            context_chapters = "\n".join(f"- Completed: {title}" for title, _ in written_chapters)

        writer_prompt = f"""
We are writing an Amazon KDP guide.
Book Details:
- Title: {title}
- Subtitle: {subtitle}
- Author: {author}

We have completed the following chapters so far:
{context_chapters if context_chapters else "None (This is the first chapter)"}

Overall Book Context:
{book_context}

This Chapter's Blueprint:
{chapter_blueprint}

Here is the Web Research Brief containing facts and sources to integrate:
{research_summary}

Now, write the complete content for this chapter following the chapter blueprint guidelines:
- Chapter Index / Number: {idx}
- Chapter Title: {chapter_title}
- Chapter Focus: {chapter_focus}

Writing Guidelines:
- Return ONLY the chapter markdown content. Start directly with the header `## {chapter_title}`.
- Below the header, immediately embed the chapter illustration using this exact markdown code:
  `![{chapter.get("image_caption", "Illustration for " + chapter_title)}](chapter_{idx}.png)`
- Cover all subsections using H3 subheadings (`### [Subsection Title]`).
- Write at least 1500-2500 words of comprehensive content. Do not truncate or summarize.
- Write in an engaging, opinionated, first-person traveler perspective (using "I", "we", "my") as if sharing your personal lived experience.
- Grounding: EVERY specific concrete detail — prices, named accommodations/restaurants/bars, named people, quotes, wait times, exact dates — MUST come directly from the Web Research Brief. Do NOT invent, generalize, or infer details that are not in the notes. If the blueprint/outline requires a specific detail that is missing from the research, do NOT invent it. Instead, insert a clearly marked placeholder: `[NEEDS INPUT: description of missing detail]` and compile a list in a `### ⚠️ Gaps to Fill` section at the very end of the chapter draft.
- Financial Accuracy: Cite exact actual prices paid rather than generic estimates, including the date of the cost (e.g., "Paid €17 in March 2026").
- Photographic Evidence: Embed clear photographic verification figures at the exact place where they belong in the text using this strict figure verification format:
  `Figure {idx}.Y — Title of Image: Caption / Practical Guidance. | [PHOTO EVIDENCE: Category: <category> | Query: <search query for public photo> | Scene: <descriptive scene detail>]`
- CRITICAL ATTRIBUTION RULE:
  Do NOT pretend publicly sourced photos or visual reconstructions are the author's own photographs!
  Never write "Credit: Author's own". Every photograph must be truthfully documented with its source and date.
- Maps Integration: If the section involves route directions or geography, add map recommendations using this format:
  `Map {idx}.Y — [Route] Overview | Caption: Description | Source: OpenStreetMap`
- Format comparative or tabular details in clean markdown tables (e.g. `| Column 1 | Column 2 |`) for maximum readability.
- End with a summary checklist or action framework.
- Conclude the chapter (before the Gaps to Fill section) with a structured markdown blockquote box:
  > ### 📍 If You Only Have Time for 3 Things:
  > 1. **[Key Highlight 1]** - [Brief practical context]
  > 2. **[Key Highlight 2]** - [Brief practical context]
  > 3. **[Key Highlight 3]** - [Brief practical context]
"""
        writer_res = await Runner.run(writer_agent, writer_prompt, max_turns=30)
        chapter_content = writer_res.final_output
        
        # Parse inline photographic evidence recommendations and acquire figures (up to 3 per chapter)
        evidence_pattern = re.compile(
            r"(Figure\s+(\d+\.[\w\d]+)\s*—\s*([^|\n]+?):\s*([^|\n]+?)\s*\|\s*\[(?:PHOTO EVIDENCE|PHOTO RECOMMENDATION):\s*([^\]]+?)\](?:\s*\|\s*Credit:\s*[^\n]+)?)"
        )
        evidence_matches = list(evidence_pattern.finditer(chapter_content))
        
        if evidence_matches:
            for f_idx, em in enumerate(evidence_matches[:3], 1):
                full_match_text = em.group(1)
                fig_num = em.group(2)
                fig_title = em.group(3).strip()
                fig_desc = em.group(4).strip()
                raw_params = em.group(5).strip()
                
                cat = "general"
                search_q = f"{fig_title} {title}"
                scene_desc = f"{fig_title}: {fig_desc}"
                
                if "Query:" in raw_params or "Scene:" in raw_params or "Category:" in raw_params:
                    q_m = re.search(r"Query:\s*([^|]+)", raw_params)
                    s_m = re.search(r"Scene:\s*([^|]+)", raw_params)
                    c_m = re.search(r"Category:\s*([^|]+)", raw_params)
                    if q_m: search_q = q_m.group(1).strip()
                    if s_m: scene_desc = s_m.group(1).strip()
                    if c_m: cat = c_m.group(1).strip()
                else:
                    search_q = f"{fig_title} {raw_params}"
                    scene_desc = raw_params
                
                fig_filename = f"chapter_{idx}_fig_{f_idx}.png"
                print(f"[Orchestrator] Acquiring photographic evidence for figure {fig_num}: '{fig_title}' (Query: '{search_q}')...")
                saved_fname, attribution = acquire_photographic_evidence(
                    query=search_q,
                    fallback_scene=scene_desc,
                    filename=fig_filename,
                    output_dir=session_images_dir,
                    category=cat
                )
                replacement = f"![Figure {fig_num} — {fig_title}: {fig_desc} | {attribution}](images/{saved_fname})"
                chapter_content = chapter_content.replace(full_match_text, replacement, 1)
        else:
            simple_pattern = re.compile(r"(\[(?:PHOTO EVIDENCE|PHOTO RECOMMENDATION):\s*([^\]]+?)\])")
            simple_matches = list(simple_pattern.finditer(chapter_content))
            for f_idx, sm in enumerate(simple_matches[:2], 1):
                full_match_text = sm.group(1)
                desc = sm.group(2).strip()
                fig_filename = f"chapter_{idx}_fig_{f_idx}.png"
                print(f"[Orchestrator] Acquiring photographic evidence for chapter {idx} figure {f_idx}...")
                saved_fname, attribution = acquire_photographic_evidence(
                    query=f"{title} {desc[:40]}",
                    fallback_scene=desc,
                    filename=fig_filename,
                    output_dir=session_images_dir
                )
                replacement = f"![Figure {idx}.{f_idx} — {desc[:60]} | {attribution}](images/{saved_fname})"
                chapter_content = chapter_content.replace(full_match_text, replacement, 1)

        # Save individual chapter draft to disk inside session folder
        save_document(f"chapter_{idx}.md", chapter_content, output_dir=session_dir)
        written_chapters.append((chapter_title, chapter_content))

        # Compute stats
        word_count = len(chapter_content.split())
        chapter_stats.append((chapter_title, word_count))
        print(f"[Orchestrator] Chapter '{chapter_title}' written successfully ({word_count} words).")
        yield update_progress(f"  🎨 Generating chapter header illustration...")

        # D. Generate Chapter Illustration with Enhanced Editorial Prompt
        print(f"[Orchestrator] Generating enhanced illustration for '{chapter_title}'...")
        enhanced_img_prompt = enhance_chapter_illustration_prompt(image_prompt, chapter_title)
        generate_image_tool(enhanced_img_prompt, f"chapter_{idx}.png", output_dir=session_images_dir)
        yield update_progress(f"  ✅ Chapter {idx} finalized successfully ({word_count} words).")

    # --------------------------------------------------------
    # STEP 3 — GENERATE COVER & FORMAT FINAL BOOK
    # --------------------------------------------------------
    print("\n[Orchestrator] Step 3: Compiling cover and final formatting...")
    yield update_progress("🎨 **Step 3: Generating book cover design** via Antigravity CLI...")
    
    # Generate Book Cover with Enhanced Editorial Prompt
    cover_prompt = outline.get("cover_image_prompt", f"A beautiful book cover for {title}: {subtitle}, minimalist flat design")
    enhanced_cover_prompt = enhance_cover_prompt(cover_prompt, title, subtitle)
    print(f"[Orchestrator] Generating enhanced cover image...")
    generate_image_tool(enhanced_cover_prompt, "cover.png", output_dir=session_images_dir)

    yield update_progress("📁 **Formatting and compiling final publication manuscripts (Markdown, HTML & PDF)...**")

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
- Number of Chapters: {len(chapters)}

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

    # Build final markdown response report
    md_path = os.path.abspath(os.path.join(session_dir, f"{clean_title}.md")).replace("\\", "/")
    html_path = os.path.abspath(os.path.join(session_dir, f"{clean_title}.html")).replace("\\", "/")
    pdf_path = os.path.abspath(os.path.join(session_dir, f"{clean_title}.pdf")).replace("\\", "/")
    docx_path = os.path.abspath(docx_filename).replace("\\", "/")
    launch_path = os.path.abspath(launch_filename).replace("\\", "/")
    session_path = os.path.abspath(session_dir).replace("\\", "/")

    stats_list = "\n".join(f"* **{c_title}**: {w_count} words" for c_title, w_count in chapter_stats)
    total_words = sum(w_count for _, w_count in chapter_stats)

    report = f"""# 📖 Amazon KDP Guide Generation Complete!

## **{title}**
### *{subtitle}*
**Author**: {author}

---

### 📁 **Output Files & Links (Click to Open)**
* 📁 **Publication Folder**: [{session_shortname}/](file:///{session_path})
* 📕 **Manuscript (PDF Field Guide)**: [{clean_title}.pdf](file:///{pdf_path})
* 📝 **Manuscript (Editable Word Document)**: [{clean_title}.docx](file:///{docx_path})
* 📄 **Manuscript (KDP Markdown)**: [{clean_title}.md](file:///{md_path})
* 🌐 **Kindle Upload Format (Self-Contained HTML)**: [{clean_title}.html](file:///{html_path})
* 🚀 **KDP Launch & Metadata Package**: [{clean_title}_launch_package.md](file:///{launch_path})

---

### 📊 **Manuscript Statistics**
* **Total Chapters**: {len(chapters)}
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
        gr.Markdown("### Brainstorm and validate underserved niches, series brand names, title formulas, and backend KDP keywords before writing.")
        with gr.Row():
            with gr.Column():
                dest_input = gr.Textbox(label="Destination(s)", placeholder="e.g. Lisbon, Swiss Alps", value="Swiss Alps")
                profile_input = gr.Textbox(label="Traveler Profile / Identity / Constraints", placeholder="e.g. solo travelers, parents", value="budget backpackers")
                constraints_input = gr.Textbox(label="Trip Constraints", placeholder="e.g. 5-day, carry-on only", value="5-day itinerary")
                interests_input = gr.Textbox(label="Interest Verticals", placeholder="e.g. hiking, street food", value="hiking, local food")
                architect_btn = gr.Button("Architect Niche & Series", variant="primary")
            with gr.Column():
                architect_output = gr.Markdown(label="Architecture Plan")
        
        architect_btn.click(
            fn=run_niche_architect,
            inputs=[dest_input, profile_input, constraints_input, interests_input],
            outputs=architect_output
        )

    with gr.Tab("Phase B-E: Guide Writer & Formatter"):
        gr.ChatInterface(
            fn=chat,
            description=(
                "Describe the guide you want to create (e.g. title and angle chosen from Phase A). "
                "The system plans the outline, executes deep field research using Tavily, writes chapters in a first-person lived-experience persona, "
                "generates documentary visual covers and verified photographic evidence, compiles print-ready HTML/PDFs and editable Word (.docx) manuscripts, and constructs the KDP launch metadata package."
            ),
            examples=[
                "Create a comprehensive KDP travel guide for hiking in the Swiss Alps, covering the Bernese Oberland and Valais regions.",
                "Write a detailed KDP field guide for backpacking through Japan's historic trails, including the Kumano Kodo and Nakasendo.",
            ]
        )

if __name__ == "__main__":
    demo.launch()