export function isValidDateFormat(value: string): boolean {
  const regExp = /^\d{1,2}\/\d{1,2}\/\d{4}$/;
  return regExp.test(value);
}
