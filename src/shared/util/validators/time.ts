export function isValidTimeFormat(value: string): boolean {
  const regExp = /^\d{1,2}:\d{1,2}$/;
  return regExp.test(value);
}
