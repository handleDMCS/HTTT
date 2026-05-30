# Book Exchange Club - Speaking Script

Target timing: about 8 to 10 minutes for 15 slides.

## Slide 1 - Team Introduction

Good afternoon. We are team ĐT2.N15. Our members are Trương Tuấn Dũng, student ID 21020058, and Đặng Anh Tôn, student ID 23020146.

Today we are presenting Book Exchange Club, a prototype that helps members of a book club exchange and lend books.

The main point I want to make from the beginning is this: our project is not only a book catalog. The catalog helps people find books, but the most important part is the transaction behind each exchange.

## Slide 2 - Project Objective and Scope

The project objective is to turn informal book exchange into a controlled workflow.

In a normal club, people might post books in a chat group and then message privately. That works at small scale, but it creates unclear status, unclear delivery, and unclear point updates.

Our scope covers member accounts, book listings, two exchange modes, an optional courier role, chatbox coordination, physical handoff confirmation, point updates, and a final archive.

Members start with 20 points. A permanent exchange uses 10 points. A loan uses 5 points. A volunteer courier can earn 2 points after a successful delivery.

## Slide 3 - The Core Problem

Discovery is easy. Trust is the real workflow.

If the system is only a catalog, important decisions happen outside the system. The owner does not have a structured way to choose a requester or courier. The delivery status can become ambiguous after people meet. A requester can commit to more books than their points can cover. And after completion, there may be no shared record explaining why points changed.

Our prototype solves this by making the transaction the source of truth.

Applications and approvals attach roles to the transaction. Physical handoff is confirmed by the correct two people. Budget is checked before a requester can overcommit. Finally, the archive preserves the result.

## Slide 4 - Prototype Structure

The implementation is intentionally compact for a hackathon.

The backend is a single Python file: `backend/main.py`. It uses FastAPI for routes, SQLModel for models, and SQLite for local persistence. This file contains the member, book, transaction, message, and activity tracking logic.

The frontend is written in Svelte. It provides the book list, book details, chatbox tabs, role application UI, confirmation buttons, profile view, and archive cards.

The `docs` folder contains the technical report, including requirements, architecture, diagrams, API descriptions, UI design, testing, and deployment notes.

The important point is that even with a small codebase, the full business loop is implemented.

## Slide 5 - Core Model

The central model is the transaction.

A transaction binds one book to the participants and state flags that control the exchange. It has an owner, an optional requester, and an optional courier. It stores confirmation flags, lock state, whether points have already been applied, and whether the transaction is archived.

This design makes the rest of the app consistent. The UI can decide what a user is allowed to do based on their role in the transaction. The backend can decide when points are allowed to move. The archive can explain the outcome later.

So, from first principles, a transaction is the unit of trust.

## Slide 6 - Role Application Flow

The first important mechanism is role application.

A role is not claimed automatically. It is requested, reviewed, and accepted.

The flow is: a member finds a book, chooses to apply as requester or courier, writes an intro message, the owner receives a join request notification, and the owner approves one person for that role.

When approved, the transaction stores that member as the requester or courier.

The backend also blocks invalid role combinations. The owner cannot apply to their own book. The same member cannot be both requester and courier in the same transaction. Accepted participants must leave before re-applying.

This gives the owner control while keeping the process visible inside the transaction.

## Slide 7 - Open State

The transaction begins in the open state.

Open does not mean uncontrolled. It means the transaction is still negotiable.

In this state, people can apply, withdraw applications, chat, and coordinate meetup details. The owner can accept or replace a requester or courier. An accepted requester or courier can leave, and the owner can remove them if necessary.

But the system still enforces guards. The requester must have enough available points. The owner cannot apply to their own transaction. Requester and courier must be different members.

This is the flexible state where the team formation happens.

## Slide 8 - Locked State

Locked state begins when the real-world handoff starts.

If the owner hands the book directly to the requester, the transaction can immediately complete. If there is a courier, the owner-to-courier handoff locks the transaction while the book is in transit.

When the transaction locks, pending join requests are deleted and accepted roles stop changing. This matters because after the book starts moving, we should not allow late applicants or role swaps to destabilize the delivery.

In the courier route, the transaction stays locked until the courier and requester confirm delivery.

No points move just because the transaction is locked. Points only move after the required confirmations are complete.

## Slide 9 - Archived State

Archived state is the completed state.

When both confirmation flags are true, the backend applies points exactly once, marks `points_applied` true, marks the transaction archived, locks it, and marks the book unavailable.

For a permanent exchange, the owner receives 10 points and the requester loses 10. For a loan, the owner receives 5 and the requester loses 5. If there is a courier, the courier receives 2 points.

After archive, the chatbox is no longer a negotiation space. It becomes a read-only record that explains what happened.

## Slide 10 - IRL Confirmation

The transaction state machine is connected to real-life meetup confirmation.

There are two delivery paths.

The first path is direct handoff: owner to requester. One side creates the confirmation request, and the other side approves while present. When approved, both owner and requester confirmation become true, points apply, and the transaction is archived.

The second path uses a courier. First, owner and courier confirm pickup. That sets `owner_confirmed` true and locks the transaction. Then courier and requester confirm delivery. That sets `requester_confirmed` true. Only then do points apply.

The backend validates that the two users in the confirmation match the expected participants. So a random member cannot confirm a handoff they were not part of.

## Slide 11 - 60-Second Timeout

The 60-second timeout is designed for real-life meetups.

The idea is simple: if I hand you the book now, you should approve now.

When a confirmation request is created, the expected counterparty has 60 seconds to approve it. If the request stays open too long, the backend clears the approver fields, so it can no longer be approved. The participants must create a fresh confirmation request.

This discourages delayed remote approval. It makes the confirmation closer to proof of physical presence.

## Slide 12 - Point Economy

The point economy is intentionally simple.

Every new member starts with 20 points. A permanent exchange moves 10 points from requester to owner. A loan moves 5. A courier earns 2 points only after successful delivery.

Points are never moved when someone only applies. At application time, the user is expressing intent, not completing an exchange.

Points are moved only after confirmation, and only once. This prevents accidental duplicate rewards or duplicate deductions.

## Slide 13 - Budget Anticipation

The second major mechanism is worst-case budget anticipation.

The system does not wait until completion to discover that a requester has overspent. It calculates available points before allowing the request.

The formula is:

Available points equals current points minus reserved exposure.

Reserved exposure includes accepted requester commitments and pending requester applications. In other words, the system asks: what if every active request succeeds?

For example, if a member has 20 points but already has 15 points reserved, only 5 points are available. A new loan request can still be allowed because it requires 5. A permanent exchange request is blocked because it requires 10.

This protects the economy before damage happens.

## Slide 14 - Archive Transparency

The archive is the third important mechanism.

It acts as a transparency layer between the owner, requester, and courier.

The owner can see who received or borrowed the book and why the owner earned points. The requester can see which transaction completed and why points were deducted. The courier can see which delivery they completed and why they earned the courier reward.

So the archive is not just old data. It is a shared receipt. It reduces disputes because the final roles, delivery path, and point outcome remain visible.

## Slide 15 - Closing

To conclude, what we built is a trust layer for book exchange.

The transaction state machine keeps system state aligned with real-world delivery. The confirmation mechanism makes physical handoff explicit. The budget guard prevents users from overspending their points. The archive makes the final result transparent.

In the demo, the path to watch is: apply for a role, owner accepts, participants confirm handoff, points apply, and the transaction becomes archived.

That is the main idea of our prototype: a small app, but with the core business logic needed for fair and traceable exchange.
