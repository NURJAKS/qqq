import streamlit as st
import requests
import json
import base64
from PIL import Image
import io
from datetime import datetime, date
import pandas as pd

# Configuration
API_BASE_URL = "http://localhost:8000"

# Initialize session state
if 'token' not in st.session_state:
    st.session_state.token = None
if 'user_info' not in st.session_state:
    st.session_state.user_info = None

def make_api_request(endpoint, method="GET", data=None, files=None, auth=True):
    """Make API request with authentication"""
    headers = {}
    if auth and st.session_state.token:
        headers["Authorization"] = f"Bearer {st.session_state.token}"
    
    url = f"{API_BASE_URL}{endpoint}"
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            if files:
                response = requests.post(url, headers=headers, data=data, files=files)
            else:
                headers["Content-Type"] = "application/json"
                response = requests.post(url, headers=headers, json=data)
        
        return response
    except requests.exceptions.ConnectionError:
        st.error("Не удается подключиться к серверу. Убедитесь, что сервер запущен.")
        return None

def login_page():
    """Login and registration page"""
    st.title("🎓 Alumni Club Connect")
    st.markdown("### Система учёта общественных часов студентов")
    
    tab1, tab2 = st.tabs(["Вход", "Регистрация"])
    
    with tab1:
        st.subheader("Войти в систему")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Пароль", type="password", key="login_password")
        
        if st.button("Войти", key="login_btn"):
            if email and password:
                response = make_api_request("/login", "POST", {
                    "email": email,
                    "password": password
                }, auth=False)
                
                if response and response.status_code == 200:
                    data = response.json()
                    st.session_state.token = data["access_token"]
                    
                    # Get user info
                    user_response = make_api_request("/me")
                    if user_response and user_response.status_code == 200:
                        st.session_state.user_info = user_response.json()
                        st.success("Успешный вход!")
                        st.rerun()
                    else:
                        st.error("Ошибка получения информации о пользователе")
                else:
                    st.error("Неверный email или пароль")
            else:
                st.error("Заполните все поля")
    
    with tab2:
        st.subheader("Регистрация")
        name = st.text_input("Имя", key="reg_name")
        email = st.text_input("Email", key="reg_email")
        password = st.text_input("Пароль", type="password", key="reg_password")
        role = st.selectbox("Роль", ["student", "organizer"], 
                           format_func=lambda x: "Студент" if x == "student" else "Организатор")
        
        if st.button("Зарегистрироваться", key="reg_btn"):
            if name and email and password:
                response = make_api_request("/register", "POST", {
                    "name": name,
                    "email": email,
                    "password": password,
                    "role": role
                }, auth=False)
                
                if response and response.status_code == 200:
                    st.success("Регистрация успешна! Теперь войдите в систему.")
                else:
                    st.error("Ошибка регистрации. Возможно, email уже используется.")
            else:
                st.error("Заполните все поля")

def student_dashboard():
    """Student dashboard"""
    st.title(f"👋 Добро пожаловать, {st.session_state.user_info['name']}!")
    
    # Progress display
    total_hours = st.session_state.user_info['total_hours']
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
            files = {"file": uploaded_file.getvalue()}
            response = make_api_request("/scan-qr-image", "POST", files=files)
            
            if response and response.status_code == 200:
                data = response.json()
                st.success(data["message"])
                st.info(f"Получено часов: {data['hours_awarded']}")
                st.info(f"Всего часов: {data['total_hours']}")
                
                if data.get("certificate_message"):
                    st.balloons()
                    st.success(data["certificate_message"])
                
                # Refresh user info
                user_response = make_api_request("/me")
                if user_response and user_response.status_code == 200:
                    st.session_state.user_info = user_response.json()
                    st.rerun()
            else:
                st.error("Ошибка сканирования QR-кода")
    
    with tab2:
        qr_data = st.text_input("Введите данные QR-кода")
        if qr_data and st.button("Подтвердить участие"):
            response = make_api_request("/scan-qr", "POST", {"qr_data": qr_data})
            
            if response and response.status_code == 200:
                data = response.json()
                st.success(data["message"])
                st.info(f"Получено часов: {data['hours_awarded']}")
                st.info(f"Всего часов: {data['total_hours']}")
                
                if data.get("certificate_message"):
                    st.balloons()
                    st.success(data["certificate_message"])
                
                # Refresh user info
                user_response = make_api_request("/me")
                if user_response and user_response.status_code == 200:
                    st.session_state.user_info = user_response.json()
                    st.rerun()
            else:
                st.error("Ошибка подтверждения участия")
    
    # Participation history
    st.subheader("📊 История участия")
    response = make_api_request("/my-participations")
    
    if response and response.status_code == 200:
        participations = response.json()
        
        if participations:
            df = pd.DataFrame(participations)
            df['event_date'] = pd.to_datetime(df['event_date']).dt.strftime('%d.%m.%Y %H:%M')
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%d.%m.%Y %H:%M')
            
            st.dataframe(df[['event_name', 'event_date', 'hours_awarded', 'timestamp']], 
                        column_config={
                            'event_name': 'Мероприятие',
                            'event_date': 'Дата мероприятия',
                            'hours_awarded': 'Часов получено',
                            'timestamp': 'Время участия'
                        })
        else:
            st.info("Пока нет участий в мероприятиях")

def organizer_dashboard():
    """Organizer dashboard"""
    st.title(f"👋 Добро пожаловать, {st.session_state.user_info['name']}!")
    
    tab1, tab2 = st.tabs(["Создать мероприятие", "Мои мероприятия"])
    
    with tab1:
        st.subheader("➕ Создать новое мероприятие")
        
        name = st.text_input("Название мероприятия")
        description = st.text_area("Описание")
        event_date = st.date_input("Дата мероприятия", min_value=date.today())
        event_time = st.time_input("Время мероприятия")
        duration = st.number_input("Продолжительность (часы)", min_value=0.5, max_value=24.0, step=0.5)
        
        if st.button("Создать мероприятие"):
            if name and event_date and duration:
                # Combine date and time
                event_datetime = datetime.combine(event_date, event_time)
                
                response = make_api_request("/events", "POST", {
                    "name": name,
                    "description": description,
                    "date": event_datetime.isoformat(),
                    "duration": duration
                })
                
                if response and response.status_code == 200:
                    data = response.json()
                    st.success("Мероприятие создано успешно!")
                    
                    # Display QR code
                    st.subheader("QR-код для мероприятия")
                    qr_image = base64.b64decode(data["qr_code"])
                    st.image(qr_image, caption="QR-код для сканирования участниками")
                    
                    # Download QR code
                    st.download_button(
                        label="Скачать QR-код",
                        data=qr_image,
                        file_name=f"qr_code_{data['event_id']}.png",
                        mime="image/png"
                    )
                    
                    st.code(f"Данные QR-кода: {data['qr_data']}")
                else:
                    st.error("Ошибка создания мероприятия")
            else:
                st.error("Заполните все обязательные поля")
    
    with tab2:
        st.subheader("📅 Мои мероприятия")
        response = make_api_request("/my-events")
        
        if response and response.status_code == 200:
            events = response.json()
            
            if events:
                for event in events:
                    with st.expander(f"{event['name']} - {event['date'][:10]}"):
                        st.write(f"**Описание:** {event['description'] or 'Нет описания'}")
                        st.write(f"**Дата:** {event['date'][:16].replace('T', ' ')}")
                        st.write(f"**Продолжительность:** {event['duration']} часов")
                        
                        # Get participants
                        if st.button(f"Показать участников", key=f"participants_{event['id']}"):
                            participants_response = make_api_request(f"/events/{event['id']}/participants")
                            
                            if participants_response and participants_response.status_code == 200:
                                participants_data = participants_response.json()
                                participants = participants_data["participants"]
                                
                                st.write(f"**Всего участников:** {participants_data['total_participants']}")
                                
                                if participants:
                                    df = pd.DataFrame(participants)
                                    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.strftime('%d.%m.%Y %H:%M')
                                    
                                    st.dataframe(df[['user_name', 'user_email', 'timestamp', 'hours_awarded']], 
                                                column_config={
                                                    'user_name': 'Имя',
                                                    'user_email': 'Email',
                                                    'timestamp': 'Время участия',
                                                    'hours_awarded': 'Часов начислено'
                                                })
                                else:
                                    st.info("Пока нет участников")
            else:
                st.info("Пока нет созданных мероприятий")

def main():
    """Main application"""
    st.set_page_config(
        page_title="Alumni Club Connect",
        page_icon="🎓",
        layout="wide"
    )
    
    # Sidebar
    with st.sidebar:
        if st.session_state.token:
            st.write(f"**Пользователь:** {st.session_state.user_info['name']}")
            st.write(f"**Роль:** {st.session_state.user_info['role']}")
            st.write(f"**Email:** {st.session_state.user_info['email']}")
            
            if st.button("Выйти"):
                st.session_state.token = None
                st.session_state.user_info = None
                st.rerun()
        else:
            st.write("Войдите в систему")
    
    # Main content
    if not st.session_state.token:
        login_page()
    else:
        if st.session_state.user_info['role'] == 'student':
            student_dashboard()
        elif st.session_state.user_info['role'] == 'organizer':
            organizer_dashboard()
        else:
            st.error("Неизвестная роль пользователя")

if __name__ == "__main__":
    main()
