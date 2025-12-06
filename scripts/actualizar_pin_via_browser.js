// Script para ejecutar en la consola del navegador en https://stvaldivia.cl
// Después de iniciar sesión como administrador

// Actualizar PIN del empleado ID 6 (Sebastian Cañizarez) a 1025
fetch('/admin/equipo/api/employees/6', {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    name: 'Sebastian Cañizarez',
    cargo: 'CAJA',
    pin: '1025',
    active: true
  })
})
.then(response => response.json())
.then(data => {
  console.log('✅ Resultado:', data);
  if (data.success) {
    alert('✅ PIN actualizado correctamente a 1025');
  } else {
    alert('❌ Error: ' + data.message);
  }
})
.catch(error => {
  console.error('❌ Error:', error);
  alert('❌ Error al actualizar PIN: ' + error.message);
});

