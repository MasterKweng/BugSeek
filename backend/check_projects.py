import sys
import os
import warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.orm import sessionmaker
from app.db.base import Base, Project, Version, ApiEndpointGroup
from app.db.session import engine

Session = sessionmaker(bind=engine)
session = Session()

print("Projects:")
projects = session.query(Project).all()
for p in projects:
    print(f"  - {p.name} (id={p.id})")
    versions = session.query(Version).filter(Version.project_id == p.id).all()
    for v in versions:
        print(f"    - Version ID: {v.id}")

print("\nEndpoint Groups:")
groups = session.query(ApiEndpointGroup).all()
for g in groups:
    print(f"  - {g.name} (id={g.id}, project_id={g.project_id})")

session.close()
