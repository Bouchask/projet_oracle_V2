-- =================================================================
-- security.sql - V7 - FINAL with Statement Terminators
-- =================================================================
-- This script provides a complete and audited set of permissions for
-- the per-role security model AND creates public synonyms.
-- This version includes semicolons after every SQL statement for
-- compatibility with SQL*Plus.
-- =================================================================

SET ECHO ON;
WHENEVER SQLERROR EXIT SQL.SQLCODE;

SET SERVEROUTPUT ON;
ALTER SESSION SET "_ORACLE_SCRIPT"=true;

-- This script must be run as a DBA user (e.g., SYSTEM)

-- 1. Clean up old objects
PROMPT Dropping old users and roles (ignoring 'does not exist' errors)...
BEGIN EXECUTE IMMEDIATE 'DROP USER app_admin CASCADE'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1918 THEN NULL; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP USER app_prof CASCADE'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1918 THEN NULL; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP USER app_student CASCADE'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1918 THEN NULL; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP USER app_auth CASCADE'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1918 THEN NULL; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP ROLE ROLE_ADMIN'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1940 THEN NULL; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP ROLE ROLE_PROF'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1940 THEN NULL; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP ROLE ROLE_STUDENT'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1940 THEN NULL; END IF; END;
/
BEGIN EXECUTE IMMEDIATE 'DROP ROLE ROLE_AUTH'; EXCEPTION WHEN OTHERS THEN IF SQLCODE != -1940 THEN NULL; END IF; END;
/

-- 2. Create Application Users
PROMPT Creating application users...
CREATE USER app_admin IDENTIFIED BY "admin_password";
CREATE USER app_prof IDENTIFIED BY "prof_password";
CREATE USER app_student IDENTIFIED BY "student_password";
CREATE USER app_auth IDENTIFIED BY "auth_password";

GRANT CREATE SESSION TO app_admin, app_prof, app_student, app_auth;

ALTER USER app_admin QUOTA UNLIMITED ON USERS;
ALTER USER app_prof QUOTA UNLIMITED ON USERS;
ALTER USER app_student QUOTA UNLIMITED ON USERS;
ALTER USER app_auth QUOTA UNLIMITED ON USERS;

-- 3. Create Roles
PROMPT Creating roles...
CREATE ROLE ROLE_ADMIN;
CREATE ROLE ROLE_PROF;
CREATE ROLE ROLE_STUDENT;
CREATE ROLE ROLE_AUTH;

-- =====================================================
-- 4. Grant Privileges to Roles (Fully Audited)
-- =====================================================
PROMPT Granting privileges to roles...

-- AUTH Role:
GRANT SELECT ON YAHYA_ADMIN.user_account TO ROLE_AUTH;

-- STUDENT Role:
GRANT SELECT ON YAHYA_ADMIN.student TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.filiere TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.semestre TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.academic_year TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.course TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.prof TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.prof_course TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.seance TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.section TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.student_section TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.inscription_request TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.course_result TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.departement TO ROLE_STUDENT;
GRANT UPDATE (password_hash) ON YAHYA_ADMIN.user_account TO ROLE_STUDENT;
GRANT INSERT ON YAHYA_ADMIN.inscription_request TO ROLE_STUDENT;
GRANT INSERT ON YAHYA_ADMIN.student_section TO ROLE_STUDENT;
GRANT EXECUTE ON YAHYA_ADMIN.fn_student_seances TO ROLE_STUDENT;
GRANT EXECUTE ON YAHYA_ADMIN.fn_student_courses TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.v_detail_course TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.v_student_current_courses TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.v_student_absence_stats TO ROLE_STUDENT;
GRANT SELECT ON YAHYA_ADMIN.v_student_blocked_courses TO ROLE_STUDENT;

-- PROF Role:
GRANT SELECT ON YAHYA_ADMIN.course TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.semestre TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.academic_year TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.student TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.inscription_request TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.attendance TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.seance TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.prof TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.prof_course TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.filiere TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.section TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.v_prof_courses TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.v_prof_seances TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.v_prof_students_by_course TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.v_prof_blocked_students TO ROLE_PROF;
GRANT SELECT ON YAHYA_ADMIN.v_prof_absence_stats TO ROLE_PROF;
GRANT UPDATE ON YAHYA_ADMIN.inscription_request TO ROLE_PROF;
GRANT UPDATE ON YAHYA_ADMIN.attendance TO ROLE_PROF;
GRANT EXECUTE ON YAHYA_ADMIN.fn_students_in_seance TO ROLE_PROF;
GRANT EXECUTE ON YAHYA_ADMIN.sp_prof_submit_grade TO ROLE_PROF;

-- ADMIN Role:
PROMPT -> Granting ADMIN privileges...
DECLARE
  v_owner VARCHAR2(30) := 'YAHYA_ADMIN';
BEGIN
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = v_owner) LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT, INSERT, UPDATE, DELETE ON '||v_owner||'.'||t.table_name||' TO ROLE_ADMIN';
  END LOOP;
  FOR v IN (SELECT view_name FROM all_views WHERE owner = v_owner) LOOP
    EXECUTE IMMEDIATE 'GRANT SELECT ON '||v_owner||'.'||v.view_name||' TO ROLE_ADMIN';
  END LOOP;
END;
/

-- =====================================================
-- 5. Assign Roles to Application Users
-- =====================================================
PROMPT Assigning roles to users...
GRANT ROLE_ADMIN TO app_admin;
GRANT ROLE_PROF TO app_prof;
GRANT ROLE_STUDENT TO app_student;
GRANT ROLE_AUTH TO app_auth;


-- =====================================================
-- 6. Create Public Synonyms
-- =====================================================
PROMPT Creating public synonyms...
DECLARE
  v_owner VARCHAR2(30) := 'YAHYA_ADMIN';
BEGIN
  FOR t IN (SELECT table_name FROM all_tables WHERE owner = v_owner) LOOP
    EXECUTE IMMEDIATE 'CREATE OR REPLACE PUBLIC SYNONYM '||t.table_name||' FOR '||v_owner||'.'||t.table_name;
  END LOOP;
  FOR v IN (SELECT view_name FROM all_views WHERE owner = v_owner) LOOP
    EXECUTE IMMEDIATE 'CREATE OR REPLACE PUBLIC SYNONYM '||v.view_name||' FOR '||v_owner||'.'||v.view_name;
  END LOOP;
  FOR p IN (SELECT object_name FROM all_objects WHERE owner = v_owner AND object_type IN ('PROCEDURE', 'FUNCTION')) LOOP
    EXECUTE IMMEDIATE 'CREATE OR REPLACE PUBLIC SYNONYM '||p.object_name||' FOR '||v_owner||'.'||p.object_name;
  END LOOP;
END;
/

PROMPT Security script finished.

COMMIT;
/