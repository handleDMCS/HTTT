<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { Pencil, Plus, RotateCcw, X } from '@lucide/svelte';
	import ListingSection from '$lib/components/ListingSection.svelte';
	import ConfirmModal from '$lib/components/ConfirmModal.svelte';
	import {
		apiFetch,
		clearSession,
		getStoredMember,
		getToken,
		mediaUrl,
		refreshMember,
		type ActivityMessage,
		type Book,
		type Member,
		type Transaction
	} from '$lib/api';

	const REALTIME_REFRESH_MS = 1800;
	type RouteTab = 'book info' | 'chatbox' | 'notification';

	let member = $state<Member | null>(null);
	let books = $state<Book[]>([]);
	let transactions = $state<Transaction[]>([]);
	let applicationMessages = $state<ActivityMessage[]>([]);
	let loading = $state(true);
	let error = $state('');
	let renewingBookId = $state<number | null>(null);
	let renewTarget = $state<{ transaction: Transaction; book: Book } | null>(null);
	let deletingBookId = $state<number | null>(null);
	let deleteTarget = $state<Book | null>(null);
	let blockedDeleteTarget = $state<Book | null>(null);
	let realtimeTimer: ReturnType<typeof setInterval> | null = null;
	let realtimeRefreshInFlight = false;

	let archivedBookIds = $derived(
		new Set(transactions.filter((transaction) => transaction.archived).map((transaction) => transaction.book_id))
	);
	let myBooks = $derived(
		member ? books.filter((book) => book.owner_id === member?.id && !archivedBookIds.has(book.id)) : []
	);
	let acceptedTransactions = $derived(
		member
			? transactions.filter(
					(transaction) =>
						!transaction.archived &&
						(transaction.requester_id === member?.id || transaction.courier_id === member?.id)
				)
			: []
	);
	let archivedTransactions = $derived(
		member
			? transactions.filter(
					(transaction) =>
						transaction.archived &&
						(transaction.owner_id === member?.id ||
							transaction.requester_id === member?.id ||
							transaction.courier_id === member?.id)
				)
			: []
	);
	let acceptedBookIds = $derived(new Set(acceptedTransactions.map((transaction) => transaction.book_id)));
	let acceptedBooks = $derived(books.filter((book) => acceptedBookIds.has(book.id)));
	let applyingBookIds = $derived(new Set(applicationMessages.map((message) => message.book_id)));
	let applyingRows = $derived(
		applicationMessages
			.map((message) => ({
				message,
				book: books.find((book) => book.id === message.book_id)
			}))
			.filter((row): row is { message: ActivityMessage; book: Book } => !!row.book)
	);
	let archivedBookRows = $derived(
		archivedTransactions
			.map((transaction) => ({
				transaction,
				book: books.find((book) => book.id === transaction.book_id)
			}))
			.filter((row): row is { transaction: Transaction; book: Book } => !!row.book)
	);
	let unavailableBookIds = $derived(
		new Set([
			...transactions
				.filter(
					(transaction) =>
						transaction.archived ||
						transaction.locked
				)
				.map((transaction) => transaction.book_id),
			...acceptedBookIds,
			...applyingBookIds,
			...myBooks.map((book) => book.id)
		])
	);
	let availableBooks = $derived(
		books.filter((book) => book.available && !unavailableBookIds.has(book.id))
	);

	onMount(() => {
		if (!getToken()) {
			goto('/login');
			return undefined;
		}
		member = getStoredMember();
		loadShelves().then(startRealtimeRefresh);

		return () => {
			if (realtimeTimer) clearInterval(realtimeTimer);
		};
	});

	async function loadShelves() {
		try {
			member = await refreshMember();
			const [bookRows, transactionRows] = await Promise.all([
				apiFetch<Book[]>('/api/books'),
				apiFetch<Transaction[]>('/api/transactions')
			]);
			books = bookRows;
			transactions = transactionRows;
			await loadApplications();
		} catch (err) {
			clearSession();
			goto('/login');
		} finally {
			loading = false;
		}
	}

	function startRealtimeRefresh() {
		if (realtimeTimer) clearInterval(realtimeTimer);
		realtimeTimer = setInterval(refreshRealtimeShelves, REALTIME_REFRESH_MS);
	}

	async function refreshRealtimeShelves() {
		if (realtimeRefreshInFlight) return;
		realtimeRefreshInFlight = true;
		try {
			const [latestMember, bookRows, transactionRows] = await Promise.all([
				refreshMember(),
				apiFetch<Book[]>('/api/books'),
				apiFetch<Transaction[]>('/api/transactions')
			]);
			member = latestMember;
			books = bookRows;
			transactions = transactionRows;
			await loadApplications();
		} catch {
			// Keep the current shelves visible during brief backend/network gaps.
		} finally {
			realtimeRefreshInFlight = false;
		}
	}

	function bookDetailUrl(
		bookId: number,
		tab: RouteTab,
		options: { transactionId?: number | null; timestamp?: string } = {}
	) {
		const params = new URLSearchParams({ tab });
		if (options.transactionId) params.set('transaction_id', String(options.transactionId));
		if (options.timestamp) params.set('timestamp', options.timestamp);
		return `/books/${bookId}?${params.toString()}`;
	}

	function openBook(book: Book, tab: RouteTab) {
		goto(bookDetailUrl(book.id, tab));
	}

	function openArchivedBook(book: Book, transaction: Transaction) {
		goto(bookDetailUrl(book.id, 'chatbox', { transactionId: transaction.id }));
	}

	function editBook(event: MouseEvent, book: Book) {
		event.stopPropagation();
		goto(`/books/new?mode=edit&book_id=${book.id}`);
	}

	function bookHasParticipants(book: Book) {
		return transactions.some(
			(transaction) =>
				transaction.book_id === book.id &&
				(transaction.requester_id !== null || transaction.courier_id !== null)
		);
	}

	function requestDeleteBook(book: Book) {
		if (bookHasParticipants(book)) {
			blockedDeleteTarget = book;
			return;
		}
		deleteTarget = book;
	}

	function openDeleteBlockedChatbox() {
		if (!blockedDeleteTarget) return;
		const book = blockedDeleteTarget;
		blockedDeleteTarget = null;
		goto(bookDetailUrl(book.id, 'chatbox'));
	}

	async function confirmDeleteBook() {
		if (!member || !deleteTarget) return;
		const book = deleteTarget;
		deletingBookId = book.id;
		error = '';
		try {
			await apiFetch<{ deleted: boolean }>(`/api/books/${book.id}?owner_id=${member.id}`, {
				method: 'DELETE'
			});
			deleteTarget = null;
			await refreshRealtimeShelves();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to delete this book';
		} finally {
			deletingBookId = null;
		}
	}

	function canRenewArchivedLoan(row: { transaction: Transaction; book: Book }) {
		return (
			row.book.exchange_mode === 'loan' &&
			row.transaction.archived &&
			!!member &&
			member.id === row.transaction.owner_id &&
			member.id === row.book.owner_id
		);
	}

	function requestRenewLoanBook(row: { transaction: Transaction; book: Book }) {
		if (!canRenewArchivedLoan(row)) return;
		renewTarget = row;
	}

	async function confirmRenewLoanBook() {
		if (!renewTarget || !canRenewArchivedLoan(renewTarget)) return;
		const row = renewTarget;
		const book = row.book;
		const ownerId = row.transaction.owner_id;
		renewingBookId = book.id;
		error = '';
		try {
			await apiFetch<Book>(`/api/books/${book.id}/renew?owner_id=${ownerId}`, {
				method: 'POST'
			});
			await refreshRealtimeShelves();
			renewTarget = null;
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to renew this book';
		} finally {
			renewingBookId = null;
		}
	}

	async function loadApplications() {
		if (!member) return;
		try {
			applicationMessages = await apiFetch<ActivityMessage[]>(`/api/members/${member.id}/applications`);
		} catch {
			// Keep the current shelf stable during brief backend/network gaps.
		}
	}

	function exchangeModeLabel(mode: string) {
		if (mode === 'permanent') return 'Permanent';
		if (mode === 'loan') return 'Loan';
		return mode;
	}
</script>

{#snippet myBookCard(book: Book)}
	<div class="book-card owned">
		<button
			class="card-delete-button"
			type="button"
			aria-label={`Delete ${book.title}`}
			title={bookHasParticipants(book) ? 'Remove all chatbox participants before deleting' : 'Delete book'}
			disabled={deletingBookId === book.id}
			onclick={() => requestDeleteBook(book)}
		>
			<X size={17} />
		</button>
		<button class="card-hitbox" type="button" onclick={() => openBook(book, 'chatbox')}>
			{#if book.picture_path}
				<img class="book-thumb" src={mediaUrl(book.picture_path)} alt={book.title} />
			{/if}
			<span class="book-spine">{book.genre}</span>
			<strong>{book.title}</strong>
			<small>{book.author}</small>
			<span class="tag-row">
				<span class="pill">{exchangeModeLabel(book.exchange_mode)}</span>
			</span>
		</button>
		<button class="edit-button icon-label" type="button" onclick={(event) => editBook(event, book)}>
			<Pencil size={17} />
			Edit
		</button>
	</div>
{/snippet}

{#snippet acceptedBookCard(book: Book)}
	<button class="book-card accepted" type="button" onclick={() => openBook(book, 'chatbox')}>
		{#if book.picture_path}
			<img class="book-thumb" src={mediaUrl(book.picture_path)} alt={book.title} />
		{/if}
		<span class="book-spine">{book.owner_name}</span>
		<strong>{book.title}</strong>
		<small>{book.author}</small>
		<span class="tag-row">
			<span class="pill">{exchangeModeLabel(book.exchange_mode)}</span>
			<span class="pill">Chatbox open</span>
		</span>
	</button>
{/snippet}

{#snippet applyingBookCard(row: { message: ActivityMessage; book: Book })}
	<button
		class="book-card accepted"
		type="button"
		onclick={() => goto(bookDetailUrl(row.book.id, 'book info', { transactionId: row.message.transaction_id }))}
	>
		{#if row.book.picture_path}
			<img class="book-thumb" src={mediaUrl(row.book.picture_path)} alt={row.book.title} />
		{/if}
		<span class="book-spine">{row.book.owner_name}</span>
		<strong>{row.book.title}</strong>
		<small>{row.book.author}</small>
		<span class="tag-row">
			<span class="pill">{exchangeModeLabel(row.book.exchange_mode)}</span>
			<span class="pill">Applying as {row.message.applied_role}</span>
		</span>
	</button>
{/snippet}

{#snippet availableBookCard(book: Book)}
	<div class="book-card available">
		<button class="card-hitbox" type="button" onclick={() => openBook(book, 'book info')}>
			{#if book.picture_path}
				<img class="book-thumb" src={mediaUrl(book.picture_path)} alt={book.title} />
			{/if}
			<span class="book-spine">{book.condition}</span>
			<strong>{book.title}</strong>
			<small>{book.author}</small>
			<span class="tag-row">
				<span class="pill">{exchangeModeLabel(book.exchange_mode)}</span>
			</span>
		</button>
		<a class="book-owner-link" href={`/profile/${book.owner_id}`}>{book.owner_name}</a>
	</div>
{/snippet}

{#snippet archivedBookCard(row: { transaction: Transaction; book: Book })}
	<div class="book-card accepted">
		<button class="card-hitbox" type="button" onclick={() => openArchivedBook(row.book, row.transaction)}>
			{#if row.book.picture_path}
				<img class="book-thumb" src={mediaUrl(row.book.picture_path)} alt={row.book.title} />
			{/if}
			<span class="book-spine">{row.transaction.courier_name || 'Direct handoff'}</span>
			<strong>{row.book.title}</strong>
			<small>{row.book.author}</small>
			<span class="tag-row">
				<span class="pill">{exchangeModeLabel(row.book.exchange_mode)}</span>
				<span class="pill">Archived</span>
			</span>
		</button>
		{#if canRenewArchivedLoan(row)}
			<button
				class="renew-button icon-label"
				disabled={renewingBookId === row.book.id}
				type="button"
				onclick={() => requestRenewLoanBook(row)}
			>
				<RotateCcw size={17} />
				{renewingBookId === row.book.id ? 'Renewing...' : 'Renew'}
			</button>
		{/if}
	</div>
{/snippet}

{#snippet newBookAction()}
	<button class="book-card add-card" type="button" onclick={() => goto('/books/new?mode=new')}>
		<span><Plus size={28} strokeWidth={2.4} /></span>
		<strong>New book</strong>
	</button>
{/snippet}

<main class="app-shell">
	{#if loading}
		<section class="empty-state">Loading books...</section>
	{:else if error}
		<section class="empty-state">{error}</section>
	{:else}
		<ListingSection
			title="My books"
			items={myBooks}
			getBook={(book) => book}
			card={myBookCard}
			actions={newBookAction}
			emptyText="No books listed yet."
			countSuffix="listed"
		/>

		<ListingSection
			title="Accepted"
			items={acceptedBooks}
			getBook={(book) => book}
			card={acceptedBookCard}
			emptyText="No accepted exchanges yet."
			countSuffix="active"
		/>

		<ListingSection
			title="Applying"
			items={applyingRows}
			getBook={(row) => row.book}
			card={applyingBookCard}
			emptyText="No pending applications."
			countSuffix="pending"
		/>

		<ListingSection
			title="Available"
			items={availableBooks}
			getBook={(book) => book}
			card={availableBookCard}
			emptyText="No available books right now."
			countSuffix="open"
		/>

		<ListingSection
			title="Archive"
			items={archivedBookRows}
			getBook={(row) => row.book}
			card={archivedBookCard}
			emptyText="No archived exchanges yet."
			countSuffix="completed"
		/>
	{/if}
</main>

{#if renewTarget}
	<ConfirmModal
		title="Renew loan listing?"
		message={`Create a new independent loan listing for "${renewTarget.book.title}". The archived transaction, chatbox, and notifications will stay unchanged.`}
		confirmLabel="Renew"
		busy={renewingBookId === renewTarget.book.id}
		onCancel={() => {
			if (renewingBookId === null) renewTarget = null;
		}}
		onConfirm={confirmRenewLoanBook}
	/>
{/if}

{#if deleteTarget}
	<ConfirmModal
		title="Delete book listing?"
		message={`Delete "${deleteTarget.title}" and its empty chatbox data? This action cannot be undone.`}
		confirmLabel="Delete"
		tone="danger"
		busy={deletingBookId === deleteTarget.id}
		onCancel={() => {
			if (deletingBookId === null) deleteTarget = null;
		}}
		onConfirm={confirmDeleteBook}
	/>
{/if}

{#if blockedDeleteTarget}
	<ConfirmModal
		title="Cannot delete yet"
		message={`"${blockedDeleteTarget.title}" still has people in its chatbox. Remove the requester and courier before deleting this book.`}
		cancelLabel="Close"
		confirmLabel="Open chatbox"
		onCancel={() => (blockedDeleteTarget = null)}
		onConfirm={openDeleteBlockedChatbox}
	/>
{/if}
