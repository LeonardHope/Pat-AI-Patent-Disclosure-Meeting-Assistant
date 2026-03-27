/**
 * Small horizontal VU meter that shows audio level (0-1).
 * Turns green when audio is detected, stays gray when silent.
 */
export function VuMeter({ level, className = "" }: { level: number; className?: string }) {
  const bars = 8;
  const activeBars = Math.round(level * bars);

  return (
    <div className={`flex items-center gap-[2px] ${className}`} title={`Level: ${Math.round(level * 100)}%`}>
      {Array.from({ length: bars }, (_, i) => {
        const isActive = i < activeBars;
        const color =
          i < 5 ? "bg-green-400" : i < 7 ? "bg-yellow-400" : "bg-red-400";
        return (
          <div
            key={i}
            className={`w-[3px] rounded-sm transition-all duration-75 ${
              isActive ? color : "bg-gray-700"
            }`}
            style={{ height: `${8 + i * 1.5}px` }}
          />
        );
      })}
    </div>
  );
}
