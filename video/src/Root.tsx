import { Composition, Folder } from "remotion";
import { BarsScene } from "./BarsScene";
import { BeforeAfterScene } from "./BeforeAfterScene";
import { BlooperScene } from "./BlooperScene";
import { Caption } from "./Caption";
import { FactScene } from "./FactScene";
import { MissScene } from "./MissScene";
import { SiteScene } from "./SiteScene";
import { TitleCard } from "./TitleCard";
import { MainVideo } from "./Video";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="MainVideo"
        component={MainVideo}
        durationInFrames={5325}
        fps={30}
        width={1920}
        height={1080}
      />
      <Folder name="Scenes">
        <Composition
          id="TitleCard"
          component={TitleCard}
          durationInFrames={75}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            kicker: "Part 1",
            title: "The website",
            note: "100 Britannica scans, compared with Wikipedia",
            style: { backgroundColor: "#f6f0e6", justifyContent: "center", alignItems: "center" },
          }}
        />
        <Composition
          id="SiteScene"
          component={SiteScene}
          durationInFrames={300}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            image: "site/site-index.png",
            imageWidth: 1600,
            imageHeight: 1000,
            url: "artifacts/site/index.html",
            start: { cx: 800, cy: 300, zoom: 1.5 },
            end: { cx: 800, cy: 350, zoom: 1.6 },
            text: "100 scans · 86 Wikipedia matches · 98 LaTeX documents · 45 agent runs",
            caption: "We took 100 pages of the Encyclopaedia Britannica and compared them with today's Wikipedia.",
            style: { backgroundColor: "#f6f0e6" },
          }}
        />
        <Composition
          id="FactScene"
          component={FactScene}
          durationInFrames={750}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            headword: "ENERGY",
            edition: "Britannica, second edition",
            scanLabel: "Scan 523 · block 9 · entry E0037 · National Library of Scotland, CC0 1.0",
            scan: "scans/scan-0523.jpg",
            pageWidth: 1800,
            pageHeight: 2424,
            block: [0.085, 0.4414, 0.4893, 0.482],
            marks: [[0.257, 0.468, 0.398, 0.481]],
            quoteBefore:
              "ENERGY, a term of Greek origin, signifying the power, virtue, or efficacy of a thing. It is also used, figuratively, to denote ",
            quoteMark: "emphasis of speech",
            quoteAfter: ".",
            nowText:
              "1802: Thomas Young first uses “energy” in its modern sense. Today: energy cannot be created or destroyed, only transformed.",
            citation: "Wikipedia, “History of energy”, revision 1315594974",
            nowAt: 12,
            captionThen: "In the 1780s, the whole Britannica entry on energy was two lines long.",
            captionNow: "In 1802, Thomas Young first used the word in its modern sense.",
            style: { backgroundColor: "#f6f0e6" },
          }}
        />
        <Composition
          id="BlooperScene"
          component={BlooperScene}
          durationInFrames={300}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            scan: "scans/scan-2473.jpg",
            pageWidth: 1800,
            pageHeight: 2427,
            block: [0.4902, 0.4523, 0.915, 0.493],
            marks: [[0.572, 0.452, 0.631, 0.4643]],
            scanRow: { label: "SCAN, 1771", before: "ERIE, a ", mark: "vast lake", after: " to the westward of Pensilvania" },
            parseRow: { label: "PARSE 3.5", before: "ERRI, a ", mark: "wall take", after: " to the wellhead of Penfilivana" },
            modelRow: { label: "SUPER VL", before: "ERIE, a ", mark: "salt", after: " lake to the westward of Pennsylvania" },
            source: "Raw reply: artifacts/correct/raw/crop_nothink/page-2473-b849fb7f25f2-b18.json",
            captionFirst: "Our OCR corrector once made a fact up.",
            captionSecond: "Lake Erie is fresh water.",
            style: { backgroundColor: "#f6f0e6" },
          }}
        />
        <Composition
          id="BarsScene"
          component={BarsScene}
          durationInFrames={300}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            kicker: "Part 3 · Matching",
            title: "Right article ranked first",
            bars: [
              { label: "BM25 rank", value: 28, color: "#9a9188" },
              { label: "Embedder cosine", value: 49, color: "#5d86b0" },
              { label: "Reranker logit", value: 65, color: "#2b5a8a" },
            ],
            max: 100,
            unit: "%",
            decimals: 0,
            stat: { label: "Accepted matches", before: "57", after: "86" },
            footnote: "On 60 hand labels: F1 0.56 → 0.59 (cross-validated).",
            source: "docs/evaluation/match-calibration.md",
            caption: "The reranker puts the right article first two times out of three.",
            style: { backgroundColor: "#f6f0e6" },
          }}
        />
        <Composition
          id="BeforeAfterScene"
          component={BeforeAfterScene}
          durationInFrames={300}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            kicker: "Part 3 · Agent",
            title: "Evidence rules stop invented facts",
            before: {
              label: "FIRST TRIAL, NO RULES",
              text: "“the 1911 Encyclopaedia Britannica”",
              note: "No tool result gives an edition or a year.",
            },
            after: {
              label: "WITH EVIDENCE RULES",
              text: "No edition or year without tool evidence",
              note: "Question q01-heat",
            },
            source: "Case F3, docs/evaluation/cases.json",
            caption: "Without rules, our agent invented an edition year.",
            style: { backgroundColor: "#f6f0e6" },
          }}
        />
        <Composition
          id="MissScene"
          component={MissScene}
          durationInFrames={300}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{
            kicker: "What still fails",
            title: "Our matcher missed EXERCISE",
            candidates: [
              { title: "Exercise", logit: -2.719 },
              { title: "Exercise medicine", logit: -2.734 },
              { title: "Exercise prescription", logit: -2.898 },
            ],
            margin: 0.015,
            rule: 0.5,
            scaleMax: 0.6,
            source: "artifacts/match/candidates/E0163.json",
            caption: "We show our misses too.",
            style: { backgroundColor: "#f6f0e6" },
          }}
        />
      </Folder>
      <Folder name="Elements">
        <Composition
          id="Caption"
          component={Caption}
          durationInFrames={90}
          fps={30}
          width={1920}
          height={1080}
          defaultProps={{ children: "Voice-over line from video/script.md" }}
        />
      </Folder>
    </>
  );
};
