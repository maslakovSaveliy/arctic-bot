import smtplib
from email.mime.text import MIMEText
import logging
from bot.config.config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_TO_EMAIL, SMTP_SUBJECT

def send_consultation_email(phone_number: str):
    """
    Отправляет письмо с номером телефона пользователя на рабочую почту.
    Args:
        phone_number (str): Номер телефона пользователя
    Returns:
        bool: True если письмо отправлено успешно, иначе False
    """
    if not all([SMTP_USER, SMTP_PASSWORD, SMTP_TO_EMAIL, SMTP_SUBJECT]):
        return False
    # Добавляем + перед номером, если его нет
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    body = phone_number
    msg = MIMEText(body)
    msg['Subject'] = SMTP_SUBJECT
    msg['From'] = SMTP_USER
    msg['To'] = SMTP_TO_EMAIL

    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, [SMTP_TO_EMAIL], msg.as_string())
        logging.info(f"Письмо с номером {phone_number} успешно отправлено на {SMTP_TO_EMAIL}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при отправке письма с номером {phone_number}: {e}")
        return False 