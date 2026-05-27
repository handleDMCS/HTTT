<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { Bell, LogOut, Pencil, Plus, User, BookOpenTextIcon } from '@lucide/svelte';
	import ListingSection from '$lib/components/ListingSection.svelte';
	import {
		apiFetch,
		clearSession,
		formatTimestamp,
		getStoredMember,
		getToken,
		mediaUrl,
		refreshMember,
		type ActivityMessage,
		type Book,
		type Member,
		type Transaction,
		type UnreadCounts
	} from '$lib/api';

	const REALTIME_REFRESH_MS = 1800;
	type RouteTab = 'book info' | 'chatbox' | 'notification';

	let member = $state<Member | null>(null);
	let books = $state<Book[]>([]);
	let transactions = $state<Transaction[]>([]);
	let activityMessages = $state<ActivityMessage[]>([]);
	let applicationMessages = $state<ActivityMessage[]>([]);
	let unreadCounts = $state<UnreadCounts>({ dropdown: 0 });
	let messageDropdownOpen = $state(false);
	let loading = $state(true);
	let error = $state('');
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
						transaction.locked ||
						transaction.points_applied ||
						(transaction.requester_id !== null && transaction.courier_id !== null)
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
	let dropdownUnread = $derived(unreadCounts.dropdown ?? 0);

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
			await Promise.all([loadMessageActivity(), loadApplications()]);
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
			await Promise.all([loadMessageActivity(), loadApplications()]);
			if (messageDropdownOpen) await markDropdownViewed();
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

	async function loadMessageActivity() {
		if (!member) return;
		try {
			const [messageRows, unread] = await Promise.all([
				apiFetch<ActivityMessage[]>(`/api/members/${member.id}/messages`),
				apiFetch<UnreadCounts>(`/api/activity/unread?member_id=${member.id}`)
			]);
			activityMessages = messageRows;
			unreadCounts = unread;
		} catch {
			// Keep the current dropdown stable during brief backend/network gaps.
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

	async function markDropdownViewed() {
		if (!member) return;
		await apiFetch('/api/activity', {
			method: 'POST',
			body: JSON.stringify({
				member_id: member.id,
				transaction_id: null,
				tab: 'dropdown'
			})
		});
		unreadCounts = await apiFetch<UnreadCounts>(`/api/activity/unread?member_id=${member.id}`);
	}

	async function toggleMessageDropdown() {
		messageDropdownOpen = !messageDropdownOpen;
		if (messageDropdownOpen) {
			await markDropdownViewed();
			await loadMessageActivity();
		}
	}

	function openActivityMessage(message: ActivityMessage) {
		goto(
			bookDetailUrl(message.book_id, message.notification_type ? 'notification' : 'chatbox', {
				transactionId: message.transaction_id,
				timestamp: message.timestamp
			})
		);
	}

	function logout() {
		clearSession();
		goto('/login');
	}
</script>

{#snippet myBookCard(book: Book)}
	<div class="book-card owned">
		<button class="card-hitbox" type="button" onclick={() => openBook(book, 'chatbox')}>
			{#if book.picture_path}
				<img class="book-thumb" src={mediaUrl(book.picture_path)} alt={book.title} />
			{/if}
			<span class="book-spine">{book.genre}</span>
			<strong>{book.title}</strong>
			<small>{book.author}</small>
			<span class="pill">{book.exchange_mode}</span>
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
		<span class="pill">Chatbox open</span>
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
		<span class="pill">Applying as {row.message.applied_role}</span>
	</button>
{/snippet}

{#snippet availableBookCard(book: Book)}
	<button class="book-card available" type="button" onclick={() => openBook(book, 'book info')}>
		{#if book.picture_path}
			<img class="book-thumb" src={mediaUrl(book.picture_path)} alt={book.title} />
		{/if}
		<span class="book-spine">{book.condition}</span>
		<strong>{book.title}</strong>
		<small>{book.author}</small>
		<span class="pill">By {book.owner_name}</span>
	</button>
{/snippet}

{#snippet archivedBookCard(row: { transaction: Transaction; book: Book })}
	<button
		class="book-card accepted"
		type="button"
		onclick={() => openArchivedBook(row.book, row.transaction)}
	>
		{#if row.book.picture_path}
			<img class="book-thumb" src={mediaUrl(row.book.picture_path)} alt={row.book.title} />
		{/if}
		<span class="book-spine">{row.transaction.courier_name || 'Direct handoff'}</span>
		<strong>{row.book.title}</strong>
		<small>{row.book.author}</small>
		<span class="pill">Archived</span>
	</button>
{/snippet}

{#snippet newBookAction()}
	<button class="book-card add-card" type="button" onclick={() => goto('/books/new?mode=new')}>
		<span><Plus size={28} strokeWidth={2.4} /></span>
		<strong>New book</strong>
	</button>
{/snippet}

<main class="app-shell">
	<header class="topbar">
		<div>
			<p class="eyebrow">Book Exchange Club</p>
			<h2>
				<BookOpenTextIcon class="inline" size={35}></BookOpenTextIcon> In knowledge we trust
			</h2>
		</div>
		<div class="account-block">
			{#if member}
				<p class="font-bold">{member.name}</p>
				<strong>{member.points} pts</strong>
				<div class="message-dropdown">
					<button
						class="ghost-button icon-label message-toggle"
						type="button"
						aria-expanded={messageDropdownOpen}
						onclick={toggleMessageDropdown}
					>
						<Bell size={17} />
						Messages
						{#if dropdownUnread > 0}
							<span class="unread-badge">{dropdownUnread}</span>
						{/if}
					</button>
					{#if messageDropdownOpen}
						<div class="message-dropdown-panel" aria-label="Recent messages">
							{#each activityMessages as message}
								<button class="message-dropdown-item" type="button" onclick={() => openActivityMessage(message)}>
									<span>
										<strong>{message.user_name}</strong>
										<small>{message.book_title}</small>
									</span>
									<p>{message.message}</p>
									<time datetime={message.timestamp}>{formatTimestamp(message.timestamp)}</time>
								</button>
							{:else}
								<p class="empty-state">No messages yet.</p>
							{/each}
						</div>
					{/if}
				</div>
				<button class="ghost-button icon-label" type="button" onclick={() => goto(`/profile/${member?.id}`)}>
					<User size={17} />
					Profile
				</button>
			{/if}
			<button class="ghost-button icon-label" type="button" onclick={logout}>
				<LogOut size={17} />
				Log out
			</button>
		</div>
	</header>

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
