from fastapi import (
    FastAPI,
    File,
    UploadFile,
    HTTPException,
    Depends,
    Request,
    Form
)

from sqlmodel import Session, select

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from datetime import datetime
import httpx
import os
import aiofiles
import json
import uuid
from typing import Optional

from database.session import get_session

from models.user import User, UserCreate, UserResponse
from models.document import Document, DocumentCreate, DocumentUpdate
from models.webhook import Webhook

from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_current_admin,
    get_current_manager
)

from services.weather import get_weather
from fastapi.security import OAuth2PasswordRequestForm
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="SendIt API",
    version="1.0.0"
)

from database.session import create_db_and_tables

@app.on_event("startup")
def on_startup():
    create_db_and_tables()
# ============================================================
# CONFIGURATION
# ============================================================

UPLOAD_DIR = "uploads"

os.makedirs(
    UPLOAD_DIR,
    exist_ok=True
)


MAX_FILE_SIZE = int(
    os.getenv(
        "MAX_UPLOAD_SIZE",
        5 * 1024 * 1024
    )
)


ALLOWED_EXTENSIONS = [
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".docx"
]


# ============================================================
# RATE LIMITING
# ============================================================

limiter = Limiter(
    key_func=get_remote_address
)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)
# ============================================================
# AUTHENTICATION ENDPOINTS
# ============================================================

@app.post("/register", response_model=UserResponse, status_code=201)
@limiter.limit("5/minute")
def register_user(
    request: Request,
    user_data: UserCreate,
    session: Session = Depends(get_session)
):
    """
    Register a new user.
    """

    existing = session.exec(
        select(User).where(
            User.username == user_data.username
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Username already exists"
        )

    existing = session.exec(
        select(User).where(
            User.email == user_data.email
        )
    ).first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail="Email already exists"
        )
    print(user_data)
    print(user_data.password)

    

    db_user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role
    )

    session.add(db_user)
    session.commit()
    session.refresh(db_user)

    return db_user


@app.post("/login")
@limiter.limit("5/minute")
def login_user(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
):
    """
    Login and receive an access token.
    """

    user = session.exec(
        select(User).where(
            User.username == form_data.username
        )
    ).first()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not verify_password(
        form_data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="User is inactive"
        )

    user.last_login = datetime.utcnow()
    session.commit()

    token = create_access_token(
        {"sub": user.username}
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 30 * 60,
        "username": user.username,
        "role": user.role
    }


# ============================================================
# FILE UPLOAD ENDPOINTS
# ============================================================



def validate_file(file: UploadFile) -> tuple:
    """
    Validate file size and type.
    Returns (is_valid, error_message)
    """

    file_extension = os.path.splitext(
        file.filename
    )[1].lower()


    if file_extension not in ALLOWED_EXTENSIONS:

        return (
            False,
            f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )


    return True, ""

async def send_webhook_notification(
    event_type: str,
    document: Document,
    session: Session
):
    """
    Send webhook notifications for document events.
    """

    webhooks = session.exec(
        select(Webhook).where(
            Webhook.event_type == event_type,
            Webhook.is_active == True
        )
    ).all()

    payload = {
        "event": event_type,
        "document_id": document.id,
        "filename": document.original_filename,
        "status": document.status,
        "city": document.city,
        "country": document.country
    }

    async with httpx.AsyncClient() as client:
        for webhook in webhooks:
            try:
                await client.post(
                    webhook.webhook_url,
                    json=payload,
                    timeout=10
                )
            except Exception as e:
                print(f"Webhook failed: {e}")









@app.post("/documents/upload")
@limiter.limit("10/hour")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    city: str = Form(...),
    description: Optional[str] = Form(None),
    country: str = Form("Kenya"),
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    # Read uploaded file
    contents = await file.read()
    file_size = len(contents)

    # Create upload folder if it does not exist
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)

    # Generate unique filename
    filename = file.filename or "uploaded_file"
    safe_filename = f"{uuid.uuid4()}_{filename}"

    # Create full file path
    file_path = os.path.join(upload_dir, safe_filename)

    # Save file to storage
    async with aiofiles.open(file_path, "wb") as out_file:
        await out_file.write(contents)

    # Check if document already exists to determine version
    existing_document = session.exec(
        select(Document)
        .where(Document.original_filename == file.filename)
        .order_by(Document.version.desc())
    ).first()

    version = 1

    if existing_document:
        version = existing_document.version + 1

    # Create database record
    document = Document(
        filename=safe_filename,
        original_filename=file.filename,
        version=version,
        file_size=file_size,
        file_type=file.content_type or "application/octet-stream",
        city=city,
        country=country,
        description=description,
        uploader_id=current_user.id,
        file_path=file_path,
        status="processing"
    )

    session.add(document)
    session.commit()
    session.refresh(document)

    try:
        weather_data = await get_weather(city, country)

        if weather_data and "error" not in weather_data:
            document.weather_data = json.dumps(weather_data)
            document.weather_fetched_at = datetime.utcnow()
            document.status = "enriched"

            session.commit()

            await send_webhook_notification(
                "document.enriched",
                document,
                session
            )

        else:
            document.status = "uploaded"

            session.commit()

            await send_webhook_notification(
                "document.uploaded",
                document,
                session
            )

    except Exception as e:
        print(f"Weather API error: {e}")

        document.status = "uploaded"
        session.commit()

        await send_webhook_notification(
            "document.uploaded",
            document,
            session
        )

    return {
        "message": "Document uploaded successfully",
        "document_id": document.id,
        "filename": document.original_filename,
        "status": document.status
    }

@app.get("/documents")
@limiter.limit("30/minute")
def list_documents(

    request: Request,

    status: Optional[str] = None,

    city: Optional[str] = None,

    current_user: User = Depends(get_current_user),

    session: Session = Depends(get_session)

):

    """
    List all documents with optional filters.
    """


    query = select(Document)



    # Managers and admins see all documents
    # Staff see only their own

    if current_user.role not in [
        "admin",
        "manager"
    ]:

        query = query.where(
            Document.uploader_id == current_user.id
        )



    if status:

        query = query.where(
            Document.status == status
        )


    if city:

        query = query.where(
            Document.city == city
        )


    return session.exec(query).all()




@app.get("/documents/{document_id}")
@limiter.limit("30/minute")
def get_document(

    request: Request,

    document_id: int,

    current_user: User = Depends(get_current_user),

    session: Session = Depends(get_session)

):

    """
    Get a specific document.
    """


    document = session.get(
        Document,
        document_id
    )


    if not document:

        raise HTTPException(
            404,
            "Document not found"
        )



    if (
        current_user.role not in ["admin", "manager"]
        and document.uploader_id != current_user.id
    ):

        raise HTTPException(
            403,
            "Access denied"
        )


    return document




@app.delete("/documents/{document_id}")
def delete_document(

    document_id: int,

    current_user: User = Depends(get_current_manager),

    session: Session = Depends(get_session)

):

    """
    Delete a document.
    Managers and admins only.
    """


    document = session.get(
        Document,
        document_id
    )


    if not document:

        raise HTTPException(
            404,
            "Document not found"
        )



    # Delete physical file

    if os.path.exists(
        document.file_path
    ):

        os.remove(
            document.file_path
        )



    session.delete(document)

    session.commit()


    return {
        "message": "Document deleted successfully"
    }

# ============================================================
# DOCUMENT ENRICHMENT ENDPOINT
# ============================================================


@app.post("/documents/{document_id}/enrich")
@limiter.limit("5/minute")
async def enrich_document(

    request: Request,

    document_id: int,

    current_user: User = Depends(get_current_manager),

    session: Session = Depends(get_session)

):

    """
    Manually trigger weather enrichment for a document.
    Useful for documents that failed initial enrichment.
    """


    document = session.get(
        Document,
        document_id
    )


    if not document:

        raise HTTPException(
            404,
            "Document not found"
        )



    if document.status == "enriched":

        return {
            "message": "Document already enriched"
        }



    weather_data = await get_weather(
        document.city,
        document.country
    )



    if weather_data:


        document.weather_data = json.dumps(
            weather_data
        )


        document.weather_fetched_at = datetime.utcnow()


        document.status = "enriched"


        session.commit()
        await send_webhook_notification(
    "document.enriched",
    document,
    session
)


        return {

            "message": "Document enriched successfully",

            "weather": weather_data

        }



    else:


        document.status = "failed"


        session.commit()


        raise HTTPException(

            500,

            "Failed to enrich document with weather data"

        )





@app.get("/documents/{document_id}/weather")
@limiter.limit("10/minute")
def get_document_weather(

    request: Request,

    document_id: int,

    current_user: User = Depends(get_current_user),

    session: Session = Depends(get_session)

):

    """
    Get the weather data associated with a document.
    """



    document = session.get(
        Document,
        document_id
    )


    if not document:

        raise HTTPException(
            404,
            "Document not found"
        )



    # Staff can only view their own documents

    if (
        current_user.role not in ["admin", "manager"]
        and document.uploader_id != current_user.id
    ):

        raise HTTPException(
            403,
            "Access denied"
        )



    if not document.weather_data:

        raise HTTPException(
            404,
            "No weather data available for this document"
        )



    return {

        "document_id": document.id,

        "city": document.city,

        "country": document.country,

        "weather": json.loads(
            document.weather_data
        )

    }
# ============================================================
# DOCUMENT SEARCH WITH FILTERS
# ============================================================


@app.get("/documents/search")
@limiter.limit("20/minute")
def search_documents(

    request: Request,

    q: Optional[str] = None,

    city: Optional[str] = None,

    status: Optional[str] = None,

    date_from: Optional[datetime] = None,

    date_to: Optional[datetime] = None,

    current_user: User = Depends(get_current_user),

    session: Session = Depends(get_session)

):

    """
    Search documents with multiple filters.
    """


    query = select(Document)



    # Role-based access
    # Managers/Admins see all documents
    # Staff see only their own documents

    if current_user.role not in [
        "admin",
        "manager"
    ]:

        query = query.where(
            Document.uploader_id == current_user.id
        )



    # Search by filename or description

    if q:

        query = query.where(

            (Document.original_filename.contains(q))
            |
            (Document.description.contains(q))

        )



    # Filter by city

    if city:

        query = query.where(
            Document.city == city
        )



    # Filter by status

    if status:

        query = query.where(
            Document.status == status
        )



    # Filter by upload date range

    if date_from:

        query = query.where(
            Document.uploaded_at >= date_from
        )



    if date_to:

        query = query.where(
            Document.uploaded_at <= date_to
        )



    documents = session.exec(
        query
    ).all()



    return documents
# ============================================================
# WEBHOOK REGISTRATION
# ============================================================





@app.post("/webhooks/register")
def register_webhook(

    webhook_url: str,

    event_type: str,

    current_user: User = Depends(get_current_admin),

    session: Session = Depends(get_session)

):

    """
    Register a webhook for document events.
    """


    allowed_events = [
        "document.enriched",
        "document.uploaded"
    ]


    if event_type not in allowed_events:

      raise HTTPException(
        status_code=400,
        detail="Invalid event type"
    )



    webhook = Webhook(

        webhook_url=webhook_url,

        event_type=event_type

    )


    session.add(webhook)

    session.commit()

    session.refresh(webhook)


    return {

        "message": "Webhook registered successfully",

        "webhook_id": webhook.id

    }