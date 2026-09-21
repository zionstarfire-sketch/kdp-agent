import os
import re
import time
import subprocess
import pymupdf

def parse_markdown_tables(text: str) -> str:
    """Helper to parse markdown tables into styled HTML tables."""
    lines = text.split('\n')
    in_table = False
    table_lines = []
    new_lines = []
    
    def render_html_table(lines):
        if not lines:
            return ""
        html = ['<table class="kdp-table">']
        has_header = False
        divider_idx = -1
        
        # Check for divider line at index 1 (e.g. |---|---|)
        for idx, line in enumerate(lines):
            if idx == 1 and all(c in '|:- ' for c in line.strip()):
                divider_idx = idx
                break
                
        for idx, line in enumerate(lines):
            if idx == divider_idx:
                continue
            cells = [c.strip() for c in line.split('|')[1:-1]]
            
            if idx == 0 and divider_idx == 1:
                html.append('  <thead>')
                html.append('    <tr>')
                for cell in cells:
                    html.append(f'      <th>{cell}</th>')
                html.append('    </tr>')
                html.append('  </thead>')
                html.append('  <tbody>')
                has_header = True
            else:
                html.append('    <tr>')
                for cell in cells:
                    html.append(f'      <td>{cell}</td>')
                html.append('    </tr>')
                
        if has_header:
            html.append('  </tbody>')
        html.append('</table>')
        return '\n'.join(html)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('|') and stripped.endswith('|'):
            in_table = True
            table_lines.append(stripped)
        else:
            if in_table:
                html_table = render_html_table(table_lines)
                new_lines.append(html_table)
                table_lines = []
                in_table = False
            new_lines.append(line)
            
    return '\n'.join(new_lines)


def parse_markdown_blockquotes(text: str) -> str:
    """Helper to parse multi-line blockquotes into styled HTML callouts."""
    lines = text.split('\n')
    in_bq = False
    bq_lines = []
    new_lines = []
    
    def render_bq(lines):
        if not lines:
            return ""
        bq_text = '<br>\n'.join(lines)
        is_warning = '⚠️' in bq_text or 'MISTAKE' in bq_text.upper() or 'WARNING' in bq_text.upper()
        is_three_things = 'TIME FOR 3 THINGS' in bq_text.upper() or '3 THINGS' in bq_text.upper()
        
        if is_three_things:
            return f'<div class="three-things-box">\n{bq_text}\n</div>'
        elif is_warning:
            return f'<blockquote class="warning-callout">\n{bq_text}\n</blockquote>'
        else:
            return f'<blockquote class="highlight-quote">\n{bq_text}\n</blockquote>'

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('>'):
            in_bq = True
            content_line = stripped[1:].strip()
            bq_lines.append(content_line)
        else:
            if in_bq:
                new_lines.append(render_bq(bq_lines))
                bq_lines = []
                in_bq = False
            new_lines.append(line)
            
    if in_bq:
        new_lines.append(render_bq(bq_lines))
        
    return '\n'.join(new_lines)


def format_kdp_docx(title: str, subtitle: str, content: str, author: str = "AI Writer", output_dir: str = "output") -> str:
    """
    Format raw manuscript text into an Amazon KDP-compatible editable Microsoft Word (.docx) guide.
    Applies 7x10 book geometry, styled headings, embedded images with truthful attribution captions,
    styled blockquote callouts, and clean tables.
    """
    try:
        import docx
        from docx.shared import Inches, Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.oxml import parse_xml
        from docx.oxml.ns import nsdecls

        doc = docx.Document()
        section = doc.sections[0]
        # KDP 7" x 10" Trim Size
        section.page_width = Inches(7.0)
        section.page_height = Inches(10.0)
        section.left_margin = Inches(0.6)
        section.right_margin = Inches(0.6)
        section.top_margin = Inches(0.6)
        section.bottom_margin = Inches(0.6)

        clean_title = re.sub(r'[^\w\s-]', '', title).strip()
        clean_title = re.sub(r'[\s-]+', '_', clean_title)

        # 1. Front Cover (if available)
        cover_candidates = [
            os.path.join(output_dir, "images", "cover.png"),
            os.path.join(output_dir, "cover.png"),
            "output/images/cover.png",
            "images/cover.png"
        ]
        for c_path in cover_candidates:
            if os.path.exists(c_path):
                cp = doc.add_paragraph()
                cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = cp.add_run()
                try:
                    run.add_picture(c_path, width=Inches(5.5))
                    doc.add_page_break()
                except Exception:
                    pass
                break

        # 2. Title Page
        tp = doc.add_paragraph()
        tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        tp.paragraph_format.space_before = Pt(40)
        tp.paragraph_format.space_after = Pt(12)
        t_run = tp.add_run(title)
        t_run.font.name = "Georgia"
        t_run.font.size = Pt(26)
        t_run.font.bold = True
        t_run.font.color.rgb = RGBColor(4, 146, 148)  # Teal accent

        sp = doc.add_paragraph()
        sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sp.paragraph_format.space_after = Pt(24)
        s_run = sp.add_run(subtitle.upper())
        s_run.font.name = "Georgia"
        s_run.font.size = Pt(13)
        s_run.font.color.rgb = RGBColor(204, 153, 68)  # Gold accent

        ap = doc.add_paragraph()
        ap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        a_run = ap.add_run(f"By {author}")
        a_run.font.name = "Calibri"
        a_run.font.size = Pt(11)
        a_run.font.color.rgb = RGBColor(100, 100, 100)

        doc.add_page_break()

        # 3. Copyright & Legal Disclaimer
        c_head = doc.add_paragraph()
        c_head.paragraph_format.space_before = Pt(30)
        c_head.paragraph_format.space_after = Pt(6)
        c_run = c_head.add_run(f"Copyright © 2026 by {author}")
        c_run.font.name = "Georgia"
        c_run.font.size = Pt(14)
        c_run.font.bold = True
        c_run.font.color.rgb = RGBColor(27, 58, 107)

        c_body = doc.add_paragraph()
        c_body.paragraph_format.space_after = Pt(12)
        c_body_run = c_body.add_run(
            "All rights reserved. No part of this publication may be reproduced, distributed, or transmitted in any form or by any means without the prior written permission of the publisher.\n\n"
            "First Edition: 2026\n"
            "Format: Amazon KDP Direct (Print & Digital)"
        )
        c_body_run.font.size = Pt(9.5)
        c_body_run.font.color.rgb = RGBColor(80, 80, 80)

        d_head = doc.add_paragraph()
        d_head.paragraph_format.space_before = Pt(16)
        d_head.paragraph_format.space_after = Pt(6)
        d_run = d_head.add_run("Disclaimer & Legal Notice")
        d_run.font.name = "Georgia"
        d_run.font.size = Pt(12)
        d_run.font.bold = True
        d_run.font.color.rgb = RGBColor(27, 58, 107)

        d_body = doc.add_paragraph()
        d_body_run = d_body.add_run(
            "This field guide is intended for informational and personal planning purposes only. "
            "Readers assume full responsibility for their own safety, route choices, transit ticketing, "
            "and health precautions. Prices, operating hours, and local regulations are subject to change."
        )
        d_body_run.font.size = Pt(9.5)
        d_body_run.font.color.rgb = RGBColor(80, 80, 80)

        doc.add_page_break()

        # 4. Table of Contents
        toc_p = doc.add_paragraph()
        toc_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        toc_p.paragraph_format.space_after = Pt(18)
        toc_run = toc_p.add_run("TABLE OF CONTENTS")
        toc_run.font.name = "Georgia"
        toc_run.font.size = Pt(18)
        toc_run.font.bold = True
        toc_run.font.color.rgb = RGBColor(4, 146, 148)

        raw_chapters = re.split(r'(^##\s+.*$)', content, flags=re.MULTILINE)
        for i in range(1, len(raw_chapters), 2):
            ch_line = raw_chapters[i].replace("##", "").strip()
            item_p = doc.add_paragraph()
            item_p.paragraph_format.space_after = Pt(4)
            item_run = item_p.add_run(f"•  {ch_line}")
            item_run.font.name = "Georgia"
            item_run.font.size = Pt(10.5)
            item_run.font.bold = True
            item_run.font.color.rgb = RGBColor(27, 58, 107)

        doc.add_page_break()

        # 5. Body Chapters Content
        lines = content.split("\n")
        in_table = False
        table_lines = []
        in_blockquote = False
        bq_lines = []

        def flush_table():
            nonlocal table_lines, in_table
            if not table_lines:
                return
            rows = []
            for tl in table_lines:
                if all(c in '|:- ' for c in tl.strip()):
                    continue
                cells = [c.strip() for c in tl.split('|')[1:-1]]
                if cells:
                    rows.append(cells)
            if rows:
                num_cols = max(len(r) for r in rows)
                t = doc.add_table(rows=len(rows), cols=num_cols)
                t.alignment = WD_TABLE_ALIGNMENT.CENTER
                for r_idx, row_data in enumerate(rows):
                    row = t.rows[r_idx]
                    is_header = (r_idx == 0)
                    for c_idx in range(num_cols):
                        val = row_data[c_idx] if c_idx < len(row_data) else ""
                        cell = row.cells[c_idx]
                        cell.text = val
                        p = cell.paragraphs[0]
                        p.paragraph_format.space_after = Pt(2)
                        p.paragraph_format.space_before = Pt(2)
                        if is_header:
                            p.runs[0].font.bold = True
                            p.runs[0].font.size = Pt(9.5)
                            p.runs[0].font.color.rgb = RGBColor(27, 58, 107)
                            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F0F4F8"/>')
                            cell._tc.get_or_add_tcPr().append(shd)
                        else:
                            if p.runs:
                                p.runs[0].font.size = Pt(9)
                                p.runs[0].font.color.rgb = RGBColor(50, 50, 50)
            table_lines = []
            in_table = False

        def flush_blockquote():
            nonlocal bq_lines, in_blockquote
            if not bq_lines:
                return
            bq_text = " ".join(bq_lines)
            bp = doc.add_paragraph()
            bp.paragraph_format.left_indent = Inches(0.4)
            bp.paragraph_format.right_indent = Inches(0.4)
            bp.paragraph_format.space_before = Pt(6)
            bp.paragraph_format.space_after = Pt(8)
            b_run = bp.add_run(bq_text)
            b_run.font.italic = True
            b_run.font.size = Pt(9.5)
            b_run.font.color.rgb = RGBColor(45, 55, 72)
            bq_lines = []
            in_blockquote = False

        for line in lines:
            stripped = line.strip()

            if stripped.startswith("|") and stripped.endswith("|"):
                if in_blockquote:
                    flush_blockquote()
                in_table = True
                table_lines.append(stripped)
                continue
            else:
                if in_table:
                    flush_table()

            if stripped.startswith(">"):
                bq_text = stripped.lstrip(">").strip()
                in_blockquote = True
                bq_lines.append(bq_text)
                continue
            else:
                if in_blockquote:
                    flush_blockquote()

            if not stripped:
                continue

            # Heading 1 (Chapter)
            if stripped.startswith("## "):
                ch_title = stripped[3:].strip()
                h1_p = doc.add_paragraph()
                h1_p.paragraph_format.space_before = Pt(20)
                h1_p.paragraph_format.space_after = Pt(10)
                h1_run = h1_p.add_run(ch_title)
                h1_run.font.name = "Georgia"
                h1_run.font.size = Pt(18)
                h1_run.font.bold = True
                h1_run.font.color.rgb = RGBColor(4, 146, 148)
                continue

            # Heading 2 (Section)
            if stripped.startswith("### "):
                sec_title = stripped[4:].strip()
                h2_p = doc.add_paragraph()
                h2_p.paragraph_format.space_before = Pt(14)
                h2_p.paragraph_format.space_after = Pt(6)
                h2_run = h2_p.add_run(sec_title)
                h2_run.font.name = "Georgia"
                h2_run.font.size = Pt(13)
                h2_run.font.bold = True
                h2_run.font.color.rgb = RGBColor(27, 58, 107)
                continue

            # Heading 3 (Subsection)
            if stripped.startswith("#### "):
                sub_title = stripped[5:].strip()
                h3_p = doc.add_paragraph()
                h3_p.paragraph_format.space_before = Pt(10)
                h3_p.paragraph_format.space_after = Pt(4)
                h3_run = h3_p.add_run(sub_title)
                h3_run.font.name = "Georgia"
                h3_run.font.size = Pt(11)
                h3_run.font.bold = True
                h3_run.font.color.rgb = RGBColor(192, 86, 33)
                continue

            # Image markdown: ![caption](path)
            img_match = re.match(r'!\[(.*?)\]\((.*?)\)', stripped)
            if img_match:
                caption = img_match.group(1)
                img_path = img_match.group(2)
                fname = os.path.basename(img_path)
                candidates = [
                    os.path.join(output_dir, "images", fname),
                    os.path.join(output_dir, fname),
                    img_path,
                    os.path.join("output", "images", fname)
                ]
                actual_img = None
                for cand in candidates:
                    if os.path.exists(cand):
                        actual_img = cand
                        break
                
                if actual_img:
                    try:
                        ip = doc.add_paragraph()
                        ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
                        ip.paragraph_format.space_before = Pt(10)
                        ip.paragraph_format.space_after = Pt(2)
                        run = ip.add_run()
                        run.add_picture(actual_img, width=Inches(5.2))
                    except Exception:
                        pass

                cap_p = doc.add_paragraph()
                cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap_p.paragraph_format.space_after = Pt(12)
                cap_run = cap_p.add_run(caption)
                cap_run.font.italic = True
                cap_run.font.size = Pt(8.5)
                cap_run.font.color.rgb = RGBColor(113, 128, 150)
                continue

            # Normal Paragraph
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(5)
            p.paragraph_format.line_spacing = 1.15
            run = p.add_run(stripped)
            run.font.name = "Calibri"
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(40, 40, 40)

        if in_table:
            flush_table()
        if in_blockquote:
            flush_blockquote()

        docx_filepath = os.path.join(output_dir, f"{clean_title}.docx")
        doc.save(docx_filepath)
        return docx_filepath
    except Exception as e:
        print(f"[DocxFormatter Error] Failed to generate docx: {e}")
        return None


def format_kdp_guide(title: str, subtitle: str, content: str, author: str = "AI Writer", output_dir: str = "output") -> str:
    """
    Format raw manuscript text into an Amazon KDP-compatible guide.
    This includes adding a Title Page, Copyright Page, Disclaimer Page, Table of Contents,
    inserting page breaks, and formatting headers.

    Args:
        title: The main title of the guide.
        subtitle: The subtitle of the guide.
        content: The raw markdown content of the guide chapters.
        author: The author name to put on the cover and copyright pages.
        output_dir: The directory where final files (.md, .html, .pdf) are saved. Defaults to 'output'.

    Returns:
        The formatted manuscript as a Markdown string.
    """
    try:
        # 1. Title Page
        title_page = f"""# {title}
## {subtitle}
**By {author}**

---
"""
        
        # 2. Copyright Page
        copyright_page = f"""### Copyright © 2026 by {author}

All rights reserved. No part of this publication may be reproduced, distributed, or transmitted in any form or by any means, including photocopying, recording, or other electronic or mechanical methods, without the prior written permission of the publisher, except in the case of brief quotations embodied in critical reviews and certain other noncommercial uses permitted by copyright law.

First Edition: August 2026
Format: Amazon KDP Direct

---
"""

        # 2.5 Disclaimer Page
        disclaimer_page = f"""### Disclaimer & Legal Notice

1. Accuracy of Information: Every effort has been made to ensure that the information contained in this book is accurate, complete, and up to date as of the publication date of 2026. However, conditions, rules, travel logistics, and pricing can change frequently. The author makes no representations or warranties of any kind regarding the completeness, accuracy, or suitability of the information. Readers are strongly encouraged to verify all details independently before planning trips.

2. Safety and Risks: This book contains information about outdoor activities, travel, and adventure in mountain environments. It does not constitute professional mountain safety instruction, medical advice, or legal counsel. Mountain hiking and outdoor trekking carry inherent risks. Readers assume full responsibility for their own safety and decisions.

3. Limitation of Liability: The author and publisher shall not be held liable for any loss, injury, damage, or inconvenience arising from the use of or reliance on any information provided in this publication.

---
"""

        # 3. Build Hierarchical Table of Contents (Chapters + Subsections)
        chapter_tree = []
        current_chapter = None

        for line in content.split("\n"):
            line_s = line.strip()
            if line_s.startswith("## "):
                h_title = line_s[3:].strip()
                if (h_title and h_title.lower() != subtitle.strip().lower() 
                    and not h_title.startswith("#") and not h_title.startswith("![")):
                    current_chapter = {"title": h_title, "subsections": []}
                    chapter_tree.append(current_chapter)
            elif line_s.startswith("### ") and current_chapter is not None:
                sub_title = line_s[4:].strip()
                if sub_title and not sub_title.startswith("#") and "GAPS TO FILL" not in sub_title.upper():
                    current_chapter["subsections"].append(sub_title)

        toc = "### Table of Contents\n\n"
        toc += "- [Copyright Notice](#copyright-notice)\n"
        toc += "- [Disclaimer & Legal Notice](#disclaimer-and-legal-notice)\n"
        if chapter_tree:
            for ch in chapter_tree:
                slug = re.sub(r"[^\w\s-]", "", ch["title"].lower().strip())
                slug = re.sub(r"\s+", "-", slug)
                toc += f"- [{ch['title']}](#{slug})\n"
                for sub in ch["subsections"]:
                    sub_slug = re.sub(r"[^\w\s-]", "", sub.lower().strip())
                    sub_slug = re.sub(r"\s+", "-", sub_slug)
                    toc += f"  - [{sub}](#{sub_slug})\n"
        else:
            toc += "*No chapters defined yet.*\n"
        
        toc += "\n---\n"

        # 4. Process Content: Ensure page breaks
        processed_content = content
        sections = re.split(r"^(##\s+.+)$", processed_content, flags=re.MULTILINE)
        compiled_sections = []
        if sections:
            compiled_sections.append(sections[0])
            
        for i in range(1, len(sections), 2):
            header = sections[i]
            body = sections[i+1] if i+1 < len(sections) else ""
            page_break = '\n<div style="page-break-after: always;"></div>\n\n'
            compiled_sections.append(f"{page_break}{header}{body}")
            
        final_content = "".join(compiled_sections)

        # Assemble the full book
        manuscript = f"{title_page}\n{copyright_page}\n{disclaimer_page}\n{toc}\n{final_content}"
        
        # Save standard markdown
        os.makedirs(output_dir, exist_ok=True)
        clean_title = re.sub(r'[^\w\s-]', '', title).strip()
        clean_title = re.sub(r'[\s-]+', '_', clean_title)
        filepath = os.path.join(output_dir, f"{clean_title}.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(manuscript)

        # Build HTML content generator
        def build_html_document(toc_pages=None, embed_base64=False):
            cover_html = ""
            cover_candidates = [
                os.path.join(output_dir, "images", "cover.png"),
                os.path.join(output_dir, "cover.png"),
                "output/images/cover.png",
                "images/cover.png"
            ]
            cover_found = None
            for c_path in cover_candidates:
                if os.path.exists(c_path):
                    cover_found = c_path
                    break

            if cover_found:
                if embed_base64:
                    import base64
                    with open(cover_found, "rb") as cf:
                        b64_cov = base64.b64encode(cf.read()).decode("utf-8")
                    cover_src = f"data:image/png;base64,{b64_cov}"
                else:
                    cover_src = os.path.relpath(cover_found, output_dir).replace("\\", "/")
                cover_html = f"""
    <div class="page-break cover-page" style="text-align: center; margin: 0; padding: 0;">
        <img src="{cover_src}" alt="{title} Cover" style="width: 100%; height: 9.3in; object-fit: cover; border-radius: 4px;">
    </div>
"""

            body_html = final_content
            body_html = parse_markdown_tables(body_html)
            body_html = parse_markdown_blockquotes(body_html)

            def replace_markdown_image(match):
                caption = match.group(1)
                path = match.group(2)
                if "PHOTO RECOMMENDATION" in caption.upper() or "TODO" in path.upper() or "TODO" in caption.upper():
                    return f"""
<div class="photo-placeholder-box">
    <span class="camera-icon">📷</span>
    <strong>Photo Opportunity</strong>
    <p class="placeholder-caption">{caption.replace("PHOTO RECOMMENDATION:", "").strip()}</p>
</div>
"""
                fname = os.path.basename(path)
                img_candidates = [
                    os.path.join(output_dir, "images", fname),
                    os.path.join(output_dir, fname),
                    path,
                    os.path.join("output", "images", fname),
                    f"images/{fname}"
                ]
                actual_img = None
                for cand in img_candidates:
                    if os.path.exists(cand):
                        actual_img = cand
                        break

                if actual_img:
                    if embed_base64:
                        import base64
                        ext = os.path.splitext(actual_img)[1].lower().lstrip('.')
                        if ext == 'jpg':
                            ext = 'jpeg'
                        with open(actual_img, "rb") as im_f:
                            b64_im = base64.b64encode(im_f.read()).decode("utf-8")
                        img_src = f"data:image/{ext};base64,{b64_im}"
                    else:
                        img_src = os.path.relpath(actual_img, output_dir).replace("\\", "/")
                else:
                    img_src = f"images/{fname}"

                return f"""
<div class="image-container" style="text-align: center; margin: 20px 0; page-break-inside: avoid;">
    <img src="{img_src}" alt="{caption}" style="max-width: 95%; max-height: 5.5in; object-fit: contain; border-radius: 4px;">
    <p class="image-caption" style="font-size: 9.5pt; color: #718096; font-style: italic; margin-top: 6px;">{caption}</p>
</div>
"""
            body_html = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_markdown_image, body_html)

            body_html = re.sub(r"^##\s+(.+)$", r'<h1 class="chapter-title">\1</h1>', body_html, flags=re.MULTILINE)
            body_html = re.sub(r"^###\s+(.+)$", r'<h2 class="section-title">\1</h2>', body_html, flags=re.MULTILINE)
            body_html = re.sub(r"^####\s+(.+)$", r'<h3 class="subsection-title">\1</h3>', body_html, flags=re.MULTILINE)
            body_html = re.sub(r"^#####\s+(.+)$", r'<h4 class="sub-subsection-title">\1</h4>', body_html, flags=re.MULTILINE)
            body_html = re.sub(r"^######\s+(.+)$", r'<h5 class="minor-subtopic">\1</h5>', body_html, flags=re.MULTILINE)
            body_html = re.sub(r"\*\*(.+?)\*\*", r'<strong>\1</strong>', body_html)
            body_html = re.sub(r"\*(.+?)\*", r'<em>\1</em>', body_html)

            paragraphs = body_html.split('\n\n')
            wrapped_paragraphs = []
            for p in paragraphs:
                p = p.strip()
                if not p:
                    continue
                if p.startswith(('<h', '<div', '</div', '<ul', '<li', '---', '<p', '<table', '<tr', '<td', '<th', '<thead>', '<tbody>', '<blockquote', '</blockquote')):
                    wrapped_paragraphs.append(p)
                else:
                    wrapped_paragraphs.append(f"<p>{p}</p>")
            body_html = "\n\n".join(wrapped_paragraphs)

            toc_items = []
            cp_num = toc_pages.get("Copyright Notice", 3) if toc_pages else ""
            dc_num = toc_pages.get("Disclaimer & Legal Notice", 3) if toc_pages else ""
            toc_items.append(f'<li class="toc-chapter"><span class="toc-title">Copyright Notice</span><span class="toc-dots"></span><span class="toc-page">{cp_num}</span></li>')
            toc_items.append(f'<li class="toc-chapter"><span class="toc-title">Disclaimer & Legal Notice</span><span class="toc-dots"></span><span class="toc-page">{dc_num}</span></li>')
            
            for ch in chapter_tree:
                ch_p = toc_pages.get(ch["title"], "") if toc_pages else ""
                toc_items.append(f'<li class="toc-chapter"><span class="toc-title">{ch["title"]}</span><span class="toc-dots"></span><span class="toc-page">{ch_p}</span></li>')
                for sub in ch["subsections"]:
                    sub_p = toc_pages.get(sub, "") if toc_pages else ""
                    # Only show subsections in printed TOC when resolved or in pass 1 preview
                    if sub_p or not toc_pages:
                        toc_items.append(f'<li class="toc-sub"><span class="toc-title">{sub}</span><span class="toc-dots"></span><span class="toc-page">{sub_p}</span></li>')
            toc_html = "\n".join(toc_items)

            return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}: {subtitle}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Aleo:ital,wght@0,300;0,400;0,700;1,400;1,700&family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&display=swap');

        @page {{
            size: 7in 10in;
            margin: 0.75in 0.65in 0.85in 0.65in;
        }}
        body {{
            font-family: 'Inter', Arial, Helvetica, sans-serif;
            line-height: 1.48;
            margin: 0;
            font-size: 10pt;
            color: #1a202c;
            text-align: justify;
            text-justify: inter-word;
        }}
        .page-break {{
            page-break-after: always;
        }}
        .cover-page {{
            page-break-before: avoid;
            page-break-after: always;
        }}
        h1.chapter-title {{
            font-family: 'Aleo', Georgia, 'Times New Roman', serif;
            font-size: 21pt;
            font-weight: 700;
            color: #049294; /* Cyan / Deep Teal */
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-top: 0.4in;
            margin-bottom: 0.25in;
            page-break-before: always;
            border-bottom: 2.5px solid #049294;
            padding-bottom: 0.1in;
        }}
        h2.section-title {{
            font-family: 'Aleo', Georgia, 'Times New Roman', serif;
            font-size: 14pt;
            font-weight: 700;
            color: #1b3a6b; /* Royal Navy */
            text-align: left;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 0.35in;
            margin-bottom: 0.15in;
            page-break-after: avoid;
            border-bottom: 1.5px solid #cc9944; /* Warm Gold / Ochre */
            padding-bottom: 0.05in;
        }}
        h3.subsection-title {{
            font-family: 'Inter', Arial, sans-serif;
            font-size: 11pt;
            font-weight: 700;
            color: #b83280; /* Rich Magenta / Berry accent */
            text-align: left;
            margin-top: 0.25in;
            margin-bottom: 0.1in;
            page-break-after: avoid;
        }}
        h4.sub-subsection-title {{
            font-family: 'Inter', Arial, sans-serif;
            font-size: 10.5pt;
            font-weight: 600;
            color: #2d3748;
            text-align: left;
            margin-top: 0.2in;
            margin-bottom: 0.08in;
            page-break-after: avoid;
        }}
        h5.minor-subtopic {{
            font-family: 'Inter', Arial, sans-serif;
            font-size: 10pt;
            font-weight: 600;
            color: #4a5568;
            text-align: left;
            margin-top: 0.15in;
            margin-bottom: 0.06in;
            page-break-after: avoid;
        }}
        p {{
            margin-top: 0;
            margin-bottom: 0.85em;
        }}
        blockquote.highlight-quote {{
            background-color: #f0fdfa;
            border-left: 4.5px solid #049294;
            margin: 1.2em 0;
            padding: 0.8em 1.2em;
            color: #134e4a;
            page-break-inside: avoid;
            border-radius: 0 5px 5px 0;
        }}
        blockquote.warning-callout {{
            background-color: #fffaf0;
            border-left: 4.5px solid #dd6b20;
            margin: 1.2em 0;
            padding: 0.8em 1.2em;
            color: #744210;
            page-break-inside: avoid;
            border-radius: 0 5px 5px 0;
        }}
        .three-things-box {{
            background-color: #f8fafc;
            border: 1.5px solid #cbd5e0;
            border-top: 4px solid #1b3a6b;
            border-radius: 6px;
            padding: 14px 18px;
            margin: 1.5em 0;
            page-break-inside: avoid;
            color: #1a202c;
        }}
        .three-things-box h3 {{
            margin-top: 0;
            color: #1b3a6b;
            font-family: 'Aleo', Georgia, serif;
            font-size: 12pt;
        }}
        .photo-placeholder-box {{
            background-color: #f8fafc;
            border: 1.5px dashed #cbd5e0;
            padding: 16px;
            margin: 0.3in 0;
            text-align: center;
            border-radius: 6px;
            page-break-inside: avoid;
        }}
        .photo-placeholder-box .camera-icon {{
            font-size: 24pt;
            display: block;
            margin-bottom: 8px;
        }}
        .photo-placeholder-box strong {{
            color: #4a5568;
            font-size: 10.5pt;
            letter-spacing: 1px;
            text-transform: uppercase;
        }}
        .photo-placeholder-box .placeholder-caption {{
            font-size: 9.5pt;
            color: #718096;
            margin-top: 6px;
            font-style: italic;
        }}
        .toc {{
            list-style: none;
            padding: 0;
            margin-top: 25px;
        }}
        .toc-chapter {{
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            margin-top: 14px;
            margin-bottom: 5px;
            font-size: 10.5pt;
            font-weight: bold;
            font-family: 'Aleo', Georgia, serif;
            color: #1b3a6b;
        }}
        .toc-chapter .toc-title {{
            text-transform: uppercase;
            max-width: 82%;
        }}
        .toc-sub {{
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            margin-left: 18px;
            margin-bottom: 5px;
            font-size: 9.5pt;
            color: #4a5568;
        }}
        .toc-sub .toc-title {{
            max-width: 80%;
            font-weight: normal;
        }}
        .toc-dots {{
            flex-grow: 1;
            border-bottom: 1px dotted #cbd5e0;
            margin: 0 8px;
        }}
        .toc-page {{
            font-weight: bold;
            color: #cc9944;
            font-size: 9.5pt;
        }}
        table.kdp-table, table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1.4em 0;
            page-break-inside: avoid;
            font-size: 9.5pt;
        }}
        th, td {{
            border: 1px solid #e2e8f0;
            padding: 8px 10px;
            text-align: left;
        }}
        th {{
            background-color: #1b3a6b;
            color: white;
            font-weight: bold;
            font-family: 'Inter', Arial, sans-serif;
        }}
        tr:nth-child(even) {{
            background-color: #f8fafc;
        }}
    </style>
</head>
<body>
    {cover_html}
    
    <div class="page-break title-page" style="text-align: center; padding-top: 1.2in;">
        <h1 style="font-family: 'Aleo', Georgia, serif; font-size: 26pt; color: #049294; margin-bottom: 0.2in; border: none;">{title}</h1>
        <p style="font-family: 'Aleo', Georgia, serif; font-size: 15pt; color: #cc9944; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.6in;">{subtitle}</p>
        <p style="font-size: 12pt; color: #4a5568;">By <strong>{author}</strong></p>
    </div>

    <div class="page-break copyright" style="padding-top: 1in; font-size: 9.5pt; color: #4a5568;">
        <h3 style="font-family: 'Aleo', Georgia, serif; color: #1b3a6b;">Copyright © 2026 by {author}</h3>
        <p>All rights reserved. No part of this publication may be reproduced, distributed, or transmitted in any form or by any means without the prior written permission of the publisher.</p>
        <p>Published by Author Direct | 2026 Edition</p>
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <h4 style="font-family: 'Aleo', Georgia, serif; color: #1b3a6b;">Disclaimer & Legal Notice</h4>
        <p>This field guide is for informational purposes only. Readers assume full responsibility for route selection, gear, weather precautions, and travel safety.</p>
    </div>

    <div class="page-break">
        <h2 style="font-family: 'Aleo', Georgia, serif; color: #049294; text-align: center; border: none; font-size: 20pt; margin-bottom: 25px; text-transform: uppercase; letter-spacing: 1px;">TABLE OF CONTENTS</h2>
        <ul class="toc">
            {toc_html}
        </ul>
    </div>

    <div class="book-content">
        {body_html}
    </div>
</body>
</html>
"""

        # Write Pass 1 HTML
        html_filepath = os.path.join(output_dir, f"{clean_title}.html")
        pass1_html = build_html_document(toc_pages=None, embed_base64=False)
        with open(html_filepath, "w", encoding="utf-8") as f:
            f.write(pass1_html)

        # Generate PDF version using headless Microsoft Edge
        pdf_filepath = os.path.join(output_dir, f"{clean_title}.pdf")
        edge_exe = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        pdf_status = ""
        
        if os.path.exists(edge_exe):
            html_abs = os.path.abspath(html_filepath)
            pdf_abs = os.path.abspath(pdf_filepath)
            try:
                import tempfile
                base_flags = [
                    edge_exe,
                    "--headless",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-extensions",
                    "--disable-background-networking",
                    "--disable-default-apps",
                    "--no-pdf-header-footer",
                ]

                def run_edge_print(cmd, target_pdf, timeout=60):
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    start_t = time.time()
                    last_size = -1
                    stable_count = 0
                    while time.time() - start_t < timeout:
                        ret = proc.poll()
                        if ret is not None:
                            return ret
                        if os.path.exists(target_pdf):
                            cur_size = os.path.getsize(target_pdf)
                            if cur_size > 10000:
                                if cur_size == last_size:
                                    stable_count += 1
                                    if stable_count >= 2:
                                        time.sleep(1)
                                        try:
                                            proc.terminate()
                                            proc.wait(timeout=3)
                                        except Exception:
                                            proc.kill()
                                        return 0
                                else:
                                    stable_count = 0
                                    last_size = cur_size
                        time.sleep(1)
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    return 0

                # Pass 1: Render layout to discover page targets
                with tempfile.TemporaryDirectory() as temp_dir_1:
                    cmd1 = base_flags + [f"--user-data-dir={temp_dir_1}", f"--print-to-pdf={pdf_abs}", html_abs]
                    run_edge_print(cmd1, pdf_abs, timeout=60)

                # Discover page numbers with PyMuPDF
                doc = pymupdf.open(pdf_abs)
                heading_pages = {"Copyright Notice": 3, "Disclaimer & Legal Notice": 3}
                for pno in range(3, len(doc)):
                    page = doc[pno]
                    blocks = page.get_text("dict")["blocks"]
                    for b in blocks:
                        if "lines" in b:
                            block_text = " ".join(" ".join(s["text"] for s in l["spans"]) for l in b["lines"])
                            b_clean = re.sub(r'\W+', '', block_text).upper()
                            first_span = b["lines"][0]["spans"][0]
                            font_size = first_span["size"]
                            # Check Level 1 (Chapters)
                            if font_size >= 12.5:
                                for ch in chapter_tree:
                                    ch_clean = re.sub(r'\W+', '', ch["title"]).upper()
                                    if ch_clean[:18] in b_clean and ch["title"] not in heading_pages:
                                        heading_pages[ch["title"]] = pno + 1
                            # Check Level 2 (Subsections)
                            elif 8.8 <= font_size < 12.5:
                                for ch in chapter_tree:
                                    for sub in ch["subsections"]:
                                        sub_clean = re.sub(r'\W+', '', sub).upper()
                                        if sub_clean[:18] in b_clean and sub not in heading_pages:
                                            heading_pages[sub] = pno + 1
                doc.close()

                # Pass 2: Re-generate HTML with exact page numbers in TOC
                pass2_html = build_html_document(toc_pages=heading_pages, embed_base64=False)
                with open(html_filepath, "w", encoding="utf-8") as f:
                    f.write(pass2_html)

                # Re-render final PDF
                with tempfile.TemporaryDirectory() as temp_dir_2:
                    cmd2 = base_flags + [f"--user-data-dir={temp_dir_2}", f"--print-to-pdf={pdf_abs}", html_abs]
                    run_edge_print(cmd2, pdf_abs, timeout=60)

                # Post-process with PyMuPDF: Stamp page numbers & inject bookmark outline
                doc_final = pymupdf.open(pdf_abs)
                for i, page in enumerate(doc_final):
                    page_num = i + 1
                    rect = page.rect
                    if i > 0:  # Skip cover page
                        p_text = str(page_num)
                        text_w = pymupdf.get_text_length(p_text, fontname="helv", fontsize=9)
                        pt = pymupdf.Point((rect.width - text_w) / 2, rect.height - 35)
                        page.insert_text(pt, p_text, fontname="helv", fontsize=9, color=(0.4, 0.4, 0.4))

                # Build hierarchical bookmarks (Level 1 Chapters, Level 2 Subsections)
                toc_tree = [
                    [1, "Front Matter: Copyright & Disclaimer", 3],
                    [1, "Table of Contents", 4]
                ]
                for ch in chapter_tree:
                    ch_title = ch["title"]
                    if ch_title in heading_pages:
                        toc_tree.append([1, ch_title, heading_pages[ch_title]])
                        for sub in ch["subsections"]:
                            if sub in heading_pages:
                                toc_tree.append([2, sub, heading_pages[sub]])

                doc_final.set_toc(toc_tree)
                final_page_count = len(doc_final)
                temp_pdf = pdf_abs + ".tmp"
                doc_final.save(temp_pdf, deflate=True, garbage=4)
                doc_final.close()
                if os.path.exists(pdf_abs):
                    os.remove(pdf_abs)
                os.replace(temp_pdf, pdf_abs)

                # Save final standalone HTML with base64 embedded images so it remains self-contained after raw images are cleaned up
                final_standalone_html = build_html_document(toc_pages=heading_pages, embed_base64=True)
                with open(html_filepath, "w", encoding="utf-8") as f:
                    f.write(final_standalone_html)

                if os.path.exists(pdf_filepath) and os.path.getsize(pdf_filepath) > 0:
                    pdf_status = f"\n- Saved PDF: {pdf_filepath} (7x10 trim, {final_page_count} pages, bookmarks included)"
                else:
                    pdf_status = "\n- PDF Generation Failed: Output file was empty."
            except Exception as e:
                pdf_status = f"\n- PDF Generation Failed: {str(e)}"
        else:
            pdf_status = "\n- PDF Generation Skipped: Microsoft Edge executable not found."

        # Generate editable Word (.docx) manuscript
        docx_status = ""
        try:
            docx_path = format_kdp_docx(title, subtitle, content, author, output_dir=output_dir)
            if docx_path and os.path.exists(docx_path):
                docx_status = f"\n- Saved DOCX: {docx_path} (Editable Word format, 7x10 trim)"
        except Exception as de:
            docx_status = f"\n- DOCX Generation Skipped: {str(de)}"

        return f"Manuscript successfully formatted for KDP.\n- Saved Markdown: {filepath}\n- Saved HTML: {html_filepath}{docx_status}{pdf_status}"
    except Exception as e:
        return f"Formatting failed: {str(e)}"
