<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { Bell, BookOpenTextIcon, LogOut, User } from '@lucide/svelte';
	import './layout.css';
	import favicon from '$lib/assets/favicon.svg';
	import {
		apiFetch,
		clearSession,
		formatTimestamp,
		getStoredMember,
		getToken,
		refreshMember,
		type ActivityMessage,
		type Member,
		type RequestBudget,
		type UnreadCounts
	} from '$lib/api';

	let { children } = $props();
	const REALTIME_REFRESH_MS = 1800;
	type RouteTab = 'book info' | 'chatbox' | 'notification';

	let member = $state<Member | null>(null);
	let activityMessages = $state<ActivityMessage[]>([]);
	let unreadCounts = $state<UnreadCounts>({ dropdown: 0 });
	let requestBudget = $state<RequestBudget | null>(null);
	let messageDropdownOpen = $state(false);
	let realtimeTimer: ReturnType<typeof setInterval> | null = null;
	let refreshInFlight = false;

	let dropdownUnread = $derived(unreadCounts.dropdown ?? 0);

	onMount(() => {
		syncHeaderState();
		if (realtimeTimer) clearInterval(realtimeTimer);
		realtimeTimer = setInterval(syncHeaderState, REALTIME_REFRESH_MS);

		return () => {
			if (realtimeTimer) clearInterval(realtimeTimer);
		};
	});

	$effect(() => {
		page.url.pathname;
		syncHeaderState();
	});

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

	async function syncHeaderState() {
		if (refreshInFlight) return;
		const token = getToken();
		if (!token) {
			member = null;
			activityMessages = [];
			unreadCounts = { dropdown: 0 };
			requestBudget = null;
			messageDropdownOpen = false;
			return;
		}

		refreshInFlight = true;
		try {
			member = getStoredMember() ?? member;
			const latestMember = await refreshMember();
			member = latestMember;
			const [messageRows, unread, budget] = await Promise.all([
				apiFetch<ActivityMessage[]>(`/api/members/${latestMember.id}/messages`),
				apiFetch<UnreadCounts>(`/api/activity/unread?member_id=${latestMember.id}`),
				apiFetch<RequestBudget>(`/api/members/${latestMember.id}/request-budget`)
			]);
			activityMessages = messageRows;
			unreadCounts = unread;
			requestBudget = budget;
		} catch {
			// Keep the current header stable during brief backend/network gaps.
		} finally {
			refreshInFlight = false;
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
			await syncHeaderState();
		}
	}

	function openActivityMessage(message: ActivityMessage) {
		messageDropdownOpen = false;
		goto(
			bookDetailUrl(message.book_id, message.notification_type ? 'notification' : 'chatbox', {
				transactionId: message.transaction_id,
				timestamp: message.timestamp
			})
		);
	}

	function logout() {
		clearSession();
		member = null;
		activityMessages = [];
		unreadCounts = { dropdown: 0 };
		requestBudget = null;
		messageDropdownOpen = false;
		goto('/login');
	}
</script>

<svelte:head><link rel="icon" href={favicon} /></svelte:head>
<div class="site-shell">
	<header class="topbar site-topbar">
		<button class="site-brand" type="button" onclick={() => goto(getToken() ? '/books' : '/login')}>
			<p class="eyebrow">Book Exchange Club</p>
			<h2>
				<BookOpenTextIcon class="inline" size={35} />
				In knowledge we trust
			</h2>
		</button>
		{#if member}
			<div class="account-block">
				<p class="font-bold">{member.name}</p>
				<strong>{member.points} pts ({requestBudget?.available_points ?? member.points} available)</strong>
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
				<button class="ghost-button icon-label" type="button" onclick={logout}>
					<LogOut size={17} />
					Log out
				</button>
			</div>
		{/if}
	</header>
	{@render children()}
</div>
