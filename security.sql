-- =====================================================
-- Idempotent Security Setup Script
-- With PDB Container Switch
-- =====================================================
SET SERVEROUTPUT ON;
ALTER SESSION SET "_ORACLE_SCRIPT"=true;

-- =====================================================
-- 0️⃣ Switch to Pluggable Database (PDB)
-- =====================================================
DECLARE
  v_pdb_name VARCHAR2(100);
BEGIN
  -- In a multi-tenant environment, switch to the application's PDB.
  -- This assumes there is one writable PDB where the schema resides.
  SELECT name INTO v_pdb_name FROM v$pdbs WHERE open_mode = 'READ WRITE' AND ROWNUM = 1 AND name != 'PDB$SEED';
  IF v_pdb_name IS NOT NULL THEN
    DBMS_OUTPUT.PUT_LINE('Switching session container to PDB: ' || v_pdb_name);
    EXECUTE IMMEDIATE 'ALTER SESSION SET CONTAINER = ' || v_pdb_name;
  END IF;
EXCEPTION
  WHEN NO_DATA_FOUND THEN
    DBMS_OUTPUT.PUT_LINE('No open PDB found. Assuming non-CDB or already in the correct container.');
  WHEN OTHERS THEN
    DBMS_OUTPUT.PUT_LINE('Warning: Could not switch PDB container. ' || SQLERRM);
END;
/

-- =====================================================
-- 1️⃣ Create Application Owner (if not exists)
-- =====================================================
DECLARE
  v_user_exists NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_user_exists FROM all_users WHERE username = 'YAHYA_ADMIN';
  IF v_user_exists = 0 THEN
    EXECUTE IMMEDIATE 'CREATE USER YAHYA_ADMIN IDENTIFIED BY "yahya_admin_password"';
    EXECUTE IMMEDIATE 'GRANT CONNECT, RESOURCE, CREATE VIEW, CREATE PROCEDURE, CREATE TRIGGER TO YAHYA_ADMIN';
    EXECUTE IMMEDIATE 'ALTER USER YAHYA_ADMIN QUOTA UNLIMITED ON USERS';
  END IF;
END;
/

-- =====================================================
-- 2️⃣ Create Roles (if not exists)
-- =====================================================
DECLARE
  v_role_exists NUMBER;
BEGIN
  SELECT COUNT(*) INTO v_role_exists FROM dba_roles WHERE role = 'ROLE_STUDENT';
  IF v_role_exists = 0 THEN
    EXECUTE IMMEDIATE 'CREATE ROLE role_student';
  END IF;

  SELECT COUNT(*) INTO v_role_exists FROM dba_roles WHERE role = 'ROLE_PROF';
  IF v_role_exists = 0 THEN
    EXECUTE IMMEDIATE 'CREATE ROLE role_prof';
  END IF;

  SELECT COUNT(*) INTO v_role_exists FROM dba_roles WHERE role = 'ROLE_ADMIN';
  IF v_role_exists = 0 THEN
    EXECUTE IMMEDIATE 'CREATE ROLE role_admin';
  END IF;
END;
/

-- =====================================================
-- 3️⃣ Grant Basic Privileges
-- =====================================================
GRANT CREATE SESSION TO role_student, role_prof, role_admin;

-- =====================================================
-- 4️⃣ Create App Users (if not exists)
-- =====================================================
DECLARE
    v_user_exists NUMBER;
BEGIN
    SELECT COUNT(*) INTO v_user_exists FROM all_users WHERE username = 'PROF_USER';
    IF v_user_exists = 0 THEN
        EXECUTE IMMEDIATE 'CREATE USER prof_user IDENTIFIED BY "123"';
    END IF;
    EXECUTE IMMEDIATE 'GRANT role_prof TO prof_user';

    SELECT COUNT(*) INTO v_user_exists FROM all_users WHERE username = 'STUDENT_USER';
    IF v_user_exists = 0 THEN
        EXECUTE IMMEDIATE 'CREATE USER student_user IDENTIFIED BY "123"';
    END IF;
    EXECUTE IMMEDIATE 'GRANT role_student TO student_user';
END;
/

-- =====================================================
-- 5️⃣ Grant Object Privileges
-- =====================================================
DECLARE
    v_owner VARCHAR2(30) := 'YAHYA_ADMIN';
BEGIN
    -- Grant full CRUD on all tables to admin
    FOR t IN (SELECT table_name FROM all_tables WHERE owner = v_owner) LOOP
        EXECUTE IMMEDIATE 'GRANT SELECT, INSERT, UPDATE, DELETE ON '||v_owner||'.'||t.table_name||' TO role_admin';
    END LOOP;

    -- Grant SELECT on all views to admin and specific roles
    FOR v IN (SELECT view_name FROM all_views WHERE owner = v_owner) LOOP
        EXECUTE IMMEDIATE 'GRANT SELECT ON '||v_owner||'.'||v.view_name||' TO role_admin';
        
        IF v.view_name LIKE 'V_PROF_%' THEN
            EXECUTE IMMEDIATE 'GRANT SELECT ON '||v_owner||'.'||v.view_name||' TO role_prof';
        ELSIF v.view_name LIKE 'V_STUDENT_%' THEN
            EXECUTE IMMEDIATE 'GRANT SELECT ON '||v_owner||'.'||v.view_name||' TO role_student';
        END IF;
    END LOOP;

    -- Grant specific privileges to roles
    EXECUTE IMMEDIATE 'GRANT INSERT ON '||v_owner||'.inscription_request TO role_student';
    EXECUTE IMMEDIATE 'GRANT SELECT, INSERT, UPDATE ON '||v_owner||'.attendance TO role_prof';
    EXECUTE IMMEDIATE 'GRANT SELECT, INSERT, UPDATE ON '||v_owner||'.course_result TO role_prof';
    EXECUTE IMMEDIATE 'GRANT SELECT ON '||v_owner||'.prof_course TO role_prof';
    EXECUTE IMMEDIATE 'GRANT SELECT ON '||v_owner||'.seance TO role_prof';
END;
/

-- =====================================================
-- 6️⃣ Create Procedures (owned by YAHYA_ADMIN)
-- =====================================================
CREATE OR REPLACE PROCEDURE YAHYA_ADMIN.sp_add_student (
    p_login      IN VARCHAR2,
    p_pass       IN VARCHAR2,
    p_name       IN VARCHAR2,
    p_filiere    IN NUMBER,
    p_semestre   IN NUMBER
) AS 
BEGIN
    INSERT INTO YAHYA_ADMIN.user_account (login_code, password_hash, role) 
    VALUES (UPPER(p_login), p_pass, 'STUDENT');
    
    INSERT INTO YAHYA_ADMIN.student (code_apoge, full_name, filiere_id, current_semestre_id) 
    VALUES (UPPER(p_login), p_name, p_filiere, p_semestre);
END;
/

CREATE OR REPLACE PROCEDURE YAHYA_ADMIN.sp_prof_submit_grade (
    p_student_id IN NUMBER,
    p_course_id  IN NUMBER,
    p_grade      IN NUMBER
) AS
    v_sem_id NUMBER;
    v_year_id NUMBER;
BEGIN
    SELECT semestre_id INTO v_sem_id FROM YAHYA_ADMIN.course WHERE course_id = p_course_id;
    SELECT year_id INTO v_year_id FROM YAHYA_ADMIN.semestre WHERE semestre_id = v_sem_id;

    MERGE INTO YAHYA_ADMIN.course_result cr
    USING DUAL ON (cr.student_id = p_student_id AND cr.course_id = p_course_id)
    WHEN MATCHED THEN
        UPDATE SET grade = p_grade, status = CASE WHEN p_grade >= 10 THEN 'VALID' ELSE 'FAILED' END
    WHEN NOT MATCHED THEN
        INSERT (student_id, course_id, semestre_id, year_id, grade, status)
        VALUES (p_student_id, p_course_id, v_sem_id, v_year_id, p_grade, CASE WHEN p_grade >= 10 THEN 'VALID' ELSE 'FAILED' END);
END;
/

-- =====================================================
-- 7️⃣ Grant Execute Privileges and Create Synonyms
-- =====================================================
GRANT EXECUTE ON YAHYA_ADMIN.sp_add_student TO role_admin;
GRANT EXECUTE ON YAHYA_ADMIN.admin_unblock_student TO role_admin;
GRANT EXECUTE ON YAHYA_ADMIN.sp_prof_submit_grade TO role_prof;
GRANT EXECUTE ON YAHYA_ADMIN.fn_student_current_courses TO role_student;
GRANT EXECUTE ON YAHYA_ADMIN.fn_student_courses TO role_student;
GRANT EXECUTE ON YAHYA_ADMIN.fn_student_seances TO role_student;
GRANT EXECUTE ON YAHYA_ADMIN.fn_student_blocked_courses TO role_student;
GRANT EXECUTE ON YAHYA_ADMIN.fn_missing_prerequisites TO role_student;
GRANT EXECUTE ON YAHYA_ADMIN.fn_prof_courses TO role_prof;
GRANT EXECUTE ON YAHYA_ADMIN.fn_prof_seances TO role_prof;
GRANT EXECUTE ON YAHYA_ADMIN.fn_students_in_seance TO role_prof;
GRANT EXECUTE ON YAHYA_ADMIN.fn_students_present_in_seance TO role_prof;
GRANT EXECUTE ON YAHYA_ADMIN.fn_course_prerequisites TO role_student, role_prof, role_admin;
GRANT EXECUTE ON YAHYA_ADMIN.fn_blocked_students TO role_admin;

CREATE OR REPLACE PUBLIC SYNONYM sp_add_student FOR YAHYA_ADMIN.sp_add_student;
CREATE OR REPLACE PUBLIC SYNONYM sp_prof_submit_grade FOR YAHYA_ADMIN.sp_prof_submit_grade;
CREATE OR REPLACE PUBLIC SYNONYM admin_unblock_student FOR YAHYA_ADMIN.admin_unblock_student;

COMMIT;