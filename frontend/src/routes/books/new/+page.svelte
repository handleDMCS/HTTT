<script lang="ts">
	import { goto } from '$app/navigation';
	import { onMount } from 'svelte';
	import { ArrowLeft, Save, Trash2 } from '@lucide/svelte';
	import {
		apiFetch,
		getStoredMember,
		getToken,
		mediaUrl,
		refreshMember,
		type Book,
		type Member,
		type Transaction
	} from '$lib/api';

	let member = $state<Member | null>(null);
	let mode = $state<'new' | 'edit'>('new');
	let bookId = $state<number | null>(null);
	let title = $state('');
	let genre = $state('');
	let author = $state('');
	let description = $state('');
	let publicationYear = $state(new Date().getFullYear());
	let condition = $state('Good');
	let exchangeMode = $state('permanent');
	let pictureFile = $state<File | null>(null);
	let existingPicturePath = $state('');
	let loading = $state(false);
	let deleting = $state(false);
	let deleteBlocked = $state(false);
	let error = $state('');
	let previewUrl = $derived(pictureFile ? URL.createObjectURL(pictureFile) : mediaUrl(existingPicturePath));

	onMount(async () => {
		if (!getToken()) {
			goto('/login');
			return;
		}
		member = getStoredMember() ?? (await refreshMember());
		const params = new URLSearchParams(window.location.search);
		mode = params.get('mode') === 'edit' ? 'edit' : 'new';
		bookId = Number(params.get('book_id')) || null;

		if (mode === 'edit' && bookId) {
			try {
				const [books, transactions] = await Promise.all([
					apiFetch<Book[]>('/api/books'),
					apiFetch<Transaction[]>('/api/transactions')
				]);
				const book = books.find((row) => row.id === bookId);
				if (!book) throw new Error('Book not found');
				if (member && book.owner_id !== member.id) throw new Error('Only the owner can edit this book');
				deleteBlocked = transactions.some(
					(transaction) => transaction.book_id === book.id && (transaction.locked || transaction.archived)
				);
				title = book.title;
				genre = book.genre;
				author = book.author;
				description = book.description;
				publicationYear = book.publication_year;
				condition = book.condition;
				exchangeMode = book.exchange_mode;
				existingPicturePath = book.picture_path;
			} catch (err) {
				error = err instanceof Error ? err.message : 'Unable to load this book';
			}
		}
	});

	function choosePicture(event: Event) {
		const input = event.currentTarget as HTMLInputElement;
		pictureFile = input.files?.[0] ?? null;
	}

	async function saveBook() {
		if (!member) return;
		error = '';
		loading = true;
		const payload = new FormData();
		payload.set('owner_id', String(member.id));
		payload.set('title', title);
		payload.set('genre', genre);
		payload.set('author', author);
		payload.set('description', description);
		payload.set('publication_year', String(publicationYear));
		payload.set('condition', condition);
		payload.set('exchange_mode', exchangeMode);
		if (pictureFile) payload.set('picture', pictureFile);

		try {
			if (mode === 'edit' && bookId) {
				await apiFetch<Book>(`/api/books/${bookId}`, {
					method: 'PUT',
					body: payload
				});
			} else {
				await apiFetch<Book>('/api/books', {
					method: 'POST',
					body: payload
				});
			}
			goto('/books');
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to save book';
		} finally {
			loading = false;
		}
	}

	async function deleteBook() {
		if (!member || !bookId || deleteBlocked) return;
		if (!window.confirm('Delete this book listing?')) return;
		error = '';
		deleting = true;

		try {
			await apiFetch<{ deleted: boolean }>(`/api/books/${bookId}?owner_id=${member.id}`, {
				method: 'DELETE'
			});
			goto('/books');
		} catch (err) {
			error = err instanceof Error ? err.message : 'Unable to delete book';
		} finally {
			deleting = false;
		}
	}
</script>

<main class="form-page">
	<section class="form-shell">
		<div class="form-header">
			<button class="icon-button" type="button" aria-label="Back to books" onclick={() => goto('/books')}>
				<ArrowLeft size={21} />
			</button>
			<div>
				<p class="eyebrow">{mode === 'edit' ? 'Edit listing' : 'New listing'}</p>
				<h1>{mode === 'edit' ? 'Update book' : 'Add a book'}</h1>
			</div>
		</div>

		<form
			class="book-form"
			onsubmit={(event) => {
				event.preventDefault();
				saveBook();
			}}
		>
			<label>
				Title
				<input bind:value={title} required placeholder="Clean Code" />
			</label>
			<label>
				Author
				<input bind:value={author} required placeholder="Robert C. Martin" />
			</label>
			<label>
				Description <span class="optional-label">Optional</span>
				<textarea bind:value={description} rows="4" placeholder="Add notes about the edition, story, or why it is worth reading"></textarea>
			</label>
			<div class="form-grid">
				<label>
					Genre
					<input bind:value={genre} required placeholder="Software" />
				</label>
				<label>
					Publication year
					<input bind:value={publicationYear} required type="number" min="1400" max="2100" />
				</label>
			</div>
			<div class="form-grid">
				<label>
					Condition
					<select bind:value={condition}>
						<option>Like new</option>
						<option>Good</option>
						<option>Used</option>
						<option>Fair</option>
					</select>
				</label>
				<label>
					Exchange mode
					<select bind:value={exchangeMode}>
						<option value="permanent">Permanent</option>
						<option value="loan">Loan</option>
					</select>
				</label>
			</div>

			<label>
				Book picture
				<input accept="image/*" type="file" onchange={choosePicture} />
			</label>

			{#if previewUrl}
				<img class="picture-preview" src={previewUrl} alt="Book preview" />
			{/if}

			{#if error}
				<p class="form-error">{error}</p>
			{/if}

			<button class="primary-action icon-label" disabled={loading} type="submit">
				{#if !loading}
					<Save size={18} />
				{/if}
				{loading ? 'Saving...' : mode === 'edit' ? 'Save changes' : 'Create listing'}
			</button>
			{#if mode === 'edit'}
				<button
					class="danger-action icon-label"
					disabled={loading || deleting || deleteBlocked}
					type="button"
					onclick={deleteBook}
				>
					{#if !deleting}
						<Trash2 size={18} />
					{/if}
					{deleting ? 'Deleting...' : 'Delete book'}
				</button>
				{#if deleteBlocked}
					<p class="muted">This book cannot be deleted because its transaction is locked or archived.</p>
				{/if}
			{/if}
		</form>
	</section>
</main>
