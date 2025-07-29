import qrcode
import io
import base64
from PIL import Image
import uuid
import cv2
import numpy as np
from pyzbar import pyzbar

def generate_qr_code(event_id: int) -> str:
    """Generate QR code for an event and return base64 encoded image"""
    # Create unique QR data
    qr_data = f"alumni_club_event_{event_id}_{uuid.uuid4().hex[:8]}"
    
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Convert to base64
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    return qr_data, img_str

def decode_qr_from_image(image_data) -> str:
    """Decode QR code from uploaded image"""
    try:
        # Convert image data to numpy array
        if isinstance(image_data, bytes):
            nparr = np.frombuffer(image_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            img = np.array(image_data)
        
        # Decode QR codes
        decoded_objects = pyzbar.decode(img)
        
        if decoded_objects:
            return decoded_objects[0].data.decode('utf-8')
        return None
    except Exception as e:
        print(f"Error decoding QR: {e}")
        return None

def validate_qr_data(qr_data: str) -> bool:
    """Validate if QR data is from our system"""
    return qr_data and qr_data.startswith("alumni_club_event_")
