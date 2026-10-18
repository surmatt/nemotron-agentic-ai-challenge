import { loadFont as loadGaramond } from "@remotion/google-fonts/EBGaramond";
import { loadFont as loadInter } from "@remotion/google-fonts/Inter";

const garamond = loadGaramond("normal", {
  weights: ["400", "600"],
  subsets: ["latin"],
});
const inter = loadInter("normal", {
  weights: ["400", "600", "700"],
  subsets: ["latin"],
});

export const fonts = {
  serif: garamond.fontFamily,
  sans: inter.fontFamily,
};

// The same three colours as the site: Britannica source, Wikipedia source, generated analysis.
export const colors = {
  paper: "#f6f0e6",
  ink: "#222222",
  muted: "#6b6258",
  britannica: "#8a5a2b",
  britannicaBg: "#fbf7f1",
  wikipedia: "#2b5a8a",
  wikipediaBg: "#f1f6fb",
  generated: "#666666",
  generatedBg: "#f4f4f4",
  highlight: "rgba(255, 214, 64, 0.55)",
  bad: "#a11111",
  good: "#176b2c",
};
