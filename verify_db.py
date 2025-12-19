import os
from app import app, db, User, Product, ConfigEntry

def verify():
    with app.app_context():
        print("Starting verification...")
        print(f"Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        # Check Users
        try:
            users = User.query.all()
            print(f"✅ Users found: {len(users)}")
            for u in users:
                print(f"  - {u.username} ({u.role})")
        except Exception as e:
            print(f"❌ Error checking users: {e}")
            
        # Check Products
        try:
            prods = Product.query.all()
            print(f"✅ Products found: {len(prods)}")
            for p in prods:
                print(f"  - {p.name}: S/. {p.price}")
        except Exception as e:
            print(f"❌ Error checking products: {e}")
            
        # Check Theme
        try:
            configs = ConfigEntry.query.filter(ConfigEntry.key.like('theme_%')).all()
            print(f"✅ Theme configs found: {len(configs)}")
        except Exception as e:
            print(f"❌ Error checking themes: {e}")

if __name__ == "__main__":
    verify()
