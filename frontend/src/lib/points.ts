import type { Transaction } from './api';

export type PointChange = {
	role: 'Owner' | 'Requester' | 'Courier';
	name: string;
	delta: number;
};

const COURIER_REWARD_POINTS = 2;

export function pointsForExchangeMode(exchangeMode: string) {
	if (exchangeMode === 'permanent') return 10;
	if (exchangeMode === 'loan') return 5;
	return 0;
}

export function pointDeltaForMember(transaction: Transaction, memberId?: number | null) {
	if (!memberId) return null;

	const exchangePoints = pointsForExchangeMode(transaction.exchange_mode);
	if (memberId === transaction.owner_id) return exchangePoints;
	if (memberId === transaction.requester_id) return -exchangePoints;
	if (memberId === transaction.courier_id) return COURIER_REWARD_POINTS;
	return null;
}

export function transactionPointChanges(transaction: Transaction): PointChange[] {
	const exchangePoints = pointsForExchangeMode(transaction.exchange_mode);
	const changes: PointChange[] = [
		{
			role: 'Owner',
			name: transaction.owner_name,
			delta: exchangePoints
		}
	];

	if (transaction.requester_id) {
		changes.push({
			role: 'Requester',
			name: transaction.requester_name || 'Requester',
			delta: -exchangePoints
		});
	}

	if (transaction.courier_id) {
		changes.push({
			role: 'Courier',
			name: transaction.courier_name || 'Courier',
			delta: COURIER_REWARD_POINTS
		});
	}

	return changes;
}

export function formatPointDelta(delta: number) {
	return `${delta > 0 ? '+' : ''}${delta} pts`;
}
