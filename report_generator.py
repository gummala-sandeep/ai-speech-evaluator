"""
report_generator.py — In-Memory PDF Report Engine for SkillEcho
Assembles a structured evaluation report entirely within RAM using
ReportLab Platypus, avoiding any disk I/O for the output artefact.
"""

from __future__ import annotations

import io
import logging
from datetime import datetime

from reportlab.lib import colors  # type: ignore[import]
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT  # type: ignore[import]
from reportlab.lib.pagesizes import A4  # type: ignore[import]
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # type: ignore[import]
from reportlab.lib.units import cm  # type: ignore[import]
from reportlab.platypus import (  # type: ignore[import]
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

_DARK_BG: colors.Color = colors.HexColor("#1a1a2e")
_ACCENT: colors.Color = colors.HexColor("#7c3aed")
_HEADER_FG: colors.Color = colors.white
_CELL_BG_ALT: colors.Color = colors.HexColor("#f0eeff")
_BORDER_COLOR: colors.Color = colors.HexColor("#c4b5fd")

# Understanding level colour map (matches scoring_engine.py)
_LEVEL_COLORS: dict[str, colors.Color] = {
    "Strong Understanding": colors.HexColor("#2ecc71"),
    "Moderate Understanding": colors.HexColor("#f39c12"),
    "Poor Understanding": colors.HexColor("#e74c3c"),
    "Topic Mismatch": colors.HexColor("#e74c3c"),
}


# ---------------------------------------------------------------------------
# Style factory
# ---------------------------------------------------------------------------


def _build_styles() -> dict[str, ParagraphStyle]:
    """Construct and return a mapping of named ParagraphStyle objects."""
    base = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "VBCUATitle",
        parent=base["Title"],
        fontSize=22,
        leading=28,
        textColor=_ACCENT,
        alignment=TA_CENTER,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )

    subtitle_style = ParagraphStyle(
        "VBCUASubtitle",
        parent=base["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#6b7280"),
        alignment=TA_CENTER,
        spaceAfter=2,
        fontName="Helvetica",
    )

    section_header_style = ParagraphStyle(
        "VBCUASectionHeader",
        parent=base["Heading2"],
        fontSize=13,
        leading=18,
        textColor=_ACCENT,
        fontName="Helvetica-Bold",
        spaceBefore=14,
        spaceAfter=6,
    )

    body_style = ParagraphStyle(
        "VBCUABody",
        parent=base["Normal"],
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#374151"),
        alignment=TA_JUSTIFY,
        fontName="Helvetica",
    )

    box_style = ParagraphStyle(
        "VBCUABox",
        parent=base["Normal"],
        fontSize=10,
        leading=15,
        textColor=colors.HexColor("#1e1b4b"),
        alignment=TA_JUSTIFY,
        fontName="Helvetica",
        backColor=colors.HexColor("#f5f3ff"),
        borderPadding=(8, 10, 8, 10),
    )

    return {
        "title": title_style,
        "subtitle": subtitle_style,
        "section_header": section_header_style,
        "body": body_style,
        "box": box_style,
    }


# ---------------------------------------------------------------------------
# Table builder helpers
# ---------------------------------------------------------------------------


def _build_metrics_table(metrics: dict) -> Table:
    """
    Construct a styled ReportLab Table displaying evaluation metrics.

    Args:
        metrics: Dictionary with keys ``similarity_score``, ``cross_encoder_score``,
                 ``topic_match``, ``filler_ratio``, ``pause_ratio``, ``rms_energy``,
                 ``overall_score``, and ``understanding_level``.

    Returns:
        A fully configured ``Table`` flowable.
    """
    header_style = ParagraphStyle(
        "TH",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    cell_style = ParagraphStyle(
        "TD",
        fontSize=10,
        fontName="Helvetica",
        textColor=colors.HexColor("#111827"),
        alignment=TA_CENTER,
    )

    level: str = str(metrics.get("understanding_level", "N/A"))
    level_color: colors.Color = _LEVEL_COLORS.get(level, colors.grey)

    level_style = ParagraphStyle(
        "Level",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=level_color,
        alignment=TA_CENTER,
    )

    topic_match: bool = bool(metrics.get("topic_match", True))
    topic_str: str = "MATCH" if topic_match else "MISMATCH"
    topic_style = ParagraphStyle(
        "TopicStyle",
        fontSize=10,
        fontName="Helvetica-Bold",
        textColor=colors.HexColor("#2ecc71") if topic_match else colors.HexColor("#e74c3c"),
        alignment=TA_CENTER,
    )

    bi_pct: str = f"{float(metrics.get('similarity_score', 0.0)) * 100:.1f}%"
    cross_pct: str = f"{float(metrics.get('cross_encoder_score', 0.0)) * 100:.1f}%"
    filler_pct: str = f"{float(metrics.get('filler_ratio', 0.0)) * 100:.2f}%"
    pause_pct: str = f"{float(metrics.get('pause_ratio', 0.0)) * 100:.1f}%"
    rms_val: str = f"{float(metrics.get('rms_energy', 0.0)):.6f}"
    score_val: str = f"{int(metrics.get('overall_score', 0))} / 100"

    table_data = [
        [
            Paragraph("Metric", header_style),
            Paragraph("Value", header_style),
            Paragraph("Interpretation", header_style),
        ],
        [
            Paragraph("Topic Guardrail", cell_style),
            Paragraph(topic_str, topic_style),
            Paragraph("Keyword-based vocabulary alignment check", cell_style),
        ],
        [
            Paragraph("Semantic Match (Bi-Encoder)", cell_style),
            Paragraph(bi_pct, cell_style),
            Paragraph("Dense semantic concept similarity", cell_style),
        ],
        [
            Paragraph("Semantic Accuracy (Cross-Encoder)", cell_style),
            Paragraph(cross_pct, cell_style),
            Paragraph("Deep semantic concept verification", cell_style),
        ],
        [
            Paragraph("Filler Word Ratio", cell_style),
            Paragraph(filler_pct, cell_style),
            Paragraph("Speech fluency indicator", cell_style),
        ],
        [
            Paragraph("Pause / Silence Ratio", cell_style),
            Paragraph(pause_pct, cell_style),
            Paragraph("Confidence and pacing balance", cell_style),
        ],
        [
            Paragraph("RMS Energy", cell_style),
            Paragraph(rms_val, cell_style),
            Paragraph("Vocal delivery strength", cell_style),
        ],
        [
            Paragraph("Overall Score", cell_style),
            Paragraph(score_val, cell_style),
            Paragraph(level, level_style),
        ],
    ]

    col_widths = [5.5 * cm, 3.5 * cm, 7.5 * cm]
    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    table.setStyle(
        TableStyle(
            [
                # Header row
                ("BACKGROUND", (0, 0), (-1, 0), _ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _CELL_BG_ALT]),
                # Grid
                ("GRID", (0, 0), (-1, -1), 0.5, _BORDER_COLOR),
                ("LINEBELOW", (0, 0), (-1, 0), 1.5, _ACCENT),
                # Padding
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                # Highlight final score row
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("LINEABOVE", (0, -1), (-1, -1), 1.5, _ACCENT),
            ]
        )
    )

    return table


# ---------------------------------------------------------------------------
# Primary public function
# ---------------------------------------------------------------------------


def generate_pdf_report(
    metrics: dict,
    transcript: str,
    reference_text: str,
    waveform_bytes: io.BytesIO,
) -> io.BytesIO:
    """
    Generate a fully formatted PDF evaluation report entirely in RAM.

    Args:
        metrics:        Dictionary containing all computed evaluation metrics.
                        Expected keys: ``similarity_score``, ``filler_ratio``,
                        ``pause_ratio``, ``rms_energy``, ``overall_score``,
                        ``understanding_level``.
        transcript:     The Whisper-generated transcript string.
        reference_text: The reference concept definition text.
        waveform_bytes: An ``io.BytesIO`` buffer containing a PNG/JPEG waveform
                        chart image (rewound to position 0 before passing).

    Returns:
        An ``io.BytesIO`` buffer containing the fully compiled PDF document,
        with the read pointer reset to position 0.
    """
    styles = _build_styles()
    output_buffer: io.BytesIO = io.BytesIO()

    doc = SimpleDocTemplate(
        output_buffer,
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.2 * cm,
        bottomMargin=2.0 * cm,
    )

    page_width: float = A4[0] - 4.0 * cm  # usable width after margins
    story: list = []

    # ------------------------------------------------------------------
    # Document Header
    # ------------------------------------------------------------------
    story.append(Paragraph("🎙️ SkillEcho Evaluation Report", styles["title"]))
    story.append(
        Paragraph(
            f"Evaluation Report  •  Generated on {datetime.utcnow().strftime('%d %B %Y at %H:%M UTC')}",
            styles["subtitle"],
        )
    )
    story.append(HRFlowable(width="100%", thickness=1.5, color=_ACCENT, spaceAfter=10))

    # ------------------------------------------------------------------
    # Reference Concept Box
    # ------------------------------------------------------------------
    story.append(Paragraph("Reference Concept", styles["section_header"]))

    ref_table = Table(
        [[Paragraph(reference_text or "No reference provided.", styles["box"])]],
        colWidths=[page_width],
    )
    ref_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f3ff")),
                ("BOX", (0, 0), (-1, -1), 1.2, _BORDER_COLOR),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(ref_table)
    story.append(Spacer(1, 10))

    # ------------------------------------------------------------------
    # Transcribed Explanation Box
    # ------------------------------------------------------------------
    story.append(Paragraph("Transcribed Student Explanation", styles["section_header"]))

    transcript_display: str = transcript.strip() if transcript.strip() else "(No speech detected)"
    transcript_table = Table(
        [[Paragraph(transcript_display, styles["box"])]],
        colWidths=[page_width],
    )
    transcript_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fefce8")),
                ("BOX", (0, 0), (-1, -1), 1.2, colors.HexColor("#fde68a")),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(transcript_table)
    story.append(Spacer(1, 10))

    # ------------------------------------------------------------------
    # Waveform Chart
    # ------------------------------------------------------------------
    story.append(Paragraph("Audio Signal Waveform", styles["section_header"]))

    try:
        waveform_bytes.seek(0)
        waveform_image = Image(waveform_bytes, width=page_width, height=5.5 * cm)
        story.append(waveform_image)
    except Exception:
        logger.warning("Could not embed waveform image; skipping chart section.")
        story.append(
            Paragraph("(Waveform chart unavailable for this report.)", styles["body"])
        )

    story.append(Spacer(1, 12))

    # ------------------------------------------------------------------
    # Evaluation Metrics Table
    # ------------------------------------------------------------------
    story.append(Paragraph("Evaluation Summary", styles["section_header"]))
    story.append(_build_metrics_table(metrics))
    story.append(Spacer(1, 14))

    # ------------------------------------------------------------------
    # Footer note
    # ------------------------------------------------------------------
    story.append(HRFlowable(width="100%", thickness=0.8, color=_BORDER_COLOR, spaceAfter=6))
    footer_style = ParagraphStyle(
        "Footer",
        fontSize=8,
        textColor=colors.HexColor("#9ca3af"),
        alignment=TA_LEFT,
        fontName="Helvetica",
    )
    story.append(
        Paragraph(
            "This report was automatically generated by the SkillEcho system. "
            "Scores are computed deterministically from acoustic and semantic signals. "
            "All processing was performed locally — no audio data was transmitted externally.",
            footer_style,
        )
    )

    # ------------------------------------------------------------------
    # Build PDF into buffer
    # ------------------------------------------------------------------
    doc.build(story)
    output_buffer.seek(0)

    logger.info("PDF report generated successfully — buffer size: %d bytes", output_buffer.getbuffer().nbytes)

    return output_buffer
