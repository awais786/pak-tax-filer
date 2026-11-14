import { onTestFinished, vi } from "vitest";

/**
 * Stand in for the browser's download (feature 008's PDFs): jsdom has no blob addresses and
 * can't follow a download link. Returns the downloads started, by file name.
 */
export function catchDownloads(): string[] {
  const saved: string[] = [];
  URL.createObjectURL = vi.fn(() => "blob:the-file");
  URL.revokeObjectURL = vi.fn();
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(function (this: HTMLAnchorElement) {
      saved.push(this.download);
    });
  onTestFinished(() => click.mockRestore());
  return saved;
}
