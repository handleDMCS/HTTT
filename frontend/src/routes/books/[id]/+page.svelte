<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount, tick } from 'svelte';
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
		Undo2,
		User,
		UserMinus,
		type Icon
	} from '@lucide/svelte';
	import { formatPointDelta, transactionPointChanges } from '$lib/points';
	import {
		apiFetch,
		formatTimestamp,
		getStoredMember,
		getToken,
		mediaUrl,
		parseApiTimestamp,
		refreshMember,
		type Book,
		type ChatMessage,
		type ApplicationStats,
		type Member,
		type MemberProfile,
		type RequestBudget,
		type Transaction,
		type UnreadCounts
	} from '$lib/api';

	type DetailTab = 'info' | 'chat' | 'notification';
	type RouteTab = 'book info' | 'chatbox' | 'notification';
	type Role = 'requester' | 'courier';
	type RoleName = 'owner' | Role;
	type ConfirmNotificationType =
		| 'confirm_direct_handoff'
		| 'confirm_handoff'
		| 'confirm_delivered';
	const REALTIME_REFRESH_MS = 1800;
	const CONFIRM_NOTIFICATION_TIMEOUT_SECONDS = 60;
	const CONFIRM_NOTIFICATION_TYPES = new Set<ChatMessage['notification_type']>([
		'confirm_direct_handoff',
		'confirm_handoff',
		'confirm_delivered'
	]);

	let member = $state<Member | null>(null);
	let book = $state<Book | null>(null);
	let transaction = $state<Transaction | null>(null);
	let messages = $state<ChatMessage[]>([]);
	let pendingApplication = $state<ChatMessage | null>(null);
	let applicationStats = $state<ApplicationStats>({
		requester: { applying: 0, accepted: false, accepted_name: '' },
		courier: { applying: 0, accepted: false, accepted_name: '' }
	});
	let requestBudget = $state<RequestBudget | null>(null);
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
	let countdownTimer: ReturnType<typeof setInterval> | null = null;
	let realtimeRefreshInFlight = false;
	let nowMs = $state(Date.now());
	let messageListElement = $state<HTMLDivElement | null>(null);
	let pendingListElement = $state<HTMLDivElement | null>(null);
	let lastScrollKey = '';
	let lastRouteTabKey = '';
	let lastAppliedRoleKey = '';
	let hadAcceptedMembership = false;

	let requestedTab = $derived(parseRouteTab(page.url.searchParams));
	let requestedTimestamp = $derived(page.url.searchParams.get('timestamp') ?? '');
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
	let canViewChat = $derived(acceptedRole !== null);
	let chatboxLocked = $derived(!!transaction?.locked || !!transaction?.points_applied);
	let notificationMessages = $derived(messages.filter((message) => message.notification_type !== null));
	let selectedRoleStats = $derived(applicationStats[applyRole]);
	let chatMessages = $derived(
		messages.filter((message) => message.accepted && message.notification_type === null)
	);
	let requesterBudgetOk = $derived(applyRole !== 'requester' || requestBudget?.can_request !== false);
	let canWithdrawSelectedRole = $derived(pendingApplication?.applied_role === applyRole);
	let ownerInfoName = $derived(transaction?.owner_name || book?.owner_name || '');
	let requesterInfoId = $derived(transaction?.requester_id ?? null);
	let requesterInfoName = $derived(transaction?.requester_name || '');
	let courierInfoId = $derived(transaction?.courier_id ?? null);
	let courierInfoName = $derived(transaction?.courier_name || '');
	let archivePointChanges = $derived(transaction ? transactionPointChanges(transaction) : []);

	let chatboxUnread = $derived(unreadCounts.chatbox ?? 0);
	let notificationUnread = $derived(unreadCounts.notification ?? 0);

	$effect(() => {
		if (!book || loading) return;
		const routeTabKey = `${requestedTab}:${canViewChat}`;
		if (routeTabKey === lastRouteTabKey) return;
		lastRouteTabKey = routeTabKey;
		activeTab = allowedDetailTab(requestedTab);
	});

	$effect(() => {
		if (loading || activeTab === 'info') return;
		const visibleMessages = activeTab === 'chat' ? chatMessages : notificationMessages;
		const newestMessage = visibleMessages[visibleMessages.length - 1];
		if (!newestMessage) return;
		const scrollKey = `${activeTab}:${requestedTimestamp}:${visibleMessages.length}:${newestMessage.message_id}`;
		if (scrollKey === lastScrollKey) return;
		lastScrollKey = scrollKey;
		tick().then(() => scrollToRequestedMessage(activeTab, requestedTimestamp));
	});

	$effect(() => {
		if (!member || !book || selectedInfoMember) return;
		if (canViewChat) {
			selectedInfoMember = member;
			return;
		}
		selectInfoMember(book.owner_id);
	});

	$effect(() => {
		const appliedRoleKey = pendingApplication
			? `${pendingApplication.message_id}:${pendingApplication.applied_role}`
			: '';
		if (appliedRoleKey === lastAppliedRoleKey) return;
		lastAppliedRoleKey = appliedRoleKey;
		if (pendingApplication?.applied_role === 'requester' || pendingApplication?.applied_role === 'courier') {
			applyRole = pendingApplication.applied_role;
		}
	});

	onMount(() => {
		if (!getToken()) {
			goto('/login');
			return undefined;
		}

		member = getStoredMember();
		countdownTimer = setInterval(() => {
			nowMs = Date.now();
		}, 1000);
		loadPage().then(startRealtimeRefresh);

		return () => {
			if (realtimeTimer) clearInterval(realtimeTimer);
			if (countdownTimer) clearInterval(countdownTimer);
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
			hadAcceptedMembership = !!acceptedRole;
			activeTab = allowedDetailTab(requestedTab);
			await Promise.all([
				loadMessages(),
				loadApplicationStats(),
				loadUnreadCounts(),
				loadRequestBudget(),
				loadPendingApplication()
			]);
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

			const wasAcceptedBeforeRefresh = hadAcceptedMembership;
			transaction = latestTransaction;
			const isAcceptedAfterRefresh = !!memberRoleForTransaction(latestTransaction, latestMember.id);
			hadAcceptedMembership = isAcceptedAfterRefresh;
			if (shouldRedirectToChatbox(latestTransaction, latestMember, wasAcceptedBeforeRefresh)) return;
			if (!transaction) {
				messages = [];
				resetApplicationStats();
				return;
			}

			await Promise.all([
				loadMessages(),
				loadApplicationStats(),
				loadUnreadCounts(),
				loadRequestBudget(),
				loadPendingApplication()
			]);
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

	async function loadRequestBudget() {
		if (!member || !book) {
			requestBudget = null;
			return;
		}
		try {
			const params = new URLSearchParams(
				transaction ? { transaction_id: String(transaction.id) } : { book_id: String(book.id) }
			);
			requestBudget = await apiFetch<RequestBudget>(
				`/api/members/${member.id}/request-budget?${params.toString()}`
			);
		} catch {
			requestBudget = null;
		}
	}

	async function loadPendingApplication() {
		if (!member || !transaction || canViewChat) {
			pendingApplication = null;
			return;
		}
		try {
			pendingApplication = await apiFetch<ChatMessage | null>(
				`/api/transactions/${transaction.id}/application?user_id=${member.id}`
			);
		} catch {
			pendingApplication = null;
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
		if (applyRole === 'requester' && requestBudget?.can_request === false) {
			error = `You need ${requestBudget.required_points} available points.`;
			return;
		}
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

	async function withdrawApplication() {
		if (!member || !transaction || readOnly || !canWithdrawSelectedRole) return;
		busy = true;
		error = '';
		try {
			await apiFetch(`/api/transactions/${transaction.id}/withdraw-application`, {
				method: 'POST',
				body: JSON.stringify({ user_id: member.id })
			});
			await refreshRealtimeState(true);
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to withdraw application';
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

	async function createConfirmNotification(notificationType: ConfirmNotificationType) {
		if (!member || !transaction || readOnly || activeConfirmCooldown(notificationType)) return;
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

	function isConfirmNotification(message: ChatMessage) {
		return CONFIRM_NOTIFICATION_TYPES.has(message.notification_type);
	}

	function confirmCountdownRemaining(message: ChatMessage) {
		const expiresAt = parseApiTimestamp(message.timestamp) + CONFIRM_NOTIFICATION_TIMEOUT_SECONDS * 1000;
		return Math.max(0, Math.ceil((expiresAt - nowMs) / 1000));
	}

	function confirmCountdownProgress(message: ChatMessage) {
		return (
			(confirmCountdownRemaining(message) / CONFIRM_NOTIFICATION_TIMEOUT_SECONDS) * 100
		).toFixed(2);
	}

	function confirmCountdownLabel(message: ChatMessage) {
		const remaining = confirmCountdownRemaining(message);
		return remaining > 0 ? `${remaining}s` : '0s';
	}

	function confirmTimedOut(message: ChatMessage) {
		return isConfirmNotification(message) && !message.accepted && confirmCountdownRemaining(message) <= 0;
	}

	function activeConfirmCooldown(notificationType: ConfirmNotificationType) {
		let activeMessage: ChatMessage | null = null;
		for (const message of notificationMessages) {
			if (
				message.notification_type === notificationType &&
				!message.accepted &&
				message.approver_id !== null &&
				message.approver_role !== null &&
				confirmCountdownRemaining(message) > 0
			) {
				activeMessage = message;
			}
		}
		return activeMessage;
	}

	function canApproveNotification(message: ChatMessage) {
		return (
			!!member &&
			!!acceptedRole &&
			!readOnly &&
			!message.accepted &&
			!confirmTimedOut(message) &&
			message.approver_id === member.id &&
			message.approver_role === acceptedRole
		);
	}

	function openProfile(userId: number | null | undefined) {
		if (userId) goto(`/profile/${userId}`);
	}

	function selectDetailTab(tab: DetailTab) {
		activeTab = tab;
		updateDetailRoute(tab);
		markVisibleActiveTab();
	}

	function shouldRedirectToChatbox(
		latestTransaction: Transaction | null,
		latestMember: Member,
		wasAcceptedBeforeRefresh: boolean
	) {
		if (!book || !latestTransaction || routeTransactionId || requestedTab !== 'book info') return false;
		const approvedRole = memberRoleForTransaction(latestTransaction, latestMember.id);
		if (!approvedRole || approvedRole === 'owner' || wasAcceptedBeforeRefresh) return false;
		goto(bookDetailUrl(book.id, 'chatbox'));
		return true;
	}

	function memberRoleForTransaction(transaction: Transaction | null, memberId: number): RoleName | null {
		if (!transaction) return null;
		if (memberId === transaction.owner_id) return 'owner';
		if (memberId === transaction.requester_id) return 'requester';
		if (memberId === transaction.courier_id) return 'courier';
		return null;
	}

	function selectedInfoRole() {
		if (!selectedInfoMember) return null;
		return memberRoleForTransaction(transaction, selectedInfoMember.id);
	}

	function parseRouteTab(params: URLSearchParams): RouteTab {
		const value = params.get('tab');
		if (value === 'chatbox' || value === 'notification' || value === 'book info') return value;
		if (value === 'chat') return 'chatbox';
		if (value === 'info') return 'book info';
		if (params.get('view_chatbox') === 'true') return 'chatbox';
		return 'book info';
	}

	function internalTab(tab: RouteTab): DetailTab {
		if (tab === 'chatbox') return 'chat';
		if (tab === 'notification') return 'notification';
		return 'info';
	}

	function routeTab(tab: DetailTab): RouteTab {
		if (tab === 'chat') return 'chatbox';
		if (tab === 'notification') return 'notification';
		return 'book info';
	}

	function allowedDetailTab(tab: RouteTab): DetailTab {
		const nextTab = internalTab(tab);
		if (nextTab !== 'info' && !canViewChat) return 'info';
		return nextTab;
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

	function updateDetailRoute(tab: DetailTab) {
		if (!book) return;
		const transactionId = routeTransactionId ?? (readOnly ? transaction?.id : null);
		goto(bookDetailUrl(book.id, routeTab(tab), { transactionId }), {
			replaceState: true,
			noScroll: true,
			keepFocus: true
		});
	}

	function targetMessage(messagesForTab: ChatMessage[], timestamp: string) {
		if (messagesForTab.length === 0) return null;
		const targetTime = parseApiTimestamp(timestamp);
		if (!Number.isFinite(targetTime)) return messagesForTab[messagesForTab.length - 1] ?? null;
		return messagesForTab.reduce((nearest, message) => {
			const nearestDistance = Math.abs(parseApiTimestamp(nearest.timestamp) - targetTime);
			const messageDistance = Math.abs(parseApiTimestamp(message.timestamp) - targetTime);
			return messageDistance < nearestDistance ? message : nearest;
		});
	}

	function scrollToRequestedMessage(tab: DetailTab, timestamp: string) {
		const container = tab === 'chat' ? messageListElement : pendingListElement;
		const messagesForTab = tab === 'chat' ? chatMessages : notificationMessages;
		const message = targetMessage(messagesForTab, timestamp);
		if (!container || !message) return;
		const target = container.querySelector<HTMLElement>(`[data-message-id="${message.message_id}"]`);
		if (!target) return;
		const centeredTop = target.offsetTop - container.offsetTop - (container.clientHeight - target.clientHeight) / 2;
		container.scrollTo({ top: Math.max(0, centeredTop), behavior: 'smooth' });
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

{#snippet confirmRequestButton(
	notificationType: ConfirmNotificationType,
	label: string,
	disabled = false
)}
	{@const cooldownMessage = activeConfirmCooldown(notificationType)}
	<button
		class="ghost-button icon-label confirm-request-button"
		class:cooling-down={!!cooldownMessage}
		disabled={busy || disabled || !!cooldownMessage}
		type="button"
		onclick={() => createConfirmNotification(notificationType)}
	>
		<Handshake size={18} />
		<span>{label}</span>
		{#if cooldownMessage}
			<span
				class="countdown-circle compact"
				class:expired={confirmCountdownRemaining(cooldownMessage) <= 0}
				style={`--countdown-progress: ${confirmCountdownProgress(cooldownMessage)}%;`}
				aria-label={`Confirmation cooldown ends in ${confirmCountdownLabel(cooldownMessage)}`}
				title={`Cooldown ends in ${confirmCountdownLabel(cooldownMessage)}`}
			>
				<span>{confirmCountdownLabel(cooldownMessage)}</span>
			</span>
		{/if}
	</button>
{/snippet}

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
										{#if applyRole === 'requester' && requestBudget}
											<div>
												<span>Available points</span>
												<strong>{requestBudget.available_points}</strong>
											</div>
											<div>
												<span>Needed</span>
												<strong>{requestBudget.required_points}</strong>
											</div>
										{/if}
									</div>
									{#if applyRole === 'requester' && requestBudget?.can_request === false}
										<p class="form-help">You need {requestBudget.required_points} available points.</p>
									{/if}
									<label>
										Introduction note
										<input
											bind:value={applyMessage}
											placeholder="Share pickup timing, location, or why you want this book"
										/>
									</label>
									<div class="application-actions">
										<button
											class="primary-action icon-label"
											disabled={busy || !requesterBudgetOk}
											type="submit"
										>
											{#if !busy}
												<Send size={18} />
											{/if}
											{busy ? 'Sending...' : 'Apply'}
										</button>
										<button
											class="primary-action icon-label"
											disabled={busy || !canWithdrawSelectedRole}
											type="button"
											onclick={withdrawApplication}
										>
											<Undo2 size={18} />
											Withdraw
										</button>
									</div>
								</form>
							{:else if !isOwner && !canViewChat && chatboxLocked}
								<p class="empty-state">This chatbox is locked for handoff.</p>
							{:else if !isOwner && !book.available}
								<p class="empty-state">This book is no longer available.</p>
							{/if}
						</div>
					{:else if activeTab === 'chat'}
						<div class="message-list" bind:this={messageListElement}>
							{#each chatMessages as message}
								{@const MessageRoleIcon = roleIcon(message.applied_role)}
								{@const messageAvatarUrl = mediaUrl(message.user_avatar_path)}
								<article
									class:mine={message.user_id === member?.id}
									class="message-bubble"
									data-message-id={message.message_id}
								>
									<div class="message-copy">
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
									</div>
									<img
										class="message-avatar"
										src={messageAvatarUrl}
										alt={`${message.user_name} avatar`}
										loading="lazy"
									/>
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
								<button class="primary-action" disabled={busy} type="submit">
									<Send size={18} class="inline"/>
									Send
								</button>
							</form>
						{/if}
					{:else}
						<div class="pending-list" bind:this={pendingListElement}>
							{#each notificationMessages as message}
								{@const PendingRoleIcon = roleIcon(message.applied_role)}
								{@const messageAvatarUrl = mediaUrl(message.user_avatar_path)}
								<article class="pending-card" data-message-id={message.message_id}>
									<div class="pending-copy">
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
										{#if confirmTimedOut(message) || (isConfirmNotification(message) && !message.accepted && !message.approver_role)}
											<p class="muted">Expired.</p>
										{:else if message.approver_role && !message.accepted}
											<p class="muted">Waiting for {roleLabel(message.approver_role)} approval.</p>
										{:else if message.approver_role && message.accepted}
											<p class="muted">Approved.</p>
										{/if}
									</div>
									<img
										class="message-avatar"
										src={messageAvatarUrl}
										alt={`${message.user_name} avatar`}
										loading="lazy"
									/>
									{#if isConfirmNotification(message) && !message.accepted && message.approver_role}
										<div
											class:expired={confirmCountdownRemaining(message) <= 0}
											class="countdown-circle"
											style={`--countdown-progress: ${confirmCountdownProgress(message)}%;`}
											aria-label={`Confirmation expires in ${confirmCountdownLabel(message)}`}
											title={`Expires in ${confirmCountdownLabel(message)}`}
										>
											<span>{confirmCountdownLabel(message)}</span>
										</div>
									{/if}
									{#if canApproveNotification(message)}
										<div class="pending-actions">
											<button
												class="primary-action"
												disabled={busy || readOnly}
												type="button"
												onclick={() => approveNotification(message)}
											>
												<Check size={18} class="inline"/>
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
							{@const infoRole = selectedInfoRole()}
							<div>
								<strong class="personal-name">
									{selectedInfoMember.name}
									{#if infoRole}
										<span>({roleLabel(infoRole)})</span>
									{/if}
								</strong>
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
							<div class="archive-point-summary" aria-label="Archived point changes">
								{#each archivePointChanges as pointChange}
									<div
										class:negative={pointChange.delta < 0}
										class:positive={pointChange.delta > 0}
										class="archive-point-row"
									>
										<span>{pointChange.role}</span>
										<strong>{formatPointDelta(pointChange.delta)}</strong>
										<small>{pointChange.name}</small>
									</div>
								{/each}
							</div>
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
								{@render confirmRequestButton(
									'confirm_handoff',
									'Request courier handoff',
									transaction.owner_confirmed
								)}
							{:else if transaction.requester_id}
								{@render confirmRequestButton(
									'confirm_direct_handoff',
									'Request direct handoff',
									transaction.points_applied
								)}
							{/if}
						{:else if acceptedRole === 'courier'}
							{#if !transaction.owner_confirmed}
								{@render confirmRequestButton('confirm_handoff', 'Request owner pickup')}
							{:else}
								{@render confirmRequestButton(
									'confirm_delivered',
									'Request delivery approval',
									transaction.requester_confirmed || !transaction.requester_id
								)}
							{/if}
						{:else if acceptedRole === 'requester' && !transaction.courier_id}
							{@render confirmRequestButton(
								'confirm_direct_handoff',
								'Request direct handoff',
								transaction.points_applied
							)}
						{:else if acceptedRole === 'requester' && transaction.courier_id && transaction.owner_confirmed}
							{@render confirmRequestButton(
								'confirm_delivered',
								'Request delivery approval',
								transaction.requester_confirmed
							)}
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
