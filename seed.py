from app import app
from models import db, User

with app.app_context():
    db.create_all()

    if not User.query.filter_by(email="faiz@gmail.com").first():
        user = User(email="faiz@gmail.com")
        user.set_password("faiz123")

        db.session.add(user)
        db.session.commit()
        print("Seeder berhasil: User faiz@gmail.com ditambahkan.")
    else:
        print("Seeder dilewati: User sudah ada.")