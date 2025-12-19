from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False) # admin, supervisor, photographer
    
    # Professional Information
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    department = db.Column(db.String(100), nullable=True)
    
    # Account Status
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Photo(db.Model):
    __tablename__ = 'photos'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    relative_path = db.Column(db.String(500), nullable=False) # e.g., 2023-12-18/Juan/img.jpg
    photographer = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_archived = db.Column(db.Boolean, default=False)
    archive_path = db.Column(db.String(500))
    
    # Relation to descriptors
    descriptors = db.relationship('FaceDescriptor', backref='photo', cascade='all, delete-orphan')

class FaceDescriptor(db.Model):
    __tablename__ = 'face_descriptors'
    id = db.Column(db.Integer, primary_key=True)
    photo_id = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=False)
    vector_json = db.Column(db.Text, nullable=False) # JSON representation of the embedding array
    
    # Store search index metadata? For now, we'll search via SQL or a local service
    box_json = db.Column(db.Text) # Bounding box in photo

class Sale(db.Model):
    __tablename__ = 'sales'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total = db.Column(db.Float, nullable=False)
    final_total = db.Column(db.Float, nullable=False)
    discount_code = db.Column(db.String(50))
    status = db.Column(db.String(20), default='completed') # completed, pending
    access_code = db.Column(db.String(20), unique=True) # Unique code for the client to see their album
    
    items = db.relationship('SaleItem', backref='sale', cascade='all, delete-orphan')

class SaleItem(db.Model):
    __tablename__ = 'sale_items'
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    photo_id = db.Column(db.Integer, db.ForeignKey('photos.id'), nullable=True) # Link to photo
    product_name = db.Column(db.String(100))
    price = db.Column(db.Float)
    product_type = db.Column(db.String(50)) # digital, print
    photographer = db.Column(db.String(80))

class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    product_type = db.Column(db.String(50)) # digital, print
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)

class Coupon(db.Model):
    __tablename__ = 'coupons'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    coupon_type = db.Column(db.String(20)) # percent, fixed
    value = db.Column(db.Float, nullable=False)
    max_uses = db.Column(db.Integer, default=1)
    current_uses = db.Column(db.Integer, default=0)
    expiry = db.Column(db.DateTime) # If null, never expires

class EODReport(db.Model):
    __tablename__ = 'eod_reports'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    total_revenue = db.Column(db.Float)
    digital_count = db.Column(db.Integer)
    print_count = db.Column(db.Integer)
    photographer_splits_json = db.Column(db.Text) # JSON of ph_splits
    closing_user = db.Column(db.String(80))
    notes = db.Column(db.Text)

class ConfigEntry(db.Model):
    __tablename__ = 'configs'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text)

def get_theme(mode='light'):
    """Retrieves theme configuration from the database."""
    prefix = f"theme_{mode}_"
    entries = ConfigEntry.query.filter(ConfigEntry.key.like(f"{prefix}%")).all()
    theme = {e.key[len(prefix):]: e.value for e in entries}
    
    # Fallback/Default values if empty
    if not theme:
        if mode == 'dark':
            return {
                'primary': '#3b82f6', 'primary_hover': '#2563eb', 'secondary': '#22c55e',
                'bg': '#0f172a', 'card_bg': '#1e293b', 'text_primary': '#ffffff',
                'text_secondary': '#94a3b8', 'surface': '#334155', 'accent': '#f59e0b', 'error': '#ef4444'
            }
        else:
            return {
                'primary': '#3b82f6', 'primary_hover': '#2563eb', 'secondary': '#22c55e',
                'bg': '#f8fafc', 'card_bg': '#ffffff', 'text_primary': '#0f172a',
                'text_secondary': '#475569', 'surface': '#e2e8f0', 'accent': '#f59e0b', 'error': '#dc2626'
            }
    return theme

def save_theme(data, mode=None):
    """Saves theme configuration to the database."""
    if mode in ['light', 'dark']:
        prefix = f"theme_{mode}_"
        for k, v in data.items():
            if v is not None and k != 'mode':
                entry = ConfigEntry.query.get(prefix + k)
                if not entry:
                    entry = ConfigEntry(key=prefix + k, value=str(v))
                    db.session.add(entry)
                else:
                    entry.value = str(v)
    elif 'light' in data and 'dark' in data:
        save_theme(data['light'], mode='light')
        save_theme(data['dark'], mode='dark')
    db.session.commit()

def init_db(app):
    with app.app_context():
        db.create_all()
        # Seed admin if needed
        if not User.query.filter_by(username='admin').first():
            from werkzeug.security import generate_password_hash
            hashed = generate_password_hash('admin', method='pbkdf2:sha256')
            admin = User(username='admin', password=hashed, role='admin')
            db.session.add(admin)
            db.session.commit()
            print("Default admin created (Yaku-Pix)")
