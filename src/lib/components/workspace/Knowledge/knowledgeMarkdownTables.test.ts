import { describe, expect, it } from 'vitest';

import {
	appendMarkdownTableRow,
	appendMarkdownTableColumn,
	duplicateMarkdownTableRow,
	parseMarkdownTable,
	removeMarkdownTableColumn,
	removeMarkdownTableRow,
	stringifyMarkdownTable,
	updateMarkdownTableCell,
	updateMarkdownTableHeader
} from './knowledgeMarkdownTables';

describe('knowledgeMarkdownTables', () => {
	it('parses markdown table into headers and rows', () => {
		const table = `| 原始商品名称 | 标准规格 |
| --- | --- |
| A4打印纸 | A4 / 70g |
| 螺栓 | M8*40 |
`;

		const parsed = parseMarkdownTable(table);

		expect(parsed.headers).toEqual(['原始商品名称', '标准规格']);
		expect(parsed.rows).toEqual([
			['A4打印纸', 'A4 / 70g'],
			['螺栓', 'M8*40']
		]);
	});

	it('stringifies edited rows back to markdown table', () => {
		const markdown = stringifyMarkdownTable({
			headers: ['字段', '内容'],
			rows: [
				['分类', '办公耗材'],
				['维护人', '采购工程B']
			]
		});

		expect(markdown).toContain('| 字段 | 内容 |');
		expect(markdown).toContain('| 分类 | 办公耗材 |');
		expect(markdown).toContain('| 维护人 | 采购工程B |');
	});

	it('appends an empty row matching the header count', () => {
		expect(
			appendMarkdownTableRow({
				headers: ['字段', '内容'],
				rows: [['分类', '办公耗材']]
			}).rows
		).toEqual([
			['分类', '办公耗材'],
			['', '']
		]);
	});

	it('duplicates and removes the targeted row', () => {
		const duplicated = duplicateMarkdownTableRow(
			{
				headers: ['字段', '内容'],
				rows: [['分类', '办公耗材']]
			},
			0
		);

		expect(duplicated.rows).toEqual([
			['分类', '办公耗材'],
			['分类', '办公耗材']
		]);

		expect(removeMarkdownTableRow(duplicated, 0).rows).toEqual([['分类', '办公耗材']]);
	});

	it('edits headers and cells without mutating the original table', () => {
		const table = {
			headers: ['字段', '内容'],
			rows: [['分类', '办公耗材']]
		};

		const withHeader = updateMarkdownTableHeader(table, 0, '属性');
		const withCell = updateMarkdownTableCell(table, 0, 1, '办公用品');

		expect(withHeader.headers).toEqual(['属性', '内容']);
		expect(withCell.rows).toEqual([['分类', '办公用品']]);
		expect(table).toEqual({
			headers: ['字段', '内容'],
			rows: [['分类', '办公耗材']]
		});
	});

	it('appends and removes columns across headers and rows', () => {
		const table = {
			headers: ['字段', '内容'],
			rows: [
				['分类', '办公耗材'],
				['维护人', '采购工程B']
			]
		};

		const appended = appendMarkdownTableColumn(table);

		expect(appended.headers).toEqual(['字段', '内容', '']);
		expect(appended.rows).toEqual([
			['分类', '办公耗材', ''],
			['维护人', '采购工程B', '']
		]);

		expect(removeMarkdownTableColumn(appended, 1)).toEqual({
			headers: ['字段', ''],
			rows: [
				['分类', ''],
				['维护人', '']
			]
		});
	});
});
