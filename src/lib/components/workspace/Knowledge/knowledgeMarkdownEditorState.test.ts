import { describe, expect, it } from 'vitest';

import {
	deriveKnowledgeBlockPresentation,
	deriveSaveState,
	hasPendingMarkdownChanges,
	isInteractionWithinClassName,
	isInteractionWithinTarget,
	shouldCloseActiveEditorFromInteraction,
	shouldWarnBeforeUnload
} from './knowledgeMarkdownEditorState';

describe('knowledgeMarkdownEditorState', () => {
	it('marks content dirty when current markdown differs from last saved markdown', () => {
		expect(hasPendingMarkdownChanges('# A', '# B')).toBe(true);
		expect(hasPendingMarkdownChanges('# A', '# A')).toBe(false);
	});

	it('derives saving state with the correct priority', () => {
		expect(deriveSaveState({ saving: true, error: null, dirty: true })).toBe('saving');
		expect(deriveSaveState({ saving: false, error: '保存失败', dirty: true })).toBe('error');
		expect(deriveSaveState({ saving: false, error: null, dirty: true })).toBe('dirty');
		expect(deriveSaveState({ saving: false, error: null, dirty: false })).toBe('saved');
	});

	it('warns before unload when content is dirty or currently saving', () => {
		expect(shouldWarnBeforeUnload({ dirty: true, saving: false })).toBe(true);
		expect(shouldWarnBeforeUnload({ dirty: false, saving: true })).toBe(true);
		expect(shouldWarnBeforeUnload({ dirty: false, saving: false })).toBe(false);
	});

	it('derives continuous-document presentation for text blocks and embedded presentation for tables', () => {
		expect(
			deriveKnowledgeBlockPresentation({
				kind: 'heading',
				active: false,
				writeAccess: true
			})
		).toEqual({
			layout: 'flow',
			chrome: 'hover'
		});

		expect(
			deriveKnowledgeBlockPresentation({
				kind: 'table',
				active: false,
				writeAccess: true
			})
		).toEqual({
			layout: 'embedded',
			chrome: 'hover'
		});

		expect(
			deriveKnowledgeBlockPresentation({
				kind: 'paragraph',
				active: true,
				writeAccess: true
			})
		).toEqual({
			layout: 'flow',
			chrome: 'editing'
		});

		expect(
			deriveKnowledgeBlockPresentation({
				kind: 'paragraph',
				active: false,
				writeAccess: false
			})
		).toEqual({
			layout: 'flow',
			chrome: 'static'
		});
	});

	it('keeps the editor open when the interaction path still points at the workbench surface', () => {
		const workbench = { id: 'workbench' };
		const surface = {
			classList: {
				contains: (className: string) => className === 'knowledge-workbench-block__surface'
			}
		};

		const interactionPath = [surface, workbench];

		expect(isInteractionWithinTarget(interactionPath, workbench)).toBe(true);
		expect(
			isInteractionWithinClassName(interactionPath, 'knowledge-workbench-block__surface')
		).toBe(true);
		expect(
			shouldCloseActiveEditorFromInteraction({
				hasActiveEditor: true,
				withinWorkbench: true,
				withinEditingBlock: false,
				withinEditableSurface: true
			})
		).toBe(false);
	});

	it('closes the editor only when the interaction lands outside the active block and surface', () => {
		expect(
			shouldCloseActiveEditorFromInteraction({
				hasActiveEditor: true,
				withinWorkbench: true,
				withinEditingBlock: false,
				withinEditableSurface: false
			})
		).toBe(true);

		expect(
			shouldCloseActiveEditorFromInteraction({
				hasActiveEditor: true,
				withinWorkbench: false,
				withinEditingBlock: false,
				withinEditableSurface: false
			})
		).toBe(true);

		expect(
			shouldCloseActiveEditorFromInteraction({
				hasActiveEditor: false,
				withinWorkbench: false,
				withinEditingBlock: false,
				withinEditableSurface: false
			})
		).toBe(false);
	});
});
