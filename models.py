from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from datetime import datetime

db = SQLAlchemy()
bcrypt = Bcrypt()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

class RiwayatPrediksi(db.Model):
    __tablename__ = 'riwayat_prediksi'

    id = db.Column(db.Integer, primary_key=True)
    id_user = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    path_gambar = db.Column(db.String(255), nullable=False)
    label_prediksi = db.Column(db.String(120), nullable=False)
    waktu_prediksi = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('riwayat_prediksi', lazy=True))

blacklist = set()