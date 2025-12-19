# LocalPix V1.4 Enterprise
### Sistema de Fotografía con Reconocimiento Facial IA

![LocalPix](https://img.shields.io/badge/Version-1.4-blue) ![Python](https://img.shields.io/badge/Python-3.11-green) ![License](https://img.shields.io/badge/License-Proprietary-red)

---

## 🎯 ¿Qué es LocalPix?

Sistema completo de punto de venta (POS) + gestión fotográfica con reconocimiento facial basado en IA, diseñado para parques, eventos y estudios fotográficos.

**Características principales:**
- ✅ Reconocimiento facial automático con Face-API.js
- ✅ POS completo con cupones y promociones
- ✅ Gestión multinivel (Admin/Supervisor/Fotógrafos)
- ✅ Reportes empresariales avanzados
- ✅ Sistema de cierre de caja (EOD) automatizado
- ✅ Personalización de marca (dual theme: día/noche)
- ✅ Privacy Shield (cumple GDPR y Ley 29733 Perú)

---

## 🚀 Deploy Rápido

### Render.com (Gratis)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

Ver guía completa: [`deployment_guide.md`](deployment_guide.md)

---

## 💻 Instalación Local

### Requisitos
- Python 3.11+
- pip
- SQLite3

### Pasos

```bash
# 1. Clonar repositorio
git clone https://github.com/tu-usuario/localpix.git
cd localpix

# 2. Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Ejecutar
python app.py
```

Abre: `http://localhost:5001`

**Login inicial:**
- Usuario: `admin`
- Contraseña: `admin123`

---

## 📦 Estructura del Proyecto

```
localpix/
├── app.py                 # Aplicación Flask principal
├── models.py              # Modelos de base de datos
├── config.py              # Configuración
├── theme_analyzer.py      # Análisis de temas con K-means
├── ai_engine.py           # Motor de reconocimiento facial
├── requirements.txt       # Dependencias Python
├── render.yaml            # Config para Render.com
├── templates/             # Templates HTML
│   ├── admin.html         # Panel de administración
│   ├── client.html        # Interfaz de cliente
│   └── theme_loader.html  # Sistema de temas
├── static/                # Assets estáticos
│   └── style.css          # Estilos globales
└── uploads/               # Fotos subidas
```

---

## 🎨 Funcionalidades

### Para Administradores
- Dashboard con métricas en tiempo real
- Gestión de usuarios (fotógrafos/supervisores)
- Gestión de productos fotográficos
- Sistema de cupones promocionales
- Reportes de ventas avanzados
- Cierre de caja automático (EOD)
- Personalización de temas

### Para Fotógrafos
- Subida masiva de fotos
- Procesamiento automático con IA
- POS para ventas directas
- Historial de ventas

### Para Clientes
- Búsqueda de fotos vía selfie
- Visualización instantánea
- Compra digital o impresa
- Descarga inmediata

---

## 🔧 Configuración

### Variables de Entorno

```env
# Producción
FLASK_ENV=production
PORT=10000
SECRET_KEY=tu-clave-secreta-aqui

# Desarrollo
FLASK_ENV=development
PORT=5001
```

---

## 📊 Stack Tecnológico

**Backend:**
- Flask 3.0
- SQLAlchemy 3.1
- Gunicorn

**Frontend:**
- HTML5/CSS3/JavaScript
- Face-API.js (reconocimiento facial)
- Chart.js (gráficos)

**IA/ML:**
- scikit-learn (K-means para análisis de colores)
- face-api.js (detección y reconocimiento facial)

**Storage:**
- SQLite (desarrollo)
- Compatible con PostgreSQL (producción)

---

## 💰 Licencia

**Propietaria** - Contactar para licenciamiento comercial

---

## 📞 Soporte

Para preguntas o problemas:
- Email: [tu-email@ejemplo.com]
- Documentación: Ver carpeta `/docs`

---

## 🎖️ Autor

Desarrollado para el mercado peruano de parques temáticos y estudios fotográficos.

**Cliente objetivo:** YakuPark y similares

---

## ⚠️ Notas Importantes

1. **Cambiar contraseña de admin** en primera ejecución
2. **Configurar SECRET_KEY** en producción
3. **Backup regular** de la base de datos
4. **Plan Free de Render:** Las fotos se borran al redeploy (usar storage externo para producción)

---

**Version:** 1.4 Enterprise  
**Última actualización:** Diciembre 2024
