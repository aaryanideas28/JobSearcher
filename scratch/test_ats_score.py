import asyncio
from src.agents.ats_engine import ATSEngine
from src.agents.optimizer import ResumeOptimizer

import pytest

@pytest.mark.asyncio
async def test_ats():
    engine = ATSEngine()
    optimizer = ResumeOptimizer()
    
    jenil_resume_raw = """Jenil Shah
jenil.shah6730@gmail.com | LinkedIn: jenil-shah | GitHub: jenil0108
Leetcode | Codeforces | Codechef

EDUCATION
SVKM's Dwarkadas Jivanlal Sanghvi College of Engineering | May 2026
Computer Science and Engineering: Data Sciences | CGPA: 8.6

ACHIEVEMENTS
- Candidate Master - Codeforces (Max Rating 2015) | Top 0.15% in India Among 100k+ (AIR 129)
- 5 Star - Codechef | Top 0.5% Among 200K+ Active Users
- AIR 2 and Global Rank 58 | With an International Grandmaster Performance in Educational Codeforces Round 158 (Div 2)
- Rank 615 in Meta Hacker Cup 2024
- Rank 57 in TCS Codevita 12
- Winner at Algorythmia, CordeSpree and 10+ CP Contests in India.

PROJECTS
Movie QA | Python, Langchain, Selenium, Faiss | Jun 2024
- Implemented a question-answering system using a Retrieval-Augmented Generation model with Gemini.
- Built a robust web scraping bot using Selenium to efficiently extract movie reviews from IMDB, reducing the time of extraction by 20%.
- Utilized state-of-the-art embedding models from Google AI to represent text data for improved question-answering capabilities.

Catalyst: Chemistry Edutainment Website | ReactJS, Flask, Deeplmer, Transformers | May 2024
- Feature-rich Website, offering 4 engaging features such as compound lookup, AI quiz generation, duels, and compound drawing flashcards.
- Engineered robust Flask APIs to facilitate every feature of the platform.
- Implemented the AI quiz generation functionality and the chemical compound recognition using Deeplmer - a powerful Pretrained Model with 96% Accuracy.

EXTRACURRICULARS
Codestars | Vice Chairperson | Nov 2023-Present
- Constructed problem statements for and Organized 4 Competitive Programming Events, including the Largest Competition in Mumbai in 2024.
- Facilitated post-contest discussions after every contest on discord and Youtube , with 2k+ views, and taking live lectures, enhancing their coding comprehension and problem-solving skills.

SKILLS
Languages: C/C++, Python, Java, JavaScript, HTML/CSS
Tools: MySQL, VS Code, Jupyter Notebook, Git/Github
Libraries: Pandas, NumPy, Tkinter, ScikitLearn, Tensorflow, Pytorch, Langchain, MLX, Selenium, Flask"""

    jd = """Seeking a Data Science and Python AI Engineer with experience in Python, PyTorch, Langchain, Flask, MySQL, Git, and RAG systems."""

    opt_result = await optimizer.optimize_resume(
        jenil_resume_raw, 
        jd, 
        skills_to_highlight=["Python", "PyTorch", "Langchain", "Flask", "MySQL", "Git"],
        target_role="AI & Data Science Engineer"
    )
    
    print("OPTIMIZED RESUME TEXT:\n")
    print(opt_result.optimized_resume)
    print("\n" + "="*50 + "\n")
    
    score = await engine.combined_score(opt_result.optimized_resume, jd)
    print(f"ATS MATCH SCORE: {round(score.score * 100)}% ({score.score})")
    print(f"Resume Length: {len(opt_result.optimized_resume)} characters")
    print(f"Missing Keywords: {score.details.get('missing_keywords', [])}")

asyncio.run(test_ats())
