"""
Intent Router - Detecta la intención del mensaje del usuario
"""
from typing import Optional
import re


class IntentRouter:
    """
    Router de intenciones para el bot BimbaBot.
    Detecta qué tipo de consulta está haciendo el usuario.
    """
    
    # Intenciones disponibles
    INTENT_EVENTO_HOY = "evento_hoy"
    INTENT_ESTADO_NOCHE = "estado_noche"
    INTENT_PROXIMOS_EVENTOS = "proximos_eventos"
    INTENT_PRECIOS = "precios"
    INTENT_HORARIO = "horario"
    INTENT_LISTA = "lista"
    INTENT_DJS = "djs"
    INTENT_UNKNOWN = "unknown"
    
    @staticmethod
    def _normalize_message(mensaje: str) -> str:
        """
        Normaliza el mensaje para comparación (lowercase, sin acentos básicos).
        
        Args:
            mensaje: Mensaje original
            
        Returns:
            str: Mensaje normalizado
        """
        mensaje = mensaje.lower().strip()
        # Reemplazos básicos de acentos
        replacements = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'ñ': 'n', '¿': '', '?': '', '¡': '', '!': ''
        }
        for old, new in replacements.items():
            mensaje = mensaje.replace(old, new)
        return mensaje
    
    @staticmethod
    def detectar_intent(mensaje: str) -> str:
        """
        Detecta la intención del mensaje del usuario.
        
        Args:
            mensaje: Mensaje del usuario
            
        Returns:
            str: Intención detectada (una de las constantes INTENT_*)
        """
        if not mensaje or not mensaje.strip():
            return IntentRouter.INTENT_UNKNOWN
        
        normalized = IntentRouter._normalize_message(mensaje)
        
        # Patrones para "qué hay hoy" / "evento de hoy"
        if re.search(r'\b(que|q)\s*(hay|tiene|pasa|sucede|ocurre)\s*(hoy|esta noche|esta nochecita)\b', normalized) or \
           re.search(r'\bevento\s*(de|del|hoy|esta noche)\b', normalized) or \
           re.search(r'\b(hay|tiene|tendran)\s*(algo|evento|fiesta|noche)\s*(hoy|esta noche)\b', normalized):
            return IntentRouter.INTENT_EVENTO_HOY
        
        # Patrones para "cómo va la noche"
        if re.search(r'\b(como|como va|como esta|como andamos|como andan)\s*(la noche|la nochecita|la fiesta|el ambiente|todo)\b', normalized) or \
           re.search(r'\b(como va|como esta|como andamos)\s*(hoy|esta noche|esta nochecita)\b', normalized):
            return IntentRouter.INTENT_ESTADO_NOCHE
        
        # Patrones para "próximos eventos"
        if re.search(r'\b(proximos|siguientes|que viene|que vienen|futuros)\s*(eventos|evento|fiestas|fiesta|noches|noche)\b', normalized) or \
           re.search(r'\b(que|q)\s*(viene|vienen|sigue|siguen|hay despues)\b', normalized):
            return IntentRouter.INTENT_PROXIMOS_EVENTOS
        
        # Patrones para "precios"
        if re.search(r'\b(precio|precios|cuanto|cuanto cuesta|cuanto vale|tarifa|tarifas|entrada|entradas)\b', normalized):
            return IntentRouter.INTENT_PRECIOS
        
        # Patrones para "horario"
        if re.search(r'\b(horario|hora|a que hora|desde que hora|hasta que hora|cuando|que hora)\b', normalized):
            return IntentRouter.INTENT_HORARIO
        
        # Patrones para "lista"
        if re.search(r'\b(lista|lista de espera|reserva|reservas|mesa|mesas)\b', normalized):
            return IntentRouter.INTENT_LISTA
        
        # Patrones para "DJ" / "música"
        if re.search(r'\b(dj|djs|disc jockey|musica|musical|quien toca|quienes tocan)\b', normalized):
            return IntentRouter.INTENT_DJS
        
        # Si no hay match, retornar unknown
        return IntentRouter.INTENT_UNKNOWN


