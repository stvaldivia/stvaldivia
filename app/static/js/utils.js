/**
 * Utilidades JavaScript para la aplicación BIMBA
 * Funciones reutilizables para UI/UX, validación y feedback visual
 */

// ============================================================================
// Utilidades de Feedback Visual
// ============================================================================

/**
 * Muestra un mensaje de éxito con animación
 */
function showSuccess(message, duration = 3000) {
    showFlashMessage(message, 'success', duration);
}

/**
 * Muestra un mensaje de error con animación
 */
function showError(message, duration = 5000) {
    showFlashMessage(message, 'error', duration);
}

/**
 * Muestra un mensaje informativo con animación
 */
function showInfo(message, duration = 3000) {
    showFlashMessage(message, 'info', duration);
}

/**
 * Muestra un mensaje flash personalizado
 */
function showFlashMessage(message, type = 'info', duration = 3000) {
    // Crear elemento de mensaje
    const flashDiv = document.createElement('div');
    flashDiv.className = `flash-message flash-${type}`;
    flashDiv.textContent = message;
    
    // Estilos inline para asegurar visibilidad
    flashDiv.style.cssText = `
        position: fixed;
        top: 80px;
        right: 20px;
        padding: 15px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        z-index: 10000;
        animation: slideInRight 0.3s ease-out;
        max-width: 400px;
        word-wrap: break-word;
    `;
    
    // Colores según tipo
    if (type === 'success') {
        flashDiv.style.background = '#00ff00';
        flashDiv.style.color = '#000';
    } else if (type === 'error') {
        flashDiv.style.background = '#ff4444';
        flashDiv.style.color = '#fff';
    } else if (type === 'info') {
        flashDiv.style.background = '#667eea';
        flashDiv.style.color = '#fff';
    } else {
        flashDiv.style.background = '#2a2a3e';
        flashDiv.style.color = '#fff';
    }
    
    // Agregar al body
    document.body.appendChild(flashDiv);
    
    // Auto-remover después de duration
    setTimeout(() => {
        flashDiv.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => {
            if (flashDiv.parentNode) {
                flashDiv.parentNode.removeChild(flashDiv);
            }
        }, 300);
    }, duration);
    
    // Permitir cerrar con click
    flashDiv.addEventListener('click', () => {
        flashDiv.style.animation = 'slideOutRight 0.3s ease-out';
        setTimeout(() => {
            if (flashDiv.parentNode) {
                flashDiv.parentNode.removeChild(flashDiv);
            }
        }, 300);
    });
}

/**
 * Muestra un loading spinner overlay
 */
function showLoading(message = 'Cargando...') {
    // Remover cualquier loading existente
    hideLoading();
    
    const overlay = document.createElement('div');
    overlay.id = 'loading-overlay';
    overlay.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.7);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 99999;
        flex-direction: column;
    `;
    
    const spinner = document.createElement('div');
    spinner.style.cssText = `
        width: 50px;
        height: 50px;
        border: 5px solid rgba(102, 126, 234, 0.3);
        border-top-color: #667eea;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin-bottom: 20px;
    `;
    
    const text = document.createElement('div');
    text.textContent = message;
    text.style.cssText = `
        color: #fff;
        font-size: 1.1rem;
        font-weight: bold;
    `;
    
    overlay.appendChild(spinner);
    overlay.appendChild(text);
    document.body.appendChild(overlay);
}

/**
 * Oculta el loading spinner
 */
function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.remove();
    }
}

// ============================================================================
// Utilidades de Validación
// ============================================================================

/**
 * Valida un campo de formulario
 */
function validateField(field, rules) {
    const value = field.value.trim();
    const errors = [];
    
    if (rules.required && !value) {
        errors.push('Este campo es obligatorio');
    }
    
    if (rules.minLength && value.length < rules.minLength) {
        errors.push(`Debe tener al menos ${rules.minLength} caracteres`);
    }
    
    if (rules.maxLength && value.length > rules.maxLength) {
        errors.push(`No puede tener más de ${rules.maxLength} caracteres`);
    }
    
    if (rules.pattern && value && !rules.pattern.test(value)) {
        errors.push(rules.message || 'Formato inválido');
    }
    
    if (rules.type === 'number' && value) {
        const num = parseFloat(value);
        if (isNaN(num)) {
            errors.push('Debe ser un número válido');
        } else {
            if (rules.min !== undefined && num < rules.min) {
                errors.push(`Debe ser mayor o igual a ${rules.min}`);
            }
            if (rules.max !== undefined && num > rules.max) {
                errors.push(`Debe ser menor o igual a ${rules.max}`);
            }
        }
    }
    
    return {
        isValid: errors.length === 0,
        errors: errors
    };
}

/**
 * Valida un formulario completo
 */
function validateForm(formId, validationRules) {
    const form = document.getElementById(formId);
    if (!form) return { isValid: false, errors: {} };
    
    const errors = {};
    let isValid = true;
    
    for (const [fieldName, rules] of Object.entries(validationRules)) {
        const field = form.querySelector(`[name="${fieldName}"]`);
        if (field) {
            const validation = validateField(field, rules);
            if (!validation.isValid) {
                isValid = false;
                errors[fieldName] = validation.errors;
                showFieldError(field, validation.errors[0]);
            } else {
                clearFieldError(field);
            }
        }
    }
    
    return { isValid, errors };
}

/**
 * Muestra error en un campo
 */
function showFieldError(field, message) {
    clearFieldError(field);
    
    field.style.borderColor = '#ff4444';
    field.style.boxShadow = '0 0 5px rgba(255, 68, 68, 0.5)';
    
    const errorDiv = document.createElement('div');
    errorDiv.className = 'field-error';
    errorDiv.textContent = message;
    errorDiv.style.cssText = `
        color: #ff4444;
        font-size: 0.85rem;
        margin-top: 5px;
        animation: fadeIn 0.3s;
    `;
    
    field.parentNode.appendChild(errorDiv);
}

/**
 * Limpia error de un campo
 */
function clearFieldError(field) {
    field.style.borderColor = '';
    field.style.boxShadow = '';
    
    const errorDiv = field.parentNode.querySelector('.field-error');
    if (errorDiv) {
        errorDiv.remove();
    }
}

// ============================================================================
// Utilidades de Formularios
// ============================================================================

/**
 * Convierte FormData a objeto JavaScript
 */
function formDataToObject(formData) {
    const object = {};
    formData.forEach((value, key) => {
        // Si hay múltiples valores con la misma clave, crear un array
        if (object[key]) {
            if (Array.isArray(object[key])) {
                object[key].push(value);
            } else {
                object[key] = [object[key], value];
            }
        } else {
            object[key] = value;
        }
    });
    return object;
}

/**
 * Deshabilita un formulario durante el envío
 */
function disableForm(form, disable = true) {
    const inputs = form.querySelectorAll('input, select, textarea, button');
    inputs.forEach(input => {
        input.disabled = disable;
        if (disable) {
            input.style.opacity = '0.6';
            input.style.cursor = 'not-allowed';
        } else {
            input.style.opacity = '1';
            input.style.cursor = '';
        }
    });
}

/**
 * Maneja el envío de formularios con validación y feedback
 */
function handleFormSubmit(formId, validationRules, onSubmit, options = {}) {
    const form = document.getElementById(formId);
    if (!form) return;
    
    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // Validar formulario
        if (validationRules) {
            const validation = validateForm(formId, validationRules);
            if (!validation.isValid) {
                showError('Por favor, corrige los errores en el formulario');
                return;
            }
        }
        
        // Mostrar loading
        if (options.showLoading !== false) {
            showLoading(options.loadingMessage || 'Enviando...');
        }
        
        // Deshabilitar formulario
        disableForm(form, true);
        
        try {
            // Preparar datos
            const formData = new FormData(form);
            const data = options.useFormData ? formData : formDataToObject(formData);
            
            // Ejecutar callback
            const result = await onSubmit(data);
            
            // Manejar resultado
            if (result.success) {
                if (options.successMessage) {
                    showSuccess(options.successMessage);
                }
                if (options.onSuccess) {
                    options.onSuccess(result);
                } else if (options.redirect) {
                    setTimeout(() => {
                        window.location.href = options.redirect;
                    }, 1500);
                }
            } else {
                showError(result.message || 'Error al procesar la solicitud');
                if (options.onError) {
                    options.onError(result);
                }
            }
        } catch (error) {
            console.error('Error en formulario:', error);
            showError('Error inesperado. Por favor, intenta nuevamente.');
            if (options.onError) {
                options.onError({ error: error.message });
            }
        } finally {
            hideLoading();
            disableForm(form, false);
        }
    });
}

// ============================================================================
// Animaciones CSS (inyectar en head si no existen)
// ============================================================================

function injectAnimations() {
    if (document.getElementById('bimba-animations')) return;
    
    const style = document.createElement('style');
    style.id = 'bimba-animations';
    style.textContent = `
        @keyframes slideInRight {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes slideOutRight {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
        
        @keyframes spin {
            to {
                transform: rotate(360deg);
            }
        }
        
        @keyframes fadeIn {
            from {
                opacity: 0;
            }
            to {
                opacity: 1;
            }
        }
        
        .field-error {
            animation: fadeIn 0.3s;
        }
    `;
    document.head.appendChild(style);
}

// Inyectar animaciones al cargar
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectAnimations);
} else {
    injectAnimations();
}

// ============================================================================
// Utilidades de Optimización
// ============================================================================

/**
 * Debounce: Retrasa la ejecución de una función hasta que no se llame por un tiempo determinado
 * Útil para búsquedas, validaciones en tiempo real, etc.
 */
function debounce(func, wait = 300) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle: Limita la ejecución de una función a una vez por periodo de tiempo
 * Útil para eventos de scroll, resize, etc.
 */
function throttle(func, limit = 300) {
    let inThrottle;
    return function executedFunction(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Cache simple en memoria para evitar requests repetidos
 */
const requestCache = new Map();
const CACHE_TTL = 5 * 60 * 1000; // 5 minutos

function cachedRequest(url, options = {}, ttl = CACHE_TTL) {
    const cacheKey = `${url}:${JSON.stringify(options)}`;
    const cached = requestCache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < ttl) {
        return Promise.resolve(cached.data);
    }
    
    return fetch(url, options)
        .then(response => response.json())
        .then(data => {
            requestCache.set(cacheKey, {
                data: data,
                timestamp: Date.now()
            });
            return data;
        });
}

/**
 * Limpiar cache
 */
function clearCache() {
    requestCache.clear();
}

/**
 * Lazy load de imágenes
 */
function initLazyLoading() {
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        imageObserver.unobserve(img);
                    }
                }
            });
        });
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
}

