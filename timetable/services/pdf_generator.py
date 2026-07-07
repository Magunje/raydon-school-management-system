import io
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.units import mm
from school_system_django.native import get_pdf_header

class TimetablePDFGenerator:
    @staticmethod
    def generate_timetable_pdf(title, subtitle, timetable_rows, periods, school_settings, response_stream):
        """
        Generates a beautifully formatted landscape PDF timetable.
        - timetable_rows: list of dicts:
            {
                'day_name': 'Monday',
                'cells': [
                    { 'subject_name': 'Mathematics', 'teacher_name': 'Mr Moyo', 'room_name': 'Room 1A', 'is_locked': False },
                    # or None / Break dictionary
                ]
            }
        - periods: list of TimetablePeriodConfig or period dictionaries (period_no, start_time, end_time, period_type, label)
        - response_stream: file-like object (HttpResponse or BytesIO) to write the PDF to.
        """
        # A4 Landscape width is 841.89 points, height is 595.27 points
        # Margins: 10mm (approx 28.3 points)
        doc = SimpleDocTemplate(
            response_stream,
            pagesize=landscape(A4),
            leftMargin=10 * mm,
            rightMargin=10 * mm,
            topMargin=10 * mm,
            bottomMargin=10 * mm
        )

        width_pts = doc.width  # printable width (approx 785 pts)
        styles = getSampleStyleSheet()

        # Styles definition
        title_style = ParagraphStyle(
            'TimetableTitle',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=16,
            textColor=colors.HexColor('#0f766e'), # Teal
            spaceAfter=5
        )
        
        subtitle_style = ParagraphStyle(
            'TimetableSubtitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#475569'),
            spaceAfter=15
        )

        cell_header_style = ParagraphStyle(
            'TimetableHeaderCell',
            fontName='Helvetica-Bold',
            fontSize=8,
            leading=10,
            textColor=colors.white,
            alignment=1 # Centered
        )

        cell_body_style = ParagraphStyle(
            'TimetableBodyCell',
            fontName='Helvetica-Bold',
            fontSize=7,
            leading=9,
            textColor=colors.HexColor('#1e293b'),
            alignment=1 # Centered
        )

        cell_body_small_style = ParagraphStyle(
            'TimetableBodyCellSmall',
            fontName='Helvetica',
            fontSize=6,
            leading=8,
            textColor=colors.HexColor('#64748b'),
            alignment=1 # Centered
        )

        cell_break_style = ParagraphStyle(
            'TimetableBreakCell',
            fontName='Helvetica-BoldOblique',
            fontSize=9,
            leading=11,
            textColor=colors.HexColor('#475569'),
            alignment=1 # Centered
        )

        elements = []

        # 1. School Header
        header_table = get_pdf_header(school_settings, width_pts)
        elements.append(header_table)
        elements.append(Spacer(1, 10))

        # 2. Titles
        elements.append(Paragraph(title, title_style))
        elements.append(Paragraph(subtitle, subtitle_style))

        # 3. Timetable Grid Construction
        # Headers: ["Day", "08:00 - 08:40\nPeriod 1", ...]
        headers = [Paragraph("<b>Day</b>", cell_header_style)]
        for p in periods:
            p_label = p.label or (f"Period {p.period_no}" if p.period_type == 'Lesson' else p.period_type)
            headers.append(Paragraph(f"<b>{p.start_time} - {p.end_time}</b><br/>{p_label}", cell_header_style))

        table_data = [headers]

        # Row styling attributes
        # We will dynamically build table styles depending on cell contents (breaks/lunches)
        t_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')), # Teal Header
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#0f766e')),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]

        for row_idx, row in enumerate(timetable_rows):
            pdf_row = [Paragraph(f"<b>{row['day_name']}</b>", cell_body_style)]
            
            for col_idx, cell in enumerate(row['cells']):
                actual_row_idx = row_idx + 1 # offset header row
                actual_col_idx = col_idx + 1 # offset day name column
                
                # Check period type for the corresponding config
                p_config = periods[col_idx]
                
                if p_config.period_type in ['Break', 'Lunch']:
                    # Style cell as Break/Lunch
                    cell_label = p_config.label or p_config.period_type
                    pdf_row.append(Paragraph(cell_label.upper(), cell_break_style))
                    t_style.append(('BACKGROUND', (actual_col_idx, actual_row_idx), (actual_col_idx, actual_row_idx), colors.HexColor('#f1f5f9')))
                else:
                    if cell:
                        subject = cell.get('subject_name', '')
                        teacher = cell.get('teacher_name', '') or ''
                        room = cell.get('room_name', '') or ''
                        extra = cell.get('extra_label', '') # E.g. class name if teacher timetable
                        
                        cell_content = f"<b>{subject}</b>"
                        if extra:
                            cell_content += f"<br/>{extra}"
                        if teacher:
                            cell_content += f"<br/>{teacher}"
                        if room:
                            cell_content += f"<br/>({room})"
                            
                        pdf_row.append(Paragraph(cell_content, cell_body_style))
                        
                        # Soft background color for scheduled slots
                        t_style.append(('BACKGROUND', (actual_col_idx, actual_row_idx), (actual_col_idx, actual_row_idx), colors.HexColor('#f8fafc')))
                    else:
                        pdf_row.append(Paragraph("-", cell_body_small_style))
                        t_style.append(('BACKGROUND', (actual_col_idx, actual_row_idx), (actual_col_idx, actual_row_idx), colors.white))
                        
            table_data.append(pdf_row)

        # Columns widths distribution
        # Day column gets approx 75pts. Remaining space split evenly
        col_count = len(periods) + 1
        rem_width = width_pts - 75
        col_widths = [75] + [rem_width / (col_count - 1)] * (col_count - 1)

        grid_table = Table(table_data, colWidths=col_widths, repeatRows=1)
        grid_table.setStyle(TableStyle(t_style))
        elements.append(grid_table)

        # Build PDF
        doc.build(elements)
