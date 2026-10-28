/** Mirrors EstimatingParams' guide default and accepted range. */
export const DEFAULT_WALL_HEIGHT_M = 2.7;
export const MAX_WALL_HEIGHT_M = 10;

export function parseWallHeight(value: string): number | null {
  if (!value.trim()) return null;
  const height = Number(value);
  return Number.isFinite(height) && height > 0 && height <= MAX_WALL_HEIGHT_M ? height : null;
}
