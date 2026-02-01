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
            course_id_var = cursor.var(oracledb.NUMBER)
            cursor.execute(
                "INSERT INTO YAHYA_ADMIN.course (NAME, FILIERE_ID, SEMESTRE_ID, CAPACITY) VALUES (:1, :2, :3, :4) RETURNING COURSE_ID INTO :5",
                [course_name, filiere_id, semestre_id, capacity, course_id_var]
            )
            new_course_id = int(course_id_var.getvalue()[0])

            cursor.execute("INSERT INTO YAHYA_ADMIN.prof_course (PROF_ID, COURSE_ID) VALUES (:1, :2)", [prof_id, new_course_id])
            
            if prerequisite_ids:
                prereq_data = [(new_course_id, int(prereq_id)) for prereq_id in prerequisite_ids]
                cursor.executemany("INSERT INTO YAHYA_ADMIN.course_prerequisite (COURSE_ID, PREREQUISITE_COURSE_ID) VALUES (:1, :2)", prereq_data)
        
        connection.commit()
        return (True, f"Course '{course_name}' created successfully.")
    except Exception as e:
        if connection: connection.rollback()
        return (False, str(e))
    finally:
        if connection: pool.release(connection)

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