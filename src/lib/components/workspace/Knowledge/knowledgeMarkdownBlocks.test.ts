import { describe, expect, it } from 'vitest';

import {
	isKnowledgeMarkdownFile,
	parseMarkdownBlocks,
	replaceMarkdownBlockRaw,
	type KnowledgeMarkdownBlock
} from './knowledgeMarkdownBlocks';

describe('knowledgeMarkdownBlocks', () => {
	it('splits markdown into top-level editable blocks while preserving raw source', () => {
		const markdown = `# 标题

第一段正文。

| 列 1 | 列 2 |
| --- | --- |
| A | B |
`;

		const blocks = parseMarkdownBlocks(markdown);

		expect(blocks.map((block) => block.kind)).toEqual(['heading', 'paragraph', 'table']);
		expect(blocks[0].raw).toContain('# 标题');
		expect(blocks[1].raw).toContain('第一段正文');
		expect(blocks[2].raw).toContain('| 列 1 | 列 2 |');
	});

	it('replaces a single block without losing surrounding markdown', () => {
		const markdown = `# 标题

第一段正文。

第二段正文。`;
		const blocks = parseMarkdownBlocks(markdown);
		const paragraph = blocks.find((block) =>
			block.raw.includes('第一段正文')
		) as KnowledgeMarkdownBlock;

		const next = replaceMarkdownBlockRaw(blocks, paragraph.id, '第一段正文，已更新。\n');

		expect(next).toContain('# 标题');
		expect(next).toContain('第一段正文，已更新。');
		expect(next).toContain('第二段正文。');
	});

	it('accepts md, markdown and mdx files', () => {
		expect(isKnowledgeMarkdownFile('template.md')).toBe(true);
		expect(isKnowledgeMarkdownFile('template.markdown')).toBe(true);
		expect(isKnowledgeMarkdownFile('template.mdx')).toBe(true);
	});

	it('rejects non-markdown text files', () => {
		expect(isKnowledgeMarkdownFile('template.txt')).toBe(false);
		expect(isKnowledgeMarkdownFile('template.docx')).toBe(false);
	});
});
