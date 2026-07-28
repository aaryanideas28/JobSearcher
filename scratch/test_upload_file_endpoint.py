from fastapi.testclient import TestClient
from src.api.main import app
import io

def main():
    client = TestClient(app)
    
    # First create a profile
    profile_response = client.post("/api/v1/intake/profile", json={
        "email": "test_user2@example.com",
        "full_name": "Test User 2",
        "target_role": "Software Engineer",
        "skills_to_highlight": ["Python", "FastAPI"],
        "preferred_locations": ["Remote"],
        "experience_level": "mid"
    })
    print("Profile Response Status:", profile_response.status_code)
    
    # Create a mock text file
    file_content = b"Resume of Test User 2. Experence in Python and FastAPI."
    file_like = io.BytesIO(file_content)
    
    print("Sending resume file upload request...")
    try:
        response = client.post(
            "/api/v1/resume/upload-file",
            files={"file": ("resume.txt", file_like, "text/plain")},
            data={
                "user_email": "test_user2@example.com",
                "full_name": "Test User 2",
                "version_label": "dashboard"
            }
        )
        print("Upload Response Status:", response.status_code)
        print("Upload Response Text/JSON:", response.text)
    except Exception as e:
        import traceback
        print("Exception occurred:")
        traceback.print_exc()

if __name__ == "__main__":
    main()
