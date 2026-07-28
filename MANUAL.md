# Ocaso Gestion - Manual de Usuario

Aplicacion web para la gestion integral de una oficina de seguros Ocaso en Armilla (Granada).

## Indice

1. [Instalacion y acceso](#1-instalacion-y-acceso)
2. [Dashboard](#2-dashboard)
3. [Recibos y Cobros](#3-recibos-y-cobros)
4. [Clientes](#4-clientes)
5. [Polizas](#5-polizas)
6. [Renovaciones](#6-renovaciones)
7. [Listados](#7-listados)
8. [Siniestros](#8-siniestros)
9. [Comunicaciones](#9-comunicaciones)
10. [WhatsApp](#10-whatsapp)
11. [Leads](#11-leads)
12. [Agenda](#12-agenda)
13. [Asistente IA](#13-asistente-ia)
14. [Ajustes](#14-ajustes)
15. [Usuarios y Permisos](#15-usuarios-y-permisos)
16. [Seguridad (2FA)](#16-seguridad-2fa)
17. [API Externa](#17-api-externa)
18. [Copias de Seguridad](#18-copias-de-seguridad)

---

## 1. Instalacion y acceso

### Requisitos
- Docker y Docker Compose instalados

### Instalacion
```bash
git clone https://github.com/amolinagrx/agente-ocaso.git
cd agente-ocaso
docker compose up -d --build
```

### Acceso
- URL: `http://localhost:5050`
- Usuario por defecto: `admin`
- Contrasena por defecto: `ocaso2025`

### Variables de entorno
| Variable | Descripcion | Default |
|---|---|---|
| `OCASO_USER` | Usuario administrador | `admin` |
| `OCASO_PASS` | Contrasena administrador | `ocaso2025` |
| `SECRET_KEY` | Clave secreta Flask | Generada automaticamente |
| `DEEPSEEK_API_KEY` | API Key para Asistente IA | - |
| `OCASO_ENV` | Entorno (`production`/`development`) | `production` |
| `DATA_DIR` | Directorio de datos | `/data` |

### Modo desarrollo (con datos de ejemplo)
```bash
OCASO_ENV=development docker compose up -d --build
```
Esto genera automaticamente 50 clientes, ~170 polizas, ~1900 recibos, 10 siniestros y ~90 renovaciones.

### Navegacion

La aplicacion tiene un **menu lateral azul** a la izquierda con todos los modulos. En la parte superior hay un **buscador universal** (busca por nombre, DNI, telefono, poliza, matricula) y un **toggle de modo oscuro** (icono luna). En dispositivos moviles, el menu lateral se oculta y se muestra con el boton flotante azul de la esquina superior izquierda.

---

## 2. Dashboard

**Ruta**: `Dashboard` en el menu lateral

### KPIs del mes en curso
- **Polizas Ocaso este mes**: suma de unidades de polizas Ocaso nuevas (si una poliza multi cuenta como x3, se suma 3)
- **Otras comp. este mes**: polizas nuevas de otras companias
- **Cobrado este mes**: total de primas cobradas en el mes
- **Devuelto**: total de recibos devueltos en el mes

### Grafico de evolucion
Grafico de barras con los ultimos 12 meses mostrando polizas nuevas y primas cobradas, con doble eje Y.

### Ranking por ramo
Tabla con primas acumuladas por tipo de seguro (Auto, Hogar, Vida, etc.)

### Top 10 clientes
Ranking de los 10 clientes con mayor volumen de prima anual.

---

## 3. Recibos y Cobros

**Ruta**: `Recibos` en el menu lateral

### Tabla principal
- **Filtros**: estado (cobrado/devuelto/pendiente), compania, mes/ano, texto libre
- **Columnas**: cliente, poliza, concepto, importe, fecha emision, fecha cargo, estado (badge de color), gestion

### Colores de estado
- 🟢 **Cobrado**: verde
- 🔴 **Devuelto**: rojo  
- 🟡 **Pendiente**: amarillo

### Gestion de devoluciones
Cada recibo devuelto tiene un boton de engranaje que abre un modal con:
- **Estado de gestion**: contactado, pagado por transferencia, anulado, pendiente de revision
- **Notas**: campo de texto libre

### Cambio rapido de estado
Dropdown en cada fila para marcar directamente como cobrado, devuelto o pendiente.

### Importacion masiva
Boton `Importar` que permite subir archivos CSV o Excel con recibos. Detecta automaticamente las columnas por nombre (cliente, dni, poliza, concepto, importe, fecha, estado). Tambien permite mapeo manual de columnas.

---

## 4. Clientes

**Ruta**: `Clientes` en el menu lateral

### Listado de clientes
Tabla paginada con buscador por nombre, DNI o telefono.

### Ficha de cliente
Al hacer click en un cliente se accede a su ficha con **5 pestanas**:

#### Polizas
Lista de polizas activas del cliente con botones para:
- **Editar** (lapiz): modal con todos los campos de la poliza
- **Dar de baja** (archivo): desactiva la poliza
- **Nueva poliza**: formulario completo de alta

Campos: numero, ramo, capital, prima anual, fecha efecto, fecha vencimiento, IBAN, unidades, detalles.

#### Recibos
Historial de recibos del cliente. Boton `Nuevo Recibo` para dar de alta manualmente.

#### Siniestros
Siniestros asociados. Boton `Nuevo Siniestro` para registrar desde aqui.

#### Historial de contacto
Cronologia de interacciones (llamada, WhatsApp, email, visita) con fecha y notas.

#### Documentos
- **Subir archivo**: seleccionar del disco
- **Camara**: capturar con el dispositivo (se guarda como PDF)
- **Previsualizar, Descargar, Eliminar** cada documento

### Crear cliente
Formulario con: nombre, DNI, direccion, codigo postal (autocompletable con todas las poblaciones de Espana), poblacion, provincia, telefono, email, fecha nacimiento, notas.

### Eliminar cliente
Boton rojo de papelera con confirmacion. Elimina tambien todas sus polizas, recibos y siniestros asociados.

---

## 5. Polizas

**Ruta**: `Polizas` en el menu lateral

Panel independiente para gestionar todas las polizas, sin necesidad de entrar cliente por cliente.

### Filtros
- **Ramo**: desplegable con autocompletado de 37 ramos (Auto, Hogar, Vida, Salud, Comercio, etc.)
- **Estado**: todas, activas, de baja
- **Vencimiento**: proximos 30/60 dias, vencidas
- **Compania**: 40+ aseguradoras (Ocaso, Mapfre, AXA, Allianz...)
- **Buscar**: por cliente, numero de poliza o matricula

### Totales
Contadores de polizas activas, de baja y prima total acumulada.

### Tabla
Columnas ordenables: cliente, poliza, ramo (con indicador x2/x3 si es multi-unidad), compania, prima, capital, fecha efecto, vencimiento, estado.
- Filas en **amarillo**: vencen en <30 dias
- Filas en **rojo**: vencidas

### Acciones
Click en el nombre del cliente lleva a su ficha.

---

## 6. Renovaciones

**Ruta**: `Renovaciones` en el menu lateral

### Contadores superiores
- Vencen en ≤30 dias
- Pendientes de contactar
- Confirmados
- Total proximos 90 dias

### Codigo de colores por urgencia
- 🟢 **Verde**: mas de 60 dias
- 🟡 **Amarillo**: entre 30 y 60 dias
- 🔴 **Rojo**: menos de 30 dias
- ⚫ **Gris**: vencida

### Tabla
Cliente, poliza, ramo, vencimiento, dias restantes, prima, estado de gestion.

### Acciones rapidas
- 📞 **Telefono**: marcar como contactado
- ✉️ **Sobre**: marcar presupuesto enviado
- ✅ **Check**: marcar como confirmado
- Notas opcionales en cada accion

### Estados de gestion
No contactado → Contactado → Presupuesto enviado → Confirmado

### Exportar PDF
Boton que genera un PDF con el listado filtrado para llevar a reuniones.

---

## 7. Listados

**Ruta**: `Listados` en el menu lateral

Informes predefinidos con filtros y totales. Todos tienen boton **Imprimir**.

### Polizas
Filtro por fecha desde/hasta, ramo, estado (activas/bajas) y texto. Totales de cantidad, prima y capital.

### Recibos
Filtro por fecha y estado. Totales separados de cobrado, devuelto y pendiente.

### Produccion
Grafico de evolucion mensual de altas + tabla por ramo con primas y capital. Filtro por ano y mes.

### Siniestros
Filtro por estado (abiertos/cerrados), tipo y texto. Importe estimado total.

Todos los listados se pueden imprimir con el boton de impresora.

---

## 8. Siniestros

**Ruta**: `Siniestros` en el menu lateral

### Tabla principal
- **Columnas**: expediente, cliente, poliza, tipo, fecha ocurrencia, estado, dias sin actualizar
- **Filtros**: por estado y texto
- **Alerta**: filas en rojo si llevan >15 dias sin actualizacion (configurable en Ajustes)

### Estados del siniestro
Abierto → Documentacion enviada → Perito asignado → En taller → En valoracion → Pendiente resolucion → Resuelto → Cerrado

### Ficha del siniestro
- Datos del expediente
- Linea de tiempo con todos los hitos (fecha, estado, notas)
- Documentos asociados con posibilidad de subir nuevos
- Boton `Cambiar estado` para avanzar en el flujo

### Nuevo siniestro
Formulario con: cliente, poliza asociada, numero de expediente, tipo, importe estimado, fechas y descripcion.

---

## 9. Comunicaciones

**Ruta**: `Comunicaciones` en el menu lateral

### Plantillas
Tres tipos de plantillas predefinidas:

#### WhatsApp
Plantillas con variables `{nombre}`, `{poliza}`, `{importe}`, `{fecha}`, `{enlace}`:
- Recibo devuelto
- Renovacion pendiente
- Cita confirmada
- Presupuesto listo
- Siniestro actualizado
- Felicitacion de cumpleanos

#### Email
Plantillas HTML con logo de Ocaso:
- Recibo devuelto
- Renovacion pendiente

#### SMS
Plantillas de texto plano listas para copiar.

### Uso de plantillas
1. Seleccionar plantilla
2. Elegir cliente
3. El mensaje se personaliza automaticamente con los datos del cliente
4. Boton para abrir WhatsApp/Email directamente

### Crear plantillas personalizadas
Boton `Nueva plantilla` para crear tus propias plantillas con las variables disponibles.

---

## 10. WhatsApp

**Ruta**: `WhatsApp` en el menu lateral

### Lista de clientes
Grid de tarjetas con todos los clientes que tienen telefono registrado.

### Filtros
- **Todos**: solo clientes con telefono
- **Con alertas**: clientes con recibos devueltos
- **Contactados/No contactados**: segun historial

### Acciones por cliente
- **Chatear** (boton verde): abre WhatsApp Web con mensaje predefinido
- **Plantillas** (icono documento): elige plantilla o escribe mensaje personalizado
- **Copiar telefono**: copia al portapapeles

### Historial
Registro de todos los mensajes de WhatsApp enviados, con fecha, cliente y contenido.

### Numero de empresa
Se configura en **Ajustes > WhatsApp empresa** (con prefijo 34).

---

## 11. Leads

**Ruta**: `Leads` en el menu lateral

Gestion de prospectos comerciales.

### Estados
- **Nuevo**: recien registrado
- **Contactado**: se ha establecido contacto
- **Presupuesto enviado**: se ha enviado propuesta
- **Ganado**: convertido a cliente
- **Perdido**: no se cerro la venta

### Origenes
Web, Telefono, Presencial, Recomendacion, Otro

### Funcionalidades
- **Grid de tarjetas** con codigo de colores por estado
- **Nuevo lead**: formulario rapido con datos basicos
- **Editar**: todos los campos modificables en modal
- **Cambiar estado**: dropdown con cambio rapido
- **Convertir a cliente** (boton verde): crea automaticamente un cliente con los datos del lead y redirige a la pagina de edicion para completar datos faltantes
- **Eliminar**

---

## 12. Agenda

**Ruta**: `Agenda` en el menu lateral

Agenda personal por usuario. Cada usuario ve solo sus propias entradas.

### Vista Lista
- Entradas del dia seleccionado
- Navegacion por fechas (flechas + selector de fecha)
- Checkbox para marcar como completado
- Tipos: Nota, Llamada, Reunion, Tarea

### Vista Calendario
- Grid mensual con entradas visibles
- Codigo de colores por tipo
- Click en un dia para ver sus entradas

### Funcionalidades
- **Nueva entrada**: modal con titulo, tipo, fecha y notas
- **Toggle completado**: checkbox en cada entrada
- **Eliminar**: con confirmacion

---

## 13. Asistente IA

**Ruta**: `Asistente IA` en el menu lateral

Asistente con IA basado en Deepseek. Dos pestañas:

### Chat
- Conversacion directa con el modelo Deepseek
- El asistente puede consultar los documentos subidos y los datos de la plataforma
- Ejemplos de uso:
  - *"¿Que coberturas tiene el seguro de hogar?"* → consulta documentacion
  - *"¿Que polizas tiene Antonio Garcia?"* → consulta la BD
  - *"¿Cuantos siniestros hay abiertos?"* → consulta estadisticas

### Documentacion
- **Subir documentos**: PDF, Markdown o TXT (max 10MB, multiples archivos)
- **Tabla**: lista de documentos con fecha y tipo
- **Eliminar**: borra el documento del sistema

### Configuracion
Requiere API Key de Deepseek. Se configura en **Ajustes > APIs y servicios**.

---

## 14. Ajustes

**Ruta**: `Ajustes` en el menu lateral

Panel de configuracion unificado.

### Datos de la oficina
Nombre, direccion, telefono, email, WhatsApp empresa.

### Alertas
Dias sin actualizacion para marcar siniestros en rojo (default: 15).

### APIs y servicios
- **Deepseek API Key**: para el Asistente IA. Se puede configurar por variable de entorno o desde esta interfaz.
- **Estadisticas del asistente**: documentos, fragmentos y mensajes.

### API Keys
Gestion de tokens de acceso para la API externa. Generar claves con nombre (ej: "Zapier", "PowerBI") y revocarlas cuando sea necesario.

### Copia de seguridad y reset
- **Exportar backup**: descarga la base de datos SQLite completa
- **Importar backup**: restaura desde un archivo .db (hace copia de seguridad previa)
- **Borrar todos los datos**: requiere codigo de seguridad y confirmacion. Elimina clientes, polizas, recibos, siniestros... pero conserva los usuarios.

---

## 15. Usuarios y Permisos

**Ruta**: `Usuarios` en el menu lateral (solo visible para administradores)

### Tipos de usuario
- **Administrador**: acceso total a todos los modulos
- **Usuario**: permisos granulares por modulo

### Permisos por modulo
Cada uno de los 13 modulos puede tener:
- **Lectura y Escritura (rw)**: acceso completo
- **Solo Lectura (r)**: puede ver pero no modificar
- **Sin acceso (none)**: el modulo no aparece en el menu

### Gestion de usuarios
- **Crear**: usuario, contrasena, nombre, tipo (admin/usuario) y permisos
- **Editar**: cambiar nombre, permisos, activo/inactivo
- **Cambiar contrasena**: desde la pantalla de edicion
- **Eliminar**: borra el usuario (no se puede auto-eliminar)

### Visibilidad del menu
El menu lateral se adapta a los permisos de cada usuario. Los modulos sin acceso no aparecen.

---

## 16. Seguridad (2FA)

### Autenticacion en dos pasos
Cada usuario puede activar 2FA con aplicaciones authenticator (Google Authenticator, Authy, Microsoft Authenticator).

### Activar 2FA
1. Ir a **Usuarios > icono del escudo** junto al usuario
2. Escanear el codigo QR con la app
3. Introducir el codigo de 6 digitos para verificar

### Inicio de sesion con 2FA
1. Usuario + contrasena
2. Si 2FA activado → pantalla de codigo de verificacion
3. Introducir codigo de la app authenticator

### Recordar equipo
Checkbox "Recordar este equipo 7 dias" (marcado por defecto). Al verificarte, no se vuelve a pedir el codigo en ese navegador durante 7 dias. Al cerrar sesion se elimina la cookie.

### Recuperacion
Si un usuario pierde el acceso a su app authenticator, el administrador puede desactivar 2FA desde Usuarios.

---

## 17. API Externa

La aplicacion expone una API REST para integraciones con terceros (agentes IA, Zapier, PowerBI, etc.).

### Autenticacion
Header HTTP: `X-API-Key: tu-token`

Los tokens se generan en **Ajustes > API Keys**.

### Endpoints disponibles

| Metodo | Ruta | Descripcion |
|---|---|---|
| GET | `/v1/health` | Estado del servicio (sin auth) |
| GET | `/v1/search?q=` | Busqueda unificada |
| GET | `/v1/stats` | Estadisticas generales |
| GET | `/v1/me` | Info del token actual |
| GET/POST | `/v1/clientes` | Listar/Crear clientes |
| GET/PUT/DELETE | `/v1/clientes/:id` | Ver/Editar/Eliminar cliente |
| GET/POST | `/v1/clientes/:id/documentos` | Listar/Subir documentos |
| GET/POST | `/v1/polizas` | Listar/Crear polizas |
| GET/PUT/DELETE | `/v1/polizas/:id` | Ver/Editar/Eliminar poliza |
| GET/POST | `/v1/recibos` | Listar/Crear recibos |
| GET | `/v1/siniestros` | Listar siniestros |
| GET/POST | `/v1/leads` | Listar/Crear leads |

### Ejemplos

```bash
# Listar clientes
curl -H "X-API-Key: mi-token" http://localhost:5050/v1/clientes

# Crear cliente
curl -X POST -H "X-API-Key: mi-token" \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Nuevo Cliente","telefono":"600111222"}' \
  http://localhost:5050/v1/clientes

# Buscar
curl -H "X-API-Key: mi-token" \
  "http://localhost:5050/v1/search?q=garcia"

# Subir documento
curl -X POST -H "X-API-Key: mi-token" \
  -F "documento=@poliza.pdf" -F "tipo=poliza" \
  http://localhost:5050/v1/clientes/1/documentos
```

### Paginacion
Todos los endpoints de listado aceptan `?page=1&per_page=50` (max 200).

---

## 18. Copias de Seguridad

### Exportar
En **Ajustes > Copia de seguridad y reset > Exportar backup** se descarga un archivo `.db` con toda la base de datos.

### Importar
En **Ajustes > Copia de seguridad y reset > Importar backup** se restaura desde un archivo `.db`. Automaticamente se guarda una copia de la BD actual antes de sobrescribir.

### Reset completo
En **Ajustes > Copia de seguridad y reset > Borrar todos los datos**:
1. Requiere codigo de seguridad
2. Requiere escribir "BORRAR TODO" para confirmar
3. Elimina todos los datos de negocio pero conserva los usuarios y sus permisos

### Volumen Docker
La base de datos persiste en el volumen `ocaso_data`. Al reconstruir el contenedor sin eliminar el volumen (`docker compose down` sin `-v`), los datos se mantienen.

---

## Resumen de modulos

| Modulo | Icono | Funcion principal |
|---|---|---|
| Dashboard | 🏠 | KPIs y graficos |
| Recibos | 🧾 | Gestion de cobros y devoluciones |
| Clientes | 👥 | Fichas, polizas, documentos |
| Polizas | 📄 | Panel de todas las polizas |
| Renovaciones | 📅 | Agenda de vencimientos |
| Listados | 📊 | Informes imprimibles |
| Siniestros | ⚠️ | Seguimiento de expedientes |
| Comunicaciones | 💬 | Plantillas WhatsApp/Email/SMS |
| WhatsApp | 💚 | Envio directo a clientes |
| Leads | 👤 | Prospectos comerciales |
| Agenda | 📝 | Notas personales |
| Asistente IA | 🤖 | Chat con IA + documentacion |
| Ajustes | ⚙️ | Configuracion y respaldos |
| Usuarios | 👥🔧 | Gestion de accesos |

---

## Atajos de teclado

| Tecla | Accion |
|---|---|
| `Ctrl+K` o `/` | Foco en el buscador universal |
| `Esc` | Cerrar sidebar (movil) / cerrar modales |
| `Enter` | Enviar mensaje en chat IA |
| `Shift+Enter` | Nueva linea en chat IA |

---

## Soporte

- **Repositorio**: https://github.com/amolinagrx/agente-ocaso
- **Version**: 1.0
- **Stack**: Python 3.11 + Flask + SQLite + Bootstrap 5 + HTMX
