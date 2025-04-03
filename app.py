from flask import Flask, render_template, request, redirect, url_for, session
import pymysql
import pandas as pd
import os
import datetime
import random
from werkzeug.utils import secure_filename
from pdfminer.high_level import extract_text
import spacy
import Courses

app = Flask(__name__)
app.secret_key = "secret_key"

# Load spaCy model for Named Entity Recognition (NER)
nlp = spacy.load("en_core_web_sm")

# Database connection
db = pymysql.connect(host="localhost", user="root", password="root", database="sra")
cursor = db.cursor()

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Predefined skill keywords
SKILL_KEYWORDS = {
    "python", "machine learning", "deep learning", "flask", "django",
    "react", "nodejs", "android", "kotlin", "swift", "figma", "adobe xd"
}

def save_uploaded_file(file):
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)
    return filepath

def extract_resume_text(filepath):
    """Extract raw text from PDF using pdfminer.six"""
    return extract_text(filepath)

def extract_entities(text):
    """Extract structured info using spaCy"""
    doc = nlp(text)
    entities = {
        "name": None,
        "email": None,
        "skills": []
    }
    
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            entities["name"] = ent.text
        elif ent.label_ == "EMAIL":
            entities["email"] = ent.text

    return entities

def extract_skills(text):
    """Extract skills based on predefined keywords"""
    words = text.lower().split()
    return [skill for skill in SKILL_KEYWORDS if skill in words]

def analyze_resume(filepath):
    """Analyze the resume for key details and suggest courses"""
    text = extract_resume_text(filepath)
    entities = extract_entities(text)
    skills = extract_skills(text)

    recommended_skills, reco_field, courses = [], "", []

    categories = {
        "Data Science": (["python", "machine learning", "deep learning"], Courses.ds_course),
        "Web Development": (["flask", "django", "react", "nodejs"], Courses.web_course),
        "Android Development": (["android", "kotlin"], Courses.android_course),
        "iOS Development": (["swift"], Courses.ios_course),
        "UI/UX": (["figma", "adobe xd"], Courses.uiux_course),
    }

    for category, (keywords, courses_list) in categories.items():
        if any(skill in keywords for skill in skills):
            reco_field = category
            recommended_skills = keywords
            courses = random.sample(courses_list, 3)
            break

    return {
        "name": entities.get("name", "Unknown"),
        "email": entities.get("email", "Unknown"),
        "skills": skills
    }, text, reco_field, recommended_skills, courses

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        file = request.files["resume"]
        if file:
            filepath = save_uploaded_file(file)
            resume_data, text, reco_field, recommended_skills, courses = analyze_resume(filepath)

            cursor.execute(
                "INSERT INTO user_data (Name, Email_ID, resume_score, Timestamp, Page_no, Predicted_Field, "
                "User_level, Actual_skills, Recommended_skills, Recommended_courses) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    resume_data["name"],
                    resume_data["email"],
                    80,  
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    1,  # Assuming single-page resume
                    reco_field,
                    "Intermediate",
                    ", ".join(resume_data["skills"]),
                    ", ".join(recommended_skills),
                    ", ".join([course[0] for course in courses]),
                ),
            )
            db.commit()

            return render_template(
                "result.html",
                resume=resume_data,
                text=text,
                reco_field=reco_field,
                recommended_skills=recommended_skills,
                courses=courses,
            )

    return render_template("index.html")

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == "admin" and password == "password":
            session["admin"] = True
            return redirect(url_for("dashboard"))

    return render_template("admin_login.html")

@app.route("/dashboard")
def dashboard():
    if "admin" not in session:
        return redirect(url_for("admin"))

    cursor.execute("SELECT * FROM user_data")
    users = cursor.fetchall()
    df = pd.DataFrame(users, columns=["ID", "Name", "Email", "Resume Score", "Timestamp", "Pages", "Predicted Field", "Level", "Skills", "Recommended Skills", "Courses"])

    return render_template("dashboard.html", tables=[df.to_html(classes="table")], titles=df.columns.values, now=datetime.datetime.now())

@app.route("/logout")
def logout():
    session.pop("admin", None)
    return redirect(url_for("admin"))

if __name__ == "__main__":
    print("Flask is running at: http://127.0.0.1:5000/")  
    app.run(debug=True)