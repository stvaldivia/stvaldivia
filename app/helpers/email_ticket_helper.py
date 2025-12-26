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


def get_payment_link_by_amount(monto: float) -> str:
    """
    Obtiene el link de pago según el monto de la compra
    
    Args:
        monto: Monto total de la compra
        
    Returns:
        URL del link de pago correspondiente
    """
    # Links de pago SumUp según monto
    payment_links = {
        5000: 'https://pay.sumup.com/b2c/Q3XX3AP6',
        10000: 'https://pay.sumup.com/b2c/Q877B989',
        15000: 'https://pay.sumup.com/b2c/QV9H60YE',
        20000: 'https://pay.sumup.com/b2c/QWXAE7H2'
    }
    
    # Redondear al monto más cercano
    monto_redondeado = round(monto / 1000) * 1000
    
    # Buscar el link correspondiente (usar el más cercano hacia abajo)
    if monto_redondeado >= 20000:
        return payment_links[20000]
    elif monto_redondeado >= 15000:
        return payment_links[15000]
    elif monto_redondeado >= 10000:
        return payment_links[10000]
    elif monto_redondeado >= 5000:
        return payment_links[5000]
    else:
        # Si es menor a $5.000, usar el link de $5.000
        return payment_links[5000]


def generate_resumen_compra_html(entrada: Entrada, preview: bool = False) -> tuple[str, str]:
    """
    Genera el HTML del email de resumen de compra
    
    Args:
        entrada: Objeto Entrada
        preview: Si es True, no incluye información sensible
        
    Returns:
        Tupla con (subject, html_body)
    """
    from app.helpers.qr_ticket_helper import generate_ticket_qr
    
    email_subject = f"Resumen de tu compra - {entrada.evento_nombre} | BIMBA"
    
    # Generar URL del ticket
    try:
        ticket_url = url_for('ecommerce.view_ticket', ticket_code=entrada.ticket_code, _external=True)
    except RuntimeError:
        public_base_url = current_app.config.get('PUBLIC_BASE_URL') or os.environ.get('PUBLIC_BASE_URL')
        if public_base_url:
            ticket_url = f"{public_base_url.rstrip('/')}/ecommerce/ticket/{entrada.ticket_code}"
        else:
            ticket_url = f"/ecommerce/ticket/{entrada.ticket_code}"
    
    # Formatear fechas
    fecha_evento = entrada.evento_fecha.strftime('%d de %B de %Y a las %H:%M') if entrada.evento_fecha else 'No especificada'
    fecha_compra = entrada.created_at.strftime('%d/%m/%Y %H:%M') if entrada.created_at else 'N/A'
    fecha_pago = entrada.paid_at.strftime('%d/%m/%Y %H:%M') if entrada.paid_at else 'N/A'
    
    # Calcular precio total
    precio_total = float(entrada.cantidad) * float(entrada.precio_unitario) if entrada.precio_unitario else float(entrada.precio_total or 0)
    
    # Obtener link de pago según el monto
    payment_link = get_payment_link_by_amount(precio_total)
    
    # Estado en español
    estados = {
        'recibido': 'Recibido',
        'pagado': 'Pagado',
        'entregado': 'Entregado'
    }
    estado_display = estados.get(entrada.estado_pago.lower(), entrada.estado_pago.title())
    
    # Método de pago en español
    metodos_pago = {
        'getnet_web': 'Tarjeta de Crédito/Débito (GetNet)',
        'getnet_link': 'Link de Pago (GetNet)',
        'manual': 'Pago Manual',
        'sumup': 'Link de Pago (SumUp)'
    }
    metodo_display = metodos_pago.get(entrada.metodo_pago, entrada.metodo_pago or 'No especificado')
    
    # Determinar si mostrar link de pago (solo si el estado es "recibido")
    mostrar_link_pago = entrada.estado_pago.lower() == 'recibido'
    
    # Generar QR solo si el pago está realizado (pagado o entregado)
    mostrar_qr = entrada.estado_pago.lower() in ['pagado', 'entregado']
    qr_code_base64 = None
    if mostrar_qr:
        qr_code_base64 = generate_ticket_qr(entrada.ticket_code, size=250)
    
    email_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background-color: #f5f5f5;">
        
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 28px;">🎫 BIMBA</h1>
            <p style="color: rgba(255,255,255,0.9); margin: 10px 0 0 0; font-size: 16px;">Resumen de tu Compra</p>
        </div>
        
        <!-- Contenido Principal -->
        <div style="background: white; padding: 30px; border-radius: 0 0 10px 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
            
            <p style="font-size: 16px; margin-bottom: 20px;">Hola <strong>{entrada.comprador_nombre}</strong>,</p>
            
            <p style="font-size: 16px; color: #666;">Gracias por tu compra. Aquí está el resumen completo de tu pedido:</p>
            
            <!-- Código de Ticket -->
            <div style="background: linear-gradient(135deg, #f5f5f5 0%, #e8e8e8 100%); padding: 25px; border-radius: 8px; margin: 25px 0; text-align: center; border: 2px dashed #667eea;">
                <p style="margin: 0 0 10px 0; color: #666; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">Código de Ticket</p>
                <p style="font-size: 32px; font-weight: bold; letter-spacing: 4px; color: #667eea; margin: 0; font-family: 'Courier New', monospace;">
                    {entrada.ticket_code}
                </p>
            </div>
            
            {'<!-- Código QR (solo válido si el pago está realizado) -->' if mostrar_qr and qr_code_base64 else ''}
            {f'''
            <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); padding: 30px; border-radius: 8px; margin: 25px 0; text-align: center;">
                <h2 style="color: white; margin-top: 0; font-size: 22px; margin-bottom: 15px;">✅ Código QR de Acceso</h2>
                <p style="color: rgba(255,255,255,0.95); margin: 0 0 20px 0; font-size: 16px; font-weight: 500;">
                    Presenta este código QR en la entrada del evento
                </p>
                <div style="background: white; padding: 20px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 20px rgba(0,0,0,0.2);">
                    <img src="{qr_code_base64}" 
                         alt="Código QR - Ticket {entrada.ticket_code}" 
                         style="width: 250px; height: 250px; display: block; margin: 0 auto;" />
                </div>
                <p style="color: rgba(255,255,255,0.9); margin: 20px 0 0 0; font-size: 14px;">
                    <strong>✓ Pago Verificado</strong> - Este código QR es válido para ingresar al evento
                </p>
            </div>
            ''' if mostrar_qr and qr_code_base64 else ''}
            
            <!-- Información del Evento -->
            <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #667eea;">
                <h2 style="color: #667eea; margin-top: 0; font-size: 22px;">📅 Información del Evento</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #666; width: 40%;"><strong>Evento:</strong></td>
                        <td style="padding: 8px 0; color: #333;">{entrada.evento_nombre}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;"><strong>Fecha:</strong></td>
                        <td style="padding: 8px 0; color: #333;">{fecha_evento}</td>
                    </tr>
                    {f'<tr><td style="padding: 8px 0; color: #666;"><strong>Lugar:</strong></td><td style="padding: 8px 0; color: #333;">{entrada.evento_lugar}</td></tr>' if entrada.evento_lugar else ''}
                </table>
            </div>
            
            <!-- Detalles de la Compra -->
            <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #10b981;">
                <h2 style="color: #10b981; margin-top: 0; font-size: 22px;">💰 Detalles de la Compra</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #666; width: 40%;"><strong>Cantidad:</strong></td>
                        <td style="padding: 8px 0; color: #333;">{entrada.cantidad} entrada(s)</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;"><strong>Precio unitario:</strong></td>
                        <td style="padding: 8px 0; color: #333;">${float(entrada.precio_unitario):,.0f}</td>
                    </tr>
                    <tr style="border-top: 2px solid #ddd;">
                        <td style="padding: 12px 0; color: #333; font-size: 18px;"><strong>Total a pagar:</strong></td>
                        <td style="padding: 12px 0; color: #10b981; font-size: 20px; font-weight: bold;">${precio_total:,.0f}</td>
                    </tr>
                </table>
            </div>
            
            {'<!-- Link de Pago -->' if mostrar_link_pago else ''}
            {f'''
            <div style="background: linear-gradient(135deg, #f59e0b 0%, #f97316 100%); padding: 25px; border-radius: 8px; margin: 20px 0; text-align: center;">
                <h2 style="color: white; margin-top: 0; font-size: 22px;">💳 Realizar Pago</h2>
                <p style="color: rgba(255,255,255,0.9); margin: 15px 0; font-size: 16px;">
                    Para completar tu compra, haz clic en el siguiente botón para realizar el pago:
                </p>
                <a href="{payment_link}" 
                   target="_blank"
                   style="background: white; color: #f59e0b; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: 600; font-size: 16px; box-shadow: 0 4px 15px rgba(0,0,0,0.2); margin-top: 10px;">
                    💳 Pagar ${precio_total:,.0f}
                </a>
                <p style="color: rgba(255,255,255,0.8); margin: 15px 0 0 0; font-size: 12px;">
                    O copia este link: <a href="{payment_link}" style="color: white; word-break: break-all;">{payment_link}</a>
                </p>
            </div>
            ''' if mostrar_link_pago else ''}
            
            <!-- Información de Pago -->
            <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #f59e0b;">
                <h2 style="color: #f59e0b; margin-top: 0; font-size: 22px;">💳 Información de Pago</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #666; width: 40%;"><strong>Estado:</strong></td>
                        <td style="padding: 8px 0; color: #333;">
                            <span style="background: {'#10b981' if entrada.estado_pago in ['pagado', 'entregado'] else '#f59e0b'}; color: white; padding: 4px 12px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                                {estado_display}
                            </span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;"><strong>Método de pago:</strong></td>
                        <td style="padding: 8px 0; color: #333;">{metodo_display}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;"><strong>Fecha de compra:</strong></td>
                        <td style="padding: 8px 0; color: #333;">{fecha_compra}</td>
                    </tr>
                    {f'<tr><td style="padding: 8px 0; color: #666;"><strong>Fecha de pago:</strong></td><td style="padding: 8px 0; color: #333;">{fecha_pago}</td></tr>' if entrada.paid_at else ''}
                    {f'<tr><td style="padding: 8px 0; color: #666;"><strong>ID Transacción:</strong></td><td style="padding: 8px 0; color: #333; font-family: monospace; font-size: 12px;">{entrada.getnet_transaction_id}</td></tr>' if entrada.getnet_transaction_id else ''}
                </table>
            </div>
            
            <!-- Tus Datos -->
            <div style="background: #f9f9f9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #8b5cf6;">
                <h2 style="color: #8b5cf6; margin-top: 0; font-size: 22px;">👤 Tus Datos</h2>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; color: #666; width: 40%;"><strong>Nombre:</strong></td>
                        <td style="padding: 8px 0; color: #333;">{entrada.comprador_nombre}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; color: #666;"><strong>Email:</strong></td>
                        <td style="padding: 8px 0; color: #333;">{entrada.comprador_email}</td>
                    </tr>
                    {f'<tr><td style="padding: 8px 0; color: #666;"><strong>Teléfono:</strong></td><td style="padding: 8px 0; color: #333;">{entrada.comprador_telefono}</td></tr>' if entrada.comprador_telefono else ''}
                    {f'<tr><td style="padding: 8px 0; color: #666;"><strong>RUT:</strong></td><td style="padding: 8px 0; color: #333;">{entrada.comprador_rut}</td></tr>' if entrada.comprador_rut else ''}
                </table>
            </div>
            
            <!-- Botón Ver Ticket -->
            <div style="text-align: center; margin: 30px 0;">
                <a href="{ticket_url}" 
                   style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 15px 30px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: 600; font-size: 16px; box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);">
                    📱 Ver mi Ticket Digital
                </a>
            </div>
            
            <!-- Información Importante -->
            <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin: 20px 0;">
                <p style="margin: 0; color: #856404; font-size: 14px;">
                    <strong>ℹ️ Importante:</strong> Presenta este ticket en la entrada del evento. Puedes mostrarlo desde tu teléfono o imprimirlo. Guarda este email como comprobante de tu compra.
                </p>
            </div>
            
        </div>
        
        <!-- Footer -->
        <div style="text-align: center; padding: 20px; color: #999; font-size: 12px;">
            <p style="margin: 5px 0;">BIMBA - Valdivia es BIMBA</p>
            <p style="margin: 5px 0;">Si tienes alguna pregunta, contáctanos en hola@valdiviaesbimba.cl</p>
            <p style="margin: 5px 0;">Este es un email automático, por favor no respondas a este mensaje.</p>
        </div>
        
    </body>
    </html>
    """
    
    return email_subject, email_body


def send_resumen_compra_email(entrada: Entrada) -> bool:
    """
    Envía email con resumen de compra y datos de pago directamente al comprador
    
    Args:
        entrada: Objeto Entrada a enviar
        
    Returns:
        True si se envió exitosamente, False en caso contrario
    """
    try:
        if not entrada.comprador_email:
            logger.warning(f"⚠️ No hay email del comprador para entrada {entrada.ticket_code}")
            return False
        
        email_subject = f"Resumen de tu compra - {entrada.evento_nombre} | BIMBA"
        
        # Generar URL del ticket
        try:
            ticket_url = url_for('ecommerce.view_ticket', ticket_code=entrada.ticket_code, _external=True)
        except RuntimeError:
            public_base_url = current_app.config.get('PUBLIC_BASE_URL') or os.environ.get('PUBLIC_BASE_URL')
            if public_base_url:
                ticket_url = f"{public_base_url.rstrip('/')}/ecommerce/ticket/{entrada.ticket_code}"
            else:
                ticket_url = f"/ecommerce/ticket/{entrada.ticket_code}"
        
        # Formatear fechas
        fecha_evento = entrada.evento_fecha.strftime('%d de %B de %Y a las %H:%M') if entrada.evento_fecha else 'No especificada'
        fecha_compra = entrada.created_at.strftime('%d/%m/%Y %H:%M') if entrada.created_at else 'N/A'
        fecha_pago = entrada.paid_at.strftime('%d/%m/%Y %H:%M') if entrada.paid_at else 'N/A'
        
        # Generar HTML del email usando la función helper
        email_subject, email_body = generate_resumen_compra_html(entrada, preview=False)
        
        # Enviar email usando smtplib
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Obtener configuración de email
        smtp_server = current_app.config.get('SMTP_SERVER') or os.environ.get('SMTP_SERVER')
        smtp_port = int(current_app.config.get('SMTP_PORT') or os.environ.get('SMTP_PORT', '587'))
        smtp_user = current_app.config.get('SMTP_USER') or os.environ.get('SMTP_USER')
        smtp_password = current_app.config.get('SMTP_PASSWORD') or os.environ.get('SMTP_PASSWORD')
        smtp_from = current_app.config.get('SMTP_FROM') or os.environ.get('SMTP_FROM') or smtp_user
        
        if not smtp_server or not smtp_user or not smtp_password:
            logger.warning("⚠️ Configuración de SMTP incompleta. Email no enviado.")
            logger.info(f"📧 Email de resumen preparado para {entrada.comprador_email} (no enviado)")
            return False
        
        try:
            # Crear mensaje - ENVIAR AL COMPRADOR
            msg = MIMEMultipart('alternative')
            msg['Subject'] = email_subject
            msg['From'] = smtp_from
            msg['To'] = entrada.comprador_email
            
            # Agregar cuerpo HTML
            html_part = MIMEText(email_body, 'html', 'utf-8')
            msg.attach(html_part)
            
            # Conectar y enviar
            if smtp_port == 465:
                server = smtplib.SMTP_SSL(smtp_server, smtp_port)
            else:
                server = smtplib.SMTP(smtp_server, smtp_port)
                server.starttls()
            
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"✅ Email de resumen enviado exitosamente a {entrada.comprador_email} (Ticket: {entrada.ticket_code})")
            return True
            
        except Exception as email_error:
            logger.error(f"❌ Error al enviar email de resumen a {entrada.comprador_email}: {email_error}", exc_info=True)
            return False
        
    except Exception as e:
        logger.error(f"Error al enviar email de resumen: {e}", exc_info=True)
        return False

