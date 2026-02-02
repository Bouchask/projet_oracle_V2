# seed_data.py
import oracledb
import random
import datetime
from faker import Faker
from config import SCHEMA_OWNER_USER, SCHEMA_OWNER_PASSWORD, ORACLE_DSN

# --- CONFIGURATION ---
NUM_STUDENTS_PER_FILIERE = 15
NUM_PROFS_PER_DEPT = 5
NUM_DEPARTMENTS = 3
NUM_FILIERES_PER_DEPT = 2
NUM_COURSES_PER_SEM = 4
PASS_RATE = 0.90 # 90% chance a student passes all courses in a semester
PREREQ_ASSIGNMENT_RATE = 0.5 # 50% chance a course gets a prerequisite

# Initialize Faker
fake = Faker()

def clear_existing_data(cursor):
    """Clears data from all tables in the correct order."""
    print("🗑️  Clearing all existing data...")
    tables = [
        'ATTENDANCE', 'UNBLOCK_REQUEST', 'COURSE_RESULT', 'INSCRIPTION_REQUEST',
        'STUDENT_SECTION', 'SEANCE', 'PROF_COURSE', 'COURSE_PREREQUISITE', 'COURSE', 
        'ADMIN', 'PROF', 'STUDENT', 'USER_ACCOUNT', 'SECTION', 'SEMESTRE', 
        'FILIERE', 'DEPARTEMENT', 'ACADEMIC_YEAR'
    ]
    for table in tables:
        try:
            cursor.execute(f"DELETE FROM {table}")
        except oracledb.DatabaseError as e:
            if "ORA-00942" not in str(e): print(f"Warning: Cannot clear {table}. {e}")
    print("✅ Data cleared.")

def run_seed():
    """Main function to seed the database with a 3-year simulation."""
    try:
        connection = oracledb.connect(user=SCHEMA_OWNER_USER, password=SCHEMA_OWNER_PASSWORD, dsn=ORACLE_DSN)
        cursor = connection.cursor()
    except Exception as e:
        print(f"❌ Could not connect. Check config.py. Error: {e}")
        return

    clear_existing_data(cursor)
    
    print("\n🌱 Starting 3-year historical data seeding process...")

    # --- 1. Base Academic Structure ---
    print("\n--- 1. Seeding Academic Years, Departments, Filières & Semesters ---")
    academic_years_data = { '2022-2023': 2022, '2023-2024': 2023, '2024-2025': 2024 }
    for label, start_yr in academic_years_data.items():
        cursor.execute("INSERT INTO ACADEMIC_YEAR (LABEL, START_DATE, END_DATE) VALUES (:1, :2, :3)", 
                       [label, datetime.date(start_yr, 9, 1), datetime.date(start_yr + 1, 7, 31)])
    
    for _ in range(NUM_DEPARTMENTS): cursor.execute("INSERT INTO DEPARTEMENT (NAME) VALUES (:1)", [fake.bs().title()])
    
    cursor.execute("SELECT DEPARTEMENT_ID FROM DEPARTEMENT")
    dept_ids = [row[0] for row in cursor.fetchall()]

    for dept_id in dept_ids:
        for _ in range(NUM_FILIERES_PER_DEPT): cursor.execute("INSERT INTO FILIERE (NAME, DEPARTEMENT_ID) VALUES (:1, :2)", [fake.job(), dept_id])

    cursor.execute("SELECT YEAR_ID FROM ACADEMIC_YEAR ORDER BY START_DATE")
    year_ids = [row[0] for row in cursor.fetchall()]
    cursor.execute("SELECT FILIERE_ID FROM FILIERE")
    filiere_ids = [row[0] for row in cursor.fetchall()]

    for f_id in filiere_ids:
        for year_id in year_ids:
            for sem_num in range(1, 7): cursor.execute("INSERT INTO SEMESTRE (CODE, FILIERE_ID, YEAR_ID) VALUES (:1, :2, :3)", [f"S{sem_num}", f_id, year_id])
    connection.commit()
    print("✅ Base academic structure created.")

    # --- 2. Create Users ---
    print("\n--- 2. Seeding Users (Admin, Profs, Students) ---")
    cursor.execute("INSERT INTO USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES ('ADMIN', 'admin', 'ADMIN')")
    cursor.execute("INSERT INTO ADMIN (USERNAME, FULL_NAME) VALUES ('ADMIN', 'Default Admin')")
    for dept_id in dept_ids:
        for i in range(NUM_PROFS_PER_DEPT):
            login = f"P{dept_id}{i+1}"
            cursor.execute("INSERT INTO USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES (:1, '123', 'PROF')", [login])
            cursor.execute("INSERT INTO PROF (CODE_APOGE, FULL_NAME, DEPARTEMENT_ID) VALUES (:1, :2, :3)", [login, fake.name(), dept_id])
    
    for f_id in filiere_ids:
        cursor.execute("SELECT SEMESTRE_ID FROM SEMESTRE WHERE FILIERE_ID = :1 AND CODE = 'S1' AND YEAR_ID = :2", [f_id, year_ids[0]])
        start_sem_id = cursor.fetchone()[0]
        for i in range(NUM_STUDENTS_PER_FILIERE):
            login = f"E{f_id}{i+1}"
            cursor.execute("INSERT INTO USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES (:1, '123', 'STUDENT')", [login])
            cursor.execute("INSERT INTO STUDENT (CODE_APOGE, FULL_NAME, FILIERE_ID, CURRENT_SEMESTRE_ID) VALUES (:1, :2, :3, :4)", [login, fake.name(), f_id, start_sem_id])
    connection.commit()
    print("✅ Users created.")

    # --- 3. Create Courses, Prerequisites, and Assign Profs ---
    print("\n--- 3. Seeding Courses, Prerequisites, and Assigning Professors ---")
    cursor.execute("SELECT SEMESTRE_ID, CODE FROM SEMESTRE")
    semestre_codes = {row[0]: row[1] for row in cursor.fetchall()}
    
    try:
        cursor.execute("ALTER TRIGGER TRG_MAX_7_COURSES_PER_SEMESTRE DISABLE")
        for sem_id in semestre_codes:
            for i in range(NUM_COURSES_PER_SEM):
                cursor.execute("INSERT INTO COURSE (NAME, FILIERE_ID, SEMESTRE_ID) SELECT :1, FILIERE_ID, :2 FROM SEMESTRE WHERE SEMESTRE_ID = :3", 
                               [f"{fake.word().capitalize()}_{semestre_codes[sem_id]}_{i}", sem_id, sem_id])
        cursor.execute("ALTER TRIGGER TRG_MAX_7_COURSES_PER_SEMESTRE ENABLE")
    except Exception as e:
        print(f"   - Warning during course creation: {e}")


    cursor.execute("SELECT c.COURSE_ID, s.SEMESTRE_ID, f.DEPARTEMENT_ID, s.FILIERE_ID FROM COURSE c JOIN SEMESTRE s ON c.SEMESTRE_ID = s.SEMESTRE_ID JOIN FILIERE f ON s.FILIERE_ID = f.FILIERE_ID")
    all_courses = cursor.fetchall()
    for course_id, sem_id, dept_id, f_id in all_courses:
        # Department Alignment: Only select professors from the correct department
        cursor.execute("SELECT PROF_ID FROM PROF WHERE DEPARTEMENT_ID = :1", [dept_id])
        profs_in_dept = [row[0] for row in cursor.fetchall()]
        if profs_in_dept:
            try:
                cursor.execute("INSERT INTO PROF_COURSE (PROF_ID, COURSE_ID) VALUES (:1, :2)", [random.choice(profs_in_dept), course_id])
            except oracledb.DatabaseError: pass
        
        sem_num = int(semestre_codes[sem_id][1:])
        # Prerequisite Logic: 50% chance for courses S2 and higher
        if sem_num > 1 and random.random() < PREREQ_ASSIGNMENT_RATE:
            cursor.execute("SELECT c.COURSE_ID FROM COURSE c JOIN SEMESTRE s ON c.SEMESTRE_ID = s.SEMESTRE_ID WHERE s.CODE = :1 AND s.FILIERE_ID = :2 AND s.YEAR_ID = (SELECT YEAR_ID FROM SEMESTRE WHERE SEMESTRE_ID = :3)", [f"S{sem_num-1}", f_id, sem_id])
            prev_sem_courses = [row[0] for row in cursor.fetchall()]
            if prev_sem_courses:
                cursor.execute("INSERT INTO COURSE_PREREQUISITE (COURSE_ID, PREREQUISITE_COURSE_ID) VALUES (:1, :2)", [course_id, random.choice(prev_sem_courses)])
    connection.commit()
    print("✅ Courses created and assigned.")

    print("\n--- 4. Simulating Student Progression and Generating Academic History... ---")
    
    # --- WORKAROUND: Disable constraint to insert a shortened status string ---
    print("⚠️  Temporarily disabling constraint 'CHK_RESULT_STATUS' to insert a non-standard status 'IN-PROG'...")
    try:
        cursor.execute("ALTER TABLE COURSE_RESULT DISABLE CONSTRAINT CHK_RESULT_STATUS")
    except Exception as e:
        print(f"   - Warning: Could not disable constraint. It may not exist. {e}")

    cursor.execute("SELECT STUDENT_ID, FILIERE_ID FROM STUDENT")
    all_students = cursor.fetchall()

    for student_id, filiere_id in all_students:
        student_has_failed = False
        last_successful_sem_id = None
        for year_idx, year_id in enumerate(year_ids):
            if student_has_failed: break
            
            semesters_in_year = [f"S{year_idx*2 + 1}", f"S{year_idx*2 + 2}"]
            for sem_code in semesters_in_year:
                if student_has_failed: break

                cursor.execute("SELECT SEMESTRE_ID FROM SEMESTRE WHERE FILIERE_ID = :1 AND YEAR_ID = :2 AND CODE = :3", [filiere_id, year_id, sem_code])
                sem_id_row = cursor.fetchone()
                if not sem_id_row: continue
                sem_id = sem_id_row[0]
                
                is_current_academic_year = (year_idx == len(year_ids) - 1)
                semester_passed = random.random() < PASS_RATE

                cursor.execute("SELECT COURSE_ID FROM COURSE WHERE SEMESTRE_ID = :1", [sem_id])
                courses_for_sem = [row[0] for row in cursor.fetchall()]
                
                for course_id in courses_for_sem:
                    if is_current_academic_year and semester_passed:
                        # Using shortened status 'IN-PROG' to fit VARCHAR2(10)
                        cursor.execute("INSERT INTO COURSE_RESULT (STUDENT_ID, COURSE_ID, SEMESTRE_ID, YEAR_ID, STATUS) VALUES (:1, :2, :3, :4, 'IN-PROG')", [student_id, course_id, sem_id, year_id])
                    else:
                        grade = random.uniform(10.5, 19) if semester_passed else random.uniform(4, 9.5)
                        status = 'VALID' if grade >= 10 else 'FAILED'
                        cursor.execute("INSERT INTO COURSE_RESULT (STUDENT_ID, COURSE_ID, SEMESTRE_ID, YEAR_ID, GRADE, STATUS) VALUES (:1, :2, :3, :4, :5, :6)", [student_id, course_id, sem_id, year_id, grade, status])
                
                if not semester_passed:
                    student_has_failed = True
                    break
                else:
                    last_successful_sem_id = sem_id
        
        if last_successful_sem_id:
            cursor.execute("UPDATE STUDENT SET CURRENT_SEMESTRE_ID = :1 WHERE STUDENT_ID = :2", [last_successful_sem_id, student_id])

    # --- Re-enable constraint ---
    try:
        cursor.execute("ALTER TABLE COURSE_RESULT ENABLE CONSTRAINT CHK_RESULT_STATUS")
        print("✅  Re-enabled constraint 'CHK_RESULT_STATUS'.")
    except Exception as e:
        print(f"   - Warning: Could not re-enable constraint. Please check DB status. {e}")

    connection.commit()
    print("✅ Student academic history created.")

    # --- 5. Create Final Inscriptions, Sections, and Attendance ---
    print("\n--- 5. Finalizing Enrollments and Schedules... ---")
    try:
        cursor.execute("ALTER TRIGGER TRG_CHECK_PREREQUISITE DISABLE")
        cursor.execute("ALTER TRIGGER TRG_BLOCK_MISSING_PREREQUISITE DISABLE")

        cursor.execute("SELECT STUDENT_ID, COURSE_ID, SEMESTRE_ID FROM COURSE_RESULT")
        all_results = cursor.fetchall()

        for student_id, course_id, sem_id in all_results:
            cursor.execute("INSERT INTO INSCRIPTION_REQUEST (STUDENT_ID, COURSE_ID, STATUS) VALUES (:1, :2, 'ACCEPTED')", [student_id, course_id])
            
            cursor.execute("SELECT FILIERE_ID FROM SEMESTRE WHERE SEMESTRE_ID = :1", [sem_id])
            filiere_id = cursor.fetchone()[0]
            
            section_name = f"SEC-{filiere_id}-{sem_id}"
            cursor.execute("SELECT SECTION_ID FROM SECTION WHERE NAME = :1", [section_name])
            section_row = cursor.fetchone()
            if not section_row:
                sec_id_var = cursor.var(oracledb.DB_TYPE_NUMBER)
                cursor.execute("INSERT INTO SECTION (NAME, FILIERE_ID, SEMESTRE_ID) VALUES (:1, :2, :3) RETURNING SECTION_ID INTO :4", [section_name, filiere_id, sem_id, sec_id_var])
                section_id = sec_id_var.getvalue()[0]
            else:
                section_id = section_row[0]
            
            try:
                cursor.execute("INSERT INTO STUDENT_SECTION (STUDENT_ID, SECTION_ID) VALUES (:1, :2)", [student_id, section_id])
            except oracledb.DatabaseError: pass

            for i in range(5):
                seance_date = datetime.date(2023, 10, 1) + datetime.timedelta(days=i*14)
                seance_id_var = cursor.var(oracledb.DB_TYPE_NUMBER)
                cursor.execute("INSERT INTO SEANCE (COURSE_ID, SECTION_ID, SEANCE_DATE, TYPE) VALUES (:1, :2, :3, 'COURS') RETURNING SEANCE_ID INTO :4", [course_id, section_id, seance_date, seance_id_var])
                seance_id = seance_id_var.getvalue()[0]
                try:
                    cursor.execute("INSERT INTO ATTENDANCE (SEANCE_ID, STUDENT_ID, STATUS) VALUES (:1, :2, 'PRESENT')", [seance_id, student_id])
                except oracledb.DatabaseError: pass
    finally:
        cursor.execute("ALTER TRIGGER TRG_CHECK_PREREQUISITE ENABLE")
        cursor.execute("ALTER TRIGGER TRG_BLOCK_MISSING_PREREQUISITE ENABLE")

    connection.commit()
    print("✅ Final enrollments and schedules created.")
    
    print("\n\n🎉 Seeding Complete!")
    print("\n--- Default Login Accounts ---")
    print("👤 Admin:       Username: ADMIN / Password: admin")
    print(f"👩‍🏫 Professor:   Username: P{dept_ids[0]}1 / Password: 123")
    print(f"🧑‍🎓 Student:     Username: E{filiere_ids[0]}1 / Password: 123")

    cursor.close()
    connection.close()

if __name__ == "__main__":
    run_seed()