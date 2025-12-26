"""
Helper para envío de emails con tickets de entrada
"""
import logging
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
        email_subject = f"Tu entrada para {entrada.evento_nombre}"
        ticket_url = url_for('ecommerce.view_ticket', ticket_code=entrada.ticket_code, _external=True)
        
        email_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #667eea;">¡Gracias por tu compra!</h2>
            
            <p>Hola {entrada.comprador_nombre},</p>
            
            <p>Tu compra ha sido confirmada. Aquí están los detalles de tu entrada:</p>
            
            <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <h3 style="margin-top: 0;">{entrada.evento_nombre}</h3>
                <p style="font-size: 24px; font-weight: bold; letter-spacing: 3px; color: #333;">
                    {entrada.ticket_code}
                </p>
            </div>
            
            <div style="margin: 20px 0;">
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
        
        # TODO: Implementar envío real de email cuando haya SMTP configurado
        # Por ahora solo loguear
        logger.info(f"📧 Email de ticket preparado para {entrada.comprador_email}")
        logger.debug(f"Subject: {email_subject}")
        logger.debug(f"Ticket URL: {ticket_url}")
        
        # Si hay configuración de email, enviar
        # if current_app.config.get('MAIL_SERVER'):
        #     from flask_mail import Message
        #     msg = Message(
        #         subject=email_subject,
        #         recipients=[entrada.comprador_email],
        #         html=email_body
        #     )
        #     mail.send(msg)
        #     logger.info(f"✅ Email enviado a {entrada.comprador_email}")
        #     return True
        # else:
        logger.warning("⚠️ Servidor de email no configurado. Email no enviado.")
        return False
        
    except Exception as e:
        logger.error(f"Error al enviar email de ticket: {e}", exc_info=True)
        return False

