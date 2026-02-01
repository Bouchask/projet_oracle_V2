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
    
    # 1. Form to add a new course
    with st.expander("➕ Add New Course", expanded=False):
        # (The form to add a course remains unchanged)
        filieres_df_form = execute_query("SELECT FILIERE_ID, NAME FROM FILIERE ORDER BY NAME")
        if not filieres_df_form.empty:
            selected_filiere_form = st.selectbox("Select Filiere", filieres_df_form['NAME'], key="add_c_filiere")
            f_id_form = filieres_df_form[filieres_df_form['NAME'] == selected_filiere_form]['FILIERE_ID'].values[0].item()
            
            col1_form, col2_form = st.columns(2)
            c_name_form = col1_form.text_input("Course Name")
            capacity_form = col1_form.number_input("Capacity", min_value=1, value=30)
            
            sem_query_form = "SELECT s.SEMESTRE_ID, s.CODE, s.YEAR_ID, s.CODE || ' (' || ay.LABEL || ')' as DISP FROM SEMESTRE s JOIN ACADEMIC_YEAR ay ON s.YEAR_ID = ay.YEAR_ID WHERE s.FILIERE_ID = :1 AND s.YEAR_ID = (SELECT MAX(YEAR_ID) FROM ACADEMIC_YEAR)"
            sems_form = execute_query(sem_query_form, [int(f_id_form)])
            selected_sem_display_form = col2_form.selectbox("Semestre", sems_form['DISP'] if not sems_form.empty else [])
            
            if not sems_form.empty and selected_sem_display_form:
                current_sem_id_form = int(sems_form[sems_form['DISP'] == selected_sem_display_form]['SEMESTRE_ID'].values[0])
                current_year_id_form = int(sems_form[sems_form['DISP'] == selected_sem_display_form]['YEAR_ID'].values[0])
                
                prof_query_form = "SELECT p.PROF_ID, p.FULL_NAME FROM PROF p LEFT JOIN PROF_COURSE pc ON p.PROF_ID = pc.PROF_ID LEFT JOIN COURSE c ON pc.COURSE_ID = c.COURSE_ID LEFT JOIN SEMESTRE s ON c.SEMESTRE_ID = s.SEMESTRE_ID WHERE p.DEPARTEMENT_ID = (SELECT DEPARTEMENT_ID FROM FILIERE WHERE FILIERE_ID = :1) GROUP BY p.PROF_ID, p.FULL_NAME HAVING COUNT(CASE WHEN s.YEAR_ID = :2 THEN pc.COURSE_ID END) < 3 OR COUNT(pc.COURSE_ID) = 0 ORDER BY p.FULL_NAME"
                profs_form = execute_query(prof_query_form, [int(f_id_form), int(current_year_id_form)])
                selected_prof_form = col2_form.selectbox("Assign Professor", profs_form['FULL_NAME'] if not profs_form.empty else [])

            if st.button("Add Course"):
                if not c_name_form or 'profs_form' not in locals() or profs_form.empty or sems_form.empty:
                    st.error("Please fill all required fields and ensure a professor is selected.")
                else:
                    p_id_form = int(profs_form[profs_form['FULL_NAME'] == selected_prof_form]['PROF_ID'].values[0])
                    success, msg = create_course_with_details(c_name_form, f_id_form, current_sem_id_form, capacity_form, p_id_form, [])
                    if success: 
                        st.success(msg)
                        st.rerun()
                    else: 
                        st.error(msg)
    
    st.divider()

    # 1. Main Course List
    st.subheader("📚 Global Course List")
    courses_df = execute_query("SELECT * FROM V_DETAIL_COURSE ORDER BY COURSE_NAME")
    st.dataframe(courses_df, use_container_width=True, hide_index=True)
    
    st.divider()

    # 2. Integrated Explore & Detail Section
    st.subheader("🔎 Explore Course Details")
    
    if not courses_df.empty:
        courses_df['display'] = courses_df['COURSE_NAME'] + ' (ID: ' + courses_df['COURSE_ID'].astype(str) + ')'
        selected_course_display = st.selectbox("Select a course to manage:", ["-- Choose a Course --"] + courses_df['display'].tolist())

        if selected_course_display != "-- Choose a Course --":
            selected_course_info = courses_df[courses_df['display'] == selected_course_display].iloc[0]
            cid = int(selected_course_info['COURSE_ID'])

            # Fetch additional details for the selected course
            prereqs_df = execute_query("SELECT cp.NAME FROM COURSE_PREREQUISITE pr JOIN COURSE cp ON pr.PREREQUISITE_COURSE_ID = cp.COURSE_ID WHERE pr.COURSE_ID = :1", [cid])
            inscriptions_df = execute_query("SELECT s.full_name, ir.status, ir.request_id FROM INSCRIPTION_REQUEST ir JOIN STUDENT s ON ir.student_id = s.student_id WHERE ir.course_id = :1", [cid])
            
            # Filter for accepted students
            enrolled_students_df = inscriptions_df[inscriptions_df['STATUS'] == 'ACCEPTED']

            # Full Profile Card
            with st.container(border=True):
                st.markdown(f"### 🎯 Full Profile: {selected_course_info['COURSE_NAME']}")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Enrollment Progress", f"{len(enrolled_students_df)} / {selected_course_info['CAPACITY']}")
                    st.write(f"**Filière:** {selected_course_info['FILIERE']}")
                    st.write(f"**Semestre:** {selected_course_info['SEMESTRE']}")
                with col2:
                    st.write(f"**Professor:** {selected_course_info['PROF_NAME'] if pd.notna(selected_course_info['PROF_NAME']) else 'Not Assigned'}")
                    st.write(f"**Prerequisites:** {', '.join(prereqs_df['NAME'].tolist()) if not prereqs_df.empty else 'None'}")

            # Active Enrollment List
            st.write("---")
            st.write("👥 **Active Enrollment List**")
            if not enrolled_students_df.empty:
                st.dataframe(enrolled_students_df[['FULL_NAME']], use_container_width=True, hide_index=True, column_config={"FULL_NAME": "Student Name"})
            else:
                st.info("No students are actively enrolled in this course yet.")
            
            st.divider()

            # 3. Contextual Enrollment Management
            st.subheader(f"✉️ Enrollment Requests for {selected_course_info['COURSE_NAME']}")
            
            search_enrollment = st.text_input("Search enrollments by student name:", key=f"search_enroll_{cid}")
            
            display_inscriptions = inscriptions_df
            if search_enrollment:
                display_inscriptions = inscriptions_df[inscriptions_df['FULL_NAME'].str.contains(search_enrollment, case=False, na=False)]
            
            st.dataframe(display_inscriptions[['FULL_NAME', 'STATUS']], use_container_width=True, hide_index=True, column_config={"FULL_NAME": "Student Name", "STATUS": "Status"})

            # Cancel Action
            st.write("---")
            st.write("⚙️ **Manage Inscription Status**")
            
            cancellable_inscriptions = inscriptions_df[inscriptions_df['STATUS'].isin(['PENDING', 'ACCEPTED'])]
            if not cancellable_inscriptions.empty:
                cancellable_inscriptions['display'] = cancellable_inscriptions.apply(lambda row: f"{row['FULL_NAME']} ({row['STATUS']}) - ID: {row['REQUEST_ID']}", axis=1)
                
                selected_to_cancel = st.selectbox("Select an enrollment to cancel:", cancellable_inscriptions['display'])
                
                req_id_to_cancel = int(cancellable_inscriptions[cancellable_inscriptions['display'] == selected_to_cancel].iloc[0]['REQUEST_ID'])
                
                if st.button("🔴 Cancel Enrollment", key=f"cancel_enroll_{req_id_to_cancel}"):
                    success, msg = execute_dml("UPDATE INSCRIPTION_REQUEST SET status = 'REJECTED' WHERE request_id = :1", [req_id_to_cancel])
                    if success:
                        st.success("Enrollment has been canceled/rejected.")
                        st.rerun()
                    else:
                        st.error(f"Failed to cancel enrollment: {msg}")
            else:
                st.info("No active or pending enrollments to manage for this course.")
    else:
        st.info("No courses available in the system.")
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
            
            # New code to show all sessions filtered by Filière and Semestre
            st.divider()
            st.subheader("🗓️ All Sessions")

            # Query to fetch all sessions for the selected filiere and semestre
            sessions_query = """
                SELECT
                    c.name AS "Course",
                    se.type AS "Type",
                    TO_CHAR(se.seance_date, 'YYYY-MM-DD') AS "Date",
                    TO_CHAR(se.start_time, 'HH24:MI') AS "Start Time",
                    TO_CHAR(se.end_time, 'HH24:MI') AS "End Time",
                    se.room AS "Room"
                FROM seance se
                JOIN course c ON se.course_id = c.course_id
                JOIN section sec ON se.section_id = sec.section_id
                WHERE sec.filiere_id = :filiere_id AND sec.semestre_id = :semestre_id
                ORDER BY se.seance_date, se.start_time
            """
            sessions_df = execute_query(sessions_query, [int(f_id), int(s_id)])

            if not sessions_df.empty:
                st.dataframe(sessions_df, use_container_width=True, hide_index=True)
            else:
                st.info(f"No sessions found for Filière '{f_name}' and Semestre '{selected_sem}'.")
        else: # if not sems.empty is false, but filieres is not empty
            st.info("No active semesters found for the selected Filière. Please create one.")
    else: # if filieres is empty
        st.info("No filières found. Please create a Filière first.")

def display_filiere_management():
    st.subheader("🎓 Filière Management")

    # --- Form: Add New Filière ---
    with st.expander("➕ Add New Filière"):
        with st.form("add_filiere_form"):
            filiere_name = st.text_input("Filière Name")
            
            # Fetch departments for the selectbox
            depts_df = execute_query("SELECT DEPARTEMENT_ID, NAME FROM DEPARTEMENT ORDER BY NAME")
            if not depts_df.empty:
                dept_name = st.selectbox("Parent Department", depts_df['NAME'])
            else:
                st.warning("No departments found. Please create a department first.")
                dept_name = None

            submitted = st.form_submit_button("Create Filière")
            if submitted:
                if not filiere_name or not dept_name:
                    st.error("Please fill all fields.")
                else:
                    dept_id = depts_df[depts_df['NAME'] == dept_name]['DEPARTEMENT_ID'].values[0]
                    success, msg = execute_dml("INSERT INTO FILIERE (NAME, DEPARTEMENT_ID) VALUES (:1, :2)", [filiere_name, int(dept_id)])
                    if success:
                        st.success("Filière created successfully!")
                        st.rerun()
                    else:
                        st.error(f"Error creating filière: {msg}")

    st.divider()

    # --- View All Filières with Search ---
    st.subheader("📋 All Filières")
    search_filiere = st.text_input("🔍 Search by Filière Name or Department", key="search_filiere")
    
    filieres_df = execute_query("SELECT FILIERE_ID, FILIERE, DEPARTEMENT, TOTAL_SEMESTRES FROM V_DETAIL_FILIERE")

    if search_filiere and not filieres_df.empty:
        # Using a more robust search method to check all string columns
        filieres_df = filieres_df[filieres_df.apply(lambda row: row.astype(str).str.contains(search_filiere, case=False).any(), axis=1)]

    st.dataframe(filieres_df, use_container_width=True, hide_index=True)

    if not filieres_df.empty:
        st.divider()
        st.subheader("🔎 Explore Filière")
        
        filiere_names = filieres_df['FILIERE'].tolist()
        selected_filiere_name = st.selectbox("Select a filière", ["-- Choose a Filière --"] + filiere_names)

        if selected_filiere_name != "-- Choose a Filière --":
            # Ensure the selected filiere is still in the dataframe after a potential search filter
            filtered_filiere_info = filieres_df[filieres_df['FILIERE'] == selected_filiere_name]
            if not filtered_filiere_info.empty:
                selected_filiere_id = int(filtered_filiere_info.iloc[0]['FILIERE_ID'])

                col1, col2 = st.columns(2)

                with col1:
                    st.write("👥 **Enrolled Students**")
                    students_df = execute_query("SELECT FULL_NAME, CODE_APOGE FROM STUDENT WHERE FILIERE_ID = :1 ORDER BY FULL_NAME", [selected_filiere_id])
                    if not students_df.empty:
                        st.dataframe(students_df, hide_index=True, use_container_width=True)
                    else:
                        st.info("No students enrolled in this filière.")

                with col2:
                    st.write("📚 **Semesters**")
                    semesters_df = execute_query("""
                        SELECT s.CODE, ay.LABEL AS ACADEMIC_YEAR
                        FROM SEMESTRE s
                        JOIN ACADEMIC_YEAR ay ON s.YEAR_ID = ay.YEAR_ID
                        WHERE s.FILIERE_ID = :1
                        ORDER BY ay.START_DATE DESC, s.CODE
                    """, [selected_filiere_id])
                    if not semesters_df.empty:
                        st.dataframe(semesters_df, hide_index=True, use_container_width=True)
                    else:
                        st.info("No semesters defined for this filière.")

                # --- Drop Filière ---
                st.divider()
                with st.expander("🗑️ Danger Zone: Delete Filière"):
                    st.warning(f"This will attempt to delete the **{selected_filiere_name}** filière. This action is irreversible and will fail if any students, semesters, or courses are still assigned to it.")
                    
                    if st.button("Confirm and Delete Filière", key=f"delete_filiere_{selected_filiere_id}"):
                        success, msg = execute_dml("DELETE FROM FILIERE WHERE FILIERE_ID = :1", [selected_filiere_id])
                        if success:
                            st.success(f"Filière '{selected_filiere_name}' deleted successfully.")
                            st.rerun()
                        else:
                            st.error(f"Deletion Failed: {msg}")

def display_department_management():
    st.subheader("🏢 Department Management")

    # --- Form: Add New Department ---
    with st.expander("➕ Add New Department"):
        with st.form("add_dept_form"):
            dept_name = st.text_input("Department Name")
            submitted = st.form_submit_button("Create Department")
            if submitted:
                if not dept_name:
                    st.error("Department name cannot be empty.")
                else:
                    success, msg = execute_dml("INSERT INTO DEPARTEMENT (NAME) VALUES (:1)", [dept_name])
                    if success:
                        st.success("Department created successfully!")
                        st.rerun()
                    else:
                        st.error(f"Error creating department: {msg}")

    st.divider()

    # --- View All Departments ---
    st.subheader("📋 All Departments")
    search_dept = st.text_input("🔍 Search Department by Name", key="search_department")
    depts_df = execute_query("SELECT DEPARTEMENT_ID, DEPARTEMENT as \"Department Name\", TOTAL_FILIERES as \"Total Filières\", TOTAL_PROFS as \"Total Professors\" FROM V_DETAIL_DEPARTEMENT ORDER BY \"Department Name\"")
    
    if search_dept and not depts_df.empty:
        depts_df = depts_df[depts_df.apply(lambda row: row.astype(str).str.contains(search_dept, case=False).any(), axis=1)]

    st.dataframe(depts_df, use_container_width=True, hide_index=True)

    if not depts_df.empty:
        st.divider()
        st.subheader("🔎 Explore Department")
        
        dept_names = depts_df['Department Name'].tolist()
        selected_dept_name = st.selectbox("Select a department", ["-- Choose a Department --"] + dept_names)

        if selected_dept_name != "-- Choose a Department --":
            # Ensure the selected department is still in the dataframe after a potential search filter
            filtered_dept_info = depts_df[depts_df['Department Name'] == selected_dept_name]
            if not filtered_dept_info.empty:
                selected_dept_id = int(filtered_dept_info.iloc[0]['DEPARTEMENT_ID'])

                col1, col2 = st.columns(2)

                # --- List Professors in Department ---
                with col1:
                    st.write("👨‍🏫 **Professors**")
                    profs_in_dept = execute_query("SELECT FULL_NAME FROM PROF WHERE DEPARTEMENT_ID = :1 ORDER BY FULL_NAME", [selected_dept_id])
                    if not profs_in_dept.empty:
                        st.dataframe(profs_in_dept, hide_index=True, use_container_width=True)
                    else:
                        st.info("No professors in this department.")

                # --- List Filières in Department ---
                with col2:
                    st.write("🎓 **Filières**")
                    filieres_in_dept = execute_query("SELECT NAME FROM FILIERE WHERE DEPARTEMENT_ID = :1 ORDER BY NAME", [selected_dept_id])
                    if not filieres_in_dept.empty:
                        st.dataframe(filieres_in_dept, hide_index=True, use_container_width=True)
                    else:
                        st.info("No filières in this department.")

                # --- Drop Department ---
                st.divider()
                with st.expander("🗑️ Danger Zone: Delete Department"):
                    st.warning(f"This will attempt to delete the **{selected_dept_name}** department. This action is irreversible and will only succeed if no professors or filières are currently assigned to it.")
                    
                    if st.button("Confirm and Delete Department", key=f"delete_dept_{selected_dept_id}"):
                        # Attempt to delete. The DML utility will catch the integrity constraint error.
                        success, msg = execute_dml("DELETE FROM DEPARTEMENT WHERE DEPARTEMENT_ID = :1", [selected_dept_id])
                        if success:
                            st.success(f"Department '{selected_dept_name}' deleted successfully.")
                            st.rerun()
                        else:
                            st.error(f"Deletion Failed: {msg}")

def display_semestre_management():
    st.subheader("📚 Semester Management")

    # 1. Add New Semestre
    with st.expander("➕ Add New Semester"):
        with st.form("add_semester_form"):
            filieres_df = execute_query("SELECT FILIERE_ID, NAME FROM FILIERE ORDER BY NAME")
            years_df = execute_query("SELECT YEAR_ID, LABEL FROM ACADEMIC_YEAR ORDER BY LABEL DESC")

            selected_filiere_name = st.selectbox("Filiere", filieres_df['NAME'] if not filieres_df.empty else [], key="sem_filiere")
            semester_code = st.text_input("Semester Code (e.g., S1, S2)")
            selected_year_label = st.selectbox("Academic Year", years_df['LABEL'] if not years_df.empty else [], key="sem_year")

            submitted = st.form_submit_button("Create Semester")
            if submitted:
                if not all([selected_filiere_name, semester_code, selected_year_label]):
                    st.error("Please fill all fields.")
                else:
                    f_id = filieres_df[filieres_df['NAME'] == selected_filiere_name]['FILIERE_ID'].iloc[0]
                    y_id = years_df[years_df['LABEL'] == selected_year_label]['YEAR_ID'].iloc[0]
                    success, msg = execute_dml(
                        "INSERT INTO SEMESTRE (CODE, FILIERE_ID, YEAR_ID) VALUES (:1, :2, :3)",
                        [semester_code.upper(), int(f_id), int(y_id)]
                    )
                    if success:
                        st.success("Semester created successfully!")
                        st.rerun()
                    else:
                        st.error(f"Failed to create semester: {msg}")

    st.divider()

    # 2. View & Filter Semesters
    st.subheader("📋 All Semesters")
    
    all_semesters_query = """
        SELECT 
            s.SEMESTRE_ID, 
            s.CODE, 
            f.NAME as FILIERE_NAME, 
            ay.LABEL as ACADEMIC_YEAR
        FROM SEMESTRE s
        JOIN FILIERE f ON s.FILIERE_ID = f.FILIERE_ID
        JOIN ACADEMIC_YEAR ay ON s.YEAR_ID = ay.YEAR_ID
        ORDER BY ay.LABEL DESC, f.NAME, s.CODE
    """
    all_semesters_df = execute_query(all_semesters_query)

    filiere_list_filter = ["All Filières"] + sorted(all_semesters_df['FILIERE_NAME'].unique())
    selected_filiere_filter = st.selectbox("Filter by Filière", filiere_list_filter)

    if selected_filiere_filter == "All Filières":
        display_semesters_df = all_semesters_df
    else:
        display_semesters_df = all_semesters_df[all_semesters_df['FILIERE_NAME'] == selected_filiere_filter]
    
    st.dataframe(display_semesters_df[['CODE', 'FILIERE_NAME', 'ACADEMIC_YEAR']], use_container_width=True, hide_index=True)

    st.divider()

    # 3. Detailed Semester View
    st.subheader("🔎 Explore Semester Content")
    if not display_semesters_df.empty:
        display_semesters_df['display'] = display_semesters_df.apply(
            lambda row: f"{row['CODE']} - {row['FILIERE_NAME']} ({row['ACADEMIC_YEAR']})", axis=1
        )
        selected_semester_display = st.selectbox(
            "Select a semester to see its courses:",
            ["-- Choose a Semester --"] + display_semesters_df['display'].tolist()
        )

        if selected_semester_display != "-- Choose a Semester --":
            selected_sem_id = display_semesters_df[display_semesters_df['display'] == selected_semester_display].iloc[0]['SEMESTRE_ID']
            
            courses_in_sem_df = execute_query("""
                SELECT 
                    c.NAME AS "Course Name",
                    p.FULL_NAME AS "Professor"
                FROM COURSE c
                LEFT JOIN PROF_COURSE pc ON c.COURSE_ID = pc.COURSE_ID
                LEFT JOIN PROF p ON pc.PROF_ID = p.PROF_ID
                WHERE c.SEMESTRE_ID = :1
                ORDER BY c.NAME
            """, [int(selected_sem_id)])

            st.write(f"**Courses in {selected_semester_display}:**")
            if not courses_in_sem_df.empty:
                st.dataframe(courses_in_sem_df, use_container_width=True, hide_index=True)
            else:
                st.info("No courses are assigned to this semester yet.")
    else:
        st.info("No semesters to display for the selected filter.")

def display_admin_dashboard():
    st.title("🎓 University Management System")
    
    tabs = st.tabs([
        "Statistics", "Students", "Courses", "Professors", 
        "Departments", "Filières", "Semesters", "Schedules", "Blocked"
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
    with tabs[4]: display_department_management()
    with tabs[5]: display_filiere_management()
    with tabs[6]: display_semestre_management()
    with tabs[7]: display_schedule_management()