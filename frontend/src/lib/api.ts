import { browser } from '$app/environment';

export const API_BASE = 'http://localhost:8000';

export type Member = {
	id: number;
	name: string;
	email: string;
	points: number;
	gender: 'male' | 'female';
	age: number;
	avatar_path: string;
	biography: string;
	is_courier: boolean;
};

export type Book = {
	id: number;
	owner_id: number;
	owner_name: string;
	owner_email: string;
	title: string;
	genre: string;
	author: string;
	description: string;
	publication_year: number;
	condition: string;
	exchange_mode: string;
	available: boolean;
	picture_path: string;
};

export type Transaction = {
	id: number;
	book_id: number;
	book_title: string;
	owner_id: number;
	owner_name: string;
	requester_id: number | null;
	requester_name: string;
	exchange_mode: string;
	courier_id: number | null;
	courier_name: string;
	owner_confirmed: boolean;
	requester_confirmed: boolean;
	locked: boolean;
	points_applied: boolean;
	archived: boolean;
};

export type ChatMessage = {
	message_id: number;
	user_id: number;
	user_name: string;
	transaction_id: number;
	message: string;
	applied_role: 'owner' | 'requester' | 'courier';
	notification_type:
		| 'join_request'
		| 'kicked'
		| 'leave'
		| 'join'
		| 'confirm_direct_handoff'
		| 'confirm_handoff'
		| 'confirm_delivered'
		| null;
	approver_id: number | null;
	approver_role: 'owner' | 'requester' | 'courier' | null;
	accepted: boolean;
	timestamp: string;
};

export type ActivityMessage = ChatMessage & {
	book_id: number;
	book_title: string;
	transaction_archived: boolean;
};

export type UnreadCounts = {
	dropdown: number;
	chatbox?: number;
	notification?: number;
};

export type RoleApplicationStats = {
	applying: number;
	accepted: boolean;
	accepted_name: string;
};

export type ApplicationStats = {
	requester: RoleApplicationStats;
	courier: RoleApplicationStats;
};

export type RequestBudget = {
	member_id: number;
	points: number;
	reserved_points: number;
	available_points: number;
	loan_requests: number;
	permanent_requests: number;
	required_points: number;
	can_request: boolean;
};

export type MemberProfile = {
	member: Member;
	books: Book[];
};

const TOKEN_KEY = 'httt_token';
const MEMBER_KEY = 'httt_member';

export function getToken() {
	if (!browser) return '';
	return localStorage.getItem(TOKEN_KEY) ?? '';
}

export function getStoredMember(): Member | null {
	if (!browser) return null;
	const raw = localStorage.getItem(MEMBER_KEY);
	return raw ? (JSON.parse(raw) as Member) : null;
}

export function setSession(token: string, member: Member) {
	localStorage.setItem(TOKEN_KEY, token);
	localStorage.setItem(MEMBER_KEY, JSON.stringify(member));
}

export function clearSession() {
	localStorage.removeItem(TOKEN_KEY);
	localStorage.removeItem(MEMBER_KEY);
}

export function mediaUrl(path: string) {
	if (!path) return '';
	if (path.startsWith('http')) return path;
	return `${API_BASE}${path}`;
}

export function parseApiTimestamp(timestamp: string) {
	const hasTimezone = /(?:z|[+-]\d{2}:?\d{2})$/i.test(timestamp);
	return Date.parse(hasTimezone ? timestamp : `${timestamp}Z`);
}

export function formatTimestamp(timestamp: string) {
	return new Intl.DateTimeFormat(undefined, {
		month: 'short',
		day: 'numeric',
		hour: '2-digit',
		minute: '2-digit'
	}).format(new Date(parseApiTimestamp(timestamp)));
}

export async function apiFetch<T>(path: string, options: RequestInit = {}) {
	const token = getToken();
	const headers = new Headers(options.headers);
	if (!(options.body instanceof FormData)) {
		headers.set('Content-Type', 'application/json');
	}
	if (token) headers.set('Authorization', `Bearer ${token}`);

	const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
	const body = await response.json().catch(() => ({}));
	if (!response.ok) {
		throw new Error(body.detail ?? 'Request failed');
	}
	return body as T;
}

export async function refreshMember() {
	const member = await apiFetch<Member>('/api/auth/me');
	if (browser) localStorage.setItem(MEMBER_KEY, JSON.stringify(member));
	return member;
}
