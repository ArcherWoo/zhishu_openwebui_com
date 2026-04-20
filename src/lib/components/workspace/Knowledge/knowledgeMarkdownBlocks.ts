import { marked, type TokensList } from 'marked';

export type KnowledgeMarkdownBlockKind =
	| 'heading'
	| 'paragraph'
	| 'list'
	| 'blockquote'
	| 'code'
	| 'table'
	| 'html'
	| 'hr'
	| 'other';

export type KnowledgeMarkdownBlock = {
	id: string;
	kind: KnowledgeMarkdownBlockKind;
	raw: string;
	index: number;
};

const MARKDOWN_EXTS = new Set(['md', 'markdown', 'mdx']);

const kindFromToken = (token: TokensList[number]): KnowledgeMarkdownBlockKind => {
	switch (token.type) {
		case 'heading':
		case 'paragraph':
		case 'list':
		case 'blockquote':
		case 'code':
		case 'table':
		case 'html':
		case 'hr':
			return token.type;
		default:
			return 'other';
	}
};

export const parseMarkdownBlocks = (content: string): KnowledgeMarkdownBlock[] => {
	const tokens = marked.lexer(content, { gfm: true, breaks: true });

	return tokens
		.filter((token) => token.type !== 'space')
		.map((token, index) => ({
			id: `${token.type}-${index}`,
			kind: kindFromToken(token),
			raw: token.raw ?? '',
			index
		}))
		.filter((block) => block.raw.trim().length > 0);
};

export const replaceMarkdownBlockRaw = (
	blocks: KnowledgeMarkdownBlock[],
	blockId: string,
	nextRaw: string
): string => {
	return blocks.map((block) => (block.id === blockId ? nextRaw : block.raw)).join('');
};

export const isKnowledgeMarkdownFile = (filename: string | null | undefined): boolean => {
	const ext = filename?.split('.').pop()?.toLowerCase() ?? '';
	return MARKDOWN_EXTS.has(ext);
};
