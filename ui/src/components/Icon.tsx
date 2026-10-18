const PATHS: Record<string, string> = {
  upload: "M12 16V4m0 0-4 4m4-4 4 4M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2",
  play: "M7 5v14l11-7z",
  replay: "M3 12a9 9 0 1 0 3-6.7M3 4v5h5",
  check: "M5 12.5 10 17l9-10",
  x: "M6 6l12 12M18 6 6 18",
  alert: "M12 8v5m0 3.5v.5M10.3 3.9 2.6 17.2A2 2 0 0 0 4.3 20h15.4a2 2 0 0 0 1.7-2.8L13.7 3.9a2 2 0 0 0-3.4 0z",
  clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z",
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  fit: "M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5",
  layers: "m12 3 9 5-9 5-9-5zm-9 9 9 5 9-5M3 16l9 5 9-5",
  external: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
  book: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zm0 0v16M8 7h7",
  copy: "M9 9h10v11H9zM5 15V5a1 1 0 0 1 1-1h9",
  dot: "M12 12h.01",
  search: "m20 20-4.3-4.3M17 10.5a6.5 6.5 0 1 1-13 0 6.5 6.5 0 0 1 13 0z",
  scale: "M12 4v16M7 20h10M5 8h14M5 8l-3 7a4 4 0 0 0 6 0zm14 0-3 7a4 4 0 0 0 6 0z",
  spark: "M12 3v4m0 10v4M3 12h4m10 0h4M6 6l2.5 2.5m7 7L18 18M6 18l2.5-2.5m7-7L18 6",
  arrow: "M5 12h14m-5-5 5 5-5 5",
  refresh: "M20 11a8 8 0 0 0-14.9-3.9M4 5v4h4m-4 4a8 8 0 0 0 14.9 3.9M20 19v-4h-4",
  doc: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6m-6 4h6",
};

export function Icon({ name, size = 18, label }: { name: keyof typeof PATHS | string; size?: number; label?: string }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={name === "play" ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className="icon"
    >
      <path d={PATHS[name] ?? PATHS.dot} />
    </svg>
  );
}
