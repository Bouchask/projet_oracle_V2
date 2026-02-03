# db_utils.py
import oracledb
import pandas as pd
import streamlit as st
import random
from config import ORACLE_DSN, APP_USERS

# --- New Per-Role Connection Management ---

def get_credentials_for_role(role: str) -> tuple[str, str]:
    """Gets the database username and password for a given application role."""
    role_creds = APP_USERS.get(role)
    if not role_creds:
        raise ValueError(f"No database credentials found for role: {role}")
    return role_creds["user"], role_creds["pass"]

def get_db_pool():
    """
    Dynamically gets or creates a connection pool based on the user's role.
    The role is determined from the session_state.
    """
    # Default to the 'AUTH' role if no user is logged in yet.
    user_role = st.session_state.get('user_info', {}).get('ROLE', 'AUTH')

    # Initialize the dictionary of pools if it doesn't exist.
    if 'db_pools' not in st.session_state:
        st.session_state.db_pools = {}

    # If a pool for the current role doesn't exist, create it.
    if user_role not in st.session_state.db_pools:
        try:
            user, password = get_credentials_for_role(user_role)
            print(f"Creating new connection pool for role: {user_role} (DB User: {user})")
            
            pool = oracledb.create_pool(
                user=user,
                password=password,
                dsn=ORACLE_DSN,
                min=2,
                max=5,
                increment=1
            )
            st.session_state.db_pools[user_role] = pool
        except Exception as e:
            st.error(f"Fatal: Could not create database connection pool for role '{user_role}'. Error: {e}")
            st.stop()
            
    return st.session_state.db_pools[user_role]

# --- Modified Core Database Functions ---

def execute_query(query, params=None):
    """Executes a SELECT query using the appropriate role-based connection pool."""
    pool = get_db_pool() # Dynamically get the pool
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, params or [])
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                df = pd.DataFrame(rows, columns=columns)
                return df
    except oracledb.DatabaseError as e:
        st.error(f"Database query failed: {e}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
        return pd.DataFrame()

def sanitize_params(params):
    if params is None: return None
    return [int(p.item()) if hasattr(p, 'item') else p for p in params]

def execute_dml(dml_statement, params=None):
    """Executes a DML statement using the appropriate role-based connection pool."""
    params = sanitize_params(params)
    pool = get_db_pool() # Dynamically get the pool
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                cursor.execute(dml_statement, params or [])
                connection.commit()
        return (True, "DML statement executed successfully.")
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        return (False, f"Database error: {error_obj.message}")
    except Exception as e:
        return (False, f"An unexpected error occurred: {e}")

def call_procedure(proc_name, params=None):
    """Calls a stored procedure using the appropriate role-based connection pool."""
    pool = get_db_pool() # Dynamically get the pool
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                cursor.callproc(proc_name, params or [])
                connection.commit()
        return (True, f"Procedure '{proc_name}' executed successfully.")
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        friendly_message = error_obj.message.split(':', 1)[-1].strip()
        return (False, friendly_message)
    except Exception as e:
        return (False, f"An unexpected error occurred: {e}")
        
def call_function_ref_cursor(func_name, params=None):
    """Calls a function returning a ref cursor using the appropriate role-based pool."""
    pool = get_db_pool() # Dynamically get the pool
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                output_cursor = cursor.callfunc(func_name, oracledb.DB_TYPE_CURSOR, params or [])
                columns = [col[0] for col in output_cursor.description]
                rows = output_cursor.fetchall()
                df = pd.DataFrame(rows, columns=columns)
                return df
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        st.error(f"Database function '{func_name}' failed: {error_obj.message.split(':', 1)[-1].strip()}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"An unexpected error occurred calling function '{func_name}': {e}")
        return pd.DataFrame()


# --- Admin-specific complex operations ---
# These functions should only be callable when the user has the ADMIN role,
# otherwise the underlying DB connection will lack permissions.

def create_course_with_details(course_name, filiere_id, semestre_id, capacity, prof_id, prerequisite_ids=None):
    pool = get_db_pool()
    connection = None
    try:
        connection = pool.acquire()
        connection.begin()
        with connection.cursor() as cursor:
            # --- New Validation Logic: Check if professor belongs to the correct department ---
            cursor.execute("SELECT d.DEPARTEMENT_ID FROM YAHYA_ADMIN.FILIERE f JOIN YAHYA_ADMIN.DEPARTEMENT d ON f.DEPARTEMENT_ID = d.DEPARTEMENT_ID WHERE f.FILIERE_ID = :1", [filiere_id])
            filiere_dept_id_row = cursor.fetchone()
            if not filiere_dept_id_row:
                raise ValueError("Invalid Filiere ID provided.")
            filiere_dept_id = filiere_dept_id_row[0]

            cursor.execute("SELECT DEPARTEMENT_ID FROM YAHYA_ADMIN.PROF WHERE PROF_ID = :1", [prof_id])
            prof_dept_id_row = cursor.fetchone()
            if not prof_dept_id_row:
                raise ValueError("Invalid Professor ID provided.")
            prof_dept_id = prof_dept_id_row[0]

            if filiere_dept_id != prof_dept_id:
                raise ValueError("The assigned professor must belong to the same department as the course's filière.")
            # --- End New Validation Logic ---

            # 1. Insert the course and get its new ID
            course_id_var = cursor.var(oracledb.NUMBER)
            sql_insert_course = "INSERT INTO YAHYA_ADMIN.course (NAME, FILIERE_ID, SEMESTRE_ID, CAPACITY) VALUES (:1, :2, :3, :4) RETURNING COURSE_ID INTO :5"
            cursor.execute(sql_insert_course, [course_name, filiere_id, semestre_id, capacity, course_id_var])
            new_course_id = int(course_id_var.getvalue()[0])

            # 2. Insert the professor-course link
            sql_assign_prof = "INSERT INTO YAHYA_ADMIN.prof_course (PROF_ID, COURSE_ID) VALUES (:1, :2)"
            cursor.execute(sql_assign_prof, [prof_id, new_course_id])
            
            # 3. Insert prerequisites if any are provided
            if prerequisite_ids:
                sql_add_prereq = "INSERT INTO YAHYA_ADMIN.course_prerequisite (COURSE_ID, PREREQUISITE_COURSE_ID) VALUES (:1, :2)"
                prereq_data = [(new_course_id, int(prereq_id)) for prereq_id in prerequisite_ids]
                cursor.executemany(sql_add_prereq, prereq_data)
        
        connection.commit()
        return (True, f"Course '{course_name}' created successfully.")
    except Exception as e:
        if connection:
            connection.rollback()
        return (False, str(e))
    finally:
        if connection:
            pool.release(connection)

def create_new_professor(full_name, department_id, password):
    pool = get_db_pool()
    connection = None
    try:
        connection = pool.acquire()
        connection.begin()
        with connection.cursor() as cursor:
            new_code = f"P{random.randint(1000, 9999)}"
            cursor.execute(
                "INSERT INTO YAHYA_ADMIN.USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES (:1, :2, 'PROF')",
                [new_code, password]
            )
            cursor.execute(
                "INSERT INTO YAHYA_ADMIN.PROF (CODE_APOGE, FULL_NAME, DEPARTEMENT_ID) VALUES (:1, :2, :3)",
                [new_code, full_name, department_id]
            )
        connection.commit()
        return (True, f"Professor '{full_name}' created.", new_code)
    except Exception as e:
        if connection: connection.rollback()
        return (False, str(e), None)
    finally:
        if connection: pool.release(connection)

def delete_course_with_details(course_id):
    # This function now requires high privileges and should only be run by an admin.
    # The underlying 'app_admin' user should have DELETE rights.
    pool = get_db_pool()
    connection = None
    try:
        connection = pool.acquire()
        connection.begin()
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM YAHYA_ADMIN.ATTENDANCE WHERE SEANCE_ID IN (SELECT SEANCE_ID FROM YAHYA_ADMIN.SEANCE WHERE COURSE_ID = :1)", [course_id])
            cursor.execute("DELETE FROM YAHYA_ADMIN.SEANCE WHERE COURSE_ID = :1", [course_id])
            cursor.execute("DELETE FROM YAHYA_ADMIN.COURSE_RESULT WHERE COURSE_ID = :1", [course_id])
            cursor.execute("DELETE FROM YAHYA_ADMIN.INSCRIPTION_REQUEST WHERE COURSE_ID = :1", [course_id])
            cursor.execute("DELETE FROM YAHYA_ADMIN.UNBLOCK_REQUEST WHERE COURSE_ID = :1", [course_id])
            cursor.execute("DELETE FROM YAHYA_ADMIN.COURSE_PREREQUISITE WHERE COURSE_ID = :1", [course_id])
            cursor.execute("DELETE FROM YAHYA_ADMIN.COURSE_PREREQUISITE WHERE PREREQUISITE_COURSE_ID = :1", [course_id])
            cursor.execute("DELETE FROM YAHYA_ADMIN.PROF_COURSE WHERE COURSE_ID = :1", [course_id])
            cursor.execute("DELETE FROM YAHYA_ADMIN.COURSE WHERE COURSE_ID = :1", [course_id])
        connection.commit()
        return (True, f"Course ID {course_id} and related data deleted.")
    except Exception as e:
        if connection: connection.rollback()
        return (False, str(e))
    finally:
        if connection: pool.release(connection)

def create_seances_for_all_sections(course_id, filiere_id, semestre_id, filiere_name, semestre_code, seance_date, start_time, end_time, room, seance_type):
    """
    Creates a seance for every section associated with a filiere/semestre.
    If no sections exist, it creates two default ones.
    This is a transactional operation.
    """
    pool = get_db_pool()
    connection = None
    try:
        connection = pool.acquire()
        connection.begin()
        
        with connection.cursor() as cursor:
            # 1. Check for existing sections
            cursor.execute("SELECT SECTION_ID FROM SECTION WHERE FILIERE_ID = :1 AND SEMESTRE_ID = :2", [filiere_id, semestre_id])
            sections = cursor.fetchall()
            section_ids = [row[0] for row in sections]

            # 2. If no sections exist, create two default ones
            if not section_ids:
                st.info("No sections found, creating two default sections (G1, G2)...")
                new_sections_to_create = 2
                for i in range(1, new_sections_to_create + 1):
                    section_name = f"{filiere_name[:4].upper()}-{semestre_code}-G{i}"
                    # Use a variable to hold the returned ID
                    new_id_var = cursor.var(oracledb.NUMBER)
                    cursor.execute(
                        "INSERT INTO SECTION (NAME, FILIERE_ID, SEMESTRE_ID) VALUES (:1, :2, :3) RETURNING SECTION_ID INTO :4",
                        [section_name, filiere_id, semestre_id, new_id_var]
                    )
                    # Get the value from the variable and add to our list
                    section_ids.append(new_id_var.getvalue()[0])

            # 3. Insert a seance for the FIRST available section to avoid conflicts.
            #    The original logic of looping through all sections was guaranteed to fail
            #    the room/time overlap trigger if more than one section existed.
            seance_dml = "INSERT INTO SEANCE (COURSE_ID, SECTION_ID, SEANCE_DATE, START_TIME, END_TIME, ROOM, TYPE) VALUES (:1, :2, :3, :4, :5, :6, :7)"
            seances_created = 0
            if section_ids:
                # Use only the first section to prevent room/time conflicts
                first_section_id = section_ids[0]
                params = [course_id, first_section_id, seance_date, start_time, end_time, room, seance_type]
                cursor.execute(seance_dml, params)
                seances_created = 1
            else:
                # This case should ideally not be reached due to section creation logic above, but as a safeguard:
                return (False, "Could not find or create a section to assign the seance to.")

        connection.commit()
        return (True, f"Successfully created {seances_created} séance. It has been assigned to the first available section.")
    except oracledb.DatabaseError as e:
        if connection:
            connection.rollback()
        error_obj, = e.args
        return (False, f"Database error: {error_obj.message}")
    except Exception as e:
        if connection:
            connection.rollback()
        return (False, f"An unexpected error occurred: {str(e)}")
    finally:
        if connection:
            pool.release(connection)