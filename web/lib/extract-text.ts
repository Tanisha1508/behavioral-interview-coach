/** Extract plain text from an uploaded document in the browser. The agent
 * consumes plain text, so .md and .txt pass through as-is and PDFs go
 * through pdf.js locally; nothing is uploaded to any server. */
export async function extractText(file: File): Promise<string> {
  if (file.name.toLowerCase().endsWith('.pdf')) {
    const pdfjs = await import('pdfjs-dist');
    pdfjs.GlobalWorkerOptions.workerSrc = new URL(
      'pdfjs-dist/build/pdf.worker.min.mjs',
      import.meta.url
    ).toString();
    const doc = await pdfjs.getDocument({ data: await file.arrayBuffer() }).promise;
    const pages: string[] = [];
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i);
      const content = await page.getTextContent();
      pages.push(
        content.items
          .map((item) => ('str' in item ? item.str : ''))
          .join(' ')
          .replace(/\s+/g, ' ')
          .trim()
      );
    }
    return pages.join('\n\n');
  }
  return file.text();
}
