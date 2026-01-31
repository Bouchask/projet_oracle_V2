import streamlit as st
import pandas as pd
import random
import datetime
from db_utils import (
    execute_query, execute_dml, create_course_with_details, create_new_professor
)

# --- Helper Functions ---
def generate_login_code(full_name):
    """Generates a unique login like YBOUCHAK777"""
    parts = full_name.upper().split()
    if len(parts) >= 2:
        code = parts[0][0] + parts[-1] + str(random.randint(100, 999))
    else:
        code = full_name[:3].upper() + str(random.randint(100, 999))
    return code

# --- Tab Implementations ---

def display_student_management():
    st.subheader("👥 Student Management")
    
    # --- Form: Add New Student ---
    with st.expander("➕ Add New Student", expanded=False):
        with st.form("add_student_form"):
            full_name = st.text_input("Full Name")
            password = st.text_input("Password", type="password", value="123")
            
            filieres_df = execute_query("SELECT FILIERE_ID, NAME FROM FILIERE ORDER BY NAME")
            selected_filiere = st.selectbox("Filiere", filieres_df['NAME'] if not filieres_df.empty else [])
            
            if not filieres_df.empty:
                f_id = filieres_df[filieres_df['NAME'] == selected_filiere]['FILIERE_ID'].values[0]
                sem_query = """
                    SELECT s.SEMESTRE_ID, s.CODE || ' (' || ay.LABEL || ')' as DISP 
                    FROM SEMESTRE s JOIN ACADEMIC_YEAR ay ON s.YEAR_ID = ay.YEAR_ID
                    WHERE s.FILIERE_ID = :1 AND s.YEAR_ID = (SELECT MAX(YEAR_ID) FROM ACADEMIC_YEAR)
                """
                semestres_df = execute_query(sem_query, [int(f_id)])
                selected_sem = st.selectbox("Semestre", semestres_df['DISP'] if not semestres_df.empty else ["No active semesters found"])
            
            if st.form_submit_button("Create Student"):
                if not full_name or semestres_df.empty:
                    st.error("Please fill all fields.")
                else:
                    login_code = generate_login_code(full_name)
                    s_id = semestres_df[semestres_df['DISP'] == selected_sem]['SEMESTRE_ID'].values[0]
                    success, msg = execute_dml("INSERT INTO USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES (:1, :2, 'STUDENT')", [login_code, password])
                    if success:
                        execute_dml("INSERT INTO STUDENT (CODE_APOGE, FULL_NAME, FILIERE_ID, CURRENT_SEMESTRE_ID) VALUES (:1, :2, :3, :4)", 
                                    [login_code, full_name, int(f_id), int(s_id)])
                        st.success(f"Student Created! Login Code: {login_code}")
                        st.rerun()
                    else:
                        st.error(msg)

    st.divider()

    # --- Student List & Search ---
    search = st.text_input("🔍 Search Student by Name or Filiere", key="search_student")
    students = execute_query("SELECT * FROM V_DETAIL_STUDENT")
    if search and not students.empty:
        students = students[students.apply(lambda row: row.astype(str).str.contains(search, case=False).any(), axis=1)]
    st.dataframe(students, use_container_width=True, hide_index=True)

    # --- NEW SECTION: View Detailed Student Enrollment ---
    if not students.empty:
        st.markdown("---")
        st.subheader("🔎 Detailed Enrollment & History")
        
        # Dropdown bach t-khtar talib mo3ayyan
        student_list = students['FULL_NAME'].tolist()
        selected_name = st.selectbox("Select a student to view academic details:", ["-- Choose Student --"] + student_list)
        
        if selected_name != "-- Choose Student --":
            s_id = students[students['FULL_NAME'] == selected_name]['STUDENT_ID'].values[0]
            
            # Fetch Courses & Grades
            enrollment_df = execute_query("""
                SELECT COURSE_NAME, SEMESTRE, NVL(COURSE_STATUS, 'IN_PROGRESS') as STATUS 
                FROM V_STUDENT_CURRENT_COURSES 
                WHERE STUDENT_ID = :1
            """, [int(s_id)])
            
            # Fetch Absence Stats
            absences_df = execute_query("""
                SELECT COURSE_NAME, ABSENCES 
                FROM V_STUDENT_ABSENCE_STATS 
                WHERE STUDENT_ID = :1
            """, [int(s_id)])

            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Current Courses & Results**")
                if not enrollment_df.empty:
                    st.dataframe(enrollment_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No course history found.")

            with col2:
                st.write("**Absence Statistics**")
                if not absences_df.empty:
                    st.dataframe(absences_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No absence records found.")
            
            # Warning ila kan t-talib bloqué
            blocked = execute_query("SELECT COURSE_NAME FROM V_STUDENT_BLOCKED_COURSES WHERE STUDENT_ID = :1", [int(s_id)])
            if not blocked.empty:
                st.warning(f"⚠️ Student is currently **FAILED/BLOCKED** in: {', '.join(blocked['COURSE_NAME'].tolist())}")

def display_course_management():
    st.subheader("📖 Course Management")
    
    # 1. Form: Create New Course
    with st.expander("➕ Create New Course", expanded=False):
        filieres_df = execute_query("SELECT FILIERE_ID, NAME FROM FILIERE ORDER BY NAME")
        if not filieres_df.empty:
            selected_filiere = st.selectbox("Select Filiere", filieres_df['NAME'], key="add_c_filiere")
            f_id = filieres_df[filieres_df['NAME'] == selected_filiere]['FILIERE_ID'].values[0].item()
            
            col1, col2 = st.columns(2)
            c_name = col1.text_input("Course Name")
            capacity = col1.number_input("Capacity", min_value=1, value=30)
            
            # Filter semesters by Latest Year
            sem_query = "SELECT SEMESTRE_ID, CODE FROM SEMESTRE WHERE FILIERE_ID = :1 AND YEAR_ID = (SELECT MAX(YEAR_ID) FROM ACADEMIC_YEAR)"
            sems = execute_query(sem_query, [int(f_id)])
            selected_sem_code = col2.selectbox("Semestre", sems['CODE'] if not sems.empty else [])
            
            # Professors from the SAME department
            prof_query = "SELECT PROF_ID, FULL_NAME FROM PROF WHERE DEPARTEMENT_ID = (SELECT DEPARTEMENT_ID FROM FILIERE WHERE FILIERE_ID = :1)"
            profs = execute_query(prof_query, [int(f_id)])
            selected_prof = col2.selectbox("Assign Professor", profs['FULL_NAME'] if not profs.empty else [])

            # Prerequisites: Only from previous semesters
            selected_prereqs = []
            if not sems.empty and selected_sem_code:
                current_sem_id = sems[sems['CODE'] == selected_sem_code]['SEMESTRE_ID'].values[0]
                prereqs_df = execute_query("SELECT COURSE_ID, NAME FROM COURSE WHERE FILIERE_ID = :1 AND SEMESTRE_ID < :2", [int(f_id), int(current_sem_id)])
                selected_prereqs = st.multiselect("Prerequisites (Optional)", prereqs_df['NAME'] if not prereqs_df.empty else [])

            if st.button("Add Course"):
                if not c_name or profs.empty or sems.empty:
                    st.error("Please fill all required fields.")
                else:
                    p_id = profs[profs['FULL_NAME'] == selected_prof]['PROF_ID'].values[0]
                    pr_ids = prereqs_df[prereqs_df['NAME'].isin(selected_prereqs)]['COURSE_ID'].tolist() if not prereqs_df.empty else []
                    success, msg = create_course_with_details(c_name, f_id, current_sem_id, capacity, p_id, pr_ids)
                    if success: 
                        st.success(msg)
                        st.rerun()
                    else: 
                        st.error(msg)

    st.divider()

    # 2. Global Course List
    courses_df = execute_query("SELECT * FROM V_DETAIL_COURSE")
    if not courses_df.empty:
        st.dataframe(courses_df, use_container_width=True, hide_index=True)

        st.markdown("---")
        
        # 3. Section: View Full Course Details
        st.subheader("🔎 View Full Course Details")
        
        course_names = courses_df['COURSE_NAME'].tolist()
        selected_c_name = st.selectbox("Select a course to explore its enrollment and prerequisites:", ["-- Choose a Course --"] + course_names)
        
        if selected_c_name != "-- Choose a Course --":
            c_info = courses_df[courses_df['COURSE_NAME'] == selected_c_name].iloc[0]
            cid = c_info['COURSE_ID']
            
            # Fetch Prerequisites
            prereqs = execute_query("""
                SELECT cp.NAME FROM COURSE_PREREQUISITE pr 
                JOIN COURSE cp ON pr.PREREQUISITE_COURSE_ID = cp.COURSE_ID 
                WHERE pr.COURSE_ID = :1
            """, [int(cid)])
            
            # Fetch Enrolled Students
            enrolled_students = execute_query("""
                SELECT s.FULL_NAME, s.CODE_APOGE FROM INSCRIPTION_REQUEST ir 
                JOIN STUDENT s ON ir.STUDENT_ID = s.STUDENT_ID 
                WHERE ir.COURSE_ID = :1 AND ir.STATUS = 'ACCEPTED'
            """, [int(cid)])

            # Profile Display
            with st.container(border=True):
                st.markdown(f"### 🎯 Full Profile: {selected_c_name}")
                
                c1, c2 = st.columns(2)
                with c1:
                    st.write(f"**Capacity:** {len(enrolled_students)} / {c_info['CAPACITY']}")
                    st.write(f"**Filière:** {c_info['FILIERE']} | **Semestre:** {c_info['SEMESTRE']}")
                    # Fetch Dept dynamically
                    dept = execute_query("SELECT d.NAME FROM DEPARTEMENT d JOIN FILIERE f ON d.DEPARTEMENT_ID = f.DEPARTEMENT_ID WHERE f.NAME = :1", [c_info['FILIERE']])
                    st.write(f"**Department:** {dept.iloc[0]['NAME'] if not dept.empty else 'N/A'}")
                
                with c2:
                    st.write(f"**Professor:** {c_info['PROF_NAME'] if c_info['PROF_NAME'] else 'Not Assigned'}")
                    if not prereqs.empty:
                        st.write(f"**📚 Prerequisites:** {', '.join(prereqs['NAME'].tolist())}")
                    else:
                        st.write("**📚 Prerequisites:** None")

                st.divider()
                st.write("👥 **Active Student Enrollment**")
                if not enrolled_students.empty:
                    st.dataframe(enrolled_students, use_container_width=True, hide_index=True)
                else:
                    st.info("No students enrolled in this course yet.")
def display_professor_management():
    st.subheader("👨‍🏫 Professor Management")
    with st.expander("➕ Add New Professor"):
        with st.form("add_prof_form"):
            name = st.text_input("Full Name")
            dept_df = execute_query("SELECT DEPARTEMENT_ID, NAME FROM DEPARTEMENT")
            dept_name = st.selectbox("Department", dept_df['NAME'] if not dept_df.empty else [])
            password = st.text_input("Password", type="password", value="123")
            if st.form_submit_button("Create Professor"):
                d_id = dept_df[dept_df['NAME'] == dept_name]['DEPARTEMENT_ID'].values[0]
                success, msg, code = create_new_professor(name, int(d_id), password)
                if success: st.success(f"{msg} Code: {code}"); st.rerun()
                else: st.error(msg)
    
    search_prof = st.text_input("🔍 Search Professor", key="search_prof")
    profs = execute_query("SELECT p.PROF_ID, p.CODE_APOGE, p.FULL_NAME, d.NAME as DEPARTEMENT FROM PROF p JOIN DEPARTEMENT d ON p.DEPARTEMENT_ID = d.DEPARTEMENT_ID")
    if search_prof and not profs.empty:
        profs = profs[profs.apply(lambda row: row.astype(str).str.contains(search_prof, case=False).any(), axis=1)]
    st.dataframe(profs, use_container_width=True, hide_index=True)

def display_schedule_management():
    st.subheader("📅 Schedule Management")
    filieres = execute_query("SELECT FILIERE_ID, NAME FROM FILIERE")
    if not filieres.empty:
        f_name = st.selectbox("Filiere", filieres['NAME'], key="sch_f")
        f_id = filieres[filieres['NAME'] == f_name]['FILIERE_ID'].values[0]
        
        sems = execute_query("SELECT SEMESTRE_ID, CODE FROM SEMESTRE WHERE FILIERE_ID = :1 AND YEAR_ID = (SELECT MAX(YEAR_ID) FROM ACADEMIC_YEAR)", [int(f_id)])
        if not sems.empty:
            selected_sem = st.selectbox("Semestre", sems['CODE'], key="sch_s")
            s_id = sems[sems['CODE'] == selected_sem]['SEMESTRE_ID'].values[0]
            
            with st.form("new_seance"):
                courses = execute_query("SELECT COURSE_ID, NAME FROM COURSE WHERE SEMESTRE_ID = :1", [int(s_id)])
                sel_c = st.selectbox("Course", courses['NAME'] if not courses.empty else [])
                col1, col2 = st.columns(2)
                s_date = col1.date_input("Date")
                room = col2.text_input("Room")
                t_start = col1.time_input("Start Time", value=datetime.time(8,30))
                t_end = col2.time_input("End Time", value=datetime.time(10,30))
                type_sel = st.selectbox("Type", ["COURS", "TD", "TP"])
                
                if st.form_submit_button("Add Séance"):
                    c_id = courses[courses['NAME'] == sel_c]['COURSE_ID'].values[0]
                    start_dt = datetime.datetime.combine(s_date, t_start)
                    end_dt = datetime.datetime.combine(s_date, t_end)
                    dml = "INSERT INTO SEANCE (COURSE_ID, SEANCE_DATE, START_TIME, END_TIME, ROOM, TYPE, SECTION_ID) VALUES (:1, :2, :3, :4, :5, :6, (SELECT SECTION_ID FROM SECTION WHERE FILIERE_ID=:7 AND SEMESTRE_ID=:8 FETCH FIRST 1 ROW ONLY))"
                    success, msg = execute_dml(dml, [int(c_id), s_date, start_dt, end_dt, room, type_sel, int(f_id), int(s_id)])
                    if success: st.success("Scheduled!"); st.rerun()
                    else: st.error(msg)

def display_admin_dashboard():
    st.title("🎓 University Management System")
    
    # Corrected Tabs for all Management sections
    tabs = st.tabs([
        "Statistics", "Students", "Courses", "Professors", 
        "Departments", "Filières", "Schedules", "Blocked"
    ])
    
    with tabs[0]:
        stats_df = execute_query("SELECT * FROM V_DASHBOARD_STATS")
        if not stats_df.empty:
            stats = stats_df.iloc[0]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Students", stats['TOTAL_STUDENTS'])
            c2.metric("Profs", stats['TOTAL_PROFS'])
            c3.metric("Courses", stats['TOTAL_COURSES'])
            c4.metric("Blocked", stats['BLOCKED_STUDENTS'])
        
    with tabs[1]: display_student_management()
    with tabs[2]: display_course_management()
    with tabs[3]: display_professor_management()
    with tabs[6]: display_schedule_management()