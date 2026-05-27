<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { onMount } from 'svelte';
	import { ArrowLeft, Edit3, Save, X } from '@lucide/svelte';
	import ListingSection from '$lib/components/ListingSection.svelte';
	import {
		apiFetch,
		getStoredMember,
		getToken,
		mediaUrl,
		refreshMember,
		type Book,
		type Member,
		type MemberProfile
	} from '$lib/api';

	let currentMember = $state<Member | null>(null);
	let profile = $state<MemberProfile | null>(null);
	let loading = $state(true);
	let saving = $state(false);
	let editing = $state(false);
	let error = $state('');
	let name = $state('');
	let gender = $state<'male' | 'female'>('male');
	let age = $state(18);
	let biography = $state('');
	let avatarFile = $state<File | null>(null);
	let avatarPreviewUrl = $derived(
		avatarFile ? URL.createObjectURL(avatarFile) : mediaUrl(profile?.member.avatar_path ?? '')
	);
	let isOwnProfile = $derived(!!currentMember && !!profile && currentMember.id === profile.member.id);

	onMount(() => {
		if (!getToken()) {
			goto('/login');
			return;
		}
		currentMember = getStoredMember();
		loadProfile();
	});

	async function loadProfile() {
		loading = true;
		error = '';
		try {
			currentMember = await refreshMember();
			profile = await apiFetch<MemberProfile>(`/api/members/${page.params.id}/profile`);
			resetForm();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to load profile';
		} finally {
			loading = false;
		}
	}

	function resetForm() {
		if (!profile) return;
		name = profile.member.name;
		gender = profile.member.gender;
		age = profile.member.age;
		biography = profile.member.biography;
		avatarFile = null;
	}

	function startEditing() {
		resetForm();
		editing = true;
		error = '';
	}

	function cancelEditing() {
		resetForm();
		editing = false;
		error = '';
	}

	function chooseAvatar(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		avatarFile = input.files?.[0] ?? null;
	}

	async function saveProfile() {
		if (!profile) return;
		saving = true;
		error = '';
		const payload = new FormData();
		payload.set('name', name);
		payload.set('gender', gender);
		payload.set('age', String(age));
		payload.set('biography', biography);
		if (avatarFile) payload.set('avatar', avatarFile);

		try {
			const updated = await apiFetch<Member>(`/api/members/${profile.member.id}/profile`, {
				method: 'PUT',
				body: payload
			});
			profile = { ...profile, member: updated };
			currentMember = await refreshMember();
			editing = false;
			await loadProfile();
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to save profile';
		} finally {
			saving = false;
		}
	}

	function openBook(book: Book) {
		goto(`/books/${book.id}?view_chatbox=false`);
	}
</script>

{#snippet postedBookCard(book: Book)}
	<button class="book-card available" type="button" onclick={() => openBook(book)}>
		{#if book.picture_path}
			<img class="book-thumb" src={mediaUrl(book.picture_path)} alt={book.title} />
		{/if}
		<span class="book-spine">{book.condition}</span>
		<strong>{book.title}</strong>
		<small>{book.author}</small>
		<span class="pill">{book.exchange_mode}</span>
	</button>
{/snippet}

<main class="profile-page">
	<section class="profile-shell">
		<div class="profile-topbar">
			<button class="icon-button" type="button" aria-label="Back to books" onclick={() => goto('/books')}>
				<ArrowLeft size={21} />
			</button>
		</div>

		{#if loading}
			<p class="empty-state">Loading profile...</p>
		{:else if error && !profile}
			<p class="empty-state">{error}</p>
		{:else if profile}
			<div class="profile-layout">
				<section class="profile-card">
					<img class="avatar-large" src={avatarPreviewUrl} alt={`${profile.member.name} avatar`} />
					<div class="profile-summary">
						<div>
							<p class="eyebrow">{profile.member.gender}, {profile.member.age}</p>
							<h2>{profile.member.name}</h2>
						</div>
						<div class="profile-stats">
							<span>{profile.member.email}</span>
							<strong>{profile.member.points} pts</strong>
						</div>
						{#if isOwnProfile && !editing}
							<button class="ghost-button icon-label" type="button" onclick={startEditing}>
								<Edit3 size={17} />
								Edit profile
							</button>
						{/if}
					</div>
					<div class="profile-bio" aria-label="Biography">
						<p>{profile.member.biography || 'No biography yet.'}</p>
					</div>
				</section>

				{#if isOwnProfile && editing}
					<form
						class="profile-edit-form"
						onsubmit={(event) => {
							event.preventDefault();
							saveProfile();
						}}
					>
						<label>
							Name
							<input bind:value={name} required autocomplete="name" />
						</label>
						<div class="form-grid">
							<label>
								Gender
								<select bind:value={gender}>
									<option value="male">Male</option>
									<option value="female">Female</option>
								</select>
							</label>
							<label>
								Age
								<input bind:value={age} required type="number" min="1" max="120" />
							</label>
						</div>
						<label>
							Biography
							<textarea bind:value={biography} rows="4" placeholder="Share what you like to read or exchange"></textarea>
						</label>
						<label>
							Avatar
							<input accept="image/*" type="file" onchange={chooseAvatar} />
						</label>
						<div class="protected-fields">
							<span>Email: {profile.member.email}</span>
							<span>Points: {profile.member.points}</span>
						</div>
						{#if error}
							<p class="form-error">{error}</p>
						{/if}
						<div class="profile-edit-actions">
							<button class="primary-action icon-label" disabled={saving} type="submit">
								{#if !saving}
									<Save size={18} />
								{/if}
								{saving ? 'Saving...' : 'Save changes'}
							</button>
							<button class="ghost-button icon-label" disabled={saving} type="button" onclick={cancelEditing}>
								<X size={18} />
								Cancel
							</button>
						</div>
					</form>
				{/if}
			</div>

			<ListingSection
				title="Posted books"
				items={profile.books}
				getBook={(book) => book}
				card={postedBookCard}
				emptyText="No books posted yet."
				countSuffix="posted"
			/>
		{/if}
	</section>
</main>
