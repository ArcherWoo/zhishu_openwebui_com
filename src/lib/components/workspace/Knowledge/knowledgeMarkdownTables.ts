export type MarkdownTableData = {
	headers: string[];
	rows: string[][];
};

const normalizeRow = (row: string[], columnCount: number): string[] =>
	Array.from({ length: columnCount }, (_, index) => row[index] ?? '');

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
		rows: bodyLines.map((line) => normalizeRow(splitCells(line), headers.length))
	};
};

export const stringifyMarkdownTable = ({ headers, rows }: MarkdownTableData): string => {
	const normalize = (cells: string[]) => `| ${cells.map((cell) => cell.trim()).join(' | ')} |`;
	const divider = `| ${headers.map(() => '---').join(' | ')} |`;

	return [
		normalize(headers),
		divider,
		...rows.map((row) => normalize(normalizeRow(row, headers.length))),
		''
	].join('\n');
};

export const updateMarkdownTableHeader = (
	table: MarkdownTableData,
	columnIndex: number,
	value: string
): MarkdownTableData => ({
	...table,
	headers: table.headers.map((header, index) => (index === columnIndex ? value : header))
});

export const updateMarkdownTableCell = (
	table: MarkdownTableData,
	rowIndex: number,
	cellIndex: number,
	value: string
): MarkdownTableData => ({
	...table,
	rows: table.rows.map((row, index) =>
		index === rowIndex
			? normalizeRow(row, table.headers.length).map((cell, currentCellIndex) =>
					currentCellIndex === cellIndex ? value : cell
				)
			: normalizeRow(row, table.headers.length)
	)
});

export const appendMarkdownTableRow = (table: MarkdownTableData): MarkdownTableData => ({
	...table,
	rows: [...table.rows, Array.from({ length: table.headers.length }, () => '')]
});

export const appendMarkdownTableColumn = (table: MarkdownTableData): MarkdownTableData => ({
	headers: [...table.headers, ''],
	rows: table.rows.map((row) => [...normalizeRow(row, table.headers.length), ''])
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

export const removeMarkdownTableColumn = (
	table: MarkdownTableData,
	columnIndex: number
): MarkdownTableData => {
	if (table.headers.length <= 1) {
		return table;
	}

	return {
		headers: table.headers.filter((_, index) => index !== columnIndex),
		rows: table.rows.map((row) =>
			normalizeRow(row, table.headers.length).filter((_, index) => index !== columnIndex)
		)
	};
};
