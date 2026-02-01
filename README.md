# 🎓 Advanced Course Registration System

An advanced university course registration system built with a Streamlit frontend and a powerful Oracle Database backend. This project emphasizes a database-centric architecture where business logic, security, and data integrity are enforced at the database level using PL/SQL triggers, procedures, and a role-based security model.

---

## ✨ Core Features

The system provides three distinct dashboards, one for each user role:

### 👤 Admin Dashboard
*   **Full System Overview**: A statistics panel showing counts of students, professors, courses, and blocked students.
*   **Student Management**: Add new students, view detailed academic profiles, and track enrollment history.
*   **Course Management**: Create new courses with prerequisites, assign professors, and manage capacity.
*   **Enrollment Management**: A dedicated interface to view all inscription requests and manually `Accept` or `Reject` them.
*   **Academic Structure**: Full CRUD management for Departments, Filières, Semesters, and class Sections.
*   **Scheduling**: A complete interface to schedule individual class sessions (`séances`) with conflict detection for rooms and professors.

### 👩‍🏫 Professor Dashboard
*   **Course & Student Overview**: View assigned courses and see a detailed list of enrolled students, including their academic status (e.g., `BLOCKED`).
*   **Enrollment Management**: Accept or refuse pending enrollment requests from students for assigned courses.
*   **Attendance Tracking**: Mark student attendance (`Present`, `Absent`, `Late`, etc.) for each session.
*   **Grade Submission**: A simple form to submit final grades for students. The database automatically validates the grade and sets the student's status to `VALID` or `FAILED`.
*   **Performance Analytics**: View a summary of student absences to identify at-risk students.

### 🧑‍🎓 Student Dashboard
*   **Personalized Homepage**: A profile card and a summary of academic standing (blocked courses, total absences).
*   **Course Registration**: View available courses for the current semester and submit enrollment requests.
*   **Enrollment Status**: Track the status (`PENDING`, `ACCEPTED`, `REJECTED`) of all enrollment requests.
*   **Section Selection**: Interactively join a `Section` (tutorial/lab group) for the semester.
*   **Personalized Schedule**: View a detailed schedule of all sessions for accepted courses and joined sections.
*   **Grades & Performance**: Check final grades, GPA, and a detailed summary of absences per course.
*   **Profile Management**: Change account password.

---

## 🏛️ Architecture Overview

This project uses a **database-centric, two-tier architecture**.

1.  **Frontend**: A responsive user interface built entirely in **Python** with the **Streamlit** framework.
2.  **Backend & Database**: An **Oracle Database** serves as more than just a data store; it's the core of the system's logic.
    *   **PL/SQL Triggers** automate and enforce all critical business rules (course capacity, prerequisites, absence tracking, scheduling conflicts).
    *   **Stored Procedures & Functions** encapsulate complex, multi-step business logic (e.g., `admin_unblock_student`, `sp_prof_submit_grade`).
    *   **Database Views** act as a secure and simplified API layer, providing pre-joined and pre-formatted data to the Streamlit frontend.
    *   **Role-Based Security** ensures that data access is controlled at the database level, providing a high degree of security.

---

## 🚀 How to Run the Project

Follow these steps to set up the database and run the application.

### Prerequisites
*   Python 3.8+
*   Docker Desktop
*   An Oracle Database Docker image (e.g., `container-registry.oracle.com/database/enterprise:19.3.0.0`)

### Step 1: Start the Oracle Database
Open a terminal and run the following command to start an Oracle database container. Replace `YourSystemPassword` with a strong password for the `SYSTEM` user.

```bash
docker run -d --name oracle-19c -p 1521:1521 -e ORACLE_PWD=YourSystemPassword container-registry.oracle.com/database/enterprise:19.3.0.0
```
> **Note:** It may take 5-15 minutes for the database to be fully initialized and ready to accept connections.

### Step 2: Set Up the Python Environment
In your project directory, create a virtual environment and install the required packages.
```bash
# Create a virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Initialize the Database (One-Time Setup)
This is the most critical step. The following two scripts must be run **in order** to create the schema, users, and permissions.

**A. Create Tables, Views, and Triggers**
This script should be run by the schema owner, `YAHYA_ADMIN`.

1.  **Copy `db.sql` to the container:**
    ```powershell
    docker cp db.sql oracle-19c:/tmp/db.sql
    ```
2.  **Connect as `YAHYA_ADMIN` and run the script:**
    ```powershell
    # The default password is set in config.py
    docker exec -it oracle-19c sqlplus yahya_admin/yahya_admin_password
    ```
3.  Inside SQL*Plus, execute the script:
    ```sql
    @/tmp/db.sql
    ```

**B. Create Users, Roles, and Permissions**
This script **must be run by a DBA user like `SYSTEM`**.

1.  **Stop your Streamlit application if it is running.** This is crucial to release any open connections.
2.  **Copy `security.sql` to the container:**
    ```powershell
    docker cp security.sql oracle-19c:/tmp/security.sql
    ```
3.  **Connect as `SYSTEM` and run the script:**
    ```powershell
    # Use the password you set in the `docker run` command
    docker exec -it oracle-19c sqlplus system/YourSystemPassword
    ```
4.  Inside SQL*Plus, execute the script:
    ```sql
    @/tmp/security.sql
    ```

### Step 4: Seed the Database (Optional)
To populate the application with realistic fake data for testing, run the seed script:
```bash
python seed_data.py
```

### Step 5: Run the Streamlit Application
You are now ready to start the application.
```bash
streamlit run app.py
```
Open your web browser to the local URL provided by Streamlit (usually `http://localhost:8501`).

**Default Logins:**
*   **Admin:** `ADMIN` / `admin`
*   **Professor:** `P2000` / `123`
*   **Student:** `E100000` / `123`
*(More users are available if you run the seed script)*

---

## ✍️ About the Author

Created by Yahya Bouchak, student Master SIIA, module Administration Database Oracle.