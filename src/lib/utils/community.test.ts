import { describe, expect, it } from 'vitest';

import { COMMUNITY_UI_VISIBLE, shouldShowCommunityFeatures } from './community';

describe('community UI visibility', () => {
	it('keeps community UI hidden even when backend community sharing is enabled', () => {
		expect(COMMUNITY_UI_VISIBLE).toBe(false);
		expect(shouldShowCommunityFeatures(true)).toBe(false);
	});

	it('keeps community UI hidden when backend community sharing is disabled or missing', () => {
		expect(shouldShowCommunityFeatures(false)).toBe(false);
		expect(shouldShowCommunityFeatures(undefined)).toBe(false);
		expect(shouldShowCommunityFeatures(null)).toBe(false);
	});
});
