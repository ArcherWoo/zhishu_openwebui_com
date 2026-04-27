export const deriveTableHoverState = ({
	hoveredRowIndex,
	hoveredColumnIndex,
	rowIndex,
	columnIndex
}: {
	hoveredRowIndex: number | null;
	hoveredColumnIndex: number | null;
	rowIndex: number;
	columnIndex: number;
}): {
	rowActive: boolean;
	columnActive: boolean;
	cellActive: boolean;
} => {
	const rowActive = hoveredRowIndex === rowIndex;
	const columnActive = hoveredColumnIndex === columnIndex;

	return {
		rowActive,
		columnActive,
		cellActive: rowActive || columnActive
	};
};
