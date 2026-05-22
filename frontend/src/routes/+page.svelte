<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { getToken } from '$lib/api';

	onMount(() => {
		goto(getToken() ? '/books' : '/login');
	});
</script>

<main class="center-screen">
	<p>Loading your shelf...</p>
</main>
