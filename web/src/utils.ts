export function isBlank(val: string | null | undefined): boolean {
  return val === "" || val === null || val === undefined;
}
