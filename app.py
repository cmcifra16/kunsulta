from asyncio.windows_events import NULL
from flask import Flask, render_template, url_for, request, redirect, session, flash, abort
import firebase_admin
from firebase_admin import credentials, firestore
import pyrebase
import pickle
import numpy as np
import uuid
import os
import pathlib
import requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from pip._vendor import cachecontrol
import google.auth.transport.requests


# date time asia manila
from datetime import datetime   
import pytz
datenow = datetime.now(pytz.timezone('Asia/Manila'))
todayDate = datenow.strftime("%Y-%m-%d")


# Load the Random Forest CLassifier model
my_dir = os.path.dirname(__file__)
pickle_file_path = os.path.join(my_dir, 'covid.pkl')
dokconsulta_file_path = os.path.join(my_dir, 'dokconsulta.json')
classifier = pickle.load(open(pickle_file_path, 'rb'))
app = Flask(__name__)
app.secret_key = 'sectretke7289191'


# google auth
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" 
GOOGLE_CLIENT_ID = '910804857480-836u1sr0u220loknk41eful9hm1n07i1.apps.googleusercontent.com'
client_secrets_file = os.path.join(pathlib.Path(__file__).parent, "client_secret.json") #set the path to where the .json file you got Google console is
flow = Flow.from_client_secrets_file(  #Flow is OAuth 2.0 a class that stores all the information on how we want to authorize our users
    client_secrets_file=client_secrets_file,
    scopes=["https://www.googleapis.com/auth/userinfo.profile", "https://www.googleapis.com/auth/userinfo.email", "openid"],  #here we are specifing what do we get after the authorization
    redirect_uri="http://127.0.0.1:5000/login/google/authorize"  #and the redirect URI is the point where the user will end up after the authorization
)


# firebase setup
# Use a service account
cred = credentials.Certificate(dokconsulta_file_path)
firebase_admin.initialize_app(cred)
db = firestore.client()
firebaseConfig = {
  'apiKey': "AIzaSyDGer2NBn6Tj9uF7ut9vPeoOCsWyt5Ufug",
  'authDomain': "dokonsulta-6ce1b.firebaseapp.com",
  'databaseURL': 'https://dokonsulta-6ce1b-default-rtdb.firebaseio.com',
  'projectId': "dokonsulta-6ce1b",
  'storageBucket': "dokonsulta-6ce1b.appspot.com",
  'messagingSenderId': "513490090153",
  'appId': "1:513490090153:web:f8815aacad94ad3c3bd1b8",
  'measurementId': "G-D74HESHHW8"
}
firebase = pyrebase.initialize_app(firebaseConfig)
storage = firebase.storage()
auth = firebase.auth()


# FUNCTIONS
def age(year,month,day):
    today = datetime.today()
    age = today.year - int(year) - ((today.month, today.day) < (int(month), int(day)))
    return age

def login_is_required(function):  #a function to check if the user is authorized or not
    def wrapper(*args, **kwargs):
        if "user" not in session:  #authorization required
            return abort(401)
        else:
            return function()
    return wrapper


#-MAIN PAGES--------------------------------------------------------------------------------------------------------------------------
# Main Dashboard
# Also use in Patients and Doctors Dashboard
@app.route('/', methods=['GET'])
def home_page():
    if 'user' not in session:
        page = [pages.to_dict() for pages in db.collection(u'page').stream()]
       
        docs = [doc.to_dict() for doc in db.collection(u'doctor').stream()]
        return render_template('index.html',page=page,docs =docs)
    else:
        return redirect('/logout')

# Main ABOUT US 
# Use in all accounts
@app.route('/about', methods=['GET'])
def about():
    if 'user' not in session:
        page = [pages.to_dict() for pages in db.collection(u'page').stream()]
        return render_template('About.html', page=page)

# Main Rooms and Services
@app.route('/rooms-services', methods=['GET'])
def roomsServices():
    services =[servicess.to_dict() for servicess in db.collection(u'services').stream()]
    return render_template('rooms_services.html',services=services)

# Main login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'user' not in session:
            return render_template('login.html')
        else:
            return redirect('/logout')
    elif request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        # check e-mail,pass
        flag_4 = False
        # check pass
        try:
            patient_user = auth.sign_in_with_email_and_password(
                email, password)
            # print(teacher_user) # get back details
            # e-mail verification check
            acc_info = auth.get_account_info(patient_user['idToken'])
            if acc_info['users'][0]['emailVerified'] == False:
                flag_4 = True
        except:
            flag_3 = False
        if flag_4 == False:
            flash(
                'Incorrect, unverified or non-existent e-mail or password...', 'error')
            return redirect('/login')
        doc_ref = db.collection(u'patient').document(email)
        doc = doc_ref.get()
        if doc.exists:
            session['acc'] = patient_user
            session['pass'] = password
            session['user'] = email
            session['person_type'] = 'patient'
            return redirect('/patient/appointments')
        else:
            session['acc'] = patient_user
            session['pass'] = password
            session['user'] = email
            session['person_type'] = 'doctor'
            return redirect('/doctor/dashboard')

# Main Patient create account
@app.route('/patient_signup', methods=['GET', 'POST'])
def patient_signup():
    if request.method == 'GET':
        if 'user' not in session:
            return render_template('signup.html')
        else:
            return redirect('/logout')
    elif request.method == 'POST':
        fname = request.form['fname']
        lname = request.form['lname']
        email = request.form['email']
        password = request.form['password']
        password2 = request.form['password2']
        # check if passwords match
        if password != password2:
            flash('The passwords do not match...', 'error')
            return redirect('/patient_signup')
        # check length of pass
        if len(password) < 6:
            flash('The password has to be more than 5 characters long...', 'error')
            return redirect('/patient_signup')
        # auth user
        try:
            patient_user = auth.create_user_with_email_and_password(
                email, password)
        except:
            flash(
                'This e-mail has already been registered. Please use another e-mail...', 'error')
            return redirect('/patient_signup')
        # e-mail verification
        auth.send_email_verification(patient_user['idToken'])
        # add patient to db
        # db.collection('patient').document(patient['localId']).set({
        db.collection('patient').document(email).set({
            'firstName':  fname.lower(),
            'lastName': lname.lower(),
            'middleName': " ",
            'contact':" ",
            'profile':"{{ url_for('static', filename='images/avatar.png') }}",
            'email':email,
            'gender':"",
            'birthDate': "",
            'password': password,
            'created_at': datenow,
            'updated_at':datenow,
        })
        # check for div
        flash('Registration successful! ', 'info')
        return redirect('/login')

# Google login route
@app.route('/login/google')
def google_login():
    authorization_url,state = flow.authorization_url()
    session['state'] = state
    return redirect(authorization_url)

# Google authorize route
@app.route('/login/google/authorize')
def google_authorize():
    flow.fetch_token(authorization_response=request.url)
    # if not session["state"] == request.args["state"]:
    #     abort(500)  #state does not match!
    credentials = flow.credentials
    request_session = requests.session()
    cached_session = cachecontrol.CacheControl(request_session)
    token_request = google.auth.transport.requests.Request(session=cached_session)
    id_info = id_token.verify_oauth2_token(
        id_token=credentials._id_token,
        request=token_request,
        audience=GOOGLE_CLIENT_ID
    )
    print("id_info : ",id_info)
    session['user'] = id_info.get("email")
    session['person_type'] = 'patient'
    return redirect(url_for('appointment_page', isGoole=True , userInfo=id_info))

# PATIENTS ACCOUNT---------------------------------------------------------------------------------------------------------------------------
# START PATIENTS CREATE APPOINTMENT STEPS----------------------------------------------------------------------------------------------------------------
# 1st step Select Doctor / Book appointment button
# renders html
@app.route('/patient/book', methods=['GET', 'POST'])
def book():
    if request.method == "GET":
        if 'user' in session and session['person_type'] == 'patient':
            if request.args:
                doctorSpecialty = request.args['doctorSpecialty']
                triageid = request.args['triageid']
                patient_details = db.collection(
                    'patient').document(session['user']).get()
                docs = [doc.to_dict() for doc in db.collection(u'doctor').where(u'specialty',u'==',doctorSpecialty).stream()]
                return render_template('Patients/book_appointment.html', patient_details=patient_details.to_dict(),docs=docs,triageid=triageid) 
            else:
                patient_details = db.collection(
                'patient').document(session['user']).get()
                docs = [doc.to_dict() for doc in db.collection(u'doctor').stream()]
                return render_template('Patients/book_appointment.html', patient_details=patient_details.to_dict(), docs=docs,triageid="")  
        else:
            return redirect('/logout')
    if request.method == "POST":
        doctorSpecialty = request.form.get("doctorSpecialty")
        if 'user' in session and session['person_type'] == 'patient':
            patient_details = db.collection(
                'patient').document(session['user']).get()
            docs = [doc.to_dict() for doc in db.collection(u'doctor').stream()]
            return render_template('Patients/book_appointment.html', patient_details=patient_details.to_dict(), docs=docs)
        else:
            return redirect('/logout')

# Patients Book Appointment Triage 
# 2nd step fill up triage survey
# renders html
@app.route('/patient/book/triage', methods=['GET', 'POST'])
def bookAppointmentTriage():
    doctorEmail = request.form.get("docemail")
    triageid = request.form.get("triageid")
    if 'user' in session and session['person_type'] == 'patient':
        patient_details = db.collection(
            'patient').document(session['user']).get()
        doc= db.collection(u'doctor').document(doctorEmail).get()
        if triageid:
            triage = db.collection(
                'triage').document(triageid).get()
            return render_template('Patients/book_apointment_create.html',triage=triage.to_dict(),triageid=triageid, patient_details=patient_details.to_dict(), doc=doc.to_dict())
        else:
            return render_template('Patients/book_apointment_triage.html', patient_details=patient_details.to_dict(), doctorEmail=doctorEmail)        
    else:
        return redirect('/logout')

#Patients Book Appointment Triage
# 3rd step fill up triage survey, insert to firebase then
# redirect bookAppointmentTriageResult(triageid, error, patientage)
# with parameters triageid, error, patientage
# renders functions
@app.route('/patientsBookAppointmentTriage', methods=['POST'])
def patientsBookAppointmentTriage():
    if request.method == "POST":
        if 'user' in session and session['person_type'] == 'patient':
            print('session-user',session['user'])
            fname = request.form['fname']
            mname = request.form['mname']
            lname = request.form['lname']
            mnth = str(request.form['month'])
            dy = str(request.form['day'])
            yr = str(request.form['year'])
            date_of_birth = mnth+"/"+dy+"/"+yr
            gender = request.form['gender']
            travelHistory = request.form['travelHistory']
            travelWhen = request.form['travelWhen']
            travelWhere = request.form['travelWhere']
            knowCovidInfected = request.form['knowCovidInfected']
            Vaccinated = request.form['Vaccinated']
            fever = request.form.get('fever')
            cold = request.form.get('cold')
            headache = request.form.get('headache')
            tired = request.form.get('tired')
            taste = request.form.get('taste')
            cough = request.form.get('cough')
            sorethroat = request.form.get('sorethroat')
            diarrhea = request.form.get('diarrhea')
            shortbreath = request.form.get('shortbreath')
            smell = request.form.get('smell')
            patientAge = age(yr,mnth,dy)
            if knowCovidInfected == 'Yes':
                knowCovidInfected='contact with covid'+', '
            else:
                knowCovidInfected='' 
            if fever:
                fever = 'Fever'+','
                fvr =1
            else:
                fever = ''
                fvr =0
            if cold:
                cold = 'Cold'+','
            else:
                cold = ''
                
            if headache:
                headache = 'Headache'+', '
                hd =1
            else:
                headache = ''
                hd =0
            if tired:
                tired = 'Tired'+','
            else:
                tired = ''
            if taste:
                taste = 'No sense of taste'+', '
            else:
                taste = ''
            if cough:
                cough = 'Cough'
                cf =1
            else:
                cough = ''
                cf =0
            if sorethroat:
                sorethroat = 'Sorethroat'+', '
                st =1
            else:
                sorethroat = ''
                st =0
            if diarrhea:
                diarrhea = 'Diarrhea'+', '
            else:
                diarrhea = ''
            if shortbreath:
                shortbreath = 'shortness of breath'+', '
                sb =1
            else:
                shortbreath = ''
                sb =0
            if smell:
                smell = ' NO sense of Smell'+', '
            else:
                smell = ' '
            data = np.array([[cf,fvr,st,sb,hd]])
            my_prediction = classifier.predict(data)
            if my_prediction == 1:
                result = 'high risk'
            elif my_prediction == 0:
                result = 'low risk'
            data = {
                'date': datenow.strftime("%Y-%m-%d"),
                'gender': gender.lower(),
                'firstName':  fname.lower(),
                'middleName':  mname.lower(),
                'lastName':  lname.lower(),
                'birthdate ':date_of_birth.lower(),
                'symptoms':headache.lower()+sorethroat.lower()+shortbreath.lower()+fever.lower()+cough.lower()+tired.lower()+smell.lower()+diarrhea.lower()+taste.lower()+cold.lower(),
                'travelHistory ': travelHistory.lower(),
                'travelWhen ': travelWhen.lower(),
                'travelWhere': travelWhere.lower(),
                'knowCovidInfected': knowCovidInfected.lower(),
                'vaccinated': Vaccinated.lower(),
                'result': result.lower(),
                'userId':session['user'],
                'created_at': datenow,
                'updated_at':datenow,  
            }
            triage_ref = db.collection('triage').document()
            try:
                update_time = triage_ref.set(data)
                if update_time:
                    return redirect(url_for('bookAppointmentTriageResult', triageid = triage_ref.id, patientAge=patientAge))
                else:
                    return redirect(url_for('bookAppointmentTriageResult', triageid = ""))
            except NameError:
                print("book_apointment_triage ERROR : ",NameError)
                return redirect(url_for('bookAppointmentTriageResult', triageid = ""))
        else:
            return redirect('/logout')

# 4th step triage result
# renders html
@app.route('/patient/book/triage/result', methods=['GET', 'POST'])
def bookAppointmentTriageResult():
    triageid = request.args['triageid']
    patientAge = request.args['patientAge']
    if(int(patientAge) < 18):
        doctorSpecialty = "internal medicine"
    else:
        doctorSpecialty = "family medicine"
    if 'user' in session and session['person_type'] == 'patient':
        patient_details = db.collection(
            'patient').document(session['user']).get()
        triage = db.collection('triage').document(triageid).get()
        return render_template('Patients/book_apointment_triage_result.html',triageid=triageid,triage=triage.to_dict(), patient_details=patient_details.to_dict(),doctorSpecialty=doctorSpecialty,patientAge=patientAge)
    else:
        return redirect('/logout')

# 4th step filters doctors result base on specialty
# then redirects back to patient/book route | navigate back to 1st step
@app.route('/patientBookSelectDoctor', methods=['POST'])
def patientBookSelectDoctor():
    doctorSpecialty = request.form.get("doctorSpecialty")
    triageid = request.form.get("triageid")
    if 'user' in session and session['person_type'] == 'patient':
        return redirect(url_for("book",doctorSpecialty=doctorSpecialty,triageid=triageid))
    else:
        return redirect('/logout')

# last step - create appouintment
@app.route('/bookAppointmentCreate', methods=['POST'])
def bookAppointmentCreate():
    if request.method == 'POST':
        if 'user' in session and session['person_type'] == 'patient':
            reason = request.form['reason']
            docEmail = request.form['docEmail']
            docFirstName = request.form['docFirstName']
            docMiddleName = request.form['docMiddleName']
            docLastName = request.form['docLastName']
            patientFirstName = request.form['triageFirstName']
            patientMiddleName = request.form['triageMiddleName']
            patientLastName = request.form['triageLastName']
            Stime = request.form.get('Stime')
            Sdate = request.form.get('Sdate')
            uniqueId = str(uuid.uuid4())
            db.collection('appointment').document(uniqueId).set({
                'documentId': uniqueId,
                'userId':session['user'],
                'doctorId': docEmail,
                'patientsName': patientLastName + ", " + patientFirstName + " " + patientMiddleName,
                'doctorsName': docLastName + ", " + docFirstName + " " + docMiddleName,
                'status':'pending',
                'scheduleDate':Sdate,
                'scheduleTime':Stime,
                'symptoms':reason.lower(),  
                'created_at': datenow,
                'updated_at':datenow,
            })
        return redirect('/patient/appointments')
    else:
        return redirect('/logout')
#
# END PATIENTS CREATE APPOINTMENT STEPS----------------------------------------------------------------------------------------------------------------


# PATIENTS CREATE TRIAGE START----------------------------------------------------------------------------------------------------------------
# 1st step - click create triage
# Patients Triage page
@app.route('/patient/triage', methods=['GET', "POST"])
def triage_patients():
    print('session : ', session)
    if 'user' in session and session['person_type'] == 'patient':
        patient_details = db.collection(
            'patient').document(session['user']).get()
        triage =[triages.to_dict() for triages in db.collection(u'triage').where(u'userId',u'==',session['user']).order_by(u'updated_at', 'DESCENDING').stream()]
        docs = [doc.to_dict() for doc in db.collection(u'doctor').stream()]
        return render_template('Patients/triage.html', patient_details=patient_details.to_dict(), docs=docs,triage=triage   )
    else:
        return redirect('/logout')

# 2nd step - fill up triage forms then submit
# Patients Triage Create page
@app.route('/patient/triage/create', methods=['POST', "GET"])
def triage_patients_create():
    if 'user' in session and session['person_type'] == 'patient':
        patient_details = db.collection(
            'patient').document(session['user']).get()
        return render_template('Patients/triage_create.html', patient_details=patient_details.to_dict())
    else:
        return redirect('/logout')

# 3rd step - create triage then submit to database
# Patients Triage Create function
@app.route('/patientsTriageCreate', methods=['POST'])
def patientsTriageCreate():
    if request.method == "POST":
        if 'user' in session and session['person_type'] == 'patient':
            print('session-user',session['user'])
            fname = request.form['fname']
            mname = request.form['mname']
            lname = request.form['lname']
            mnth = str(request.form['month'])
            dy = str(request.form['day'])
            yr = str(request.form['year'])
            date_of_birth = mnth+"/"+dy+"/"+yr
           
            travelHistory = request.form['travelHistory']
            travelWhen = request.form['travelWhen']
            travelWhere = request.form['travelWhere']
            knowCovidInfected = request.form['knowCovidInfected']
            Vaccinated = request.form['Vaccinated']
            fever = request.form.get('fever')
            cold = request.form.get('cold')
            headache = request.form.get('headache')
            tired = request.form.get('tired')
            taste = request.form.get('taste')
            cough = request.form.get('cough')
            sorethroat = request.form.get('sorethroat')
            diarrhea = request.form.get('diarrhea')
            shortbreath = request.form.get('shortbreath')
            smell = request.form.get('smell')
            patientAge = age(yr,mnth,dy)
            
            
            
            gender=request.form['gender']
                
                
            if knowCovidInfected == 'Yes':
                knowCovidInfected='contact with covid'+', '
            else:
                knowCovidInfected='' 
            if fever:
                fever = 'Fever'+','
                fvr =1
            else:
                fever = ''
                fvr =0
            if cold:
                cold = 'Cold'+','
            else:
                cold = ''
                
            if headache:
                headache = 'Headache'+', '
                hd =1
            else:
                headache = ''
                hd =0
            if tired:
                tired = 'Tired'+','
            else:
                tired = ''
            if taste:
                taste = 'No sense of taste'+', '
            else:
                taste = ''
            if cough:
                cough = 'Cough'
                cf =1
            else:
                cough = ''
                cf =0
            if sorethroat:
                sorethroat = 'Sorethroat'+', '
                st =1
            else:
                sorethroat = ''
                st =0
            if diarrhea:
                diarrhea = 'Diarrhea'+', '
            else:
                diarrhea = ''
            if shortbreath:
                shortbreath = 'shortness of breath'+', '
                sb =1
            else:
                shortbreath = ''
                sb =0
            if smell:
                smell = ' NO sense of Smell'+', '
            else:
                smell = ' '
            data = np.array([[cf,fvr,st,sb,hd]])
            my_prediction = classifier.predict(data)
            if my_prediction == 1:
                result = 'high risk'
            elif my_prediction == 0:
                result = 'low risk'
            data = {
                'date': datenow.strftime("%Y-%m-%d"),
                'gender': gender.lower(),
                'firstName': fname.lower(),
                'middleName': mname.lower(),
                'lastName':  lname.lower(),
                'birthdate ':date_of_birth.lower(),
                'symptoms':headache.lower()+sorethroat.lower()+shortbreath.lower()+fever.lower()+cough.lower()+tired.lower()+smell.lower()+diarrhea.lower()+taste.lower()+cold.lower(),
                'travelHistory ': travelHistory.lower(),
                'travelWhen ': travelWhen.lower(),
                'travelWhere': travelWhere.lower(),
                'knowCovidInfected': knowCovidInfected.lower(),
                'vaccinated': Vaccinated.lower(),
                'result': result.lower(),
                'userId':session['user'],
                'created_at': datenow,
                'updated_at': datenow,  
            }
            triage_ref = db.collection('triage').document()
            try:
                update_time = triage_ref.set(data)
                if update_time:
                    return redirect(url_for('patientsTriageCreateResult', triageid = triage_ref.id, patientAge=patientAge))
                else:
                    return redirect(url_for('patientsTriageCreateResult', triageid = ""))
            except NameError:
                print("patientsTriageCreateResult ERROR : ",NameError)
                return redirect(url_for('patientsTriageCreateResult', triageid = ""))
        else:
            return redirect('/logout')

# 4th step - View triage results
# Patients Triage Create Result page
@app.route('/patient/triage/create/result', methods=['GET', 'POST'])
def patientsTriageCreateResult():
    triageid = request.args['triageid']
    patientAge = request.args['patientAge']
    if(int(patientAge) < 18):
        doctorSpecialty = "internal medicine"
    else:
        doctorSpecialty = "family medicine"
    if 'user' in session and session['person_type'] == 'patient':
        patient_details = db.collection(
            'patient').document(session['user']).get()
        triage = db.collection('triage').document(triageid).get()
        return render_template('Patients/triage_create_result.html',triageid=triageid,triage=triage.to_dict(), 
                                patient_details=patient_details.to_dict(),patientAge=patientAge,doctorSpecialty=doctorSpecialty)
    else:
        return redirect('/logout')
#
# PATIENTS CREATE TRIAGE END----------------------------------------------------------------------------------------------------------------


# PATIENTS PAGES----------------------------------------------------------------------------------------------------------------
# Patients Appointments Page
@app.route('/patient/appointments', methods=['GET', "POST"])
def appointment_page():

    if request.method == "POST":
        search = request.form["search"]
        if 'user' in session and session['person_type'] == 'patient':
            patient_details = db.collection(
                'patient').document(session['user']).get()
            apoint =[appoints.to_dict() for appoints in db.collection(u'appointment').where(u'userId',u'==',session['user']).where(u'patientsName',u'==',search.lower()).order_by(u'updated_at', 'DESCENDING').stream()]
            docs = [doc.to_dict() for doc in db.collection(u'doctor').stream()]
            return render_template('Patients/appointments.html', patient_details=patient_details.to_dict(), docs=docs,  apoint= apoint)
        else:
            return redirect('/logout')
    if request.method == "GET":  
        if 'user' in session and session['person_type'] == 'patient':
            # isGoole = request.args['isGoole']
            # userInfo = request.args['userInfo']
            patient_details = db.collection(
                'patient').document(session['user']).get()
            apoint =[appoints.to_dict() for appoints in db.collection(u'appointment').where(u'userId',u'==',session['user']).order_by(u'updated_at', 'DESCENDING').stream()]
            docs = [doc.to_dict() for doc in db.collection(u'doctor').stream()]
            return render_template('Patients/appointments.html', patient_details=patient_details.to_dict(), docs=docs,  apoint= apoint)
        else:
            return redirect('/logout')

# Patients Profile Page
@app.route('/patient/profile', methods=['GET'])
def patientProfile():
    if 'user' in session and session['person_type'] == 'patient':
        patient_details = db.collection(
            'patient').document(session['user']).get()
        return render_template('Patients/profile.html', patient_details=patient_details.to_dict())
    else:
        return redirect('/logout')

# Patients Profile Update Page
@app.route('/patient/profile/update', methods=['GET', 'POST'])
def update():
    testtt = request.form.get("")
    if 'user' in session and session['person_type'] == 'patient':
        patient_details = db.collection(
        'patient').document(session['user']).get()
        return render_template('Patients/profile_update.html', patient_details=patient_details.to_dict())

# Patients Profile Update Function
@app.route('/patientProfileUpdate', methods=['POST'])
def patientProfileUpdate():
    if request.method == 'POST':
        if 'user' in session and session['person_type'] == 'patient':
            upload = request.files['Ppic']
            storage.child(session['user']).put(upload)
            fname = request.form['fname']
            mname = request.form['mname']
            lname = request.form['lname']
            mnth = str(request.form['month'])
            dy = str(request.form['day'])
            yr = str(request.form['year'])
            date_of_birth = mnth+"/"+dy+"/"+yr
            gender = request.form['gender']
            contact = request.form['contact']
            url = storage.child(session['user']).get_url(session['acc'])
            doc_ref = db.collection('patient').document(session['user'])
            doc_ref.update({                                                                                                                   
                'firstName':  fname,
                'lastName': lname,
                'middleName': mname,
                'contact ':contact,
                'profile':url,
                'gender':gender,
                'birthDate':date_of_birth,
                'updated_at':datenow,
            })
            return redirect('/patient/profile')
        return redirect('/')
    else:
        return redirect('/logout')

# Patients Book Appointment Create Page
@app.route('/patient/book/create', methods=['GET', 'POST'])
def triage():
    if 'user' in session and session['person_type'] == 'patient':
        patient_details = db.collection(
            'patient').document(session['user']).get()
        bookdoc = request.form['docid']
        doctors = db.collection('doctor').document(bookdoc).get()
        return render_template('Patients/book_apointment_create.html', patient_details=patient_details.to_dict(), docs=doctors.to_dict())
    else:
        return redirect('/logout')

@app.route('/patient/aboutus', methods=['GET'])
def patient_aboutuspage():
    if 'user' in session and session['person_type'] == 'patient':
        patient_details = db.collection(
            'patient').document(session['user']).get()
        page = [pages.to_dict() for pages in db.collection(u'page').stream()]
        return render_template('Patients/About.html', patient_details=patient_details.to_dict(), page=page)
    else:
        return redirect('/logout')




#-Doctors PAGES---------------------------------------------------------------------------------------------------------------------------
# Doctor Dashboard
@app.route('/doctor/dashboard', methods=['GET', 'POST'])
def doctor_dashboard():
    if 'user' in session and session['person_type'] == 'doctor':
        doctor = db.collection(
            'doctor').document(session['user']).get()
        appointmentsToday =[appoints.to_dict() for appoints in db.collection(u'appointment').where(u'scheduleDate',u'==',todayDate)
                            .where(u'status',u'==','approved').where(u'doctorId',u'==',session['user']).stream()]
        appointmentsAll =[appoints.to_dict() for appoints in db.collection(u'appointment').where(u'doctorId',u'==',session['user']).stream()]
        return render_template('Doctor/dashboard.html', doc=doctor.to_dict(),appointmentsToday=len(appointmentsToday),
                               appointmentsAll=len(appointmentsAll),apoint=appointmentsToday,apointAll=appointmentsAll)
    else:
        return redirect('/logout')

# Doctor Appointments
@app.route('/doctor/appointments', methods=['GET', 'POST'])
def doctor_appointment():
    if request.method == "POST":
        if 'user' in session and session['person_type'] == 'doctor':
            dt= request.form["appointmentDate"]
            doctor = db.collection(
            'doctor').document(session['user']).get()
            apointments =[appoints.to_dict() for appoints in db.collection(u'appointment').where(u'doctorId',u'==',session['user']).where(u'scheduleDate',u'==', dt).order_by(u'updated_at', 'DESCENDING').stream()]
            return render_template('Doctor/appointments.html', apointments= apointments, doc=doctor.to_dict())
        else:
            return redirect('/logout')
    if request.method == "GET":
        if 'user' in session and session['person_type'] == 'doctor':
            doctor = db.collection(
                'doctor').document(session['user']).get()     
            apointments =[appoints.to_dict() for appoints in db.collection(u'appointment').where(u'doctorId',u'==',session['user']).order_by(u'updated_at', 'DESCENDING').stream()]
            return render_template('Doctor/appointments.html', apointments= apointments, doc=doctor.to_dict())
        else:
            return redirect('/logout')

# Doctor Appointments Approval Function
@app.route('/doctorAppointmentsApproval', methods=['GET'])
def doctorAppointmentsApproval():
    if 'user' in session and session['person_type'] == 'doctor':
        appoinmentId = request.args.get("appoinmentId")
        appoinmentStatus = request.args.get("status")
        appointment_ref = db.collection('appointment').document(appoinmentId)
        appointment_ref.update({
            "status": appoinmentStatus.lower()
        })
        print("appointment_ref : ",appointment_ref.id)
        return redirect('/doctor/appointments')
    else:
        return redirect('/logout')





#-Admin PAGES---------------------------------------------------------------------------------------------------------------------------
# Admin Login
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'GET':
        if 'user' not in session:
            return render_template('Admin/index.html')
        else:
            return redirect('/logout')
    elif request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        flag_4 = False
        # validate account
        try:
            admin_user = auth.sign_in_with_email_and_password(email, password)
            print("admin_user : ",admin_user)
            # e-mail verification check
            acc_info = auth.get_account_info(admin_user['idToken'])
            if acc_info['users'][0]['emailVerified'] == False:
                flag_4 = True
        except:
            flag_3 = False
        if flag_4 == False:
            flash(
                'Incorrect e-mail or password', 'error')
            return redirect('/admin')
       
        doc_ref = db.collection(u'Admin').document(email)
        doc = doc_ref.get()
        if doc.exists:
            
            session['pass'] = password
            session ['acc'] = admin_user
            session['user'] = email
            session['person_type'] = 'admin'
            return redirect('/admin_dashboard')
        else:
            flash(
                'Incorrect e-mail or password', 'error')
            return redirect('/admin')

# Admin Dashboard
@app.route('/admin_dashboard', methods=['GET'])
def admin_dashboard():
    if 'user' in session and session['person_type'] == 'admin':
        admin =db.collection('admin').document(session['user']).get()
        triage =[triages.to_dict() for triages in db.collection(u'triage').stream()]
        #count doctors
        docss = db.collection(u'doctor').stream()
        counter = 0
        for doc in docss:
            counter +=1 
            print(f'{doc.id} => {doc.to_dict()}')
        numdoc =counter
        #count appointments today
        appointmentsToday =[appoints.to_dict() for appoints in db.collection(u'appointment').where(u'scheduleDate',u'==',todayDate).where(u'status',u'==','approved').stream()]
        return render_template('Admin/dashboard.html', triage=triage,admin=admin.to_dict(), numdoc = numdoc, 
                               appointmentsToday = len(appointmentsToday), apoint=appointmentsToday)
    else:
        return redirect('/logout')

# Admin Doctors
@app.route('/admin_add_doctor', methods=['GET'])
def admin_add_doctor():
    if 'user' in session and session['person_type'] == 'admin':
        patient_details = db.collection(
            'patient').document(session['user']).get()
        # where clause
        # docs = [doc.to_dict() for doc in db.collection(u'doctor').where(u'gender',u'==',u'Male').stream()]
        docs = [doc.to_dict() for doc in db.collection(u'doctor').where(u'status',u'==',u'active').stream()]
        admin = db.collection('admin').document(session['user']).get()
        return render_template('Admin/doctors.html', patient_details=patient_details.to_dict(), docs=docs,admin=admin.to_dict())
    else:
        return redirect('/logout')

# Admin Doctors Add 
@app.route('/admin/doctors/add', methods=['GET'])
def adminAddDoctor():
    if 'user' in session and session['person_type'] == 'admin':
        admin = db.collection('admin').document(session['user']).get()
        return render_template('Admin/doctors_create.html', admin=admin.to_dict())
    else:
        return redirect('/logout')

# Admin Doctors Update 
@app.route('/admin/doctors/update', methods=['GET'])
def adminUpdateDoctor():
    # retrieve email from doctors table
    docemail = request.args.get("docemail")
    doctor = db.collection('doctor').document(docemail).get()
    if 'user' in session and session['person_type'] == 'admin':
        admin = db.collection('admin').document(session['user']).get()
        return render_template('Admin/doctors_update.html', admin=admin.to_dict(), doctor=doctor.to_dict())
    else:
        return redirect('/logout')


# Admin all apointments
@app.route('/Admin_appointment', methods=['GET' ,'POST'])
def Admin_appointment():
    if request.method == 'POST':
        if 'user' in session and session['person_type'] == 'admin':
            dt= request.form["appointmentDate"]
            apoint =[appoints.to_dict() for appoints in db.collection(u'appointment').where(u'scheduleDate',u'==', dt).order_by(u'updated_at', 'DESCENDING').stream()]
            admin = db.collection('admin').document(session['user']).get()
            return render_template('Admin/appointments.html', apoint= apoint, admin=admin.to_dict())
        else:
            return redirect('/logout')
    if request.method == "GET":
        if 'user' in session and session['person_type'] == 'admin':
            apoint =[appoints.to_dict() for appoints in db.collection(u'appointment').stream()]
            docs = [doc.to_dict() for doc in db.collection(u'doctor').stream()]
            admin = db.collection('admin').document(session['user']).get()
            return render_template('Admin/appointments.html', docs=docs,  apoint= apoint, admin=admin.to_dict())
        else:
            return redirect('/logout')

# Admin Triage
@app.route('/admin_triage', methods=['GET', 'POST'])
def admin_triage():
    if request.method == "POST":
        if 'user' in session and session['person_type'] == 'admin':
            dt= request.form["appointmentDate"]
            triage =[triages.to_dict() for triages in db.collection(u'triage').where(u'date',u'==', dt).order_by(u'updated_at', 'DESCENDING').stream()]
            admin = db.collection('admin').document(session['user']).get()
            return render_template('Admin/triage.html',triage=triage,admin=admin.to_dict()   )
        else:
            return redirect('/logout')
    if request.method == "GET":
        if 'user' in session and session['person_type'] == 'admin':
            triage =[triages.to_dict() for triages in db.collection(u'triage').stream()]
            admin = db.collection('admin').document(session['user']).get()
            return render_template('Admin/triage.html',triage=triage,admin=admin.to_dict()   )
        else:
            return redirect('/logout')


# Admin Services Page
@app.route('/admin/services', methods=['GET', 'POST'])
def adminServices():
    if 'user' in session and session['person_type'] == 'admin':
        services =[servicess.to_dict() for servicess in db.collection(u'services').stream()]
        admin = db.collection('admin').document(session['user']).get()
        return render_template('Admin/services.html',admin=admin.to_dict(),services=services)
    else:
         return redirect('/logout')

# Admin Services Create Page
@app.route('/admin/services/create', methods=['GET', 'POST'])
def adminServicesCreatePage():
    if 'user' in session and session['person_type'] == 'admin':
        admin = db.collection('admin').document(session['user']).get()
        return render_template('Admin/services_create.html',admin=admin.to_dict())
    else:
         return redirect('/logout')

# Admin Services Create Function
@app.route('/admin_service_create', methods=['POST'])
def adminServicesCreateFunction():
    if request.method == 'POST':
        serviceName = request.form['serviceName']
        uniqueId = str(uuid.uuid4())
        db.collection('services').document(uniqueId).set({
            'documentId': uniqueId,
            'serviceName': serviceName.lower(),
            'created_at': datenow,
            'updated_at':datenow,
            # firebase auth
        })
        return redirect("/admin/services")

# Admin Services Delete Function
@app.route('/admin_service_delete', methods=['POST', 'GET'])
def adminServicesDeleteFunction():
    documentId = request.args.get("serviceId")
    if 'user' in session and session['person_type'] == 'admin':
        db.collection('services').document(documentId).delete()
        return redirect('/admin/services')
    else:
        return redirect('/logout')

# Admin Services Update Page
@app.route('/admin/services/update', methods=['GET', 'POST'])
def adminServicesUpdatePage():
    if 'user' in session and session['person_type'] == 'admin':
        documentId = request.args.get("serviceId")
        service = db.collection('services').document(documentId).get()
        admin = db.collection('admin').document(session['user']).get()
        return render_template('Admin/services_update.html',admin=admin.to_dict(),service=service.to_dict())
    else:
         return redirect('/logout')

# Admin Services Update Function
@app.route('/admin_service_update', methods=['GET', 'POST'])
def adminServicesUpdateFunction():
    if 'user' in session and session['person_type'] == 'admin':
        documentId = request.form["serviceId"]
        serviceName = request.form['serviceName']
        service_ref = db.collection('services').document(documentId)
        service_ref.update({
            'serviceName': serviceName,
            'updated_at':datenow,
        })
        return redirect('/admin/services')
    else:
         return redirect('/logout')



#-Backend routes---------------------------------------------------------------------------------------------------------------------------

# Doctor update data
@app.route('/doctor/update', methods=['POST'])
def doctorUpdate():
    if request.method == 'POST':
        if 'user' in session and session['person_type'] == 'admin':
            fname = request.form['fname']
            lname = request.form['lname']
            mname = request.form['mname']
            gender = request.form['gender']
            mnth = str(request.form['month'])
            dy = str(request.form['day'])
            yr = str(request.form['year'])
            date_of_birth = mnth+"/"+dy+"/"+yr
            special = request.form['specialty']
            doctorEmail = request.form['doctorEmail']
            contact = request.form['contact']
            doctor_ref = db.collection('doctor').document(doctorEmail)
            doctor_ref.update({                                                                                                                   
                'firstName': fname.lower(),
                'lastName': lname.lower(),
                'middleName': mname.lower(),
                'gender': gender.lower(),
                'birthDate': date_of_birth.lower(),
                'specialty': special.lower(),
                'email': doctorEmail,
                'contact':contact.lower(),
                'updated_at':datenow,
            })
        return redirect('/admin_add_doctor')
    else:
        return redirect('/logout')

# Doctor delete data
@app.route('/admin/doctors/delete', methods=['POST', 'GET'])
def doctorDelete():
    docemail = request.args.get("doctoremail")
    if 'user' in session and session['person_type'] == 'admin':
        db.collection('doctor').document(docemail).update({
            'status':'inactive'.lower(),
        })
        return redirect('/admin_add_doctor')
    else:
        return redirect('/logout')

# Doctor Create Account
@app.route('/admin_doctors_add', methods=['GET', 'POST'])
def admin_add():
    if request.method == 'GET':
        if 'user' not in session:
            return redirect('/admin')
    elif request.method == 'POST':
        fname = request.form['fname']
        lname = request.form['lname']
        mname = request.form['mname']
        gender = request.form['gender']
        mnth = str(request.form['month'])
        dy = str(request.form['day'])
        yr = str(request.form['year'])
        date_of_birth = mnth+"/"+dy+"/"+yr
        special = request.form['specialty']
        email = request.form['email']
        password = request.form['password']
        password2 = request.form['password2']
        contact = request.form['contact']
        # check if passwords match
        if password != password2:
            flash('The passwords do not match...', 'error')
            return redirect('/admin_doctors_add')
        # auth user
        try:
            doctor_user = auth.create_user_with_email_and_password(
                email, password)
        except:
            flash(
                'This e-mail has already been registered. Please use another e-mail...', 'error')
            return redirect('/admin_doctors_add')
        # e-mail verification
        auth.send_email_verification(doctor_user['idToken'])
        doc1 = db.collection('admin').document('doctors')
        doc1.set({u'doctor_name': email})
        db.collection('doctor').document(email).set({
            'firstName': fname.lower(),
            'lastName': lname.lower(),
            'middleName': mname.lower(),
            'gender': gender.lower(),
            'birthDate': date_of_birth.lower(),
            'specialty': special.lower(),
            'email': email,
            'password': password,
            'contact':contact.lower(),
            'status':'active'.lower(),
            'created_at': datenow,
            'Updated_at':datenow,
            # firebase auth
        })
        # check for div
        docs = [doc.to_dict() for doc in db.collection(u'doctor').stream()]
        admin = db.collection('admin').document(session['user']).get()
        flash('Registration successful! ', 'info')
        return redirect("/admin_add_doctor")

# Doctor Search Account
@app.route('/admin/doctors/search', methods=['GET', 'POST'])
def doctorSearch():
    if request.method == "GET":
        if 'user' in session and session['person_type'] == 'admin':
            patient_details = db.collection(
                        'patient').document(session['user']).get()
            docs = [doc.to_dict() for doc in db.collection(u'doctor').where('status','==',"active").stream()]
            admin = db.collection('admin').document(session['user']).get()
            return render_template('Admin/doctors.html', patient_details=patient_details.to_dict(), docs=docs,admin=admin.to_dict())
        else:
            return redirect('/logout')
    
    if request.method == 'POST':
        searchValue = request.form.get("txtDoctorSearch")
        if 'user' in session and session['person_type'] == 'admin':
            patient_details = db.collection(
                        'patient').document(session['user']).get()
            docs = [doc.to_dict() for doc in db.collection(u'doctor').where(u'firstName',u'==',searchValue).stream()]
            print('docs : ',docs)
            admin = db.collection('admin').document(session['user']).get()
            return render_template('Admin/doctors.html', patient_details=patient_details.to_dict(), docs=docs,admin=admin.to_dict())
        else:
            return redirect('/logout')


@app.route('/predict', methods=['POST'])
def predict():
    if request.method == 'POST':
        if 'user' in session and session['person_type'] == 'patient':
            patient_details = db.collection('patient').document(session['user']).get()
            fname = request.form['fname']
            mname = request.form['mname']
            lname = request.form['lname']
            mnth = str(request.form['month'])
            dy = str(request.form['day'])
            yr = str(request.form['year'])
            date_of_birth = mnth+"/"+dy+"/"+yr
            reason = request.form['reason']
            travelHistory = request.form['travelHistory']
            travelWhen = request.form['travelWhen']
            travelWhere = request.form['travelWhere']
            knowCovidInfected = request.form['knowCovidInfected']
            Vaccinated = request.form['Vaccinated']
            docid = request.form['docid']
            gender = request.form['gender']
            Stime = request.form.get('Stime')
            Sdate = request.form.get('Sdate')
            fever = request.form.get('fever')
            cold = request.form.get('cold')
            headache = request.form.get('headache')
            tired = request.form.get('tired')
            taste = request.form.get('taste')
            cough = request.form.get('cough')
            sorethroat = request.form.get('sorethroat')
            diarrhea = request.form.get('diarrhea')
            shortbreath = request.form.get('shortbreath')
            smell = request.form.get('smell')
            if knowCovidInfected == 'Yes':
                knowCovidInfected='contact with covid'+', '
            else:
                knowCovidInfected='' 
            if fever:
                fever = 'Fever'+','
                fvr =1
            else:
                fever = ''
                fvr =0
            if cold:
                cold = 'Cold'+','
            else:
                cold = ''
                
            if headache:
                headache = 'Headache'+', '
                hd =1
            else:
                headache = ''
                hd =0
            if tired:
                tired = 'Tired'+','
            else:
                tired = ''
            if taste:
                taste = 'No sense of taste'+', '
            else:
                taste = ''
            if cough:
                cough = 'Cough'
                cf =1
            else:
                cough = ''
                cf =0
            if sorethroat:
                sorethroat = 'Sorethroat'+', '
                st =1
            else:
                sorethroat = ''
                st =0
            if diarrhea:
                diarrhea = 'Diarrhea'+', '
            else:
                diarrhea = ''
            if shortbreath:
                shortbreath = 'shortness of breath'+', '
                sb =1
            else:
                shortbreath = ''
                sb =0
            if smell:
                smell = ' NO sense of Smell'+', '
            else:
                smell = ' '
            data = np.array([[cf,fvr,st,sb,hd]])
            my_prediction = classifier.predict(data)
            if my_prediction == 1:
                result = 'high risk'
            elif my_prediction == 0:
                result = 'low risk'
            doc_ref = db.collection('triage').document()
            doc_ref.set({       
                'gender': gender,
                'First_name':  fname,
                'Middle_name':  mname,
                'Last_name':  lname,
                'Date_of_birth ':date_of_birth,
                'symptoms':headache+sorethroat+shortbreath+fever+cough+tired+smell+diarrhea+taste+cold,
                'travelHistory ': travelHistory,
                'travelWhen ': travelWhen,
                'travelWhere': travelWhere,
                'knowCovidInfected': knowCovidInfected,
                'Vaccinated': Vaccinated,
                'result': result,
                'user_id':session['user'],
                'created_at': datenow,
                'Updated_at':datenow,
                # firebase auth
            })
            db.collection('appointment').document().set({
                'user_id':session['user'],
                'traige_id': doc_ref.id,
                'Doctors_id':docid,
                'status':'pending',
                'Schedule_date':Stime,
                'Schedule_time':Sdate ,
                'Symptoms':reason,
                'created_at': datenow,
                'Updated_at':datenow,
            })
        return redirect('/dashboard')
    else:
        return redirect('/logout')






#-Others---------------------------------------------------------------------------------------------------------------------------
@app.route('/page', methods=['GET', 'POST'])
def page():
    if 'user' in session and session['person_type'] == 'admin':
        admin = db.collection('admin').document(session['user']).get()
        page = [pages.to_dict() for pages in db.collection(u'page').stream()]

        return render_template('Admin/page.html', admin=admin.to_dict(),page = page)

@app.route('/edit_page', methods=['POST'])
def edit_page():
    if request.method == 'POST':
        #dictionary = page
        #document page1

        if 'user' in session and session['person_type'] == 'admin':
            upload = request.files['picturepage']
            st = storage.child("page1").put(upload)
            url = storage.child("page1").get_url(session['acc'])

            doc_ref = db.collection('page').document('page1')
            doc_ref.set({      
                 'picture':url,      
             })
        return redirect('/page')
    else:
        return redirect('/logout')

@app.route('/edit_page2', methods=['POST'])
def edit_page2():
    if request.method == 'POST':
        #dictionary = page
        #document page1

        if 'user' in session and session['person_type'] == 'admin':
            upload = request.files['picturepage']
            st = storage.child("page2").put(upload)
            url = storage.child("page2").get_url(session['acc'])

            doc_ref = db.collection('page').document('page2')
            doc_ref.set({      
                 'picture':url,      
             })
        return redirect('/page')
    else:
        return redirect('/logout')

@app.route('/edit_page3', methods=['POST'])
def edit_page3():
    if request.method == 'POST':
        #dictionary = page
        #document page1

        if 'user' in session and session['person_type'] == 'admin':
            upload = request.files['picturepage']
            st = storage.child("page3").put(upload)
            url = storage.child("page3").get_url(session['acc'])

            doc_ref = db.collection('page').document('page3')
            doc_ref.set({      
                 'picture':url,      
             })
        return redirect('/page')
    else:
        return redirect('/logout')

@app.route('/edit_page4', methods=['POST'])
def edit_page4():
    if request.method == 'POST':
        #dictionary = page
        #document page1

        if 'user' in session and session['person_type'] == 'admin':
            upload = request.files['picturepage']
            st = storage.child("page4").put(upload)
            url = storage.child("page4").get_url(session['acc'])

            doc_ref = db.collection('page').document('page4')
            doc_ref.set({      
                 'picture':url,      
             })
        return redirect('/page')
    else:
        return redirect('/logout')

@app.route('/doc_update', methods=['GET', 'POST'])
def doc_update():
    if 'user' in session and session['person_type'] == 'doctor':
        
         
        doctor = db.collection(
            'doctor').document(session['user']).get()
     

 
        return render_template('Doctor/doctor_edit.html', doc=doctor.to_dict())

@app.route('/Doc_edit', methods=['POST'])
def Doc_edit():
    if request.method == 'POST':
        if 'user' in session and session['person_type'] == 'doctor':
            patient_details = db.collection('doctor').document(session['user']).get()
            #pfile = request.form['Ppic']
            #blob = storage.child(pfile)
            #blob.upload_from_filename('profiles'/pfile)
            upload = request.files['Ppic']
            st = storage.child(session['user']).put(upload)
            special = request.form['specialty']
            fname = request.form['fname']
            mname = request.form['mname']
            lname = request.form['lname']
            mnth = str(request.form['month'])
            dy = str(request.form['day'])
            yr = str(request.form['year'])
            date_of_birth = mnth+"/"+dy+"/"+yr
            gender = request.form['gender']
            contact = request.form['contact']
            url = storage.child(session['user']).get_url(session['acc'])
             
            doc_ref = db.collection('doctor').document(session['user'])
            doc_ref.update({                                                                                                                     
                'First_name':  fname,
                'Last_name': lname,
                'Middle_name': mname,
                'contact_number ':contact,
                'profile':url,
                'Gender':gender,
                'Date_of_birth':date_of_birth,
                'Updated_at':datenow,
                'specialty': special,
                'Updated_at':datenow,
            })
        return redirect('/doc_update')
    else:
        return redirect('/logout')

@app.route('/image', methods=['GET', 'POST'])
def image():
    if request.method == 'GET':
        if 'user' not in session:
            return render_template('image.html')
        else:
            return redirect('/logout')

    elif request.method == 'POST':
        upload = request.files['upload']
        storage.child("images").put(upload)
        return redirect(url_for('uploads'))
    return render_template('image.html')

@app.route('/uploads', methods=['GET', 'POST'])
def uploads():

    if request.method == 'POST':
        return redirect(url_for('basic'))
    if True:
        links = storage.child('images/new.mp4').get_url(None)
        return render_template('upload.html', l=links)



@app.route('/logout', methods=['GET'])
def logout():
    if 'user' in session:
        session.pop('user', None)
        session.pop('person_type', None)
      

        flash('You have been logged out...', 'warning')
        return redirect('/')
    else:
        return redirect('/')

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgotPassword():
    if request.method == 'GET':
        if 'user' not in session:
            return render_template('forgot_password_page.html')
        else:
            return redirect('/logout')
    elif request.method == 'POST':
        email = request.form['email']
        try:
            auth.send_password_reset_email(email)
        except:
            flash('That e-mail ID is not registered...', 'error')
            return redirect('/')
        flash('Check your e-mail to set new password...', 'info')
        return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
