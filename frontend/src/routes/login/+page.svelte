<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { apiFetch, getToken, setSession, type Member } from '$lib/api';

	let mode = $state<'login' | 'register'>('login');
	let name = $state('');
	let email = $state('');
	let password = $state('');
	let error = $state('');
	let loading = $state(false);

	onMount(() => {
		if (getToken()) goto('/books');
	});

	async function submit() {
		error = '';
		loading = true;
		try {
			const result = await apiFetch<{ access_token: string; member: Member }>(
				mode === 'login' ? '/api/auth/login' : '/api/auth/register',
				{
					method: 'POST',
					body: JSON.stringify({ name, email, password })
				}
			);
			setSession(result.access_token, result.member);
			goto('/books');
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to continue';
		} finally {
			loading = false;
		}
	}
</script>

<main class="auth-page">
	<section class="auth-panel">
		<div>
			<p class="eyebrow">Book Exchange Club</p>
			<h1>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
			<p class="muted">Track your books, accepted exchanges, and delivery chats from one shelf.</p>
		</div>

		<div class="mode-toggle" aria-label="Authentication mode">
			<button class:active={mode === 'login'} type="button" onclick={() => (mode = 'login')}>
				Log in
			</button>
			<button class:active={mode === 'register'} type="button" onclick={() => (mode = 'register')}>
				Register
			</button>
		</div>

		<form
			onsubmit={(event) => {
				event.preventDefault();
				submit();
			}}
		>
			{#if mode === 'register'}
				<label>
					Name
					<input bind:value={name} autocomplete="name" required placeholder="An Nguyen" />
				</label>
			{/if}

			<label>
				Email
				<input bind:value={email} autocomplete="email" required type="email" placeholder="you@example.com" />
			</label>

			<label>
				Password
				<input bind:value={password} autocomplete="current-password" required type="password" minlength="4" />
			</label>

			{#if error}
				<p class="form-error">{error}</p>
			{/if}

			<button class="primary-action" disabled={loading} type="submit">
				{loading ? 'Please wait...' : mode === 'login' ? 'Log in' : 'Create account'}
			</button>
		</form>
	</section>
</main>
