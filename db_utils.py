# db_utils.py
import oracledb
import pandas as pd
import streamlit as st
import random
from config import ORACLE_USER, ORACLE_PASSWORD, ORACLE_DSN

# It's best practice to create the pool once and reuse it.
# We can store it in Streamlit's session state to avoid recreating it on every rerun.
def init_connection_pool():
    if "db_pool" not in st.session_state:
        try:
            pool = oracledb.create_pool(
                user=ORACLE_USER,
                password=ORACLE_PASSWORD,
                dsn=ORACLE_DSN,
                min=2,
                max=5,
                increment=1
            )
            st.session_state.db_pool = pool
            print("Database connection pool created successfully.")
        except Exception as e:
            st.error(f"Error creating connection pool: {e}")
            st.stop()
    return st.session_state.db_pool
def sanitize_params(params):
    if params is None:
        return None
    # Converti ay haja fiha .item() (bhal int64 dial pandas) l-Python int
    return [int(p.item()) if hasattr(p, 'item') else p for p in params]
# Function to execute SELECT queries and return a pandas DataFrame
def execute_query(query, params=None):
    pool = init_connection_pool()
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)
                
                # Fetch column names from the cursor description
                columns = [col[0] for col in cursor.description]
                # Fetch all rows and create a DataFrame
                rows = cursor.fetchall()
                df = pd.DataFrame(rows, columns=columns)
                return df
    except Exception as e:
        st.error(f"Database query failed: {e}")
        return pd.DataFrame()

def execute_dml(dml_statement, params=None):
    """
    Executes a DML statement (INSERT, UPDATE, DELETE).
    Returns a tuple (success: bool, message: str)
    """
    params = sanitize_params(params) # FIX HNA
    pool = init_connection_pool()
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                cursor.execute(dml_statement, params or [])
                connection.commit()
        return (True, "DML statement executed successfully.")
    except oracledb.DatabaseError as e:
        error_obj, = e.args
        friendly_message = error_obj.message.split(':', 1)[-1].strip()
        return (False, friendly_message)
    except Exception as e:
        return (False, f"An unexpected error occurred: {e}")

# Function to call a stored procedure
# Returns a tuple (success: bool, message: str)
def call_procedure(proc_name, params=None):
    pool = init_connection_pool()
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                if params:
                    cursor.callproc(proc_name, params)
                else:
                    cursor.callproc(proc_name)
                connection.commit()
        return (True, f"Procedure '{proc_name}' executed successfully.")
    except oracledb.DatabaseError as e:
        # This is how we catch the custom errors from RAISE_APPLICATION_ERROR
        error_obj, = e.args
        # The error message is in the 'message' attribute
        # We strip the Oracle error code part (e.g., "ORA-20001: ")
        friendly_message = error_obj.message.split(':', 1)[-1].strip()
        return (False, friendly_message)
    except Exception as e:
        return (False, f"An unexpected error occurred: {e}")

def create_course_with_details(course_name, filiere_id, semestre_id, capacity, prof_id, prerequisite_ids=None):
    """
    Creates a course, assigns a professor, and adds prerequisites in a single transaction.
    Returns a tuple (success: bool, message: str)
    """
    pool = init_connection_pool()
    connection = None
    try:
        connection = pool.acquire()
        connection.begin() # Start a transaction
        with connection.cursor() as cursor:
            # 1. Insert the course and get its new ID
            course_id_var = cursor.var(oracledb.NUMBER)
            sql_insert_course = "INSERT INTO course (NAME, FILIERE_ID, SEMESTRE_ID, CAPACITY) VALUES (:1, :2, :3, :4) RETURNING COURSE_ID INTO :5"
            cursor.execute(sql_insert_course, [course_name, filiere_id, semestre_id, capacity, course_id_var])
            new_course_id = course_id_var.getvalue()[0]

            # 2. Insert the professor-course link
            sql_assign_prof = "INSERT INTO prof_course (PROF_ID, COURSE_ID) VALUES (:1, :2)"
            cursor.execute(sql_assign_prof, [prof_id, new_course_id])
            
            # 3. Insert prerequisites if any are provided
            if prerequisite_ids:
                sql_add_prereq = "INSERT INTO course_prerequisite (COURSE_ID, PREREQUISITE_COURSE_ID) VALUES (:1, :2)"
                # Use executemany for efficiency
                prereq_data = [(new_course_id, prereq_id) for prereq_id in prerequisite_ids]
                cursor.executemany(sql_add_prereq, prereq_data)
        
        connection.commit() # Commit the transaction
        return (True, f"Course '{course_name}' created successfully.")

    except oracledb.DatabaseError as e:
        if connection:
            connection.rollback() # Rollback on any database error
        error_obj, = e.args
        friendly_message = error_obj.message.split(':', 1)[-1].strip()
        return (False, friendly_message)
    except Exception as e:
        if connection:
            connection.rollback()
        return (False, f"An unexpected error occurred: {e}")
    finally:
        if connection:
            pool.release(connection)

def create_new_professor(full_name, department_id, password):
    """
    Creates a new professor and their user account in a single transaction.
    Returns a tuple (success: bool, message: str, new_code: str)
    """
    pool = init_connection_pool()
    connection = None
    # Generate a unique code_apoge, retry if it somehow already exists
    for _ in range(5): # Try up to 5 times
        try:
            connection = pool.acquire()
            connection.begin()
            with connection.cursor() as cursor:
                # 1. Generate code and insert into USER_ACCOUNT
                new_code = f"P{random.randint(1000, 9999)}"
                sql_user_account = "INSERT INTO USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES (:1, :2, 'PROF')"
                cursor.execute(sql_user_account, [new_code, password])

                # 2. Insert into PROF table
                sql_prof = "INSERT INTO PROF (CODE_APOGE, FULL_NAME, DEPARTEMENT_ID) VALUES (:1, :2, :3)"
                cursor.execute(sql_prof, [new_code, full_name, department_id])
            
            connection.commit()
            return (True, f"Professor '{full_name}' created successfully.", new_code)
        
        except oracledb.DatabaseError as e:
            if connection:
                connection.rollback()
            error_obj, = e.args
            # If it's a unique constraint violation on the code, the loop will retry
            if "ORA-00001" in error_obj.message:
                print(f"Generated code {new_code} already exists. Retrying...")
                continue
            friendly_message = error_obj.message.split(':', 1)[-1].strip()
            return (False, friendly_message, None)
        except Exception as e:
            if connection:
                connection.rollback()
            return (False, f"An unexpected error occurred: {e}", None)
        finally:
            if connection:
                pool.release(connection)
    
    # If we exit the loop
    return (False, "Failed to generate a unique login code after several attempts.", None)




# Function to call a stored function that returns a ref cursor
def call_function_ref_cursor(func_name, params=None):
    """
    Calls a stored function that returns a SYS_REFCURSOR and returns a pandas DataFrame.
    """
    pool = init_connection_pool()
    try:
        with pool.acquire() as connection:
            with connection.cursor() as cursor:
                # For functions that RETURN a cursor, we call it directly.
                # The list of parameters should only be the IN parameters.
                output_cursor = cursor.callfunc(func_name, oracledb.DB_TYPE_CURSOR, params or [])
                
                # Fetch data from the returned ref cursor
                columns = [col[0] for col in output_cursor.description]
                rows = output_cursor.fetchall()
                df = pd.DataFrame(rows, columns=columns)
                return df
    except oracledb.DatabaseError as e:
        # Provide more specific error info
        error_obj, = e.args
        friendly_message = error_obj.message.split(':', 1)[-1].strip()
        st.error(f"Database function '{func_name}' failed: {friendly_message}")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"An unexpected error occurred calling function '{func_name}': {e}")
        return pd.DataFrame()
