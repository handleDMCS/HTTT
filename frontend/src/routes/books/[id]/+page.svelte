<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import {
		ArrowLeft,
		BookOpen,
		Check,
		ClipboardList,
		Crown,
		Handshake,
		LogOut,
		MessageCircle,
		QrCode,
		Send,
		Truck,
		User,
		UserMinus,
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
		type ApplicationStats,
		type Member,
		type Transaction
	} from '$lib/api';

	type DetailTab = 'info' | 'chat' | 'pending';
	type Role = 'requester' | 'courier';
	type RoleName = 'owner' | Role;
	const REALTIME_REFRESH_MS = 1800;

	let member = $state<Member | null>(null);
	let book = $state<Book | null>(null);
	let transaction = $state<Transaction | null>(null);
	let messages = $state<ChatMessage[]>([]);
	let applicationStats = $state<ApplicationStats>({
		requester: { applying: 0, accepted: false, accepted_name: '' },
		courier: { applying: 0, accepted: false, accepted_name: '' }
	});
	let activeTab = $state<DetailTab>('info');
	let loading = $state(true);
	let busy = $state(false);
	let error = $state('');
	let applyRole = $state<Role>('requester');
	let applyMessage = $state('');
	let chatMessage = $state('');
	let realtimeTimer: ReturnType<typeof setInterval> | null = null;
	let realtimeRefreshInFlight = false;

	let viewChatbox = $derived(page.url.searchParams.get('view_chatbox') === 'true');
	let routeTransactionId = $derived(Number(page.url.searchParams.get('transaction_id')) || null);
	let isOwner = $derived(!!member && !!book && member.id === book.owner_id);
	let readOnly = $derived(!!transaction?.archived);
	let acceptedRole = $derived<RoleName | null>(
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
	let canViewChat = $derived((viewChatbox || readOnly) && acceptedRole !== null);
	let chatboxLocked = $derived(!!transaction?.locked || !!transaction?.points_applied);
	let pendingMessages = $derived(
		messages.filter((message) => !message.accepted && message.applied_role !== 'owner')
	);
	let selectedRoleStats = $derived(applicationStats[applyRole]);
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

	onMount(() => {
		if (!getToken()) {
			goto('/login');
			return undefined;
		}

		member = getStoredMember();
		loadPage().then(startRealtimeRefresh);

		return () => {
			if (realtimeTimer) clearInterval(realtimeTimer);
		};
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
			transaction = routeTransactionId
				? transactionRows.find((row) => row.id === routeTransactionId) ?? null
				: transactionRows.find((row) => row.book_id === book?.id && !row.archived) ?? null;
			if (!transaction && isOwner) {
				transaction = await apiFetch<Transaction>('/api/transactions', {
					method: 'POST',
					body: JSON.stringify({ book_id: book.id })
				});
			}
			activeTab = canViewChat ? 'chat' : 'info';
			await Promise.all([loadMessages(), loadApplicationStats()]);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to load this book';
		} finally {
			loading = false;
		}
	}

	function startRealtimeRefresh() {
		if (realtimeTimer) clearInterval(realtimeTimer);
		realtimeTimer = setInterval(refreshRealtimeState, REALTIME_REFRESH_MS);
	}

	async function refreshRealtimeState(force = false) {
		if (!member || !book || realtimeRefreshInFlight || (busy && !force)) return;
		realtimeRefreshInFlight = true;
		try {
			const [latestMember, transactionRows] = await Promise.all([
				refreshMember(),
				apiFetch<Transaction[]>('/api/transactions')
			]);
			member = latestMember;
			const latestTransaction = routeTransactionId
				? transactionRows.find((row) => row.id === routeTransactionId) ?? null
				: transactionRows.find((row) => row.book_id === book?.id && !row.archived) ?? null;
			const completedTransaction = transactionRows.find(
				(row) => !routeTransactionId && row.book_id === book?.id && row.archived
			);

			if (completedTransaction) {
				goto('/books');
				return;
			}

			transaction = latestTransaction;
			if (!transaction) {
				messages = [];
				resetApplicationStats();
				return;
			}

			await Promise.all([loadMessages(), loadApplicationStats()]);
		} catch {
			// Keep the current screen stable during brief backend/network gaps.
		} finally {
			realtimeRefreshInFlight = false;
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

	async function loadApplicationStats() {
		if (!transaction) {
			resetApplicationStats();
			return;
		}
		try {
			applicationStats = await apiFetch<ApplicationStats>(
				`/api/transactions/${transaction.id}/application-stats`
			);
		} catch {
			resetApplicationStats();
		}
	}

	function resetApplicationStats() {
		applicationStats = {
			requester: { applying: 0, accepted: false, accepted_name: '' },
			courier: { applying: 0, accepted: false, accepted_name: '' }
		};
	}

	async function ensureTransaction() {
		if (readOnly) return null;
		if (transaction || !book) return transaction;
		transaction = await apiFetch<Transaction>('/api/transactions', {
			method: 'POST',
			body: JSON.stringify({ book_id: book.id })
		});
		return transaction;
	}

	async function applyToChatbox() {
		if (!member || !book || readOnly) return;
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
			await refreshRealtimeState(true);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to send application';
		} finally {
			busy = false;
		}
	}

	async function sendChatMessage() {
		if (!member || !transaction || !chatMessage.trim() || readOnly) return;
		busy = true;
		error = '';
		try {
			await apiFetch<ChatMessage>(`/api/transactions/${transaction.id}/messages`, {
				method: 'POST',
				body: JSON.stringify({ user_id: member.id, message: chatMessage.trim() })
			});
			chatMessage = '';
			await refreshRealtimeState(true);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to send message';
		} finally {
			busy = false;
		}
	}

	async function decideApplicant(message: ChatMessage, accept: boolean) {
		if (!member || !transaction || readOnly) return;
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
			await refreshRealtimeState(true);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to update participant';
		} finally {
			busy = false;
		}
	}

	async function kickAccepted(userId: number | null | undefined, role: Role) {
		if (!member || !transaction || !userId || readOnly) return;
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
			await refreshRealtimeState(true);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to remove participant';
		} finally {
			busy = false;
		}
	}

	async function leaveChatbox() {
		if (!member || !transaction || readOnly) return;
		busy = true;
		error = '';
		try {
			transaction = await apiFetch<Transaction>(`/api/transactions/${transaction.id}/leave`, {
				method: 'POST',
				body: JSON.stringify({ user_id: member.id })
			});
			await refreshRealtimeState(true);
			activeTab = 'info';
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to leave chatbox';
		} finally {
			busy = false;
		}
	}

	async function confirmMeeting(otherUserId: number | null) {
		if (!member || !transaction || !otherUserId || readOnly) return;
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
			await refreshRealtimeState(true);
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

	function roleIcon(role: RoleName): typeof Icon {
		if (role === 'owner') return Crown;
		if (role === 'courier') return Truck;
		return User;
	}

	function roleLabel(role: RoleName) {
		if (role === 'owner') return 'Owner';
		if (role === 'courier') return 'Courier';
		return 'Requester';
	}
</script>

<main class="detail-page">
	<section class="chatbox-shell">
		<div class="detail-topbar">
			<button class="icon-button" type="button" aria-label="Back to books" onclick={() => goto('/books')}>
				<ArrowLeft size={21} />
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
					{#if typedTab === 'info' || (typedTab === 'chat' && canViewChat) || (typedTab === 'pending' && (isOwner || readOnly))}
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
								{#if book.description}
									<p class="book-description">{book.description}</p>
								{/if}
							</div>

							{#if !readOnly && !isOwner && !canViewChat && book.available && !chatboxLocked}
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
											class="icon-label"
											type="button"
											onclick={() => (applyRole = 'requester')}
										>
											<User size={17} />
											Requester
										</button>
										<button
											class:active={applyRole === 'courier'}
											class="icon-label"
											type="button"
											onclick={() => (applyRole = 'courier')}
										>
											<Truck size={17} />
											Courier
										</button>
									</div>
									<div class="role-stats" aria-live="polite">
										<div>
											<span>Applying</span>
											<strong>{selectedRoleStats.applying}</strong>
										</div>
										<div>
											<span>Status</span>
											<strong
												>{selectedRoleStats.accepted
													? `Accepted: ${selectedRoleStats.accepted_name}`
													: 'Open'}</strong
											>
										</div>
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
							{:else if !isOwner && !canViewChat && chatboxLocked}
								<p class="empty-state">This chatbox is locked for handoff.</p>
							{:else if !isOwner && !book.available}
								<p class="empty-state">This book is no longer available.</p>
							{/if}
						</div>
					{:else if activeTab === 'chat'}
						<div class="message-list">
							{#each chatMessages as message}
								{@const MessageRoleIcon = roleIcon(message.applied_role)}
								<article class:mine={message.user_id === member?.id} class="message-bubble">
									<strong>
										{message.user_name}
										<span class="role-label">
											<MessageRoleIcon size={15} />
											{roleLabel(message.applied_role)}
										</span>
									</strong>
									<p>{message.message}</p>
								</article>
							{:else}
								<p class="empty-state">No chat messages yet.</p>
							{/each}
						</div>
						{#if !readOnly}
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
						{/if}
					{:else}
						<div class="pending-list">
							{#each pendingMessages as message}
								{@const PendingRoleIcon = roleIcon(message.applied_role)}
								<article class="pending-card">
									<div>
										<p class="eyebrow role-label">
											<PendingRoleIcon size={15} />
											{roleLabel(message.applied_role)}
										</p>
										<h2>{message.user_name}</h2>
										<p class="muted">{message.message}</p>
									</div>
									<div class="pending-actions">
										<button
											class="primary-action icon-label"
											disabled={busy || transaction?.locked || readOnly}
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
						<span>{member?.points ?? 0} pts</span>
					</div>

					{#if transaction}
						<div class="handoff-status">
							<p>
								<strong class="role-label"><User size={15} /> Requester:</strong>
								{transaction.requester_name || 'Open'}
							</p>
							<p>
								<strong class="role-label"><Truck size={15} /> Courier:</strong>
								{transaction.courier_name || 'None'}
							</p>
							<p><strong>Status:</strong> {transaction.archived ? 'Archived' : transaction.locked ? 'Locked' : 'Open'}</p>
						</div>

						{#if readOnly}
							<p class="empty-state">Archived read-only room.</p>
						{:else if acceptedRole === 'owner'}
							{#if transaction.requester_id}
								<button
									class="leave-button icon-label"
									disabled={busy || transaction.locked}
									type="button"
									onclick={() => kickAccepted(transaction?.requester_id, 'requester')}
								>
									<UserMinus size={18} />
									Remove requester
								</button>
							{/if}
							{#if transaction.courier_id}
								<button
									class="leave-button icon-label"
									disabled={busy || transaction.locked}
									type="button"
									onclick={() => kickAccepted(transaction?.courier_id, 'courier')}
								>
									<UserMinus size={18} />
									Remove courier
								</button>
							{/if}
							{#if transaction.courier_id}
								<button
									class="ghost-button icon-label"
									disabled={busy || transaction.owner_confirmed}
									type="button"
									onclick={() => confirmWith(transaction?.courier_id)}
								>
									<Handshake size={18} />
									Confirm courier handoff
								</button>
							{:else if transaction.requester_id}
								<button
									class="ghost-button icon-label"
									disabled={busy || transaction.points_applied}
									type="button"
									onclick={() => confirmWith(transaction?.requester_id)}
								>
									<Handshake size={18} />
									Confirm direct handoff
								</button>
							{/if}
						{:else if acceptedRole === 'courier'}
							{#if !transaction.owner_confirmed}
								<button
									class="ghost-button icon-label"
									disabled={busy}
									type="button"
									onclick={() => confirmWith(transaction?.owner_id)}
								>
									<Handshake size={18} />
									Confirm owner pickup
								</button>
							{:else}
								<button
									class="ghost-button icon-label"
									disabled={busy || transaction.requester_confirmed || !transaction.requester_id}
									type="button"
									onclick={() => confirmWith(transaction?.requester_id)}
								>
									<Handshake size={18} />
									Confirm requester delivery
								</button>
							{/if}
						{:else if acceptedRole === 'requester' && !transaction.courier_id}
							<button
								class="ghost-button icon-label"
								disabled={busy || transaction.points_applied}
								type="button"
								onclick={() => confirmWith(transaction?.owner_id)}
							>
								<Handshake size={18} />
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
