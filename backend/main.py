import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlmodel import Field, SQLModel, Session, create_engine, select


DATABASE_URL = "sqlite:///db.sqlite3"
JWT_SECRET = os.getenv("JWT_SECRET", "hackathon-local-secret")
JWT_EXPIRE_HOURS = 72
PIC_DIR = "pic"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    password_hash: str = ""
    points: int = 20


class MemberCreate(SQLModel):
    name: str
    email: str


class AuthRequest(SQLModel):
    name: str = ""
    email: str
    password: str


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="member.id")
    title: str
    genre: str
    author: str
    publication_year: int
    condition: str
    exchange_mode: str = "permanent"
    available: bool = True
    picture_path: str = ""


class BookCreate(SQLModel):
    owner_id: int
    title: str
    genre: str
    author: str
    publication_year: int
    condition: str
    exchange_mode: str = "permanent"


class BookUpdate(SQLModel):
    owner_id: int
    title: str
    genre: str
    author: str
    publication_year: int
    condition: str
    exchange_mode: str = "permanent"


class ExchangeTransaction(SQLModel, table=True):
    __tablename__ = "transactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    owner_id: int = Field(foreign_key="member.id")
    exchange_mode: str
    requester_id: Optional[int] = Field(default=None, foreign_key="member.id")
    courier_id: Optional[int] = Field(default=None, foreign_key="member.id")
    owner_confirmed: bool = False
    requester_confirmed: bool = False
    locked: bool = False
    points_applied: bool = False


class TransactionCreate(SQLModel):
    book_id: int


class Message(SQLModel, table=True):
    __tablename__ = "messages"

    message_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="member.id")
    transaction_id: int = Field(foreign_key="transactions.id")
    message: str
    applied_role: str
    accepted: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApplyRequest(SQLModel):
    user_id: int
    applied_role: str
    message: str


class ChatMessageCreate(SQLModel):
    user_id: int
    message: str


class RoleDecision(SQLModel):
    owner_id: int
    user_id: int
    applied_role: str


class LeaveRequest(SQLModel):
    user_id: int


class MeetingConfirm(SQLModel):
    transaction_id: int
    user_1_id: int
    user_2_id: int


app = FastAPI(title="Book Exchange Club Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs(PIC_DIR, exist_ok=True)
app.mount("/pic", StaticFiles(directory=PIC_DIR), name="pic")


def get_member(session: Session, member_id: int) -> Member:
    """
    tl;dr: Load one member or stop the request with a 404 error.
    input:
    * session: active database session
    * member_id: id of the member to load
    output:
    * matching Member record
    """
    member = session.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


def get_book(session: Session, book_id: int) -> Book:
    """
    tl;dr: Load one book or stop the request with a 404 error.
    input:
    * session: active database session
    * book_id: id of the book to load
    output:
    * matching Book record
    """
    book = session.get(Book, book_id)
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return book


def save_book_picture(picture: Optional[UploadFile]) -> str:
    """
    tl;dr: Save an uploaded book picture into the local pic folder.
    input:
    * picture: optional uploaded image file
    output:
    * public picture path or empty string
    """
    if picture is None or not picture.filename:
        return ""
    if picture.content_type and not picture.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Picture must be an image file")

    os.makedirs(PIC_DIR, exist_ok=True)
    extension = os.path.splitext(picture.filename)[1].lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        extension = ".png"
    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(8)}{extension}"
    disk_path = os.path.join(PIC_DIR, filename)
    with open(disk_path, "wb") as output:
        shutil.copyfileobj(picture.file, output)
    return f"/pic/{filename}"


def get_transaction(session: Session, transaction_id: int) -> ExchangeTransaction:
    """
    tl;dr: Load one exchange transaction or stop the request with a 404 error.
    input:
    * session: active database session
    * transaction_id: id of the transaction to load
    output:
    * matching ExchangeTransaction record
    """
    transaction = session.get(ExchangeTransaction, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


def get_member_by_email(session: Session, email: str) -> Optional[Member]:
    """
    tl;dr: Load one member by email address.
    input:
    * session: active database session
    * email: email address to look up
    output:
    * matching Member record or None
    """
    return session.exec(select(Member).where(Member.email == email.strip().lower())).first()


def hash_password(password: str) -> str:
    """
    tl;dr: Hash a password with a random salt.
    input:
    * password: plain text password
    output:
    * salt and password hash string
    """
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"{salt}:{digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """
    tl;dr: Check a plain password against a stored password hash.
    input:
    * password: plain text password
    * password_hash: stored salt and hash string
    output:
    * True when the password matches
    """
    if ":" not in password_hash:
        return False
    salt, expected = password_hash.split(":", 1)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return hmac.compare_digest(digest.hex(), expected)


def base64url_encode(data: bytes) -> str:
    """
    tl;dr: Encode bytes using JWT base64url format.
    input:
    * data: raw bytes to encode
    output:
    * base64url string without padding
    """
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def base64url_decode(data: str) -> bytes:
    """
    tl;dr: Decode a JWT base64url string.
    input:
    * data: base64url string without padding
    output:
    * decoded bytes
    """
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(member: Member) -> str:
    """
    tl;dr: Create a signed JWT for a member.
    input:
    * member: authenticated member
    output:
    * signed access token
    """
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": member.id,
        "email": member.email,
        "exp": int((datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)).timestamp()),
    }
    signing_input = ".".join(
        [
            base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    return f"{signing_input}.{base64url_encode(signature)}"


def read_access_token(token: str) -> dict:
    """
    tl;dr: Validate a signed JWT and return its payload.
    input:
    * token: signed access token
    output:
    * decoded token payload
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=401, detail="Invalid token")
    signing_input = ".".join(parts[:2])
    expected = hmac.new(JWT_SECRET.encode("utf-8"), signing_input.encode("utf-8"), hashlib.sha256).digest()
    actual = base64url_decode(parts[2])
    if not hmac.compare_digest(actual, expected):
        raise HTTPException(status_code=401, detail="Invalid token")
    payload = json.loads(base64url_decode(parts[1]))
    if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="Token expired")
    return payload


def get_current_member(session: Session, authorization: str) -> Member:
    """
    tl;dr: Resolve the current member from an Authorization header.
    input:
    * session: active database session
    * authorization: Bearer token header value
    output:
    * authenticated Member record
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    payload = read_access_token(authorization.removeprefix("Bearer ").strip())
    member = session.get(Member, payload.get("sub"))
    if not member:
        raise HTTPException(status_code=401, detail="Member not found")
    return member


def auth_response(member: Member) -> dict:
    """
    tl;dr: Build the auth response used by login and register.
    input:
    * member: authenticated member
    output:
    * token and member dictionary
    """
    return {
        "access_token": create_access_token(member),
        "token_type": "bearer",
        "member": member_to_dict(member, set()),
    }


def get_courier_member_ids(session: Session) -> set[int]:
    """
    tl;dr: Return members who have been assigned as couriers in transactions.
    input:
    * session: active database session
    output:
    * set of member ids used as transaction couriers
    """
    courier_ids = session.exec(select(ExchangeTransaction.courier_id)).all()
    return {courier_id for courier_id in courier_ids if courier_id is not None}


def member_to_dict(member: Member, courier_member_ids: set[int]) -> dict:
    """
    tl;dr: Convert a member into a frontend-friendly dictionary with derived courier status.
    input:
    * member: Member database record
    * courier_member_ids: member ids used as transaction couriers
    output:
    * dictionary with member fields and derived courier status
    """
    return {
        "id": member.id,
        "name": member.name,
        "email": member.email,
        "points": member.points,
        "is_courier": member.id in courier_member_ids,
    }


def get_table_columns(connection: Connection, table_name: str) -> set[str]:
    """
    tl;dr: Return the column names currently present in a database table.
    input:
    * connection: active database connection
    * table_name: table to inspect
    output:
    * set of column names in the table
    """
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").mappings().all()
    return {row["name"] for row in rows}


def table_exists(connection: Connection, table_name: str) -> bool:
    """
    tl;dr: Check whether a SQLite table exists.
    input:
    * connection: active database connection
    * table_name: table to inspect
    output:
    * True when the table exists
    """
    row = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type = 'table' AND name = :table_name"),
        {"table_name": table_name},
    ).first()
    return row is not None


def ensure_open_chatbox(transaction: ExchangeTransaction) -> None:
    """
    tl;dr: Stop changes to chatbox membership after the first physical handoff.
    input:
    * transaction: transaction whose chatbox may be locked
    output:
    * None
    """
    if transaction.locked:
        raise HTTPException(status_code=400, detail="Chatbox is locked")


def migrate_schema() -> None:
    """
    tl;dr: Apply small schema updates for older prototype databases.
    output:
    * None
    """
    with engine.begin() as connection:
        member_columns = get_table_columns(connection, "member")
        if "contact" in member_columns and "email" not in member_columns:
            connection.execute(text("ALTER TABLE member ADD COLUMN email VARCHAR NOT NULL DEFAULT ''"))
            connection.execute(text("UPDATE member SET email = contact WHERE email IS NULL OR email = ''"))
        elif "contact" in member_columns and "email" in member_columns:
            connection.execute(text("UPDATE member SET email = contact WHERE email IS NULL OR email = ''"))
        if "contact" in member_columns:
            connection.execute(text("ALTER TABLE member DROP COLUMN contact"))
        member_columns = get_table_columns(connection, "member")
        if "password_hash" not in member_columns:
            connection.execute(text("ALTER TABLE member ADD COLUMN password_hash VARCHAR NOT NULL DEFAULT ''"))

        book_columns = get_table_columns(connection, "book")
        if book_columns and "picture_path" not in book_columns:
            connection.execute(text("ALTER TABLE book ADD COLUMN picture_path VARCHAR NOT NULL DEFAULT ''"))

        if table_exists(connection, "message"):
            if table_exists(connection, "messages"):
                connection.execute(
                    text(
                        """
                        INSERT OR IGNORE INTO messages (
                            message_id,
                            user_id,
                            transaction_id,
                            message,
                            applied_role,
                            accepted,
                            timestamp
                        )
                        SELECT
                            message_id,
                            user_id,
                            transaction_id,
                            message,
                            applied_role,
                            accepted,
                            timestamp
                        FROM message
                        """
                    )
                )
                connection.execute(text("DROP TABLE message"))
            else:
                connection.execute(text("ALTER TABLE message RENAME TO messages"))

        if table_exists(connection, "exchangetransaction"):
            legacy_transaction_columns = get_table_columns(connection, "exchangetransaction")
            if table_exists(connection, "transactions"):
                requester_select = "requester_id" if "requester_id" in legacy_transaction_columns else "NULL"
                courier_select = "courier_id" if "courier_id" in legacy_transaction_columns else "NULL"
                owner_confirmed_select = "owner_confirmed" if "owner_confirmed" in legacy_transaction_columns else "0"
                requester_confirmed_select = (
                    "requester_confirmed" if "requester_confirmed" in legacy_transaction_columns else "0"
                )
                points_applied_select = "points_applied" if "points_applied" in legacy_transaction_columns else "0"
                locked_select = "locked" if "locked" in legacy_transaction_columns else "0"
                connection.execute(
                    text(
                        f"""
                        INSERT OR IGNORE INTO transactions (
                            id,
                            book_id,
                            owner_id,
                            exchange_mode,
                            requester_id,
                            courier_id,
                            owner_confirmed,
                            requester_confirmed,
                            locked,
                            points_applied
                        )
                        SELECT
                            id,
                            book_id,
                            owner_id,
                            exchange_mode,
                            {requester_select},
                            {courier_select},
                            {owner_confirmed_select},
                            {requester_confirmed_select},
                            {locked_select},
                            {points_applied_select}
                        FROM exchangetransaction
                        """
                    )
                )
                connection.execute(text("DROP TABLE exchangetransaction"))
            else:
                connection.execute(text("ALTER TABLE exchangetransaction RENAME TO transactions"))

        transaction_columns = get_table_columns(connection, "transactions")
        if not transaction_columns:
            return
        needs_transaction_rebuild = (
            "delivery_mode" in transaction_columns
            or "note" in transaction_columns
            or "status" in transaction_columns
            or "locked" not in transaction_columns
        )
        if not needs_transaction_rebuild:
            return

        connection.execute(text("ALTER TABLE transactions RENAME TO transactions_old"))
        connection.execute(
            text(
                """
                CREATE TABLE transactions (
                    id INTEGER NOT NULL,
                    book_id INTEGER NOT NULL,
                    owner_id INTEGER NOT NULL,
                    exchange_mode VARCHAR NOT NULL,
                    requester_id INTEGER,
                    courier_id INTEGER,
                    owner_confirmed BOOLEAN NOT NULL,
                    requester_confirmed BOOLEAN NOT NULL,
                    locked BOOLEAN NOT NULL,
                    points_applied BOOLEAN NOT NULL,
                    PRIMARY KEY (id),
                    FOREIGN KEY(book_id) REFERENCES book (id),
                    FOREIGN KEY(owner_id) REFERENCES member (id),
                    FOREIGN KEY(requester_id) REFERENCES member (id),
                    FOREIGN KEY(courier_id) REFERENCES member (id)
                )
                """
            )
        )
        requester_select = "requester_id" if "requester_id" in transaction_columns else "NULL"
        courier_select = "courier_id" if "courier_id" in transaction_columns else "NULL"
        owner_confirmed_select = "owner_confirmed" if "owner_confirmed" in transaction_columns else "0"
        requester_confirmed_select = "requester_confirmed" if "requester_confirmed" in transaction_columns else "0"
        points_applied_select = "points_applied" if "points_applied" in transaction_columns else "0"
        locked_select = "locked" if "locked" in transaction_columns else "0"
        connection.execute(
            text(
                f"""
                INSERT INTO transactions (
                    id,
                    book_id,
                    owner_id,
                    exchange_mode,
                    requester_id,
                    courier_id,
                    owner_confirmed,
                    requester_confirmed,
                    locked,
                    points_applied
                )
                SELECT
                    id,
                    book_id,
                    owner_id,
                    exchange_mode,
                    {requester_select},
                    {courier_select},
                    {owner_confirmed_select},
                    {requester_confirmed_select},
                    {locked_select},
                    {points_applied_select}
                FROM transactions_old
                """
            )
        )
        connection.execute(text("DROP TABLE transactions_old"))


def points_for_mode(exchange_mode: str) -> int:
    """
    tl;dr: Return the point value for an exchange mode.
    input:
    * exchange_mode: permanent exchange or loan mode
    output:
    * positive point value for the giver and negative value for the receiver
    """
    if exchange_mode == "permanent":
        return 10
    if exchange_mode == "loan":
        return 5
    raise HTTPException(status_code=400, detail="exchange_mode must be permanent or loan")


def book_to_dict(book: Book, owner: Member) -> dict:
    """
    tl;dr: Convert a book and owner into a frontend-friendly dictionary.
    input:
    * book: Book database record
    * owner: Member who owns the book
    output:
    * dictionary with book fields and owner display fields
    """
    return {
        "id": book.id,
        "owner_id": book.owner_id,
        "owner_name": owner.name,
        "owner_email": owner.email,
        "title": book.title,
        "genre": book.genre,
        "author": book.author,
        "publication_year": book.publication_year,
        "condition": book.condition,
        "exchange_mode": book.exchange_mode,
        "available": book.available,
        "picture_path": book.picture_path,
    }


def member_role_in_transaction(session: Session, transaction: ExchangeTransaction, user_id: int) -> Optional[str]:
    """
    tl;dr: Return the accepted chatbox role for a member.
    input:
    * session: active database session
    * transaction: transaction chatbox to inspect
    * user_id: member id to inspect
    output:
    * accepted role name or None
    """
    if user_id == transaction.owner_id:
        return "owner"
    message = session.exec(
        select(Message).where(
            Message.transaction_id == transaction.id,
            Message.user_id == user_id,
            Message.accepted == True,
        )
    ).first()
    return message.applied_role if message else None


def add_message(session: Session, transaction_id: int, user_id: int, role: str, message_text: str, accepted: bool) -> Message:
    """
    tl;dr: Insert one chatbox message row.
    input:
    * session: active database session
    * transaction_id: chatbox transaction id
    * user_id: member sending the message
    * role: role attached to the message
    * message_text: message body
    * accepted: whether this message is visible to accepted chatbox participants
    output:
    * created Message record
    """
    message = Message(
        transaction_id=transaction_id,
        user_id=user_id,
        applied_role=role,
        message=message_text,
        accepted=accepted,
    )
    session.add(message)
    return message


def message_to_dict(message: Message, member: Member) -> dict:
    """
    tl;dr: Convert a chatbox message into a frontend-friendly dictionary.
    input:
    * message: Message database record
    * member: message author
    output:
    * dictionary with message fields and author name
    """
    return {
        "message_id": message.message_id,
        "user_id": message.user_id,
        "user_name": member.name,
        "transaction_id": message.transaction_id,
        "message": message.message,
        "applied_role": message.applied_role,
        "accepted": message.accepted,
        "timestamp": message.timestamp.isoformat(),
    }


def transaction_to_dict(
    transaction: ExchangeTransaction,
    book: Book,
    owner: Member,
    requester: Optional[Member],
    courier: Optional[Member],
) -> dict:
    """
    tl;dr: Convert a transaction and related records into a frontend-friendly dictionary.
    input:
    * transaction: ExchangeTransaction database record
    * book: Book attached to the transaction
    * owner: Member giving or lending the book
    * requester: Member receiving or borrowing the book
    * courier: optional Member delivering the book
    output:
    * dictionary with transaction fields and readable related names
    """
    point_value = points_for_mode(transaction.exchange_mode)
    return {
        "id": transaction.id,
        "book_id": transaction.book_id,
        "book_title": book.title,
        "owner_id": transaction.owner_id,
        "owner_name": owner.name,
        "requester_id": transaction.requester_id,
        "requester_name": requester.name if requester else "",
        "exchange_mode": transaction.exchange_mode,
        "courier_id": transaction.courier_id,
        "courier_name": courier.name if courier else "",
        "owner_confirmed": transaction.owner_confirmed,
        "requester_confirmed": transaction.requester_confirmed,
        "locked": transaction.locked,
        "points_applied": transaction.points_applied,
        "owner_points_delta": point_value,
        "requester_points_delta": -point_value,
        "courier_points_delta": 2 if courier else 0,
    }


def complete_transaction_if_ready(session: Session, transaction: ExchangeTransaction) -> None:
    """
    tl;dr: Apply point changes once both sides have confirmed a transaction.
    input:
    * session: active database session
    * transaction: transaction that may be ready to complete
    output:
    * None
    """
    if not transaction.owner_confirmed or not transaction.requester_confirmed:
        return
    if transaction.points_applied:
        return
    if transaction.requester_id is None:
        raise HTTPException(status_code=400, detail="No accepted requester for this transaction")

    owner = get_member(session, transaction.owner_id)
    requester = get_member(session, transaction.requester_id)
    point_value = points_for_mode(transaction.exchange_mode)

    owner.points += point_value
    requester.points -= point_value
    if transaction.courier_id:
        courier = get_member(session, transaction.courier_id)
        courier.points += 2
        session.add(courier)

    transaction.points_applied = True
    session.add(owner)
    session.add(requester)
    session.add(transaction)


def delete_chatbox_messages(session: Session, transaction_id: int) -> None:
    """
    tl;dr: Delete all messages for a finished chatbox.
    input:
    * session: active database session
    * transaction_id: chatbox transaction id
    output:
    * None
    """
    messages = session.exec(select(Message).where(Message.transaction_id == transaction_id)).all()
    for message in messages:
        session.delete(message)


@app.on_event("startup")
def on_startup() -> None:
    """
    tl;dr: Create all DB tables and apply small schema updates on startup.
    output:
    * None
    """
    SQLModel.metadata.create_all(engine)
    migrate_schema()


@app.get("/api/health")
def health() -> dict:
    """
    tl;dr: Return a quick backend health check.
    output:
    * dictionary showing the API is running
    """
    return {"ok": True}


@app.post("/api/auth/register")
def register(payload: AuthRequest) -> dict:
    """
    tl;dr: Register a member and return an access token.
    input:
    * payload: member name, email, and password
    output:
    * access token and member dictionary
    """
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters")

    with Session(engine) as session:
        existing = get_member_by_email(session, payload.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email is already registered")
        member = Member(
            name=payload.name.strip(),
            email=payload.email.strip().lower(),
            password_hash=hash_password(payload.password),
            points=20,
        )
        session.add(member)
        session.commit()
        session.refresh(member)
        return auth_response(member)


@app.post("/api/auth/login")
def login(payload: AuthRequest) -> dict:
    """
    tl;dr: Authenticate a member and return an access token.
    input:
    * payload: email and password
    output:
    * access token and member dictionary
    """
    with Session(engine) as session:
        member = get_member_by_email(session, payload.email)
        if not member or not verify_password(payload.password, member.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return auth_response(member)


@app.get("/api/auth/me")
def me(authorization: str = Header(default="")) -> dict:
    """
    tl;dr: Return the member attached to a bearer token.
    input:
    * authorization: bearer access token header
    output:
    * current member dictionary
    """
    with Session(engine) as session:
        member = get_current_member(session, authorization)
        courier_member_ids = get_courier_member_ids(session)
        return member_to_dict(member, courier_member_ids)


@app.get("/api/members")
def list_members() -> list[dict]:
    """
    tl;dr: Return all registered members.
    output:
    * list of Member records
    """
    with Session(engine) as session:
        members = session.exec(select(Member).order_by(Member.id)).all()
        courier_member_ids = get_courier_member_ids(session)
        return [member_to_dict(member, courier_member_ids) for member in members]


@app.post("/api/members")
def create_member(member: MemberCreate) -> dict:
    """
    tl;dr: Register a new exchange member with 20 starting points.
    input:
    * member: member name and email address
    output:
    * created Member record
    """
    with Session(engine) as session:
        new_member = Member(name=member.name, email=member.email.strip().lower(), points=20)
        session.add(new_member)
        session.commit()
        session.refresh(new_member)
        return member_to_dict(new_member, set())


@app.get("/api/books")
def list_books() -> list[dict]:
    """
    tl;dr: Return all books with owner names and email addresses.
    output:
    * list of dictionaries describing books and owners
    """
    with Session(engine) as session:
        books = session.exec(select(Book).order_by(Book.id)).all()
        return [book_to_dict(book, get_member(session, book.owner_id)) for book in books]


@app.post("/api/books")
def create_book(
    owner_id: int = Form(...),
    title: str = Form(...),
    genre: str = Form(...),
    author: str = Form(...),
    publication_year: int = Form(...),
    condition: str = Form(...),
    exchange_mode: str = Form("permanent"),
    picture: Optional[UploadFile] = File(default=None),
) -> dict:
    """
    tl;dr: Add a member-owned book to the exchange catalog.
    input:
    * owner_id: member who owns the book
    * title: book title
    * genre: book genre
    * author: book author
    * publication_year: book publication year
    * condition: book condition
    * exchange_mode: permanent exchange or loan mode
    * picture: optional uploaded book image
    output:
    * created book dictionary with owner details
    """
    points_for_mode(exchange_mode)
    with Session(engine) as session:
        owner = get_member(session, owner_id)
        new_book = Book(
            owner_id=owner_id,
            title=title,
            genre=genre,
            author=author,
            publication_year=publication_year,
            condition=condition,
            exchange_mode=exchange_mode,
            picture_path=save_book_picture(picture),
        )
        session.add(new_book)
        session.commit()
        session.refresh(new_book)
        transaction = ExchangeTransaction(
            book_id=new_book.id,
            owner_id=owner.id,
            exchange_mode=new_book.exchange_mode,
        )
        session.add(transaction)
        session.commit()
        session.refresh(transaction)
        add_message(session, transaction.id, owner.id, "owner", f"Posted book: {new_book.title}", True)
        session.commit()
        return book_to_dict(new_book, owner)


@app.put("/api/books/{book_id}")
def update_book(
    book_id: int,
    owner_id: int = Form(...),
    title: str = Form(...),
    genre: str = Form(...),
    author: str = Form(...),
    publication_year: int = Form(...),
    condition: str = Form(...),
    exchange_mode: str = Form("permanent"),
    picture: Optional[UploadFile] = File(default=None),
) -> dict:
    """
    tl;dr: Update one book owned by a member.
    input:
    * book_id: book being edited
    * owner_id: member who owns the book
    * title: updated book title
    * genre: updated book genre
    * author: updated book author
    * publication_year: updated publication year
    * condition: updated condition
    * exchange_mode: updated exchange mode
    * picture: optional replacement book image
    output:
    * updated book dictionary with owner details
    """
    points_for_mode(exchange_mode)
    with Session(engine) as session:
        book = get_book(session, book_id)
        if book.owner_id != owner_id:
            raise HTTPException(status_code=403, detail="Only the owner can edit this book")
        owner = get_member(session, owner_id)
        book.title = title
        book.genre = genre
        book.author = author
        book.publication_year = publication_year
        book.condition = condition
        book.exchange_mode = exchange_mode
        new_picture_path = save_book_picture(picture)
        if new_picture_path:
            book.picture_path = new_picture_path
        session.add(book)
        session.commit()
        session.refresh(book)
        return book_to_dict(book, owner)


@app.get("/api/transactions")
def list_transactions() -> list[dict]:
    """
    tl;dr: Return all exchange transactions with readable names.
    output:
    * list of transaction dictionaries
    """
    with Session(engine) as session:
        transactions = session.exec(select(ExchangeTransaction).order_by(ExchangeTransaction.id)).all()
        rows = []
        for transaction in transactions:
            book = get_book(session, transaction.book_id)
            owner = get_member(session, transaction.owner_id)
            requester = get_member(session, transaction.requester_id) if transaction.requester_id else None
            courier = get_member(session, transaction.courier_id) if transaction.courier_id else None
            rows.append(transaction_to_dict(transaction, book, owner, requester, courier))
        return rows


@app.post("/api/transactions")
def create_transaction(payload: TransactionCreate) -> dict:
    """
    tl;dr: Create a chatbox transaction for an available book.
    input:
    * payload: requested book for the chatbox
    output:
    * created transaction dictionary
    """
    with Session(engine) as session:
        book = get_book(session, payload.book_id)
        owner = get_member(session, book.owner_id)
        transaction = ExchangeTransaction(
            book_id=book.id,
            owner_id=owner.id,
            exchange_mode=book.exchange_mode,
        )
        session.add(transaction)
        session.commit()
        session.refresh(transaction)
        add_message(session, transaction.id, owner.id, "owner", f"Opened chatbox for: {book.title}", True)
        session.commit()
        return transaction_to_dict(transaction, book, owner, None, None)


@app.get("/api/transactions/{transaction_id}/messages")
def list_messages(transaction_id: int, member_id: int) -> list[dict]:
    """
    tl;dr: Return visible chatbox messages for one member.
    input:
    * transaction_id: chatbox transaction id
    * member_id: member trying to read the chatbox
    output:
    * list of message dictionaries visible to that member
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        get_member(session, member_id)
        role = member_role_in_transaction(session, transaction, member_id)
        if role is None:
            raise HTTPException(status_code=403, detail="Only accepted participants can view this chatbox")

        statement = select(Message).where(Message.transaction_id == transaction_id)
        if role != "owner":
            statement = statement.where(Message.accepted == True)

        messages = session.exec(statement.order_by(Message.timestamp, Message.message_id)).all()
        return [message_to_dict(message, get_member(session, message.user_id)) for message in messages]


@app.post("/api/transactions/{transaction_id}/messages")
def create_chat_message(transaction_id: int, payload: ChatMessageCreate) -> dict:
    """
    tl;dr: Add a normal visible message from an accepted chatbox participant.
    input:
    * transaction_id: chatbox transaction id
    * payload: sender id and message body
    output:
    * created message dictionary
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        member = get_member(session, payload.user_id)
        role = member_role_in_transaction(session, transaction, payload.user_id)
        if role is None:
            raise HTTPException(status_code=403, detail="Only accepted participants can post visible messages")

        message = add_message(session, transaction_id, payload.user_id, role, payload.message, True)
        session.commit()
        session.refresh(message)
        return message_to_dict(message, member)


@app.post("/api/transactions/{transaction_id}/apply")
def apply_to_chatbox(transaction_id: int, payload: ApplyRequest) -> dict:
    """
    tl;dr: Save a requester or courier application as an owner-visible intro message.
    input:
    * transaction_id: chatbox transaction id
    * payload: applicant id, requested role, and intro message
    output:
    * created intro message dictionary
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        ensure_open_chatbox(transaction)
        member = get_member(session, payload.user_id)
        if payload.applied_role not in {"requester", "courier"}:
            raise HTTPException(status_code=400, detail="Applicants must choose requester or courier")
        if member.id == transaction.owner_id:
            raise HTTPException(status_code=400, detail="Owner cannot apply to their own chatbox")
        if payload.applied_role == "requester" and member.id == transaction.courier_id:
            raise HTTPException(status_code=400, detail="Requester and courier must be different members")
        if payload.applied_role == "courier" and member.id == transaction.requester_id:
            raise HTTPException(status_code=400, detail="Courier and requester must be different members")

        message = add_message(session, transaction_id, member.id, payload.applied_role, payload.message, False)
        session.commit()
        session.refresh(message)
        return message_to_dict(message, member)


@app.post("/api/transactions/{transaction_id}/accept")
def accept_participant(transaction_id: int, payload: RoleDecision) -> dict:
    """
    tl;dr: Let the owner approve one requester or courier and revoke the previous accepted member for that role.
    input:
    * transaction_id: chatbox transaction id
    * payload: owner id, applicant id, and role being approved
    output:
    * updated transaction dictionary
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        ensure_open_chatbox(transaction)
        if payload.owner_id != transaction.owner_id:
            raise HTTPException(status_code=403, detail="Only the owner can accept participants")
        member = get_member(session, payload.user_id)
        if payload.applied_role not in {"requester", "courier"}:
            raise HTTPException(status_code=400, detail="Owner can only accept requester or courier roles")
        if member.id == transaction.owner_id:
            raise HTTPException(status_code=400, detail="Owner cannot fill requester or courier role")
        if payload.applied_role == "requester" and member.id == transaction.courier_id:
            raise HTTPException(status_code=400, detail="Requester and courier must be different members")
        if payload.applied_role == "courier" and member.id == transaction.requester_id:
            raise HTTPException(status_code=400, detail="Courier and requester must be different members")

        applicant_messages = session.exec(
            select(Message).where(
                Message.transaction_id == transaction_id,
                Message.user_id == member.id,
                Message.applied_role == payload.applied_role,
            )
        ).all()
        if not applicant_messages:
            raise HTTPException(status_code=400, detail="Member has not applied for this role")

        role_messages = session.exec(
            select(Message).where(
                Message.transaction_id == transaction_id,
                Message.applied_role == payload.applied_role,
                Message.accepted == True,
            )
        ).all()
        for message in role_messages:
            message.accepted = False
            session.add(message)
        for message in applicant_messages:
            message.accepted = True
            session.add(message)

        if payload.applied_role == "requester":
            transaction.requester_id = member.id
        else:
            transaction.courier_id = member.id
        transaction.owner_confirmed = False
        transaction.requester_confirmed = False
        session.add(transaction)
        session.commit()
        session.refresh(transaction)

        book = get_book(session, transaction.book_id)
        owner = get_member(session, transaction.owner_id)
        requester = get_member(session, transaction.requester_id) if transaction.requester_id else None
        courier = get_member(session, transaction.courier_id) if transaction.courier_id else None
        return transaction_to_dict(transaction, book, owner, requester, courier)


@app.post("/api/transactions/{transaction_id}/leave")
def leave_chatbox(transaction_id: int, payload: LeaveRequest) -> dict:
    """
    tl;dr: Let an accepted requester or courier leave an unlocked chatbox without deleting their messages.
    input:
    * transaction_id: chatbox transaction id
    * payload: member id leaving the chatbox
    output:
    * updated transaction dictionary
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        ensure_open_chatbox(transaction)
        if payload.user_id == transaction.owner_id:
            raise HTTPException(status_code=400, detail="Owner cannot leave their own chatbox")
        role = member_role_in_transaction(session, transaction, payload.user_id)
        if role not in {"requester", "courier"}:
            raise HTTPException(status_code=400, detail="Member is not an accepted requester or courier")

        messages = session.exec(
            select(Message).where(
                Message.transaction_id == transaction_id,
                Message.user_id == payload.user_id,
                Message.applied_role == role,
            )
        ).all()
        for message in messages:
            message.accepted = False
            session.add(message)
        if role == "requester":
            transaction.requester_id = None
        else:
            transaction.courier_id = None
        transaction.owner_confirmed = False
        transaction.requester_confirmed = False
        session.add(transaction)
        session.commit()
        session.refresh(transaction)

        book = get_book(session, transaction.book_id)
        owner = get_member(session, transaction.owner_id)
        requester = get_member(session, transaction.requester_id) if transaction.requester_id else None
        courier = get_member(session, transaction.courier_id) if transaction.courier_id else None
        return transaction_to_dict(transaction, book, owner, requester, courier)


@app.post("/api/transactions/{transaction_id}/kick")
def kick_participant(transaction_id: int, payload: RoleDecision) -> dict:
    """
    tl;dr: Let the owner remove an accepted requester or courier without deleting their messages.
    input:
    * transaction_id: chatbox transaction id
    * payload: owner id, member id, and role being removed
    output:
    * updated transaction dictionary
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        ensure_open_chatbox(transaction)
        if payload.owner_id != transaction.owner_id:
            raise HTTPException(status_code=403, detail="Only the owner can kick participants")
        if payload.applied_role not in {"requester", "courier"}:
            raise HTTPException(status_code=400, detail="Owner can only kick requester or courier roles")
        if payload.applied_role == "requester" and transaction.requester_id != payload.user_id:
            raise HTTPException(status_code=400, detail="Member is not the accepted requester")
        if payload.applied_role == "courier" and transaction.courier_id != payload.user_id:
            raise HTTPException(status_code=400, detail="Member is not the accepted courier")

        messages = session.exec(
            select(Message).where(
                Message.transaction_id == transaction_id,
                Message.user_id == payload.user_id,
                Message.applied_role == payload.applied_role,
            )
        ).all()
        for message in messages:
            message.accepted = False
            session.add(message)
        if payload.applied_role == "requester":
            transaction.requester_id = None
        else:
            transaction.courier_id = None
        transaction.owner_confirmed = False
        transaction.requester_confirmed = False
        session.add(transaction)
        session.commit()
        session.refresh(transaction)

        book = get_book(session, transaction.book_id)
        owner = get_member(session, transaction.owner_id)
        requester = get_member(session, transaction.requester_id) if transaction.requester_id else None
        courier = get_member(session, transaction.courier_id) if transaction.courier_id else None
        return transaction_to_dict(transaction, book, owner, requester, courier)


@app.post("/api/transactions/confirm-meeting")
def confirm_meeting(payload: MeetingConfirm) -> dict:
    """
    tl;dr: Confirm that two accepted chatbox participants physically met.
    input:
    * payload: transaction id and the two users who met
    output:
    * updated transaction dictionary
    """
    with Session(engine) as session:
        transaction = get_transaction(session, payload.transaction_id)
        user_ids = {payload.user_1_id, payload.user_2_id}
        expected_owner_handoff = {transaction.owner_id, transaction.courier_id}
        expected_direct_handoff = {transaction.owner_id, transaction.requester_id}
        expected_requester_handoff = {transaction.requester_id, transaction.courier_id}

        if None in user_ids:
            raise HTTPException(status_code=400, detail="Both users must be accepted chatbox participants")

        if user_ids == expected_owner_handoff or (
            user_ids == expected_direct_handoff and transaction.courier_id is None
        ):
            transaction.owner_confirmed = True
            transaction.locked = True
            if user_ids == expected_direct_handoff and transaction.courier_id is None:
                transaction.requester_confirmed = True
        elif user_ids == expected_requester_handoff:
            if not transaction.owner_confirmed:
                raise HTTPException(status_code=400, detail="Owner handoff must be confirmed first")
            transaction.requester_confirmed = True
        else:
            raise HTTPException(status_code=400, detail="Meeting users do not match this transaction")

        complete_transaction_if_ready(session, transaction)
        if transaction.points_applied:
            delete_chatbox_messages(session, transaction.id)
            book = get_book(session, transaction.book_id)
            book.available = False
            session.add(book)
        session.add(transaction)
        session.commit()
        session.refresh(transaction)

        book = get_book(session, transaction.book_id)
        owner = get_member(session, transaction.owner_id)
        requester = get_member(session, transaction.requester_id) if transaction.requester_id else None
        courier = get_member(session, transaction.courier_id) if transaction.courier_id else None
        return transaction_to_dict(transaction, book, owner, requester, courier)


@app.post("/api/demo-seed")
def demo_seed() -> dict:
    """
    tl;dr: Add sample members and books when the database is empty.
    output:
    * dictionary describing whether demo records were created
    """
    with Session(engine) as session:
        existing = session.exec(select(Member)).first()
        if existing:
            return {"created": False, "message": "Demo data already exists"}

        demo_password = "demo1234"
        an = Member(name="An", email="an@example.com", password_hash=hash_password(demo_password), points=20)
        binh = Member(name="Binh", email="binh@example.com", password_hash=hash_password(demo_password), points=20)
        chi = Member(name="Chi", email="chi@example.com", password_hash=hash_password(demo_password), points=20)
        dung = Member(name="Dung", email="dung@example.com", password_hash=hash_password(demo_password), points=20)
        giang = Member(name="Giang", email="giang@example.com", password_hash=hash_password(demo_password), points=20)
        members = [an, binh, chi, dung, giang]
        for member in members:
            session.add(member)
        session.commit()
        for member in members:
            session.refresh(member)

        books = [
            Book(
                owner_id=an.id,
                title="Clean Code",
                genre="Software",
                author="Robert C. Martin",
                publication_year=2008,
                condition="Good",
                exchange_mode="loan",
                picture_path="/pic/dummy.png",
            ),
            Book(
                owner_id=chi.id,
                title="The Pragmatic Programmer",
                genre="Software",
                author="Andrew Hunt, David Thomas",
                publication_year=1999,
                condition="Used",
                exchange_mode="permanent",
                picture_path="/pic/dummy.png",
            ),
            Book(
                owner_id=giang.id,
                title="Atomic Habits",
                genre="Self-help",
                author="James Clear",
                publication_year=2018,
                condition="Like new",
                exchange_mode="loan",
                picture_path="/pic/dummy.png",
            ),
            Book(
                owner_id=binh.id,
                title="The Hobbit",
                genre="Fantasy",
                author="J.R.R. Tolkien",
                publication_year=1937,
                condition="Good",
                exchange_mode="permanent",
                picture_path="/pic/dummy.png",
            ),
            Book(
                owner_id=dung.id,
                title="Dune",
                genre="Science fiction",
                author="Frank Herbert",
                publication_year=1965,
                condition="Fair",
                exchange_mode="loan",
                picture_path="/pic/dummy.png",
            ),
        ]
        for book in books:
            session.add(book)
        session.commit()
        return {
            "created": True,
            "message": "Demo data created",
            "demo_password": demo_password,
            "emails": [member.email for member in members],
        }
