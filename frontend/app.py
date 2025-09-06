import os
import uuid
import qrcode
import qrcode.image.svg
from io import BytesIO
import csv
from datetime import datetime
from dotenv import load_dotenv

from flask import Flask, render_template, request, redirect, url_for, flash, send_file, Response, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import desc

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your_super_secret_key_if_not_set_in_env')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///swiftattend.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# --- Models ---
class Event(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    participants = db.relationship('Participant', backref='event', lazy=True, cascade="all, delete-orphan")
    attendances = db.relationship('Attendance', backref='event', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Event {self.name}>'

class Participant(db.Model):
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = db.Column(db.String(36), db.ForeignKey('event.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    student_id = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)

    # A participant can have one attendance record per event
    attendance = db.relationship('Attendance', backref='participant', uselist=False, lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Participant {self.name} - Event {self.event_id}>'

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.String(36), db.ForeignKey('participant.id'), unique=True, nullable=False)
    event_id = db.Column(db.String(36), db.ForeignKey('event.id'), nullable=False)
    check_in_time = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Attendance {self.participant_id} at {self.check_in_time}>'

# --- Database Initialization ---
with app.app_context():
    db.create_all()

# --- Helper Functions ---
def generate_qr_code_svg(data):
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(data, image_factory=factory, box_size=10)
    buffer = BytesIO()
    img.save(buffer)
    buffer.seek(0)
    return buffer.getvalue().decode('utf-8')

def send_registration_email(recipient_email, participant_name, event_name, qr_code_svg):
    """
    Mocks sending an email. In a real application, you'd use Flask-Mail
    or an email service (SendGrid, Mailgun) here.
    """
    print(f"--- MOCK EMAIL SENT ---")
    print(f"To: {recipient_email}")
    print(f"Subject: Your SwiftAttend Registration for {event_name}")
    print(f"Body: Dear {participant_name},\n\nThank you for registering for {event_name}!")
    print(f"Please use the QR code below for check-in.\n\n[QR Code Placeholder Image/SVG would be here]")
    print(f"QR Code Data: {qr_code_svg[:100]}...") # Print first 100 chars of SVG
    print(f"------------------------")
    # Example for Flask-Mail (needs configuration)
    # from flask_mail import Message, Mail
    # mail = Mail(app)
    # msg = Message(
    #     subject=f"Your SwiftAttend Registration for {event_name}",
    #     recipients=[recipient_email],
    #     html=render_template('email/registration_email.html', participant_name=participant_name, event_name=event_name, qr_code_svg=qr_code_svg)
    # )
    # try:
    #     mail.send(msg)
    #     print(f"Email sent successfully to {recipient_email}")
    # except Exception as e:
    #     print(f"Failed to send email to {recipient_email}: {e}")


# --- Routes ---

@app.route('/')
def index():
    events = Event.query.order_by(desc(Event.date)).all()
    return render_template('event_list.html', events=events)

# --- Admin Routes ---
@app.route('/admin')
def admin_dashboard():
    # In a real app, this would require admin login
    return redirect(url_for('admin_events'))

@app.route('/admin/events')
def admin_events():
    events = Event.query.order_by(desc(Event.date)).all()
    return render_template('admin_events.html', events=events)

@app.route('/admin/events/create', methods=['GET', 'POST'])
def create_event():
    if request.method == 'POST':
        name = request.form['name']
        date_str = request.form['date']
        time_str = request.form['time']
        location = request.form['location']
        description = request.form['description']

        try:
            event_datetime = datetime.strptime(f"{date_str} {time_str}", '%Y-%m-%d %H:%M')
        except ValueError:
            flash('Invalid date or time format.', 'danger')
            return render_template('create_event.html', form_data=request.form)

        new_event = Event(name=name, date=event_datetime, location=location, description=description)
        db.session.add(new_event)
        db.session.commit()
        flash('Event created successfully!', 'success')
        return redirect(url_for('admin_events'))
    return render_template('create_event.html')

@app.route('/admin/event/<event_id>')
def event_details(event_id):
    event = Event.query.get_or_404(event_id)
    participants = Participant.query.filter_by(event_id=event.id).all()
    attendance_count = Attendance.query.filter_by(event_id=event.id).count()
    return render_template('event_details.html', event=event, participants=participants, attendance_count=attendance_count)

@app.route('/admin/event/<event_id>/delete', methods=['POST'])
def delete_event(event_id):
    event = Event.query.get_or_404(event_id)
    db.session.delete(event)
    db.session.commit()
    flash(f'Event "{event.name}" and all its related data have been deleted.', 'success')
    return redirect(url_for('admin_events'))

@app.route('/admin/event/<event_id>/qr_code')
def event_qr_code(event_id):
    event = Event.query.get_or_404(event_id)
    # The QR code for event registration should lead to the event's registration page
    registration_url = url_for('register_for_event', event_id=event.id, _external=True)
    qr_svg = generate_qr_code_svg(registration_url)
    return render_template('event_qr_code.html', event=event, qr_svg=qr_svg)

@app.route('/admin/event/<event_id>/download_attendees')
def download_attendees(event_id):
    event = Event.query.get_or_404(event_id)
    participants = db.session.query(Participant, Attendance)\
                           .outerjoin(Attendance, Participant.id == Attendance.participant_id)\
                           .filter(Participant.event_id == event.id)\
                           .all()

    si = BytesIO()
    cw = csv.writer(si)

    headers = ['Participant Name', 'Student ID', 'Email', 'Registration Date', 'Check-in Time']
    cw.writerow(headers)

    for participant, attendance in participants:
        check_in_time = attendance.check_in_time.strftime('%Y-%m-%d %H:%M:%S') if attendance else 'N/A'
        row = [
            participant.name,
            participant.student_id,
            participant.email,
            participant.registration_date.strftime('%Y-%m-%d %H:%M:%S'),
            check_in_time
        ]
        cw.writerow(row)

    output = si.getvalue().decode('utf-8')
    response = Response(output, mimetype='text/csv')
    response.headers['Content-Disposition'] = f'attachment; filename={event.name.replace(" ", "_")}_attendees.csv'
    return response

@app.route('/admin/event/<event_id>/live_attendance')
def live_attendance(event_id):
    event = Event.query.get_or_404(event_id)
    attendance_count = Attendance.query.filter_by(event_id=event.id).count()
    return jsonify({'attendance_count': attendance_count})


# --- Participant Routes ---
@app.route('/event/<event_id>/register', methods=['GET', 'POST'])
def register_for_event(event_id):
    event = Event.query.get_or_404(event_id)
    if request.method == 'POST':
        name = request.form['name']
        student_id = request.form['student_id']
        email = request.form['email']

        # Basic validation
        if not all([name, student_id, email]):
            flash('All fields are required.', 'danger')
            return render_template('register.html', event=event, form_data=request.form)

        # Check if participant already registered for this event with this student ID or email
        existing_participant = Participant.query.filter(
            Participant.event_id == event.id,
            (Participant.student_id == student_id) | (Participant.email == email)
        ).first()

        if existing_participant:
            flash('You are already registered for this event.', 'warning')
            # Redirect to their existing QR code
            return redirect(url_for('show_participant_qr', participant_id=existing_participant.id))

        new_participant = Participant(event_id=event.id, name=name, student_id=student_id, email=email)
        db.session.add(new_participant)
        db.session.commit()

        # Generate unique QR code for the participant's registration ID
        # The QR code data will be the participant's ID
        participant_qr_data = new_participant.id
        qr_svg = generate_qr_code_svg(participant_qr_data)

        # Mock sending email (replace with real email service)
        send_registration_email(email, name, event.name, qr_svg)

        flash('Registration successful! Please save your QR code.', 'success')
        return redirect(url_for('show_participant_qr', participant_id=new_participant.id))

    return render_template('register.html', event=event)

@app.route('/participant/<participant_id>/qr')
def show_participant_qr(participant_id):
    participant = Participant.query.get_or_404(participant_id)
    event = Event.query.get_or_404(participant.event_id)

    # The QR code data is the participant's ID
    qr_data = participant.id
    qr_svg = generate_qr_code_svg(qr_data)

    return render_template('participant_qr.html', participant=participant, event=event, qr_svg=qr_svg)

# --- Staff/Volunteer Check-in Routes ---
@app.route('/checkin/<event_id>')
def checkin_scanner(event_id):
    event = Event.query.get_or_404(event_id)
    return render_template('scan.html', event=event)

@app.route('/api/checkin', methods=['POST'])
def api_checkin():
    data = request.get_json()
    participant_id = data.get('participant_id')
    event_id = data.get('event_id')

    if not participant_id or not event_id:
        return jsonify({'status': 'error', 'message': 'Missing participant ID or event ID'}), 400

    participant = Participant.query.filter_by(id=participant_id, event_id=event_id).first()

    if not participant:
        return jsonify({'status': 'error', 'message': 'Participant not found for this event'}), 404

    # Check if already checked in
    existing_attendance = Attendance.query.filter_by(participant_id=participant.id, event_id=event.id).first()
    if existing_attendance:
        return jsonify({
            'status': 'warning',
            'message': f'{participant.name} (ID: {participant.student_id}) already checked in at {existing_attendance.check_in_time.strftime("%H:%M")}.'
        })

    new_attendance = Attendance(participant_id=participant.id, event_id=event.id)
    db.session.add(new_attendance)
    db.session.commit()

    return jsonify({
        'status': 'success',
        'message': f'Checked in {participant.name} ({participant.student_id}) for {event.name}.',
        'participant_name': participant.name,
        'student_id': participant.student_id
    })

if __name__ == '__main__':
    app.run(debug=True)
