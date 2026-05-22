<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import {
		apiFetch,
		clearSession,
		getStoredMember,
		getToken,
		mediaUrl,
		refreshMember,
		type Book,
		type Member,
		type Transaction
	} from '$lib/api';

	let member = $state<Member | null>(null);
	let books = $state<Book[]>([]);
	let transactions = $state<Transaction[]>([]);
	let loading = $state(true);
	let error = $state('');

	let myBooks = $derived(member ? books.filter((book) => book.owner_id === member?.id) : []);
	let acceptedTransactions = $derived(
		member
			? transactions.filter(
					(transaction) =>
						transaction.requester_id === member?.id || transaction.courier_id === member?.id
				)
			: []
	);
	let acceptedBookIds = $derived(new Set(acceptedTransactions.map((transaction) => transaction.book_id)));
	let acceptedBooks = $derived(books.filter((book) => acceptedBookIds.has(book.id)));
	let unavailableBookIds = $derived(
		new Set([
			...transactions
				.filter((transaction) => transaction.requester_id !== null || transaction.courier_id !== null)
				.map((transaction) => transaction.book_id),
			...myBooks.map((book) => book.id)
		])
	);
	let availableBooks = $derived(
		books.filter((book) => book.available && !unavailableBookIds.has(book.id))
	);

	onMount(async () => {
		if (!getToken()) {
			goto('/login');
			return;
		}
		member = getStoredMember();
		try {
			member = await refreshMember();
			const [bookRows, transactionRows] = await Promise.all([
				apiFetch<Book[]>('/api/books'),
				apiFetch<Transaction[]>('/api/transactions')
			]);
			books = bookRows;
			transactions = transactionRows;
		} catch (err) {
			clearSession();
			goto('/login');
		} finally {
			loading = false;
		}
	});

	function openBook(book: Book, viewChatbox: boolean) {
		goto(`/books/${book.id}?view_chatbox=${viewChatbox ? 'true' : 'false'}`);
	}

	function editBook(event: MouseEvent, book: Book) {
		event.stopPropagation();
		goto(`/books/new?mode=edit&book_id=${book.id}`);
	}

	function logout() {
		clearSession();
		goto('/login');
	}
</script>

<main class="app-shell">
	<header class="topbar">
		<div>
			<p class="eyebrow">Book Exchange Club</p>
			<h1>Your exchange shelf</h1>
		</div>
		<div class="account-block">
			{#if member}
				<span>{member.name}</span>
				<strong>{member.points} pts</strong>
			{/if}
			<button class="ghost-button" type="button" onclick={logout}>Log out</button>
		</div>
	</header>

	{#if loading}
		<section class="empty-state">Loading books...</section>
	{:else if error}
		<section class="empty-state">{error}</section>
	{:else}
		<section class="shelf-section">
			<div class="section-heading">
				<h2>My books</h2>
				<p>{myBooks.length} listed</p>
			</div>
			<div class="book-row">
				{#each myBooks as book}
					<div class="book-card owned">
						<button class="card-hitbox" type="button" onclick={() => openBook(book, true)}>
							{#if book.picture_path}
								<img class="book-thumb" src={mediaUrl(book.picture_path)} alt={book.title} />
							{/if}
							<span class="book-spine">{book.genre}</span>
							<strong>{book.title}</strong>
							<small>{book.author}</small>
							<span class="pill">{book.exchange_mode}</span>
						</button>
						<button class="edit-button" type="button" onclick={(event) => editBook(event, book)}>
							Edit
						</button>
					</div>
				{/each}
				<button class="book-card add-card" type="button" onclick={() => goto('/books/new?mode=new')}>
					<span>+</span>
					<strong>New book</strong>
				</button>
			</div>
		</section>

		<section class="shelf-section">
			<div class="section-heading">
				<h2>Accepted</h2>
				<p>{acceptedBooks.length} active</p>
			</div>
			<div class="book-row">
				{#each acceptedBooks as book}
					<button class="book-card accepted" type="button" onclick={() => openBook(book, true)}>
						{#if book.picture_path}
							<img class="book-thumb" src={mediaUrl(book.picture_path)} alt={book.title} />
						{/if}
						<span class="book-spine">{book.owner_name}</span>
						<strong>{book.title}</strong>
						<small>{book.author}</small>
						<span class="pill">Chatbox open</span>
					</button>
				{:else}
					<div class="empty-card">No accepted exchanges yet.</div>
				{/each}
			</div>
		</section>

		<section class="shelf-section">
			<div class="section-heading">
				<h2>Available</h2>
				<p>{availableBooks.length} open</p>
			</div>
			<div class="book-row">
				{#each availableBooks as book}
					<button class="book-card available" type="button" onclick={() => openBook(book, false)}>
						{#if book.picture_path}
							<img class="book-thumb" src={mediaUrl(book.picture_path)} alt={book.title} />
						{/if}
						<span class="book-spine">{book.condition}</span>
						<strong>{book.title}</strong>
						<small>{book.author}</small>
						<span class="pill">By {book.owner_name}</span>
					</button>
				{:else}
					<div class="empty-card">No available books right now.</div>
				{/each}
			</div>
		</section>
	{/if}
</main>
