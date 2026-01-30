import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.orm import sessionmaker
from app.db.base import Base, User
from app.db.session import engine
import bcrypt

Session = sessionmaker(bind=engine)
session = Session()

# Check if test user exists
user = session.query(User).filter(User.username == 'testuser').first()

if user:
    # Reset password
    hashed = bcrypt.hashpw(b'test123', bcrypt.gensalt()).decode('utf-8')
    user.password_hash = hashed
    session.commit()
    print(f"Reset password for existing user: {user.username}")
else:
    # Create new user
    hashed = bcrypt.hashpw(b'test123', bcrypt.gensalt()).decode('utf-8')
    user = User(
        username='testuser',
        email='testuser@test.com',
        password_hash=hashed,
        nickname='Test User'
    )
    session.add(user)
    session.commit()
    print(f"Created new user: {user.username}")

session.close()