# seed_data.py
import oracledb
import random
import datetime
from faker import Faker
from db_utils import init_connection_pool

# --- CONFIGURATION ---
NUM_STUDENTS = 100
NUM_PROFS = 20
NUM_DEPARTMENTS = 5
NUM_FILIERES_PER_DEPT = 2
NUM_COURSES_PER_FILIERE_PER_SEM = 4
CURRENT_DATE = datetime.date(2025, 2, 1)

# Initialize Faker
fake = Faker()

def clear_existing_data(cursor):
    """Clears data from tables in the correct order to avoid FK constraints."""
    print("🗑️ Clearing existing data...")
    tables_to_clear = [
        'ATTENDANCE', 'UNBLOCK_REQUEST', 'COURSE_RESULT', 'PROF_COURSE', 'COURSE_PREREQUISITE',
        'INSCRIPTION_REQUEST', 'SEANCE', 'STUDENT_SECTION', 'COURSE', 'SECTION',
        'ADMIN', 'PROF', 'STUDENT', 'USER_ACCOUNT', 'SEMESTRE', 'FILIERE',
        'DEPARTEMENT', 'ACADEMIC_YEAR'
    ]
    for table in tables_to_clear:
        try:
            print(f"  - Clearing {table}...")
            cursor.execute(f"DELETE FROM {table}")
        except oracledb.DatabaseError as e:
            print(f"    Warning: Could not clear {table}. Error: {e}")
    print("✅ Data cleared.")

def get_ids_from_table(cursor, table_name, id_column):
    cursor.execute(f"SELECT {id_column} FROM {table_name}")
    return [row[0] for row in cursor.fetchall()]

def seed_data():
    """Main function to seed all data with a 2-year history."""
    pool = init_connection_pool()
    with pool.acquire() as connection:
        cursor = connection.cursor()
        
        clear_existing_data(cursor)
        print("\n🌱 Starting 2-year historical data seeding process...")

        # --- Base Data ---
        print("\n--- Seeding Academic Years & Departments ---")
        years = {'2023-2024': (datetime.date(2023, 9, 1), datetime.date(2024, 7, 31)), '2024-2025': (datetime.date(2024, 9, 1), datetime.date(2025, 7, 31))}
        for label, (start, end) in years.items():
            cursor.execute("INSERT INTO ACADEMIC_YEAR (LABEL, START_DATE, END_DATE) VALUES (:1, :2, :3)", [label, start, end])
        for _ in range(NUM_DEPARTMENTS):
            cursor.execute("INSERT INTO DEPARTEMENT (NAME) VALUES (:1)", [fake.bs().title()])
        connection.commit()
        year_ids = get_ids_from_table(cursor, 'ACADEMIC_YEAR', 'YEAR_ID')
        dept_ids = get_ids_from_table(cursor, 'DEPARTEMENT', 'DEPARTEMENT_ID')
        print("✅ Seeded Academic Years and Departments.")

        print("\n--- Seeding Filieres & Semestres ---")
        filiere_id_var = cursor.var(oracledb.NUMBER)
        semestre_id_var = cursor.var(oracledb.NUMBER) # Declare once
        # Collect filiere_id and semestre_id combinations for section creation
        semestre_combinations = []
        for dept_id in dept_ids:
            for _ in range(NUM_FILIERES_PER_DEPT):
                cursor.execute("INSERT INTO FILIERE (NAME, DEPARTEMENT_ID) VALUES (:1, :2) RETURNING FILIERE_ID INTO :3", [fake.job().title()[:50], dept_id, filiere_id_var])
                filiere_id = filiere_id_var.getvalue()[0]
                for year_id in year_ids:
                    for i in range(2):
                        sem_code = f"S{i+1}"
                        cursor.execute("INSERT INTO SEMESTRE (CODE, FILIERE_ID, YEAR_ID) VALUES (:1, :2, :3) RETURNING SEMESTRE_ID INTO :4", [sem_code, filiere_id, year_id, semestre_id_var])
                        semestre_combinations.append({'filiere_id': filiere_id, 'semestre_id': semestre_id_var.getvalue()[0]}) 
        connection.commit()
        filiere_ids = get_ids_from_table(cursor, 'FILIERE', 'FILIERE_ID')
        print("✅ Seeded Filieres & Semestres.")

        # Sections
        print("\n--- Seeding Sections ---")
        section_id_var = cursor.var(oracledb.NUMBER)
        all_section_ids = []
        for combo in semestre_combinations:
            for i in range(random.randint(1, 2)): # 1 or 2 sections per filiere/semestre combo
                section_name = f"SEC-{combo['filiere_id']}-{combo['semestre_id']}-{i+1}"
                cursor.execute("INSERT INTO SECTION (NAME, FILIERE_ID, SEMESTRE_ID) VALUES (:1, :2, :3) RETURNING SECTION_ID INTO :4", [section_name, combo['filiere_id'], combo['semestre_id'], section_id_var])
                all_section_ids.append(section_id_var.getvalue()[0])
        connection.commit()
        print(f"✅ Seeded {len(all_section_ids)} Sections.")
        
        # Users
        print("\n--- Seeding Users (Admin, Profs, Students) ---")
        cursor.execute("INSERT INTO USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES ('ADMIN', 'admin', 'ADMIN')")
        cursor.execute("INSERT INTO ADMIN (USERNAME, FULL_NAME) VALUES ('ADMIN', 'Administrator')")
        for i in range(NUM_PROFS):
            cursor.execute("INSERT INTO USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES (:1, '123', 'PROF')", [f"P{2000+i}"])
            cursor.execute("INSERT INTO PROF (CODE_APOGE, FULL_NAME, DEPARTEMENT_ID) VALUES (:1, :2, :3)", [f"P{2000+i}", fake.name(), random.choice(dept_ids)])
        for i in range(NUM_STUDENTS):
            filiere_id = random.choice(filiere_ids)
            cursor.execute("SELECT SEMESTRE_ID FROM SEMESTRE WHERE FILIERE_ID = :1 AND YEAR_ID = :2 AND CODE = 'S1'", [filiere_id, year_ids[0]])
            start_sem_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES (:1, '123', 'STUDENT')", [f"E{100000+i}"])
            cursor.execute("INSERT INTO STUDENT (CODE_APOGE, FULL_NAME, FILIERE_ID, CURRENT_SEMESTRE_ID) VALUES (:1, :2, :3, :4)", [f"E{100000+i}", fake.name(), filiere_id, start_sem_id])
        connection.commit()
        prof_ids = get_ids_from_table(cursor, 'PROF', 'PROF_ID')
        student_ids = get_ids_from_table(cursor, 'STUDENT', 'STUDENT_ID')
        print(f"✅ Seeded 1 Admin, {len(prof_ids)} Profs, {len(student_ids)} Students.")

        print("\n--- Seeding 2-Year Historical Data (this may take a moment) ---")
        for filiere_id in filiere_ids:
            cursor.execute("SELECT SEMESTRE_ID FROM SEMESTRE WHERE FILIERE_ID = :1", [filiere_id])
            for (semestre_id,) in cursor.fetchall():
                for i in range(NUM_COURSES_PER_FILIERE_PER_SEM):
                    cursor.execute("INSERT INTO COURSE (NAME, FILIERE_ID, SEMESTRE_ID) VALUES (:1, :2, :3)", [f"{fake.catch_phrase().title()} {'I'*i}", filiere_id, semestre_id])
        connection.commit()
        course_ids = get_ids_from_table(cursor, 'COURSE', 'COURSE_ID')

        # Assign profs to courses, respecting the 3-course limit
        prof_assignments = {prof_id: 0 for prof_id in prof_ids}
        unassigned_courses = list(course_ids)
        random.shuffle(unassigned_courses)

        for course_id in unassigned_courses:
            available_profs = [prof_id for prof_id, count in prof_assignments.items() if count < 3]
            if not available_profs:
                print("  - Warning: All professors have reached their maximum course load. Some courses will remain unassigned.")
                break
            
            prof_to_assign = random.choice(available_profs)
            try:
                cursor.execute("INSERT INTO PROF_COURSE (PROF_ID, COURSE_ID) VALUES (:1, :2)", [prof_to_assign, course_id])
                prof_assignments[prof_to_assign] += 1
            except oracledb.DatabaseError:
                pass
        
        print(f"✅ Assigned {sum(prof_assignments.values())} courses to professors.")
        
        # Explicitly create a prerequisite scenario
        try:
            cursor.execute("SELECT c.COURSE_ID, s.CODE FROM COURSE c JOIN SEMESTRE s ON c.SEMESTRE_ID = s.SEMESTRE_ID WHERE s.FILIERE_ID = :1", [filiere_ids[0]])
            filiere_courses = cursor.fetchall()
            s1_course = next(c[0] for c in filiere_courses if c[1] == 'S1')
            s2_course = next(c[0] for c in filiere_courses if c[1] == 'S2')
            cursor.execute("INSERT INTO COURSE_PREREQUISITE (COURSE_ID, PREREQUISITE_COURSE_ID) VALUES (:1, :2)", [s2_course, s1_course])
            print("✅ Created explicit S1->S2 prerequisite.")
        except (StopIteration, oracledb.DatabaseError):
            print("  - Warning: Could not create explicit prerequisite.")

        students_to_block = random.sample(student_ids, k=min(5, len(student_ids)))
        seance_id_var = cursor.var(oracledb.NUMBER)
        for student_id in student_ids:
            cursor.execute("SELECT c.COURSE_ID, c.SEMESTRE_ID, c.FILIERE_ID FROM COURSE c JOIN STUDENT s ON c.SEMESTRE_ID = s.CURRENT_SEMESTRE_ID WHERE s.STUDENT_ID = :1", [student_id])
            for course_id, semestre_id, filiere_of_course in cursor.fetchall():
                cursor.execute("INSERT INTO INSCRIPTION_REQUEST (STUDENT_ID, COURSE_ID, STATUS) VALUES (:1, :2, 'ACCEPTED')", [student_id, course_id])
                seance_ids = []
                # Get a relevant section ID for this course's filiere/semestre
                cursor.execute("""
                    SELECT sec.SECTION_ID
                    FROM SECTION sec
                    WHERE sec.FILIERE_ID = :1 AND sec.SEMESTRE_ID = :2
                """, [filiere_of_course, semestre_id])
                section_id_for_seance_row = cursor.fetchone()
                if section_id_for_seance_row:
                    section_id_for_seance = section_id_for_seance_row[0]
                else:
                    print(f"  - Warning: No section found for filiere_id {filiere_of_course}, semestre_id {semestre_id}. Skipping seances for course {course_id}.")
                    continue

                for i in range(10):
                    seance_date = datetime.date(2023, 10, 1) + datetime.timedelta(days=i*7)
                    cursor.execute("INSERT INTO SEANCE (COURSE_ID, SECTION_ID, SEANCE_DATE, TYPE) VALUES (:1, :2, :3, 'COURS') RETURNING SEANCE_ID INTO :4", [course_id, section_id_for_seance, seance_date, seance_id_var])
                    seance_ids.append(seance_id_var.getvalue()[0])
                
                is_blocked = False
                if student_id in students_to_block and 's1_course' in locals() and course_id == s1_course:
                    is_blocked = True
                    for i, seance_id in enumerate(seance_ids):
                        status = 'ABSENT' if i < 3 else 'PRESENT'
                        cursor.execute("INSERT INTO ATTENDANCE (SEANCE_ID, STUDENT_ID, STATUS) VALUES (:1, :2, :3)", [seance_id, student_id, status])
                    students_to_block.remove(student_id)
                else:
                    for seance_id in seance_ids:
                        cursor.execute("INSERT INTO ATTENDANCE (SEANCE_ID, STUDENT_ID, STATUS) VALUES (:1, :2, 'PRESENT')", [seance_id, student_id])

                status = 'FAILED' if is_blocked else ('VALID' if random.random() < 0.8 else 'FAILED')
                if 's1_course' in locals() and course_id == s1_course and not is_blocked:
                    status = 'VALID'

                cursor.execute("INSERT INTO COURSE_RESULT (STUDENT_ID, COURSE_ID, SEMESTRE_ID, YEAR_ID, GRADE, STATUS) VALUES (:1, :2, :3, :4, :5, :6)",
                               [student_id, course_id, semestre_id, year_ids[0], random.uniform(8, 18), status])
        
        full_course_id = random.choice(course_ids)
        cursor.execute("UPDATE COURSE SET CAPACITY = :1 WHERE COURSE_ID = :2", [len(student_ids), full_course_id])

        cursor.execute("SELECT ADMIN_ID FROM ADMIN WHERE ROWNUM = 1")
        admin_id_for_unblock = cursor.fetchone()[0]
        cursor.execute("SELECT STUDENT_ID, COURSE_ID FROM COURSE_RESULT WHERE STATUS = 'FAILED' AND ROWNUM <= 3")
        for student_id, course_id in cursor.fetchall():
            cursor.execute("INSERT INTO UNBLOCK_REQUEST (STUDENT_ID, COURSE_ID, ADMIN_ID, JUSTIFICATION) VALUES (:1, :2, :3, 'Medical Certificate provided.')",
                           [student_id, course_id, admin_id_for_unblock])
        
        connection.commit()
        print("✅ Historical data seeded successfully.")
        print("\n\n🎉 Seeding complete! Database is populated with a 2-year history.")

if __name__ == "__main__":
    seed_data()
