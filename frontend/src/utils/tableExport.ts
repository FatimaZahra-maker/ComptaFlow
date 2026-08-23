export interface ExportColumn<T> {
  header: string;
  value: (row: T) => string | number | null | undefined;
}

function safeCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

function escapeCsv(value: unknown): string {
  const text = safeCell(value).replaceAll('"', '""');
  return `"${text}"`;
}

function escapeXml(value: unknown): string {
  return safeCell(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function downloadBlob(content: BlobPart, mimeType: string, filename: string): void {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function exportRowsToCsv<T>(
  filename: string,
  rows: T[],
  columns: ExportColumn<T>[],
): void {
  const lines = [
    columns.map((column) => escapeCsv(column.header)).join(";"),
    ...rows.map((row) =>
      columns.map((column) => escapeCsv(column.value(row))).join(";"),
    ),
  ];

  downloadBlob(
    `\uFEFF${lines.join("\r\n")}`,
    "text/csv;charset=utf-8",
    filename.endsWith(".csv") ? filename : `${filename}.csv`,
  );
}

/**
 * Produit un classeur SpreadsheetML 2003 réellement ouvert par Excel,
 * sans ajouter de dépendance npm et sans toucher au backend.
 */
export function exportRowsToExcel<T>(
  filename: string,
  worksheetName: string,
  rows: T[],
  columns: ExportColumn<T>[],
): void {
  const header = columns
    .map((column) => `<Cell><Data ss:Type="String">${escapeXml(column.header)}</Data></Cell>`)
    .join("");

  const body = rows
    .map((row) => {
      const cells = columns
        .map((column) => {
          const value = column.value(row);
          const isNumber = typeof value === "number" && Number.isFinite(value);
          return `<Cell><Data ss:Type="${isNumber ? "Number" : "String"}">${escapeXml(value)}</Data></Cell>`;
        })
        .join("");
      return `<Row>${cells}</Row>`;
    })
    .join("");

  const xml = `<?xml version="1.0"?>
<?mso-application progid="Excel.Sheet"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
 <Worksheet ss:Name="${escapeXml(worksheetName.slice(0, 31))}">
  <Table>
   <Row>${header}</Row>
   ${body}
  </Table>
 </Worksheet>
</Workbook>`;

  downloadBlob(
    `\uFEFF${xml}`,
    "application/vnd.ms-excel;charset=utf-8",
    filename.endsWith(".xls") ? filename : `${filename}.xls`,
  );
}