export type MarkdownTableData = {
	headers: string[];
	rows: string[][];
};

const splitCells = (line: string): string[] =>
	line
		.trim()
		.replace(/^\|/, '')
		.replace(/\|$/, '')
		.split('|')
		.map((cell) => cell.trim());

export const parseMarkdownTable = (raw: string): MarkdownTableData => {
	const lines = raw
		.split('\n')
		.map((line) => line.trim())
		.filter(Boolean);

	if (lines.length < 2) {
		return { headers: [], rows: [] };
	}

	const headers = splitCells(lines[0]);
	const bodyLines = lines.slice(2);

	return {
		headers,
		rows: bodyLines.map((line) => splitCells(line))
	};
};

export const stringifyMarkdownTable = ({ headers, rows }: MarkdownTableData): string => {
	const normalize = (cells: string[]) => `| ${cells.map((cell) => cell.trim()).join(' | ')} |`;
	const divider = `| ${headers.map(() => '---').join(' | ')} |`;

	return [normalize(headers), divider, ...rows.map(normalize), ''].join('\n');
};

export const appendMarkdownTableRow = (table: MarkdownTableData): MarkdownTableData => ({
	...table,
	rows: [...table.rows, Array.from({ length: table.headers.length }, () => '')]
});

export const duplicateMarkdownTableRow = (
	table: MarkdownTableData,
	rowIndex: number
): MarkdownTableData => ({
	...table,
	rows: [
		...table.rows.slice(0, rowIndex + 1),
		[...table.rows[rowIndex]],
		...table.rows.slice(rowIndex + 1)
	]
});

export const removeMarkdownTableRow = (
	table: MarkdownTableData,
	rowIndex: number
): MarkdownTableData => ({
	...table,
	rows: table.rows.filter((_, index) => index !== rowIndex)
});
