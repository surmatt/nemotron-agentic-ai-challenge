import type React from "react";
import {
  Easing,
  Img,
  Interactive,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Caption } from "./Caption";
import { colors, fonts } from "./theme";

// A view of the screenshot: the screenshot point at the frame centre, and the zoom (1 = screenshot width fills the frame).
type View = { readonly cx: number; readonly cy: number; readonly zoom: number };

type SiteSceneProps = {
  readonly image: string;
  readonly imageWidth: number;
  readonly imageHeight: number;
  readonly url: string;
  readonly start: View;
  readonly end: View;
  readonly text: string;
  readonly caption: string;
};

const FRAME = { left: 120, top: 40, width: 1680, height: 780 };
const BAR = 44;

const SiteSceneInner: React.FC<SiteSceneProps> = ({
  image,
  imageWidth,
  imageHeight,
  url,
  start,
  end,
  text,
  caption,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const viewH = FRAME.height - BAR;
  const base = FRAME.width / imageWidth;
  const move = {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.bezier(0.45, 0, 0.55, 1),
  } as const;
  const cx = interpolate(frame, [1 * fps, durationInFrames - 1 * fps], [start.cx, end.cx], move);
  const cy = interpolate(frame, [1 * fps, durationInFrames - 1 * fps], [start.cy, end.cy], move);
  const zoom = interpolate(frame, [1 * fps, durationInFrames - 1 * fps], [start.zoom, end.zoom], move);
  const s = base * zoom;

  return (
    <>
      <div
        style={{
          position: "absolute",
          left: FRAME.left,
          top: FRAME.top,
          width: FRAME.width,
          height: FRAME.height,
          borderRadius: 16,
          overflow: "hidden",
          backgroundColor: "white",
          boxShadow: "0 24px 60px rgba(0,0,0,0.18)",
        }}
      >
        <div
          style={{
            height: BAR,
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "0 18px",
            backgroundColor: "#e9e5df",
            fontFamily: fonts.sans,
            fontSize: 20,
            color: colors.muted,
          }}
        >
          <span style={{ width: 13, height: 13, borderRadius: 7, backgroundColor: "#d9534f" }} />
          <span style={{ width: 13, height: 13, borderRadius: 7, backgroundColor: "#f0ad4e" }} />
          <span style={{ width: 13, height: 13, borderRadius: 7, backgroundColor: "#5cb85c" }} />
          <span style={{ marginLeft: 16 }}>{url}</span>
        </div>
        <div style={{ position: "relative", height: viewH, overflow: "hidden" }}>
          <Img
            src={staticFile(image)}
            style={{
              position: "absolute",
              left: 0,
              top: 0,
              width: imageWidth,
              height: imageHeight,
              transformOrigin: "0 0",
              translate: `${FRAME.width / 2 - cx * s}px ${viewH / 2 - cy * s}px`,
              scale: `${s}`,
            }}
          />
        </div>
      </div>
      {text ? (
        <Interactive.Div
          name="On-screen text"
          style={{
            position: "absolute",
            right: 160,
            top: 600,
            maxWidth: 1100,
            padding: "20px 30px",
            borderRadius: 14,
            borderLeft: `8px solid ${colors.generated}`,
            backgroundColor: "rgba(255,255,255,0.96)",
            boxShadow: "0 12px 30px rgba(0,0,0,0.16)",
            fontFamily: fonts.sans,
            fontSize: 38,
            fontWeight: 600,
            color: colors.ink,
            opacity: interpolate(frame, [1.5 * fps, 2.2 * fps], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
            translate: interpolate(frame, [1.5 * fps, 2.2 * fps], ["0px 30px", "0px 0px"], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
              easing: Easing.bezier(0.16, 1, 0.3, 1),
            }),
          }}
        >
          {text}
        </Interactive.Div>
      ) : null}
      <Caption name="Voice-over">{caption}</Caption>
    </>
  );
};

export const SiteScene = Interactive.create({
  Component: SiteSceneInner,
  layout: "absolute-fill",
  schema: {
    ...Interactive.backgroundSchema,
    text: { type: "string", default: "", description: "On-screen text" },
    caption: { type: "string", default: "", description: "Voice-over" },
  },
});
