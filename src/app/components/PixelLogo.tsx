const PIXEL: Record<string, number[][]> = {
  T: [[1,1,1,1,1],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0],[0,0,1,0,0]],
  R: [[1,1,1,1,0],[1,0,0,0,1],[1,0,0,0,1],[1,1,1,1,0],[1,0,1,0,0],[1,0,0,1,0],[1,0,0,0,1]],
  A: [[0,0,1,0,0],[0,1,0,1,0],[1,0,0,0,1],[1,1,1,1,1],[1,0,0,0,1],[1,0,0,0,1],[1,0,0,0,1]],
  C: [[0,1,1,1,0],[1,0,0,0,1],[1,0,0,0,0],[1,0,0,0,0],[1,0,0,0,0],[1,0,0,0,1],[0,1,1,1,0]],
  E: [[1,1,1,1,1],[1,0,0,0,0],[1,0,0,0,0],[1,1,1,1,0],[1,0,0,0,0],[1,0,0,0,0],[1,1,1,1,1]],
};

export function PixelLogo({
  dotSize = 5,
  gap = 3,
  letterGap = 12,
  color = "white",
}: {
  dotSize?: number;
  gap?: number;
  letterGap?: number;
  color?: string;
}) {
  const letters = ["T", "R", "A", "C", "E"];
  const rows = 7, cols = 5;
  const lw = cols * dotSize + (cols - 1) * gap;
  const tw = letters.length * lw + (letters.length - 1) * letterGap;
  const th = rows * dotSize + (rows - 1) * gap;
  return (
    <svg width={tw} height={th} viewBox={`0 0 ${tw} ${th}`} style={{ display: "block" }}>
      {letters.map((l, li) => {
        const ox = li * (lw + letterGap);
        return PIXEL[l].map((row, ri) =>
          row.map((on, ci) =>
            on ? (
              <rect
                key={`${li}-${ri}-${ci}`}
                x={ox + ci * (dotSize + gap)}
                y={ri * (dotSize + gap)}
                width={dotSize}
                height={dotSize}
                fill={color}
                rx={1}
              />
            ) : null
          )
        );
      })}
    </svg>
  );
}
