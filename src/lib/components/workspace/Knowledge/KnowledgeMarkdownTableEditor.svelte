<script lang="ts">
	import { onMount, tick } from 'svelte';
	import { deriveTableHoverState } from './knowledgeMarkdownTableEditorState';

	import {
		appendMarkdownTableColumn,
		appendMarkdownTableRow,
		duplicateMarkdownTableRow,
		removeMarkdownTableColumn,
		removeMarkdownTableRow,
		updateMarkdownTableCell,
		updateMarkdownTableHeader,
		type MarkdownTableData
	} from './knowledgeMarkdownTables';

	export let table: MarkdownTableData;
	export let onInput = (_table: MarkdownTableData) => {};

	let editorElement: HTMLDivElement | null = null;
	let hoveredRowIndex: number | null = null;
	let hoveredColumnIndex: number | null = null;

	const updateTable = (nextTable: MarkdownTableData) => {
		onInput(nextTable);
	};

	const setHoveredCell = (rowIndex: number | null, columnIndex: number | null) => {
		hoveredRowIndex = rowIndex;
		hoveredColumnIndex = columnIndex;
	};

	const getHoverState = (rowIndex: number, columnIndex: number) =>
		deriveTableHoverState({
			hoveredRowIndex,
			hoveredColumnIndex,
			rowIndex,
			columnIndex
		});

	onMount(() => {
		void tick().then(() => {
			editorElement?.querySelector<HTMLInputElement>('input')?.focus();
		});
	});
</script>

<div class="knowledge-workbench-table-editor overflow-x-auto" bind:this={editorElement}>
	<div class="knowledge-workbench-table-editor__bar">
		<div class="knowledge-workbench-table-editor__summary">
			<span class="knowledge-workbench-table-editor__summary-dot"></span>
			<span class="knowledge-workbench-table-editor__summary-text">表格编辑</span>
			<span class="knowledge-workbench-table-editor__summary-meta">
				{table.rows.length} 行 · {table.headers.length} 列
			</span>
		</div>

		<div class="knowledge-workbench-table-editor__toolbar">
			<button
				type="button"
				class="knowledge-workbench-table-editor__tool"
				aria-label="新增行"
				title="新增行"
				on:click={() => updateTable(appendMarkdownTableRow(table))}
			>
				<svg viewBox="0 0 20 20" aria-hidden="true">
					<path d="M4 5.5h12M4 10h12M4 14.5h12" />
					<path d="M10 7.7v4.6M7.7 10h4.6" />
				</svg>
			</button>
			<button
				type="button"
				class="knowledge-workbench-table-editor__tool"
				aria-label="新增列"
				title="新增列"
				on:click={() => updateTable(appendMarkdownTableColumn(table))}
			>
				<svg viewBox="0 0 20 20" aria-hidden="true">
					<path d="M5.5 4v12M10 4v12M14.5 4v12" />
					<path d="M7.7 10h4.6M10 7.7v4.6" />
				</svg>
			</button>
		</div>
	</div>

	<table
		class="knowledge-workbench-table-editor__table min-w-full border-separate border-spacing-0"
		on:mouseleave={() => setHoveredCell(null, null)}
	>
		<thead>
			<tr>
				{#each table.headers as header, columnIndex}
					{@const headerHover = getHoverState(-1, columnIndex)}
					<th
						data-active-column={headerHover.columnActive ? 'true' : undefined}
						on:mouseenter={() => setHoveredCell(null, columnIndex)}
					>
						<div class="knowledge-workbench-table-editor__header-cell">
							<input
								class="knowledge-workbench-table-editor__input knowledge-workbench-table-editor__input--header"
								data-active-column={headerHover.columnActive ? 'true' : undefined}
								aria-label={`第 ${columnIndex + 1} 列表头`}
								value={header}
								placeholder={`列 ${columnIndex + 1}`}
								on:focus={() => setHoveredCell(null, columnIndex)}
								on:input={(event) =>
									updateTable(
										updateMarkdownTableHeader(
											table,
											columnIndex,
											(event.currentTarget as HTMLInputElement).value
										)
									)}
							/>
							<button
								type="button"
								class="knowledge-workbench-table-editor__icon-action knowledge-workbench-table-editor__icon-action--column"
								aria-label={`删除第 ${columnIndex + 1} 列`}
								title="删除列"
								disabled={table.headers.length <= 1}
								on:click={() => updateTable(removeMarkdownTableColumn(table, columnIndex))}
							>
								<svg viewBox="0 0 20 20" aria-hidden="true">
									<path d="M5 10h10" />
								</svg>
							</button>
						</div>
					</th>
				{/each}
				<th class="knowledge-workbench-table-editor__operation-heading">
					<span class="sr-only">行操作</span>
				</th>
			</tr>
		</thead>
		<tbody>
			{#each table.rows as row, rowIndex}
				<tr
					data-active-row={hoveredRowIndex === rowIndex ? 'true' : undefined}
					on:mouseenter={() => setHoveredCell(rowIndex, hoveredColumnIndex)}
				>
					{#each row as cell, cellIndex}
						{@const hoverState = getHoverState(rowIndex, cellIndex)}
						<td
							data-active-row={hoverState.rowActive ? 'true' : undefined}
							data-active-column={hoverState.columnActive ? 'true' : undefined}
							data-active-cell={hoverState.cellActive ? 'true' : undefined}
						>
							<input
								class="knowledge-workbench-table-editor__input"
								data-active-row={hoverState.rowActive ? 'true' : undefined}
								data-active-column={hoverState.columnActive ? 'true' : undefined}
								data-active-cell={hoverState.cellActive ? 'true' : undefined}
								aria-label={`第 ${rowIndex + 1} 行第 ${cellIndex + 1} 列`}
								value={cell}
								on:mouseenter={() => setHoveredCell(rowIndex, cellIndex)}
								on:focus={() => setHoveredCell(rowIndex, cellIndex)}
								on:input={(event) =>
									updateTable(
										updateMarkdownTableCell(
											table,
											rowIndex,
											cellIndex,
											(event.currentTarget as HTMLInputElement).value
										)
									)}
							/>
						</td>
					{/each}
					<td
						class="knowledge-workbench-table-editor__actions"
						data-active-row={hoveredRowIndex === rowIndex ? 'true' : undefined}
					>
						<div class="knowledge-workbench-table-editor__row-actions">
							<button
								type="button"
								class="knowledge-workbench-table-editor__icon-action knowledge-workbench-table-editor__icon-action--row"
								aria-label={`复制第 ${rowIndex + 1} 行`}
								title="复制行"
								on:click={() => updateTable(duplicateMarkdownTableRow(table, rowIndex))}
							>
								<svg viewBox="0 0 20 20" aria-hidden="true">
									<path d="M7 7.5h7.5v7.5H7z" />
									<path d="M5.5 12.5H4V4h8.5v1.5" />
								</svg>
							</button>
							<button
								type="button"
								class="knowledge-workbench-table-editor__icon-action knowledge-workbench-table-editor__icon-action--row knowledge-workbench-table-editor__icon-action--danger"
								aria-label={`删除第 ${rowIndex + 1} 行`}
								title="删除行"
								on:click={() => updateTable(removeMarkdownTableRow(table, rowIndex))}
							>
								<svg viewBox="0 0 20 20" aria-hidden="true">
									<path d="M6.5 7h7" />
									<path d="M8 7V5.5h4V7" />
									<path d="M7.3 8.7 8 15h4l.7-6.3" />
								</svg>
							</button>
						</div>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>
