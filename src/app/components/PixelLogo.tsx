// Dot-matrix wordmark. Each letter is a 5 x 7 grid of dots.
// The system name is ARCE; the older "TRACE" letters are kept so either word still renders.
const PIXEL: Record<string, number[][]> = {
  T: [[1,1,1,1,1],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0]],
  R: [[1,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[1,1,1,1,0],[1,0,1,0,0],[1,0,0,1,0],[1,0,0,0,1]],
  A: [[0,0,1,0,0],[0,1,0,1,0],[1,0,0,0,1],[1,1,1,1,1],[1,0,0,0,1],[1,0,0,0,1],[1,0,0,0,1]],
  C: [[0,1,1,1,0],[1,0,0,0,1],[1,0,0,0,0],[1,0,0,0,0],[1,0,0,0,0],[1,0,0,0,1],[0,1,1,1,0]],
  E: [[1,1,1,1,1],[1,0,0,0,0],[1,0,0,0,0],[1,1,1,1,0],[1,0,0,0,0],[1,0,0,0,0],[1,1,1,1,1]],
};

export function PixelLogo({
  text = "ARCE",
  dotSize = 5,
  gap = 3,
  letterGap = 12,
  color = "white",
  round = false,
}: {
  text?: string;
  dotSize?: number;
  gap?: number;
  letterGap?: number;
  color?: string;
  /** Draw round dots instead of small squares. */
  round?: boolean;
}) {
  const letters = text.toUpperCase().split("").filter((l) => PIXEL[l]);
  const rows = 7, cols = 5;
  const lw = cols * dotSize + (cols - 1) * gap;
  const tw = letters.length * lw + (letters.length - 1) * letterGap;
  const th = rows * dotSize + (rows - 1) * gap;
  return (
    <svg
      role="img"
      aria-label={text}
      width={tw}
      height={th}
      viewBox={`0 0 ${tw} ${th}`}
      style={{ display: "block", maxWidth: "100%", height: "auto" }}
    >
      {letters.map((l, li) => {
        const ox = li * (lw + letterGap);
        return PIXEL[l].map((row, ri) =>
          row.map((on, ci) => {
            if (!on) return null;
            const x = ox + ci * (dotSize + gap);
            const y = ri * (dotSize + gap);
            return round ? (
              <circle key={`${li}-${ri}-${ci}`} cx={x + dotSize / 2} cy={y + dotSize / 2} r={dotSize / 2} fill={color} />
            ) : (
              <rect key={`${li}-${ri}-${ci}`} x={x} y={y} width={dotSize} height={dotSize} fill={color} rx={1} />
            );
          })
        );
      })}
    </svg>
  );
}
