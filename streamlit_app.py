import streamlit as st
import pandas as pd
import qrcode
import io
import base64
from PIL import Image
from datetime import datetime, date, time
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from passlib.context import CryptContext
import uuid
import numpy as np
import cv2
from pyzbar import pyzbar
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER

# --- DB Setup ---
Base = declarative_base()
DB_PATH = "sqlite:///alumni_club.db"
engine = sa.create_engine(DB_PATH, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)

# --- Password Hashing ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def hash_password(password):
    return pwd_context.hash(password)
def verify_password(plain, hashed):
    return pwd_context.verify(plain, hashed)

# --- Models ---
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # student, organizer
    total_hours = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    events = relationship("Event", back_populates="organizer")
    participations = relationship("Participation", back_populates="user")

class Event(Base):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    date = Column(DateTime, nullable=False)
    duration = Column(Float, nullable=False)
    organizer_id = Column(Integer, ForeignKey("users.id"))
    qr_code_data = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    organizer = relationship("User", back_populates="events")
    participations = relationship("Participation", back_populates="event")

class Participation(Base):
    __tablename__ = "participation"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    event_id = Column(Integer, ForeignKey("events.id"))
    timestamp = Column(DateTime, default=datetime.utcnow)
    hours_awarded = Column(Float, nullable=False)
    user = relationship("User", back_populates="participations")
    event = relationship("Event", back_populates="participations")

Base.metadata.create_all(engine)

# --- QR utils ---
def generate_qr_code(event_id):
    qr_data = f"alumni_club_event_{event_id}_{uuid.uuid4().hex[:8]}"
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=4)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    img_bytes = buf.getvalue()
    img_b64 = base64.b64encode(img_bytes).decode()
    return qr_data, img_b64, img_bytes

def decode_qr_from_image(image_data):
    try:
        nparr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        decoded = pyzbar.decode(img)
        if decoded:
            return decoded[0].data.decode('utf-8')
        return None
    except Exception:
        return None

def validate_qr_data(qr_data):
    return qr_data and qr_data.startswith("alumni_club_event_")

# --- PDF Certificate ---
def create_certificate_pdf(student_name, total_hours, events_count):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CertificateTitle', parent=styles['Heading1'], fontSize=36, textColor=colors.HexColor('#667eea'), alignment=TA_CENTER, spaceAfter=20)
    subtitle_style = ParagraphStyle('CertificateSubtitle', parent=styles['Heading2'], fontSize=18, textColor=colors.grey, alignment=TA_CENTER, spaceAfter=30)
    content_style = ParagraphStyle('CertificateContent', parent=styles['Normal'], fontSize=14, alignment=TA_CENTER, spaceAfter=15)
    name_style = ParagraphStyle('StudentName', parent=styles['Normal'], fontSize=24, textColor=colors.black, alignment=TA_CENTER, spaceAfter=20, fontName='Helvetica-Bold')
    hours_style = ParagraphStyle('Hours', parent=styles['Normal'], fontSize=20, textColor=colors.HexColor('#667eea'), alignment=TA_CENTER, spaceAfter=20, fontName='Helvetica-Bold')
    story = []
    story.append(Paragraph("СЕРТИФИКАТ", title_style))
    story.append(Paragraph("Alumni Club Connect", subtitle_style))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph("Настоящим подтверждается, что", content_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"<u>{student_name}</u>", name_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph("успешно завершил(а) программу общественной активности,", content_style))
    story.append(Paragraph(f"накопив <b>{int(total_hours)} часов</b>", hours_style))
    story.append(Paragraph("волонтерской и социальной деятельности", content_style))
    story.append(Spacer(1, 0.3*inch))
    story.append(Paragraph(f"Количество посещенных мероприятий: <b>{events_count}</b>", content_style))
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(f"Дата выдачи: {datetime.now().strftime('%d.%m.%Y')}", content_style))
    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("Alumni Club Connect Platform<br/>Автоматически сгенерированный сертификат", content_style))
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

# --- Streamlit App ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def register_user(name, email, password, role):
    with SessionLocal() as db:
        if db.query(User).filter(User.email == email).first():
            return False, "Email уже зарегистрирован"
        user = User(name=name, email=email, password_hash=hash_password(password), role=role)
        db.add(user)
        db.commit()
        return True, "Регистрация успешна!"

def authenticate(email, password):
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        if user and verify_password(password, user.password_hash):
            return user
        return None

def get_user_by_id(user_id):
    with SessionLocal() as db:
        return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(email):
    with SessionLocal() as db:
        return db.query(User).filter(User.email == email).first()

def create_event(name, description, event_date, duration, organizer_id):
    with SessionLocal() as db:
        event = Event(name=name, description=description, date=event_date, duration=duration, organizer_id=organizer_id)
        db.add(event)
        db.commit()
        db.refresh(event)
        qr_data, qr_b64, qr_bytes = generate_qr_code(event.id)
        event.qr_code_data = qr_data
        db.commit()
        return event, qr_b64, qr_data, qr_bytes

def get_events():
    with SessionLocal() as db:
        return db.query(Event).all()

def get_my_events(organizer_id):
    with SessionLocal() as db:
        return db.query(Event).filter(Event.organizer_id == organizer_id).all()

def get_event_by_qr(qr_data):
    with SessionLocal() as db:
        return db.query(Event).filter(Event.qr_code_data == qr_data).first()

def get_participation(user_id, event_id):
    with SessionLocal() as db:
        return db.query(Participation).filter(Participation.user_id == user_id, Participation.event_id == event_id).first()

def add_participation(user_id, event_id, hours):
    with SessionLocal() as db:
        participation = Participation(user_id=user_id, event_id=event_id, hours_awarded=hours)
        db.add(participation)
        user = db.query(User).filter(User.id == user_id).first()
        user.total_hours += hours
        db.commit()
        return participation

def get_my_participations(user_id):
    with SessionLocal() as db:
        participations = db.query(Participation).filter(Participation.user_id == user_id).all()
        result = []
        for p in participations:
            event = db.query(Event).filter(Event.id == p.event_id).first()
            result.append({
                "event_name": event.name,
                "event_date": event.date,
                "hours_awarded": p.hours_awarded,
                "timestamp": p.timestamp
            })
        return result

def get_event_participants(event_id):
    with SessionLocal() as db:
        participations = db.query(Participation).filter(Participation.event_id == event_id).all()
        result = []
        for p in participations:
            user = db.query(User).filter(User.id == p.user_id).first()
            result.append({
                "user_name": user.name,
                "user_email": user.email,
                "timestamp": p.timestamp,
                "hours_awarded": p.hours_awarded
            })
        return result

def count_events_participated(user_id):
    with SessionLocal() as db:
        return db.query(Participation).filter(Participation.user_id == user_id).count()

# --- Streamlit UI ---
st.set_page_config(page_title="Alumni Club Connect", page_icon="🎓", layout="wide")

if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'role' not in st.session_state:
    st.session_state.role = None
if 'name' not in st.session_state:
    st.session_state.name = None
if 'email' not in st.session_state:
    st.session_state.email = None

def login_page():
    st.title("🎓 Alumni Club Connect")
    st.markdown("### Система учёта общественных часов студентов")
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    with tab1:
        st.subheader("Войти в систему")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Пароль", type="password", key="login_password")
        if st.button("Войти", key="login_btn"):
            user = authenticate(email, password)
            if user:
                st.session_state.user_id = user.id
                st.session_state.role = user.role
                st.session_state.name = user.name
                st.session_state.email = user.email
                st.success("Успешный вход!")
                st.rerun()
            else:
                st.error("Неверный email или пароль")
    with tab2:
        st.subheader("Регистрация")
        name = st.text_input("Имя", key="reg_name")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Пароль", type="password", key="reg_password")
        role = st.selectbox("Роль", ["student", "organizer"], format_func=lambda x: "Студент" if x=="student" else "Организатор")
        if st.button("Зарегистрироваться", key="reg_btn"):
            ok, msg = register_user(name, email, password, role)
            if ok:
                st.success(msg)
            else:
                st.error(msg)

def student_dashboard():
    user = get_user_by_id(st.session_state.user_id)
    st.title(f"👋 Добро пожаловать, {user.name}!")
    total_hours = user.total_hours
    progress = min(total_hours / 300, 1.0)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Накоплено часов", f"{total_hours:.1f}")
    with col2:
        st.metric("Прогресс", f"{progress*100:.1f}%")
    with col3:
        st.metric("До сертификата", f"{max(300-total_hours, 0):.1f} ч")
    st.progress(progress)
    st.subheader("📱 Сканирование QR-кода")
    tab1, tab2 = st.tabs(["Загрузить изображение", "Ввести данные"])
    with tab1:
        uploaded_file = st.file_uploader("Загрузите изображение с QR-кодом", type=['png', 'jpg', 'jpeg'])
        if uploaded_file and st.button("Сканировать QR-код"):
            qr_data = decode_qr_from_image(uploaded_file.read())
            if not qr_data:
                st.error("QR-код не найден или невалиден")
            elif not validate_qr_data(qr_data):
                st.error("QR-код не от Alumni Club Connect")
            else:
                event = get_event_by_qr(qr_data)
                if not event:
                    st.error("Мероприятие не найдено")
                elif get_participation(user.id, event.id):
                    st.error("Вы уже участвовали в этом мероприятии")
                else:
                    add_participation(user.id, event.id, event.duration)
                    st.success(f"Участие в {event.name} подтверждено! Получено часов: {event.duration}")
                    st.balloons()
                    st.rerun()
    with tab2:
        qr_data = st.text_input("Введите данные QR-кода")
        if qr_data and st.button("Подтвердить участие"):
            if not validate_qr_data(qr_data):
                st.error("QR-код не от Alumni Club Connect")
            else:
                event = get_event_by_qr(qr_data)
                if not event:
                    st.error("Мероприятие не найдено")
                elif get_participation(user.id, event.id):
                    st.error("Вы уже участвовали в этом мероприятии")
                else:
                    add_participation(user.id, event.id, event.duration)
                    st.success(f"Участие в {event.name} подтверждено! Получено часов: {event.duration}")
                    st.balloons()
                    st.rerun()
    st.subheader("📊 История участия")
    participations = get_my_participations(user.id)
    if participations:
        df = pd.DataFrame(participations)
        df['event_date'] = pd.to_datetime(df['event_date']).dt.strftime('%d.%m.%Y %H:%M')
        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%d.%m.%Y %H:%M')
        st.dataframe(df[['event_name', 'event_date', 'hours_awarded', 'timestamp']].rename(columns={
            'event_name': 'Мероприятие',
            'event_date': 'Дата мероприятия',
            'hours_awarded': 'Часов получено',
            'timestamp': 'Время участия'
        }))
    else:
        st.info("Пока нет участий в мероприятиях")
    if total_hours >= 300:
        st.subheader("🎉 Ваш сертификат!")
        events_count = count_events_participated(user.id)
        pdf_bytes = create_certificate_pdf(user.name, user.total_hours, events_count)
        st.download_button("Скачать сертификат (PDF)", data=pdf_bytes, file_name=f"certificate_{user.name.replace(' ', '_')}.pdf", mime="application/pdf")

def organizer_dashboard():
    user = get_user_by_id(st.session_state.user_id)
    st.title(f"👋 Добро пожаловать, {user.name}!")
    tab1, tab2 = st.tabs(["Создать мероприятие", "Мои мероприятия"])
    with tab1:
        st.subheader("➕ Создать новое мероприятие")
        name = st.text_input("Название мероприятия")
        description = st.text_area("Описание")
        event_date = st.date_input("Дата мероприятия", min_value=date.today())
        event_time = st.time_input("Время мероприятия")
        duration = st.number_input("Продолжительность (часы)", min_value=0.5, max_value=24.0, step=0.5)
        if st.button("Создать мероприятие"):
            dt = datetime.combine(event_date, event_time)
            event, qr_b64, qr_data, qr_bytes = create_event(name, description, dt, duration, user.id)
            st.success("Мероприятие создано успешно!")
            st.subheader("QR-код для мероприятия")
            st.image(qr_bytes, caption="QR-код для сканирования участниками")
            st.download_button("Скачать QR-код", data=qr_bytes, file_name=f"qr_code_{event.id}.png", mime="image/png")
            st.code(f"Данные QR-кода: {qr_data}")
    with tab2:
        st.subheader("📅 Мои мероприятия")
        events = get_my_events(user.id)
        if events:
            for event in events:
                with st.expander(f"{event.name} - {event.date.strftime('%d.%m.%Y %H:%M')}"):
                    st.write(f"**Описание:** {event.description or 'Нет описания'}")
                    st.write(f"**Дата:** {event.date.strftime('%d.%m.%Y %H:%M')}")
                    st.write(f"**Продолжительность:** {event.duration} часов")
                    participants = get_event_participants(event.id)
                    st.write(f"**Всего участников:** {len(participants)}")
                    if participants:
                        df = pd.DataFrame(participants)
                        df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%d.%m.%Y %H:%M')
                        st.dataframe(df[['user_name', 'user_email', 'timestamp', 'hours_awarded']].rename(columns={
                            'user_name': 'Имя',
                            'user_email': 'Email',
                            'timestamp': 'Время участия',
                            'hours_awarded': 'Часов начислено'
                        }))
                    else:
                        st.info("Пока нет участников")

def main():
    with st.sidebar:
        if st.session_state.user_id:
            st.write(f"**Пользователь:** {st.session_state.name}")
            st.write(f"**Роль:** {st.session_state.role}")
            st.write(f"**Email:** {st.session_state.email}")
            if st.button("Выйти"):
                st.session_state.user_id = None
                st.session_state.role = None
                st.session_state.name = None
                st.session_state.email = None
                st.rerun()
        else:
            st.write("Войдите в систему")
    if not st.session_state.user_id:
        login_page()
    else:
        if st.session_state.role == 'student':
            student_dashboard()
        elif st.session_state.role == 'organizer':
            organizer_dashboard()
        else:
            st.error("Неизвестная роль пользователя")

if __name__ == "__main__":
    main()
