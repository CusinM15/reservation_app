#!/usr/bin/env python3
"""
Bulk import users from .docx files.
Usage: python scripts/import_users.py <folder_path>
"""
import sys
import os
import random
import string
from docx import Document
from passlib.context import CryptContext

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db
from app.models import User, RoleEnum

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def generate_password(length=10):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def parse_docx(filepath):
    doc = Document(filepath)
    users = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if ':' in text:
            parts = text.split(':', 1)
            username = parts[0].strip()
            password = parts[1].strip() if len(parts) > 1 and parts[1].strip() else None
            if username:
                users.append((username, password))
    return users

def import_users_from_file(filepath, db):
    print(f"\n--- {os.path.basename(filepath)} ---")
    users = parse_docx(filepath)
    created = []
    for username, password in users:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"⚠️  {username}: že obstaja (preskočeno)")
            continue
        
        if not password:
            password = generate_password()
            print(f"✅ {username}: geslo = {password} (avtomatsko generirano)")
        else:
            print(f"✅ {username}: geslo = {password}")
        
        hashed = pwd_context.hash(password)
        user = User(username=username, password_hash=hashed, role=RoleEnum.teacher, is_active=True)
        db.add(user)
        created.append(username)
    
    db.commit()
    return created

def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/import_users.py <folder_path>")
        sys.exit(1)
    
    folder_path = sys.argv[1]
    if not os.path.isdir(folder_path):
        print(f"Napaka: {folder_path} ni veljavna mapa")
        sys.exit(1)
    
    init_db()
    db = SessionLocal()
    
    docx_files = [f for f in os.listdir(folder_path) if f.endswith('.docx')]
    if not docx_files:
        print("Ni .docx datotek v mapi")
        sys.exit(0)
    
    total_created = 0
    for filename in docx_files:
        filepath = os.path.join(folder_path, filename)
        created = import_users_from_file(filepath, db)
        total_created += len(created)
    
    print(f"\nSkupaj ustvarjenih uporabnikov: {total_created}")
    db.close()

if __name__ == "__main__":
    main()
