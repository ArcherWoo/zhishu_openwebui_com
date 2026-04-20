import type { KnowledgeMarkdownBlockKind } from './knowledgeMarkdownBlocks';

export const hasPendingMarkdownChanges = (
	currentMarkdown: string,
	lastSavedMarkdown: string
): boolean => currentMarkdown !== lastSavedMarkdown;

export const deriveSaveState = ({
	saving,
	error,
	dirty
}: {
	saving: boolean;
	error: string | null;
	dirty: boolean;
}): 'saved' | 'saving' | 'error' | 'dirty' => {
	if (saving) return 'saving';
	if (error) return 'error';
	if (dirty) return 'dirty';
	return 'saved';
};

export const shouldWarnBeforeUnload = ({
	dirty,
	saving
}: {
	dirty: boolean;
	saving: boolean;
}): boolean => dirty || saving;

export const deriveKnowledgeBlockPresentation = ({
	kind,
	active,
	writeAccess
}: {
	kind: KnowledgeMarkdownBlockKind;
	active: boolean;
	writeAccess: boolean;
}): {
	layout: 'flow' | 'embedded';
	chrome: 'hover' | 'editing' | 'static';
} => ({
	layout: ['table', 'code', 'html'].includes(kind) ? 'embedded' : 'flow',
	chrome: active && writeAccess ? 'editing' : writeAccess ? 'hover' : 'static'
});
