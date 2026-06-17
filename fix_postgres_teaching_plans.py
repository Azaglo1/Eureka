import os
import sys

try:
    import psycopg2
except ImportError:
    print("psycopg2 is not installed. Please install it first.")
    sys.exit(1)

def load_env_file():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(base_dir, ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

load_env_file()

POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
POSTGRES_DB = os.environ.get("POSTGRES_DB", "school")

if not POSTGRES_DB:
    print("POSTGRES_DB is not configured. Set POSTGRES_DB in your environment or .env file.")
    sys.exit(1)

dsn = f"dbname={POSTGRES_DB} user={POSTGRES_USER} host={POSTGRES_HOST} port={POSTGRES_PORT}"
if POSTGRES_PASSWORD:
    dsn += f" password={POSTGRES_PASSWORD}"

try:
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    
    # Create teaching_plans table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teaching_plans (
            id SERIAL PRIMARY KEY,
            school_id INTEGER NOT NULL,
            teacher_id INTEGER,
            title TEXT,
            subject TEXT,
            grade TEXT,
            section TEXT,
            description TEXT,
            objectives TEXT,
            content TEXT,
            resources TEXT,
            activities TEXT,
            assessment_methods TEXT,
            duration INTEGER,
            start_date TEXT,
            end_date TEXT,
            plan_date TEXT,
            status TEXT DEFAULT 'draft',
            is_active INTEGER DEFAULT 1,
            admin_approved TEXT DEFAULT 'pending',
            admin_notes TEXT,
            week_number INTEGER,
            week_ending TEXT,
            period_duration TEXT,
            day_of_week TEXT,
            strand TEXT,
            sub_strand TEXT,
            content_standard TEXT,
            indicator TEXT,
            performance_indicator TEXT,
            core_competencies TEXT,
            keywords TEXT,
            tlm TEXT,
            lesson_references TEXT,
            starter_activities TEXT,
            main_activities TEXT,
            formative_assessment TEXT,
            plenary_reflection TEXT,
            teacher_reflection TEXT,
            attachment_path TEXT,
            attachment_name TEXT,
             created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
             updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
             FOREIGN KEY(school_id) REFERENCES schools(id)
        )
    """)
    print("Created teaching_plans table")
    
    cur.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'week_number') THEN
                ALTER TABLE teaching_plans ADD COLUMN week_number INTEGER;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'week_ending') THEN
                ALTER TABLE teaching_plans ADD COLUMN week_ending TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'period_duration') THEN
                ALTER TABLE teaching_plans ADD COLUMN period_duration TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'day_of_week') THEN
                ALTER TABLE teaching_plans ADD COLUMN day_of_week TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'strand') THEN
                ALTER TABLE teaching_plans ADD COLUMN strand TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'sub_strand') THEN
                ALTER TABLE teaching_plans ADD COLUMN sub_strand TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'content_standard') THEN
                ALTER TABLE teaching_plans ADD COLUMN content_standard TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'indicator') THEN
                ALTER TABLE teaching_plans ADD COLUMN indicator TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'performance_indicator') THEN
                ALTER TABLE teaching_plans ADD COLUMN performance_indicator TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'core_competencies') THEN
                ALTER TABLE teaching_plans ADD COLUMN core_competencies TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'keywords') THEN
                ALTER TABLE teaching_plans ADD COLUMN keywords TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'tlm') THEN
                ALTER TABLE teaching_plans ADD COLUMN tlm TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'lesson_references') THEN
                ALTER TABLE teaching_plans ADD COLUMN lesson_references TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'starter_activities') THEN
                ALTER TABLE teaching_plans ADD COLUMN starter_activities TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'main_activities') THEN
                ALTER TABLE teaching_plans ADD COLUMN main_activities TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'formative_assessment') THEN
                ALTER TABLE teaching_plans ADD COLUMN formative_assessment TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'plenary_reflection') THEN
                ALTER TABLE teaching_plans ADD COLUMN plenary_reflection TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'teacher_reflection') THEN
                ALTER TABLE teaching_plans ADD COLUMN teacher_reflection TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'attachment_path') THEN
                ALTER TABLE teaching_plans ADD COLUMN attachment_path TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'teaching_plans' AND column_name = 'attachment_name') THEN
                ALTER TABLE teaching_plans ADD COLUMN attachment_name TEXT;
            END IF;
        END $$;
    """)
    print("Migrated teaching_plans columns")
    
    cur.close()
    conn.close()
    print("Done!")
except Exception as exc:
    print("Failed to connect to database:", exc)
    sys.exit(1)