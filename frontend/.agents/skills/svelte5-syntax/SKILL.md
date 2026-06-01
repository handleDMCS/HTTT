---
name: svelte5-syntax
description:
  SvelteKit and Svelte 5 syntax done right. Runes, load functions, form actions, SSR patterns, modern
  Svelte, and the complete file path / module convention reference.
---

## When to use

**IMPORTANT:** Always apply this skill when writing or reviewing any Svelte/SvelteKit code in this project. This is my official coding convention for Svelte 5 and SvelteKit.

**Why:** AI agents are trained on Svelte 4 patterns and frequently generate outdated code using stores, reactive declarations, and export let. This skill enforces Svelte 5 runes, load functions, and form actions.

---

## SvelteKit File Path Conventions
### Route Files (`src/routes/`)


All special route files are prefixed with `+`.

**Page files**

| File | Runs on | Purpose |
|---|---|---|
| `+page.svelte` | server + client | Page UI component |
| `+page.js` / `+page.ts` | server + client | `load` function; can export `prerender`, `ssr`, `csr` |
| `+page.server.js` / `+page.server.ts` | server only | Server-only `load` + form `actions` |

**Layout files**

| File | Runs on | Purpose |
|---|---|---|
| `+layout.svelte` | server + client | Shared UI wrapping child routes |
| `+layout.js` / `+layout.ts` | server + client | `load` for the layout; inherited by child routes |
| `+layout.server.js` / `+layout.server.ts` | server only | Server-only `load` for the layout |

**Other route files**

| File | Purpose |
|---|---|
| `+error.svelte` | Custom error page for the route (walks up the tree) |
| `+server.js` / `+server.ts` | API endpoint — exports HTTP handlers (`GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`, `HEAD`) |

### Route Directory Naming

| Pattern | Meaning |
|---|---|
| `src/routes/about/` | `/about` route |
| `src/routes/blog/[slug]/` | Dynamic param: `/blog/:slug` |
| `src/routes/blog/[...rest]/` | Rest/catch-all param |
| `src/routes/(group)/` | Route group — no URL segment added |
| `src/routes/[[optional]]/` | Optional param |
| `src/routes/a/[b=matcher]/` | Param with a type-constraint matcher |

### Special Project Files

**IMPORTANT:** All reusable components live in `src/lib/components/` and are imported as `$lib/components/MyComponent.svelte`.

| Path | Purpose |
|---|---|
| `src/lib/` | Aliased as `$lib` — shared components/utilities |
| `src/hooks.server.ts` | Server hooks: `handle`, `handleFetch`, `handleError` |
| `src/hooks.client.ts` | Client hooks: `handleError` |
| `src/hooks.ts` | Universal hooks: `reroute`, `transport` |
| `src/app.html` | HTML shell (`%sveltekit.head%`, `%sveltekit.body%`) |
| `src/error.html` | Static fallback error page |
| `src/service-worker.ts` | Service worker (use `$service-worker` module) |
| `static/` | Static assets served as-is |
| `svelte.config.js` | SvelteKit + Svelte config |
| `vite.config.js` | Vite config |

### Execution Order (per request)

```
hooks.server.ts
  └── +layout.server.ts  (load)
        └── +page.server.ts  (load)
              └── +layout.ts  (load)
                    └── +page.ts  (load)
                          └── +layout.svelte
                                └── +page.svelte
```

---

## Critical Rules

### 1. Use Svelte 5 runes — never Svelte 4 stores or reactive declarations

**Wrong (agents do this):**

```svelte
<script>
  import { writable, derived } from 'svelte/store';
  let count = writable(0);
  $: doubled = $count * 2;
  $: if (count > 5) alert('too high');
</script>
<p>{$count}</p>
```

**Correct:**

```svelte
<script>
  let count = $state(0);
  let doubled = $derived(count * 2);
  $effect(() => {
    if (count > 5) alert('too high');
  });
</script>
<p>{count}</p>
```

**Why:** Svelte 5 runes (`$state`, `$derived`, `$effect`) replace stores and `$:` syntax. Agents default to Svelte 4 patterns.

### 2. Use `$state` for reactive state — not `let` with reactive assignments

**Wrong:**

```svelte
<script>
  let count = 0;
  count = count + 1;
</script>
```

**Correct:**

```svelte
<script>
  let count = $state(0);
  count = count + 1;
</script>
```

**Why:** In Svelte 5, reactivity is opt-in via `$state`. Plain `let` is not reactive.

### 3. Use `$derived` for computed values — not `$:` reactive declarations

**Wrong:**

```svelte
<script>
  let firstName = $state('John');
  let lastName = $state('Doe');
  $: fullName = `${firstName} ${lastName}`;
</script>
```

**Correct:**

```svelte
<script>
  let firstName = $state('John');
  let lastName = $state('Doe');
  let fullName = $derived(`${firstName} ${lastName}`);
</script>
```

**Why:** `$:` is Svelte 4. Svelte 5 uses `$derived` for derivations.

### 4. Use `$effect` for side effects — not `$:` reactive statements

**Wrong:**

```svelte
<script>
  let count = $state(0);
  $: if (count > 5) console.log('count is high');
</script>
```

**Correct:**

```svelte
<script>
  let count = $state(0);
  $effect(() => {
    if (count > 5) console.log('count is high');
  });
</script>
```

**Why:** `$effect` runs when dependencies change. `$:` for side effects is deprecated.

### 5. Use `$props()` for component props — not `export let`

**Wrong:**

```svelte
<script>
  export let title = 'Default';
  export let count;
</script>
<h1>{title}</h1>
```

**Correct:**

```svelte
<script>
  let { title = 'Default', count } = $props();
</script>
<h1>{title}</h1>
```

**Why:** `export let` is Svelte 4. Svelte 5 uses `$props()`.

### 6. Use `$bindable()` for two-way binding props

**Wrong:**

```svelte
<script>
  let { value } = $props();
</script>
<input bind:value={value} />
```

**Correct:**

```svelte
<script>
  let { value = $bindable() } = $props();
</script>
<input bind:value={value} />
```

**Why:** Props are one-way by default. `$bindable()` enables `bind:value` from the parent.

### 7. Use load functions (`+page.server.ts`) for data fetching — not `onMount` fetch

**Wrong:**

```svelte
<script>
  import { onMount } from 'svelte';
  let data = $state(null);
  onMount(async () => {
    data = await fetch('/api/users').then(r => r.json());
  });
</script>
{#if data}{data.name}{/if}
```

**Correct:**

```typescript
// +page.server.ts
import type { PageServerLoad } from './$types';
export const load: PageServerLoad = async ({ fetch }) => ({
  data: await fetch('/api/users').then(r => r.json()),
});
```

```svelte
<!-- +page.svelte -->
<script>
  let { data } = $props();
</script>
{#if data}{data.name}{/if}
```

**Why:** Load runs on server for SSR, avoids loading flicker, and integrates with SvelteKit routing.

### 8. Use form actions for mutations — not API routes for form submissions

**Wrong:**

```svelte
<form on:submit={async (e) => {
  e.preventDefault();
  await fetch('/api/login', { method: 'POST', body: new FormData(e.target) });
  goto('/dashboard');
}}>
```

**Correct:**

```typescript
// +page.server.ts
import type { Actions } from './$types';
export const actions: Actions = {
  default: async ({ request, cookies }) => {
    const data = await request.formData();
    // validate, authenticate, set cookie
    return { type: 'redirect', location: '/dashboard' };
  },
};
```

```svelte
<form method="POST" use:enhance>
```

**Why:** Form actions enable progressive enhancement, work without JS, and avoid client-side fetch boilerplate.

### 9. Use `+layout.server.ts` for shared layout data

**Wrong:**

```svelte
<!-- Multiple pages each fetch user -->
<script>
  let user = $state(null);
  onMount(() => fetchUser().then(u => user = u));
</script>
```

**Correct:**

```typescript
// +layout.server.ts
export const load = async ({ locals }) => ({
  user: locals.user,
});
```

**Why:** Layout load runs once; data is available to all child pages. No duplicate fetches.

### 10. Use `+error.svelte` for error pages

```svelte
<!-- +error.svelte -->
<script>
  let { status, message } = $props();
</script>
<h1>{status}</h1>
<p>{message}</p>
```

**Why:** SvelteKit uses `+error.svelte` to render load/action errors. Use it instead of try/catch in every page.

### 11. Use `+page.ts` for universal load (server and client)

When data is needed on both server and client (e.g. from `$app/stores` or browser APIs), put logic in `+page.ts`. Use `+page.server.ts` when data is server-only.

### 12. Use `hooks.server.ts` for middleware (auth, redirects)

```typescript
// hooks.server.ts
export const handle = async ({ event, resolve }) => {
  event.locals.user = await getUser(event);
  if (!event.locals.user && event.url.pathname.startsWith('/dashboard')) {
    return redirect(302, '/login');
  }
  return resolve(event);
};
```

**Why:** `handle` runs before every request. Use for auth, redirects, and setting locals.

### 13. Use `$app/stores` sparingly — prefer load function data

Prefer passing data via load props. Use `$page`, `$navigating`, etc. only when you need client-side routing state.

### 14. Use snippet blocks for reusable template chunks (Svelte 5)

**Wrong:**

```svelte
<script>
  export let slots;
</script>
{#if slots.header}<slot name="header" />{/if}
```

**Correct:**

```svelte
<script>
  let { header = @render(() => {}) } = $props();
</script>
{@render header()}
```

**Why:** Svelte 5 snippets replace slot-based composition with `@render` and snippet props.

---

## Patterns

- **Page data:** `+page.server.ts` load returns object → `+page.svelte` receives via `$props()` as `data`
- **Form with enhance:** `method="POST"` and `use:enhance` from `$app/forms`
- **Streaming:** Return promises from load without `await`; use `{#await data.promise}` in template
- **TypeScript:** Use `import type { PageServerLoad, PageProps } from './$types'`

## Anti-Patterns

- Do not use `writable`, `readable`, `derived`, `get` from `svelte/store`
- Do not use `$:` for derivations or side effects
- Do not use `export let` for props
- Do not fetch in `onMount` when data is needed for SSR
- Do not create `+server.ts` API routes just for form POST handling
- Do not use `bind:value` with a prop unless the prop is `$bindable()`