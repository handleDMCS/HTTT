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
from sqlalchemy import Index, UniqueConstraint, func, text
from sqlalchemy.engine import Connection
from sqlmodel import Field, SQLModel, Session, create_engine, select


DATABASE_URL = "sqlite:///db.sqlite3"
JWT_SECRET = os.getenv("JWT_SECRET", "hackathon-local-secret")
JWT_EXPIRE_HOURS = 72
PIC_DIR = "pic"
AVATAR_DIR = "avatar"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str
    password_hash: str = ""
    points: int = 20
    gender: str = "male"
    age: int = 18
    avatar_path: str = "/avatar/male.svg"
    biography: str = ""


class MemberCreate(SQLModel):
    name: str
    email: str


class AuthRequest(SQLModel):
    name: str = ""
    email: str
    password: str
    gender: str = "male"
    age: int = 18


class Book(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    owner_id: int = Field(foreign_key="member.id")
    title: str
    genre: str
    author: str
    description: str = ""
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
    description: str = ""
    publication_year: int
    condition: str
    exchange_mode: str = "permanent"


class BookUpdate(SQLModel):
    owner_id: int
    title: str
    genre: str
    author: str
    description: str = ""
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
    archived: bool = False


class TransactionCreate(SQLModel):
    book_id: int


class Message(SQLModel, table=True):
    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "ix_messages_one_join_request_per_member_transaction",
            "user_id",
            "transaction_id",
            unique=True,
            sqlite_where=text("notification_type = 'join_request'"),
        ),
    )

    message_id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="member.id")
    transaction_id: int = Field(foreign_key="transactions.id")
    message: str
    applied_role: str
    notification_type: Optional[str] = None
    approver_id: Optional[int] = Field(default=None, foreign_key="member.id")
    approver_role: Optional[str] = None
    accepted: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ActivityTracking(SQLModel, table=True):
    __tablename__ = "activity_tracking"
    __table_args__ = (UniqueConstraint("member_id", "transaction_id", "tab"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    member_id: int = Field(foreign_key="member.id")
    transaction_id: Optional[int] = Field(default=None, foreign_key="transactions.id")
    tab: str
    last_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ApplyRequest(SQLModel):
    user_id: int
    applied_role: str
    message: str


class ChatMessageCreate(SQLModel):
    user_id: int
    message: str


class NotificationCreate(SQLModel):
    user_id: int
    notification_type: str
    message: str = ""


class NotificationApproval(SQLModel):
    user_id: int


class ActivityMark(SQLModel):
    member_id: int
    transaction_id: Optional[int] = None
    tab: str


class RoleApplicationStats(SQLModel):
    applying: int
    accepted: bool
    accepted_name: str = ""


class RoleDecision(SQLModel):
    owner_id: int
    user_id: int
    applied_role: str


class LeaveRequest(SQLModel):
    user_id: int


class WithdrawApplication(SQLModel):
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
os.makedirs(AVATAR_DIR, exist_ok=True)
app.mount("/pic", StaticFiles(directory=PIC_DIR), name="pic")
app.mount("/avatar", StaticFiles(directory=AVATAR_DIR), name="avatar")


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


def normalize_gender(gender: str) -> str:
    normalized = gender.strip().lower()
    if normalized not in {"male", "female"}:
        raise HTTPException(status_code=400, detail="Gender must be male or female")
    return normalized


def validate_age(age: int) -> int:
    if age < 1 or age > 120:
        raise HTTPException(status_code=400, detail="Age must be between 1 and 120")
    return age


def default_avatar_path(gender: str) -> str:
    return f"/avatar/{normalize_gender(gender)}.svg"


def save_avatar(avatar: Optional[UploadFile]) -> str:
    """
    tl;dr: Save an uploaded profile avatar into the local avatar folder.
    input:
    * avatar: optional uploaded image file
    output:
    * public avatar path or empty string
    """
    if avatar is None or not avatar.filename:
        return ""
    if avatar.content_type and not avatar.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Avatar must be an image file")

    os.makedirs(AVATAR_DIR, exist_ok=True)
    extension = os.path.splitext(avatar.filename)[1].lower()
    if extension not in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}:
        extension = ".png"
    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(8)}{extension}"
    disk_path = os.path.join(AVATAR_DIR, filename)
    with open(disk_path, "wb") as output:
        shutil.copyfileobj(avatar.file, output)
    return f"/avatar/{filename}"


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
        "gender": member.gender,
        "age": member.age,
        "avatar_path": member.avatar_path,
        "biography": member.biography,
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
    if transaction.archived:
        raise HTTPException(status_code=400, detail="Chatbox is archived")
    if transaction.locked:
        raise HTTPException(status_code=400, detail="Chatbox is locked")


NOTIFICATION_TYPES = {
    "join_request",
    "kicked",
    "leave",
    "join",
    "confirm_direct_handoff",
    "confirm_handoff",
    "confirm_delivered",
}

CONFIRM_NOTIFICATION_TYPES = {
    "confirm_direct_handoff",
    "confirm_handoff",
    "confirm_delivered",
}


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
        if "gender" not in member_columns:
            connection.execute(text("ALTER TABLE member ADD COLUMN gender VARCHAR NOT NULL DEFAULT 'male'"))
        if "age" not in member_columns:
            connection.execute(text("ALTER TABLE member ADD COLUMN age INTEGER NOT NULL DEFAULT 18"))
        if "avatar_path" not in member_columns:
            connection.execute(text("ALTER TABLE member ADD COLUMN avatar_path VARCHAR NOT NULL DEFAULT '/avatar/male.svg'"))
        if "biography" not in member_columns:
            connection.execute(text("ALTER TABLE member ADD COLUMN biography VARCHAR NOT NULL DEFAULT ''"))
        connection.execute(
            text(
                """
                UPDATE member
                SET avatar_path = CASE
                    WHEN gender = 'female' THEN '/avatar/female.svg'
                    ELSE '/avatar/male.svg'
                END
                WHERE avatar_path IS NULL OR avatar_path = ''
                """
            )
        )

        book_columns = get_table_columns(connection, "book")
        if book_columns and "picture_path" not in book_columns:
            connection.execute(text("ALTER TABLE book ADD COLUMN picture_path VARCHAR NOT NULL DEFAULT ''"))
        if book_columns and "description" not in book_columns:
            connection.execute(text("ALTER TABLE book ADD COLUMN description VARCHAR NOT NULL DEFAULT ''"))

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

        message_columns = get_table_columns(connection, "messages")
        if message_columns and "notification_type" not in message_columns:
            connection.execute(text("ALTER TABLE messages ADD COLUMN notification_type VARCHAR"))
        if message_columns and "approver_id" not in message_columns:
            connection.execute(text("ALTER TABLE messages ADD COLUMN approver_id INTEGER"))
        if message_columns and "approver_role" not in message_columns:
            connection.execute(text("ALTER TABLE messages ADD COLUMN approver_role VARCHAR"))
        if message_columns:
            connection.execute(
                text(
                    """
                    DELETE FROM messages
                    WHERE notification_type = 'join_request'
                    AND EXISTS (
                        SELECT 1
                        FROM messages AS newer
                        WHERE newer.notification_type = 'join_request'
                        AND newer.user_id = messages.user_id
                        AND newer.transaction_id = messages.transaction_id
                        AND (
                            newer.timestamp > messages.timestamp
                            OR (
                                newer.timestamp = messages.timestamp
                                AND newer.message_id > messages.message_id
                            )
                        )
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS ix_messages_one_join_request_per_member_transaction
                    ON messages (user_id, transaction_id)
                    WHERE notification_type = 'join_request'
                    """
                )
            )

        if not table_exists(connection, "activity_tracking"):
            connection.execute(
                text(
                    """
                    CREATE TABLE activity_tracking (
                        id INTEGER NOT NULL,
                        member_id INTEGER NOT NULL,
                        transaction_id INTEGER,
                        tab VARCHAR NOT NULL,
                        last_timestamp DATETIME NOT NULL,
                        PRIMARY KEY (id),
                        FOREIGN KEY(member_id) REFERENCES member (id),
                        FOREIGN KEY(transaction_id) REFERENCES transactions (id),
                        UNIQUE(member_id, transaction_id, tab)
                    )
                    """
                )
            )

        if table_exists(connection, "exchangetransaction"):
            legacy_transaction_columns = get_table_columns(connection, "exchangetransaction")
            if table_exists(connection, "transactions"):
                target_transaction_columns = get_table_columns(connection, "transactions")
                if "archived" not in target_transaction_columns:
                    connection.execute(text("ALTER TABLE transactions ADD COLUMN archived BOOLEAN NOT NULL DEFAULT 0"))
                requester_select = "requester_id" if "requester_id" in legacy_transaction_columns else "NULL"
                courier_select = "courier_id" if "courier_id" in legacy_transaction_columns else "NULL"
                owner_confirmed_select = "owner_confirmed" if "owner_confirmed" in legacy_transaction_columns else "0"
                requester_confirmed_select = (
                    "requester_confirmed" if "requester_confirmed" in legacy_transaction_columns else "0"
                )
                points_applied_select = "points_applied" if "points_applied" in legacy_transaction_columns else "0"
                archived_select = "archived" if "archived" in legacy_transaction_columns else points_applied_select
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
                            points_applied,
                            archived
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
                            {points_applied_select},
                            {archived_select}
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
            or "archived" not in transaction_columns
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
                    archived BOOLEAN NOT NULL,
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
        archived_select = "archived" if "archived" in transaction_columns else points_applied_select
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
                    points_applied,
                    archived
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
                    {points_applied_select},
                    {archived_select}
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


def requester_budget_exposure(session: Session, member_id: int, exclude_transaction_id: Optional[int] = None) -> dict:
    """
    tl;dr: Aggregate active requester point exposure for one member.
    input:
    * session: active database session
    * member_id: member whose requester exposure should be counted
    * exclude_transaction_id: optional transaction to ignore while replacing an application
    output:
    * counts and reserved point total for pending and accepted requester commitments
    """
    loan_count = 0
    permanent_count = 0
    seen_transaction_ids: set[int] = set()

    accepted_transactions = session.exec(
        select(ExchangeTransaction).where(
            ExchangeTransaction.requester_id == member_id,
            ExchangeTransaction.points_applied == False,
            ExchangeTransaction.archived == False,
        )
    ).all()
    for transaction in accepted_transactions:
        if transaction.id is None or transaction.id == exclude_transaction_id:
            continue
        seen_transaction_ids.add(transaction.id)
        if transaction.exchange_mode == "loan":
            loan_count += 1
        elif transaction.exchange_mode == "permanent":
            permanent_count += 1

    pending_requests = session.exec(
        select(Message, ExchangeTransaction)
        .join(ExchangeTransaction, Message.transaction_id == ExchangeTransaction.id)
        .where(
            Message.user_id == member_id,
            Message.notification_type == "join_request",
            Message.applied_role == "requester",
            Message.accepted == False,
            ExchangeTransaction.points_applied == False,
            ExchangeTransaction.archived == False,
        )
    ).all()
    for _, transaction in pending_requests:
        if transaction.id is None or transaction.id == exclude_transaction_id or transaction.id in seen_transaction_ids:
            continue
        seen_transaction_ids.add(transaction.id)
        if transaction.exchange_mode == "loan":
            loan_count += 1
        elif transaction.exchange_mode == "permanent":
            permanent_count += 1

    return {
        "loan_requests": loan_count,
        "permanent_requests": permanent_count,
        "reserved_points": loan_count * points_for_mode("loan") + permanent_count * points_for_mode("permanent"),
    }


def requester_budget_to_dict(
    session: Session,
    member: Member,
    transaction: Optional[ExchangeTransaction] = None,
    book: Optional[Book] = None,
    exclude_transaction_id: Optional[int] = None,
) -> dict:
    """
    tl;dr: Build a frontend-friendly requester budget summary.
    input:
    * session: active database session
    * member: member whose budget is summarized
    * transaction: optional transaction being requested
    * book: optional book being requested when no transaction exists yet
    * exclude_transaction_id: optional transaction to ignore while replacing an application
    output:
    * dictionary with current, reserved, available, and optional required points
    """
    exposure = requester_budget_exposure(session, member.id, exclude_transaction_id)
    available_points = member.points - exposure["reserved_points"]
    exchange_mode = transaction.exchange_mode if transaction else book.exchange_mode if book else ""
    required_points = points_for_mode(exchange_mode) if exchange_mode else 0
    return {
        "member_id": member.id,
        "points": member.points,
        "reserved_points": exposure["reserved_points"],
        "available_points": available_points,
        "loan_requests": exposure["loan_requests"],
        "permanent_requests": exposure["permanent_requests"],
        "required_points": required_points,
        "can_request": required_points == 0 or available_points >= required_points,
    }


def ensure_requester_budget(session: Session, member: Member, transaction: ExchangeTransaction) -> None:
    """
    tl;dr: Stop requester applications that would exceed available points.
    input:
    * session: active database session
    * member: requester applying to a transaction
    * transaction: transaction being requested
    output:
    * None
    """
    budget = requester_budget_to_dict(session, member, transaction, transaction.id)
    if not budget["can_request"]:
        raise HTTPException(
            status_code=400,
            detail=f"Not enough available points. You need {budget['required_points']} points.",
        )


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
        "description": book.description,
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
    if user_id == transaction.requester_id:
        return "requester"
    if user_id == transaction.courier_id:
        return "courier"
    return None


def validate_approval_pair(approver_id: Optional[int], approver_role: Optional[str]) -> None:
    if (approver_id is None) != (approver_role is None):
        raise HTTPException(status_code=400, detail="approver_id and approver_role must both be set or both be empty")


def add_message(
    session: Session,
    transaction_id: int,
    user_id: int,
    role: str,
    message_text: str,
    accepted: bool,
    notification_type: Optional[str] = None,
    approver_id: Optional[int] = None,
    approver_role: Optional[str] = None,
) -> Message:
    """
    tl;dr: Insert one chatbox message row.
    input:
    * session: active database session
    * transaction_id: chatbox transaction id
    * user_id: member sending the message
    * role: role attached to the message
    * message_text: message body
    * accepted: whether this message is visible or already approved
    * notification_type: optional notification routing type
    * approver_id: optional required approver id
    * approver_role: optional required approver role
    output:
    * created Message record
    """
    if notification_type is not None and notification_type not in NOTIFICATION_TYPES:
        raise HTTPException(status_code=400, detail="Unknown notification type")
    validate_approval_pair(approver_id, approver_role)
    message = Message(
        transaction_id=transaction_id,
        user_id=user_id,
        applied_role=role,
        message=message_text,
        notification_type=notification_type,
        approver_id=approver_id,
        approver_role=approver_role,
        accepted=accepted,
    )
    session.add(message)
    return message


def add_or_replace_join_request(
    session: Session,
    transaction: ExchangeTransaction,
    user_id: int,
    role: str,
    message_text: str,
) -> Message:
    """
    tl;dr: Replace a member's pending join request for a transaction with a fresh row.
    input:
    * session: active database session
    * transaction: transaction receiving the join request
    * user_id: applicant member id
    * role: requested requester or courier role
    * message_text: applicant introduction message
    output:
    * new Message record replacing previous pending join requests
    """
    existing_requests = session.exec(
        select(Message).where(
            Message.transaction_id == transaction.id,
            Message.user_id == user_id,
            Message.notification_type == "join_request",
        )
    ).all()
    next_message_id = (session.exec(select(func.max(Message.message_id))).one() or 0) + 1
    for request in existing_requests:
        session.delete(request)
    session.flush()
    replacement = Message(
        message_id=next_message_id,
        transaction_id=transaction.id,
        user_id=user_id,
        applied_role=role,
        message=message_text,
        notification_type="join_request",
        approver_id=transaction.owner_id,
        approver_role="owner",
        accepted=False,
    )
    session.add(replacement)
    return replacement


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
        "notification_type": message.notification_type,
        "approver_id": message.approver_id,
        "approver_role": message.approver_role,
        "accepted": message.accepted,
        "timestamp": message.timestamp.isoformat(),
    }


def message_to_activity_dict(session: Session, message: Message) -> dict:
    transaction = get_transaction(session, message.transaction_id)
    book = get_book(session, transaction.book_id)
    row = message_to_dict(message, get_member(session, message.user_id))
    row["book_id"] = book.id
    row["book_title"] = book.title
    row["transaction_archived"] = transaction.archived
    return row


def normalize_activity_tab(tab: str) -> str:
    normalized = tab.strip().lower()
    if normalized not in {"chatbox", "notification", "dropdown"}:
        raise HTTPException(status_code=400, detail="tab must be chatbox, notification, or dropdown")
    return normalized


def visible_message_statement(session: Session, transaction: ExchangeTransaction, member_id: int):
    role = member_role_in_transaction(session, transaction, member_id)
    if role is None:
        raise HTTPException(status_code=403, detail="Only accepted participants can view this chatbox")
    statement = select(Message).where(Message.transaction_id == transaction.id)
    if role != "owner":
        statement = statement.where((Message.accepted == True) | (Message.notification_type != None))
    return statement


def member_transactions(session: Session, member_id: int) -> list[ExchangeTransaction]:
    transactions = session.exec(select(ExchangeTransaction).order_by(ExchangeTransaction.id)).all()
    return [transaction for transaction in transactions if member_role_in_transaction(session, transaction, member_id)]


def message_scope_statement(
    session: Session,
    member_id: int,
    tab: str,
    transaction: Optional[ExchangeTransaction] = None,
):
    tab = normalize_activity_tab(tab)
    if tab in {"chatbox", "notification"}:
        if transaction is None:
            raise HTTPException(status_code=400, detail="transaction_id is required for this tab")
        statement = visible_message_statement(session, transaction, member_id)
        if tab == "chatbox":
            return statement.where(Message.notification_type == None, Message.accepted == True)
        return statement.where(Message.notification_type != None)

    transaction_ids = [row.id for row in member_transactions(session, member_id) if row.id is not None]
    if not transaction_ids:
        return select(Message).where(Message.message_id == -1)
    return select(Message).where(Message.transaction_id.in_(transaction_ids))


def get_activity_tracking(
    session: Session,
    member_id: int,
    tab: str,
    transaction_id: Optional[int],
) -> Optional[ActivityTracking]:
    return session.exec(
        select(ActivityTracking).where(
            ActivityTracking.member_id == member_id,
            ActivityTracking.tab == tab,
            ActivityTracking.transaction_id == transaction_id,
        )
    ).first()


def activity_last_timestamp(
    session: Session,
    member_id: int,
    tab: str,
    transaction_id: Optional[int],
) -> datetime:
    row = get_activity_tracking(session, member_id, tab, transaction_id)
    if row:
        return row.last_timestamp
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def utc_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def unread_count(
    session: Session,
    member_id: int,
    tab: str,
    transaction_id: Optional[int] = None,
) -> int:
    tab = normalize_activity_tab(tab)
    if tab == "dropdown":
        last_timestamp = utc_timestamp(activity_last_timestamp(session, member_id, tab, None))
        return len(
            [
                message
                for message in visible_messages_for_dropdown(session, member_id)
                if utc_timestamp(message.timestamp) > last_timestamp
            ]
        )

    transaction = get_transaction(session, transaction_id) if transaction_id is not None else None
    statement = message_scope_statement(session, member_id, tab, transaction)
    last_timestamp = activity_last_timestamp(session, member_id, tab, transaction_id)
    rows = session.exec(
        statement.where(
            Message.user_id != member_id,
            Message.timestamp > last_timestamp,
        )
    ).all()
    return len(rows)


def visible_messages_for_dropdown(session: Session, member_id: int) -> list[Message]:
    rows: list[Message] = []
    for transaction in member_transactions(session, member_id):
        rows.extend(
            session.exec(visible_message_statement(session, transaction, member_id).where(Message.user_id != member_id)).all()
        )
    return sorted(rows, key=lambda message: (utc_timestamp(message.timestamp), message.message_id or 0), reverse=True)


def application_stats_to_dict(session: Session, transaction: ExchangeTransaction) -> dict:
    """
    tl;dr: Count unique applicants for each open chatbox role.
    input:
    * session: active database session
    * transaction: transaction whose application rows should be counted
    output:
    * dictionary keyed by requester and courier with pending counts and accepted status
    """
    role_rows = session.exec(
        select(Message.user_id, Message.applied_role, Message.accepted).where(
            Message.transaction_id == transaction.id,
            Message.applied_role.in_(["requester", "courier"]),
            Message.notification_type == "join_request",
        )
    ).all()
    pending_user_ids = {"requester": set(), "courier": set()}
    for user_id, applied_role, accepted in role_rows:
        if not accepted:
            pending_user_ids[applied_role].add(user_id)

    requester = get_member(session, transaction.requester_id) if transaction.requester_id else None
    courier = get_member(session, transaction.courier_id) if transaction.courier_id else None
    return {
        "requester": {
            "applying": len(pending_user_ids["requester"]),
            "accepted": transaction.requester_id is not None,
            "accepted_name": requester.name if requester else "",
        },
        "courier": {
            "applying": len(pending_user_ids["courier"]),
            "accepted": transaction.courier_id is not None,
            "accepted_name": courier.name if courier else "",
        },
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
        "archived": transaction.archived,
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
    transaction.archived = True
    transaction.locked = True
    session.add(owner)
    session.add(requester)
    session.add(transaction)


def member_id_for_role(transaction: ExchangeTransaction, role: str) -> Optional[int]:
    if role == "owner":
        return transaction.owner_id
    if role == "requester":
        return transaction.requester_id
    if role == "courier":
        return transaction.courier_id
    return None


def transaction_membership_to_dict(session: Session, transaction: ExchangeTransaction) -> dict:
    book = get_book(session, transaction.book_id)
    owner = get_member(session, transaction.owner_id)
    requester = get_member(session, transaction.requester_id) if transaction.requester_id else None
    courier = get_member(session, transaction.courier_id) if transaction.courier_id else None
    return transaction_to_dict(transaction, book, owner, requester, courier)


def delete_pending_approval_messages(session: Session, transaction_id: int, user_id: int) -> None:
    messages = session.exec(
        select(Message).where(
            Message.transaction_id == transaction_id,
            Message.user_id == user_id,
            Message.approver_id != None,
        )
    ).all()
    for message in messages:
        session.delete(message)


def delete_join_requests(session: Session, transaction_id: int, user_id: int) -> None:
    """
    tl;dr: Delete all join request messages for one member and transaction.
    input:
    * session: active database session
    * transaction_id: transaction whose join requests should be deleted
    * user_id: member whose join requests should be deleted
    output:
    * None
    """
    messages = session.exec(
        select(Message).where(
            Message.transaction_id == transaction_id,
            Message.user_id == user_id,
            Message.notification_type == "join_request",
        )
    ).all()
    for message in messages:
        session.delete(message)


def create_participant_notification(
    session: Session,
    transaction: ExchangeTransaction,
    user_id: int,
    notification_type: str,
    message_text: str = "",
) -> Message:
    if notification_type not in NOTIFICATION_TYPES:
        raise HTTPException(status_code=400, detail="Unknown notification type")
    member = get_member(session, user_id)
    role = member_role_in_transaction(session, transaction, user_id)

    if notification_type == "join_request":
        ensure_open_chatbox(transaction)
        raise HTTPException(status_code=400, detail="Use the apply endpoint for join requests")

    if role is None:
        raise HTTPException(status_code=403, detail="Only accepted participants can create notifications")
    if transaction.archived:
        raise HTTPException(status_code=400, detail="Chatbox is archived")

    approver_id = None
    approver_role = None
    accepted = True
    default_message = message_text

    if notification_type in CONFIRM_NOTIFICATION_TYPES:
        accepted = False
        if notification_type == "confirm_direct_handoff":
            if transaction.courier_id is not None:
                raise HTTPException(status_code=400, detail="Direct handoff is only available without a courier")
            if role not in {"owner", "requester"} or not transaction.requester_id:
                raise HTTPException(status_code=400, detail="Direct handoff requires owner and requester")
            approver_role = "requester" if role == "owner" else "owner"
            default_message = default_message or "Direct handoff confirmation requested."
        elif notification_type == "confirm_handoff":
            if role not in {"owner", "courier"} or not transaction.courier_id:
                raise HTTPException(status_code=400, detail="Handoff requires owner and courier")
            if transaction.owner_confirmed:
                raise HTTPException(status_code=400, detail="Owner-courier handoff is already confirmed")
            approver_role = "courier" if role == "owner" else "owner"
            default_message = default_message or "Owner-courier handoff confirmation requested."
        elif notification_type == "confirm_delivered":
            if role not in {"requester", "courier"} or not transaction.requester_id or not transaction.courier_id:
                raise HTTPException(status_code=400, detail="Delivery requires requester and courier")
            if not transaction.owner_confirmed:
                raise HTTPException(status_code=400, detail="Owner-courier handoff must be confirmed first")
            if transaction.requester_confirmed:
                raise HTTPException(status_code=400, detail="Delivery is already confirmed")
            approver_role = "courier" if role == "requester" else "requester"
            default_message = default_message or "Requester delivery confirmation requested."
        approver_id = member_id_for_role(transaction, approver_role)
        if approver_id is None:
            raise HTTPException(status_code=400, detail="Required approver is not in this chatbox")
    else:
        default_message = default_message or f"{member.name} created a {notification_type.replace('_', ' ')} notification."

    return add_message(
        session,
        transaction.id,
        user_id,
        role,
        default_message,
        accepted,
        notification_type,
        approver_id,
        approver_role,
    )


def approve_notification(session: Session, transaction: ExchangeTransaction, notification: Message, user_id: int) -> None:
    if notification.notification_type is None:
        raise HTTPException(status_code=400, detail="Message is not a notification")
    if notification.approver_id is None or notification.approver_role is None:
        raise HTTPException(status_code=400, detail="Notification does not require approval")
    if notification.accepted:
        raise HTTPException(status_code=400, detail="Notification is already approved")

    approver_role = member_role_in_transaction(session, transaction, user_id)
    if user_id != notification.approver_id or approver_role != notification.approver_role:
        raise HTTPException(status_code=403, detail="This notification requires a different approver")

    if notification.notification_type == "join_request":
        ensure_open_chatbox(transaction)
        applicant = get_member(session, notification.user_id)
        if notification.applied_role not in {"requester", "courier"}:
            raise HTTPException(status_code=400, detail="Join request role is invalid")
        if applicant.id == transaction.owner_id:
            raise HTTPException(status_code=400, detail="Owner cannot fill requester or courier role")
        if notification.applied_role == "requester" and applicant.id == transaction.courier_id:
            raise HTTPException(status_code=400, detail="Requester and courier must be different members")
        if notification.applied_role == "courier" and applicant.id == transaction.requester_id:
            raise HTTPException(status_code=400, detail="Courier and requester must be different members")

        previous_role_messages = session.exec(
            select(Message).where(
                Message.transaction_id == transaction.id,
                Message.applied_role == notification.applied_role,
                Message.accepted == True,
            )
        ).all()
        for message in previous_role_messages:
            message.accepted = False
            session.add(message)
        if notification.applied_role == "requester":
            transaction.requester_id = applicant.id
        else:
            transaction.courier_id = applicant.id
        transaction.owner_confirmed = False
        transaction.requester_confirmed = False
        notification.accepted = True
        add_message(
            session,
            transaction.id,
            applicant.id,
            notification.applied_role,
            f"{applicant.name} joined as {notification.applied_role}.",
            True,
            "join",
        )
        delete_join_requests(session, transaction.id, applicant.id)
    elif notification.notification_type == "confirm_direct_handoff":
        if transaction.courier_id is not None:
            raise HTTPException(status_code=400, detail="Direct handoff is only available without a courier")
        transaction.owner_confirmed = True
        transaction.requester_confirmed = True
        notification.accepted = True
        complete_transaction_if_ready(session, transaction)
    elif notification.notification_type == "confirm_handoff":
        transaction.owner_confirmed = True
        transaction.locked = True
        notification.accepted = True
    elif notification.notification_type == "confirm_delivered":
        if not transaction.owner_confirmed:
            raise HTTPException(status_code=400, detail="Owner-courier handoff must be confirmed first")
        transaction.requester_confirmed = True
        notification.accepted = True
        complete_transaction_if_ready(session, transaction)
    else:
        raise HTTPException(status_code=400, detail="Notification type does not require approval")

    if transaction.points_applied:
        book = get_book(session, transaction.book_id)
        book.available = False
        session.add(book)
    if notification.notification_type != "join_request":
        session.add(notification)
    session.add(transaction)


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
    gender = normalize_gender(payload.gender)
    age = validate_age(payload.age)

    with Session(engine) as session:
        existing = get_member_by_email(session, payload.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email is already registered")
        member = Member(
            name=payload.name.strip(),
            email=payload.email.strip().lower(),
            password_hash=hash_password(payload.password),
            points=20,
            gender=gender,
            age=age,
            avatar_path=default_avatar_path(gender),
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


@app.get("/api/members/{member_id}/profile")
def get_member_profile(member_id: int) -> dict:
    """
    tl;dr: Return a public profile and the books posted by that member.
    input:
    * member_id: profile owner id
    output:
    * member dictionary plus posted book dictionaries
    """
    with Session(engine) as session:
        member = get_member(session, member_id)
        courier_member_ids = get_courier_member_ids(session)
        books = session.exec(select(Book).where(Book.owner_id == member_id).order_by(Book.id)).all()
        return {
            "member": member_to_dict(member, courier_member_ids),
            "books": [book_to_dict(book, member) for book in books],
        }


@app.get("/api/members/{member_id}/request-budget")
def get_request_budget(
    member_id: int,
    transaction_id: Optional[int] = None,
    book_id: Optional[int] = None,
) -> dict:
    """
    tl;dr: Return aggregate available points for requester applications.
    input:
    * member_id: member whose requester budget should be calculated
    * transaction_id: optional transaction being requested
    * book_id: optional book being requested when no transaction exists yet
    output:
    * current, reserved, available, and optional required point summary
    """
    with Session(engine) as session:
        member = get_member(session, member_id)
        transaction = get_transaction(session, transaction_id) if transaction_id is not None else None
        book = get_book(session, book_id) if transaction is None and book_id is not None else None
        return requester_budget_to_dict(session, member, transaction, book)


@app.get("/api/members/{member_id}/messages")
def list_member_messages(member_id: int) -> list[dict]:
    """
    tl;dr: Return every visible message stream for a member, newest first, excluding their own messages.
    input:
    * member_id: member viewing the merged dropdown
    output:
    * visible message dictionaries with book context
    """
    with Session(engine) as session:
        get_member(session, member_id)
        messages = visible_messages_for_dropdown(session, member_id)
        return [message_to_activity_dict(session, message) for message in messages]


@app.get("/api/members/{member_id}/applications")
def list_member_applications(member_id: int) -> list[dict]:
    """
    tl;dr: Return pending join request applications created by one member.
    input:
    * member_id: member whose pending applications should be returned
    output:
    * pending join request dictionaries with book context
    """
    with Session(engine) as session:
        get_member(session, member_id)
        messages = session.exec(
            select(Message).where(
                Message.user_id == member_id,
                Message.notification_type == "join_request",
                Message.accepted == False,
            )
        ).all()
        return [
            message_to_activity_dict(session, message)
            for message in sorted(messages, key=lambda row: (utc_timestamp(row.timestamp), row.message_id or 0), reverse=True)
        ]


@app.put("/api/members/{member_id}/profile")
def update_member_profile(
    member_id: int,
    name: str = Form(...),
    gender: str = Form(...),
    age: int = Form(...),
    biography: str = Form(""),
    avatar: Optional[UploadFile] = File(None),
    authorization: str = Header(default=""),
) -> dict:
    """
    tl;dr: Update editable profile fields for the authenticated member.
    input:
    * member_id: profile owner id
    * name, gender, age, biography: editable profile fields
    * avatar: optional uploaded avatar image
    * authorization: bearer token for the current member
    output:
    * updated member dictionary
    """
    if not name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    normalized_gender = normalize_gender(gender)
    validated_age = validate_age(age)

    with Session(engine) as session:
        current_member = get_current_member(session, authorization)
        if current_member.id != member_id:
            raise HTTPException(status_code=403, detail="Only the profile owner can edit this profile")

        previous_gender = current_member.gender
        current_member.name = name.strip()
        current_member.gender = normalized_gender
        current_member.age = validated_age
        current_member.biography = biography.strip()
        uploaded_avatar_path = save_avatar(avatar)
        if uploaded_avatar_path:
            current_member.avatar_path = uploaded_avatar_path
        elif current_member.avatar_path == default_avatar_path(previous_gender):
            current_member.avatar_path = default_avatar_path(normalized_gender)

        session.add(current_member)
        session.commit()
        session.refresh(current_member)
        courier_member_ids = get_courier_member_ids(session)
        return member_to_dict(current_member, courier_member_ids)


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
        new_member = Member(
            name=member.name,
            email=member.email.strip().lower(),
            points=20,
            gender="male",
            age=18,
            avatar_path=default_avatar_path("male"),
        )
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
    description: str = Form(""),
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
    * description: optional book description
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
            description=description,
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
    description: str = Form(""),
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
    * description: optional updated book description
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
        book.description = description
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


@app.delete("/api/books/{book_id}")
def delete_book(book_id: int, owner_id: int) -> dict:
    """
    tl;dr: Delete one owner-owned book unless its transaction is locked or archived.
    input:
    * book_id: book being deleted
    * owner_id: member who owns the book
    output:
    * dictionary showing the book was deleted
    """
    with Session(engine) as session:
        book = get_book(session, book_id)
        if book.owner_id != owner_id:
            raise HTTPException(status_code=403, detail="Only the owner can delete this book")

        transactions = session.exec(select(ExchangeTransaction).where(ExchangeTransaction.book_id == book.id)).all()
        if any(transaction.locked or transaction.archived for transaction in transactions):
            raise HTTPException(status_code=400, detail="Locked or archived books cannot be deleted")

        transaction_ids = [transaction.id for transaction in transactions if transaction.id is not None]
        if transaction_ids:
            messages = session.exec(select(Message).where(Message.transaction_id.in_(transaction_ids))).all()
            for message in messages:
                session.delete(message)
        for transaction in transactions:
            session.delete(transaction)
        session.delete(book)
        session.commit()
        return {"deleted": True}


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
        existing = session.exec(
            select(ExchangeTransaction).where(
                ExchangeTransaction.book_id == book.id,
                ExchangeTransaction.archived == False,
            )
        ).first()
        if existing:
            requester = get_member(session, existing.requester_id) if existing.requester_id else None
            courier = get_member(session, existing.courier_id) if existing.courier_id else None
            return transaction_to_dict(existing, book, owner, requester, courier)
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
            statement = statement.where((Message.accepted == True) | (Message.notification_type != None))

        messages = session.exec(statement.order_by(Message.timestamp, Message.message_id)).all()
        return [message_to_dict(message, get_member(session, message.user_id)) for message in messages]


@app.post("/api/activity")
def mark_activity(payload: ActivityMark) -> dict:
    """
    tl;dr: Mark one member activity stream as viewed at the current time.
    input:
    * payload: member id, optional transaction id, and tab name
    output:
    * stored activity tracking row
    """
    tab = normalize_activity_tab(payload.tab)
    transaction_id = None if tab == "dropdown" else payload.transaction_id
    if tab != "dropdown" and transaction_id is None:
        raise HTTPException(status_code=400, detail="transaction_id is required for this tab")

    with Session(engine) as session:
        get_member(session, payload.member_id)
        transaction = get_transaction(session, transaction_id) if transaction_id is not None else None
        if transaction is not None:
            message_scope_statement(session, payload.member_id, tab, transaction)

        activity = get_activity_tracking(session, payload.member_id, tab, transaction_id)
        now = datetime.now(timezone.utc)
        if activity is None:
            activity = ActivityTracking(
                member_id=payload.member_id,
                transaction_id=transaction_id,
                tab=tab,
                last_timestamp=now,
            )
        else:
            activity.last_timestamp = now
        session.add(activity)
        session.commit()
        session.refresh(activity)
        return {
            "member_id": activity.member_id,
            "transaction_id": activity.transaction_id,
            "tab": activity.tab,
            "last_timestamp": activity.last_timestamp.isoformat(),
        }


@app.get("/api/activity/unread")
def get_unread_counts(member_id: int, transaction_id: Optional[int] = None) -> dict:
    """
    tl;dr: Return unread message counts for dropdown and optionally one transaction's tabs.
    input:
    * member_id: member viewing messages
    * transaction_id: optional transaction for chatbox and notification counts
    output:
    * unread counts by tab
    """
    with Session(engine) as session:
        get_member(session, member_id)
        counts = {"dropdown": unread_count(session, member_id, "dropdown", None)}
        if transaction_id is not None:
            counts["chatbox"] = unread_count(session, member_id, "chatbox", transaction_id)
            counts["notification"] = unread_count(session, member_id, "notification", transaction_id)
        return counts


@app.post("/api/transactions/{transaction_id}/notifications")
def create_notification(transaction_id: int, payload: NotificationCreate) -> dict:
    """
    tl;dr: Create a public chatbox notification, optionally requiring role-based approval.
    input:
    * transaction_id: chatbox transaction id
    * payload: sender id, notification type, and optional message body
    output:
    * created notification dictionary
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        message = create_participant_notification(
            session,
            transaction,
            payload.user_id,
            payload.notification_type,
            payload.message,
        )
        session.commit()
        session.refresh(message)
        return message_to_dict(message, get_member(session, message.user_id))


@app.post("/api/transactions/{transaction_id}/notifications/{message_id}/approve")
def approve_transaction_notification(transaction_id: int, message_id: int, payload: NotificationApproval) -> dict:
    """
    tl;dr: Approve one notification when the current member matches its required approver id and role.
    input:
    * transaction_id: chatbox transaction id
    * message_id: notification message id
    * payload: member approving the notification
    output:
    * updated transaction dictionary
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        notification = session.get(Message, message_id)
        if not notification or notification.transaction_id != transaction_id:
            raise HTTPException(status_code=404, detail="Notification not found")
        approve_notification(session, transaction, notification, payload.user_id)
        session.commit()
        session.refresh(transaction)
        return transaction_membership_to_dict(session, transaction)


@app.get("/api/transactions/{transaction_id}/application-stats")
def get_application_stats(transaction_id: int) -> dict:
    """
    tl;dr: Return public-safe real-time application stats for requester and courier roles.
    input:
    * transaction_id: chatbox transaction id
    output:
    * unique pending applicant counts and accepted status per role
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        return application_stats_to_dict(session, transaction)


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
        if transaction.archived:
            raise HTTPException(status_code=400, detail="Chatbox is archived")
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
        if member_role_in_transaction(session, transaction, member.id) is not None:
            raise HTTPException(status_code=400, detail="Accepted participants must leave before re-applying")
        if payload.applied_role == "requester" and member.id == transaction.courier_id:
            raise HTTPException(status_code=400, detail="Requester and courier must be different members")
        if payload.applied_role == "courier" and member.id == transaction.requester_id:
            raise HTTPException(status_code=400, detail="Courier and requester must be different members")
        if payload.applied_role == "requester":
            ensure_requester_budget(session, member, transaction)

        message = add_or_replace_join_request(
            session,
            transaction,
            member.id,
            payload.applied_role,
            payload.message,
        )
        session.commit()
        session.refresh(message)
        return message_to_dict(message, member)


@app.post("/api/transactions/{transaction_id}/withdraw-application")
def withdraw_application(transaction_id: int, payload: WithdrawApplication) -> dict:
    """
    tl;dr: Delete a member's pending join request application for one transaction.
    input:
    * transaction_id: transaction whose application should be withdrawn
    * payload: member id withdrawing their join request
    output:
    * dictionary showing whether a join request was withdrawn
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        ensure_open_chatbox(transaction)
        member = get_member(session, payload.user_id)
        if member_role_in_transaction(session, transaction, member.id) is not None:
            raise HTTPException(status_code=400, detail="Accepted participants must leave instead")
        messages = session.exec(
            select(Message).where(
                Message.transaction_id == transaction_id,
                Message.user_id == member.id,
                Message.notification_type == "join_request",
                Message.accepted == False,
            )
        ).all()
        for message in messages:
            session.delete(message)
        session.commit()
        return {"withdrawn": len(messages) > 0}


@app.get("/api/transactions/{transaction_id}/application")
def get_my_application(transaction_id: int, user_id: int) -> Optional[dict]:
    """
    tl;dr: Return one member's pending join request for a transaction.
    input:
    * transaction_id: transaction whose application should be inspected
    * user_id: member whose join request should be loaded
    output:
    * pending join request dictionary or None
    """
    with Session(engine) as session:
        get_transaction(session, transaction_id)
        member = get_member(session, user_id)
        message = session.exec(
            select(Message).where(
                Message.transaction_id == transaction_id,
                Message.user_id == member.id,
                Message.notification_type == "join_request",
                Message.accepted == False,
            )
        ).first()
        return message_to_dict(message, member) if message else None


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
                Message.notification_type == "join_request",
                Message.accepted == False,
            ).order_by(Message.timestamp, Message.message_id)
        ).all()
        if not applicant_messages:
            raise HTTPException(status_code=400, detail="Member has not applied for this role")
        approve_notification(session, transaction, applicant_messages[-1], payload.owner_id)
        session.commit()
        session.refresh(transaction)
        return transaction_membership_to_dict(session, transaction)


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
        delete_pending_approval_messages(session, transaction_id, payload.user_id)
        add_message(
            session,
            transaction_id,
            payload.user_id,
            role,
            f"{get_member(session, payload.user_id).name} left the chatbox.",
            True,
            "leave",
        )
        if role == "requester":
            transaction.requester_id = None
        else:
            transaction.courier_id = None
        transaction.owner_confirmed = False
        transaction.requester_confirmed = False
        session.add(transaction)
        session.commit()
        session.refresh(transaction)
        return transaction_membership_to_dict(session, transaction)


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
        delete_pending_approval_messages(session, transaction_id, payload.user_id)
        add_message(
            session,
            transaction_id,
            payload.user_id,
            payload.applied_role,
            f"{get_member(session, payload.user_id).name} was removed from the chatbox.",
            True,
            "kicked",
        )
        if payload.applied_role == "requester":
            transaction.requester_id = None
        else:
            transaction.courier_id = None
        transaction.owner_confirmed = False
        transaction.requester_confirmed = False
        session.add(transaction)
        session.commit()
        session.refresh(transaction)
        return transaction_membership_to_dict(session, transaction)


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
        if transaction.archived:
            raise HTTPException(status_code=400, detail="Transaction is archived")
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
        an = Member(
            name="An",
            email="an@example.com",
            password_hash=hash_password(demo_password),
            points=20,
            gender="male",
            age=22,
            avatar_path=default_avatar_path("male"),
            biography="Software books and practical reading notes.",
        )
        binh = Member(
            name="Binh",
            email="binh@example.com",
            password_hash=hash_password(demo_password),
            points=20,
            gender="male",
            age=24,
            avatar_path=default_avatar_path("male"),
            biography="Fantasy and old paperbacks.",
        )
        chi = Member(
            name="Chi",
            email="chi@example.com",
            password_hash=hash_password(demo_password),
            points=20,
            gender="female",
            age=21,
            avatar_path=default_avatar_path("female"),
            biography="Likes well-used technical books.",
        )
        dung = Member(
            name="Dung",
            email="dung@example.com",
            password_hash=hash_password(demo_password),
            points=20,
            gender="male",
            age=26,
            avatar_path=default_avatar_path("male"),
            biography="Science fiction and delivery-friendly swaps.",
        )
        giang = Member(
            name="Giang",
            email="giang@example.com",
            password_hash=hash_password(demo_password),
            points=20,
            gender="female",
            age=23,
            avatar_path=default_avatar_path("female"),
            biography="Habit, design, and self-improvement shelves.",
        )
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
