"use client";

const previews = new Map<string, string>();

export function retainVideoPreview(token: string, url: string): void {
  const previous = previews.get(token);
  if (previous && previous !== url) URL.revokeObjectURL(previous);
  previews.set(token, url);
}

export function getVideoPreview(token: string): string | null {
  return previews.get(token) ?? null;
}

export function releaseVideoPreview(token: string): void {
  const url = previews.get(token);
  if (url) URL.revokeObjectURL(url);
  previews.delete(token);
}
