import os
import glob
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

# Brand colors
TEAL = colors.HexColor('#0F6E56')
TEAL_LIGHT = colors.HexColor('#E1F5EE')
TEAL_MID = colors.HexColor('#1D9E75')
AMBER = colors.HexColor('#f59e0b')
AMBER_LIGHT = colors.HexColor('#fffbeb')
RED_LIGHT = colors.HexColor('#fee2e2')
RED = colors.HexColor('#991b1b')
GREEN_LIGHT = colors.HexColor('#d1fae5')
GREEN = colors.HexColor('#065f46')
GRAY = colors.HexColor('#6b7280')
LIGHT_GRAY = colors.HexColor('#f9fafb')
BORDER = colors.HexColor('#e5e7eb')

def tissue_flowables(tissue):
    """Build the tissue-type section, or nothing at all when there is none.

    Tissue analysis is optional and user-triggered — it needs someone to draw
    a box round the wound — so most reports have no tissue data and simply
    omit this section rather than showing blanks or zeroes.
    """
    if not tissue:
        return []

    styles = getSampleStyleSheet()
    body = ParagraphStyle('tissue_body', parent=styles['Normal'],
                          fontSize=8.5, textColor=GRAY, leading=11)
    flowables = [
        Spacer(1, 0.3*cm),
        Paragraph('<font color="#0F6E56"><b>WOUND TISSUE COMPOSITION</b></font>',
                  ParagraphStyle('tissue_title', fontSize=10, spaceAfter=4)),
        HRFlowable(width="100%", thickness=1.5, color=TEAL),
        Spacer(1, 0.2*cm),
    ]
    frame = tissue.get("frame_filename") or "unknown frame"

    if tissue.get("no_wound_detected"):
        flowables.append(Paragraph(
            "<b>No wound tissue was detected in the selected area.</b> Less than "
            "1% of the selection was identified as wound, so no percentages are "
            f"reported. Analysed frame: {frame}.", body))
        return flowables

    rows = [
        ["Tissue type", "Share of wound", "Description"],
        ["Granulation", f"{tissue.get('granulation_percent') or 0:.1f}%",
         "Healthy healing tissue"],
        ["Fibrin", f"{tissue.get('fibrin_percent') or 0:.1f}%",
         "Yellow slough"],
        ["Callus", f"{tissue.get('callus_percent') or 0:.1f}%",
         "Thickened skin at the wound edge"],
    ]
    table = Table(rows, colWidths=[4.5*cm, 3.5*cm, 9.5*cm])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TEAL_LIGHT),
        ('TEXTCOLOR', (0, 0), (-1, 0), TEAL),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 1), (1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('TEXTCOLOR', (2, 1), (2, -1), GRAY),
        ('BOX', (0, 0), (-1, -1), 0.5, BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER),
        ('PADDING', (0, 0), (-1, -1), 5),
    ]))
    flowables.append(table)
    flowables.append(Spacer(1, 0.2*cm))

    wound_share = tissue.get("wound_fraction_of_box")
    share_note = (
        f" Of the selected area, {wound_share * 100:.0f}% was identified as wound "
        "tissue; unlike the percentages above, that figure does depend on how the "
        "area was drawn." if wound_share is not None else ""
    )
    flowables.append(Paragraph(
        "The three values are shares of the wound itself and total 100%, so they "
        "do not change with the size of the selected area." + share_note +
        f" Analysed frame: {frame}. Tissue types are estimated by a model trained "
        "on the DFUTissue dataset and are indicative, not a clinical diagnosis.",
        body))
    return flowables


def _general_notes():
    """Context that applies to any diabetic foot ulcer, stated as context.

    These appear on every report, so they must read as background a clinician
    already knows, not as instructions issued to them about a patient this
    system has never examined.
    """
    return [
        ("Pressure offloading",
         "Offloading with total contact casting or therapeutic footwear is widely used "
         "to reduce plantar pressure, and is associated with faster healing and lower "
         "recurrence in diabetic foot ulcers."),
        ("Blood glucose",
         "For patients with diabetes, poor glycaemic control is associated with slower "
         "healing and higher infection risk; guidelines commonly reference an HbA1c "
         "target below 7%. This system does not measure blood glucose."),
        ("Follow-up scanning",
         "Repeat scans at 7-14 day intervals allow volume change to be tracked over "
         "time. A reduction of more than 20% per week is commonly regarded as a "
         "positive healing trend."),
    ]


def get_recommendation(surface_area, volume, max_depth, scale_calibrated=True):
    """Describe what was measured and what it is commonly associated with.

    Wound-Splat is decision support: it reports observations, and a clinician
    decides what they mean. Nothing here is phrased as an instruction, a
    severity verdict, or a diagnosis.

    When `scale_calibrated` is False there was no size reference in the video,
    so the measurements are in arbitrary units. Size-dependent notes are then
    withheld entirely — advice derived from an unmeasured depth would be
    worse than no advice.
    """
    if not scale_calibrated:
        return (
            "unknown",
            "Size not assessed — scale not calibrated",
            GRAY, LIGHT_GRAY,
            "No size reference (such as a coin or bank card) was found in the video, "
            "so this scan is uncalibrated and its dimensions are relative rather than "
            "absolute. Shape and tissue observations remain usable; size-dependent "
            "notes are omitted. Include a size reference when filming to obtain "
            "absolute measurements.",
            _general_notes(),
        )

    measured = (
        f"Measured maximum depth {max_depth:.1f} mm, surface area "
        f"{surface_area:.2f} cm², estimated volume {volume:.2f} cm³. "
    )
    recs = []

    if max_depth > 20:
        severity = "severe"
        severity_label = "Deep — greater than 20 mm"
        severity_color = RED
        severity_bg = RED_LIGHT
        assessment = measured + (
            "Depths beyond 20 mm are commonly associated with deeper tissue "
            "involvement."
        )
        recs.append(("Depth beyond 20 mm",
            "Wounds of this depth are commonly reviewed by a podiatrist or wound-care "
            "specialist. In people with diabetes, deep wounds carry a raised risk of "
            "bone involvement."))
        recs.append(("Imaging sometimes used at this depth",
            "X-ray or MRI is sometimes used to look for osteomyelitis when a wound is "
            "this deep. Whether that applies here is a clinical judgement."))
    elif max_depth > 10:
        severity = "moderate"
        severity_label = "Intermediate — 10 to 20 mm"
        severity_color = colors.HexColor('#92400e')
        severity_bg = colors.HexColor('#fef3c7')
        assessment = measured + (
            "This range is commonly associated with moderate tissue involvement."
        )
        recs.append(("Typical monitoring interval",
            "Wounds in this range are commonly reassessed every 3-5 days. Signs "
            "commonly watched for include increased redness, warmth, swelling or "
            "purulent discharge."))
        recs.append(("Dressing and therapy options",
            "A moist wound-healing environment is commonly maintained, with dressings "
            "chosen for the exudate level. Negative pressure wound therapy is "
            "sometimes considered for volumes beyond about 2 cm³."))
    else:
        severity = "mild"
        severity_label = "Shallow — under 10 mm"
        severity_color = GREEN
        severity_bg = GREEN_LIGHT
        assessment = measured + (
            "This range is commonly associated with a superficial wound."
        )
        recs.append(("Typical management at this depth",
            "Wounds in this range are commonly managed with standard care: cleaning "
            "with saline and an appropriate dressing, with review at the next "
            "scheduled visit."))

    if surface_area > 10:
        recs.append(("Surface area beyond 10 cm²",
            f"A surface area of {surface_area:.2f} cm² is larger than typical for "
            "diabetic foot ulcers. Advanced therapies such as bioengineered skin "
            "substitutes or growth factors are sometimes considered at this size."))

    recs.extend(_general_notes())
    return severity, severity_label, severity_color, severity_bg, assessment, recs


def generate_report(scan_id, patient_name, patient_code, video_filename,
                    output_dir, measurements, template_dir=None, registration_rate=None,
                    render_iteration=15000, tissue=None, scale_calibrated=True):
    # build the full pdf report for a scan and save it to the output folder
    pdf_path = os.path.join(output_dir, "report.pdf")
    doc = SimpleDocTemplate(pdf_path, pagesize=A4,
                            rightMargin=1.8*cm, leftMargin=1.8*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)

    styles = getSampleStyleSheet()
    story = []

    # ── HEADER ──────────────────────────────────────────────────────
    header_data = [[
        Paragraph('<font color="white"><b>⚕ Wound-Splat</b></font><br/>'
                  '<font color="#9FE1CB" size="9">3D Wound Assessment Report</font>', styles['Normal']),
        Paragraph(f'<font color="white" size="9">Report generated<br/>'
                  f'<b>{datetime.now().strftime("%B %d, %Y")}</b><br/>'
                  f'Scan: {scan_id[:8]}...</font>', ParagraphStyle('r', alignment=TA_RIGHT))
    ]]
    header_table = Table(header_data, colWidths=[10*cm, 7.5*cm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), TEAL),
        ('PADDING', (0,0), (-1,-1), 14),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 0.5*cm))

    # ── SECTION HELPER ──────────────────────────────────────────────
    def section_title(text):
        # add a styled section heading to the report
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(f'<font color="#0F6E56"><b>{text.upper()}</b></font>',
                               ParagraphStyle('st', fontSize=10, spaceAfter=4)))
        story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL))
        story.append(Spacer(1, 0.2*cm))

    # ── PATIENT INFO ─────────────────────────────────────────────────
    section_title("Patient Information")
    info_data = [
        ['Patient Name', patient_name, 'Patient Code', patient_code],
        ['Assessment Date', datetime.now().strftime("%B %d, %Y"), 'Video File', video_filename],
        ['Reconstruction', '3D Gaussian Splatting', 'Status', 'Completed'],
    ]
    info_table = Table(info_data, colWidths=[4*cm, 6*cm, 3.5*cm, 4*cm])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), GRAY),
        ('TEXTCOLOR', (2,0), (2,-1), GRAY),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica-Bold'),
        ('FONTNAME', (3,0), (3,-1), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, LIGHT_GRAY]),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER),
    ]))
    story.append(info_table)

    # ── MEASUREMENTS ─────────────────────────────────────────────────
    section_title("Wound Measurements")
    surface_area = measurements.get("surface_area_cm2", 0)
    volume = measurements.get("volume_cm3", 0)
    max_depth = measurements.get("max_depth_mm", 0)
    width = measurements.get("width_cm", 0)
    height = measurements.get("height_cm", 0)

    metric_style = ParagraphStyle('m', fontSize=22, textColor=TEAL,
                                  fontName='Helvetica-Bold', alignment=TA_CENTER)
    unit_style = ParagraphStyle('u', fontSize=9, textColor=GRAY, alignment=TA_CENTER)
    label_style = ParagraphStyle('l', fontSize=8, textColor=colors.HexColor('#374151'),
                                 fontName='Helvetica-Bold', alignment=TA_CENTER)

    metrics_data = [[
        [Paragraph(f'{surface_area:.2f}', metric_style),
         Paragraph('cm²', unit_style),
         Paragraph('SURFACE AREA', label_style)],
        [Paragraph(f'{volume:.2f}', metric_style),
         Paragraph('cm³', unit_style),
         Paragraph('VOLUME', label_style)],
        [Paragraph(f'{max_depth:.1f}', metric_style),
         Paragraph('mm', unit_style),
         Paragraph('MAX DEPTH', label_style)],
    ]]
    metrics_table = Table(metrics_data, colWidths=[5.8*cm, 5.8*cm, 5.8*cm])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), TEAL_LIGHT),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#bbf7d0')),
        ('INNERGRID', (0,0), (-1,-1), 1, colors.HexColor('#bbf7d0')),
        ('PADDING', (0,0), (-1,-1), 14),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 0.2*cm))

    accuracy_display = f'{registration_rate:.1f}%' if registration_rate is not None else 'N/A'
    secondary_data = [
        ['Wound Width', f'{width:.2f} cm', 'Wound Height', f'{height:.2f} cm'],
        ['Reconstruction Quality', accuracy_display, 'Points Reconstructed', measurements.get("point_count", "N/A")],
    ]
    sec_table = Table(secondary_data, colWidths=[4*cm, 4*cm, 4*cm, 5.5*cm])
    sec_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), GRAY),
        ('TEXTCOLOR', (2,0), (2,-1), GRAY),
        ('FONTNAME', (1,0), (1,-1), 'Helvetica-Bold'),
        ('FONTNAME', (3,0), (3,-1), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0,0), (-1,-1), [colors.white, LIGHT_GRAY]),
        ('PADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, BORDER),
    ]))
    story.append(sec_table)

    # ── TISSUE COMPOSITION ───────────────────────────────────────────
    # Empty unless the scan has been through tissue analysis, which is a
    # separate user-triggered step after the pipeline finishes.
    story.extend(tissue_flowables(tissue))

    # ── RENDER IMAGES ────────────────────────────────────────────────
    renders_base = os.path.join(output_dir, "train")
    renders_dir = None
    if os.path.isdir(renders_base):
        candidates = sorted(glob.glob(os.path.join(renders_base, "ours_*", "renders")))
        if candidates:
            renders_dir = candidates[-1]
    if renders_dir and os.path.exists(renders_dir):
        section_title("3D Reconstructed Views")
        image_files = sorted(glob.glob(os.path.join(renders_dir, "*.png")))[:3]
        if image_files:
            img_cells = []
            for img_path in image_files:
                img_cells.append(Image(img_path, width=5.5*cm, height=4*cm))
            while len(img_cells) < 3:
                img_cells.append(Paragraph('No image', styles['Normal']))
            img_table = Table([img_cells], colWidths=[5.8*cm, 5.8*cm, 5.8*cm])
            img_table.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('PADDING', (0,0), (-1,-1), 4),
                ('BOX', (0,0), (-1,-1), 0.5, BORDER),
                ('INNERGRID', (0,0), (-1,-1), 0.5, BORDER),
            ]))
            story.append(img_table)

    # ── ASSESSMENT ───────────────────────────────────────────────────
    section_title("Clinical Assessment")
    severity, severity_label, severity_color, severity_bg, assessment, recs = \
        get_recommendation(surface_area, volume, max_depth, scale_calibrated)

    badge_data = [[Paragraph(f'<b>{severity_label}</b>',
                             ParagraphStyle('b', fontSize=10, textColor=severity_color,
                                           alignment=TA_CENTER))]]
    badge_table = Table(badge_data, colWidths=[17.5*cm])
    badge_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), severity_bg),
        ('PADDING', (0,0), (-1,-1), 8),
        ('BOX', (0,0), (-1,-1), 1, severity_color),
        ('ROUNDEDCORNERS', [6]),
    ]))
    story.append(badge_table)
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(assessment, ParagraphStyle('a', fontSize=9, leading=14,
                                                       textColor=colors.HexColor('#374151'))))

    # ── RECOMMENDATIONS ──────────────────────────────────────────────
    section_title("Recommendations")
    for title, body in recs:
        rec_data = [[
            Paragraph(f'<b>{title}</b><br/><font size="8" color="#78350f">{body}</font>',
                     ParagraphStyle('rec', fontSize=9, leading=13,
                                   textColor=colors.HexColor('#92400e')))
        ]]
        rec_table = Table(rec_data, colWidths=[17.5*cm])
        rec_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), AMBER_LIGHT),
            ('PADDING', (0,0), (-1,-1), 10),
            ('BOX', (0,0), (-1,-1), 0.5, AMBER),
            ('LEFTPADDING', (0,0), (-1,-1), 12),
        ]))
        story.append(rec_table)
        story.append(Spacer(1, 0.15*cm))

    # ── DISCLAIMER ───────────────────────────────────────────────────
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER))
    story.append(Spacer(1, 0.2*cm))
    accuracy_note = (
        f"Reconstruction quality for this scan was {registration_rate:.1f}% "
        "(based on the proportion of video frames successfully used in 3D reconstruction). "
        if registration_rate is not None else
        "Reconstruction quality for this scan could not be determined. "
    )
    disclaimer = (
        "<b>Disclaimer:</b> This report is generated automatically by the Wound-Splat 3D reconstruction system "
        "for monitoring purposes only. It is not a substitute for professional clinical diagnosis or treatment. "
        f"All measurements are estimates based on 3D Gaussian Splatting reconstruction. {accuracy_note}"
        "Please consult a qualified healthcare provider for clinical decisions."
    )
    story.append(Paragraph(disclaimer, ParagraphStyle('d', fontSize=8, textColor=GRAY, leading=12)))
    story.append(Spacer(1, 0.2*cm))
    story.append(Paragraph(
        "Wound-Splat v1.0 — GPU-Accelerated 3D Wound Monitoring System — Technological Institute of the Philippines",
        ParagraphStyle('f', fontSize=8, textColor=GRAY, alignment=TA_CENTER)
    ))

    doc.build(story)
    print(f"Report generated: {pdf_path}")
    return pdf_path


if __name__ == "__main__":
    from app.paths import GAUSSIAN_SPLATTING_DIR

    output_dir = GAUSSIAN_SPLATTING_DIR / "output" / "wound_test2"
    measurements = {
        "surface_area_cm2": 3.26,
        "volume_cm3": 0.27,
        "max_depth_mm": 7.36,
        "width_cm": 1.34,
        "height_cm": 1.79,
        "point_count": "12,450"
    }
    generate_report(
        scan_id="test-scan-001",
        patient_name="Juan dela Cruz",
        patient_code="PT-001",
        video_filename="wound_video.mp4",
        output_dir=str(output_dir),
        measurements=measurements
    )