<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import {
		BookOpen,
		Check,
		ClipboardList,
		LogOut,
		MessageCircle,
		QrCode,
		Send,
		type Icon
	} from '@lucide/svelte';
	import {
		apiFetch,
		getStoredMember,
		getToken,
		mediaUrl,
		refreshMember,
		type Book,
		type ChatMessage,
		type Member,
		type Transaction
	} from '$lib/api';

	type DetailTab = 'info' | 'chat' | 'pending';
	type Role = 'requester' | 'courier';

	let member = $state<Member | null>(null);
	let book = $state<Book | null>(null);
	let transaction = $state<Transaction | null>(null);
	let messages = $state<ChatMessage[]>([]);
	let activeTab = $state<DetailTab>('info');
	let loading = $state(true);
	let busy = $state(false);
	let error = $state('');
	let applyRole = $state<Role>('requester');
	let applyMessage = $state('');
	let chatMessage = $state('');

	let viewChatbox = $derived(page.url.searchParams.get('view_chatbox') === 'true');
	let isOwner = $derived(!!member && !!book && member.id === book.owner_id);
	let acceptedRole = $derived<Role | 'owner' | null>(
		member && transaction
			? member.id === transaction.owner_id
				? 'owner'
				: member.id === transaction.requester_id
					? 'requester'
					: member.id === transaction.courier_id
						? 'courier'
						: null
			: null
	);
	let canViewChat = $derived(viewChatbox && acceptedRole !== null);
	let pendingMessages = $derived(
		messages.filter((message) => !message.accepted && message.applied_role !== 'owner')
	);
	let chatMessages = $derived(messages.filter((message) => message.accepted));
	let hasApplied = $derived(
		!!member &&
			!!transaction &&
			messages.some(
				(message) =>
					message.user_id === member?.id &&
					message.transaction_id === transaction?.id &&
					message.applied_role !== 'owner'
			)
	);

	onMount(async () => {
		if (!getToken()) {
			goto('/login');
			return;
		}

		member = getStoredMember();
		await loadPage();
	});

	async function loadPage() {
		loading = true;
		error = '';
		try {
			member = await refreshMember();
			const [bookRows, transactionRows] = await Promise.all([
				apiFetch<Book[]>('/api/books'),
				apiFetch<Transaction[]>('/api/transactions')
			]);
			book = bookRows.find((row) => row.id === Number(page.params.id)) ?? null;
			if (!book) throw new Error('Book not found');
			transaction =
				transactionRows.find((row) => row.book_id === book?.id && !row.points_applied) ?? null;
			if (!transaction && isOwner) {
				transaction = await apiFetch<Transaction>('/api/transactions', {
					method: 'POST',
					body: JSON.stringify({ book_id: book.id })
				});
			}
			activeTab = canViewChat ? 'chat' : 'info';
			await loadMessages();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to load this book';
		} finally {
			loading = false;
		}
	}

	async function loadMessages() {
		if (!member || !transaction) {
			messages = [];
			return;
		}
		try {
			messages = await apiFetch<ChatMessage[]>(
				`/api/transactions/${transaction.id}/messages?member_id=${member.id}`
			);
		} catch {
			messages = [];
		}
	}

	async function ensureTransaction() {
		if (transaction || !book) return transaction;
		transaction = await apiFetch<Transaction>('/api/transactions', {
			method: 'POST',
			body: JSON.stringify({ book_id: book.id })
		});
		return transaction;
	}

	async function applyToChatbox() {
		if (!member || !book) return;
		busy = true;
		error = '';
		try {
			const currentTransaction = await ensureTransaction();
			if (!currentTransaction) throw new Error('Unable to open chatbox');
			await apiFetch<ChatMessage>(`/api/transactions/${currentTransaction.id}/apply`, {
				method: 'POST',
				body: JSON.stringify({
					user_id: member.id,
					applied_role: applyRole,
					message: applyMessage || `I would like to join as ${applyRole}.`
				})
			});
			applyMessage = '';
			await loadMessages();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to send application';
		} finally {
			busy = false;
		}
	}

	async function sendChatMessage() {
		if (!member || !transaction || !chatMessage.trim()) return;
		busy = true;
		error = '';
		try {
			await apiFetch<ChatMessage>(`/api/transactions/${transaction.id}/messages`, {
				method: 'POST',
				body: JSON.stringify({ user_id: member.id, message: chatMessage.trim() })
			});
			chatMessage = '';
			await loadMessages();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to send message';
		} finally {
			busy = false;
		}
	}

	async function decideApplicant(message: ChatMessage, accept: boolean) {
		if (!member || !transaction) return;
		busy = true;
		error = '';
		try {
			await apiFetch<Transaction>(
				`/api/transactions/${transaction.id}/${accept ? 'accept' : 'kick'}`,
				{
					method: 'POST',
					body: JSON.stringify({
						owner_id: member.id,
						user_id: message.user_id,
						applied_role: message.applied_role
					})
				}
			);
			await loadPage();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to update participant';
		} finally {
			busy = false;
		}
	}

	async function kickAccepted(userId: number | null | undefined, role: Role) {
		if (!member || !transaction || !userId) return;
		busy = true;
		error = '';
		try {
			transaction = await apiFetch<Transaction>(`/api/transactions/${transaction.id}/kick`, {
				method: 'POST',
				body: JSON.stringify({
					owner_id: member.id,
					user_id: userId,
					applied_role: role
				})
			});
			await loadMessages();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to remove participant';
		} finally {
			busy = false;
		}
	}

	async function leaveChatbox() {
		if (!member || !transaction) return;
		busy = true;
		error = '';
		try {
			transaction = await apiFetch<Transaction>(`/api/transactions/${transaction.id}/leave`, {
				method: 'POST',
				body: JSON.stringify({ user_id: member.id })
			});
			await loadMessages();
			activeTab = 'info';
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to leave chatbox';
		} finally {
			busy = false;
		}
	}

	async function confirmMeeting(otherUserId: number | null) {
		if (!member || !transaction || !otherUserId) return;
		busy = true;
		error = '';
		try {
			transaction = await apiFetch<Transaction>('/api/transactions/confirm-meeting', {
				method: 'POST',
				body: JSON.stringify({
					transaction_id: transaction.id,
					user_1_id: member.id,
					user_2_id: otherUserId
				})
			});
			if (transaction.points_applied) {
				goto('/books');
				return;
			}
			await loadMessages();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to confirm meeting';
		} finally {
			busy = false;
		}
	}

	function confirmWith(otherUserId: number | null | undefined) {
		confirmMeeting(otherUserId ?? null);
	}

	function tabIcon(tab: DetailTab): typeof Icon {
		if (tab === 'chat') return MessageCircle;
		if (tab === 'pending') return ClipboardList;
		return BookOpen;
	}
</script>

<main class="detail-page">
	<section class="chatbox-shell">
		<div class="detail-topbar">
			<button class="icon-button" type="button" aria-label="Back to books" onclick={() => goto('/books')}>
				&lt;
			</button>
			<div>
				<p class="eyebrow">Book Exchange Club</p>
				<h1>{book?.title ?? 'Book detail'}</h1>
			</div>
		</div>

		{#if loading}
			<p class="empty-state">Loading book...</p>
		{:else if error && !book}
			<p class="empty-state">{error}</p>
		{:else if book}
			<div class="detail-tabs" aria-label="Book detail modes">
				{#each ['info', 'chat', 'pending'] as tab}
					{@const typedTab = tab as DetailTab}
					{@const TabIcon = tabIcon(typedTab)}
					{#if typedTab === 'info' || (typedTab === 'chat' && canViewChat) || (typedTab === 'pending' && isOwner)}
						<button
							class:active={activeTab === typedTab}
							type="button"
							onclick={() => (activeTab = typedTab)}
						>
							<TabIcon size={18} />
							{typedTab === 'info' ? 'Book info' : typedTab === 'chat' ? 'Chatbox' : 'Pending'}
						</button>
					{/if}
				{/each}
			</div>

			<div class="chatbox-layout">
				<section class="main-panel">
					{#if activeTab === 'info'}
						<div class="book-info-view">
							{#if book.picture_path}
								<img class="detail-picture" src={mediaUrl(book.picture_path)} alt={book.title} />
							{/if}
							<div>
								<p class="eyebrow">{book.genre}</p>
								<h2>{book.title}</h2>
								<p class="muted">{book.author}</p>
								<div class="meta-list">
									<span>{book.publication_year}</span>
									<span>{book.condition}</span>
									<span>{book.exchange_mode}</span>
									<span>Owner: {book.owner_name}</span>
								</div>
							</div>

							{#if !isOwner && !canViewChat && book.available}
								<form
									class="application-form"
									onsubmit={(event) => {
										event.preventDefault();
										applyToChatbox();
									}}
								>
									<div class="mode-toggle">
										<button
											class:active={applyRole === 'requester'}
											type="button"
											onclick={() => (applyRole = 'requester')}
										>
											Requester
										</button>
										<button
											class:active={applyRole === 'courier'}
											type="button"
											onclick={() => (applyRole = 'courier')}
										>
											Courier
										</button>
									</div>
									<label>
										Introduction note
										<input
											bind:value={applyMessage}
											placeholder="Share pickup timing, location, or why you want this book"
										/>
									</label>
									<button class="primary-action" disabled={busy || hasApplied} type="submit">
										{hasApplied ? 'Application sent' : busy ? 'Sending...' : 'Apply'}
									</button>
								</form>
							{:else if !isOwner && !book.available}
								<p class="empty-state">This book is no longer available.</p>
							{/if}
						</div>
					{:else if activeTab === 'chat'}
						<div class="message-list">
							{#each chatMessages as message}
								<article class:mine={message.user_id === member?.id} class="message-bubble">
									<strong>{message.user_name} <span>{message.applied_role}</span></strong>
									<p>{message.message}</p>
								</article>
							{:else}
								<p class="empty-state">No chat messages yet.</p>
							{/each}
						</div>
						<form
							class="chat-form"
							onsubmit={(event) => {
								event.preventDefault();
								sendChatMessage();
							}}
						>
							<input bind:value={chatMessage} placeholder="Send a message" />
							<button class="primary-action icon-label" disabled={busy} type="submit">
								<Send size={18} />
								Send
							</button>
						</form>
					{:else}
						<div class="pending-list">
							{#each pendingMessages as message}
								<article class="pending-card">
									<div>
										<p class="eyebrow">{message.applied_role}</p>
										<h2>{message.user_name}</h2>
										<p class="muted">{message.message}</p>
									</div>
									<div class="pending-actions">
										<button
											class="primary-action icon-label"
											disabled={busy || transaction?.locked}
											type="button"
											onclick={() => decideApplicant(message, true)}
										>
											<Check size={18} />
											Accept
										</button>
									</div>
								</article>
							{:else}
								<p class="empty-state">No pending applications.</p>
							{/each}
						</div>
					{/if}
				</section>

				<aside class="member-panel">
					<p class="eyebrow">Your info</p>
					<div class="qr-box">
						<QrCode size={48} />
						<strong>{member?.name}</strong>
						<span>ID {member?.id}</span>
					</div>

					{#if transaction}
						<div class="handoff-status">
							<p><strong>Requester:</strong> {transaction.requester_name || 'Open'}</p>
							<p><strong>Courier:</strong> {transaction.courier_name || 'None'}</p>
							<p><strong>Status:</strong> {transaction.locked ? 'Locked' : 'Open'}</p>
						</div>

						{#if acceptedRole === 'owner'}
							{#if transaction.requester_id}
								<button
									class="leave-button"
									disabled={busy || transaction.locked}
									type="button"
									onclick={() => kickAccepted(transaction?.requester_id, 'requester')}
								>
									Remove requester
								</button>
							{/if}
							{#if transaction.courier_id}
								<button
									class="leave-button"
									disabled={busy || transaction.locked}
									type="button"
									onclick={() => kickAccepted(transaction?.courier_id, 'courier')}
								>
									Remove courier
								</button>
							{/if}
							{#if transaction.courier_id}
								<button
									class="ghost-button"
									disabled={busy || transaction.owner_confirmed}
									type="button"
									onclick={() => confirmWith(transaction?.courier_id)}
								>
									Confirm courier handoff
								</button>
							{:else if transaction.requester_id}
								<button
									class="ghost-button"
									disabled={busy || transaction.points_applied}
									type="button"
									onclick={() => confirmWith(transaction?.requester_id)}
								>
									Confirm direct handoff
								</button>
							{/if}
						{:else if acceptedRole === 'courier'}
							{#if !transaction.owner_confirmed}
								<button
									class="ghost-button"
									disabled={busy}
									type="button"
									onclick={() => confirmWith(transaction?.owner_id)}
								>
									Confirm owner pickup
								</button>
							{:else}
								<button
									class="ghost-button"
									disabled={busy || transaction.requester_confirmed || !transaction.requester_id}
									type="button"
									onclick={() => confirmWith(transaction?.requester_id)}
								>
									Confirm requester delivery
								</button>
							{/if}
						{:else if acceptedRole === 'requester' && !transaction.courier_id}
							<button
								class="ghost-button"
								disabled={busy || transaction.points_applied}
								type="button"
								onclick={() => confirmWith(transaction?.owner_id)}
							>
								Confirm direct handoff
							</button>
						{/if}

						{#if acceptedRole && acceptedRole !== 'owner'}
							<button
								class="leave-button icon-label"
								disabled={busy || transaction.locked}
								type="button"
								onclick={leaveChatbox}
							>
								<LogOut size={18} />
								Leave
							</button>
						{/if}
					{/if}

					{#if error}
						<p class="form-error">{error}</p>
					{/if}
				</aside>
			</div>
		{/if}
	</section>
</main>
