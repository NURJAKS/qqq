import streamlit as st
import sqlite3
import hashlib
import jwt
import qrcode
import io
import base64
from datetime import datetime, timedelta
import pandas as pd
from PIL import Image
import cv2
import numpy as np
from pyzbar import pyzbar
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os
import uuid

# Configuration
SECRET_KEY = st.secrets.get("SECRET_KEY", "alumni_club_secret_key_for_demo")
DATABASE_PATH = "alumni_club.db"

# Initialize database
def init_database():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            total_hours REAL DEFAULT 0.0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create events table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            date TIMESTAMP NOT NULL,
            duration REAL NOT NULL,
            organizer_id INTEGER,
            qr_code_data TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (organizer_id) REFERENCES users (id)
        )
    ''')
    
    # Create participation table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS participation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            event_id INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            hours_awarded REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (event_id) REFERENCES events (id),
            UNIQUE(user_id, event_id)
        )
    ''')
    
    conn.commit()
    conn.close()

# Authentication functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    return hash_password(password) == hashed

def create_token(email):
    payload = {
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload['email']
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

# Database functions
def register_user(name, email, password, role):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        password_hash = hash_password(password)
        cursor.execute(
            "INSERT INTO users (name, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (name, email, password_hash, role)
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def authenticate_user(email, password):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    if user and verify_password(password, user[3]):
        return {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'role': user[4],
            'total_hours': user[5]
        }
    return None

def get_user_by_email(email):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'role': user[4],
            'total_hours': user[5]
        }
    return None

# QR Code functions
def generate_qr_code(event_id):
    qr_data = f"alumni_club_event_{event_id}_{uuid.uuid4().hex[:8]}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return qr_data, img_str

def decode_qr_from_image(image_data):
    try:
        if isinstance(image_data, bytes):
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            img = np.array(image_data)
        
        decoded_objects = pyzbar.decode(img)
        
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
        return None
    except Exception as e:
        st.error(f"Ошибка декодирования QR: {e}")
        return None

# Event functions
def create_event(name, description, date, duration, organizer_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Generate QR code data
    temp_id = int(datetime.now().timestamp())
    qr_data, qr_image = generate_qr_code(temp_id)
    
    cursor.execute(
        "INSERT INTO events (name, description, date, duration, organizer_id, qr_code_data) VALUES (?, ?, ?, ?, ?, ?)",
        (name, description, date, duration, organizer_id, qr_data)
    )
    
    event_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return event_id, qr_data, qr_image

def get_events():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT e.*, u.name as organizer_name 
        FROM events e 
        JOIN users u ON e.organizer_id = u.id
        ORDER BY e.date DESC
    ''')
    
    events = cursor.fetchall()
    conn.close()
    return events

def get_user_events(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM events WHERE organizer_id = ? ORDER BY date DESC", (user_id,))
    events = cursor.fetchall()
    conn.close()
    return events

def participate_in_event(user_id, qr_data):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Find event by QR data
    cursor.execute("SELECT * FROM events WHERE qr_code_data = ?", (qr_data,))
    event = cursor.fetchone()
    
    if not event:
        conn.close()
        return False, "Мероприятие не найдено"
    
    # Check if already participated
    cursor.execute("SELECT * FROM participation WHERE user_id = ? AND event_id = ?", (user_id, event[0]))
    existing = cursor.fetchone()
    
    if existing:
        conn.close()
        return False, "Вы уже участвовали в этом мероприятии"
    
    # Add participation
    cursor.execute(
        "INSERT INTO participation (user_id, event_id, hours_awarded) VALUES (?, ?, ?)",
        (user_id, event[0], event[4])  # event[4] is duration
    )
    
    # Update user total hours
    cursor.execute(
        "UPDATE users SET total_hours = total_hours + ? WHERE id = ?",
        (event[4], user_id)
    )
    
    conn.commit()
    conn.close()
    
    return True, f"Участие засчитано! Получено {event[4]} часов"

def get_user_participations(user_id):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT p.*, e.name as event_name, e.date as event_date
        FROM participation p
        JOIN events e ON p.event_id = e.id
        WHERE p.user_id = ?
        ORDER BY p.timestamp DESC
    ''', (user_id,))
    
    participations = cursor.fetchall()
    conn.close()
    return participations

# PDF Certificate generation
def create_certificate_styles():
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CertificateTitle',
        parent=styles['Heading1'],
        fontSize=36,
        textColor=colors.HexColor('#667eea'),
        alignment=TA_CENTER,
        spaceAfter=20
    )
    
    content_style = ParagraphStyle(
        'CertificateContent',
        parent=styles['Normal'],
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=15
    )
    
    name_style = ParagraphStyle(
        'StudentName',
        parent=styles['Normal'],
        fontSize=24,
        textColor=colors.black,
        alignment=TA_CENTER,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )
    
    return {'title': title_style, 'content': content_style, 'name': name_style}

def generate_certificate_pdf(student_name, total_hours, events_count):
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch
    )
    
    styles = create_certificate_styles()
    story = []
    
    story.append(Paragraph("СЕРТИФИКАТ", styles['title']))
    story.append(Paragraph("Alumni Club Connect", styles['content']))
    story.append(Spacer(1, 0.5*inch))
    
    story.append(Paragraph("Настоящим подтверждается, что", styles['content']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph(f"<u>{student_name}</u>", styles['name']))
    story.append(Spacer(1, 0.3*inch))
    
    story.append(Paragraph(
        f"успешно завершил(а) программу общественной активности, накопив <b>{int(total_hours)} часов</b>",
        styles['content']
    ))
    
    story.append(Paragraph(
        f"Количество мероприятий: <b>{events_count}</b>",
        styles['content']
    ))
    
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        f"Дата выдачи: {datetime.now().strftime('%d.%m.%Y')}",
        styles['content']
    ))
    
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes

# Streamlit App
def main():
    st.set_page_config(
        page_title="Alumni Club Connect",
        page_icon="🎓",
        layout="wide"
    )
    
    # Initialize database
    init_database()
    
    # Session state
    if 'token' not in st.session_state:
        st.session_state.token = None
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    # Check authentication
    if st.session_state.token:
        email = verify_token(st.session_state.token)
        if email:
            st.session_state.user = get_user_by_email(email)
        else:
            st.session_state.token = None
            st.session_state.user = None
    
    # Sidebar
    with st.sidebar:
        if st.session_state.user:
            st.write(f"**{st.session_state.user['name']}**")
            st.write(f"Роль: {st.session_state.user['role']}")
            st.write(f"Часов: {st.session_state.user['total_hours']}")
            
            if st.button("Выйти"):
                st.session_state.token = None
                st.session_state.user = None
                st.rerun()
        else:
            st.write("Войдите в систему")
    
    # Main content
    if not st.session_state.user:
        login_page()
    else:
        if st.session_state.user['role'] == 'student':
            student_dashboard()
        elif st.session_state.user['role'] == 'organizer':
            organizer_dashboard()

def login_page():
    st.title("🎓 Alumni Club Connect")
    st.markdown("### Система учёта общественных часов студентов")
    
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    
    with tab1:
        st.subheader("Войти в систему")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Пароль", type="password", key="login_password")
        
        if st.button("Войти"):
            if email and password:
                user = authenticate_user(email, password)
                if user:
                    st.session_state.token = create_token(email)
                    st.session_state.user = user
                    st.success("Успешный вход!")
                    st.rerun()
                else:
                    st.error("Неверный email или пароль")
    
    with tab2:
        st.subheader("Регистрация")
        name = st.text_input("Имя")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Пароль", type="password", key="reg_password")
        role = st.selectbox("Роль", ["student", "organizer"], 
                           format_func=lambda x: "Студент" if x == "student" else "Организатор")
        
        if st.button("Зарегистрироваться"):
            if name and email and password:
                if register_user(name, email, password, role):
                    st.success("Регистрация успешна! Войдите в систему.")
                else:
                    st.error("Email уже используется")

def student_dashboard():
    st.title(f"👋 Добро пожаловать, {st.session_state.user['name']}!")
    
    # Progress
    total_hours = st.session_state.user['total_hours']
    progress = min(total_hours / 300, 1.0)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Накоплено часов", f"{total_hours:.1f}")
    with col2:
        st.metric("Прогресс", f"{progress*100:.1f}%")
    with col3:
        st.metric("До сертификата", f"{max(300-total_hours, 0):.1f} ч")
    
    st.progress(progress)
    
    # QR Code scanning
    st.subheader("📱 Сканирование QR-кода")
    
    tab1, tab2 = st.tabs(["Загрузить изображение", "Ввести данные"])
    
    with tab1:
        uploaded_file = st.file_uploader("Загрузите изображение с QR-кодом", 
                                       type=['png', 'jpg', 'jpeg'])
        
        if uploaded_file and st.button("Сканировать QR-код"):
            image_data = uploaded_file.read()
            qr_data = decode_qr_from_image(image_data)
            
            if qr_data and qr_data.startswith("alumni_club_event_"):
                success, message = participate_in_event(st.session_state.user['id'], qr_data)
                if success:
                    st.success(message)
                    # Update user info
                    st.session_state.user = get_user_by_email(st.session_state.user['email'])
                    
                    # Check for certificate
                    if st.session_state.user['total_hours'] >= 300:
                        st.balloons()
                        st.success("🎉 Поздравляем! Вы достигли 300 часов!")
                        
                        # Generate certificate
                        participations = get_user_participations(st.session_state.user['id'])
                        pdf_bytes = generate_certificate_pdf(
                            st.session_state.user['name'],
                            st.session_state.user['total_hours'],
                            len(participations)
                        )
                        
                        st.download_button(
                            label="📄 Скачать сертификат",
                            data=pdf_bytes,
                            file_name=f"certificate_{st.session_state.user['name']}.pdf",
                            mime="application/pdf"
                        )
                    
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Неверный QR-код")
    
    with tab2:
        qr_data = st.text_input("Введите данные QR-кода")
        if qr_data and st.button("Подтвердить участие"):
            if qr_data.startswith("alumni_club_event_"):
                success, message = participate_in_event(st.session_state.user['id'], qr_data)
                if success:
                    st.success(message)
                    st.session_state.user = get_user_by_email(st.session_state.user['email'])
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Неверный формат QR-кода")
    
    # History
    st.subheader("📊 История участия")
    participations = get_user_participations(st.session_state.user['id'])
    
    if participations:
        df = pd.DataFrame(participations, columns=[
            'id', 'user_id', 'event_id', 'timestamp', 'hours_awarded', 'event_name', 'event_date'
        ])
        st.dataframe(df[['event_name', 'event_date', 'hours_awarded', 'timestamp']])
    else:
        st.info("Пока нет участий в мероприятиях")

def organizer_dashboard():
    st.title(f"👋 Добро пожаловать, {st.session_state.user['name']}!")
    
    tab1, tab2 = st.tabs(["Создать мероприятие", "Мои мероприятия"])
    
    with tab1:
        st.subheader("➕ Создать новое мероприятие")
        
        name = st.text_input("Название мероприятия")
        description = st.text_area("Описание")
        event_date = st.date_input("Дата мероприятия")
        event_time = st.time_input("Время мероприятия")
        duration = st.number_input("Продолжительность (часы)", min_value=0.5, max_value=24.0, step=0.5)
        
        if st.button("Создать мероприятие"):
            if name and event_date and duration:
                event_datetime = datetime.combine(event_date, event_time)
                event_id, qr_data, qr_image = create_event(
                    name, description, event_datetime.isoformat(), 
                    duration, st.session_state.user['id']
                )
                
                st.success("Мероприятие создано успешно!")
                
                # Display QR code
                qr_img_data = base64.b64decode(qr_image)
                st.image(qr_img_data, caption="QR-код для сканирования")
                
                st.download_button(
                    label="Скачать QR-код",
                    data=qr_img_data,
                    file_name=f"qr_code_{event_id}.png",
                    mime="image/png"
                )
                
                st.code(f"Данные QR-кода: {qr_data}")
    
    with tab2:
        st.subheader("📅 Мои мероприятия")
        events = get_user_events(st.session_state.user['id'])
        
        if events:
            for event in events:
                with st.expander(f"{event[1]} - {event[3][:10]}"):
                    st.write(f"**Описание:** {event[2] or 'Нет описания'}")
                    st.write(f"**Дата:** {event[3]}")
                    st.write(f"**Продолжительность:** {event[4]} часов")
                    
                    # Show participants
                    conn = sqlite3.connect(DATABASE_PATH)
                    cursor = conn.cursor()
                    cursor.execute('''
                        SELECT u.name, u.email, p.timestamp, p.hours_awarded
                        FROM participation p
                        JOIN users u ON p.user_id = u.id
                        WHERE p.event_id = ?
                    ''', (event[0],))
                    participants = cursor.fetchall()
                    conn.close()
                    
                    if participants:
                        st.write(f"**Участников:** {len(participants)}")
                        df = pd.DataFrame(participants, columns=['Имя', 'Email', 'Время участия', 'Часов'])
                        st.dataframe(df)
                    else:
                        st.info("Пока нет участников")
        else:
            st.info("Пока нет созданных мероприятий")

if __name__ == "__main__":
    main()
