import sys
import os
import warnings
warnings.filterwarnings('ignore')
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy.orm import sessionmaker
from app.db.base import Base, ApiEndpointGroup, ApiEndpoint, VersionEndpoint
from app.db.session import engine
from datetime import datetime

Session = sessionmaker(bind=engine)
session = Session()

project_id = 2  # TEST project
version_id = 4  # Version for TEST project

# Check if test module group exists
group = session.query(ApiEndpointGroup).filter(
    ApiEndpointGroup.project_id == project_id,
    ApiEndpointGroup.name == "测试模块"
).first()

if not group:
    print("Test module group not found!")
    session.close()
    sys.exit(1)

print(f"Found group: {group.name} (id={group.id})")

# Check if endpoint exists in this group
endpoint = session.query(ApiEndpoint).filter(
    ApiEndpoint.group_id == group.id
).first()

if endpoint:
    print(f"Endpoint already exists in group: {endpoint.path}")
else:
    # Create a test endpoint
    endpoint = ApiEndpoint(
        group_id=group.id,
        project_id=project_id,
        path="/api/test",
        method="GET",
        summary="测试接口",
        description="用于测试模块分析的接口",
        tags=["test"],
        request_schema=None,
        response_schema=None
    )
    session.add(endpoint)
    session.commit()
    session.refresh(endpoint)
    print(f"Created endpoint: {endpoint.path} (id={endpoint.id})")

    # Link endpoint to version
    version_endpoint = VersionEndpoint(
        version_id=version_id,
        endpoint_id=endpoint.id
    )
    session.add(version_endpoint)
    session.commit()
    print(f"Linked endpoint to version {version_id}")

session.close()
print("Test data created successfully!")