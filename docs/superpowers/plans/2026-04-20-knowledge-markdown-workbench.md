# 知识库 Markdown 工作台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把知识库中的 Markdown 文件查看器升级成连续文稿式工作台，支持块级原地编辑、表格结构化编辑和自动保存，同时保留非 Markdown 文件的现有行为。

**Architecture:** 继续复用现有知识库文件抽屉、Markdown 渲染组件和文件保存接口，但把 Markdown 文件的查看逻辑从 `KnowledgeBase.svelte` 中抽出成独立工作台组件。通过纯工具函数把 Markdown 文本拆成可编辑块、把表格文本转成结构化数据，再由工作台组件负责连续文稿纸面的组织、原地编辑、自动保存和状态反馈。

**Tech Stack:** Svelte 5、TypeScript、`marked`、现有 `$lib/apis/files` 接口、Tailwind/CSS、Vitest、Vite build

---

### 任务 1：先锁住 Markdown 块拆分与回写规则

**Files:**
- Create: `src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.ts`
- Create: `src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.test.ts`

- [ ] **Step 1: Write the failing block parsing tests**

```ts
import { describe, expect, it } from 'vitest';

import {
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
		const paragraph = blocks.find((block) => block.raw.includes('第一段正文')) as KnowledgeMarkdownBlock;

		const next = replaceMarkdownBlockRaw(blocks, paragraph.id, '第一段正文，已更新。\n');

		expect(next).toContain('# 标题');
		expect(next).toContain('第一段正文，已更新。');
		expect(next).toContain('第二段正文。');
	});
});
```

- [ ] **Step 2: Run the targeted frontend tests and confirm the helper is missing**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.test.ts`

Expected:
- `FAIL`
- Error points to missing `knowledgeMarkdownBlocks.ts` exports

- [ ] **Step 3: Implement the markdown block helper**

```ts
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
```

- [ ] **Step 4: Re-run the block helper tests**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.test.ts`

Expected:
- `PASS`
- Both parsing and replace tests are green

- [ ] **Step 5: Commit the helper foundation**

```bash
git add src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.ts src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.test.ts
git commit -m "test: cover markdown block parsing"
```

### 任务 2：锁住 Markdown 表格的结构化编辑数据模型

**Files:**
- Create: `src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.ts`
- Create: `src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.test.ts`

- [ ] **Step 1: Write the failing table conversion tests**

```ts
import { describe, expect, it } from 'vitest';

import { parseMarkdownTable, stringifyMarkdownTable } from './knowledgeMarkdownTables';

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
});
```

- [ ] **Step 2: Run the table helper tests and confirm failure**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.test.ts`

Expected:
- `FAIL`
- Missing `parseMarkdownTable` / `stringifyMarkdownTable`

- [ ] **Step 3: Implement the table conversion helper**

```ts
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
```

- [ ] **Step 4: Re-run the table helper tests**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.test.ts`

Expected:
- `PASS`
- Table parsing and stringifying tests succeed

- [ ] **Step 5: Commit the table foundation**

```bash
git add src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.ts src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.test.ts
git commit -m "test: cover markdown table conversion"
```

### 任务 3：抽出 Markdown 工作台壳层并接入知识库文件抽屉

**Files:**
- Create: `src/lib/components/workspace/Knowledge/KnowledgeFileWorkbench.svelte`
- Modify: `src/lib/components/workspace/Knowledge/KnowledgeBase.svelte`
- Test: `src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.test.ts`

- [ ] **Step 1: Write the failing markdown mode gate test**

```ts
import { describe, expect, it } from 'vitest';

import { isKnowledgeMarkdownFile } from './knowledgeMarkdownBlocks';

describe('isKnowledgeMarkdownFile', () => {
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
```

- [ ] **Step 2: Run the helper tests again and confirm the new gate test fails**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.test.ts`

Expected:
- `FAIL`
- Missing `isKnowledgeMarkdownFile`

- [ ] **Step 3: Extend the helper with file type detection**

```ts
const MARKDOWN_EXTS = new Set(['md', 'markdown', 'mdx']);

export const isKnowledgeMarkdownFile = (filename: string | null | undefined): boolean => {
	const ext = filename?.split('.').pop()?.toLowerCase() ?? '';
	return MARKDOWN_EXTS.has(ext);
};
```

- [ ] **Step 4: Create the workbench shell component**

```svelte
<script lang="ts">
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';

	export let fileId: string;
	export let fileName: string;
	export let content = '';
	export let saving = false;
	export let saveState: 'saved' | 'saving' | 'error' | 'dirty' = 'saved';
	export let writeAccess = false;
	export let onCopyMarkdown = () => {};
	export let onDownload = () => {};
</script>

<div class="knowledge-workbench-shell">
	<div class="knowledge-workbench-toolbar">
		<div class="knowledge-workbench-toolbar__title">{fileName}</div>
		<div class="knowledge-workbench-toolbar__status" data-state={saveState}>
			{saveState === 'saving' ? '保存中...' : saveState === 'error' ? '保存失败' : '已保存'}
		</div>
	</div>

	<div class="knowledge-workbench-canvas">
		<div class="knowledge-workbench-document">
			<Markdown id={`knowledge-file-preview-${fileId}`} content={content} />
		</div>
	</div>
</div>
```

- [ ] **Step 5: Route markdown files through the new shell and keep non-markdown fallback unchanged**

```svelte
{#if isKnowledgeMarkdownFile(selectedFile?.meta?.name)}
	<KnowledgeFileWorkbench
		fileId={selectedFile.id}
		fileName={selectedFile?.meta?.name ?? ''}
		content={selectedFileContent}
		saving={isSaving}
		saveState="saved"
		writeAccess={knowledge?.write_access ?? false}
	/>
{:else if selectedFileViewMode === 'preview'}
	<div class="w-full h-full overflow-y-auto px-3 py-2">
		...
	</div>
{:else}
	<textarea ... />
{/if}
```

- [ ] **Step 6: Run the helper tests and a full frontend build**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.test.ts`
Expected: `PASS`

Run: `npm run build`
Expected:
- Build succeeds
- No compile errors from the new `KnowledgeFileWorkbench.svelte`

- [ ] **Step 7: Commit the shell integration**

```bash
git add src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.ts src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.test.ts src/lib/components/workspace/Knowledge/KnowledgeFileWorkbench.svelte src/lib/components/workspace/Knowledge/KnowledgeBase.svelte
git commit -m "feat: add markdown knowledge workbench shell"
```

### 任务 4：把整篇 Markdown 变成块级渲染与原地编辑

**Files:**
- Create: `src/lib/components/workspace/Knowledge/KnowledgeMarkdownDocument.svelte`
- Create: `src/lib/components/workspace/Knowledge/KnowledgeMarkdownBlock.svelte`
- Create: `src/lib/components/workspace/Knowledge/knowledgeMarkdownEditorState.ts`
- Create: `src/lib/components/workspace/Knowledge/knowledgeMarkdownEditorState.test.ts`
- Modify: `src/lib/components/workspace/Knowledge/KnowledgeFileWorkbench.svelte`

- [ ] **Step 1: Write the failing save-state tests**

```ts
import { describe, expect, it } from 'vitest';

import { deriveSaveState, hasPendingMarkdownChanges } from './knowledgeMarkdownEditorState';

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
});
```

- [ ] **Step 2: Run the targeted editor-state tests and confirm failure**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownEditorState.test.ts`

Expected:
- `FAIL`
- Missing `knowledgeMarkdownEditorState.ts`

- [ ] **Step 3: Implement the save-state helper**

```ts
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
```

- [ ] **Step 4: Implement block-level document rendering**

```svelte
<!-- KnowledgeMarkdownDocument.svelte -->
<script lang="ts">
	import KnowledgeMarkdownBlock from './KnowledgeMarkdownBlock.svelte';
	import type { KnowledgeMarkdownBlock as Block } from './knowledgeMarkdownBlocks';

	export let blocks: Block[] = [];
	export let activeBlockId: string | null = null;
	export let writeAccess = false;
	export let onEditBlock = (_blockId: string) => {};
	export let onCommitBlock = (_blockId: string, _nextRaw: string) => {};
</script>

<div class="knowledge-workbench-document">
	{#each blocks as block (block.id)}
		<KnowledgeMarkdownBlock
			{block}
			active={activeBlockId === block.id}
			{writeAccess}
			onEdit={() => onEditBlock(block.id)}
			onCommit={(nextRaw) => onCommitBlock(block.id, nextRaw)}
		/>
	{/each}
</div>
```

```svelte
<!-- KnowledgeMarkdownBlock.svelte -->
<script lang="ts">
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import type { KnowledgeMarkdownBlock } from './knowledgeMarkdownBlocks';

	export let block: KnowledgeMarkdownBlock;
	export let active = false;
	export let writeAccess = false;
	export let onEdit = () => {};
	export let onCommit = (_nextRaw: string) => {};

	let draft = '';

	$: if (active) {
		draft = block.raw;
	}
</script>

<section class="knowledge-workbench-block" data-kind={block.kind}>
	{#if active && writeAccess && block.kind !== 'table'}
		<textarea
			class="knowledge-workbench-block__editor"
			bind:value={draft}
			on:blur={() => onCommit(draft)}
		/>
	{:else}
		<button type="button" class="knowledge-workbench-block__surface" on:click={onEdit}>
			<Markdown id={`knowledge-block-${block.id}`} content={block.raw} />
		</button>
	{/if}
</section>
```

- [ ] **Step 5: Wire the workbench shell to parsed blocks and inline edit commits**

```svelte
	import { deriveSaveState, hasPendingMarkdownChanges } from './knowledgeMarkdownEditorState';
	import { parseMarkdownBlocks, replaceMarkdownBlockRaw } from './knowledgeMarkdownBlocks';
	import KnowledgeMarkdownDocument from './KnowledgeMarkdownDocument.svelte';

	let activeBlockId: string | null = null;
	let draftMarkdown = content;
	let lastSavedMarkdown = content;
	let saveError: string | null = null;

	$: blocks = parseMarkdownBlocks(draftMarkdown);
	$: dirty = hasPendingMarkdownChanges(draftMarkdown, lastSavedMarkdown);
	$: saveState = deriveSaveState({ saving, error: saveError, dirty });
```

- [ ] **Step 6: Run the editor-state tests and a build smoke test**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownEditorState.test.ts`
Expected: `PASS`

Run: `npm run build`
Expected:
- Build succeeds
- Markdown file drawer compiles with block rendering

- [ ] **Step 7: Commit the inline editing foundation**

```bash
git add src/lib/components/workspace/Knowledge/KnowledgeMarkdownDocument.svelte src/lib/components/workspace/Knowledge/KnowledgeMarkdownBlock.svelte src/lib/components/workspace/Knowledge/knowledgeMarkdownEditorState.ts src/lib/components/workspace/Knowledge/knowledgeMarkdownEditorState.test.ts src/lib/components/workspace/Knowledge/KnowledgeFileWorkbench.svelte
git commit -m "feat: add inline markdown block editing"
```

### 任务 5：给表格块加结构化编辑和行操作

**Files:**
- Create: `src/lib/components/workspace/Knowledge/KnowledgeMarkdownTableEditor.svelte`
- Modify: `src/lib/components/workspace/Knowledge/KnowledgeMarkdownBlock.svelte`
- Modify: `src/lib/components/workspace/Knowledge/KnowledgeFileWorkbench.svelte`
- Test: `src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.test.ts`

- [ ] **Step 1: Extend the table tests with row operations**

```ts
import { describe, expect, it } from 'vitest';

import {
	appendMarkdownTableRow,
	removeMarkdownTableRow,
	duplicateMarkdownTableRow
} from './knowledgeMarkdownTables';

describe('knowledgeMarkdownTables row operations', () => {
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
});
```

- [ ] **Step 2: Run the table tests and confirm the row helpers are still missing**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.test.ts`

Expected:
- `FAIL`
- Missing row operation helpers

- [ ] **Step 3: Add the row operation helpers**

```ts
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
```

- [ ] **Step 4: Implement the structured table editor component**

```svelte
<script lang="ts">
	import type { MarkdownTableData } from './knowledgeMarkdownTables';

	export let table: MarkdownTableData;
	export let onInput = (_table: MarkdownTableData) => {};
	export let onAddRow = () => {};
	export let onDuplicateRow = (_rowIndex: number) => {};
	export let onRemoveRow = (_rowIndex: number) => {};
</script>

<div class="knowledge-workbench-table-editor">
	<table class="knowledge-workbench-table-editor__table">
		<thead>
			<tr>
				{#each table.headers as header}
					<th>{header}</th>
				{/each}
				<th class="w-24">操作</th>
			</tr>
		</thead>
		<tbody>
			{#each table.rows as row, rowIndex}
				<tr>
					{#each row as cell, cellIndex}
						<td>
							<input
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
						<button type="button" on:click={() => onDuplicateRow(rowIndex)}>复制</button>
						<button type="button" on:click={() => onRemoveRow(rowIndex)}>删除</button>
					</td>
				</tr>
			{/each}
		</tbody>
	</table>

	<button type="button" class="knowledge-workbench-table-editor__add" on:click={onAddRow}>
		新增一行
	</button>
</div>
```

- [ ] **Step 5: Route table blocks to the structured editor and save them back as markdown**

```svelte
	import {
		parseMarkdownTable,
		stringifyMarkdownTable,
		appendMarkdownTableRow,
		duplicateMarkdownTableRow,
		removeMarkdownTableRow
	} from './knowledgeMarkdownTables';
	import KnowledgeMarkdownTableEditor from './KnowledgeMarkdownTableEditor.svelte';

	$: tableDraft = block.kind === 'table' ? parseMarkdownTable(block.raw) : null;

	{#if active && writeAccess && block.kind === 'table' && tableDraft}
		<KnowledgeMarkdownTableEditor
			table={tableDraft}
			onInput={(nextTable) => {
				tableDraft = nextTable;
				onCommit(stringifyMarkdownTable(nextTable));
			}}
			onAddRow={() => {
				tableDraft = appendMarkdownTableRow(tableDraft);
				onCommit(stringifyMarkdownTable(tableDraft));
			}}
			onDuplicateRow={(rowIndex) => {
				tableDraft = duplicateMarkdownTableRow(tableDraft, rowIndex);
				onCommit(stringifyMarkdownTable(tableDraft));
			}}
			onRemoveRow={(rowIndex) => {
				tableDraft = removeMarkdownTableRow(tableDraft, rowIndex);
				onCommit(stringifyMarkdownTable(tableDraft));
			}}
		/>
	{/if}
```

- [ ] **Step 6: Re-run the table tests and a full build**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.test.ts`
Expected: `PASS`

Run: `npm run build`
Expected:
- Build succeeds
- Table editor compiles and can be bundled

- [ ] **Step 7: Commit the table editing feature**

```bash
git add src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.ts src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.test.ts src/lib/components/workspace/Knowledge/KnowledgeMarkdownTableEditor.svelte src/lib/components/workspace/Knowledge/KnowledgeMarkdownBlock.svelte src/lib/components/workspace/Knowledge/KnowledgeFileWorkbench.svelte
git commit -m "feat: add structured markdown table editing"
```

### 任务 6：补足自动保存、离页保护和最终视觉样式

**Files:**
- Modify: `src/lib/components/workspace/Knowledge/KnowledgeFileWorkbench.svelte`
- Modify: `src/lib/components/workspace/Knowledge/KnowledgeMarkdownDocument.svelte`
- Modify: `src/lib/components/workspace/Knowledge/KnowledgeMarkdownBlock.svelte`
- Modify: `src/app.css`

- [ ] **Step 1: Add debounced autosave and flush-on-blur behavior**

```ts
let autosaveTimer: ReturnType<typeof setTimeout> | null = null;

const queueAutosave = () => {
	if (!dirty || saving) return;
	if (autosaveTimer) clearTimeout(autosaveTimer);
	autosaveTimer = setTimeout(() => {
		void persistMarkdown();
	}, 1000);
};

const persistMarkdown = async () => {
	saveError = null;
	try {
		await onSave(draftMarkdown);
		lastSavedMarkdown = draftMarkdown;
		activeBlockId = null;
	} catch (error) {
		saveError = `${error}`;
	}
};
```

- [ ] **Step 2: Add unload protection for unsaved markdown changes**

```ts
import { onMount } from 'svelte';

onMount(() => {
	const handleBeforeUnload = (event: BeforeUnloadEvent) => {
		if (!dirty) return;
		event.preventDefault();
		event.returnValue = '';
	};

	window.addEventListener('beforeunload', handleBeforeUnload);
	return () => {
		window.removeEventListener('beforeunload', handleBeforeUnload);
	};
});
```

- [ ] **Step 3: Add the document-canvas and ledger-table styles**

```css
.knowledge-workbench-shell {
	@apply flex h-full min-h-0 flex-col bg-gray-50/70 dark:bg-gray-900/40;
}

.knowledge-workbench-toolbar {
	@apply sticky top-0 z-10 flex items-center justify-between gap-4 border-b border-gray-200/70 bg-white/90 px-5 py-3 backdrop-blur dark:border-gray-800 dark:bg-gray-900/90;
}

.knowledge-workbench-canvas {
	@apply min-h-0 flex-1 overflow-y-auto px-6 py-6;
}

.knowledge-workbench-document {
	@apply mx-auto flex w-full max-w-5xl flex-col gap-5;
}

.knowledge-workbench-block[data-kind='table'] {
	@apply max-w-none overflow-x-auto rounded-2xl border border-gray-200 bg-white p-4 shadow-sm dark:border-gray-800 dark:bg-gray-900;
}

.knowledge-workbench-block__surface {
	@apply block w-full rounded-2xl px-6 py-5 text-left transition hover:bg-white hover:shadow-sm dark:hover:bg-gray-900/70;
}

.knowledge-workbench-block__editor {
	@apply min-h-[160px] w-full rounded-2xl border border-blue-200 bg-white px-5 py-4 font-mono text-sm outline-none ring-0 dark:border-blue-900 dark:bg-gray-950;
}
```

- [ ] **Step 4: Run the full frontend verification**

Run: `npm run test:frontend -- --run src/lib/components/workspace/Knowledge/knowledgeMarkdownBlocks.test.ts src/lib/components/workspace/Knowledge/knowledgeMarkdownTables.test.ts src/lib/components/workspace/Knowledge/knowledgeMarkdownEditorState.test.ts`
Expected:
- All targeted Vitest files pass

Run: `npm run build`
Expected:
- Build succeeds
- No Svelte compile errors

- [ ] **Step 5: Review the final diff and commit**

Run: `git diff -- src/lib/components/workspace/Knowledge src/app.css`
Expected:
- Diff is limited to the new workbench components, helper files, tests, and related CSS

```bash
git add src/lib/components/workspace/Knowledge src/app.css
git commit -m "feat: redesign markdown knowledge workbench"
```

## 自检

- Spec coverage:
  - 居中文档画布与顶部工具条：任务 3、任务 6
  - Markdown 块级原地编辑：任务 1、任务 4
  - 表格结构化编辑：任务 2、任务 5
  - 自动保存与保存状态：任务 4、任务 6
  - 仅对 Markdown 文件启用：任务 3
  - 非 Markdown 文件保留旧行为：任务 3
- Placeholder scan:
  - 计划里没有 `TODO`、`TBD`、`后续补充`
  - 每个任务都列了文件、命令和预期结果
- Type consistency:
  - 统一使用 `KnowledgeMarkdownBlock`、`parseMarkdownBlocks()`、`replaceMarkdownBlockRaw()`
  - 统一使用 `MarkdownTableData`、`parseMarkdownTable()`、`stringifyMarkdownTable()`
  - 统一使用 `deriveSaveState()`、`hasPendingMarkdownChanges()`

## 执行交接

Plan complete and saved to `docs/superpowers/plans/2026-04-20-knowledge-markdown-workbench.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
