from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
from datetime import datetime

def create_certificate_styles():
    """Create custom styles for certificate"""
    styles = getSampleStyleSheet()
    
    # Title style
    title_style = ParagraphStyle(
        'CertificateTitle',
        parent=styles['Heading1'],
        fontSize=36,
        textColor=colors.HexColor('#667eea'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    # Subtitle style
    subtitle_style = ParagraphStyle(
        'CertificateSubtitle',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=colors.grey,
        alignment=TA_CENTER,
        spaceAfter=30
    )
    
    # Content style
    content_style = ParagraphStyle(
        'CertificateContent',
        parent=styles['Normal'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=15
    )
    
    # Name style
    name_style = ParagraphStyle(
        'StudentName',
        parent=styles['Normal'],
        fontSize=24,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )
    
    # Hours style
    hours_style = ParagraphStyle(
        'Hours',
        parent=styles['Normal'],
        fontSize=20,
        textColor=colors.HexColor('#667eea'),
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )
    
    return {
        'title': title_style,
        'subtitle': subtitle_style,
        'content': content_style,
        'name': name_style,
        'hours': hours_style
    }

def generate_certificate_pdf(student_name: str, total_hours: float, events_count: int) -> bytes:
    """Generate PDF certificate for student"""
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )
    
    # Get styles
    styles = create_certificate_styles()
    
    # Create content
    story = []
    
    # Title
    story.append(Paragraph("СЕРТИФИКАТ", styles['title']))
    story.append(Paragraph("Alumni Club Connect", styles['subtitle']))
    story.append(Spacer(1, 0.5*inch))
    
    # Content
    story.append(Paragraph("Настоящим подтверждается, что", styles['content']))
    story.append(Spacer(1, 0.3*inch))
    
    # Student name
    story.append(Paragraph(f"<u>{student_name}</u>", styles['name']))
    story.append(Spacer(1, 0.3*inch))
    
    # Achievement text
    story.append(Paragraph(
        "успешно завершил(а) программу общественной активности,", 
        styles['content']
    ))
    story.append(Paragraph(
        f"накопив <b>{int(total_hours)} часов</b>", 
        styles['hours']
    ))
    story.append(Paragraph(
        "волонтерской и социальной деятельности", 
        styles['content']
    ))
    story.append(Spacer(1, 0.3*inch))
    
    # Events count
    story.append(Paragraph(
        f"Количество посещенных мероприятий: <b>{events_count}</b>", 
        styles['content']
    ))
    story.append(Spacer(1, 0.5*inch))
    
    # Footer
    story.append(Paragraph(
        f"Дата выдачи: {datetime.now().strftime('%d.%m.%Y')}", 
        styles['content']
    ))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        "Alumni Club Connect Platform<br/>Автоматически сгенерированный сертификат", 
        styles['content']
    ))
    
    # Build PDF
    doc.build(story)
    
    # Get PDF bytes
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes

def send_certificate_email(student_email: str, student_name: str, pdf_bytes: bytes):
    """Send certificate via email"""
    # Email configuration (you should use environment variables in production)
    SMTP_SERVER = "smtp.gmail.com"
    SMTP_PORT = 587
    EMAIL_USER = "your_email@gmail.com"  # Change this
    EMAIL_PASSWORD = "your_app_password"  # Change this
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USER
        msg['To'] = student_email
        msg['Subject'] = "Поздравляем! Ваш сертификат Alumni Club Connect"
        
        # Email body
        body = f"""
        Уважаемый(ая) {student_name}!

        Поздравляем с успешным завершением программы общественной активности!

        Вы накопили 300+ часов волонтерской и социальной деятельности.
        
        Ваш сертификат прикреплен к этому письму.

        С уважением,
        Команда Alumni Club Connect
        """
        
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Attach PDF
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header(
            'Content-Disposition',
            f'attachment; filename="certificate_{student_name.replace(" ", "_")}.pdf"'
        )
        msg.attach(part)
        
        # Send email
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_USER, student_email, text)
        server.quit()
        
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False
