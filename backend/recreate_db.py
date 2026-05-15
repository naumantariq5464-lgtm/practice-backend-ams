from app.database import engine, Base
from app.models import User, Attendance, Feedback
from sqlalchemy import text
import traceback

def create_tables():
    try:
        conn = engine.connect()
        print("Connected to database successfully!")
        
        # Check if tables exist
        rs = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        tables = [row[0] for row in rs]
        print(f"Current tables in public schema: {tables}")
        
        print("Attempting to drop all existing tables using cascade...")
        # Drop all carefully
        for t in ['feedback', 'attendance', 'users']:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {t} CASCADE"))
            except Exception as e:
                print(f"Error dropping {t}: {e}")
        
        try:
            conn.execute(text("DROP TYPE IF EXISTS userrole CASCADE"))
            conn.execute(text("DROP TYPE IF EXISTS attendancestatus CASCADE"))
        except Exception:
            pass
            
        conn.commit()
        conn.close()
        
        print("Running Base.metadata.create_all...")
        Base.metadata.create_all(bind=engine)
        print("Tables created successfully!")
        
        # Verify
        conn = engine.connect()
        rs = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'"))
        tables = [row[0] for row in rs]
        print(f"New tables in public schema: {tables}")
        conn.close()
    except Exception as e:
        print("ERROR:", str(e))
        traceback.print_exc()

if __name__ == "__main__":
    create_tables()

