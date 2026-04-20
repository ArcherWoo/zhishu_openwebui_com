<script lang="ts">
	import type { MarkdownTableData } from './knowledgeMarkdownTables';

	export let table: MarkdownTableData;
	export let onInput = (_table: MarkdownTableData) => {};
	export let onAddRow = () => {};
	export let onDuplicateRow = (_rowIndex: number) => {};
	export let onRemoveRow = (_rowIndex: number) => {};
</script>

<div class="knowledge-workbench-table-editor overflow-x-auto">
	<table class="knowledge-workbench-table-editor__table min-w-full border-separate border-spacing-0">
		<thead>
			<tr>
				{#each table.headers as header}
					<th>{header}</th>
				{/each}
				<th>操作</th>
			</tr>
		</thead>
		<tbody>
			{#each table.rows as row, rowIndex}
				<tr>
					{#each row as cell, cellIndex}
						<td>
							<input
								class="knowledge-workbench-table-editor__input"
								value={cell}
								on:input={(event) =>
									onInput({
										...table,
										rows: table.rows.map((currentRow, currentIndex) =>
											currentIndex === rowIndex
												? currentRow.map((currentCell, currentCellIndex) =>
														currentCellIndex === cellIndex
															? (event.currentTarget as HTMLInputElement).value
															: currentCell
												  )
												: currentRow
										)
									})}
							/>
						</td>
					{/each}
					<td class="knowledge-workbench-table-editor__actions">
						<div class="flex flex-wrap gap-2">
							<button
								type="button"
								class="knowledge-workbench-table-editor__action"
								on:click={() => onDuplicateRow(rowIndex)}
							>
								复制
							</button>
							<button
								type="button"
								class="knowledge-workbench-table-editor__action knowledge-workbench-table-editor__action--danger"
								on:click={() => onRemoveRow(rowIndex)}
							>
								删除
							</button>
						</div>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>

	<button
		type="button"
		class="knowledge-workbench-table-editor__add"
		on:click={onAddRow}
	>
		新增一行
	</button>
</div>
