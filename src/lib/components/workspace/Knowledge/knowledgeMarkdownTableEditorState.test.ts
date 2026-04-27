import { describe, expect, it } from 'vitest';

import { deriveTableHoverState } from './knowledgeMarkdownTableEditorState';

describe('knowledgeMarkdownTableEditorState', () => {
	it('marks both row and column as active for the hovered cell', () => {
		expect(
			deriveTableHoverState({
				hoveredRowIndex: 2,
				hoveredColumnIndex: 3,
				rowIndex: 2,
				columnIndex: 3
			})
		).toEqual({
			rowActive: true,
			columnActive: true,
			cellActive: true
		});
	});

	it('keeps non-hovered cells inactive', () => {
		expect(
			deriveTableHoverState({
				hoveredRowIndex: 1,
				hoveredColumnIndex: 0,
				rowIndex: 3,
				columnIndex: 2
			})
		).toEqual({
			rowActive: false,
			columnActive: false,
			cellActive: false
		});
	});

	it('highlights row or column independently when only one axis matches', () => {
		expect(
			deriveTableHoverState({
				hoveredRowIndex: 1,
				hoveredColumnIndex: 4,
				rowIndex: 1,
				columnIndex: 2
			})
		).toEqual({
			rowActive: true,
			columnActive: false,
			cellActive: true
		});

		expect(
			deriveTableHoverState({
				hoveredRowIndex: 1,
				hoveredColumnIndex: 4,
				rowIndex: 3,
				columnIndex: 4
			})
		).toEqual({
			rowActive: false,
			columnActive: true,
			cellActive: true
		});
	});
});
