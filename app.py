import os
import time
import json
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, init_db, Photo, User, Sale, SaleItem, Product, Coupon, EODReport, FaceDescriptor, ConfigEntry, get_theme, save_theme
import theme_analyzer
import shutil
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

app = Flask(__name__)
app.config.from_object(Config)
db.init_app(app)

@app.context_processor
def inject_theme():
    # Try to get mode from cookie or session, default to dark
    mode = session.get('theme_mode', 'light')
    return dict(theme=get_theme(mode=mode))

# Initialize Database and Default Admin
with app.app_context():
    init_db(app)
    if not User.query.filter_by(username='admin').first():
        admin = User(
            username='admin', 
            password=generate_password_hash('admin123', method='pbkdf2:sha256'), 
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
    
    # Add sample product if none exist
    if not Product.query.first():
        p1 = Product(name='Digital HD', price=15.0, product_type='digital', description='Foto en alta resolución vía email')
        p2 = Product(name='Impresión 10x15', price=20.0, product_type='print', description='Impresión física en papel fotográfico')
        db.session.add_all([p1, p2])
        db.session.commit()

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
        wrapped.__name__ = f.__name__
        return wrapped
    return decorator

@app.route('/')
def index():
    user = get_current_user()
    if user:
        return render_template('index.html', user=user)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session.clear()
            session['user'] = {'id': user.id, 'username': user.username, 'role': user.role}
            return redirect(url_for('index'))
        return render_template('login.html', error='Credenciales inválidas')
    return render_template('login.html')

@app.route('/client_mode')
def client_mode():
    # Modo Ventas (Acceso anónimo controlado)
    session['client_access'] = True
    return redirect(url_for('client'))

@app.route('/client')
def client():
    return render_template('client.html')

@app.route('/admin')
@login_required(roles=['admin', 'supervisor'])
def admin():
    return render_template('admin.html', user=session['user'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/photographer')
@login_required(roles=['admin', 'supervisor', 'photographer'])
def photographer():
    return render_template('photographer.html', user=session['user'])

# --- ADMIN FILE MANAGEMENT ---
@app.route('/admin/list')
@login_required(roles=['admin', 'supervisor'])
def admin_list_files():
    rel = request.args.get('path', '')
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], rel)
    if not os.path.exists(full_path): return jsonify([])
    items = []
    for entry in os.scandir(full_path):
        items.append({
            'name': entry.name,
            'path': os.path.join(rel, entry.name).replace('\\', '/'),
            'type': 'directory' if entry.is_dir() else 'file'
        })
    return jsonify(items)

@app.route('/admin/delete', methods=['POST'])
@login_required(roles=['admin'])
def admin_delete():
    path = request.json.get('path')
    full = os.path.join(app.config['UPLOAD_FOLDER'], path)
    if os.path.exists(full):
        try:
            if os.path.isdir(full): shutil.rmtree(full)
            else: os.remove(full)
            return jsonify({'status': 'ok'})
        except Exception as e: return jsonify({'error': str(e)}), 500
    return jsonify({'error': 'Not found'}), 404

@app.route('/admin/rename', methods=['POST'])
@login_required(roles=['admin'])
def admin_rename():
    old_p = request.json.get('oldPath')
    new_n = request.json.get('newName')
    old_full = os.path.join(app.config['UPLOAD_FOLDER'], old_p)
    new_full = os.path.join(os.path.dirname(old_full), new_n)
    try:
        os.rename(old_full, new_full)
        return jsonify({'status': 'ok'})
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/admin/action', methods=['POST'])
@login_required(roles=['admin'])
def admin_action():
    action = request.json.get('action')
    dest = request.json.get('dest', '')
    items = request.json.get('items', [])
    dest_full = os.path.join(app.config['UPLOAD_FOLDER'], dest)
    os.makedirs(dest_full, exist_ok=True)
    try:
        for p in items:
            src = os.path.join(app.config['UPLOAD_FOLDER'], p)
            if action == 'move': shutil.move(src, os.path.join(dest_full, os.path.basename(src)))
            else:
                if os.path.isdir(src): shutil.copytree(src, os.path.join(dest_full, os.path.basename(src)))
                else: shutil.copy2(src, dest_full)
        return jsonify({'status': 'ok'})
    except Exception as e: return jsonify({'error': str(e)}), 500

# --- API USUARIOS ---
@app.route('/api/users', methods=['GET', 'POST', 'DELETE', 'PUT'])
@login_required(roles=['admin', 'supervisor'])
def api_users():
    current = session['user']
    if request.method == 'GET':
        users = User.query.all()
        return jsonify([{
            'id': u.id, 
            'username': u.username, 
            'role': u.role,
            'first_name': u.first_name,
            'last_name': u.last_name,
            'email': u.email,
            'phone': u.phone,
            'department': u.department,
            'is_active': u.is_active,
            'created_at': u.created_at.isoformat() if u.created_at else None
        } for u in users])
    
    if request.method == 'POST':
        data = request.json
        
        # Validate required fields
        if not data.get('username'):
            return jsonify({'error': 'El nombre de usuario es requerido'}), 400
        if not data.get('password'):
            return jsonify({'error': 'La contraseña es requerida'}), 400
            
        # Check if username exists
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'El nombre de usuario ya existe'}), 400
        
        # Check if email exists (if provided)
        if data.get('email') and User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'El correo electrónico ya está registrado'}), 400
        
        from werkzeug.security import generate_password_hash
        hashed = generate_password_hash(data['password'], method='pbkdf2:sha256')
        
        new_user = User(
            username=data['username'], 
            password=hashed, 
            role=data.get('role', 'photographer'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            email=data.get('email'),
            phone=data.get('phone'),
            department=data.get('department'),
            is_active=data.get('is_active', True)
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'status': 'ok', 'user_id': new_user.id})
    
    if request.method == 'PUT':
        data = request.json
        user_id = data.get('id')
        
        if not user_id:
            return jsonify({'error': 'ID de usuario requerido'}), 400
            
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        # Check username uniqueness if changing
        if data.get('username') and data['username'] != user.username:
            if User.query.filter_by(username=data['username']).first():
                return jsonify({'error': 'El nombre de usuario ya existe'}), 400
            user.username = data['username']
        
        # Check email uniqueness if changing
        if data.get('email') and data['email'] != user.email:
            if User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'El correo electrónico ya está registrado'}), 400
            user.email = data['email']
        
        # Update other fields
        if 'first_name' in data: user.first_name = data['first_name']
        if 'last_name' in data: user.last_name = data['last_name']
        if 'phone' in data: user.phone = data['phone']
        if 'department' in data: user.department = data['department']
        if 'role' in data: user.role = data['role']
        if 'is_active' in data: user.is_active = data['is_active']
        
        # Update password if provided
        if data.get('password'):
            from werkzeug.security import generate_password_hash
            user.password = generate_password_hash(data['password'], method='pbkdf2:sha256')
        
        db.session.commit()
        return jsonify({'status': 'ok'})

    if request.method == 'DELETE':
        user_id = request.json.get('id')
        user = User.query.get(user_id)
        if user:
            db.session.delete(user)
            db.session.commit()
            return jsonify({'status': 'ok'})
        return jsonify({'error': 'No encontrado'}), 404

@app.route('/api/users/<int:user_id>/toggle_status', methods=['POST'])
@login_required(roles=['admin'])
def toggle_user_status(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'Usuario no encontrado'}), 404
    
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'status': 'ok', 'is_active': user.is_active})

# --- API PRODUCTOS ---
@app.route('/api/products', methods=['GET', 'POST', 'DELETE'])
@login_required(roles=['admin', 'supervisor'])
def api_products():
    if request.method == 'GET':
        prods = Product.query.all()
        return jsonify([{
            'id': p.id, 'name': p.name, 'price': p.price, 
            'type': p.product_type, 'description': p.description, 
            'is_active': p.is_active
        } for p in prods])
    
    if request.method == 'POST':
        data = request.json
        pid = data.get('id')
        if pid:
            prod = Product.query.get(pid)
            prod.name = data['name']
            prod.price = float(data['price'])
            prod.product_type = data['type']
            prod.description = data.get('description', '')
            prod.is_active = bool(data.get('is_active', True))
        else:
            new_prod = Product(
                name=data['name'], 
                price=float(data['price']), 
                product_type=data['type'], 
                description=data.get('description', ''),
                is_active=bool(data.get('is_active', True))
            )
            db.session.add(new_prod)
        db.session.commit()
        return jsonify({'status': 'ok'})

    if request.method == 'DELETE':
        pid = request.json.get('id')
        prod = Product.query.get(pid)
        if prod:
            db.session.delete(prod)
            db.session.commit()
            return jsonify({'status': 'ok'})
        return jsonify({'error': 'No encontrado'}), 404

@app.route('/api/products_public')
def api_products_public():
    prods = Product.query.filter_by(is_active=True).all()
    return jsonify([{
        'id': p.id, 'name': p.name, 'price': p.price, 
        'type': p.product_type, 'description': p.description
    } for p in prods])

@app.route('/api/products/<int:pid>/status', methods=['POST'])
@login_required(roles=['admin'])
def toggle_product_status(pid):
    prod = Product.query.get(pid)
    if not prod: return jsonify({'error': 'Not found'}), 404
    prod.is_active = bool(request.json.get('is_active', True))
    db.session.commit()
    return jsonify({'status': 'ok'})

# --- API CUPONES ---
@app.route('/api/coupons', methods=['GET', 'POST', 'DELETE'])
@login_required(roles=['admin', 'supervisor'])
def api_coupons():
    if request.method == 'GET':
        coups = Coupon.query.all()
        return jsonify([{
            'id': c.id, 'code': c.code, 'type': c.coupon_type,
            'value': c.value, 'max_uses': c.max_uses, 
            'current_uses': c.current_uses, 
            'expiry': c.expiry.strftime("%Y-%m-%d") if c.expiry else None
        } for c in coups])
    
    if request.method == 'POST':
        data = request.json
        if Coupon.query.filter_by(code=data['code']).first():
            return jsonify({'error': 'Código ya existe'}), 400
        
        expiry = None
        if data.get('expiry'):
            expiry = datetime.strptime(data['expiry'], "%Y-%m-%d")
            
        new_coup = Coupon(
            code=data['code'],
            coupon_type=data['type'],
            value=float(data['value']),
            max_uses=int(data.get('max_uses', 1)),
            expiry=expiry
        )
        db.session.add(new_coup)
        db.session.commit()
        return jsonify({'status': 'ok'})

    if request.method == 'DELETE':
        cid = request.json.get('id')
        coup = Coupon.query.get(cid)
        if coup:
            db.session.delete(coup)
            db.session.commit()
            return jsonify({'status': 'ok'})
        return jsonify({'error': 'No encontrado'}), 404

@app.route('/api/coupons/batch_generate', methods=['POST'])
@login_required(roles=['admin', 'supervisor'])
def api_coupon_batch():
    count = request.json.get('count', 50)
    val = request.json.get('value', 10)
    codes = []
    expiry = datetime.now().replace(hour=23, minute=59, second=59)
    for _ in range(count):
        c = 'YP-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        while Coupon.query.filter_by(code=c).first():
            c = 'YP-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
        db.session.add(Coupon(code=c, coupon_type='fixed', value=val, max_uses=1, expiry=expiry))
        codes.append(c)
    db.session.commit()
    return jsonify({'status': 'ok', 'codes': codes})

@app.route('/api/coupons/batch_clear', methods=['POST'])
@login_required(roles=['admin'])
def api_coupon_clear():
    Coupon.query.filter(Coupon.code.like('YP-%')).delete(synchronize_session=False)
    db.session.commit()
    return jsonify({'status': 'ok'})

@app.route('/api/sales_report')
@login_required(roles=['admin', 'supervisor'])
def api_sales_report():
    sales = Sale.query.all()
    return jsonify([{
        'id': s.id, 'date': s.timestamp.strftime("%Y-%m-%d %H:%M"),
        'total': s.total, 'final_total': s.final_total, 'discount_code': s.discount_code,
        'items': [{'product_name': i.product_name, 'price': i.price, 'product_type': i.product_type, 'photographer': i.photographer} for i in s.items]
    } for s in sales])

@app.route('/api/validate_coupon', methods=['POST'])
def validate_coupon():
    code = request.json.get('code')
    coup = Coupon.query.filter_by(code=code).first()
    if not coup:
        return jsonify({'valid': False, 'message': 'Código no existe'})
    
    # Check expiry
    if coup.expiry and coup.expiry < datetime.now():
        return jsonify({'valid': False, 'message': 'Cupón expirado'})
    
    # Check uses
    if coup.current_uses >= coup.max_uses:
        return jsonify({'valid': False, 'message': 'Límite de usos alcanzado'})
    
    return jsonify({
        'valid': True, 
        'type': coup.coupon_type, 
        'value': coup.value
    })

# --- THEME API ---
@app.route('/api/theme/save', methods=['POST'])
@login_required(roles=['admin'])
def save_theme_api():
    data = request.json
    if 'light' in data or 'dark' in data:
        save_theme(data)
    else:
        mode = data.get('mode', 'dark')
        save_theme(data, mode=mode)
    return jsonify({'status': 'ok'})

@app.route('/api/theme/get', methods=['GET'])
def get_current_theme_api():
    mode = session.get('theme_mode', 'light')
    return jsonify(get_theme(mode=mode))

@app.route('/api/theme/get/<mode>', methods=['GET'])
def get_theme_config(mode='dark'):
    if mode not in ['light', 'dark']: mode = 'light'
    return jsonify(get_theme(mode=mode))

@app.route('/api/theme/analyze_logo', methods=['POST'])
@login_required(roles=['admin'])
def analyze_theme_logo():
    if 'logo' not in request.files: return jsonify({'error': 'No file'}), 400
    file = request.files['logo']
    if file.filename == '': return jsonify({'error': 'Empty file'}), 400
    
    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    path = os.path.join(app.static_folder, 'branding', filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    file.save(path)
    
    palettes = theme_analyzer.analyze_logo(path)
    logo_url = url_for('static', filename='branding/' + filename)
    palettes['light']['logo_url'] = logo_url
    palettes['dark']['logo_url'] = logo_url
    return jsonify({'status': 'ok', 'palettes': palettes})

# --- API VENTAS ---
@app.route('/api/checkout', methods=['POST'])
def checkout():
    data = request.json
    try:
        # data: { items: [...], total: 100, discount_code: 'XYZ', final_total: 80 }
        from models import Sale, SaleItem, Coupon
        
        new_sale = Sale(
            total=float(data['total']),
            final_total=float(data['final_total']),
            discount_code=data.get('discount_code'),
            access_code=''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        )
        db.session.add(new_sale)
        
        # Update Coupon Uses
        if data.get('discount_code'):
            coup = Coupon.query.filter_by(code=data['discount_code']).first()
            if coup:
                coup.current_uses += 1
        
        for item in data['items']:
            new_item = SaleItem(
                sale=new_sale,
                photo_id=item.get('photo_id'),
                product_name=item['product_name'],
                price=float(item['price']),
                product_type=item.get('product_type', 'digital'),
                photographer=item.get('photographer', 'Manual')
            )
            db.session.add(new_item)
            
        db.session.commit()
        return jsonify({'status': 'ok', 'sale_id': new_sale.id, 'access_code': new_sale.access_code})
    except Exception as e:
        print(f"Checkout Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales/close_day', methods=['POST'])
@login_required(roles=['admin'])
def close_day_api():
    data = request.json or {}
    notes = data.get('notes', '')
    try:
        from models import Sale, SaleItem, EODReport, FaceDescriptor
        
        # 1. Logic to get sales since last closing
        last_eod = EODReport.query.order_by(EODReport.timestamp.desc()).first()
        query = Sale.query
        if last_eod:
            query = query.filter(Sale.timestamp > last_eod.timestamp)
        
        sales = query.all()
        total_rev = sum(s.final_total for s in sales)
        
        digital_count = 0
        print_count = 0
        ph_splits = {}
        
        for s in sales:
            for item in s.items:
                if 'print' in (item.product_type or '').lower():
                    print_count += 1
                else:
                    digital_count += 1
                
                ph = item.photographer or 'Manual'
                ph_splits[ph] = ph_splits.get(ph, 0) + item.price

        # 2. Save Report
        new_report = EODReport(
            total_revenue=total_rev,
            digital_count=digital_count,
            print_count=print_count,
            photographer_splits_json=json.dumps(ph_splits),
            closing_user=session['user']['username'],
            notes=notes
        )
        db.session.add(new_report)
        
        # 3. FACE PRIVACY SHIELD: Clear descriptors
        FaceDescriptor.query.delete()
        
        db.session.commit()
        return jsonify({'status': 'ok', 'id': new_report.id})
    except Exception as e:
        print(f"EOD Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/sales/history', methods=['GET'])
@login_required(roles=['admin'])
def get_sales_history():
    history = EODReport.query.order_by(EODReport.timestamp.desc()).all()
    return jsonify([{
        'id': r.id,
        'date': r.timestamp.strftime("%Y-%m-%d %H:%M"),
        'total': r.total_revenue,
        'digital': r.digital_count,
        'print': r.print_count,
        'user': r.closing_user
    } for r in history])

@app.route('/api/sales/last_closing')
@login_required(roles=['admin'])
def last_closing_api():
    last = EODReport.query.order_by(EODReport.timestamp.desc()).first()
    return jsonify({'last_closing': last.timestamp.isoformat() if last else None})

# --- AI BACKGROUND WORKER ---

def process_photo_ai(photo_id, file_path):
    """Background task to extract faces and save descriptors."""
    with app.app_context():
        try:
            from ai_engine import engine
            from models import FaceDescriptor
            
            print(f"AI: Processing photo {photo_id}...")
            faces = engine.extract_faces(file_path)
            
            for f in faces:
                desc = FaceDescriptor(
                    photo_id=photo_id,
                    vector_json=json.dumps(f['embedding']),
                    box_json=json.dumps(f['box'])
                )
                db.session.add(desc)
            
            db.session.commit()
            print(f"AI: Found {len(faces)} faces in photo {photo_id}")
        except Exception as e:
            print(f"AI: Critical error processing photo {photo_id}: {e}")

# Helper for Photographer Attribution
def get_photographer():
    return session.get('user', {}).get('username', 'Manual')

@app.route('/api/upload/chunk', methods=['POST'])
def upload_chunk():
    if 'photo' not in request.files:
        return jsonify({"error": "No photo part"}), 400
    
    file = request.files['photo']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    date_str = time.strftime("%Y-%m-%d")
    photographer = get_photographer()
    
    # Target directory: uploads/YYYY-MM-DD/Photographer
    target_dir = os.path.join(app.config['UPLOAD_FOLDER'], date_str, photographer)
    os.makedirs(target_dir, exist_ok=True)
    
    file_path = os.path.join(target_dir, filename)
    
    # Avoid collisions
    if os.path.exists(file_path):
        base, ext = os.path.splitext(filename)
        filename = f"{base}_{int(time.time() * 1000)}{ext}"
        file_path = os.path.join(target_dir, filename)
    
    file.save(file_path)
    
    # Relative path for DB
    rel_path = os.path.join(date_str, photographer, filename).replace('\\', '/')
    
    # Save to Database
    new_photo = Photo(
        filename=filename,
        relative_path=rel_path,
        photographer=photographer
    )
    db.session.add(new_photo)
    db.session.commit()

    # Trigger AI Background Processing
    executor.submit(process_photo_ai, new_photo.id, file_path)
    
    return jsonify({
        "status": "success", 
        "id": new_photo.id,
        "path": rel_path
    })

# --- IDENTIFICATION ENDPOINT ---
import base64
from io import BytesIO
from PIL import Image

@app.route('/api/identify', methods=['POST'])
def identify_client():
    """Identifies a client by a webcam snapshot."""
    data = request.json or {}
    image_b64 = data.get('image') # Base64 from webcam
    
    if not image_b64:
        return jsonify({"error": "No image provided"}), 400

    try:
        # 1. Decode image
        header, encoded = image_b64.split(",", 1)
        image_data = base64.b64decode(encoded)
        
        # Save temp image for processing
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"temp_search_{int(time.time())}.jpg")
        with open(temp_path, "wb") as f:
            f.write(image_data)

        # 2. Extract Face Encoding
        from ai_engine import engine
        target_faces = engine.extract_faces(temp_path)
        os.remove(temp_path) # cleanup

        if not target_faces:
            return jsonify({"results": [], "message": "No se detectó ningún rostro"}), 200

        target_encoding = target_faces[0]['embedding']

        # 3. Search in DB (Linear scan for Zero-Budget Demo)
        from models import FaceDescriptor, Photo
        import json
        import numpy as np

        all_descriptors = FaceDescriptor.query.all()
        matches = []

        for d in all_descriptors:
            db_encoding = json.loads(d.vector_json)
            sim = engine.get_similarity(target_encoding, db_encoding)
            
            if sim > 0.65: # Threshold for Facenet512
                matches.append({
                    "photo_id": d.photo_id,
                    "similarity": float(sim),
                    "path": d.photo.relative_path,
                    "date": d.photo.created_at.strftime("%Y-%m-%d %H:%M")
                })

        # Sort by similarity
        matches.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Limit to top 20
        return jsonify({"results": matches[:20]})

    except Exception as e:
        print(f"Identify Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/preview/<path:filename>')
def serve_preview(filename):
    """Serves a watermarked version of the image."""
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(full_path):
        return "Not found", 404
    
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.open(full_path)
        
        # Resize for preview if too large (e.g., max 800px)
        img.thumbnail((1200, 1200))
        
        # Add Watermark
        draw = ImageDraw.Draw(img)
        # We'll use a simple cross and text for guaranteed compatibility
        w, h = img.size
        draw.line((0, 0, w, h), fill=(255, 255, 255, 128), width=3)
        draw.line((0, h, w, 0), fill=(255, 255, 255, 128), width=3)
        
        text = "YAKU-PIX PREVIEW"
        # draw text in center (approx)
        draw.text((w//2 - 100, h//2), text, fill=(255,255,255,180))
        
        img_io = BytesIO()
        img.save(img_io, 'JPEG', quality=70)
        img_io.seek(0)
        return send_from_directory(os.path.dirname(full_path), os.path.basename(full_path)) # Fallback if error, but we want the stream
    except Exception as e:
        print(f"Watermark error: {e}")
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Fixed serve_preview to return the actually processed bytes
@app.route('/p/<path:filename>')
def serve_p(filename):
    full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(full_path): return "Not found", 404
    
    try:
        from PIL import Image, ImageDraw
        img = Image.open(full_path)
        img.thumbnail((800, 800))
        draw = ImageDraw.Draw(img)
        w, h = img.size
        # Diagonal text
        draw.text((w/4, h/2), "YAKU-PIX", fill=(255,255,255,100))
        
        img_io = BytesIO()
        img.save(img_io, 'JPEG', quality=60)
        img_io.seek(0)
        from flask import make_response
        response = make_response(img_io.getvalue())
        response.headers.set('Content-Type', 'image/jpeg')
        return response
    except Exception as e:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['ARCHIVE_FOLDER'], exist_ok=True)
    
    # Get port from environment variable (for Render/Heroku) or use default
    port = int(os.environ.get('PORT', 5001))
    # Get debug mode from environment (production = False)
    debug_mode = os.environ.get('FLASK_ENV', 'development') == 'development'
    
    print(f"LocalPix V1.4 Enterprise started on port {port}")
    print(f"Debug mode: {debug_mode}")
    
    # Allow external connections in production
    app.run(host='0.0.0.0', port=port, debug=debug_mode)

