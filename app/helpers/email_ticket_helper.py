"""
Helper para envío de emails con tickets de entrada
"""
import logging
import os
from typing import Optional
from flask import current_app, url_for
from app.models.ecommerce_models import Entrada

logger = logging.getLogger(__name__)


def send_ticket_email(entrada: Entrada) -> bool:
    """
    Envía email con el ticket de entrada al comprador
    
    Args:
        entrada: Objeto Entrada a enviar
        
    Returns:
        True si se envió exitosamente, False en caso contrario
    """
    try:
        # Verificar si hay configuración de email
        # Por ahora solo loguear, implementar envío real cuando haya SMTP configurado
        email_subject = f"Nueva compra: {entrada.evento_nombre} - {entrada.comprador_nombre}"
        
        # Generar URL del ticket (manejar caso fuera de request)
        try:
            ticket_url = url_for('ecommerce.view_ticket', ticket_code=entrada.ticket_code, _external=True)
        except RuntimeError:
            # Si no hay request activo, construir URL manualmente
            public_base_url = current_app.config.get('PUBLIC_BASE_URL') or os.environ.get('PUBLIC_BASE_URL')
            if public_base_url:
                ticket_url = f"{public_base_url.rstrip('/')}/ecommerce/ticket/{entrada.ticket_code}"
            else:
                ticket_url = f"/ecommerce/ticket/{entrada.ticket_code}"
        
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #667eea;">¡Gracias por tu compra!</h2>
            
            <p>Hola,</p>
            
            <p>Se ha recibido una nueva compra de <strong>{entrada.comprador_nombre}</strong> ({entrada.comprador_email}).</p>
            <p>Aquí están los detalles de la entrada:</p>
            
            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <h3 style="margin-top: 0;">{entrada.evento_nombre}</h3>
                <p style="font-size: 24px; font-weight: bold; letter-spacing: 3px; color: #333;">
                    {entrada.ticket_code}
                </p>
            </div>
            
            <div style="margin: 20px 0;">
                <p><strong>Comprador:</strong> {entrada.comprador_nombre}</p>
                <p><strong>Email del comprador:</strong> {entrada.comprador_email}</p>
                <p><strong>Teléfono:</strong> {entrada.comprador_telefono if entrada.comprador_telefono else 'No proporcionado'}</p>
                <p><strong>RUT:</strong> {entrada.comprador_rut if entrada.comprador_rut else 'No proporcionado'}</p>
                <hr style="border: none; border-top: 1px solid #ddd; margin: 15px 0;">
                <p><strong>Fecha del evento:</strong> {entrada.evento_fecha.strftime('%d/%m/%Y %H:%M') if entrada.evento_fecha else 'N/A'}</p>
                {f'<p><strong>Lugar:</strong> {entrada.evento_lugar}</p>' if entrada.evento_lugar else ''}
                <p><strong>Cantidad:</strong> {entrada.cantidad} entrada(s)</p>
                <p><strong>Total pagado:</strong> ${entrada.precio_total:,.0f}</p>
            </div>
            
            <div style="margin: 30px 0; text-align: center;">
                <a href="{ticket_url}" 
                   style="background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                    Ver mi Ticket
                </a>
            </div>
            
            <p style="color: #666; font-size: 14px; margin-top: 30px;">
                Presenta este ticket en la entrada del evento. También puedes mostrarlo desde tu teléfono.
            </p>
            
            <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
            
            <p style="color: #999; font-size: 12px;">
                Si tienes alguna pregunta, por favor contacta con nosotros.
            </p>
        </body>
        </html>
        """
        
        # Enviar email usando smtplib (estándar de Python)
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Obtener configuración de email desde variables de entorno
        smtp_server = current_app.config.get('SMTP_SERVER') or os.environ.get('SMTP_SERVER')
        smtp_port = int(current_app.config.get('SMTP_PORT') or os.environ.get('SMTP_PORT', '587'))
        smtp_user = current_app.config.get('SMTP_USER') or os.environ.get('SMTP_USER')
        smtp_password = current_app.config.get('SMTP_PASSWORD') or os.environ.get('SMTP_PASSWORD')
        smtp_from = current_app.config.get('SMTP_FROM') or os.environ.get('SMTP_FROM') or smtp_user
        
        if not smtp_server or not smtp_user or not smtp_password:
            logger.warning("⚠️ Configuración de SMTP incompleta. Email no enviado.")
            logger.info(f"📧 Email de ticket preparado para {entrada.comprador_email} (no enviado)")
            logger.debug(f"Subject: {email_subject}")
            logger.debug(f"Ticket URL: {ticket_url}")
            return False
        
        try:
            # Crear mensaje
            # Siempre enviar a hola@valdiviaesbimba.cl
            email_destino = 'hola@valdiviaesbimba.cl'
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = email_subject
            msg['From'] = smtp_from
            msg['To'] = email_destino
            # Incluir el email del comprador en el cuerpo del mensaje para referencia
            
            # Agregar cuerpo HTML
            html_part = MIMEText(email_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Conectar y enviar
            if smtp_port == 465:
                # SSL
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            else:
                # TLS
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
            
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✅ Email enviado exitosamente a {email_destino} (comprador: {entrada.comprador_email})")
            return True
            
        except Exception as email_error:
            logger.error(f"❌ Error al enviar email a hola@valdiviaesbimba.cl: {email_error}", exc_info=True)
            # No fallar la compra si el email falla
            return False
        
    except Exception as e:
        logger.error(f"Error al enviar email de ticket: {e}", exc_info=True)
        return False

