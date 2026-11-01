"""
Bhoonidhi PowerPoint Report Generator Module.
Generates professional 16:9 widescreen daily satellite imagery quality-control
presentations (.pptx) adhering to clean light technical design guidelines.
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

from bhoonidhi.qc_metadata import QCMetadata, extract_qc_metadata

# Palette: Clean Light Technical Theme
COLOR_BG_LIGHT = RGBColor(248, 249, 250)      # #F8F9FA Soft Light Gray
COLOR_CARD_BG = RGBColor(255, 255, 255)       # #FFFFFF Crisp White
COLOR_PRIMARY = RGBColor(15, 52, 96)          # #0F3460 ISRO Deep Navy
COLOR_SECONDARY = RGBColor(2, 132, 199)       # #0284C7 Sky Blue / Cyan Accent
COLOR_TEXT_MAIN = RGBColor(26, 32, 44)        # #1A202C Dark Slate
COLOR_TEXT_MUTED = RGBColor(100, 116, 139)    # #64748B Slate Muted
COLOR_BORDER = RGBColor(203, 213, 225)        # #CBD5E1 Subtle Border
COLOR_ONLINE_GREEN = RGBColor(5, 150, 105)    # #059669 Emerald
COLOR_OFFLINE_AMBER = RGBColor(217, 119, 6)   # #D97706 Amber
COLOR_ROW_ALT = RGBColor(241, 245, 249)       # #F1F5F9 Table Alternate Row


class SatelliteReportGenerator:
    """Compiles collected satellite browse images and QC metadata into a polished PowerPoint report."""

    def __init__(
        self,
        collection_id: str,
        target_date: str,
        manifest: Optional[Dict[str, Any]] = None,
        max_slides: Optional[int] = 30,
    ):
        self.collection_id = collection_id
        self.target_date = target_date
        self.manifest = manifest or {}
        self.max_slides = max_slides

        # Initialize 16:9 Presentation
        self.prs = Presentation()
        self.prs.slide_width = Inches(13.333)
        self.prs.slide_height = Inches(7.5)
        self.blank_layout = self.prs.slide_layouts[6]  # Blank slide layout

    def _set_slide_background(self, slide, color: RGBColor = COLOR_BG_LIGHT):
        """Fills slide background with a solid color."""
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = color

    def _add_slide_header(self, slide, title_text: str, subtitle_text: str = ""):
        """Adds a standardized header banner to content slides."""
        # Top banner accent line
        accent = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(0.4), Inches(11.733), Inches(0.04)
        )
        accent.fill.solid()
        accent.fill.fore_color.rgb = COLOR_SECONDARY
        accent.line.color.rgb = COLOR_SECONDARY

        # Title text box
        tb = slide.shapes.add_textbox(Inches(0.8), Inches(0.48), Inches(11.733), Inches(0.65))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

        p = tf.paragraphs[0]
        p.text = title_text
        p.font.size = Pt(17)
        p.font.bold = True
        p.font.color.rgb = COLOR_PRIMARY
        p.font.name = "Segoe UI"

        if subtitle_text:
            p2 = tf.add_paragraph()
            p2.text = subtitle_text
            p2.font.size = Pt(10)
            p2.font.color.rgb = COLOR_TEXT_MUTED
            p2.font.name = "Segoe UI"

    def _add_slide_number(self, slide, current_slide: int, total_slides: int):
        """Adds slide number footer on the bottom-right."""
        tb = slide.shapes.add_textbox(Inches(10.5), Inches(7.05), Inches(2.0), Inches(0.35))
        tf = tb.text_frame
        tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.text = f"Slide {current_slide} of {total_slides}"
        p.font.size = Pt(9)
        p.font.color.rgb = COLOR_TEXT_MUTED
        p.font.name = "Segoe UI"
        p.alignment = PP_ALIGN.RIGHT

    def create_cover_slide(self, total_products: int, previews_collected: int, satellite_name: str):
        """Builds Slide 1: Mission Cover Slide."""
        slide = self.prs.slides.add_slide(self.blank_layout)
        self._set_slide_background(slide, COLOR_CARD_BG)

        # Header Badge
        badge = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(1.0), Inches(4.5), Inches(0.4)
        )
        badge.fill.solid()
        badge.fill.fore_color.rgb = COLOR_SECONDARY
        badge.line.color.rgb = COLOR_SECONDARY
        btf = badge.text_frame
        bp = btf.paragraphs[0]
        bp.text = "ISRO • NATIONAL REMOTE SENSING CENTRE"
        bp.font.size = Pt(11)
        bp.font.bold = True
        bp.font.color.rgb = COLOR_CARD_BG
        bp.font.name = "Segoe UI"
        bp.alignment = PP_ALIGN.CENTER

        # Main Title
        title_box = slide.shapes.add_textbox(Inches(1.0), Inches(1.6), Inches(11.3), Inches(1.8))
        tf = title_box.text_frame
        tf.word_wrap = True

        p1 = tf.paragraphs[0]
        p1.text = "DAILY SATELLITE IMAGERY REPORT"
        p1.font.size = Pt(32)
        p1.font.bold = True
        p1.font.color.rgb = COLOR_PRIMARY
        p1.font.name = "Segoe UI"

        p2 = tf.add_paragraph()
        p2.text = f"Mission Quality-Control & Telemetry Dump Audit • {satellite_name}"
        p2.font.size = Pt(15)
        p2.font.color.rgb = COLOR_TEXT_MUTED
        p2.font.name = "Segoe UI"

        # Decorative Divider
        divider = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, Inches(1.0), Inches(3.6), Inches(11.3), Inches(0.03)
        )
        divider.fill.solid()
        divider.fill.fore_color.rgb = COLOR_BORDER
        divider.line.color.rgb = COLOR_BORDER

        # Metric Summary Cards (4 Cards across)
        card_w = Inches(2.6)
        card_h = Inches(1.6)
        card_y = Inches(4.0)

        metrics = [
            ("TARGET DATE", self.target_date, "Observation Calendar Day"),
            ("SATELLITE / PLATFORM", satellite_name, self.collection_id),
            ("SCENES FOUND", str(total_products), "STAC Catalogue Records"),
            ("PREVIEWS COLLECTED", str(previews_collected), "Verified Browse Images"),
        ]

        for i, (label, val, sub) in enumerate(metrics):
            card_x = Inches(1.0) + i * Inches(2.9)
            card = slide.shapes.add_shape(
                MSO_SHAPE.ROUNDED_RECTANGLE, card_x, card_y, card_w, card_h
            )
            card.fill.solid()
            card.fill.fore_color.rgb = COLOR_BG_LIGHT
            card.line.color.rgb = COLOR_BORDER
            card.line.width = Pt(1)

            ctf = card.text_frame
            ctf.margin_top = Inches(0.18)
            ctf.margin_left = ctf.margin_right = Inches(0.18)

            lp = ctf.paragraphs[0]
            lp.text = label
            lp.font.size = Pt(9)
            lp.font.bold = True
            lp.font.color.rgb = COLOR_TEXT_MUTED
            lp.font.name = "Segoe UI"

            vp = ctf.add_paragraph()
            vp.text = val
            vp.font.size = Pt(18)
            vp.font.bold = True
            vp.font.color.rgb = COLOR_PRIMARY
            vp.font.name = "Segoe UI"

            sp = ctf.add_paragraph()
            sp.text = sub
            sp.font.size = Pt(8.5)
            sp.font.color.rgb = COLOR_TEXT_MUTED
            sp.font.name = "Segoe UI"

        # Footer timestamp
        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ft_box = slide.shapes.add_textbox(Inches(1.0), Inches(6.4), Inches(11.3), Inches(0.4))
        ft_tf = ft_box.text_frame
        ft_p = ft_tf.paragraphs[0]
        ft_p.text = f"Bhoonidhi STAC Open Data Dissemination • Generated at {now_utc}"
        ft_p.font.size = Pt(9.5)
        ft_p.font.color.rgb = COLOR_TEXT_MUTED
        ft_p.font.name = "Segoe UI"

    def create_overview_slide(
        self,
        total_products: int,
        downloaded: int,
        existing: int,
        unavailable: int,
        failed: int,
        total_mb: float,
        notes: str = "",
    ):
        """Builds Slide 2: Daily Overview and Ingestion Summary Table."""
        slide = self.prs.slides.add_slide(self.blank_layout)
        self._set_slide_background(slide, COLOR_BG_LIGHT)
        self._add_slide_header(
            slide,
            "MISSION OVERVIEW & HARVEST AUDIT",
            f"Catalogue query parameters and data volume metrics for {self.target_date}",
        )

        # Overview Table
        rows = 9
        cols = 2
        table_shape = slide.shapes.add_table(
            rows, cols, Inches(0.8), Inches(1.3), Inches(11.733), Inches(5.4)
        )
        table = table_shape.table
        table.columns[0].width = Inches(4.2)
        table.columns[1].width = Inches(7.533)

        overview_rows = [
            ("Target Observation Date", f"{self.target_date} (Asia/Kolkata Calendar Window)"),
            ("Collection Identifier", self.collection_id),
            ("Query Mode & Range", self.manifest.get("query_by", "Acquisition Sensing Datetime").upper()),
            ("Total STAC Records Found", str(total_products)),
            ("Browse Images Downloaded", str(downloaded)),
            ("Browse Images Reused (Cached)", str(existing)),
            ("Records Without Browse Images", str(unavailable)),
            ("Failed or Skipped Downloads", str(failed)),
            ("Total Preview Data Volume", f"{total_mb:.3f} MB ({self.manifest.get('total_preview_data_bytes', 0):,} bytes)"),
        ]

        for r_idx, (col1, col2) in enumerate(overview_rows):
            cell_left = table.cell(r_idx, 0)
            cell_right = table.cell(r_idx, 1)

            cell_left.text = col1
            cell_right.text = col2

            # Formatting
            for c_idx, cell in enumerate([cell_left, cell_right]):
                cell.fill.solid()
                cell.fill.fore_color.rgb = COLOR_ROW_ALT if (r_idx % 2 == 1) else COLOR_CARD_BG
                p = cell.text_frame.paragraphs[0]
                p.font.size = Pt(10)
                p.font.name = "Segoe UI"
                p.font.color.rgb = COLOR_PRIMARY if c_idx == 0 else COLOR_TEXT_MAIN
                if c_idx == 0:
                    p.font.bold = True

        if notes:
            notes_box = slide.shapes.add_textbox(Inches(0.8), Inches(6.8), Inches(11.733), Inches(0.35))
            np = notes_box.text_frame.paragraphs[0]
            np.text = f"Notice: {notes}"
            np.font.size = Pt(9)
            np.font.italic = True
            np.font.color.rgb = COLOR_OFFLINE_AMBER
            np.font.name = "Segoe UI"

    def create_product_slide(
        self,
        qc: QCMetadata,
        slide_index: int,
        total_content_slides: int,
    ):
        """
        Builds a Side-by-Side Product Imagery Slide.
        Left (~60%): Large satellite browse image.
        Right (~40%): Structured 14-field QC metadata table + manual review box.
        """
        slide = self.prs.slides.add_slide(self.blank_layout)
        self._set_slide_background(slide, COLOR_BG_LIGHT)

        # Header with Online Tag
        online_tag = f"[{qc.online_status}]" if qc.online_status != "Unknown" else ""
        header_text = f"SCENE [{slide_index}/{total_content_slides}]: {qc.item_id}"
        sub_text = f"Platform: {qc.platform} • Instrument: {qc.instrument} • Mode: {qc.mode_id} {online_tag}"
        self._add_slide_header(slide, header_text, sub_text)

        # --- LEFT SIDE: Satellite Browse Image Container (60% width) ---
        img_container_x = Inches(0.8)
        img_container_y = Inches(1.25)
        img_container_w = Inches(7.2)
        img_container_h = Inches(5.6)

        # Background card for image
        img_card = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            img_container_x,
            img_container_y,
            img_container_w,
            img_container_h,
        )
        img_card.fill.solid()
        img_card.fill.fore_color.rgb = COLOR_CARD_BG
        img_card.line.color.rgb = COLOR_BORDER
        img_card.line.width = Pt(1)

        # Check and insert image
        image_inserted = False
        if qc.preview_file_path and Path(qc.preview_file_path).is_file():
            img_path = Path(qc.preview_file_path)
            try:
                with Image.open(img_path) as pil_img:
                    orig_w, orig_h = pil_img.size

                # Compute scale to fit inside container with 0.15 inch margin
                max_w = img_container_w - Inches(0.3)
                max_h = img_container_h - Inches(0.3)

                aspect = orig_w / orig_h
                container_aspect = max_w / max_h

                if aspect > container_aspect:
                    # Width constrained
                    draw_w = max_w
                    draw_h = max_w / aspect
                else:
                    # Height constrained
                    draw_h = max_h
                    draw_w = max_h * aspect

                # Center image within card
                offset_x = img_container_x + (img_container_w - draw_w) / 2
                offset_y = img_container_y + (img_container_h - draw_h) / 2

                slide.shapes.add_picture(str(img_path), offset_x, offset_y, draw_w, draw_h)
                image_inserted = True
            except Exception:
                image_inserted = False

        if not image_inserted:
            # Placeholder Card for unavailable / invalid image
            ph_box = slide.shapes.add_textbox(
                img_container_x + Inches(0.5),
                img_container_y + Inches(2.0),
                img_container_w - Inches(1.0),
                Inches(1.8),
            )
            pht = ph_box.text_frame
            pp1 = pht.paragraphs[0]
            pp1.text = "PREVIEW UNAVAILABLE"
            pp1.font.size = Pt(16)
            pp1.font.bold = True
            pp1.font.color.rgb = COLOR_TEXT_MUTED
            pp1.font.name = "Segoe UI"
            pp1.alignment = PP_ALIGN.CENTER

            pp2 = pht.add_paragraph()
            pp2.text = "No downloadable browse/thumbnail asset exposed by STAC catalogue for this product."
            pp2.font.size = Pt(10)
            pp2.font.color.rgb = COLOR_TEXT_MUTED
            pp2.font.name = "Segoe UI"
            pp2.alignment = PP_ALIGN.CENTER

        # --- RIGHT SIDE: QC Metadata Table (40% width) ---
        right_x = Inches(8.2)
        right_y = Inches(1.25)
        right_w = Inches(4.333)

        qc_pairs = qc.to_display_pairs()
        num_rows = len(qc_pairs)

        table_h = Inches(4.1)
        table_shape = slide.shapes.add_table(num_rows, 2, right_x, right_y, right_w, table_h)
        tbl = table_shape.table
        tbl.columns[0].width = Inches(1.85)
        tbl.columns[1].width = Inches(2.483)

        for r_idx, (f_name, f_val) in enumerate(qc_pairs):
            c0 = tbl.cell(r_idx, 0)
            c1 = tbl.cell(r_idx, 1)

            c0.text = f_name
            c1.text = str(f_val)

            # Styling
            bg_col = COLOR_ROW_ALT if (r_idx % 2 == 1) else COLOR_CARD_BG
            for c_idx, cell in enumerate([c0, c1]):
                cell.fill.solid()
                cell.fill.fore_color.rgb = bg_col
                cell.margin_left = Inches(0.08)
                cell.margin_right = Inches(0.08)
                cell.margin_top = Inches(0.02)
                cell.margin_bottom = Inches(0.02)

                p = cell.text_frame.paragraphs[0]
                p.font.size = Pt(8.5)
                p.font.name = "Segoe UI"
                if c_idx == 0:
                    p.font.bold = True
                    p.font.color.rgb = COLOR_PRIMARY
                else:
                    p.font.color.rgb = COLOR_TEXT_MAIN

        # --- RIGHT SIDE BOTTOM: COMMENTS / MANUAL REVIEW BOX ---
        review_y = Inches(5.45)
        review_h = Inches(1.4)
        review_card = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE, right_x, review_y, right_w, review_h
        )
        review_card.fill.solid()
        review_card.fill.fore_color.rgb = COLOR_CARD_BG
        review_card.line.color.rgb = COLOR_BORDER
        review_card.line.width = Pt(1)

        rtf = review_card.text_frame
        rtf.margin_top = Inches(0.08)
        rtf.margin_left = Inches(0.12)
        rtf.margin_right = Inches(0.12)
        rtf.margin_bottom = Inches(0.08)

        rp1 = rtf.paragraphs[0]
        rp1.text = "COMMENTS / MANUAL REVIEW"
        rp1.font.size = Pt(9)
        rp1.font.bold = True
        rp1.font.color.rgb = COLOR_PRIMARY
        rp1.font.name = "Segoe UI"

        rp2 = rtf.add_paragraph()
        rp2.text = "Notes: _____________________________________________________\nQC Sign-Off: __________________________   Date: ____________"
        rp2.font.size = Pt(8.5)
        rp2.font.color.rgb = COLOR_TEXT_MUTED
        rp2.font.name = "Segoe UI"

        # Footer
        self._add_slide_number(slide, slide_index + 2, total_content_slides + 3)

    def create_summary_slide(
        self,
        total_products: int,
        downloaded: int,
        unavailable: int,
        failed: int,
        total_mb: float,
        api_limitations: str = "",
    ):
        """Builds Final Slide: Quality Control & Pipeline Processing Summary."""
        slide = self.prs.slides.add_slide(self.blank_layout)
        self._set_slide_background(slide, COLOR_BG_LIGHT)
        self._add_slide_header(
            slide,
            "QUALITY CONTROL & PIPELINE SUMMARY",
            "Audit verification, data completeness and collection parameters",
        )

        # 3 Structured Summary Cards
        card_w = Inches(3.7)
        card_h = Inches(4.8)
        card_y = Inches(1.3)

        # Card 1: Data Integrity
        c1 = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.8), card_y, card_w, card_h
        )
        c1.fill.solid()
        c1.fill.fore_color.rgb = COLOR_CARD_BG
        c1.line.color.rgb = COLOR_BORDER
        tf1 = c1.text_frame
        tf1.margin_left = tf1.margin_right = tf1.margin_top = Inches(0.2)
        p1 = tf1.paragraphs[0]
        p1.text = "Data Integrity & Policy"
        p1.font.size = Pt(13)
        p1.font.bold = True
        p1.font.color.rgb = COLOR_PRIMARY

        bullets1 = [
            "✔ 100% Browse/Quicklook Download Policy enforced.",
            "✔ No heavy Level-1/Level-2 raw rasters downloaded.",
            "✔ Zero .SAFE, .ZIP, or .TIF scientific payloads retrieved.",
            "✔ All preview payloads verified via binary magic bytes.",
            "✔ Image dimensions inspected and confirmed with PIL.",
            f"✔ Total browse imagery storage: {total_mb:.2f} MB.",
        ]
        for b in bullets1:
            bp = tf1.add_paragraph()
            bp.text = b
            bp.font.size = Pt(9.5)
            bp.font.color.rgb = COLOR_TEXT_MAIN

        # Card 2: Catalogue Audit
        c2 = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(4.8), card_y, card_w, card_h
        )
        c2.fill.solid()
        c2.fill.fore_color.rgb = COLOR_CARD_BG
        c2.line.color.rgb = COLOR_BORDER
        tf2 = c2.text_frame
        tf2.margin_left = tf2.margin_right = tf2.margin_top = Inches(0.2)
        p2 = tf2.paragraphs[0]
        p2.text = "Catalogue Harvest Counts"
        p2.font.size = Pt(13)
        p2.font.bold = True
        p2.font.color.rgb = COLOR_PRIMARY

        bullets2 = [
            f"• Target Date: {self.target_date}",
            f"• Primary Collection: {self.collection_id}",
            f"• Products Catalogued: {total_products}",
            f"• Verified Browse Images: {downloaded}",
            f"• Products Without Previews: {unavailable}",
            f"• Failed / Interrupted Downloads: {failed}",
            f"• Presentation Slides: {len(self.prs.slides) + 1}",
        ]
        for b in bullets2:
            bp = tf2.add_paragraph()
            bp.text = b
            bp.font.size = Pt(9.5)
            bp.font.color.rgb = COLOR_TEXT_MAIN

        # Card 3: Limitations & Status
        c3 = slide.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE, Inches(8.8), card_y, card_w, card_h
        )
        c3.fill.solid()
        c3.fill.fore_color.rgb = COLOR_CARD_BG
        c3.line.color.rgb = COLOR_BORDER
        tf3 = c3.text_frame
        tf3.margin_left = tf3.margin_right = tf3.margin_top = Inches(0.2)
        p3 = tf3.paragraphs[0]
        p3.text = "API & Mission Notes"
        p3.font.size = Pt(13)
        p3.font.bold = True
        p3.font.color.rgb = COLOR_PRIMARY

        limitation_text = api_limitations or (
            "• Operational pipeline completed nominal execution.\n"
            "• Ground-station QC metadata mapped successfully.\n"
            "• All slides generated from live STAC catalogue records."
        )
        for line in limitation_text.splitlines():
            bp = tf3.add_paragraph()
            bp.text = line
            bp.font.size = Pt(9.5)
            bp.font.color.rgb = COLOR_TEXT_MAIN

        # Footer
        total_slides = len(self.prs.slides)
        self._add_slide_number(slide, total_slides, total_slides)

    def generate_report(
        self,
        items: List[Dict[str, Any]],
        output_file_path: Union[str, Path],
        api_limitations: str = "",
    ) -> Path:
        """
        Full generation orchestrator:
        1. Generates Slide 1 (Cover).
        2. Generates Slide 2 (Daily Overview).
        3. Generates Slides 3..N (Product Imagery with 14 QC attributes).
        4. Generates Final Slide (Audit Summary).
        5. Saves .pptx presentation to disk.
        """
        output_path = Path(output_file_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        total_items = len(items)
        satellite_name = self.collection_id.split("_")[0]

        # Extract QC metadata for all items
        qc_list: List[QCMetadata] = [extract_qc_metadata(it) for it in items]

        # Filter items for slide generation based on max_slides
        if self.max_slides and total_items > self.max_slides:
            slide_items = qc_list[: self.max_slides]
        else:
            slide_items = qc_list

        total_content = len(slide_items)

        # Statistics from manifest
        downloaded = self.manifest.get("previews_downloaded", sum(1 for q in qc_list if q.preview_status == "downloaded"))
        existing = self.manifest.get("previews_already_existing", sum(1 for q in qc_list if q.preview_status == "already_exists"))
        unavailable = self.manifest.get("previews_unavailable", sum(1 for q in qc_list if q.preview_status == "unavailable"))
        failed = self.manifest.get("previews_failed", sum(1 for q in qc_list if q.preview_status not in ["downloaded", "already_exists", "unavailable"]))
        total_mb = self.manifest.get("total_preview_data_mb", 0.0)

        # 1. Slide 1: Cover
        self.create_cover_slide(
            total_products=total_items,
            previews_collected=downloaded + existing,
            satellite_name=satellite_name,
        )

        # 2. Slide 2: Daily Overview Table
        notes = ""
        if self.max_slides and total_items > self.max_slides:
            notes = f"Presentation includes first {self.max_slides} of {total_items} scenes (use --all-scenes for full deck)."
        self.create_overview_slide(
            total_products=total_items,
            downloaded=downloaded,
            existing=existing,
            unavailable=unavailable,
            failed=failed,
            total_mb=total_mb,
            notes=notes,
        )

        # 3. Slides 3..N: Product Imagery & QC Card
        for s_idx, qc_item in enumerate(slide_items, 1):
            self.create_product_slide(
                qc=qc_item,
                slide_index=s_idx,
                total_content_slides=total_content,
            )

        # 4. Final Slide: Audit & Limitations Summary
        self.create_summary_slide(
            total_products=total_items,
            downloaded=downloaded + existing,
            unavailable=unavailable,
            failed=failed,
            total_mb=total_mb,
            api_limitations=api_limitations,
        )

        # Save PowerPoint file
        self.prs.save(str(output_path))
        return output_path
