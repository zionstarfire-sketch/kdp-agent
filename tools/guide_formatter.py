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
    """Helper to parse multi-line blockquotes into styled HTML callouts matching exemplar PDF standards."""
    lines = text.split('\n')
    in_bq = False
    bq_lines = []
    new_lines = []
    
    def render_bq(lines):
        if not lines:
            return ""
        header_text = ""
        body_parts = []
        for l in lines:
            l_s = l.strip()
            if l_s.startswith("### "):
                header_text = l_s[4:].strip()
            elif l_s.startswith("## "):
                header_text = l_s[3:].strip()
            elif l_s.startswith("**") and l_s.endswith("**") and len(l_s) > 4:
                header_text = l_s.strip("*").strip()
            else:
                body_parts.append(l)
                
        h_upper = header_text.upper()
        box_class = "callout-box"
        if "MYTH" in h_upper or "BUSTED" in h_upper:
            box_class += " callout-myths"
        elif "DOS & DON'TS" in h_upper or "DOS AND DON'TS" in h_upper or "DO'S & DON'TS" in h_upper:
            box_class += " callout-dos-donts"
        elif "FIRST-TIMER" in h_upper or "RECOMMENDATION" in h_upper:
            box_class += " callout-first-timer"
        elif "CHECKLIST" in h_upper or "ESSENTIALS" in h_upper:
            box_class += " callout-checklist"
        elif "ACCESSIBILITY" in h_upper:
            box_class += " callout-accessibility"

        body_html = "<br>\n".join(body_parts) if body_parts else "<br>\n".join(lines)
        if header_text:
            return f'<div class="{box_class}"><div class="callout-header">{header_text.upper()}</div><div class="callout-body">{body_html}</div></div>'
        else:
            return f'<div class="{box_class}"><div class="callout-body">{body_html}</div></div>'

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

        # Enforce Section terminology across manuscript
        content = re.sub(r'\bPart\s+(\d+|[IVX]+)\b', r'Section \1', content, flags=re.IGNORECASE)
        content = re.sub(r'\bPART\s+(\d+|[IVX]+)\b', r'SECTION \1', content)

        doc = docx.Document()

        # Set default styles for Word & Google Docs
        styles = doc.styles
        normal_style = styles['Normal']
        normal_style.font.name = "Arial"
        normal_style.font.size = Pt(11.5)
        normal_style.font.color.rgb = RGBColor(0, 0, 0)
        normal_style.paragraph_format.line_spacing = 1.15
        normal_style.paragraph_format.space_before = Pt(4)
        normal_style.paragraph_format.space_after = Pt(0)
        normal_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        if 'Heading 1' in styles:
            h1_style = styles['Heading 1']
            h1_style.font.name = "Arial"
            h1_style.font.size = Pt(48)
            h1_style.font.bold = True
            h1_style.font.color.rgb = RGBColor(27, 58, 107)  # #1B3A6B
            h1_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            h1_style.paragraph_format.space_before = Pt(28)
            h1_style.paragraph_format.space_after = Pt(6)

        if 'Heading 2' in styles:
            h2_style = styles['Heading 2']
            h2_style.font.name = "Arial"
            h2_style.font.size = Pt(18)
            h2_style.font.bold = True
            h2_style.font.color.rgb = RGBColor(224, 27, 132)  # #E01B84
            h2_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
            h2_style.paragraph_format.space_before = Pt(18)
            h2_style.paragraph_format.space_after = Pt(6)

        section = doc.sections[0]
        # Executive 7" x 10" Trim Size with Template Margins (Top: 0.5", Bottom: 1.0", Left: 0.5", Right: 0.5")
        section.page_width = Inches(7.0)
        section.page_height = Inches(10.0)
        section.top_margin = Inches(0.5)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(0.5)
        section.right_margin = Inches(0.5)

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
                    run.add_picture(c_path, width=Inches(5.8))
                    doc.add_page_break()
                except Exception:
                    pass
                break

        # Helper to parse inline markdown runs
        def add_markdown_runs(paragraph, text, base_font="Arial", base_size=Pt(11.5), base_color=RGBColor(0, 0, 0), bold_override=False, italic_override=False):
            tokens = re.split(r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*)', text)
            for token in tokens:
                if not token:
                    continue
                run = paragraph.add_run()
                run.font.name = base_font
                run.font.size = base_size
                run.font.color.rgb = base_color
                
                if token.startswith('***') and token.endswith('***') and len(token) >= 6:
                    run.text = token[3:-3]
                    run.bold = True
                    run.italic = True
                elif token.startswith('**') and token.endswith('**') and len(token) >= 4:
                    run.text = token[2:-2]
                    run.bold = True
                elif token.startswith('*') and token.endswith('*') and len(token) >= 2:
                    run.text = token[1:-1]
                    run.italic = True
                else:
                    run.text = token
                    if bold_override:
                        run.bold = True
                    if italic_override:
                        run.italic = True

        # 2. Title Page (Arial Typography System)
        tp = doc.add_paragraph()
        tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        tp.paragraph_format.space_before = Pt(40)
        tp.paragraph_format.space_after = Pt(14)
        t_run = tp.add_run(title.title())
        t_run.font.name = "Arial"
        t_run.font.size = Pt(36)
        t_run.font.bold = True
        t_run.font.color.rgb = RGBColor(27, 58, 107)  # #1B3A6B

        sp = doc.add_paragraph()
        sp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        sp.paragraph_format.space_after = Pt(28)
        s_run = sp.add_run(subtitle.upper())
        s_run.font.name = "Arial"
        s_run.font.size = Pt(24)
        s_run.font.bold = True
        s_run.font.color.rgb = RGBColor(204, 153, 68)  # #CC9944

        ap = doc.add_paragraph()
        ap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        a_run = ap.add_run(f"By {author}")
        a_run.font.name = "Arial"
        a_run.font.size = Pt(12)
        a_run.font.color.rgb = RGBColor(85, 85, 85)

        doc.add_page_break()

        # 3. Copyright & Legal Disclaimer
        c_head = doc.add_paragraph()
        c_head.paragraph_format.space_before = Pt(30)
        c_head.paragraph_format.space_after = Pt(6)
        c_run = c_head.add_run(f"Copyright © 2026 by {author}")
        c_run.font.name = "Arial"
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
        c_body_run.font.name = "Arial"
        c_body_run.font.size = Pt(10)
        c_body_run.font.color.rgb = RGBColor(60, 60, 60)

        d_head = doc.add_paragraph()
        d_head.paragraph_format.space_before = Pt(16)
        d_head.paragraph_format.space_after = Pt(6)
        d_run = d_head.add_run("Disclaimer & Legal Notice")
        d_run.font.name = "Arial"
        d_run.font.size = Pt(14)
        d_run.font.bold = True
        d_run.font.color.rgb = RGBColor(27, 58, 107)

        d_body = doc.add_paragraph()
        d_body_run = d_body.add_run(
            "This field guide is intended for informational and personal planning purposes only. "
            "Readers assume full responsibility for their own safety, route choices, transit ticketing, "
            "and health precautions. Prices, operating hours, and local regulations are subject to change."
        )
        d_body_run.font.name = "Arial"
        d_body_run.font.size = Pt(10)
        d_body_run.font.color.rgb = RGBColor(60, 60, 60)

        doc.add_page_break()

        # 4. Table of Contents
        toc_p = doc.add_paragraph()
        toc_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        toc_p.paragraph_format.space_after = Pt(18)
        toc_run = toc_p.add_run("TABLE OF CONTENTS")
        toc_run.font.name = "Arial"
        toc_run.font.size = Pt(18)
        toc_run.font.bold = True
        toc_run.font.color.rgb = RGBColor(27, 58, 107)

        raw_chapters = re.split(r'(^##\s+.*$)', content, flags=re.MULTILINE)
        page_tracker = 5
        for i in range(1, len(raw_chapters), 2):
            ch_line = raw_chapters[i].replace("##", "").strip()
            item_p = doc.add_paragraph()
            item_p.paragraph_format.space_before = Pt(3)
            item_p.paragraph_format.space_after = Pt(3)
            
            dots = " " + ("." * max(8, 46 - len(ch_line))) + " "
            
            ch_run = item_p.add_run(ch_line.upper())
            ch_run.font.name = "Arial"
            ch_run.font.size = Pt(11)
            ch_run.font.bold = True
            ch_run.font.color.rgb = RGBColor(0, 0, 0)
            
            d_run = item_p.add_run(dots)
            d_run.font.name = "Arial"
            d_run.font.size = Pt(10)
            d_run.font.color.rgb = RGBColor(140, 140, 140)
            
            p_run = item_p.add_run(str(page_tracker))
            p_run.font.name = "Arial"
            p_run.font.size = Pt(11)
            p_run.font.bold = True
            p_run.font.color.rgb = RGBColor(0, 0, 0)
            page_tracker += 10

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
                            p.runs[0].font.name = "Arial"
                            p.runs[0].font.bold = True
                            p.runs[0].font.size = Pt(10)
                            p.runs[0].font.color.rgb = RGBColor(255, 255, 255)
                            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="1B3A6B"/>')
                            cell._tc.get_or_add_tcPr().append(shd)
                        else:
                            if r_idx % 2 == 1:
                                shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="EBF3FB"/>')
                                cell._tc.get_or_add_tcPr().append(shd)
                            if p.runs:
                                p.runs[0].font.name = "Arial"
                                p.runs[0].font.size = Pt(9.5)
                                p.runs[0].font.color.rgb = RGBColor(30, 30, 30)
            table_lines = []
            in_table = False

        def flush_blockquote():
            nonlocal bq_lines, in_blockquote
            if not bq_lines:
                return
            full_bq = "\n".join(bq_lines)
            
            # Identify box category from header
            h_text = ""
            for l in bq_lines:
                ls = l.strip()
                if ls.startswith("### ") or ls.startswith("## ") or (ls.startswith("**") and ls.endswith("**")):
                    h_text = ls.strip("#* ").upper()
                    break

            border_hex = "1B3A6B" # Midnight Navy default
            header_rgb = RGBColor(27, 58, 107)
            bg_hex = "F8FAFC"

            if "MYTH" in h_text or "BUSTED" in h_text:
                border_hex = "C04A26" # Rust Orange
                header_rgb = RGBColor(192, 74, 38)
                bg_hex = "FFFFFF"
            elif "DOS & DON'TS" in h_text or "DOS AND DON'TS" in h_text or "DO'S & DON'TS" in h_text:
                border_hex = "4B6B94" # Slate Blue
                header_rgb = RGBColor(27, 58, 107)
                bg_hex = "F8FAFC"
            elif "FIRST-TIMER" in h_text or "RECOMMENDATION" in h_text:
                border_hex = "2D7D46" # Forest Green
                header_rgb = RGBColor(45, 125, 70)
                bg_hex = "FFFFFF"
            elif "CHECKLIST" in h_text or "ESSENTIALS" in h_text:
                border_hex = "4A2E80" # Deep Purple
                header_rgb = RGBColor(74, 46, 128)
                bg_hex = "FFFFFF"
            elif "ACCESSIBILITY" in h_text:
                border_hex = "A1346C" # Berry Magenta
                header_rgb = RGBColor(161, 52, 108)
                bg_hex = "FFFFFF"

            box_table = doc.add_table(rows=1, cols=1)
            box_table.alignment = WD_TABLE_ALIGNMENT.CENTER
            cell = box_table.cell(0, 0)
            cell.width = Inches(5.8)
            
            shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{bg_hex}"/>')
            tcBorders = parse_xml(
                f'<w:tcBorders {nsdecls("w")}>\n'
                f'  <w:left w:val="single" w:sz="16" w:space="0" w:color="{border_hex}"/>\n'
                f'  <w:top w:val="single" w:sz="16" w:space="0" w:color="{border_hex}"/>\n'
                f'  <w:right w:val="single" w:sz="16" w:space="0" w:color="{border_hex}"/>\n'
                f'  <w:bottom w:val="single" w:sz="16" w:space="0" w:color="{border_hex}"/>\n'
                f'</w:tcBorders>'
            )
            tcPr = cell._tc.get_or_add_tcPr()
            tcPr.append(shd)
            tcPr.append(tcBorders)
            
            lines_in_bq = full_bq.split("\n")
            for idx_bq, bq_l in enumerate(lines_in_bq):
                bql_strip = bq_l.strip()
                if not bql_strip:
                    continue
                cp = cell.paragraphs[0] if idx_bq == 0 else cell.add_paragraph()
                cp.paragraph_format.space_before = Pt(2)
                cp.paragraph_format.space_after = Pt(2)
                cp.paragraph_format.line_spacing = 1.15
                
                if bql_strip.startswith("### ") or bql_strip.startswith("## "):
                    t_text = bql_strip.lstrip("#").strip().upper()
                    r = cp.add_run(t_text)
                    r.font.name = "Arial"
                    r.font.size = Pt(12)
                    r.font.bold = True
                    r.font.color.rgb = header_rgb
                else:
                    cp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                    add_markdown_runs(cp, bql_strip, base_font="Arial", base_size=Pt(11), base_color=RGBColor(0, 0, 0))

            bq_lines = []
            in_blockquote = False

        is_first_chapter = True
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

            # Skip raw HTML tags and horizontal dividers
            if stripped.startswith(("<div", "</div", "<br", "<p", "</p", "<!--")) or stripped == "---":
                continue

            # CHAPTER HEADINGS - Heading Style: Heading 1, Font size: 48, ALL CAPITAL LETTERS, Color: #1B3A6B, Bold Text, Center
            # CHAPTER SUBHEADINGS - Heading Style: Normal text, Font size: 24, ALL CAPITAL LETTERS, Color: #CC9944, Bold Text, Center
            if stripped.startswith("## "):
                if not is_first_chapter:
                    doc.add_page_break()
                is_first_chapter = False
                ch_raw = stripped[3:].strip()
                main_title = ""
                sub_title = ""

                # Match Chapter X: Subtitle
                m_ch = re.match(r'^(?:CHAPTER|Chapter)\s+([\dIVX]+)\s*(?:[:—\-]\s*|\s+)(.*)$', ch_raw, re.IGNORECASE)
                if m_ch:
                    main_title = f"CHAPTER {m_ch.group(1)}".upper()
                    sub_title = m_ch.group(2).strip().upper()
                elif re.match(r'^(?:BEFORE YOU GO|INTRODUCTION)\b', ch_raw, re.IGNORECASE):
                    main_title = "INTRODUCTION"
                    sub_title = re.sub(r'^(?:BEFORE YOU GO|INTRODUCTION)\s*[:—\-]\s*', '', ch_raw, flags=re.I).strip().upper()
                elif re.match(r'^(?:BEFORE YOU FLY HOME|CONCLUSION)\b', ch_raw, re.IGNORECASE):
                    main_title = "CONCLUSION"
                    sub_title = re.sub(r'^(?:BEFORE YOU FLY HOME|CONCLUSION)\s*[:—\-]\s*', '', ch_raw, flags=re.I).strip().upper()
                elif " — " in ch_raw:
                    parts = ch_raw.split(" — ", 1)
                    main_title = parts[0].strip().upper()
                    sub_title = parts[1].strip().upper()
                elif " - " in ch_raw:
                    parts = ch_raw.split(" - ", 1)
                    main_title = parts[0].strip().upper()
                    sub_title = parts[1].strip().upper()
                elif ":" in ch_raw:
                    parts = [p.strip() for p in ch_raw.split(":") if p.strip()]
                    if len(parts) >= 2:
                        main_title = parts[0].upper()
                        sub_title = ": ".join(parts[1:]).upper()
                    else:
                        main_title = ch_raw.upper()
                        sub_title = ""
                else:
                    main_title = ch_raw.upper()
                    sub_title = ""

                h1_p = doc.add_paragraph(style='Heading 1')
                h1_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                h1_p.paragraph_format.space_before = Pt(32)
                h1_p.paragraph_format.space_after = Pt(4 if sub_title else 16)
                h1_run = h1_p.add_run(main_title)
                h1_run.font.name = "Arial"
                h1_run.font.size = Pt(48)
                h1_run.font.bold = True
                h1_run.font.color.rgb = RGBColor(27, 58, 107)  # #1B3A6B

                if sub_title:
                    sub_p = doc.add_paragraph(style='Normal')
                    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    sub_p.paragraph_format.space_before = Pt(4)
                    sub_p.paragraph_format.space_after = Pt(18)
                    sub_run = sub_p.add_run(sub_title)
                    sub_run.font.name = "Arial"
                    sub_run.font.size = Pt(24)
                    sub_run.font.bold = True
                    sub_run.font.color.rgb = RGBColor(204, 153, 68)  # #CC9944
                continue

            # SECTION HEADINGS - Heading Style: Heading 2, Font size: 18, Uppercase, Color: #E01B84, Bold Text, Center
            if stripped.startswith("### "):
                sec_title = stripped[4:].strip()
                h2_p = doc.add_paragraph(style='Heading 2')
                h2_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                h2_p.paragraph_format.space_before = Pt(18)
                h2_p.paragraph_format.space_after = Pt(6)
                h2_run = h2_p.add_run(sec_title.upper())
                h2_run.font.name = "Arial"
                h2_run.font.size = Pt(18)
                h2_run.font.bold = True
                h2_run.font.color.rgb = RGBColor(224, 27, 132)  # #E01B84
                continue

            # SECTION SUBHEADINGS - Heading Style: Normal text, Font size: 16, Title Case, Color: #000B50, Bold Text, Left
            if stripped.startswith("#### "):
                sub_title = stripped[5:].strip()
                h3_p = doc.add_paragraph(style='Normal')
                h3_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                h3_p.paragraph_format.space_before = Pt(14)
                h3_p.paragraph_format.space_after = Pt(4)
                h3_run = h3_p.add_run(sub_title.title())
                h3_run.font.name = "Arial"
                h3_run.font.size = Pt(16)
                h3_run.font.bold = True
                h3_run.font.color.rgb = RGBColor(0, 11, 80)  # #000B50
                continue

            # Heading 4 (Sub-Subsection)
            if stripped.startswith("##### "):
                sub4_title = stripped[6:].strip()
                h4_p = doc.add_paragraph(style='Normal')
                h4_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                h4_p.paragraph_format.space_before = Pt(10)
                h4_p.paragraph_format.space_after = Pt(3)
                h4_run = h4_p.add_run(sub4_title.title())
                h4_run.font.name = "Arial"
                h4_run.font.size = Pt(14)
                h4_run.font.bold = True
                h4_run.font.color.rgb = RGBColor(0, 11, 80)
                continue

            # Heading 5 (Minor Subtopic)
            if stripped.startswith("###### "):
                sub5_title = stripped[7:].strip()
                h5_p = doc.add_paragraph(style='Normal')
                h5_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                h5_p.paragraph_format.space_before = Pt(8)
                h5_p.paragraph_format.space_after = Pt(2)
                h5_run = h5_p.add_run(sub5_title.title())
                h5_run.font.name = "Arial"
                h5_run.font.size = Pt(12)
                h5_run.font.bold = True
                h5_run.font.color.rgb = RGBColor(27, 58, 107)
                continue

            # Check for Figure or Map visual description card (3-4 per chapter)
            fig_m = re.match(r'^(?:Figure|Map|FIGURE|MAP)\s+([\dIVX\w\.]+)\s*(?:—|:|-)\s*(.*?)(?::|\s*—|\s*-\s*|\s*\|\s*)(.+)$', stripped)
            if not fig_m:
                fig_m = re.match(r'^(?:Figure|Map|FIGURE|MAP)\s+([\dIVX\w\.]+)\s*(?:—|:|-)\s*(.+)$', stripped)

            if fig_m:
                if in_blockquote:
                    flush_blockquote()
                if in_table:
                    flush_table()

                is_map = stripped.lower().startswith("map")
                fig_label = fig_m.group(1).strip()
                if len(fig_m.groups()) >= 3 and fig_m.group(3):
                    fig_title = fig_m.group(2).strip()
                    fig_desc = fig_m.group(3).strip()
                else:
                    fig_title = "Route & Area Map" if is_map else "Documentary Scene"
                    fig_desc = fig_m.group(2).strip()

                fig_table = doc.add_table(rows=1, cols=1)
                fig_table.alignment = WD_TABLE_ALIGNMENT.CENTER
                f_cell = fig_table.cell(0, 0)
                f_cell.width = Inches(5.8)

                f_shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F8FAFC"/>')
                f_borders = parse_xml(
                    f'<w:tcBorders {nsdecls("w")}>\n'
                    f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="1B3A6B"/>\n'
                    f'  <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E0"/>\n'
                    f'  <w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E0"/>\n'
                    f'  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E0"/>\n'
                    f'</w:tcBorders>'
                )
                f_tcPr = f_cell._tc.get_or_add_tcPr()
                f_tcPr.append(f_shd)
                f_tcPr.append(f_borders)

                prefix = "🗺️ MAP" if is_map else "📷 FIGURE"
                fp1 = f_cell.paragraphs[0]
                fp1.alignment = WD_ALIGN_PARAGRAPH.LEFT
                fp1.paragraph_format.space_before = Pt(4)
                fp1.paragraph_format.space_after = Pt(2)
                fr1 = fp1.add_run(f"{prefix} {fig_label.upper()} — {fig_title.upper()}")
                fr1.font.name = "Arial"
                fr1.font.size = Pt(10.5)
                fr1.font.bold = True
                fr1.font.color.rgb = RGBColor(27, 58, 107)

                fp_badge = f_cell.add_paragraph()
                fp_badge.alignment = WD_ALIGN_PARAGRAPH.LEFT
                fp_badge.paragraph_format.space_before = Pt(0)
                fp_badge.paragraph_format.space_after = Pt(4)
                fr_badge = fp_badge.add_run("VISUAL ART BRIEF / PHOTO SPECIFICATION")
                fr_badge.font.name = "Arial"
                fr_badge.font.size = Pt(8.5)
                fr_badge.font.bold = True
                fr_badge.font.color.rgb = RGBColor(204, 153, 68)

                fp2 = f_cell.add_paragraph()
                fp2.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
                fp2.paragraph_format.space_before = Pt(2)
                fp2.paragraph_format.space_after = Pt(4)
                fp2.paragraph_format.line_spacing = 1.15
                fr2 = fp2.add_run(fig_desc)
                fr2.font.name = "Arial"
                fr2.font.size = Pt(9.5)
                fr2.font.italic = True
                fr2.font.color.rgb = RGBColor(74, 85, 104)
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
                        run.add_picture(actual_img, width=Inches(5.5))
                    except Exception:
                        pass

                cap_p = doc.add_paragraph()
                cap_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                cap_p.paragraph_format.space_after = Pt(10)
                cap_run = cap_p.add_run(caption)
                cap_run.font.name = "Arial"
                cap_run.font.italic = True
                cap_run.font.size = Pt(9)
                cap_run.font.color.rgb = RGBColor(100, 100, 100)
                continue

            # Bullet List
            if stripped.startswith(("- ", "* ", "• ")):
                bullet_text = re.sub(r'^[-*•]\s*', '', stripped)
                bp = doc.add_paragraph(style='List Bullet')
                bp.alignment = WD_ALIGN_PARAGRAPH.LEFT
                bp.paragraph_format.line_spacing = 1.15
                bp.paragraph_format.space_before = Pt(2)
                bp.paragraph_format.space_after = Pt(0)
                add_markdown_runs(bp, bullet_text, base_font="Arial", base_size=Pt(11.5), base_color=RGBColor(0, 0, 0))
                continue

            # BODY TEXT: Heading Style: Normal text, Font size: 11.5, Text: Sentence/Prose, Color: #000000, Line Spacing: 1.15, Add space before paragraph, Remove space after paragraph, Text Alignment: Justify
            p = doc.add_paragraph(style='Normal')
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            p.paragraph_format.line_spacing = 1.15
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(0)
            add_markdown_runs(p, stripped, base_font="Arial", base_size=Pt(11.5), base_color=RGBColor(0, 0, 0))

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
    # Enforce Section terminology across manuscript
    content = re.sub(r'\bPart\s+(\d+|[IVX]+)\b', r'Section \1', content, flags=re.IGNORECASE)
    content = re.sub(r'\bPART\s+(\d+|[IVX]+)\b', r'SECTION \1', content)
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

        # 4. Process Content: Clean markdown without duplicate page-break wrappers
        # (h1.chapter-title has page-break-before: always in CSS; no extra divs needed)
        cleaned_content = re.sub(r'<div style="page-break-[^>]+></div>', '', content)
        final_content = cleaned_content.strip()

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
            def replace_figure_line(match):
                prefix_type = "MAP" if match.group(0).lower().startswith("map") else "FIGURE"
                icon = "🗺️" if prefix_type == "MAP" else "📷"
                fig_num = match.group(1).strip()
                fig_title = match.group(2).strip()
                fig_desc = match.group(3).strip() if match.group(3) else fig_title
                return f'''
<div class="figure-card">
    <div class="figure-card-header">
        <span class="camera-icon">{icon}</span>
        <span class="figure-title">{prefix_type} {fig_num.upper()} — {fig_title.upper()}</span>
    </div>
    <div class="figure-card-badge">VISUAL ART BRIEF / PHOTO SPECIFICATION</div>
    <p class="figure-card-desc">{fig_desc}</p>
</div>
'''

            body_html = re.sub(
                r'^(?:Figure|Map|FIGURE|MAP)\s+([\dIVX\w\.]+)\s*(?:—|:|-)\s*(.*?)(?::|\s*—|\s*-\s*|\s*\|\s*)(.+)$',
                replace_figure_line,
                body_html,
                flags=re.MULTILINE
            )
            body_html = re.sub(r'!\[(.*?)\]\((.*?)\)', replace_markdown_image, body_html)

            def replace_chapter_header(match):
                ch_raw = match.group(1).strip()
                main_title = ""
                sub_title = ""

                m_ch = re.match(r'^(?:CHAPTER|Chapter)\s+([\dIVX]+)\s*(?:[:—\-]\s*|\s+)(.*)$', ch_raw, re.IGNORECASE)
                if m_ch:
                    main_title = f"CHAPTER {m_ch.group(1)}".upper()
                    sub_title = m_ch.group(2).strip().upper()
                elif re.match(r'^(?:BEFORE YOU GO|INTRODUCTION)\b', ch_raw, re.IGNORECASE):
                    main_title = "INTRODUCTION"
                    sub_title = re.sub(r'^(?:BEFORE YOU GO|INTRODUCTION)\s*[:—\-]\s*', '', ch_raw, flags=re.I).strip().upper()
                elif re.match(r'^(?:BEFORE YOU FLY HOME|CONCLUSION)\b', ch_raw, re.IGNORECASE):
                    main_title = "CONCLUSION"
                    sub_title = re.sub(r'^(?:BEFORE YOU FLY HOME|CONCLUSION)\s*[:—\-]\s*', '', ch_raw, flags=re.I).strip().upper()
                elif " — " in ch_raw:
                    parts = ch_raw.split(" — ", 1)
                    main_title = parts[0].strip().upper()
                    sub_title = parts[1].strip().upper()
                elif " - " in ch_raw:
                    parts = ch_raw.split(" - ", 1)
                    main_title = parts[0].strip().upper()
                    sub_title = parts[1].strip().upper()
                elif ":" in ch_raw:
                    parts = [p.strip() for p in ch_raw.split(":") if p.strip()]
                    if len(parts) >= 2:
                        main_title = parts[0].upper()
                        sub_title = ": ".join(parts[1:]).upper()
                    else:
                        main_title = ch_raw.upper()
                        sub_title = ""
                else:
                    main_title = ch_raw.upper()
                    sub_title = ""
                
                out = f'<h1 class="chapter-title">{main_title}</h1>'
                if sub_title:
                    out += f'\n<div class="chapter-subheading">{sub_title}</div>'
                return out

            body_html = re.sub(r"^##\s+(.+)$", replace_chapter_header, body_html, flags=re.MULTILINE)
            body_html = re.sub(r"^###\s+(.+)$", lambda m: f'<h2 class="section-title">{m.group(1).strip().upper()}</h2>', body_html, flags=re.MULTILINE)
            body_html = re.sub(r"^####\s+(.+)$", lambda m: f'<h3 class="subsection-title">{m.group(1).strip().title()}</h3>', body_html, flags=re.MULTILINE)
            body_html = re.sub(r"^#####\s+(.+)$", lambda m: f'<h4 class="sub-subsection-title">{m.group(1).strip().title()}</h4>', body_html, flags=re.MULTILINE)
            body_html = re.sub(r"^######\s+(.+)$", lambda m: f'<h5 class="minor-subtopic">{m.group(1).strip().title()}</h5>', body_html, flags=re.MULTILINE)
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
            toc_html = "\n".join(toc_items)

            return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}: {subtitle}</title>
    <style>
        @page {{
            size: 7in 10in;
            margin: 0.5in 0.5in 1.0in 0.5in;
        }}
        body {{
            font-family: Arial, Helvetica, sans-serif;
            line-height: 1.25;
            margin: 0;
            font-size: 11pt;
            color: #000000;
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
            font-family: Arial, sans-serif;
            font-size: 48pt;
            font-weight: 700;
            color: #1B3A6B;
            text-align: center;
            letter-spacing: 1px;
            text-transform: uppercase;
            margin-top: 0.35in;
            margin-bottom: 0.08in;
            page-break-before: always;
            border-bottom: 2.5px solid #1B3A6B;
            padding-bottom: 0.08in;
        }}
        .chapter-subheading {{
            font-family: Arial, sans-serif;
            font-size: 24pt;
            font-weight: 700;
            color: #CC9944;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-top: 0.06in;
            margin-bottom: 0.28in;
            page-break-after: avoid;
        }}
        h2.section-title {{
            font-family: Arial, sans-serif;
            font-size: 18pt;
            font-weight: 700;
            color: #E01B84; /* #E01B84 */
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            margin-top: 0.3in;
            margin-bottom: 0.12in;
            page-break-after: avoid;
            border-bottom: 1.5px solid #E01B84;
            padding-bottom: 0.04in;
        }}
        h3.subsection-title {{
            font-family: Arial, sans-serif;
            font-size: 16pt;
            font-weight: 700;
            color: #000B50; /* #000B50 */
            text-align: left;
            margin-top: 0.22in;
            margin-bottom: 0.08in;
            page-break-after: avoid;
        }}
        h4.sub-subsection-title {{
            font-family: Arial, sans-serif;
            font-size: 14pt;
            font-weight: 700;
            color: #000B50;
            text-align: left;
            margin-top: 0.16in;
            margin-bottom: 0.06in;
            page-break-after: avoid;
        }}
        h5.minor-subtopic {{
            font-family: Arial, sans-serif;
            font-size: 12pt;
            font-weight: 700;
            color: #1B3A6B;
            text-align: left;
            margin-top: 0.12in;
            margin-bottom: 0.04in;
            page-break-after: avoid;
        }}
        p {{
            margin-top: 4pt;
            margin-bottom: 0;
            font-size: 11pt;
            line-height: 1.25;
            color: #000000;
            text-align: justify;
        }}
        .figure-card {{
            background-color: #F8FAFC;
            border: 1px solid #CBD5E0;
            border-left: 4px solid #1B3A6B;
            border-radius: 4px;
            padding: 12px 16px;
            margin: 18px 0;
            page-break-inside: avoid;
        }}
        .figure-card-header {{
            display: flex;
            align-items: center;
            gap: 8px;
            margin-bottom: 4px;
        }}
        .figure-card-header .camera-icon {{
            font-size: 13pt;
        }}
        .figure-card-header .figure-title {{
            font-family: Arial, sans-serif;
            font-size: 10.5pt;
            font-weight: bold;
            color: #1B3A6B;
            letter-spacing: 0.5px;
        }}
        .figure-card-badge {{
            font-family: Arial, sans-serif;
            font-size: 8.5pt;
            font-weight: bold;
            color: #CC9944;
            letter-spacing: 0.8px;
            text-transform: uppercase;
            margin-bottom: 6px;
        }}
        .figure-card-desc {{
            font-family: Arial, sans-serif;
            font-size: 9.5pt;
            color: #4A5568;
            font-style: italic;
            line-height: 1.25;
            margin: 0;
            text-align: justify;
        }}
        .callout-box {{
            background-color: #F8FAFC;
            border: 2px solid #1B3A6B;
            border-radius: 4px;
            padding: 14px 18px;
            margin: 18px 0;
            page-break-inside: avoid;
        }}
        .callout-box.callout-myths {{
            border: 2px solid #C04A26;
            background-color: #FFFFFF;
        }}
        .callout-box.callout-myths .callout-header {{
            color: #C04A26;
        }}
        .callout-box.callout-dos-donts {{
            border: 2px solid #4B6B94;
            background-color: #F8FAFC;
        }}
        .callout-box.callout-first-timer {{
            border: 2px solid #2D7D46;
            background-color: #FFFFFF;
        }}
        .callout-box.callout-first-timer .callout-header {{
            color: #2D7D46;
        }}
        .callout-box.callout-checklist {{
            border: 2px solid #4A2E80;
            background-color: #FFFFFF;
        }}
        .callout-box.callout-checklist .callout-header {{
            color: #4A2E80;
        }}
        .callout-box.callout-accessibility {{
            border: 2px solid #A1346C;
            background-color: #FFFFFF;
        }}
        .callout-box.callout-accessibility .callout-header {{
            color: #A1346C;
        }}
        .callout-header {{
            font-family: Arial, sans-serif;
            font-size: 12.5pt;
            font-weight: bold;
            color: #1B3A6B;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            margin-bottom: 8px;
        }}
        .callout-body {{
            font-family: Arial, sans-serif;
            font-size: 11pt;
            color: #000000;
            line-height: 1.25;
            text-align: justify;
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
            font-family: Arial, sans-serif;
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
            background-color: #ebf3fb;
        }}
    </style>
</head>
<body>
    {cover_html}
    
    <div class="page-break title-page" style="text-align: center; padding-top: 1.2in;">
        <h1 style="font-family: Arial, sans-serif; font-size: 36pt; font-weight: bold; color: #1B3A6B; margin-bottom: 0.2in; border: none; text-transform: uppercase;">{title}</h1>
        <p style="font-family: Arial, sans-serif; font-size: 24pt; font-weight: bold; color: #CC9944; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 0.6in;">{subtitle}</p>
        <p style="font-family: Arial, sans-serif; font-size: 12pt; color: #555555;">By <strong>{author}</strong></p>
    </div>

    <div class="page-break copyright" style="padding-top: 1in; font-size: 10pt; color: #3C3C3C;">
        <h3 style="font-family: Arial, sans-serif; font-size: 14pt; color: #1B3A6B; font-weight: bold;">Copyright © 2026 by {author}. All rights reserved.</h3>
        <p>No part of this publication may be reproduced, stored in a retrieval system, or transmitted in any form or by any means without the prior written permission of the author.</p>
        <p>First Edition: 2026 | Format: Amazon KDP Direct — Executive 7" × 10" trim size.</p>
        <hr style="border: none; border-top: 1px solid #CBD5E0; margin: 20px 0;">
        <h4 style="font-family: Arial, sans-serif; font-size: 14pt; color: #1B3A6B; font-weight: bold;">DISCLAIMER & ACCURACY NOTICE</h4>
        <p>This guide is intended for general informational and travel-planning purposes only. Readers assume full responsibility for their own safety, route choices, transit ticketing, and health precautions.</p>
    </div>

    <div class="toc-container">
        <h2 style="font-family: Arial, sans-serif; color: #1B3A6B; text-align: center; border: none; font-size: 18pt; font-weight: bold; margin-bottom: 25px; text-transform: uppercase; letter-spacing: 1px;">TABLE OF CONTENTS</h2>
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
        def find_browser():
            import shutil
            env_b = os.getenv("BROWSER_PATH")
            if env_b and os.path.exists(env_b):
                return env_b
            for name in ["chromium", "chromium-browser", "google-chrome", "google-chrome-stable", "msedge"]:
                w = shutil.which(name)
                if w:
                    return w
            for p in [
                r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                "/usr/bin/chromium",
                "/usr/bin/chromium-browser",
                "/usr/bin/google-chrome",
                "/usr/bin/google-chrome-stable",
            ]:
                if os.path.exists(p):
                    return p
            return None

        edge_exe = find_browser()
        pdf_status = ""
        
        if edge_exe:
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
                try:
                    td1 = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
                except TypeError:
                    td1 = tempfile.TemporaryDirectory()
                with td1 as temp_dir_1:
                    cmd1 = base_flags + [f"--user-data-dir={temp_dir_1}", f"--print-to-pdf={pdf_abs}", html_abs]
                    run_edge_print(cmd1, pdf_abs, timeout=60)

                # Discover page numbers with PyMuPDF
                doc = pymupdf.open(pdf_abs)
                heading_pages = {"Copyright Notice": 3, "Disclaimer & Legal Notice": 3}
                current_ch = None
                for pno in range(3, len(doc)):
                    page = doc[pno]
                    blocks = page.get_text("dict")["blocks"]
                    for b in blocks:
                        if "lines" in b:
                            block_text = " ".join(" ".join(s["text"] for s in l["spans"]) for l in b["lines"])
                            b_clean = re.sub(r'\W+', '', block_text).upper()
                            first_span = b["lines"][0]["spans"][0]
                            font_size = first_span["size"]
                            # Check Level 1 (Chapters: 48pt)
                            if font_size >= 32.0:
                                for ch in chapter_tree:
                                    ch_t = ch["title"].upper()
                                    ch_clean = re.sub(r'\W+', '', ch_t)
                                    prefix_m = re.match(r'^(CHAPTER\s+\d+|INTRODUCTION|CONCLUSION)', ch_t)
                                    prefix_clean = re.sub(r'\W+', '', prefix_m.group(1)) if prefix_m else ch_clean[:10]
                                    if prefix_clean == b_clean and ch["title"] not in heading_pages:
                                        heading_pages[ch["title"]] = pno + 1
                                        current_ch = ch
                            # Check Level 2 (Subsections: 18pt / 16pt)
                            elif 14.0 <= font_size < 20.0 and current_ch:
                                for sub in current_ch["subsections"]:
                                    sub_clean = re.sub(r'\W+', '', sub).upper()
                                    sub_key = f"{current_ch['title']}::{sub}"
                                    if sub_clean[:18] in b_clean and sub_key not in heading_pages:
                                        heading_pages[sub_key] = pno + 1
                doc.close()

                # Pass 2: Re-generate HTML with exact page numbers in TOC
                pass2_html = build_html_document(toc_pages=heading_pages, embed_base64=False)
                with open(html_filepath, "w", encoding="utf-8") as f:
                    f.write(pass2_html)

                # Re-render final PDF
                try:
                    td2 = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
                except TypeError:
                    td2 = tempfile.TemporaryDirectory()
                with td2 as temp_dir_2:
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
                    [1, "Front Matter: Copyright & Disclaimer", 2],
                    [1, "Table of Contents", 3]
                ]
                for ch in chapter_tree:
                    ch_title = ch["title"]
                    if ch_title in heading_pages:
                        toc_tree.append([1, ch_title, heading_pages[ch_title]])
                        for sub in ch["subsections"]:
                            sub_key = f"{ch_title}::{sub}"
                            sub_p = heading_pages.get(sub_key) or heading_pages.get(ch_title)
                            toc_tree.append([2, sub, sub_p])

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
            pdf_status = "\n- PDF Generation Skipped: Headless browser (Chromium/Chrome/Edge) executable not found."

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
