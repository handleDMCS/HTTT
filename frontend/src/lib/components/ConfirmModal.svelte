<script lang="ts">
	import { onMount } from 'svelte';
	import { fade, scale } from 'svelte/transition';
	import { AlertTriangle } from '@lucide/svelte';

	type Props = {
		title: string;
		message: string;
		confirmLabel?: string;
		cancelLabel?: string;
		tone?: 'default' | 'danger';
		busy?: boolean;
		onCancel: () => void;
		onConfirm: () => void;
	};

	let {
		title,
		message,
		confirmLabel = 'Confirm',
		cancelLabel = 'Cancel',
		tone = 'default',
		busy = false,
		onCancel,
		onConfirm
	}: Props = $props();

	onMount(() => {
		function handleKeydown(event: KeyboardEvent) {
			if (event.key === 'Escape' && !busy) onCancel();
		}

		window.addEventListener('keydown', handleKeydown);
		return () => window.removeEventListener('keydown', handleKeydown);
	});
</script>

<div class="modal-layer" transition:fade={{ duration: 140 }}>
	<button
		class="modal-backdrop"
		type="button"
		aria-label="Close confirmation"
		disabled={busy}
		onclick={onCancel}
	></button>
	<dialog
		open
		class:danger={tone === 'danger'}
		class="confirm-modal"
		aria-labelledby="confirm-title"
		transition:scale={{ duration: 160, start: 0.96 }}
	>
		<div class="confirm-icon" aria-hidden="true">
			<AlertTriangle size={22} />
		</div>
		<div class="confirm-copy">
			<h2 id="confirm-title">{title}</h2>
			<p>{message}</p>
		</div>
		<div class="confirm-actions">
			<button class="ghost-button" disabled={busy} type="button" onclick={onCancel}>
				{cancelLabel}
			</button>
			<button
				class={tone === 'danger' ? 'danger-action' : 'primary-action'}
				disabled={busy}
				type="button"
				onclick={onConfirm}
			>
				{busy ? 'Working...' : confirmLabel}
			</button>
		</div>
	</dialog>
</div>
