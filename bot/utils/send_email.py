import smtplib
from email.mime.text import MIMEText
import logging
from bot.config.config import SMTP_SERVER, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_TO_EMAIL, SMTP_SUBJECT

def send_consultation_email(phone_number: str, user_name: str = None, city: str = None):
    """
    Отправляет письмо с информацией о консультации на рабочую почту.
    Args:
        phone_number (str): Номер телефона пользователя
        user_name (str, optional): Имя пользователя из Telegram
        city (str, optional): Город пользователя
    Returns:
        bool: True если письмо отправлено успешно, иначе False
    """
    # Логируем SMTP конфигурацию для диагностики
    logging.info(f"SMTP конфигурация: SERVER={SMTP_SERVER}, PORT={SMTP_PORT}, USER={SMTP_USER}, TO={SMTP_TO_EMAIL}")
    
    if not all([SMTP_USER, SMTP_PASSWORD, SMTP_TO_EMAIL, SMTP_SUBJECT]):
        logging.error("Не все SMTP переменные настроены!")
        logging.error(f"SMTP_USER: {'✓' if SMTP_USER else '✗'}")
        logging.error(f"SMTP_PASSWORD: {'✓' if SMTP_PASSWORD else '✗'}")
        logging.error(f"SMTP_TO_EMAIL: {'✓' if SMTP_TO_EMAIL else '✗'}")
        logging.error(f"SMTP_SUBJECT: {'✓' if SMTP_SUBJECT else '✗'}")
        return False
    
    # Добавляем + перед номером, если его нет
    if not phone_number.startswith('+'):
        phone_number = '+' + phone_number
    
    # Формируем тело письма
    body = "Квиз\n\n"
    body += f"Имя: {user_name if user_name else 'Не указано'}\n"
    body += f"Контактный телефон: {phone_number}\n"
    body += f"Город: {city if city else 'Не указан'}\n"
    body += "Сообщение: Заявка на консультацию"
    
    msg = MIMEText(body)
    msg['Subject'] = SMTP_SUBJECT
    msg['From'] = SMTP_USER
    msg['To'] = SMTP_TO_EMAIL

    try:
        logging.info(f"Попытка подключения к SMTP серверу {SMTP_SERVER}:{SMTP_PORT}")
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            logging.info("SMTP соединение установлено, выполняем авторизацию...")
            server.login(SMTP_USER, SMTP_PASSWORD)
            logging.info("Авторизация успешна, отправляем письмо...")
            server.sendmail(SMTP_USER, [SMTP_TO_EMAIL], msg.as_string())
        logging.info(f"Письмо с консультацией успешно отправлено на {SMTP_TO_EMAIL}")
        return True
    except smtplib.SMTPAuthenticationError as e:
        logging.error(f"Ошибка авторизации SMTP: {e}")
        return False
    except smtplib.SMTPConnectError as e:
        logging.error(f"Ошибка подключения к SMTP серверу: {e}")
        return False
    except smtplib.SMTPException as e:
        logging.error(f"SMTP ошибка: {e}")
        return False
    except Exception as e:
        logging.error(f"Общая ошибка при отправке письма с консультацией: {e}")
        return False 