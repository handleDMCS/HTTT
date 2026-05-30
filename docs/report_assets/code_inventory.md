# Code Inventory

Root: `C:\Users\Administrator.LS102-26\Documents\HTTT`

## Project Texts
- `IDEA.md`: * A book club wants to build an app that connects members for the purpose of exchanging books. * After registering as a book-exchange member, each member receives **20 points**. * Members can update the list of books they want to exchange, including: * Book title * Genre * Author name * Year of publication * Book condition * Members who do not have books to exchange can register as free book deliverers. * Free book deliverers earn **2 reward points** for each successful delivery. * Members can choose between two types of book exchange: * Permanent exchange, with no return required * Lending, w
- `backend/AGENTS.md`: --- name: rapid-prototyping description: > Opinionated stack for hackathons and time-boxed sprints: FastAPI + uv (single file) + SQLite via SQLModel. Data is inspected via FastAPI's built-in /docs and sqlite-web. Trigger on any time pressure or demo context — "just get it working", "we have X hours", "MVP by end of day". --- # Rapid Prototyping Skill ## Context You are helping build a **functional prototype in a 24-hour hackathon**. The only goal is a working demo by the end of the sprint. Polish, scalability, and best practices are explicitly out of scope. Speed and clarity win. --- ## Stack 
- `frontend/AGENTS.md`: ## Skills Skills are located in `.agents/skills/`. **Always read and follow all skills before writing any code:** - `.agents/skills/svelte5-syntax/SKILL.md` - `.agents/skills/anthropic-style/SKILL.md` ## Side Note **IMPORTANT**: The dev server is on http://localhost:5173/. If you can't invoke it, DON'T ATTEMPT TO SPIN UP A NEW ONE, ask me to do it for you.

## Backend

Source: `backend\main.py`

Constants:
- `DATABASE_URL` = `"sqlite:///db.sqlite3"`
- `JWT_EXPIRE_HOURS` = `72`
- `PIC_DIR` = `"pic"`
- `AVATAR_DIR` = `"avatar"`

### Table Models

#### Member (`backend/main.py:27`)

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `Optional[int]` | PK, default |
| `name` | `str` |  |
| `email` | `str` |  |
| `password_hash` | `str` |  |
| `points` | `int` |  |
| `gender` | `str` |  |
| `age` | `int` |  |
| `avatar_path` | `str` |  |
| `biography` | `str` |  |

#### Book (`backend/main.py:52`)

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `Optional[int]` | PK, default |
| `owner_id` | `int` | FK |
| `title` | `str` |  |
| `genre` | `str` |  |
| `author` | `str` |  |
| `description` | `str` |  |
| `publication_year` | `int` |  |
| `condition` | `str` |  |
| `exchange_mode` | `str` |  |
| `available` | `bool` |  |
| `picture_path` | `str` |  |

#### ExchangeTransaction (`backend/main.py:88`)

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `Optional[int]` | PK, default |
| `book_id` | `int` | FK |
| `owner_id` | `int` | FK |
| `exchange_mode` | `str` |  |
| `requester_id` | `Optional[int]` | FK, default |
| `courier_id` | `Optional[int]` | FK, default |
| `owner_confirmed` | `bool` |  |
| `requester_confirmed` | `bool` |  |
| `locked` | `bool` |  |
| `points_applied` | `bool` |  |
| `archived` | `bool` |  |

#### Message (`backend/main.py:108`)

| Field | Type | Notes |
| --- | --- | --- |
| `message_id` | `Optional[int]` | PK, default |
| `user_id` | `int` | FK |
| `transaction_id` | `int` | FK |
| `message` | `str` |  |
| `applied_role` | `str` |  |
| `notification_type` | `Optional[str]` |  |
| `approver_id` | `Optional[int]` | FK, default |
| `approver_role` | `Optional[str]` |  |
| `accepted` | `bool` |  |
| `timestamp` | `datetime` |  |

#### ActivityTracking (`backend/main.py:132`)

| Field | Type | Notes |
| --- | --- | --- |
| `id` | `Optional[int]` | PK, default |
| `member_id` | `int` | FK |
| `transaction_id` | `Optional[int]` | FK, default |
| `tab` | `str` |  |
| `last_timestamp` | `datetime` |  |

### API Routes

| Method | Path | Function | Summary |
| --- | --- | --- | --- |
| `GET` | `/api/health` | `health` | Return a quick backend health check. |
| `POST` | `/api/auth/register` | `register` | Register a member and return an access token. |
| `POST` | `/api/auth/login` | `login` | Authenticate a member and return an access token. |
| `GET` | `/api/auth/me` | `me` | Return the member attached to a bearer token. |
| `GET` | `/api/members` | `list_members` | Return all registered members. |
| `GET` | `/api/members/{member_id}/profile` | `get_member_profile` | Return a public profile and the books posted by that member. |
| `GET` | `/api/members/{member_id}/request-budget` | `get_request_budget` | Return aggregate available points for requester applications. |
| `GET` | `/api/members/{member_id}/messages` | `list_member_messages` | Return every visible message stream for a member, newest first, excluding their own messages. |
| `GET` | `/api/members/{member_id}/applications` | `list_member_applications` | Return pending join request applications created by one member. |
| `PUT` | `/api/members/{member_id}/profile` | `update_member_profile` | Update editable profile fields for the authenticated member. |
| `POST` | `/api/members` | `create_member` | Register a new exchange member with 20 starting points. |
| `GET` | `/api/books` | `list_books` | Return all books with owner names and email addresses. |
| `POST` | `/api/books` | `create_book` | Add a member-owned book to the exchange catalog. |
| `POST` | `/api/books/{book_id}/renew` | `renew_loan_book` | Clone an archived loan book into a fresh independent listing. |
| `PUT` | `/api/books/{book_id}` | `update_book` | Update one book owned by a member. |
| `DELETE` | `/api/books/{book_id}` | `delete_book` | Delete one owner-owned book only while its chatbox has no accepted participants. |
| `GET` | `/api/transactions` | `list_transactions` | Return all exchange transactions with readable names. |
| `POST` | `/api/transactions` | `create_transaction` | Create a chatbox transaction for an available book. |
| `GET` | `/api/transactions/{transaction_id}/messages` | `list_messages` | Return visible chatbox messages for one member. |
| `POST` | `/api/activity` | `mark_activity` | Mark one member activity stream as viewed at the current time. |
| `GET` | `/api/activity/unread` | `get_unread_counts` | Return unread message counts for dropdown and optionally one transaction's tabs. |
| `POST` | `/api/transactions/{transaction_id}/notifications` | `create_notification` | Create a public chatbox notification, optionally requiring role-based approval. |
| `POST` | `/api/transactions/{transaction_id}/notifications/{message_id}/approve` | `approve_transaction_notification` | Approve one notification when the current member matches its required approver id and role. |
| `GET` | `/api/transactions/{transaction_id}/application-stats` | `get_application_stats` | Return public-safe real-time application stats for requester and courier roles. |
| `POST` | `/api/transactions/{transaction_id}/messages` | `create_chat_message` | Add a normal visible message from an accepted chatbox participant. |
| `POST` | `/api/transactions/{transaction_id}/apply` | `apply_to_chatbox` | Save a requester or courier application as an owner-visible intro message. |
| `POST` | `/api/transactions/{transaction_id}/withdraw-application` | `withdraw_application` | Delete a member's pending join request application for one transaction. |
| `GET` | `/api/transactions/{transaction_id}/application` | `get_my_application` | Return one member's pending join request for a transaction. |
| `POST` | `/api/transactions/{transaction_id}/accept` | `accept_participant` | Let the owner approve one requester or courier and revoke the previous accepted member for that role. |
| `POST` | `/api/transactions/{transaction_id}/leave` | `leave_chatbox` | Let an accepted requester or courier leave an unlocked chatbox without deleting their messages. |
| `POST` | `/api/transactions/{transaction_id}/kick` | `kick_participant` | Let the owner remove an accepted requester or courier without deleting their messages. |
| `POST` | `/api/transactions/confirm-meeting` | `confirm_meeting` | Confirm that two accepted chatbox participants physically met. |
| `POST` | `/api/demo-seed` | `demo_seed` | Add sample members and books when the database is empty. |

## Frontend

API base: `http://localhost:8000`
API types: `Member`, `Book`, `Transaction`, `ChatMessage`, `ActivityMessage`, `UnreadCounts`, `RoleApplicationStats`, `ApplicationStats`, `RequestBudget`, `MemberProfile`

### Pages

| Route | File | API calls | Navigation |
| --- | --- | --- | --- |
| `/` | `frontend\src\routes\+layout.svelte` | `/api/activity`<br>`/api/activity/unread?member_id=${latestMember.id}`<br>`/api/activity/unread?member_id=${member.id}`<br>`/api/members/${latestMember.id}/messages`<br>`/api/members/${latestMember.id}/request-budget` | `/login`<br>`/profile/${member?.id}` |
| `/` | `frontend\src\routes\+page.svelte` |  |  |
| `/books` | `frontend\src\routes\books\+page.svelte` | `/api/books`<br>`/api/transactions`<br>`/api/books/${book.id}/renew?owner_id=${ownerId}`<br>`/api/books/${book.id}?owner_id=${member.id}`<br>`/api/members/${member.id}/applications` | `/books/new?mode=new`<br>`/login`<br>`/books/new?mode=edit&book_id=${book.id}` |
| `/books/:id` | `frontend\src\routes\books\[id]\+page.svelte` | `/api/activity`<br>`/api/books`<br>`/api/transactions`<br>`/api/activity/unread?member_id=${member.id}&transaction_id=${transaction.id}`<br>`/api/members/${member.id}/request-budget?${params.toString()}`<br>`/api/members/${userId}/profile`<br>`/api/transactions/${currentTransaction.id}/apply`<br>`/api/transactions/${transaction.id}/application-stats`<br>`/api/transactions/${transaction.id}/application?user_id=${member.id}`<br>`/api/transactions/${transaction.id}/kick`<br>`/api/transactions/${transaction.id}/leave`<br>`/api/transactions/${transaction.id}/messages`<br>`/api/transactions/${transaction.id}/messages?member_id=${member.id}`<br>`/api/transactions/${transaction.id}/notifications`<br>`/api/transactions/${transaction.id}/notifications/${message.message_id}/approve`<br>`/api/transactions/${transaction.id}/withdraw-application` | `/books`<br>`/login`<br>`/profile/${userId}` |
| `/books/new` | `frontend\src\routes\books\new\+page.svelte` | `/api/books`<br>`/api/books/${bookId}` | `/books`<br>`/login` |
| `/login` | `frontend\src\routes\login\+page.svelte` |  | `/books` |
| `/profile/:id` | `frontend\src\routes\profile\[id]\+page.svelte` | `/api/members/${page.params.id}/profile`<br>`/api/members/${profile.member.id}/profile` | `/login`<br>`/books/${book.id}?tab=${encodeURIComponent('book info')}` |

### Frontend Dependencies

- `@lucide/svelte`: `^1.3.0`
- `@sveltejs/adapter-auto`: `^7.0.1`
- `@sveltejs/kit`: `^2.57.0`
- `@sveltejs/vite-plugin-svelte`: `^7.0.0`
- `@tailwindcss/typography`: `^0.5.19`
- `@tailwindcss/vite`: `^4.2.2`
- `@types/node`: `^25.9.1`
- `svelte`: `^5.55.2`
- `svelte-check`: `^4.4.6`
- `tailwindcss`: `^4.2.2`
- `typescript`: `^6.0.2`
- `vite`: `^8.0.7`
