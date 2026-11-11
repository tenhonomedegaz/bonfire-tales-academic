export function getRandomInteger(min: number, max: number): number {
  const minValue = Math.ceil(min);
  const maxValue = Math.floor(max);
  // The maximum is inclusive and the minimum is inclusive
  return Math.floor(Math.random() * (maxValue - minValue + 1) + minValue);
}
