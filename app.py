from flask import Flask, render_template, request, redirect, url_for, flash, session
import requests
import json
import base64
import mimetypes
import os
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from functools import wraps

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'default-dev-key-change-in-production')

# Authentication credentials from env
AUTH_USERNAME = os.getenv('AUTH_USERNAME', 'admin')
AUTH_PASSWORD = os.getenv('AUTH_PASSWORD', 'password')

# Google Apps Script URL from env
API_URL = os.getenv('API_URL', 'https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec')
API_PASSWORD = os.getenv('API_PASSWORD', 'mySecurePassword123')

# Configure upload folder for attachments
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please log in to access this page', 'danger')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('email_form'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == AUTH_USERNAME and password == AUTH_PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful', 'success')
            return redirect(url_for('email_form'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/email', methods=['GET', 'POST'])
@login_required
def email_form():
    if request.method == 'POST':
        # Get form data
        to_address = request.form.get('to')
        subject = request.form.get('subject')
        html_body = request.form.get('body')
        from_name = request.form.get('from_name')
        
        # Validate required fields
        if not to_address or not subject or not html_body:
            flash('Please fill out all required fields', 'danger')
            return redirect(url_for('email_form'))
        
        # Process attachments
        attachment_data = []
        files = request.files.getlist('attachments')
        
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                try:
                    mime_type = file.content_type or mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
                    
                    with open(file_path, 'rb') as f:
                        file_data = f.read()
                        base64_data = base64.b64encode(file_data).decode('utf-8')
                        
                    attachment_data.append({
                        'fileName': filename,
                        'mimeType': mime_type,
                        'data': base64_data
                    })
                    
                    # Clean up the temp file
                    if os.path.exists(file_path):
                        os.remove(file_path)
                except Exception as e:
                    flash(f'Error processing attachment {filename}: {str(e)}', 'danger')
                    return redirect(url_for('email_form'))
        
        # Create payload
        payload = {
            'password': API_PASSWORD,
            'to': to_address,
            'subject': subject,
            'htmlBody': html_body,
            'fromName': from_name,
            'attachments': attachment_data
        }
        
        # Send the request
        try:
            response = requests.post(
                API_URL,
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            result = response.json()
            if result.get('status') == 'success':
                flash('Email sent successfully!', 'success')
                return redirect(url_for('email_form'))
            else:
                error_message = result.get('message', 'Unknown error')
                flash(f'Failed to send email: {error_message}', 'danger')
        except Exception as e:
            flash(f'Failed to send email: {str(e)}', 'danger')
        
    return render_template('email_form.html')

if __name__ == '__main__':
    app.run(debug=True)