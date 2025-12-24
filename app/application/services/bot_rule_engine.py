"""
Bot Rule Engine - Genera respuestas basadas en reglas duras
"""
from typing import Optional, Dict, Any
from app.application.services.programacion_service import ProgramacionService
from app.application.services.operational_insights_service import OperationalInsightsService
from app.application.services.intent_router import IntentRouter


class BotRuleEngine:
    """
    Motor de reglas para el bot BimbaBot.
    Genera respuestas basadas en reglas duras según la intención detectada.
    """
    
    @staticmethod
    def generar_respuesta(intent: str, evento_info: Optional[Dict[str, Any]] = None,
                         operational: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """
        Genera una respuesta basada en reglas duras según la intención.
        
        Args:
            intent: Intención detectada (de IntentRouter)
            evento_info: Información del evento de hoy (opcional)
            operational: Información operativa del día (opcional)
            
        Returns:
            str: Respuesta generada o None si no hay regla para esta intención
        """
        if intent == IntentRouter.INTENT_UNKNOWN:
            return None
        
        if intent == IntentRouter.INTENT_EVENTO_HOY:
            return BotRuleEngine._respuesta_evento_hoy(evento_info)
        
        elif intent == IntentRouter.INTENT_ESTADO_NOCHE:
            return BotRuleEngine._respuesta_estado_noche(evento_info, operational)
        
        elif intent == IntentRouter.INTENT_PROXIMOS_EVENTOS:
            return BotRuleEngine._respuesta_proximos_eventos()
        
        elif intent == IntentRouter.INTENT_PRECIOS:
            return BotRuleEngine._respuesta_precios(evento_info)
        
        elif intent == IntentRouter.INTENT_HORARIO:
            return BotRuleEngine._respuesta_horario(evento_info)
        
        elif intent == IntentRouter.INTENT_LISTA:
            return BotRuleEngine._respuesta_lista(evento_info)
        
        elif intent == IntentRouter.INTENT_DJS:
            return BotRuleEngine._respuesta_djs(evento_info)
        
        elif intent == IntentRouter.INTENT_COMO_FUNCIONA:
            return BotRuleEngine._respuesta_como_funciona(evento_info)
        
        elif intent == IntentRouter.INTENT_SALUDO:
            # Los saludos NO usan reglas hardcodeadas para permitir respuestas variadas y naturales
            # Deben pasar a OpenAI para generar respuestas humanas según el prompt
            return None
        
        return None
    
    @staticmethod
    def _respuesta_evento_hoy(evento_info: Optional[Dict[str, Any]]) -> str:
        """Genera respuesta para consulta sobre evento de hoy"""
        if not evento_info:
            return "Hoy no tenemos un evento cargado en la programación 💜. Revisa nuestras redes para más información."
        
        respuesta_partes = []
        nombre_evento = evento_info.get('nombre_evento', 'Evento especial')
        respuesta_partes.append(f"🎉 **{nombre_evento}**")
        
        horario = evento_info.get('horario', '')
        if horario:
            respuesta_partes.append(f"\n🕐 Horario: {horario}")
        
        dj_principal = evento_info.get('dj_principal', '')
        if dj_principal:
            respuesta_partes.append(f"\n🎧 DJ Principal: {dj_principal}")
        
        otros_djs = evento_info.get('otros_djs', '')
        if otros_djs:
            respuesta_partes.append(f"\n🎵 También: {otros_djs}")
        
        descripcion_corta = evento_info.get('descripcion_corta', '')
        if descripcion_corta:
            respuesta_partes.append(f"\n📝 {descripcion_corta}")
        
        info_lista = evento_info.get('lista', '')
        if info_lista:
            respuesta_partes.append(f"\n📋 {info_lista}")
        
        precios = evento_info.get('precios', [])
        if precios and isinstance(precios, list) and len(precios) > 0:
            respuesta_partes.append("\n💰 Precios:")
            for precio in precios:
                if isinstance(precio, dict):
                    nombre_tier = precio.get('nombre', precio.get('tier', 'General'))
                    monto = precio.get('monto', precio.get('precio', precio.get('valor', 0)))
                    hora_limite = precio.get('hora_limite', precio.get('hasta', ''))
                    try:
                        monto_int = int(float(monto))
                    except (ValueError, TypeError):
                        monto_int = 0
                    if monto_int > 0:
                        if hora_limite:
                            respuesta_partes.append(f"   • {nombre_tier}: ${monto_int:,} hasta {hora_limite}")
                        else:
                            respuesta_partes.append(f"   • {nombre_tier}: ${monto_int:,}")
        
        respuesta_partes.append("\n\nNos vemos en la noche 💜✨")
        return "\n".join(respuesta_partes)
    
    @staticmethod
    def _respuesta_estado_noche(evento_info: Optional[Dict[str, Any]], 
                               operational: Optional[Dict[str, Any]]) -> str:
        """Genera respuesta para consulta sobre estado de la noche"""
        if not evento_info:
            return "Hoy no tenemos evento programado 💜. Revisa nuestras redes para ver qué viene."
        
        # Usar contexto operativo para dar feeling
        feeling = "La noche está empezando 💜"
        if operational:
            sales = operational.get('sales', {})
            total_sales = sales.get('total_sales', 0)
            
            if total_sales > 50:
                feeling = "La noche está súper movida 💜✨"
            elif total_sales > 20:
                feeling = "La noche está movida 💜"
            elif total_sales > 0:
                feeling = "La noche está empezando bien 💜"
            else:
                feeling = "La noche está recién empezando 💜"
        
        nombre_evento = evento_info.get('nombre_evento', 'La noche')
        return f"{feeling}. {nombre_evento} está en curso. ¡Ven a disfrutar! 💜✨"
    
    @staticmethod
    def _respuesta_proximos_eventos() -> str:
        """Genera respuesta para consulta sobre próximos eventos"""
        programacion_service = ProgramacionService()
        eventos = programacion_service.get_upcoming_events(limit=5)
        
        if not eventos or len(eventos) == 0:
            return "No tenemos eventos próximos cargados aún 💜. Revisa nuestras redes para estar al día."
        
        respuesta_partes = ["📅 **Próximos eventos:**\n"]
        for evento in eventos[:5]:
            fecha = evento.get('fecha', '')
            nombre = evento.get('nombre_evento', 'Evento')
            respuesta_partes.append(f"• {fecha}: {nombre}")
        
        respuesta_partes.append("\n💜 ¡Te esperamos!")
        return "\n".join(respuesta_partes)
    
    @staticmethod
    def _respuesta_precios(evento_info: Optional[Dict[str, Any]]) -> str:
        """Genera respuesta para consulta sobre precios"""
        if not evento_info:
            return "No hay evento programado para hoy 💜. Revisa nuestras redes para ver precios de próximos eventos."
        
        precios = evento_info.get('precios', [])
        if not precios or (isinstance(precios, list) and len(precios) == 0):
            return "No tenemos información de precios cargada para hoy 💜. Contacta directamente para más info."
        
        respuesta_partes = ["💰 **Precios de hoy:**\n"]
        if isinstance(precios, list):
            for precio in precios:
                if isinstance(precio, dict):
                    nombre_tier = precio.get('nombre', precio.get('tier', 'General'))
                    monto = precio.get('monto', precio.get('precio', precio.get('valor', 0)))
                    hora_limite = precio.get('hora_limite', precio.get('hasta', ''))
                    try:
                        monto_int = int(float(monto))
                    except (ValueError, TypeError):
                        monto_int = 0
                    if monto_int > 0:
                        if hora_limite:
                            respuesta_partes.append(f"• {nombre_tier}: ${monto_int:,} hasta {hora_limite}")
                        else:
                            respuesta_partes.append(f"• {nombre_tier}: ${monto_int:,}")
        
        respuesta_partes.append("\n💜 ¡Nos vemos!")
        return "\n".join(respuesta_partes)
    
    @staticmethod
    def _respuesta_horario(evento_info: Optional[Dict[str, Any]]) -> str:
        """Genera respuesta para consulta sobre horario"""
        if not evento_info:
            return "No hay evento programado para hoy 💜."
        
        horario = evento_info.get('horario', '')
        if horario:
            return f"🕐 **Horario de hoy:** {horario}\n\n💜 ¡Te esperamos!"
        else:
            return "No tenemos el horario cargado para hoy 💜. Revisa nuestras redes para más info."
    
    @staticmethod
    def _respuesta_lista(evento_info: Optional[Dict[str, Any]]) -> str:
        """Genera respuesta para consulta sobre lista/reservas"""
        if not evento_info:
            return "No hay evento programado para hoy 💜."
        
        info_lista = evento_info.get('lista', '')
        if info_lista:
            return f"📋 {info_lista}\n\n💜 ¡Nos vemos!"
        else:
            return "No tenemos información de lista para hoy 💜. Contacta directamente para reservas."
    
    @staticmethod
    def _respuesta_djs(evento_info: Optional[Dict[str, Any]]) -> str:
        """Genera respuesta para consulta sobre DJs"""
        if not evento_info:
            return "No hay evento programado para hoy 💜."
        
        respuesta_partes = []
        dj_principal = evento_info.get('dj_principal', '')
        otros_djs = evento_info.get('otros_djs', '')
        
        if dj_principal:
            respuesta_partes.append(f"🎧 **DJ Principal:** {dj_principal}")
        if otros_djs:
            respuesta_partes.append(f"🎵 **También:** {otros_djs}")
        
        if not respuesta_partes:
            return "No tenemos información de DJs cargada para hoy 💜."
        
        respuesta_partes.append("\n💜 ¡Ven a disfrutar la música!")
        return "\n".join(respuesta_partes)
    
    @staticmethod
    def _respuesta_como_funciona(evento_info: Optional[Dict[str, Any]] = None) -> str:
        """Genera respuesta para preguntas sobre cómo funciona el sistema"""
        return """En BIMBA, el sistema funciona así: 💜

**🛒 Haces tu pedido** en el bar o la caja
**💳 Pagas** (efectivo, débito o crédito)
**🎫 Recibes un ticket** con código QR
**📱 El bartender escanea** tu código QR
**🍺 Te entrega** tu bebida o producto

Es un sistema seguro y automatizado que asegura que recibas exactamente lo que pediste. Todo está diseñado para darte la mejor experiencia posible! ✨

¿Tienes alguna pregunta específica sobre el proceso? 💜"""
    
    @staticmethod
    def _respuesta_saludo(evento_info: Optional[Dict[str, Any]]) -> str:
        """
        DEPRECATED: Los saludos ahora pasan a OpenAI para respuestas variadas y naturales.
        Este método se mantiene solo por compatibilidad pero nunca debería ser llamado.
        """
        # No usar respuestas hardcodeadas para saludos
        # Deben pasar a OpenAI para generar respuestas humanas y variadas
        return None


