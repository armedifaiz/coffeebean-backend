from flask import Flask, request, jsonify, send_from_directory
from models import db, bcrypt, User, RiwayatPrediksi, blacklist
from utils import is_valid_email, is_valid_password
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, get_jwt, decode_token
from config import Config
from datetime import timedelta, datetime, timezone
import tensorflow as tf
from tensorflow.keras.applications import EfficientNetB0
from tensorflow.keras.applications.efficientnet import preprocess_input
from tensorflow.keras.preprocessing import image as keras_image
import numpy as np
import joblib
import json
import os
import uuid

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
bcrypt.init_app(app)
jwt = JWTManager(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load EfficientNet once
efficientnet_model = EfficientNetB0(weights='imagenet', include_top=False, pooling='avg')

# Load KNN and label map once
knn_model = joblib.load('split_internet_1_bestmodel/knn_model.pkl')
with open('split_internet_1_bestmodel/label.json', 'r') as f:
    label_map = json.load(f)

def extract_features_efficientnet(img_path):
    img = keras_image.load_img(img_path, target_size=(224, 224))
    img_array = keras_image.img_to_array(img)
    img_array = np.expand_dims(img_array, axis=0)
    img_array = preprocess_input(img_array)
    features = efficientnet_model.predict(img_array)
    return features.flatten().reshape(1, -1)

def print_token_expiry(access_token):
    try:
        decoded = decode_token(access_token)
        exp_timestamp = decoded.get("exp")
        if exp_timestamp:
            exp_datetime = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
            now = datetime.now(timezone.utc)
            remaining = exp_datetime - now
            print(f"[TOKEN DEBUG] Token expires at: {exp_datetime} UTC")
            print(f"[TOKEN DEBUG] Remaining time: {remaining}")
        else:
            print("[TOKEN DEBUG] No 'exp' claim found in token.")
    except Exception as e:
        print(f"[TOKEN DEBUG] Failed to decode token: {e}")

@jwt.token_in_blocklist_loader
def check_if_token_in_blacklist(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return jti in blacklist

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({
        "success": False,
        "message": "Terjadi kesalahan pada server.",
        "error": str(e)
    }), 500

@app.route('/')
def index():
    return jsonify({"message": "Server running"}), 200

@app.route("/register", methods=["POST"])
def register():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"success": False, "message": "Email dan password wajib diisi."}), 400
        if not is_valid_email(email):
            return jsonify({"success": False, "message": "Format email tidak valid."}), 400
        if not is_valid_password(password):
            return jsonify({"success": False, "message": "Password minimal 6 karakter."}), 400

        if User.query.filter_by(email=email).first():
            return jsonify({"success": False, "message": "Email sudah terdaftar."}), 400

        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return jsonify({"success": True, "message": "Registrasi berhasil."}), 201

    except Exception as e:
        return jsonify({"success": False, "message": "Gagal melakukan registrasi.", "error": str(e)}), 500

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()
        email = data.get("email")
        password = data.get("password")
        remember_me = data.get("remember_me", False)

        if not email or not password:
            return jsonify({"success": False, "message": "Email dan password wajib diisi."}), 400

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            expires = timedelta(days=7) if remember_me else timedelta(hours=1)
            access_token = create_access_token(identity=str(user.id), expires_delta=expires)
            print_token_expiry(access_token)
            return jsonify({
                "success": True,
                "message": "Login berhasil.",
                "access_token": access_token,
                "remember_me": remember_me
            }), 200
        else:
            return jsonify({"success": False, "message": "Email atau password salah."}), 401

    except Exception as e:
        return jsonify({"success": False, "message": "Gagal melakukan login.", "error": str(e)}), 500

@app.route("/logout", methods=["POST"])
@jwt_required()
def logout():
    try:
        jti = get_jwt()["jti"]
        blacklist.add(jti)
        return jsonify({"success": True, "message": "Logout berhasil, token telah di-blacklist."}), 200
    except Exception as e:
        return jsonify({"success": False, "message": "Gagal melakukan logout.", "error": str(e)}), 500

@app.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if user:
            return jsonify({
                "success": True,
                "message": f"Hello {user.email}, Anda berhasil mengakses endpoint terlindungi."
            }), 200
        else:
            return jsonify({"success": False, "message": "User tidak ditemukan."}), 404
    except Exception as e:
        return jsonify({"success": False, "message": "Gagal mengakses data.", "error": str(e)}), 500

@app.route('/predict', methods=['POST'])
@jwt_required()
def predict():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user:
            return jsonify({"success": False, "message": "User tidak ditemukan."}), 404

        if 'file' not in request.files:
            return jsonify({"success": False, "message": "File tidak ditemukan."}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "Nama file kosong."}), 400

        unique_filename = str(uuid.uuid4()) + ".jpg"
        save_path = os.path.join(UPLOAD_FOLDER, unique_filename)
        file.save(save_path)

        features = extract_features_efficientnet(save_path)
        pred_index = int(knn_model.predict(features)[0])
        pred_label = label_map[str(pred_index)]
        display_label = "Bukan Biji Kopi" if pred_label == "non_coffee" else pred_label.capitalize()

        riwayat = RiwayatPrediksi(
            id_user=user.id,
            path_gambar=f"{UPLOAD_FOLDER}/{unique_filename}",
            label_prediksi=display_label
        )
        db.session.add(riwayat)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Prediksi berhasil.",
            "prediksi": display_label,
            "path_gambar": f"{UPLOAD_FOLDER}/{unique_filename}"
        }), 200

    except Exception as e:
        return jsonify({"success": False, "message": "Gagal melakukan prediksi.", "error": str(e)}), 500

@app.route('/riwayat', methods=['GET'])
@jwt_required()
def get_riwayat():
    try:
        user_id = get_jwt_identity()
        riwayats = RiwayatPrediksi.query.filter_by(id_user=user_id).order_by(RiwayatPrediksi.waktu_prediksi.desc()).all()
        result = []
        for r in riwayats:
            display_label = "Bukan Biji Kopi" if r.label_prediksi == "non_coffee" else r.label_prediksi.capitalize()
            result.append({
                "id": r.id,
                "path_gambar": r.path_gambar,
                "label_prediksi": r.label_prediksi,
                "display_label": display_label,
                "waktu_prediksi": r.waktu_prediksi.isoformat()
            })
        return jsonify({"success": True, "riwayat": result}), 200
    except Exception as e:
        return jsonify({"success": False, "message": "Gagal mengambil riwayat", "error": str(e)}), 500

@app.route('/riwayat/<int:riwayat_id>', methods=['DELETE'])
@jwt_required()
def delete_riwayat(riwayat_id):
    try:
        user_id = get_jwt_identity()
        riwayat = RiwayatPrediksi.query.filter_by(id=riwayat_id, id_user=user_id).first()

        if not riwayat:
            return jsonify({"success": False, "message": "Riwayat tidak ditemukan atau Anda tidak memiliki akses."}), 404

        if riwayat.path_gambar and os.path.exists(riwayat.path_gambar):
            os.remove(riwayat.path_gambar)

        db.session.delete(riwayat)
        db.session.commit()

        return jsonify({"success": True, "message": "Riwayat berhasil dihapus."}), 200

    except Exception as e:
        return jsonify({"success": False, "message": "Gagal menghapus riwayat.", "error": str(e)}), 500

@app.route('/uploads/<path:filename>')
def serve_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

with app.app_context():
    db.create_all()