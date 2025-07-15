from flask import Flask, request, render_template, jsonify , redirect , flash, url_for ,session
import os
import smtplib
import fitz  # PyMuPDF
import google.generativeai as genai
import mysql.connector

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
EMAIL_ADDRESS = "sandeeprajeti9787@gmail.com"
EMAIL_PASSWORD = "przn lyyt nmzj kikk" 
app = Flask(__name__)
app.secret_key = 'supersecretkey123'
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ✅ Configure Gemini API
genai.configure(api_key="AIzaSyAMYBfhw23Pm9P7mQIH0-UHwQpJIAh4Aa0")
model = genai.GenerativeModel('gemini-2.0-flash')

db = mysql.connector.connect(
    host="bjz4x4ymkcqgfacnl7gw-mysql.services.clever-cloud.com",
    user="uqrwwpy0fkon2tdk",
    password="uqrwwpy0fkon2tdk",
    database="bjz4x4ymkcqgfacnl7gw",
    port=3306
)
cursor = db.cursor(dictionary=True)

# ✅ Home (Login/Register Page)
@app.route('/', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone_number']
        password = request.form['password']  # 🚫 No hashing

        try:
            cursor.execute("INSERT INTO users (name, email, phone_number, password) VALUES (%s, %s, %s, %s)",
                           (name, email, phone, password))
            db.commit()
            flash("✅ Registered successfully! You can now log in.", "success")
            return redirect(url_for('register'))
        except mysql.connector.IntegrityError:
            flash("❌ Email already exists. Please login.", "error")

    return render_template('login-register.html')

# ✅ Login Route
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    cursor.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, password))
    user = cursor.fetchone()

    if user:
        flash("✅ Login successful!", "success")
        session['user_email'] = email
        return redirect('/main-page')  # Or redirect to dashboard/interview page
    else:
        flash("❌ Invalid email or password.", "error")
        return redirect('/')

#Forgot Password Route
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        new_password = request.form['new_password']

        # ✅ Update password in the database (assuming plain text)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user:
            cursor.execute("UPDATE users SET password = %s WHERE email = %s", (new_password, email))
            db.commit()
            flash("✅ Password reset successful!", "success")
            return redirect('/')
        else:
            flash("❌ Email not found. Please register first.", "error")
            return redirect('/forgot_password')

    # GET request: show the forgot password form
    return render_template('forgot-password.html')




#Home page
@app.route('/main-page', methods=['GET'])
def home():
    return render_template('main-page.html')

#Resume upload page
@app.route('/upload', methods=['GET'])
def upload_page():
    return render_template('DashBoard.html')

#Interview start route
@app.route('/interview', methods=['POST'])
def interview():
    name = request.form['name']
    job = request.form['job']
    resume = request.files['resume']

    # Save uploaded resume
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    resume_path = os.path.join(UPLOAD_FOLDER, resume.filename)
    resume.save(resume_path)

    # Extract resume text using PyMuPDF
    text = extract_text_from_pdf(resume_path)

    # ✅ Predefined first question
    question = "Introduce yourself, and tell me your strengths and weaknesses."

    return render_template(
        'interview.html',
        name=name,
        question=question,
        job=job,
        resume=text
    )

@app.route('/contact', methods=['POST'])
def contact():
    name = request.form.get('name')
    email = request.form.get('email')
    message = request.form.get('message')
    skills = request.form.get('skills')

    insert_query = "INSERT INTO project (name, email, message, skills) VALUES (%s, %s, %s, %s)"
    cursor.execute(insert_query, (name, email, message, skills))
    
    db.commit()  # ✅ THIS should be on `conn`, NOT `cursor`

    flash("✅ Your message has been received.", "success")
    return redirect('/main-page')


@app.route('/next_question', methods=['POST'])
def next_question():
    data = request.get_json()
    user_answer = data.get('answer')
    job = data.get('job')
    resume_text = data.get('resume')

    # 🔐 Store resume & job in session (if not already)
    session['job'] = job
    session['resume_text'] = resume_text

    # ✅ Store all answers for feedback
    if 'answers' not in session:
        session['answers'] = []
    session['answers'].append(user_answer)

    # 📜 Gemini prompt
    prompt = f"""
You are an AI interviewer. The user has applied for a {job} role.

Here is their resume content:
{resume_text}

These are the answers given by the candidate so far:
{session['answers']}

Based on the above, ask the next technical interview question.
"""

    try:
        response = model.generate_content(prompt)
        next_question = response.text.strip()
    except Exception:
        next_question = "Can you explain more about your experience?"

    return jsonify({'question': next_question})

# ✅ Extract text from PDF using PyMuPDF
def extract_text_from_pdf(pdf_path):
    text = ""
    doc = fitz.open(pdf_path)
    for page in doc:
        text += page.get_text()
    return text
@app.route('/generate_feedback')
def generate_feedback():
    resume_text = session.get('resume_text', '')
    job = session.get('job', '')
    answers = session.get('answers', [])
    user_email = session.get('user_email', 'unknown@example.com')

    if not answers:
        return jsonify({'success': False, 'error': 'No answers to generate feedback from.'}), 400

    prompt = f"""
    You are an expert AI interviewer.

    The candidate has applied for a {job} role.

    Their resume content:
    {resume_text}

    Answers they provided during the interview:
    {answers}

    Please give a structured and professional feedback about:
    - Strengths observed
    - Areas for improvement
    - Communication skills
    - Technical ability

    Keep the tone helpful and clear.
    """

    try:
        response = model.generate_content(prompt)
        feedback = response.text.strip()

        send_email_feedback(user_email, feedback)  # ✅ Send feedback email
        return jsonify({'success': True, 'message': 'Feedback sent'})
    except Exception as e:
        print("❌ Feedback generation error:", e)
        return jsonify({'success': False, 'error': str(e)}), 500

def send_email_feedback(to_email, feedback_text):
    subject = "Your AI Interview Feedback"
    sender = EMAIL_ADDRESS
    receiver = to_email

    msg = MIMEMultipart()
    msg['From'] = sender
    msg['To'] = receiver
    msg['Subject'] = subject

    msg.attach(MIMEText(feedback_text, 'plain'))

    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        print("✅ Feedback email sent!")
    except Exception as e:
        print("❌ Email error:", e)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')


