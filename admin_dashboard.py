import streamlit as st
import pandas as pd
import random
import datetime
from db_utils import (
    execute_query, execute_dml, create_course_with_details, create_new_professor, delete_course_with_details
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
                    success, msg = execute_dml("INSERT INTO USER_ACCOUNT (LOGIN_CODE, PASSWORD_HASH, ROLE) VALUES (:1, :2, :3)", [login_code, password, 'STUDENT'])
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
    students = execute_query("""
        SELECT
            s.student_id,
            s.code_apoge,
            s.full_name,
            f.name AS filiere,
            sem.code || ' (' || ay.label || ')' AS semestre,
            ua.status AS account_status
        FROM student s
        JOIN filiere f ON f.filiere_id = s.filiere_id
        JOIN semestre sem ON sem.semestre_id = s.current_semestre_id
        JOIN academic_year ay ON ay.year_id = sem.year_id
        JOIN user_account ua ON ua.login_code = s.code_apoge
    """)
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
                SELECT 
                    c.NAME AS COURSE_NAME, 
                    s.CODE || ' (' || ay.LABEL || ')' AS SEMESTRE, 
                    NVL(cr.STATUS, 'IN_PROGRESS') as STATUS 
                FROM STUDENT st
                JOIN SEMESTRE s ON s.SEMESTRE_ID = st.CURRENT_SEMESTRE_ID
                JOIN ACADEMIC_YEAR ay ON ay.YEAR_ID = s.YEAR_ID
                JOIN COURSE c ON c.SEMESTRE_ID = s.SEMESTRE_ID
                LEFT JOIN COURSE_RESULT cr ON cr.STUDENT_ID = st.STUDENT_ID AND cr.COURSE_ID = c.COURSE_ID
                WHERE st.STUDENT_ID = :1
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
            sem_query = """
                SELECT s.SEMESTRE_ID, s.CODE, s.YEAR_ID, s.CODE || ' (' || ay.LABEL || ')' as DISP 
                FROM SEMESTRE s JOIN ACADEMIC_YEAR ay ON s.YEAR_ID = ay.YEAR_ID
                WHERE s.FILIERE_ID = :1 AND s.YEAR_ID = (SELECT MAX(YEAR_ID) FROM ACADEMIC_YEAR)
            """
            sems = execute_query(sem_query, [int(f_id)])
            selected_sem_display = col2.selectbox("Semestre", sems['DISP'] if not sems.empty else [])
            
            # Extract current_sem_id and current_sem_code, and its numeric part, from the selected display value
            if not sems.empty and selected_sem_display:
                current_sem_id = int(sems[sems['DISP'] == selected_sem_display]['SEMESTRE_ID'].values[0])
                current_sem_code_str = sems[sems['DISP'] == selected_sem_display]['CODE'].values[0]
                # Extract numeric part for comparison, assuming format 'S<number>'
                current_sem_code_numeric = int(current_sem_code_str[1:])
            else:
                current_sem_id = None
                current_sem_code_str = None
                current_sem_code_numeric = None

            # Prerequisites: Only from previous semesters
            selected_prereqs = []
            if not sems.empty and selected_sem_display and current_sem_id is not None: # Check if semester is selected and valid
                # current_sem_id, current_sem_code_str, current_sem_code_numeric are already derived
                
                # We need current_year_id to filter prerequisites and professors
                # This information is already available in the `sems` DataFrame as `YEAR_ID` for the `current_sem_id`
                # Find the row in `sems` that matches `current_sem_id`
                current_sem_info = sems[sems['SEMESTRE_ID'] == current_sem_id]
                if not current_sem_info.empty:
                    current_year_id = int(current_sem_info.iloc[0]['YEAR_ID'])
                    # Fetch target academic year's start date
                    target_ay_df = execute_query("SELECT START_DATE FROM ACADEMIC_YEAR WHERE YEAR_ID = :1", [int(current_year_id)])
                    if not target_ay_df.empty:
                        target_ay_start_date = target_ay_df.iloc[0]['START_DATE']
                    else:
                        st.error("Could not retrieve target academic year start date.")
                        target_ay_start_date = None
                else:
                    st.error("Could not retrieve current year information for selected semester.")
                    current_year_id = None # Ensure it's None if not found
                    target_ay_start_date = None

                if current_year_id is not None and target_ay_start_date is not None:
                    # Professors filtering: show only those with < 3 courses in the current academic year
                    prof_query = """
                        SELECT 
                            p.PROF_ID, 
                            p.FULL_NAME
                        FROM PROF p
                        LEFT JOIN PROF_COURSE pc ON p.PROF_ID = pc.PROF_ID
                        LEFT JOIN COURSE c ON pc.COURSE_ID = c.COURSE_ID
                        LEFT JOIN SEMESTRE s ON c.SEMESTRE_ID = s.SEMESTRE_ID
                        WHERE p.DEPARTEMENT_ID = (SELECT DEPARTEMENT_ID FROM FILIERE WHERE FILIERE_ID = :1)
                        GROUP BY p.PROF_ID, p.FULL_NAME
                        HAVING COUNT(CASE WHEN s.YEAR_ID = :2 THEN pc.COURSE_ID END) < 3
                        OR COUNT(pc.COURSE_ID) = 0 -- Include professors with no assigned courses
                        ORDER BY p.FULL_NAME
                    """
                    profs = execute_query(prof_query, [int(f_id), int(current_year_id)])
                    selected_prof = col2.selectbox("Assign Professor", profs['FULL_NAME'] if not profs.empty else [])

                    prereqs_df = execute_query("""
                        SELECT
                            c.COURSE_ID,
                            c.NAME || ' - ' || cs.CODE || ' (' || ay.LABEL || ')' AS DISPLAY_NAME
                        FROM
                            COURSE c
                        JOIN
                            SEMESTRE cs ON c.SEMESTRE_ID = cs.SEMESTRE_ID
                        JOIN
                            ACADEMIC_YEAR ay ON cs.YEAR_ID = ay.YEAR_ID
                        WHERE
                            c.FILIERE_ID = :1 -- Same filiere
                            AND (
                                ay.START_DATE < :2 -- Any previous Academic Year
                                OR (
                                    ay.START_DATE = :3 -- Current Academic Year
                                    AND TO_NUMBER(SUBSTR(cs.CODE, 2)) < :4 -- strictly lower semester number
                                )
                            )
                        ORDER BY
                            ay.LABEL DESC, TO_NUMBER(SUBSTR(cs.CODE, 2)) DESC
                    """, [int(f_id), target_ay_start_date, target_ay_start_date, current_sem_code_numeric])
                    selected_prereqs_display = st.multiselect("Prerequisites (Optional)", prereqs_df['DISPLAY_NAME'] if not prereqs_df.empty else [])
                else:
                    st.info("Select a valid semester to view prerequisites and assign a professor.")
            else:
                st.info("Select a semester to view prerequisites and assign a professor.")

            if st.button("Add Course"):
                if not c_name or profs.empty or sems.empty:
                    st.error("Please fill all required fields.")
                else:
                    p_id = int(profs[profs['FULL_NAME'] == selected_prof]['PROF_ID'].values[0])
                    pr_ids = prereqs_df[prereqs_df['DISPLAY_NAME'].isin(selected_prereqs_display)]['COURSE_ID'].tolist() if not prereqs_df.empty else []
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

    # 4. Form: Drop Course
    with st.expander("🗑️ Drop Course", expanded=False):
        all_courses_for_drop_df = execute_query("SELECT COURSE_ID, NAME FROM COURSE ORDER BY NAME")
        if not all_courses_for_drop_df.empty:
            course_to_drop_name = st.selectbox("Select Course to Drop", all_courses_for_drop_df['NAME'], key="drop_c_name")
            
            if st.button("Confirm Drop Course"):
                course_to_drop_id = int(all_courses_for_drop_df[all_courses_for_drop_df['NAME'] == course_to_drop_name]['COURSE_ID'].values[0])
                success, msg = delete_course_with_details(course_to_drop_id)
                if success:
                    st.success(f"Course '{course_to_drop_name}' deleted successfully.")
                    st.rerun()
                else:
                    st.error(f"Error dropping course: {msg}")
        else:
            st.info("No courses available to drop.")
        
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
    
    # --- Form: Add New Professor ---
    with st.expander("➕ Add New Professor"):
        with st.form("add_prof_form"):
            name = st.text_input("Full Name")
            dept_df = execute_query("SELECT DEPARTEMENT_ID, NAME FROM DEPARTEMENT ORDER BY NAME")
            dept_name = st.selectbox("Department", dept_df['NAME'] if not dept_df.empty else [])
            password = st.text_input("Password", type="password", value="123")
            if st.form_submit_button("Create Professor"):
                if not name or dept_df.empty:
                    st.error("Please fill all required fields.")
                else:
                    d_id = dept_df[dept_df['NAME'] == dept_name]['DEPARTEMENT_ID'].values[0].item()
                    success, msg, code = create_new_professor(name, int(d_id), password)
                    if success: st.success(f"{msg} Login Code: {code}"); st.rerun()
                    else: st.error(msg)
    
    st.divider()

    # --- Professor List & Search ---
    search_prof = st.text_input("🔍 Search Professor", key="search_prof")
    profs_list_df = execute_query("SELECT p.PROF_ID, p.CODE_APOGE, p.FULL_NAME, d.NAME as DEPARTEMENT FROM PROF p JOIN DEPARTEMENT d ON p.DEPARTEMENT_ID = d.DEPARTEMENT_ID ORDER BY p.FULL_NAME")
    if search_prof and not profs_list_df.empty:
        profs_list_df = profs_list_df[profs_list_df.apply(lambda row: row.astype(str).str.contains(search_prof, case=False).any(), axis=1)]
    st.dataframe(profs_list_df, use_container_width=True, hide_index=True)

    st.markdown("---")

    # --- Detailed Professor View ---
    st.subheader("🔎 Detailed Professor View")
    if not profs_list_df.empty:
        prof_names = profs_list_df['FULL_NAME'].tolist()
        selected_prof_name = st.selectbox("Select a professor to view details:", ["-- Select a Professor --"] + prof_names)
        
        if selected_prof_name != "-- Select a Professor --":
            selected_prof_info = profs_list_df[profs_list_df['FULL_NAME'] == selected_prof_name].iloc[0]
            prof_id_for_details = int(selected_prof_info['PROF_ID'])
            prof_department = selected_prof_info['DEPARTEMENT']

            st.markdown(f"### 🧑‍🏫 {selected_prof_name}")
            st.write(f"**Department:** {prof_department}")

            # Fetch latest academic year
            latest_year_df = execute_query("SELECT MAX(YEAR_ID) as MAX_YEAR_ID, MAX(LABEL) as MAX_YEAR_LABEL FROM ACADEMIC_YEAR")
            latest_year_id = int(latest_year_df.iloc[0]['MAX_YEAR_ID']) if not latest_year_df.empty else None
            latest_year_label = latest_year_df.iloc[0]['MAX_YEAR_LABEL'] if not latest_year_df.empty else "N/A"

            if latest_year_id is not None:
                # Fetch all courses for the selected professor
                all_prof_courses_df = execute_query(f"""
                    SELECT
                        pco.course_id,
                        c.name AS course_name,
                        f.name AS filiere_name,
                        sem.code || ' (' || ay.label || ')' AS semestre_full,
                        ay.year_id,
                        ay.label AS academic_year_label
                    FROM prof_course pco
                    JOIN prof p ON p.prof_id = pco.prof_id
                    JOIN course c ON c.course_id = pco.course_id
                    JOIN filiere f ON f.filiere_id = c.filiere_id
                    JOIN semestre sem ON sem.semestre_id = c.semestre_id
                    JOIN academic_year ay ON ay.year_id = sem.year_id
                    WHERE pco.prof_id = :1
                    ORDER BY ay.start_date DESC, TO_NUMBER(SUBSTR(sem.code, 2)) DESC
                """, [prof_id_for_details])

                if not all_prof_courses_df.empty:
                    current_year_courses = all_prof_courses_df[all_prof_courses_df['YEAR_ID'] == latest_year_id]
                    past_courses = all_prof_courses_df[all_prof_courses_df['YEAR_ID'] < latest_year_id]

                    # Capacity Counter
                    courses_this_year_count = len(current_year_courses)
                    st.metric(label=f"Courses this Year ({latest_year_label})", value=f"{courses_this_year_count} / 3")

                    st.markdown("#### Current Academic Year Courses")
                    if not current_year_courses.empty:
                        st.dataframe(current_year_courses[['COURSE_NAME', 'FILIERE_NAME', 'SEMESTRE_FULL']], use_container_width=True, hide_index=True)
                    else:
                        st.info("No courses assigned for the current academic year.")

                    st.markdown("#### Past Courses History")
                    if not past_courses.empty:
                        st.dataframe(past_courses[['COURSE_NAME', 'FILIERE_NAME', 'SEMESTRE_FULL', 'ACADEMIC_YEAR_LABEL']], use_container_width=True, hide_index=True)
                    else:
                        st.info("No past courses history found.")
                else:
                    st.info("No courses assigned to this professor.")
            else:
                st.info("Could not retrieve academic year information.")
    else:
        st.info("No professors available to display details.")

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