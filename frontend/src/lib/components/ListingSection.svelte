<script lang="ts" generics="T">
	import { ChevronLeft, ChevronRight } from '@lucide/svelte';
	import type { Snippet } from 'svelte';
	import type { Book } from '$lib/api';

	type Props<T> = {
		title: string;
		items: T[];
		getBook: (item: T) => Book;
		card: Snippet<[T]>;
		emptyText: string;
		countSuffix?: string;
		actions?: Snippet;
		pageSize?: number;
	};

	let {
		title,
		items,
		getBook,
		card,
		emptyText,
		countSuffix = 'items',
		actions,
		pageSize = 5
	}: Props<T> = $props();

	let condition = $state('');
	let yearFrom = $state('');
	let yearTo = $state('');
	let exchangeMode = $state('');
	let owner = $state('');
	let page = $state(1);

	let books = $derived(items.map((item) => getBook(item)));
	let conditions = $derived(uniqueOptions(books.map((book) => book.condition)));
	let exchangeModes = $derived(uniqueOptions(books.map((book) => book.exchange_mode)));
	let owners = $derived(uniqueOptions(books.map((book) => book.owner_name)));
	let filteredItems = $derived(
		items.filter((item) => {
			const book = getBook(item);
			const from = Number.parseInt(yearFrom, 10);
			const to = Number.parseInt(yearTo, 10);

			return (
				(!condition || book.condition === condition) &&
				(!exchangeMode || book.exchange_mode === exchangeMode) &&
				(!owner || book.owner_name === owner) &&
				(!yearFrom || book.publication_year >= from) &&
				(!yearTo || book.publication_year <= to)
			);
		})
	);
	let totalPages = $derived(Math.max(1, Math.ceil(filteredItems.length / pageSize)));
	let visibleItems = $derived(filteredItems.slice((page - 1) * pageSize, page * pageSize));
	let hasFilters = $derived(Boolean(condition || yearFrom || yearTo || exchangeMode || owner));
	let summary = $derived(`${filteredItems.length} ${countSuffix}`);

	$effect(() => {
		condition;
		yearFrom;
		yearTo;
		exchangeMode;
		owner;
		page = 1;
	});

	$effect(() => {
		if (page > totalPages) page = totalPages;
	});

	function uniqueOptions(values: string[]) {
		return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));
	}

	function clearFilters() {
		condition = '';
		yearFrom = '';
		yearTo = '';
		exchangeMode = '';
		owner = '';
	}
</script>

<section class="shelf-section">
	<div class="section-heading">
		<div>
			<h2>{title}</h2>
			<p>{summary}</p>
		</div>
		<div class="pagination-controls" aria-label={`${title} pagination`}>
			<button
				class="icon-button"
				type="button"
				aria-label="Previous page"
				disabled={page <= 1}
				onclick={() => (page -= 1)}
			>
				<ChevronLeft size={18} />
			</button>
			<span>Page {page} of {totalPages}</span>
			<button
				class="icon-button"
				type="button"
				aria-label="Next page"
				disabled={page >= totalPages}
				onclick={() => (page += 1)}
			>
				<ChevronRight size={18} />
			</button>
		</div>
	</div>

	<div class="listing-filters" aria-label={`${title} filters`}>
		<label>
			Condition
			<select bind:value={condition}>
				<option value="">Any</option>
				{#each conditions as option}
					<option value={option}>{option}</option>
				{/each}
			</select>
		</label>
		<label>
			Publication year
			<div class="range-fields">
				<input bind:value={yearFrom} type="number" min="0" placeholder="From" />
				<input bind:value={yearTo} type="number" min="0" placeholder="To" />
			</div>
		</label>
		<label>
			Exchange mode
			<select bind:value={exchangeMode}>
				<option value="">Any</option>
				{#each exchangeModes as option}
					<option value={option}>{option}</option>
				{/each}
			</select>
		</label>
		<label>
			Owner
			<select bind:value={owner}>
				<option value="">Any</option>
				{#each owners as option}
					<option value={option}>{option}</option>
				{/each}
			</select>
		</label>
		<button class="ghost-button" type="button" disabled={!hasFilters} onclick={clearFilters}>Clear</button>
	</div>

	<div class="book-row">
		{#each visibleItems as item}
			{@render card(item)}
		{:else}
			<div class="empty-card">{emptyText}</div>
		{/each}

		{#if actions}
			{@render actions()}
		{/if}
	</div>
</section>
