import type React from "react";
import { Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { colors } from "./theme";

// A box in page coordinates: [left, top, right, bottom], each from 0 to 1 (the Parse 3.5 bbox format).
export type Box = readonly [number, number, number, number];

type ScanViewProps = {
  readonly scan: string;
  readonly pageWidth: number;
  readonly pageHeight: number;
  readonly width: number;
  readonly height: number;
  readonly block: Box;
  readonly marks: readonly Box[];
  // Seconds: the zoom from the full page to the block, and the start of the marker strokes.
  readonly zoomFrom: number;
  readonly zoomTo: number;
  readonly markFrom: number;
  readonly markColor?: string;
  readonly style?: React.CSSProperties;
};

// Shows a whole scan page, then zooms into one Parse block and marks phrases with a highlighter.
export const ScanView: React.FC<ScanViewProps> = ({
  scan,
  pageWidth,
  pageHeight,
  width,
  height,
  block,
  marks,
  zoomFrom,
  zoomTo,
  markFrom,
  markColor = colors.highlight,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const fit = height / pageHeight;
  const blockW = (block[2] - block[0]) * pageWidth;
  const blockH = (block[3] - block[1]) * pageHeight;
  const close = Math.min((width * 0.92) / blockW, (height * 0.8) / blockH);
  // 0 shows the whole page, 1 shows the block. zoomTo <= zoomFrom starts on the block.
  const t =
    zoomTo > zoomFrom
      ? interpolate(frame, [zoomFrom * fps, zoomTo * fps], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.65, 0, 0.35, 1),
        })
      : 1;
  const s = fit + (close - fit) * t;
  const cx = pageWidth / 2 + (((block[0] + block[2]) / 2) * pageWidth - pageWidth / 2) * t;
  const cy = pageHeight / 2 + (((block[1] + block[3]) / 2) * pageHeight - pageHeight / 2) * t;

  return (
    <div
      style={{
        position: "relative",
        width,
        height,
        overflow: "hidden",
        borderRadius: 12,
        backgroundColor: "#e8dfcf",
        boxShadow: "0 20px 50px rgba(60,40,20,0.25)",
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          width: pageWidth,
          height: pageHeight,
          transformOrigin: "0 0",
          translate: `${width / 2 - cx * s}px ${height / 2 - cy * s}px`,
          scale: `${s}`,
        }}
      >
        <Img src={staticFile(scan)} style={{ width: pageWidth, height: pageHeight }} />
        {marks.map((m, i) => (
          <div
            key={i}
            style={{
              position: "absolute",
              left: m[0] * pageWidth,
              top: m[1] * pageHeight,
              height: (m[3] - m[1]) * pageHeight,
              width:
                (m[2] - m[0]) *
                pageWidth *
                interpolate(frame, [(markFrom + i * 0.6) * fps, (markFrom + i * 0.6 + 0.6) * fps], [0, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                }),
              backgroundColor: markColor,
              mixBlendMode: "multiply",
              borderRadius: 4,
            }}
          />
        ))}
      </div>
    </div>
  );
};
