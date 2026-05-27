<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import {
		ArrowLeft,
		Bell,
		BookOpen,
		Check,
		Crown,
		Handshake,
		LogOut,
		MessageCircle,
		Send,
		Truck,
		User,
		UserMinus,
		type Icon
	} from '@lucide/svelte';
	import {
		apiFetch,
		formatTimestamp,
		getStoredMember,
		getToken,
		mediaUrl,
		refreshMember,
		type Book,
		type ChatMessage,
		type ApplicationStats,
		type Member,
		type MemberProfile,
		type Transaction,
		type UnreadCounts
	} from '$lib/api';

	type DetailTab = 'info' | 'chat' | 'notification';
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
	let selectedInfoMember = $state<Member | null>(null);
	let infoLoading = $state(false);
	let unreadCounts = $state<UnreadCounts>({ dropdown: 0 });
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
	let notificationMessages = $derived(messages.filter((message) => message.notification_type !== null));
	let selectedRoleStats = $derived(applicationStats[applyRole]);
	let chatMessages = $derived(
		messages.filter((message) => message.accepted && message.notification_type === null)
	);
	let hasApplied = $derived(
		!!member &&
			!!transaction &&
			messages.some(
				(message) =>
					message.user_id === member?.id &&
					message.transaction_id === transaction?.id &&
					message.notification_type === 'join_request'
		)
	);
	let ownerInfoName = $derived(transaction?.owner_name || book?.owner_name || '');
	let requesterInfoId = $derived(transaction?.requester_id ?? null);
	let requesterInfoName = $derived(transaction?.requester_name || '');
	let courierInfoId = $derived(transaction?.courier_id ?? null);
	let courierInfoName = $derived(transaction?.courier_name || '');

	let chatboxUnread = $derived(unreadCounts.chatbox ?? 0);
	let notificationUnread = $derived(unreadCounts.notification ?? 0);

	$effect(() => {
		if (!member || !book || selectedInfoMember) return;
		if (canViewChat) {
			selectedInfoMember = member;
			return;
		}
		selectInfoMember(book.owner_id);
	});

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
			await Promise.all([loadMessages(), loadApplicationStats(), loadUnreadCounts()]);
			await markVisibleActiveTab();
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
			if (selectedInfoMember?.id === latestMember.id) selectedInfoMember = latestMember;
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
			if (shouldRedirectToChatbox(latestTransaction, latestMember)) return;
			if (!transaction) {
				messages = [];
				resetApplicationStats();
				return;
			}

			await Promise.all([loadMessages(), loadApplicationStats(), loadUnreadCounts()]);
			await markVisibleActiveTab();
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

	async function loadUnreadCounts() {
		if (!member || !transaction) {
			unreadCounts = { dropdown: 0 };
			return;
		}
		try {
			unreadCounts = await apiFetch<UnreadCounts>(
				`/api/activity/unread?member_id=${member.id}&transaction_id=${transaction.id}`
			);
		} catch {
			unreadCounts = { dropdown: 0 };
		}
	}

	async function markActivity(tab: 'chatbox' | 'notification') {
		if (!member || !transaction) return;
		await apiFetch('/api/activity', {
			method: 'POST',
			body: JSON.stringify({
				member_id: member.id,
				transaction_id: transaction.id,
				tab
			})
		});
		await loadUnreadCounts();
	}

	async function markVisibleActiveTab() {
		if (!canViewChat || activeTab === 'info') return;
		try {
			await markActivity(activeTab === 'chat' ? 'chatbox' : 'notification');
		} catch {
			// Unread badges should not interrupt chatbox use.
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

	async function approveNotification(message: ChatMessage) {
		if (!member || !transaction || readOnly) return;
		busy = true;
		error = '';
		try {
			transaction = await apiFetch<Transaction>(
				`/api/transactions/${transaction.id}/notifications/${message.message_id}/approve`,
				{
					method: 'POST',
					body: JSON.stringify({ user_id: member.id })
				}
			);
			if (transaction.points_applied) {
				goto('/books');
				return;
			}
			await refreshRealtimeState(true);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to approve notification';
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

	async function createConfirmNotification(notificationType: ChatMessage['notification_type']) {
		if (!member || !transaction || !notificationType || readOnly) return;
		busy = true;
		error = '';
		try {
			await apiFetch<ChatMessage>(`/api/transactions/${transaction.id}/notifications`, {
				method: 'POST',
				body: JSON.stringify({
					user_id: member.id,
					notification_type: notificationType
				})
			});
			await refreshRealtimeState(true);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to create confirmation request';
		} finally {
			busy = false;
		}
	}

	function tabIcon(tab: DetailTab): typeof Icon {
		if (tab === 'chat') return MessageCircle;
		if (tab === 'notification') return Bell;
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

	function notificationLabel(message: ChatMessage) {
		if (message.notification_type === 'join_request') return 'Join request';
		if (message.notification_type === 'kicked') return 'Removed';
		if (message.notification_type === 'leave') return 'Left';
		if (message.notification_type === 'join') return 'Joined';
		if (message.notification_type === 'confirm_direct_handoff') return 'Direct handoff';
		if (message.notification_type === 'confirm_handoff') return 'Owner-courier handoff';
		if (message.notification_type === 'confirm_delivered') return 'Delivered';
		return 'Notification';
	}

	function canApproveNotification(message: ChatMessage) {
		return (
			!!member &&
			!!acceptedRole &&
			!readOnly &&
			!message.accepted &&
			message.approver_id === member.id &&
			message.approver_role === acceptedRole
		);
	}

	function openProfile(userId: number | null | undefined) {
		if (userId) goto(`/profile/${userId}`);
	}

	function selectDetailTab(tab: DetailTab) {
		activeTab = tab;
		markVisibleActiveTab();
	}

	function shouldRedirectToChatbox(latestTransaction: Transaction | null, latestMember: Member) {
		if (!book || !latestTransaction || routeTransactionId || viewChatbox) return false;
		const approvedRole =
			latestMember.id === latestTransaction.requester_id || latestMember.id === latestTransaction.courier_id;
		if (!approvedRole || latestMember.id === latestTransaction.owner_id) return false;
		goto(`/books/${book.id}?view_chatbox=true`);
		return true;
	}

	async function selectInfoMember(userId: number | null | undefined) {
		if (!userId) return;
		if (member?.id === userId) {
			selectedInfoMember = member;
			return;
		}
		infoLoading = true;
		try {
			const profile = await apiFetch<MemberProfile>(`/api/members/${userId}/profile`);
			selectedInfoMember = profile.member;
		} catch {
			// Keep the previous badge visible if this quick profile lookup fails.
		} finally {
			infoLoading = false;
		}
	}
</script>

<main class="detail-page">
	<section class="chatbox-shell">
		<div class="detail-topbar">
			<div class="detail-title-block">
				<button class="icon-button" type="button" aria-label="Back to books" onclick={() => goto('/books')}>
					<ArrowLeft size={21} />
				</button>
				<div>
					<p class="eyebrow">Book Exchange Club</p>
					<h1>{book?.title ?? 'Book detail'}</h1>
				</div>
			</div>
			{#if book && !loading && !(error && !book)}
				<div class="detail-tabs" aria-label="Book detail modes">
					{#each ['info', 'chat', 'notification'] as tab}
						{@const typedTab = tab as DetailTab}
						{@const TabIcon = tabIcon(typedTab)}
						{#if typedTab === 'info' || (typedTab === 'chat' && canViewChat) || (typedTab === 'notification' && canViewChat)}
							<button
								class:active={activeTab === typedTab}
								type="button"
								onclick={() => selectDetailTab(typedTab)}
							>
								<TabIcon size={18} />
								<span>{typedTab === 'info' ? 'Book info' : typedTab === 'chat' ? 'Chatbox' : 'Notification'}</span>
								{#if typedTab === 'chat' && chatboxUnread > 0}
									<span class="unread-badge">{chatboxUnread}</span>
								{:else if typedTab === 'notification' && notificationUnread > 0}
									<span class="unread-badge">{notificationUnread}</span>
								{/if}
							</button>
						{/if}
					{/each}
				</div>
			{/if}
		</div>

		{#if loading}
			<p class="empty-state">Loading book...</p>
		{:else if error && !book}
			<p class="empty-state">{error}</p>
		{:else if book}
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
									<span>
										Owner -
										<button class="inline-link" type="button" onclick={() => openProfile(book?.owner_id)}>
											{book.owner_name}
										</button>
									</span>
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
										<button class="inline-link" type="button" onclick={() => openProfile(message.user_id)}>
											{message.user_name}
										</button>
										<span class="role-label">
											<MessageRoleIcon size={15} />
											{roleLabel(message.applied_role)}
										</span>
									</strong>
									<time class="message-time" datetime={message.timestamp}>
										{formatTimestamp(message.timestamp)}
									</time>
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
							{#each notificationMessages as message}
								{@const PendingRoleIcon = roleIcon(message.applied_role)}
								<article class="pending-card">
									<div>
										<p class="eyebrow role-label">
											<PendingRoleIcon size={15} />
											{notificationLabel(message)}
										</p>
										<h2>
											<button class="inline-link" type="button" onclick={() => openProfile(message.user_id)}>
												{message.user_name}
											</button>
										</h2>
										<p class="muted">{message.message}</p>
										<time class="message-time" datetime={message.timestamp}>
											{formatTimestamp(message.timestamp)}
										</time>
										{#if message.approver_role && !message.accepted}
											<p class="muted">Waiting for {roleLabel(message.approver_role)} approval.</p>
										{:else if message.approver_role && message.accepted}
											<p class="muted">Approved.</p>
										{/if}
									</div>
									{#if canApproveNotification(message)}
										<div class="pending-actions">
											<button
												class="primary-action icon-label"
												disabled={busy || readOnly}
												type="button"
												onclick={() => approveNotification(message)}
											>
												<Check size={18} />
												Approve
											</button>
										</div>
									{/if}
								</article>
							{:else}
								<p class="empty-state">No notifications yet.</p>
							{/each}
						</div>
					{/if}
				</section>

				<aside class="member-panel">
					<p class="eyebrow">Members</p>
					<div class="handoff-status">
						<p>
							<strong class="role-label"><Crown size={15} /> Owner</strong>
							<button class="member-handle" type="button" onclick={() => selectInfoMember(book?.owner_id)}>
								{ownerInfoName}
							</button>
						</p>
						<p>
							<strong class="role-label"><User size={15} /> Requester</strong>
							{#if requesterInfoId}
								<button class="member-handle" type="button" onclick={() => selectInfoMember(requesterInfoId)}>
									{requesterInfoName}
								</button>
							{:else}
								<span class="role-empty">Open</span>
							{/if}
						</p>
						<p>
							<strong class="role-label"><Truck size={15} /> Courier</strong>
							{#if courierInfoId}
								<button class="member-handle" type="button" onclick={() => selectInfoMember(courierInfoId)}>
									{courierInfoName}
								</button>
							{:else}
								<span class="role-empty">None</span>
							{/if}
						</p>
						<p>
							<strong>Status</strong>
							<span class="role-empty">{transaction?.archived ? 'Archived' : transaction?.locked ? 'Locked' : 'Open'}</span>
						</p>
					</div>

					<div class="personal-info">
						{#if infoLoading}
							<span class="info-loading">Loading member...</span>
						{:else if selectedInfoMember}
							<div>
								<strong>{selectedInfoMember.name}</strong>
								<span>{selectedInfoMember.email}</span>
							</div>
							<div class="info-facts">
								<span>{selectedInfoMember.gender}</span>
								<span>{selectedInfoMember.age} years</span>
								<span>{selectedInfoMember.points} pts</span>
							</div>
							<button class="ghost-button icon-label" type="button" onclick={() => openProfile(selectedInfoMember?.id)}>
								<User size={17} />
								Profile
							</button>
						{:else}
							<span class="info-loading">Select a member.</span>
						{/if}
					</div>

					{#if transaction}
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
									onclick={() => createConfirmNotification('confirm_handoff')}
								>
									<Handshake size={18} />
									Request courier handoff
								</button>
							{:else if transaction.requester_id}
								<button
									class="ghost-button icon-label"
									disabled={busy || transaction.points_applied}
									type="button"
									onclick={() => createConfirmNotification('confirm_direct_handoff')}
								>
									<Handshake size={18} />
									Request direct handoff
								</button>
							{/if}
						{:else if acceptedRole === 'courier'}
							{#if !transaction.owner_confirmed}
								<button
									class="ghost-button icon-label"
									disabled={busy}
									type="button"
									onclick={() => createConfirmNotification('confirm_handoff')}
								>
									<Handshake size={18} />
									Request owner pickup
								</button>
							{:else}
								<button
									class="ghost-button icon-label"
									disabled={busy || transaction.requester_confirmed || !transaction.requester_id}
									type="button"
									onclick={() => createConfirmNotification('confirm_delivered')}
								>
									<Handshake size={18} />
									Request delivery approval
								</button>
							{/if}
						{:else if acceptedRole === 'requester' && !transaction.courier_id}
							<button
								class="ghost-button icon-label"
								disabled={busy || transaction.points_applied}
								type="button"
								onclick={() => createConfirmNotification('confirm_direct_handoff')}
							>
								<Handshake size={18} />
								Request direct handoff
							</button>
						{:else if acceptedRole === 'requester' && transaction.courier_id && transaction.owner_confirmed}
							<button
								class="ghost-button icon-label"
								disabled={busy || transaction.requester_confirmed}
								type="button"
								onclick={() => createConfirmNotification('confirm_delivered')}
							>
								<Handshake size={18} />
								Request delivery approval
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
