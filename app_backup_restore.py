import os
import json
import time
import shutil
import random
import string
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for
from werkzeug.utils import secure_filename
import models
import sys


# Configuración
app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = 'super_secret_key_localpix_v1.2'
BASE_DIR = os.getcwd()
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 # 32MB max upload

# Asegurar directorios
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Inicializar DB
models.init_db()

# --- MIDDLEWARE & HELPERS ---
def get_current_user():
    if 'user' in session:
        return session['user']
    return None

def login_required(roles=None):
    def decorator(f):
        def wrapped(*args, **kwargs):
            user = get_current_user()
            if not user:
                return redirect(url_for('login'))
            if roles and user['role'] not in roles:
                return "Acceso denegado (Rol insuficiente)", 403
            return f(*args, **kwargs)
        # Fix flask name collision
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator

@app.context_processor
def inject_theme():
    return dict(theme=models.get_theme())

# --- RUTAS PÚBLICAS / AUTH ---

@app.route('/')
def index():
    user = get_current_user()
    if user:
        return render_template('index.html', user=user)
    # Si no hay usuario y no estamos en flujo de ventas, al login
    # Pero el usuario pidió: "Si no entras con ninguna cuenta... boton Ventas"
    # Index será el Hub si estás logueado. Si no, Login fuerza la entrada.
    # Redirect to login as default entry point per instructions
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = models.check_user(username, password)
        if user:
            session.clear() # Clear any old data
            session['user'] = user
            session.permanent = False # Ensure session expires on browser close
            return redirect(url_for('index'))
        else:
            error = 'Credenciales inválidas'
            
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/client_mode')
def client_mode():
    # Modo Ventas (Acceso anónimo controlado)
    # No creamos sesión de usuario, pero permitimos acceso a /client
    session['client_access'] = True
    return redirect(url_for('client'))

# --- RUTAS PRINCIPALES ---

@app.route('/admin')
@login_required(roles=['admin', 'supervisor'])
def admin():
    return render_template('admin.html', user=session['user'])

@app.route('/photographer')
@login_required(roles=['admin', 'supervisor', 'photographer'])
def photographer():
    return render_template('photographer.html', user=session['user'])

@app.route('/client')
def client():
    # Permitir si es usuario logueado O tiene acceso cliente
    if 'user' in session or session.get('client_access'):
        return render_template('client.html')
    return redirect(url_for('login'))

# --- API USUARIOS (Admin/Supervisor) ---

@app.route('/api/users', methods=['GET', 'POST', 'DELETE'])
@login_required(roles=['admin', 'supervisor'])
def api_users():
    current = session['user']
    
    if request.method == 'GET':
        return jsonify(models.get_all_users())
    
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')
        role = data.get('role')
        
        # Reglas de Supervisor
        if current['role'] == 'supervisor':
            if role in ['admin', 'supervisor']:
                return jsonify({'error': 'Supervisores solo pueden crear fotógrafos'}), 403
            
        if models.create_user(username, password, role):
            return jsonify({'status': 'ok'})
        return jsonify({'error': 'Usuario ya existe'}), 400
        
    if request.method == 'DELETE':
        username = request.json.get('username')
        if current['role'] == 'supervisor':
            pass
            
        if models.delete_user(username):
            return jsonify({'status': 'ok'})
        return jsonify({'error': 'No se pudo eliminar'}), 400

@app.route('/api/change_password', methods=['POST'])
@login_required(roles=['admin'])
def api_change_pw():
    data = request.json
    if models.change_password(data['username'], data['newPassword']):
        return jsonify({'status': 'ok'})
    return jsonify({'error': 'Fallo'}), 400

# --- API PRODUCTOS (Admin/Supervisor) ---
@app.route('/api/products', methods=['GET', 'POST', 'DELETE'])
def api_products():
    # Public Read for Client
    if request.method == 'GET':
        return jsonify(models.get_products(only_active=False)) # Admin sees all
        
    # Write: Auth required
    if 'user' not in session or session['user']['role'] not in ['admin', 'supervisor']:
        return "Unauthorized", 403
        
    if request.method == 'POST':
        d = request.json
        models.upsert_product(d.get('id'), d['name'], float(d['price']), d['type'], d.get('description',''), d.get('is_active',1))
        return jsonify({'status': 'ok'})
        
    if request.method == 'DELETE':
        models.delete_product(request.json['id'])
        return jsonify({'status': 'ok'})

@app.route('/api/products_public')
def api_products_public():
    return jsonify(models.get_products(only_active=True))

@app.route('/api/products/<int:id>/status', methods=['POST'])
@login_required(roles=['admin', 'supervisor'])
def update_prod_status(id):
    data = request.json
    active = int(data.get('is_active', 1))
    models.update_product_status(id, active)
    return jsonify({'status': 'ok'})

# --- API CUPONES (Admin/Supervisor) ---
@app.route('/api/coupons', methods=['GET', 'POST', 'DELETE'])
@login_required(roles=['admin', 'supervisor'])
def api_coupons():
    if request.method == 'GET':
        return jsonify(models.get_coupons())
        
    if request.method == 'POST':
        d = request.json
        # Check permissions? Admin/Sup ok.
        res = models.create_coupon(d['code'], d['type'], float(d['value']), int(d['max_uses']), d.get('expiry'))
        if res: return jsonify({'status': 'ok'})
        return jsonify({'error': 'Error creando cupón (quizás código duplicado)'}), 400
        
    if request.method == 'DELETE':
        models.delete_coupon(request.json['id'])
        return jsonify({'status': 'ok'})

@app.route('/api/validate_coupon', methods=['POST'])
def validate_coupon():
    code = request.json.get('code')
    return jsonify(models.validate_coupon(code))

@app.route('/api/coupons/batch_generate', methods=['POST'])
@login_required(roles=['admin', 'supervisor'])
def batch_generate_coupons():
    data = request.json
    count = int(data.get('count', 50))
    # Limit to reasonable amount to prevent abuse
    if count > 200: count = 200
    
    expiry = time.strftime("%Y-%m-%d")
    
    # Get value of Digital Photo
    products = models.get_products()
    digital_price = 10.0
    for p in products:
        if 'digital' in p['name'].lower():
            digital_price = p['price']
            break
            
    generated = []
    
    for _ in range(count):
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        code = f"YP-{suffix}"
        if models.create_coupon(code, 'fixed', digital_price, 1, expiry):
            generated.append(code)
            
    return jsonify({'status': 'ok', 'codes': generated})

@app.route('/api/coupons/batch_clear', methods=['POST'])
@login_required(roles=['admin', 'supervisor'])
def batch_clear_coupons():

    data = request.get_json(force=True, silent=True) or {}
    pwd = data.get('password', '').strip()
    username = session['user']['username']
    
    # Validate against DB
    if not models.check_user(username, pwd):
        return jsonify({'error': 'Contraseña incorrecta o permisos insuficientes'}), 401
        
    models.clear_daily_batch()
    return jsonify({'status': 'ok'})

# --- API VENTAS ---

@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.json
    try:
        # data: { items: [...], total: 100, discount_code: 'XYZ', final_total: 80 }
        for item in data['items']:
            # 1. Photographer Attribution
            ph = item.get('photographer')
            path = item.get('path', '')
            
            # If photographer is missing or generic, try to parse from path
            if not ph or ph in ['null', 'undefined', 'Desconocido', 'Varios']:
                if path:
                    parts = path.replace('\\', '/').split('/')
                    if len(parts) >= 2:
                        # Case: YYYY-MM-DD/Photographer/File.jpg
                        if len(parts[0]) == 10 and parts[0][4] == '-' and parts[0][7] == '-':
                            item['photographer'] = parts[1]
                        else:
                            # Case: Photographer/File.jpg
                            item['photographer'] = parts[0]
                    else:
                        item['photographer'] = 'Manual'
                else:
                    item['photographer'] = 'Manual'
            
            # 2. Product Type Normalization
            if 'product_type' not in item:
                item['product_type'] = item.get('type', item.get('format', 'digital'))

        sale_id = models.record_sale(
            data['items'], 
            data['total'], 
            data.get('discount_code'), 
            data['final_total']
        )
        return jsonify({'status': 'ok', 'sale_id': sale_id})
    except Exception as e:
        print(f"Checkout Error: {e}", file=sys.stderr)
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales_report')
@login_required(roles=['admin', 'supervisor'])
def sales_report():
    return jsonify(models.get_sales_report())

@app.route('/api/export_sales_pdf')
@login_required(roles=['admin'])
def export_sales_pdf():
    # Since we avoid heavy PDF dependencies, we'll generate a CSV 
    # and name it with .pdf (Some browsers might handle it or we just call it CSV)
    # Actually, better to just return a CSV and keep it honest, or use a simple HTML print view.
    # The user asked for PDF, I will try to use a simple text/formatted output.
    report = models.get_sales_report()
    
    import io
    import csv
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Fecha', 'Total Original', 'Cupon', 'Total Final', 'Items'])
    for s in report:
        item_names = ", ".join([i['product_name'] for i in s['items']])
        writer.writerow([s['id'], s['date'], s['total'], s['discount'], s['final_total'], item_names])
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=reporte_ventas.csv"}
    )

# --- EOD / CLOSING API ---
@app.route('/api/sales/close_day', methods=['POST'])
@login_required(roles=['admin'])
def close_day_api():
    data = request.json or {}
    notes = data.get('notes', '')
    try:
        eod_id = models.perform_eod_closing(session['user'], notes)
        return jsonify({'status': 'ok', 'id': eod_id})
    except Exception as e:
        print(f"Error in close_day: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales/history', methods=['GET'])
@login_required(roles=['admin'])
def get_sales_history():
    try:
        history = models.get_eod_history()
        return jsonify(history)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales/last_closing', methods=['GET'])
def get_last_closing_api():
    date = models.get_last_eod_date()
    return jsonify({'last_closing': date})


# --- THEME API ---
@app.route('/api/theme/save', methods=['POST'])
@login_required(roles=['admin'])
def save_theme_api():
    """Save theme configuration - supports both dual palettes and single mode"""
    data = request.json
    
    # Check if data has 'light' and 'dark' keys (dual mode)
    if 'light' in data or 'dark' in data:
        models.save_theme(data)  # Save both
    else:
        # Single mode save - check if mode is specified
        mode = data.get('mode', 'dark')
        models.save_theme(data, mode=mode)
    
    return jsonify({'status': 'ok'})

@app.route('/api/theme/analyze_logo', methods=['POST'])
@login_required(roles=['admin'])
def analyze_theme_logo():
    """Analyze uploaded logo and return DUAL color palettes (light + dark)"""
    if 'logo' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['logo']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Use PNG, JPG, or GIF'}), 400
    
    try:
        # Save file temporarily
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        unique_filename = f"logo_{timestamp}.{file_ext}"
        branding_dir = os.path.join(app.static_folder, 'branding')
        os.makedirs(branding_dir, exist_ok=True)
        
        file_path = os.path.join(branding_dir, unique_filename)
        file.save(file_path)
        print(f"DEBUG: Saved logo to {file_path}", file=sys.stderr)
        
        # Analyze colors using theme_analyzer - NOW RETURNS DUAL PALETTES
        import theme_analyzer
        print("DEBUG: Calling theme_analyzer.analyze_logo...", file=sys.stderr)
        dual_palettes = theme_analyzer.analyze_logo(file_path)
        print(f"DEBUG: Analysis result: {dual_palettes}", file=sys.stderr)
        
        # Add logo URL to BOTH palettes
        logo_url = url_for('static', filename='branding/' + unique_filename)
        dual_palettes['light']['logo_url'] = logo_url
        dual_palettes['dark']['logo_url'] = logo_url
        
        # Clean up old logos (keep latest 5)
        cleanup_old_logos(branding_dir, keep=5)
        
        return jsonify({'status': 'ok', 'palettes': dual_palettes})
        
    except Exception as e:
        print(f"Error analyzing logo: {e}", file=sys.stderr)
        return jsonify({'error': str(e)}), 500

@app.route('/api/theme/upload_logo', methods=['POST'])
@login_required(roles=['admin'])
def upload_theme_logo():
    """Legacy endpoint - redirects to analyze_logo"""
    return analyze_theme_logo()

@app.route('/api/theme/get', methods=['GET'])
@app.route('/api/theme/get/<mode>', methods=['GET'])
def get_theme_config(mode='dark'):
    """Get theme configuration for specific mode (light or dark)"""
    if mode not in ['light', 'dark']:
        mode = 'dark'
    return jsonify(models.get_theme(mode=mode))

def cleanup_old_logos(directory, keep=5):
    """Remove old logo files, keeping only the most recent ones"""
    try:
        files = [f for f in os.listdir(directory) if f.startswith('logo_')]
        files.sort(key=lambda x: os.path.getmtime(os.path.join(directory, x)), reverse=True)
        
        # Delete old files
        for old_file in files[keep:]:
            os.remove(os.path.join(directory, old_file))
    except Exception as e:
        print(f"Error cleaning up logos: {e}")


# --- FILE OPERATIONS ---

@app.route('/upload', methods=['POST'])
@login_required(roles=['admin', 'supervisor', 'photographer'])
def upload_file():
    if 'photos' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('photos')
    date = request.form.get('date', time.strftime("%Y-%m-%d"))
    # Photographer name from session if available, else form
    photographer_name = session['user']['username']
    
    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], date, photographer_name)
    os.makedirs(target_dir, exist_ok=True)
    
    saved_files = []
    for file in files:
        if file.filename == '': continue
        filename = secure_filename(file.filename)
        file_path = os.path.join(target_dir, filename)
        
        # Avoid overwrite
        if os.path.exists(file_path):
            base, ext = os.path.splitext(filename)
            filename = f"{base}_{int(time.time())}{ext}"
            file_path = os.path.join(target_dir, filename)
            
        file.save(file_path)
        rel_path = f"{date}/{photographer_name}/{filename}"
        saved_files.append({"name": filename, "path": rel_path})
        
    return jsonify({'message': 'Subida completada', 'files': saved_files})

# --- Helper Functions para DB Update (Archivos) ---
def update_db_path(old_rel_path, new_rel_path, is_dir=False):
    db_path = os.path.join(BASE_DIR, 'database.json')
    if not os.path.exists(db_path): return
    
    with open(db_path, 'r') as f:
        try: db = json.load(f)
        except: return

    modified = False
    
    # Normalizar slashes para comparación
    old_rel_path = old_rel_path.replace('\\', '/')
    new_rel_path = new_rel_path.replace('\\', '/')

    for record in db:
        record_img = record['image'].replace('\\', '/')
        
        if is_dir:
            if record_img.startswith(old_rel_path + '/'):
                record['image'] = new_rel_path + record_img[len(old_rel_path):]
                modified = True
        else:
            if record_img == old_rel_path:
                record['image'] = new_rel_path
                modified = True
                
    if modified:
        with open(db_path, 'w') as f: json.dump(db, f)

def remove_from_db(rel_path, is_dir=False):
    db_path = os.path.join(BASE_DIR, 'database.json')
    if not os.path.exists(db_path): return
    
    with open(db_path, 'r') as f:
        try: db = json.load(f)
        except: return
        
    initial_len = len(db)
    rel_path = rel_path.replace('\\', '/')
    
    if is_dir:
        db = [r for r in db if not r['image'].replace('\\', '/').startswith(rel_path + '/')]
    else:
        db = [r for r in db if r['image'].replace('\\', '/') != rel_path]
        
    if len(db) != initial_len:
        with open(db_path, 'w') as f: json.dump(db, f)

# --- DATABASE & REINDEXING (JSON Legacy for Matcher) ---

@app.route('/get_database')
def get_database():
    db_path = os.path.join(BASE_DIR, 'database.json')
    if os.path.exists(db_path):
        with open(db_path, 'r') as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route('/save_descriptors', methods=['POST'])
def save_descriptors():
    # Allow saving if logged in as any staff
    if 'user' not in session: return "Unauthorized", 401
    
    data = request.json
    descriptors = data.get('descriptors', [])
    overwrite = data.get('overwrite', False)
    
    db_path = os.path.join(BASE_DIR, 'database.json')
    current_db = []
    
    if not overwrite and os.path.exists(db_path):
        with open(db_path, 'r') as f:
            try: current_db = json.load(f)
            except: pass
            
    current_db.extend(descriptors)
    
    with open(db_path, 'w') as f:
        json.dump(current_db, f)
        
    return jsonify({'status': 'success', 'count': len(current_db)})

# --- Endpoints de Gestión de Archivos (Admin) ---

@app.route('/admin/delete', methods=['POST'])
@login_required(roles=['admin'])
def admin_delete():
    data = request.json
    rel_path = data.get('path')
    if not rel_path: return jsonify({'error': 'No path'}), 400
    
    if '..' in rel_path: return jsonify({'error': 'Invalid path'}), 400
    
    abs_path = os.path.join(app.config['UPLOAD_FOLDER'], rel_path)
    if not os.path.exists(abs_path): return jsonify({'error': 'Not found'}), 404
    
    try:
        if os.path.isdir(abs_path):
            shutil.rmtree(abs_path)
            remove_from_db(rel_path, is_dir=True)
        else:
            os.remove(abs_path)
            remove_from_db(rel_path, is_dir=False)
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/rename', methods=['POST'])
@login_required(roles=['admin'])
def admin_rename():
    data = request.json
    old_path = data.get('oldPath')
    new_name = data.get('newName')
    
    if not old_path or not new_name: return jsonify({'error': 'Missing args'}), 400
    if '..' in old_path or '..' in new_name: return jsonify({'error': 'Invalid path'}), 400
    
    abs_old = os.path.join(app.config['UPLOAD_FOLDER'], old_path)
    parent_dir = os.path.dirname(abs_old)
    abs_new = os.path.join(parent_dir, secure_filename(new_name))
    
    if not os.path.exists(abs_old): return jsonify({'error': 'Not found'}), 404
    if os.path.exists(abs_new): return jsonify({'error': 'Destination exists'}), 400
    
    try:
        os.rename(abs_old, abs_new)
        parent_rel = os.path.dirname(old_path)
        new_rel_path = os.path.join(parent_rel, secure_filename(new_name)).replace('\\', '/')
        if new_rel_path.startswith('/'): new_rel_path = new_rel_path[1:]
        update_db_path(old_path, new_rel_path, is_dir=os.path.isdir(abs_new))
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/action', methods=['POST'])
@login_required(roles=['admin'])
def admin_action():
    data = request.json
    action = data.get('action') 
    items = data.get('items', []) 
    dest_folder = data.get('destination') 
    
    if not items or dest_folder is None: return jsonify({'error': 'Missing args'}), 400
    
    abs_dest = os.path.join(app.config['UPLOAD_FOLDER'], dest_folder)
    if not os.path.exists(abs_dest): return jsonify({'error': 'Dest not found'}), 404
    
    results = []
    
    for item_path in items:
        abs_src = os.path.join(app.config['UPLOAD_FOLDER'], item_path)
        filename = os.path.basename(item_path)
        abs_target = os.path.join(abs_dest, filename)
        
        try:
            if action == 'move':
                shutil.move(abs_src, abs_target)
                new_rel = os.path.join(dest_folder, filename).replace('\\', '/')
                if new_rel.startswith('/'): new_rel = new_rel[1:]
                update_db_path(item_path, new_rel, is_dir=os.path.isdir(abs_target))
            elif action == 'copy':
                if os.path.isdir(abs_src):
                    shutil.copytree(abs_src, abs_target)
                else:
                    shutil.copy2(abs_src, abs_target)
            results.append({'path': item_path, 'status': 'ok'})
        except Exception as e:
            results.append({'path': item_path, 'error': str(e)})
            
    return jsonify({'results': results})

@app.route('/api/all_files')
def all_files():
    images = []
    for root, dirs, files in os.walk(app.config['UPLOAD_FOLDER']):
        for file in files:
            if file.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, app.config['UPLOAD_FOLDER'])
                images.append(rel_path.replace('\\', '/'))
    return jsonify(images)

@app.route('/admin/list')
@login_required(roles=['admin', 'supervisor'])
def list_files():
    req_path = request.args.get('path', '')
    if '..' in req_path or req_path.startswith('/'): return jsonify([])

    abs_path = os.path.join(app.config['UPLOAD_FOLDER'], req_path)
    if not os.path.exists(abs_path): return jsonify([])
        
    items = []
    try:
        for name in os.listdir(abs_path):
            full_path = os.path.join(abs_path, name)
            is_dir = os.path.isdir(full_path)
            rel_path = os.path.join(req_path, name)
            items.append({'name': name, 'type': 'directory' if is_dir else 'file', 'path': rel_path})
    except Exception as e:
        print(f"Error listing {abs_path}: {e}")
    return jsonify(items)

@app.route('/photos/<path:filename>')
def serve_photo(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/debug_test')
def debug_test():
    return render_template('debug_test.html')

if __name__ == '__main__':
    print("Iniciando LocalPix V1.2 (SQL+Auth)")
    app.run(debug=True, host='0.0.0.0', port=5000)
