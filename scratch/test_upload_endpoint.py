from fastapi.testclient import TestClient
from src.api.main import app

def main():
    client = TestClient(app)
    
    # First create a profile
    profile_response = client.post("/api/v1/intake/profile", json={
        "email": "test_user@example.com",
        "full_name": "Test User",
        "target_role": "Software Engineer",
        "skills_to_highlight": ["Python", "FastAPI"],
        "preferred_locations": ["Remote"],
        "experience_level": "mid"
    })
    print("Profile Response Status:", profile_response.status_code)
    print("Profile Response JSON:", profile_response.json())
    
    # Now upload the resume
    print("Sending resume upload request...")
    try:
        response = client.post("/api/v1/resume/upload", json={
            "user_email": "test_user@example.com",
            "full_name": "Test User",
            "resume_text": "Resume text of Test User. Python developer.",
            "version_label": "original",
            "metadata": {}
        })
        print("Upload Response Status:", response.status_code)
        print("Upload Response Text:", response.text)
    except Exception as e:
        import traceback
        print("Exception occurred:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
