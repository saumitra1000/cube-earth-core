from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
                                  Image, HRFlowable, PageBreak, KeepTogether)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from PIL import Image as PILImage

NAVY = colors.HexColor('#1A2332')
BLUE = colors.HexColor('#1E40AF')
BLUE_LIGHT = colors.HexColor('#EFF6FF')
BLUE_BORDER = colors.HexColor('#BFDBFE')
GREY = colors.HexColor('#64748B')
GREY_LIGHT = colors.HexColor('#F8FAFC')
GREEN = colors.HexColor('#16A34A')
RED = colors.HexColor('#DC2626')
BORDER = colors.HexColor('#E2E8F0')

styles = getSampleStyleSheet()
styles.add(ParagraphStyle('H1', fontSize=22, leading=25, fontName='Helvetica-Bold', textColor=NAVY, spaceAfter=3))
styles.add(ParagraphStyle('H2', fontSize=13, leading=16, fontName='Helvetica-Bold', textColor=NAVY, spaceBefore=10, spaceAfter=5))
styles.add(ParagraphStyle('Sub', fontSize=11, leading=15, fontName='Helvetica', textColor=GREY))
styles.add(ParagraphStyle('Body', fontSize=11, leading=14, fontName='Helvetica', textColor=colors.HexColor('#334155')))
styles.add(ParagraphStyle('Small', fontSize=9.5, leading=13, fontName='Helvetica', textColor=GREY))
styles.add(ParagraphStyle('TagLabel', fontSize=9, leading=12, fontName='Helvetica-Bold', textColor=BLUE))
styles.add(ParagraphStyle('BigStat', fontSize=19, leading=21, fontName='Helvetica-Bold', textColor=BLUE, alignment=TA_CENTER))
styles.add(ParagraphStyle('StatLabel', fontSize=9, leading=12, fontName='Helvetica', textColor=GREY, alignment=TA_CENTER))

doc = SimpleDocTemplate('sample-field-report.pdf', pagesize=A4,
                         topMargin=14*mm, bottomMargin=12*mm, leftMargin=16*mm, rightMargin=16*mm)
story = []

header_table = Table([[
    Paragraph('🛰️ <b>Cube Earth</b>', ParagraphStyle('Logo', fontSize=15, fontName='Helvetica-Bold', textColor=BLUE)),
    Paragraph('SAMPLE REPORT', ParagraphStyle('Tag', fontSize=8.5, fontName='Helvetica-Bold', textColor=colors.white, backColor=BLUE, alignment=TA_CENTER))
]], colWidths=[130*mm, 40*mm])
header_table.setStyle(TableStyle([
    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (1,0), (1,0), 'CENTER'),
    ('BACKGROUND', (1,0), (1,0), BLUE), ('TEXTCOLOR', (1,0), (1,0), colors.white),
    ('TOPPADDING', (1,0), (1,0), 3), ('BOTTOMPADDING', (1,0), (1,0), 3),
]))
story.append(header_table)
story.append(Spacer(1, 4*mm))
story.append(Paragraph('Field Intelligence Report', styles['H1']))
story.append(Paragraph('Parcel 54000 · Generated 27 July 2026 · LPIS 2024', styles['Sub']))
story.append(Spacer(1, 3*mm))
story.append(HRFlowable(width='100%', thickness=1, color=BORDER))
story.append(Spacer(1, 4*mm))

img_path = 'field_report_image_final.png'
pil_img = PILImage.open(img_path)
aspect = pil_img.height / pil_img.width
img_w = 170*mm
img_h = img_w * aspect
if img_h > 90*mm:
    img_h = 90*mm
    img_w = img_h / aspect
story.append(Image(img_path, width=img_w, height=img_h))
story.append(Paragraph('Selected parcel among surrounding mapped fields (illustrative)', styles['Small']))
story.append(Spacer(1, 5*mm))

story.append(Paragraph('Crop Detection', styles['H2']))
detect_table = Table([
    [Paragraph('SATELLITE ESTIMATE', styles['TagLabel']), Paragraph('LPIS DECLARATION (FARMER)', styles['TagLabel'])],
    [Paragraph('🌽 Maize', ParagraphStyle('CropBig', fontSize=16, fontName='Helvetica-Bold', textColor=NAVY)),
     Paragraph('🌾 Barley - Spring', ParagraphStyle('CropBig', fontSize=16, fontName='Helvetica-Bold', textColor=NAVY))],
    [Paragraph('Confidence: <b><font color="#16A34A">100%</font></b> 🟢 High', styles['Body']),
     Paragraph('Status: <b><font color="#DC2626">⚠ Satellite estimate differs</font></b>', styles['Body'])],
], colWidths=[85*mm, 85*mm])
detect_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), GREY_LIGHT), ('BOX', (0,0), (0,-1), 1, BORDER),
    ('BOX', (1,0), (1,-1), 1, colors.HexColor('#FECACA')), ('BACKGROUND', (1,0), (1,-1), colors.HexColor('#FEF2F2')),
    ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6),
]))
story.append(detect_table)
story.append(Spacer(1, 2*mm))
story.append(Paragraph('<i>This difference is presented as evidence for review, not as a determination that the declaration is incorrect — see Methodology for how differences are calculated.</i>', styles['Small']))
story.append(Spacer(1, 4*mm))

stats_data = [[Paragraph('1.6 ha', styles['BigStat']), Paragraph('Silking', styles['BigStat']),
               Paragraph('0.80', styles['BigStat']), Paragraph('5–15 Oct', styles['BigStat'])],
              [Paragraph('FIELD AREA', styles['StatLabel']), Paragraph('GROWTH STAGE (4/7)', styles['StatLabel']),
               Paragraph('NDVI (VEGETATION)', styles['StatLabel']), Paragraph('HARVEST WINDOW', styles['StatLabel'])]]
stats_table = Table(stats_data, colWidths=[42.5*mm]*4)
stats_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), BLUE_LIGHT), ('BOX', (0,0), (-1,-1), 1, BLUE_BORDER),
    ('LINEAFTER', (0,0), (2,-1), 0.5, BLUE_BORDER), ('TOPPADDING', (0,0), (-1,0), 7), ('BOTTOMPADDING', (0,1), (-1,1), 7),
]))
story.append(stats_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph('Growth Timeline', styles['H2']))
stages = ['Emergence','Vegetative','Tasselling','Silking','Grain Fill','Dough','Maturity']
stage_cells = []
for i, s in enumerate(stages):
    mark = '✓' if i < 3 else ('▶' if i == 3 else '')
    stage_cells.append(Paragraph(f'<font color="{"white" if i<=3 else "#94A3B8"}">{mark}</font><br/><font size=7.5>{s}</font>',
                                   ParagraphStyle('Stage', fontSize=9.5, alignment=TA_CENTER,
                                                  textColor=colors.white if i<=3 else GREY)))
stage_table = Table([stage_cells], colWidths=[24.3*mm]*7)
bgcolors = [GREEN if i<3 else (BLUE if i==3 else GREY_LIGHT) for i in range(7)]
style_cmds = [('VALIGN',(0,0),(-1,-1),'MIDDLE'), ('TOPPADDING',(0,0),(-1,-1),6), ('BOTTOMPADDING',(0,0),(-1,-1),6)]
for i, c in enumerate(bgcolors):
    style_cmds.append(('BACKGROUND', (i,0), (i,0), c))
stage_table.setStyle(TableStyle(style_cmds))
story.append(stage_table)
story.append(Spacer(1, 9*mm))

story.append(KeepTogether([Paragraph('NDVI Seasonal Profile', styles['H2']), Image('ndvi_chart.png', width=170*mm, height=55*mm)]))
story.append(Spacer(1, 4*mm))

story.append(Paragraph('Satellite Observations', styles['H2']))
obs_data = [
    ['NDVI (Vegetation)', '0.80', 'Dense canopy'],
    ['Soil Moisture (estimate)', 'Medium (29%)', 'Live, per-location — Open-Meteo'],
    ['Cloud cover (7-day)', '~45%', 'Affects imagery freshness'],
]
obs_table = Table([['Metric','Value','Note']] + obs_data, colWidths=[50*mm, 40*mm, 80*mm])
obs_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,0), NAVY), ('TEXTCOLOR', (0,0), (-1,0), colors.white),
    ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('FONTSIZE', (0,0), (-1,-1), 10.5),
    ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, GREY_LIGHT]),
    ('GRID', (0,0), (-1,-1), 0.5, BORDER), ('TOPPADDING', (0,0), (-1,-1), 5),
    ('BOTTOMPADDING', (0,0), (-1,-1), 5), ('LEFTPADDING', (0,0), (-1,-1), 8),
]))
story.append(obs_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph('7-Day Weather Forecast', styles['H2']))
wx_data = [[Paragraph('6 mm', styles['BigStat']), Paragraph('9–22°C', styles['BigStat']), Paragraph('20 km/h', styles['BigStat'])],
           [Paragraph('EXPECTED RAIN', styles['StatLabel']), Paragraph('TEMPERATURE RANGE', styles['StatLabel']), Paragraph('WIND', styles['StatLabel'])]]
wx_table = Table(wx_data, colWidths=[56.6*mm]*3)
wx_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), GREY_LIGHT), ('BOX', (0,0), (-1,-1), 1, BORDER),
    ('LINEAFTER', (0,0), (1,-1), 0.5, BORDER), ('TOPPADDING', (0,0), (-1,0), 6), ('BOTTOMPADDING', (0,1), (-1,1), 6),
]))
story.append(wx_table)
story.append(Spacer(1, 5*mm))

story.append(Paragraph('AI Insights', styles['H2']))
recs = [
    ('🔴', RED, colors.HexColor('#FEF2F2'), 'High confidence difference from LPIS',
     'Satellite strongly suggests Maize but the LPIS declaration is Barley - Spring. This parcel may warrant ground verification.'),
    ('🟢', GREEN, colors.HexColor('#F0FDF4'), 'Healthy crop',
     'Vegetation indices indicate good canopy development. No signs of stress detected from satellite data.'),
    ('🟢', GREEN, colors.HexColor('#F0FDF4'), 'Next satellite pass',
     'HLS revisit in approximately 4 days. Updated NDVI and vegetation maps will be available.'),
]
for icon, col, bg, title, body in recs:
    rec_table = Table([[Paragraph(f'{icon} <b>{title}</b><br/><font size=9.5 color="#475569">{body}</font>', styles['Body'])]], colWidths=[170*mm])
    rec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg), ('LINEBEFORE', (0,0), (0,-1), 3, col),
        ('TOPPADDING', (0,0), (-1,-1), 6), ('BOTTOMPADDING', (0,0), (-1,-1), 6), ('LEFTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(rec_table)
    story.append(Spacer(1, 1.5*mm))
story.append(Spacer(1, 4*mm))

story.append(Paragraph('Parcel Information', styles['H2']))
info_data = [
    ['Area', '1.6 ha (~4 acres)', 'Parcel ID', '54000'],
    ['Centroid Latitude', '53.1602°N', 'Centroid Longitude', '-7.0502°W'],
    ['Source', 'LPIS 2024', 'Data vintage', '2022–2025 (4 seasons)'],
]
info_table = Table(info_data, colWidths=[38*mm, 47*mm, 38*mm, 47*mm])
info_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (0,-1), GREY_LIGHT), ('BACKGROUND', (2,0), (2,-1), GREY_LIGHT),
    ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'), ('FONTNAME', (2,0), (2,-1), 'Helvetica-Bold'),
    ('FONTSIZE', (0,0), (-1,-1), 10.5), ('GRID', (0,0), (-1,-1), 0.5, BORDER),
    ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5), ('LEFTPADDING', (0,0), (-1,-1), 8),
]))
story.append(info_table)

story.append(PageBreak())

story.append(Paragraph('Methodology & Disclaimer', styles['H1']))
story.append(Spacer(1, 3*mm))
story.append(HRFlowable(width='100%', thickness=1, color=BORDER))
story.append(Spacer(1, 4*mm))

story.append(Paragraph('How this report was produced', styles['H2']))
story.append(Paragraph('This crop prediction is generated using a CatBoost machine learning model trained on 61,566 Irish tillage parcels from the LPIS 2024 dataset, using HLS (Harmonized Landsat Sentinel-2) satellite imagery — NDVI, EVI, NDWI, NDRE and NDII vegetation indices — across four growing seasons (2022–2025). The model achieves 77.05% balanced accuracy nationally on held-out validation data. Confidence scores are calibrated using isotonic regression so that the displayed percentage reflects genuine prediction reliability. Soil moisture is fetched live per-location from Open-Meteo at the time each parcel is viewed.', styles['Body']))
story.append(Spacer(1, 3*mm))

story.append(Paragraph('Reading confidence scores', styles['H2']))
conf_data = [
    ['🟢 High (80–100%)', 'Prediction is usually reliable.'],
    ['🟡 Medium (50–79%)', 'Similar crops may also fit the satellite signature.'],
    ['🔴 Low (<50%)', 'Use as a prompt for further review, not as a conclusion.'],
]
conf_table = Table(conf_data, colWidths=[55*mm, 115*mm])
conf_table.setStyle(TableStyle([
    ('FONTSIZE', (0,0), (-1,-1), 9.5), ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
    ('TOPPADDING', (0,0), (-1,-1), 5), ('BOTTOMPADDING', (0,0), (-1,-1), 5), ('LINEBELOW', (0,0), (-1,-2), 0.5, BORDER),
]))
story.append(conf_table)
story.append(Spacer(1, 3*mm))

story.append(Paragraph('Known limitations', styles['H2']))
for lim in [
    'Spring cereals (Barley, Oats, Wheat) are more easily confused with each other than with Maize or winter crops.',
    'Satellite observations are affected by cloud cover; confidence may decrease when limited clear imagery is available.',
    'Growth stage and harvest window are model estimates, not field-verified dates.',
    'The current model covers 8 tillage crop types only; grassland and other land uses are not classified.',
    'Soil moisture is a live estimate from weather-model data, not a direct field sensor reading.',
]:
    story.append(Paragraph(f'• {lim}', styles['Body']))
story.append(Spacer(1, 4*mm))

disclaimer_table = Table([[Paragraph('<b>Disclaimer:</b> Cube Earth provides decision-support information and should not be used as the sole basis for regulatory or contractual decisions without additional verification. A difference between satellite prediction and LPIS declaration does not, by itself, establish that either is incorrect.', styles['Small'])]], colWidths=[170*mm])
disclaimer_table.setStyle(TableStyle([
    ('BACKGROUND', (0,0), (-1,-1), GREY_LIGHT), ('BOX', (0,0), (-1,-1), 1, BORDER),
    ('TOPPADDING', (0,0), (-1,-1), 8), ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ('LEFTPADDING', (0,0), (-1,-1), 10), ('RIGHTPADDING', (0,0), (-1,-1), 10),
]))
story.append(disclaimer_table)
story.append(Spacer(1, 6*mm))

story.append(Paragraph('Contact: saumitra@cubed-earth.com', styles['Small']))
story.append(Paragraph('© 2026 Cube Earth. Built on HLS — Sentinel-2 (ESA/Copernicus) and Landsat (NASA/USGS) — and Ireland LPIS 2024 (DAFM Open Data).', styles['Small']))

doc.build(story)
print("Corrected report built successfully")
