import os
import cv2
import face_recognition
import torch
from facenet_pytorch import InceptionResnetV1, MTCNN
from kivy.lang import Builder
from kivy.uix.screenmanager import ScreenManager, Screen
from kivymd.app import MDApp
from kivymd.uix.button import MDRaisedButton
from kivymd.uix.dialog import MDDialog
from kivymd.uix.label import MDLabel
from kivymd.uix.textfield import MDTextField
from kivymd.uix.filemanager import MDFileManager
from kivy.core.window import Window
from shutil import copyfile
from datetime import datetime
from threading import Timer
from kivy.clock import Clock
import firebase_admin
from firebase_admin import credentials, firestore, storage
import io

# Initialize Firebase Admin SDK
cred = credentials.Certificate("serviceAccountKey.json")
firebase_admin.initialize_app(cred, {
    'storageBucket': 'kivy-56945.appspot.com'
})
db = firestore.client()
bucket = storage.bucket()

# Folder paths in Firebase Storage
CARD_FOLDER = 'card'
FACE_FOLDER = 'face'
LOGIN_FOLDER = 'login'
TEMPORARY_PHOTO = 'temporary_photo'
NOT_ALLOW_USER_FOLDER = 'not_allow_user'

# Firebase storage paths
def get_firebase_path(folder, filename):
    return f'{folder}/{filename}'

class LoginPage(Screen):
    pass

class RegistrationPage(Screen):
    pass

def show_dialog(self, title, text):
    Clock.schedule_once(lambda dt: self._show_dialog(title, text))

def _show_dialog(self, title, text):
    dialog = MDDialog(
        title=title,
        text=text,
        buttons=[
            MDRaisedButton(
                text="OK", on_release=lambda x: dialog.dismiss()
            ),
        ],
    )
    dialog.open()

class HomePage(Screen):
    def on_enter(self):
        self.schedule_next_capture()

    def schedule_next_capture(self):
        # Schedule the capture of a new face photo every 5 seconds
        self.timer = Timer(5, self.capture_and_compare_face)
        self.timer.start()

    def capture_and_compare_face(self):
        def process_images(*args):
            # Load the face photo of the logged-in user
            login_face_path = app.captured_face_path
            if not login_face_path:
                self.show_dialog("Error", "Login face photo not found")
                return

            # Download the image from Firebase Storage to a BytesIO object
            blob = bucket.blob(login_face_path)
            bytes_io = io.BytesIO()
            blob.download_to_file(bytes_io)
            bytes_io.seek(0)

            login_face_photo = face_recognition.load_image_file(bytes_io)
            login_face_photo = cv2.cvtColor(login_face_photo, cv2.COLOR_BGR2RGB)

            # Capture a new face photo
            cap = cv2.VideoCapture(0)
            ret, frame = cap.read()
            cap.release()

            if not ret:
                self.show_dialog("Error", "Failed to capture face photo.")
                return

            # Upload the captured face photo to Firebase Storage
            temporary_photo_path = get_firebase_path(TEMPORARY_PHOTO, f"{datetime.now().strftime('%Y-%m-%d___%H-%M-%S')}.jpg")
            blob = bucket.blob(temporary_photo_path)
            blob.upload_from_string(cv2.imencode('.jpg', frame)[1].tobytes(), content_type='image/jpeg')

            # Download the image from Firebase Storage to a BytesIO object
            bytes_io = io.BytesIO()
            blob.download_to_file(bytes_io)
            bytes_io.seek(0)

            captured_face_photo = face_recognition.load_image_file(bytes_io)
            captured_face_photo = cv2.cvtColor(captured_face_photo, cv2.COLOR_BGR2RGB)

            # Initialize face detection and embedding models
            mtcnn = MTCNN(image_size=160, margin=0)
            model = InceptionResnetV1(pretrained='vggface2').eval()

            try:
                login_face_cropped = mtcnn(login_face_photo)
                captured_face_cropped = mtcnn(captured_face_photo)

                if login_face_cropped is None or captured_face_cropped is None:
                    self.show_dialog("Error", "No face detected in one of the images.")
                    self.manager.current = 'login'  # Go back to login page
                    return

                login_face_embedding = model(login_face_cropped.unsqueeze(0))
                captured_face_embedding = model(captured_face_cropped.unsqueeze(0))

            except ValueError as e:
                self.handle_unauthorized_user(None)
                return

            cos = torch.nn.CosineSimilarity(dim=1, eps=1e-6)
            similarity = cos(login_face_embedding, captured_face_embedding).item()

            threshold = 0.6

            if similarity > threshold:
                # Continue to capture the next photo after 5 seconds
                self.schedule_next_capture()
            else:
                # Save the unauthorized face photo
                self.handle_unauthorized_user(frame)

        # Ensure that the processing is done on the main thread
        Clock.schedule_once(process_images)

    def handle_unauthorized_user(self, captured_face_photo):
        # Save the unauthorized face photo
        if captured_face_photo is not None:
            unauthorized_face_path = get_firebase_path(NOT_ALLOW_USER_FOLDER, f"{datetime.now().strftime('%Y-%m-%d___%H-%M-%S')}.jpg")
            blob = bucket.blob(unauthorized_face_path)
            blob.upload_from_string(cv2.imencode('.jpg', captured_face_photo)[1].tobytes(), content_type='image/jpeg')

        self.show_dialog("Unauthorized User", "You are not the authorized user. Returning to login page.")
        self.manager.current = 'login'

    def stop_face_recognition(self):
        if hasattr(self, 'timer'):
            self.timer.cancel()

    def show_dialog(self, title, text):
        dialog = MDDialog(
            title=title,
            text=text,
            buttons=[
                MDRaisedButton(
                    text="OK", on_release=lambda x: dialog.dismiss()
                ),
            ],
        )
        dialog.open()

class MyApp(MDApp):
    file_manager = None
    selected_file_path = None
    captured_face_path = None
    logged_in_username = None

    def build(self):
        self.title = "My App"
        self.theme_cls.primary_palette = "Blue"
        Window.bind(on_keyboard=self.on_back_button)

        self.file_manager = MDFileManager(
            exit_manager=self.exit_manager,
            select_path=self.select_path,
        )

        return Builder.load_string(kv)

    def on_back_button(self, window, key, *args):
        if key == 27:  # The 'Esc' key
            if self.root.current == 'home':
                self.root.current = 'login'
                return True
            elif self.root.current == 'register':
                self.root.current = 'login'
                return True
        return False

    def show_dialog(self, title, text):
        dialog = MDDialog(
            title=title,
            text=text,
            buttons=[
                MDRaisedButton(
                    text="OK", on_release=lambda x: dialog.dismiss()
                ),
            ],
        )
        dialog.open()

    def register_user(self, username, password):
        if not username or not password:
            self.show_dialog("Error", "Username and password cannot be empty")
            return

        if not self.selected_file_path:
            self.show_dialog("Error", "Please upload an ID card photo")
            return

        if not self.captured_face_path:
            self.show_dialog("Error", "Please take a face photo")
            return

        # Create a new user document in Firestore
        user_ref = db.collection('users').document()
        user_ref.set({
            'username': username,
            'password': password,
            'id_card_photo': self.selected_file_path,
            'face_photo': self.captured_face_path,
        })

        # Upload ID card photo to Firebase Storage
        id_card_photo_path = f"{CARD_FOLDER}/{username}_card.jpg"
        bucket.blob(id_card_photo_path).upload_from_filename(self.selected_file_path, content_type='image/jpeg')

        # Download the captured face photo from Firebase Storage
        blob = bucket.blob(self.captured_face_path)
        bytes_io = io.BytesIO()
        blob.download_to_file(bytes_io)
        bytes_io.seek(0)

        # Upload face photo to Firebase Storage
        face_photo_path = f"{FACE_FOLDER}/{username}_face.jpg"
        bucket.blob(face_photo_path).upload_from_string(bytes_io.getvalue(), content_type='image/jpeg')

        self.show_dialog("Success", "Registration successful. Please log in.")
        self.root.current = 'login'

    def login_user(self, username, password):
        # Query Firestore for the user document
        user_ref = db.collection('users').where('username', '==', username).where('password', '==', password).stream()
        for user in user_ref:
            self.logged_in_username = username
            self.captured_face_path = user.get('face_photo')
            self.root.get_screen('home').ids.username_label.text = f"Username: {username}"
            self.root.current = 'home'
            return

        self.show_dialog("Error", "Invalid username or password")

    def login_with_face(self):
        # Capture the face photo
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            self.show_dialog("Error", "Failed to capture face photo.")
            return

        # Upload the captured face photo to Firebase Storage
        captured_face_path = f"{LOGIN_FOLDER}/{datetime.now().strftime('%Y-%m-%d___%H-%M-%S')}.jpg"
        blob = bucket.blob(captured_face_path)
        blob.upload_from_string(cv2.imencode('.jpg', frame)[1].tobytes(), content_type='image/jpeg')

        # Download the image from Firebase Storage to a BytesIO object
        blob = bucket.blob(captured_face_path)
        bytes_io = io.BytesIO()
        blob.download_to_file(bytes_io)
        bytes_io.seek(0)

        # Extract face embedding from the captured face photo
        captured_face_photo = face_recognition.load_image_file(bytes_io)
        captured_face_photo = cv2.cvtColor(captured_face_photo, cv2.COLOR_BGR2RGB)

        # Initialize face detection and embedding models
        mtcnn = MTCNN(image_size=160, margin=0)
        model = InceptionResnetV1(pretrained='vggface2').eval()

        # Extract face embedding from the captured face photo
        captured_face_cropped = mtcnn(captured_face_photo)
        if captured_face_cropped is None:
            self.show_dialog("Error", "No face detected in the captured face photo.")
            return

        captured_face_embedding = model(captured_face_cropped.unsqueeze(0))

        # Query Firestore for the user document
        user_ref = db.collection('users').stream()
        for user in user_ref:
            face_photo_path = user.get('face_photo')
            blob = bucket.blob(face_photo_path)
            bytes_io = io.BytesIO()
            blob.download_to_file(bytes_io)
            bytes_io.seek(0)

            face_photo = face_recognition.load_image_file(bytes_io)
            face_photo = cv2.cvtColor(face_photo, cv2.COLOR_BGR2RGB)

            face_cropped = mtcnn(face_photo)
            if face_cropped is None:
                continue

            face_embedding = model(face_cropped.unsqueeze(0))

            cos = torch.nn.CosineSimilarity(dim=1, eps=1e-6)
            similarity = cos(face_embedding, captured_face_embedding).item()

            threshold = 0.6

            if similarity > threshold:
                self.logged_in_username = user.get('username')
                self.captured_face_path = face_photo_path
                self.root.get_screen('home').ids.username_label.text = f"Username: {self.logged_in_username}"
                self.root.current = 'home'
                return

        self.show_dialog("Error", "Face does not match any registered user")

    def capture_face_photo(self, username):
        # Capture the face photo
        cap = cv2.VideoCapture(0)
        ret, frame = cap.read()
        cap.release()

        if not ret:
            self.show_dialog("Error", "Failed to capture face photo.")
            return

        # Upload the captured face photo to Firebase Storage
        face_photo_path = f"{FACE_FOLDER}/{username}_face.jpg"
        blob = bucket.blob(face_photo_path)
        blob.upload_from_string(cv2.imencode('.jpg', frame)[1].tobytes(), content_type='image/jpeg')

        self.captured_face_path = face_photo_path
        self.show_dialog("Success", "Face photo captured successfully")

    def file_manager_open(self):
        self.file_manager.show('/')

    def select_path(self, path):
        self.exit_manager()
        self.selected_file_path = path

    def exit_manager(self, *args):
        self.file_manager.close()

    def upload_id_card_photo(self):
        if not self.selected_file_path:
            self.show_dialog("Error", "Please select an ID card photo")
            return

        # Upload the selected ID card photo to Firebase Storage
        id_card_photo_path = f"{CARD_FOLDER}/{self.logged_in_username}_card.jpg"
        bucket.blob(id_card_photo_path).upload_from_filename(self.selected_file_path, content_type='image/jpeg')

        self.show_dialog("Success", "ID card photo uploaded successfully")

    def on_stop(self):
        # Delete all photos in temporary_photo folder in Firebase Storage
        blobs = bucket.list_blobs(prefix=TEMPORARY_PHOTO)
        for blob in blobs:
            blob.delete()

kv = '''
ScreenManager:
    LoginPage:
    RegistrationPage:
    HomePage:

<LoginPage>:
    name: 'login'
    MDTextField:
        id: username
        hint_text: "Username"
        pos_hint: {"center_x": 0.5, "center_y": 0.6}
        size_hint_x: None
        width: 300
    MDTextField:
        id: password
        hint_text: "Password"
        password: True
        pos_hint: {"center_x": 0.5, "center_y": 0.5}
        size_hint_x: None
        width: 300
    MDRaisedButton:
        text: "Login"
        pos_hint: {"center_x": 0.5, "center_y": 0.4}
        on_release:
            app.login_user(username.text, password.text)
    MDRaisedButton:
        text: "Login with Face"
        pos_hint: {"center_x": 0.5, "center_y": 0.3}
        on_release:
            app.login_with_face()
    MDRaisedButton:
        text: "Register"
        pos_hint: {"center_x": 0.5, "center_y": 0.2}
        on_release:
            root.manager.current = 'register'

<RegistrationPage>:
    name: 'register'
    MDTextField:
        id: reg_username
        hint_text: "Username"
        pos_hint: {"center_x": 0.5, "center_y": 0.7}
        size_hint_x: None
        width: 300
    MDTextField:
        id: reg_password
        hint_text: "Password"
        password: True
        pos_hint: {"center_x": 0.5, "center_y": 0.6}
        size_hint_x: None
        width: 300
    MDRaisedButton:
        text: "Upload ID Card Photo"
        pos_hint: {"center_x": 0.5, "center_y": 0.5}
        on_release:
            app.file_manager_open()
    MDRaisedButton:
        text: "Take Face Photo"
        pos_hint: {"center_x": 0.5, "center_y": 0.4}
        on_release:
            app.capture_face_photo(reg_username.text)
    MDRaisedButton:
        text: "Register"
        pos_hint: {"center_x": 0.5, "center_y": 0.3}
        on_release:
            app.register_user(reg_username.text, reg_password.text)
    MDRaisedButton:
        text: "Back"
        pos_hint: {"center_x": 0.5, "center_y": 0.2}
        on_release:
            root.manager.current = 'login'

<HomePage>:
    name: 'home'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(48)
        spacing: dp(16)
        MDLabel:
            id: username_label
            text: 'Username:'
            halign: 'center'
            font_style: 'H4'
        Widget:
        MDRaisedButton:
            text: 'Logout'
            pos_hint: {'center_x': 0.5}
            on_release:
                app.root.current = 'login'
                app.root.get_screen('home').stop_face_recognition()
'''
if __name__ == '__main__':
    app = MyApp()
    app.run()
