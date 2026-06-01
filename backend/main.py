from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import Field, SQLModel, Session, create_engine, select


DATABASE_URL = "sqlite:///db.sqlite3"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


class Member(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    contact: str
    points: int = 20
    is_courier: bool = False


class MemberCreate(SQLModel):
    name: str
    contact: str


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


class BookCreate(SQLModel):
    owner_id: int
    title: str
    genre: str
    author: str
    publication_year: int
    condition: str
    exchange_mode: str = "permanent"


class ExchangeTransaction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    book_id: int = Field(foreign_key="book.id")
    owner_id: int = Field(foreign_key="member.id")
    requester_id: int = Field(foreign_key="member.id")
    exchange_mode: str
    delivery_mode: str = "direct"
    courier_id: Optional[int] = Field(default=None, foreign_key="member.id")
    note: str = ""
    owner_confirmed: bool = False
    requester_confirmed: bool = False
    status: str = "pending"
    points_applied: bool = False


class TransactionCreate(SQLModel):
    book_id: int
    requester_id: int
    delivery_mode: str = "direct"
    courier_id: Optional[int] = None
    note: str = ""


class ConfirmRequest(SQLModel):
    member_id: int


app = FastAPI(title="Book Exchange Club Prototype")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        "owner_contact": owner.contact,
        "title": book.title,
        "genre": book.genre,
        "author": book.author,
        "publication_year": book.publication_year,
        "condition": book.condition,
        "exchange_mode": book.exchange_mode,
        "available": book.available,
    }


def transaction_to_dict(
    transaction: ExchangeTransaction,
    book: Book,
    owner: Member,
    requester: Member,
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
        "requester_name": requester.name,
        "exchange_mode": transaction.exchange_mode,
        "delivery_mode": transaction.delivery_mode,
        "courier_id": transaction.courier_id,
        "courier_name": courier.name if courier else "",
        "note": transaction.note,
        "owner_confirmed": transaction.owner_confirmed,
        "requester_confirmed": transaction.requester_confirmed,
        "status": transaction.status,
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

    owner = get_member(session, transaction.owner_id)
    requester = get_member(session, transaction.requester_id)
    point_value = points_for_mode(transaction.exchange_mode)

    owner.points += point_value
    requester.points -= point_value
    if transaction.courier_id:
        courier = get_member(session, transaction.courier_id)
        courier.points += 2
        session.add(courier)

    transaction.status = "completed"
    transaction.points_applied = True
    session.add(owner)
    session.add(requester)
    session.add(transaction)


@app.on_event("startup")
def on_startup() -> None:
    """
    tl;dr: Create all DB tables on startup if they do not exist yet.
    output:
    * None
    """
    SQLModel.metadata.create_all(engine)


@app.get("/api/health")
def health() -> dict:
    """
    tl;dr: Return a quick backend health check.
    output:
    * dictionary showing the API is running
    """
    return {"ok": True}


@app.get("/api/members")
def list_members() -> list[Member]:
    """
    tl;dr: Return all registered members.
    output:
    * list of Member records
    """
    with Session(engine) as session:
        return session.exec(select(Member).order_by(Member.id)).all()


@app.post("/api/members")
def create_member(member: MemberCreate) -> Member:
    """
    tl;dr: Register a new exchange member with 20 starting points.
    input:
    * member: member name and contact details
    output:
    * created Member record
    """
    with Session(engine) as session:
        new_member = Member(name=member.name, contact=member.contact, points=20)
        session.add(new_member)
        session.commit()
        session.refresh(new_member)
        return new_member


@app.post("/api/members/{member_id}/courier")
def register_courier(member_id: int) -> Member:
    """
    tl;dr: Mark an existing member as a free courier.
    input:
    * member_id: id of the member volunteering for deliveries
    output:
    * updated Member record
    """
    with Session(engine) as session:
        member = get_member(session, member_id)
        member.is_courier = True
        session.add(member)
        session.commit()
        session.refresh(member)
        return member


@app.get("/api/books")
def list_books() -> list[dict]:
    """
    tl;dr: Return all books with owner names and contact details.
    output:
    * list of dictionaries describing books and owners
    """
    with Session(engine) as session:
        books = session.exec(select(Book).order_by(Book.id)).all()
        return [book_to_dict(book, get_member(session, book.owner_id)) for book in books]


@app.post("/api/books")
def create_book(book: BookCreate) -> dict:
    """
    tl;dr: Add a member-owned book to the exchange catalog.
    input:
    * book: book details and owning member id
    output:
    * created book dictionary with owner details
    """
    points_for_mode(book.exchange_mode)
    with Session(engine) as session:
        owner = get_member(session, book.owner_id)
        new_book = Book(
            owner_id=book.owner_id,
            title=book.title,
            genre=book.genre,
            author=book.author,
            publication_year=book.publication_year,
            condition=book.condition,
            exchange_mode=book.exchange_mode,
        )
        session.add(new_book)
        session.commit()
        session.refresh(new_book)
        return book_to_dict(new_book, owner)


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
            requester = get_member(session, transaction.requester_id)
            courier = get_member(session, transaction.courier_id) if transaction.courier_id else None
            rows.append(transaction_to_dict(transaction, book, owner, requester, courier))
        return rows


@app.post("/api/transactions")
def create_transaction(payload: TransactionCreate) -> dict:
    """
    tl;dr: Create a pending exchange request for an available book.
    input:
    * payload: requested book, requester, delivery choice, optional courier, and note
    output:
    * created transaction dictionary
    """
    with Session(engine) as session:
        book = get_book(session, payload.book_id)
        if not book.available:
            raise HTTPException(status_code=400, detail="Book is not available")

        owner = get_member(session, book.owner_id)
        requester = get_member(session, payload.requester_id)
        if owner.id == requester.id:
            raise HTTPException(status_code=400, detail="Requester cannot be the book owner")

        delivery_mode = payload.delivery_mode
        if delivery_mode not in {"direct", "courier"}:
            raise HTTPException(status_code=400, detail="delivery_mode must be direct or courier")

        courier = None
        if delivery_mode == "courier":
            if not payload.courier_id:
                raise HTTPException(status_code=400, detail="Choose a courier for courier delivery")
            courier = get_member(session, payload.courier_id)
            if not courier.is_courier:
                raise HTTPException(status_code=400, detail="Selected member is not a courier")
            if courier.id in {owner.id, requester.id}:
                raise HTTPException(status_code=400, detail="Courier must be a third member")

        transaction = ExchangeTransaction(
            book_id=book.id,
            owner_id=owner.id,
            requester_id=requester.id,
            exchange_mode=book.exchange_mode,
            delivery_mode=delivery_mode,
            courier_id=courier.id if courier else None,
            note=payload.note,
        )
        book.available = False
        session.add(book)
        session.add(transaction)
        session.commit()
        session.refresh(transaction)
        session.refresh(book)
        return transaction_to_dict(transaction, book, owner, requester, courier)


@app.post("/api/transactions/{transaction_id}/confirm")
def confirm_transaction(transaction_id: int, payload: ConfirmRequest) -> dict:
    """
    tl;dr: Confirm a transaction for the owner or requester and apply points if both confirmed.
    input:
    * transaction_id: id of the transaction being confirmed
    * payload: member id of the confirming owner or requester
    output:
    * updated transaction dictionary
    """
    with Session(engine) as session:
        transaction = get_transaction(session, transaction_id)
        if payload.member_id == transaction.owner_id:
            transaction.owner_confirmed = True
        elif payload.member_id == transaction.requester_id:
            transaction.requester_confirmed = True
        else:
            raise HTTPException(status_code=400, detail="Only the owner or requester can confirm")

        complete_transaction_if_ready(session, transaction)
        session.add(transaction)
        session.commit()
        session.refresh(transaction)

        book = get_book(session, transaction.book_id)
        owner = get_member(session, transaction.owner_id)
        requester = get_member(session, transaction.requester_id)
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

        an = Member(name="An", contact="an@example.com", points=20)
        binh = Member(name="Binh", contact="binh@example.com", points=20, is_courier=True)
        chi = Member(name="Chi", contact="chi@example.com", points=20)
        session.add(an)
        session.add(binh)
        session.add(chi)
        session.commit()
        session.refresh(an)
        session.refresh(binh)
        session.refresh(chi)

        books = [
            Book(
                owner_id=an.id,
                title="Clean Code",
                genre="Software",
                author="Robert C. Martin",
                publication_year=2008,
                condition="Good",
                exchange_mode="loan",
            ),
            Book(
                owner_id=chi.id,
                title="The Pragmatic Programmer",
                genre="Software",
                author="Andrew Hunt, David Thomas",
                publication_year=1999,
                condition="Used",
                exchange_mode="permanent",
            ),
        ]
        for book in books:
            session.add(book)
        session.commit()
        return {"created": True, "message": "Demo data created"}


app.mount("/", StaticFiles(directory="../mock_frontend", html=True), name="frontend")
