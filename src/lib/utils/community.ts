export const COMMUNITY_UI_VISIBLE = false;

export const shouldShowCommunityFeatures = (_enabled?: boolean | null): boolean => {
	return COMMUNITY_UI_VISIBLE && (_enabled ?? false);
};
