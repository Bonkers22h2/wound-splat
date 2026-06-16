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

def get_recommendation(surface_area, volume, max_depth):
    recs = []
    if max_depth > 20:
        severity = "severe"
        severity_label = "Severe — Immediate Attention Required"
        severity_color = RED
        severity_bg = RED_LIGHT
        assessment = (
            f"The wound presents with a maximum depth of {max_depth:.1f}mm, surface area of {surface_area:.2f}cm², "
            f"and estimated volume of {volume:.2f}cm³. This depth indicates significant tissue involvement and "
            "requires urgent clinical evaluation. Immediate referral to a wound care specialist is strongly advised."
        )
        recs.append(("Urgent Referral Required",
            "The wound depth exceeds 20mm, indicating potential deep tissue or bone involvement. "
            "Immediate consultation with a podiatrist or wound care specialist is required within 24-48 hours."))
        recs.append(("Imaging Recommended",
            "Consider ordering X-ray or MRI to assess for osteomyelitis given the wound depth. "
            "Deep wounds in diabetic patients are at high risk for bone involvement."))
    elif max_depth > 10:
        severity = "moderate"
        severity_label = "Moderate — Close Monitoring Required"
        severity_color = colors.HexColor('#92400e')
        severity_bg = colors.HexColor('#fef3c7')
        assessment = (
            f"The wound presents with a maximum depth of {max_depth:.1f}mm, surface area of {surface_area:.2f}cm², "
            f"and estimated volume of {volume:.2f}cm³. This indicates moderate tissue involvement requiring "
            "regular monitoring and active wound care."
        )
        recs.append(("Increase Monitoring Frequency",
            "Schedule wound assessments every 3-5 days. Monitor for signs of infection including "
            "increased redness, warmth, swelling, or purulent discharge."))
        recs.append(("Wound Care Protocol",
            "Maintain moist wound healing environment. Apply appropriate dressings based on wound exudate level. "
            "Consider negative pressure wound therapy (NPWT) if wound volume exceeds 2cm³."))
    else:
        severity = "mild"
        severity_label = "Mild — Routine Monitoring"
        severity_color = GREEN
        severity_bg = GREEN_LIGHT
        assessment = (
            f"The wound presents with a maximum depth of {max_depth:.1f}mm, surface area of {surface_area:.2f}cm², "
            f"and estimated volume of {volume:.2f}cm³. This suggests a superficial wound manageable with "
            "standard wound care protocols."
        )
        recs.append(("Continue Standard Care",
            "Maintain current wound care regimen. Clean wound with saline solution and apply appropriate dressing. "
            "Monitor for any signs of deterioration at next scheduled visit."))

    if surface_area > 10:
        recs.append(("Large Wound Area",
            f"The wound surface area of {surface_area:.2f}cm² is above average for diabetic foot ulcers. "
            "Consider advanced wound therapies such as bioengineered skin substitutes or growth factor treatment."))

    recs.append(("Offloading Required",
        "Total contact casting or therapeutic footwear is recommended to reduce plantar pressure. "
        "Offloading is critical for healing diabetic foot ulcers and preventing recurrence."))
    recs.append(("Glycemic Control",
        "Maintain blood glucose levels within target range (HbA1c < 7%). Poor glycemic control significantly "
        "impairs wound healing and increases infection risk in diabetic patients."))
    recs.append(("Next 3D Assessment",
        "Schedule next 3D wound scan in 7-14 days to track volume change velocity. "
        "A reduction in volume of >20% per week indicates positive healing trajectory."))

    return severity, severity_label, severity_color, severity_bg, assessment, recs


def generate_report(scan_id, patient_name, patient_code, video_filename,
                    output_dir, measurements, template_dir=None, registration_rate=None,
                    render_iteration=15000):

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
        get_recommendation(surface_area, volume, max_depth)

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