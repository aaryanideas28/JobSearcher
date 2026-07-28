from fastapi.testclient import TestClient
from src.api.main import app
import io

def main():
    client = TestClient(app)
    
    # 1. Create intake profile
    profile_response = client.post("/api/v1/intake/profile", json={
        "email": "test_wf@example.com",
        "full_name": "Test WF User",
        "target_role": "Software Engineer",
        "skills_to_highlight": ["Python", "FastAPI"],
        "preferred_locations": ["Remote"],
        "experience_level": "mid"
    })
    profile_data = profile_response.json()
    pref_id = profile_data.get("candidate_preference_id")
    print("Profile Response Status:", profile_response.status_code)
    print("Candidate Preference ID:", pref_id)
    
    # 2. Upload file to get IDs
    file_content = b"Resume of Test WF User. Experience in Python and FastAPI."
    file_like = io.BytesIO(file_content)
    upload_response = client.post(
        "/api/v1/resume/upload-file",
        files={"file": ("resume.txt", file_like, "text/plain")},
        data={
            "user_email": "test_wf@example.com",
            "full_name": "Test WF User",
            "version_label": "dashboard"
        }
    )
    print("Upload Response Status:", upload_response.status_code)
    upload_data = upload_response.json()
    resume_id = upload_data.get("resume_version_id")
    job_targets = upload_data.get("job_targets", [])
    if not job_targets:
        print("No job targets discovered!")
        return
        
    job_id = job_targets[0].get("job_id")
    print(f"Running workflow with resume_version_id={resume_id}, job_target_id={job_id}, candidate_preference_id={pref_id}...")
    
    # 3. Call workflow
    try:
        response = client.post("/api/v1/workflow/manual-optimize-draft", json={
            "resume_version_id": resume_id,
            "job_target_id": job_id,
            "recipient_email": "recruiter@example.com",
            "candidate_preference_id": pref_id
        })
        print("Workflow Response Status:", response.status_code)
        print("Workflow Response Text:", response.text[:2000])
    except Exception as e:
        import traceback
        print("Exception in workflow call:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
