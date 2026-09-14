import io
import hashlib
import pandas as pd
import streamlit as st
from supabase import create_client, Client

# --- SUPABASE DATABASE CONFIGURATION ---
# Safely pull secrets from the Streamlit environment
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "https://your-project-id.supabase.co")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "your-anon-or-service-role-key")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()
TABLE_NAME = "grades"
REQUIRED_COLUMNS = ["student_id", "class", "subject", "period", "semester", "grade", "password_hash"]

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def load_master_records() -> pd.DataFrame:
    """Fetch all rows from the Supabase table."""
    try:
        response = supabase.table(TABLE_NAME).select("*").execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame(columns=["id"] + REQUIRED_COLUMNS)
    except Exception as e:
        st.error(f"Failed to fetch data from Supabase: {e}")
        return pd.DataFrame(columns=["id"] + REQUIRED_COLUMNS)

# --- PAGE INITIALIZATION ---
st.set_page_config(page_title="Academic Records Portal", layout="wide")

st.title("🏫 Academic Records Portal")
st.write("Welcome to the Student and Supabase-Backed Grades Management System.")

tab_student, tab_admin = st.tabs(["🎓 Student Portal", "🔐 Admin Dashboard"])

# --- STUDENT PORTAL ---
with tab_student:
    st.header("Student Grade Inquiry")
    
    student_id = st.text_input("Enter Student ID:", key="stu_id_input").strip()
    student_pass = st.text_input("Enter Password:", type="password", key="stu_pass_input").strip()
    
    if st.button("Access Dashboard"):
        if student_id and student_pass:
            hashed_input = hash_password(student_pass)
            
            # Query Supabase directly for authentication matching
            try:
                response = supabase.table(TABLE_NAME)\
                    .select("*")\
                    .eq("student_id", student_id)\
                    .eq("password_hash", hashed_input)\
                    .execute()
                    
                if response.data:
                    st.success(f"✅ Welcome Back Student: {student_id}")
                    st.session_state[f"authenticated_{student_id}"] = True
                else:
                    st.error("❌ Invalid Student ID or Password.")
            except Exception as e:
                st.error(f"Database query error: {str(e)}")
        else:
            st.warning("⚠️ Both Student ID and Password are required.")

    if f"authenticated_{student_id}" in st.session_state and st.session_state[f"authenticated_{student_id}"]:
        # Pull student specific rows directly from Supabase
        try:
            response = supabase.table(TABLE_NAME).select("*").eq("student_id", student_id).execute()
            student_rows = pd.DataFrame(response.data) if response.data else pd.DataFrame()
        except Exception as e:
            st.error(f"Error pulling records: {str(e)}")
            student_rows = pd.DataFrame()
        
        if not student_rows.empty:
            student_rows['grade'] = pd.to_numeric(student_rows['grade'], errors='coerce')
            
            col1, col2 = st.columns(2)
            with col1:
                semesters = ["All Semesters"] + sorted(student_rows['semester'].dropna().astype(str).unique().tolist())
                selected_semester = st.selectbox("Filter by Semester", semesters)
            with col2:
                periods = ["All Periods"] + sorted(student_rows['period'].dropna().astype(str).unique().tolist())
                selected_period = st.selectbox("Filter by Period", periods)
            
            filtered_df = student_rows.copy()
            if selected_semester != "All Semesters":
                filtered_df = filtered_df[filtered_df['semester'].astype(str) == selected_semester]
            if selected_period != "All Periods":
                filtered_df = filtered_df[filtered_df['period'].astype(str) == selected_period]
                
            st.subheader("📊 Academic Performance Summary")
            metric_col1, metric_col2, metric_col3 = st.columns(3)
            
            current_avg = filtered_df['grade'].mean()
            with metric_col1:
                if pd.isna(current_avg):
                    st.metric(label="Current Filtered Average", value="N/A")
                else:
                    st.metric(label="Current Filtered Average", value=f"{current_avg:.2f}%")
                    
            with metric_col2:
                st.markdown("**Average by Semester**")
                sem_avg = student_rows.groupby('semester')['grade'].mean().reset_index()
                for _, row in sem_avg.iterrows():
                    st.write(f"• **{row['semester']}**: {row['grade']:.2f}%")
                    
            with metric_col3:
                st.markdown("**Average by Period**")
                per_avg = student_rows.groupby('period')['grade'].mean().reset_index()
                for _, row in per_avg.iterrows():
                    st.write(f"• **{row['period']}**: {row['grade']:.2f}%")
            
            st.divider()
            st.subheader("Your Academic Record")
            display_df = filtered_df.drop(columns=['password_hash', 'id'], errors='ignore')
            st.dataframe(display_df, use_container_width=True)
            
            # --- DOWNLOAD CONTROLS ---
            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                csv_buffer = io.StringIO()
                display_df.to_csv(csv_buffer, index=False)
                st.download_button(
                    label="📥 Download Filtered Transcript (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name=f"Transcript_{student_id}.csv",
                    mime="text/csv"
                )
                
            with dl_col2:
                txt_report = [
                    "=========================================",
                    "         OFFICIAL REPORT CARD            ",
                    "=========================================",
                    f"Student ID : {student_id}"
                ]
                if not display_df.empty and 'class' in display_df.columns:
                    txt_report.append(f"Class      : {display_df['class'].iloc[0]}")
                txt_report.append(f"Filters    : {selected_semester} | {selected_period}")
                txt_report.append("-----------------------------------------")
                
                avg_str = f"{current_avg:.2f}%" if not pd.isna(current_avg) else "N/A"
                txt_report.append(f"Overall Filtered Average: {avg_str}")
                txt_report.append("\nSummary by Semester:")
                for _, row in sem_avg.iterrows():
                    txt_report.append(f" - {row['semester']}: {row['grade']:.2f}%")
                txt_report.append("\nSummary by Period:")
                for _, row in per_avg.iterrows():
                    txt_report.append(f" - {row['period']}: {row['grade']:.2f}%")
                    
                txt_report.append("-----------------------------------------")
                txt_report.append(f"{'Subject':<18} | {'Semester':<10} | {'Period':<10} | {'Grade':<5}")
                txt_report.append("-" * 53)
                
                for _, row in display_df.iterrows():
                    txt_report.append(f"{str(row['subject']):<18} | {str(row['semester']):<10} | {str(row['period']):<10} | {str(row['grade']):<5}")
                txt_report.append("=========================================")
                
                txt_content = "\n".join(txt_report)
                st.download_button(
                    label="📄 Download Report Card (TXT)",
                    data=txt_content,
                    file_name=f"ReportCard_{student_id}.txt",
                    mime="text/plain",
                    key="student_txt_download"
                )
        else:
            st.info("No record items found for this student profile.")

# --- ADMIN DASHBOARD ---
with tab_admin:
    st.header("Administrative Access Gate")
    if "admin_authenticated" not in st.session_state:
        st.session_state["admin_authenticated"] = False
        
    if not st.session_state["admin_authenticated"]:
        admin_user = st.text_input("Username:")
        admin_pass = st.text_input("Password:", type="password")
        if st.button("Authenticate Admin"):
            if admin_user == "admin" and admin_pass == "password123":
                st.session_state["admin_authenticated"] = True
                st.rerun()
            else:
                st.error("❌ Invalid Admin Username or Password.")
    else:
        st.success("✅ Admin Authentication Successful. Live database loaded below.")
        if st.button("🚪 Logout Admin Panel"):
            st.session_state["admin_authenticated"] = False
            st.rerun()
            
        st.divider()
        st.subheader("Bulk Record Upload")
        uploaded_file = st.file_uploader("Upload grades update file (.csv)", type=["csv"])
        
        if uploaded_file is not None:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                # Align columns to table naming structure
                if "student_id" not in uploaded_df.columns and "id" in uploaded_df.columns:
                    uploaded_df = uploaded_df.rename(columns={"id": "student_id"})
                
                uploaded_df.columns = [c.strip().lower() for c in uploaded_df.columns]
                missing = [col for col in REQUIRED_COLUMNS if col not in uploaded_df.columns and col != "password_hash"]
                
                if missing:
                    st.error(f"❌ Upload Rejected. Missing target columns: {', '.join(missing)}")
                else:
                    # Provide default hashes if missing from file
                    if "password_hash" not in uploaded_df.columns:
                        uploaded_df["password_hash"] = uploaded_df["student_id"].apply(lambda x: hash_password(str(x)))
                    
                    records_to_insert = uploaded_df[REQUIRED_COLUMNS].to_dict(orient="records")
                    # Bulk insert into Supabase
                    supabase.table(TABLE_NAME).insert(records_to_insert).execute()
                    st.toast(f"🎉 Success! Uploaded and stored records in Supabase.", icon="🔥")
            except Exception as e:
                st.error(f"❌ Engine parsing error: {str(e)}")
                
        st.subheader("📝 Live Master Records Editor")
        st.caption("Double-click any cell to edit data, insert rows, or delete records. Remember to save changes below.")
        
        master_df = load_master_records()
        
        if not master_df.empty:
            edited_df = st.data_editor(
                master_df, 
                use_container_width=True, 
                num_rows="dynamic",
                key="admin_records_editor"
            )
            
            admin_col1, admin_col2 = st.columns(2)
            
            with admin_col1:
                if st.button("💾 Save Table Changes"):
                    try:
                        for index, row in edited_df.iterrows():
                            # Fix empty password hashes
                            p_hash = row.get('password_hash')
                            if pd.isna(p_hash) or str(p_hash).strip() == "":
                                p_hash = hash_password(str(row['student_id']))
                            
                            record_data = {
                                "student_id": str(row['student_id']),
                                "class": str(row['class']),
                                "subject": str(row['subject']),
                                "period": str(row['period']),
                                "semester": str(row['semester']),
                                "grade": float(row['grade']) if not pd.isna(row['grade']) else None,
                                "password_hash": p_hash
                            }
                            
                            # Upsert record back into Supabase based on ID primary key
                            if 'id' in row and not pd.isna(row['id']):
                                supabase.table(TABLE_NAME).upsert({"id": int(row['id']), **record_data}).execute()
                            else:
                                supabase.table(TABLE_NAME).insert(record_data).execute()
                        
                        st.success("🎉 Database saved successfully to Supabase!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error saving to database: {str(e)}")
            
            with admin_col2:
                admin_csv_buffer = io.StringIO()
                master_df.to_csv(admin_csv_buffer, index=False)
                
                st.download_button(
                    label="📥 Download Master Database (CSV)",
                    data=admin_csv_buffer.getvalue(),
                    file_name="master_grades_database.csv",
                    mime="text/csv",
                    key="admin_download_btn"
                )
