import { Track, useVideoConfig } from "remotion";
import { BarsScene } from "./BarsScene";
import { BeforeAfterScene } from "./BeforeAfterScene";
import { BlooperScene } from "./BlooperScene";
import { FactScene } from "./FactScene";
import { MissScene } from "./MissScene";
import { SiteScene } from "./SiteScene";
import { TitleCard } from "./TitleCard";
import { colors } from "./theme";

// Scenes follow video/script.md. Facts and sources: video/evidence/facts.json.
export const MainVideo = () => {
  const { fps } = useVideoConfig();

  return (
    <Track name="Scenes">
      <TitleCard
        name="Part 1 title"
        durationInFrames={2.5 * fps}
        kicker="Part 1"
        title="The website"
        note="100 Britannica scans, compared with Wikipedia"
        style={{ backgroundColor: colors.paper, justifyContent: "center", alignItems: "center" }}
      />
      <SiteScene
        name="1.1 Overview"
        from={2.5 * fps}
        durationInFrames={10 * fps}
        image="site/site-index.png"
        imageWidth={1600}
        imageHeight={1000}
        url="artifacts/site/index.html"
        start={{ cx: 800, cy: 300, zoom: 1.5 }}
        end={{ cx: 800, cy: 350, zoom: 1.6 }}
        text="100 scans · 86 Wikipedia matches · 98 LaTeX documents · 45 agent runs"
        caption="We took 100 pages of the Encyclopaedia Britannica, from the first edition of 1771 to the eighth edition, and compared them with today's Wikipedia."
        style={{ backgroundColor: colors.paper }}
      />
      <SiteScene
        name="1.2 Colours"
        from={12.5 * fps}
        durationInFrames={5 * fps}
        image="site/site-index.png"
        imageWidth={1600}
        imageHeight={1000}
        url="artifacts/site/index.html"
        start={{ cx: 800, cy: 230, zoom: 1.5 }}
        end={{ cx: 800, cy: 230, zoom: 1.55 }}
        text=""
        caption="Brown is the old Britannica text. Blue is Wikipedia. Grey is what our models wrote."
        style={{ backgroundColor: colors.paper }}
      />
      <SiteScene
        name="1.3 Scan page"
        from={17.5 * fps}
        durationInFrames={15 * fps}
        image="site/site-scan-1805.png"
        imageWidth={1600}
        imageHeight={2600}
        url="artifacts/site/scans/1805.html"
        start={{ cx: 800, cy: 520, zoom: 1.5 }}
        end={{ cx: 800, cy: 1400, zoom: 1.5 }}
        text="Parse 3.5: “fo reviewing … fanc-tany” → Super VL: “for reviving … sanctuary”"
        caption="Each page keeps the original scan. Parse 3.5 reads it. Super VL looks at the same crop and fixes the OCR. Every page also compiles to a LaTeX document."
        style={{ backgroundColor: colors.paper }}
      />
      <SiteScene
        name="1.4 Entry page"
        from={32.5 * fps}
        durationInFrames={15 * fps}
        image="site/site-entry-E0245.png"
        imageWidth={1600}
        imageHeight={2200}
        url="artifacts/site/entries/E0245.html"
        start={{ cx: 800, cy: 330, zoom: 1.5 }}
        end={{ cx: 800, cy: 1750, zoom: 1.5 }}
        text="More in 1771: hog, muzzle, jaw · More in Wikipedia: spines, hedgehogs, defense"
        caption="For each entry, the Nemotron embedder and reranker find the matching Wikipedia article. Then we count which words each side uses more."
        style={{ backgroundColor: colors.paper }}
      />
      <SiteScene
        name="1.5 Agent run"
        from={47.5 * fps}
        durationInFrames={15 * fps}
        image="site/site-agent-q07.png"
        imageWidth={1600}
        imageHeight={1400}
        url="artifacts/site/agent.html · run 2026-10-18T131943Z, q07-william"
        start={{ cx: 800, cy: 330, zoom: 1.5 }}
        end={{ cx: 800, cy: 1000, zoom: 1.5 }}
        text="Is the match correct? Agent: “at best a partial, headword-level match”"
        caption="Our Hermes agent answers questions with four tools. It must cite a scan ID or a Wikipedia revision for each claim. When the evidence is missing, it must say so."
        style={{ backgroundColor: colors.paper }}
      />
      <TitleCard
        name="Part 2 title"
        from={62.5 * fps}
        durationInFrames={2.5 * fps}
        kicker="Part 2"
        title="Then and now"
        note="Britannica scans against Wikipedia, with a source for each claim"
        style={{ backgroundColor: colors.paper, justifyContent: "center", alignItems: "center" }}
      />
      <FactScene
        name="2.1 Energy"
        from={65 * fps}
        durationInFrames={25 * fps}
        headword="ENERGY"
        edition="Britannica, second edition"
        scanLabel="Scan 523 · block 9 · entry E0037 · National Library of Scotland, CC0 1.0"
        scan="scans/scan-0523.jpg"
        pageWidth={1800}
        pageHeight={2424}
        block={[0.085, 0.4414, 0.4893, 0.482]}
        marks={[[0.257, 0.468, 0.398, 0.481]]}
        quoteBefore="ENERGY, a term of Greek origin, signifying the power, virtue, or efficacy of a thing. It is also used, figuratively, to denote "
        quoteMark="emphasis of speech"
        quoteAfter="."
        nowText="1802: Thomas Young first uses “energy” in its modern sense. Today: energy cannot be created or destroyed, only transformed."
        citation="Wikipedia, “History of energy”, revision 1315594974"
        nowAt={12}
        captionThen="In the 1780s, the whole Britannica entry on energy was two lines long. Energy meant force of speech."
        captionNow="In 1802, Thomas Young first used the word in its modern sense. Today it is the base of all physics: energy cannot be created or destroyed."
        style={{ backgroundColor: colors.paper }}
      />
      <FactScene
        name="2.2 Exercise"
        from={90 * fps}
        durationInFrames={25 * fps}
        headword="EXERCISE"
        edition="Britannica, fourth edition"
        scanLabel="Scan 1805 · blocks 18–19 · entry E0163 · National Library of Scotland, CC0 1.0"
        scan="scans/scan-1805.jpg"
        pageWidth={1800}
        pageHeight={2346}
        block={[0.4873, 0.2984, 0.8574, 0.4609]}
        marks={[
          [0.719, 0.3755, 0.857, 0.3875],
          [0.4906, 0.3875, 0.635, 0.4],
        ]}
        quoteBefore="Exercise may be said to be either active or passive. The active is walking, hunting, dancing, playing at bowls, and the like … "
        quoteMark="The passive is riding in a coach"
        quoteAfter=", on horseback, or in any other manner."
        nowText="Jerry Morris, 1949: bus drivers sat all day and had more heart disease. Bus conductors kept moving and had less."
        citation="Wikipedia, “Exercise”, revision 1348682182"
        nowAt={12}
        captionThen="The fourth edition says there are two kinds of exercise. Active: walking, hunting, dancing. And passive: riding in a coach."
        captionNow="A study from 1949 tells a different story. Bus drivers sat all day and had more heart disease. Bus conductors walked all day and had less."
        style={{ backgroundColor: colors.paper }}
      />
      <BlooperScene
        name="2.3 Lake Erie blooper"
        from={115 * fps}
        durationInFrames={10 * fps}
        scan="scans/scan-2473.jpg"
        pageWidth={1800}
        pageHeight={2427}
        block={[0.4902, 0.4523, 0.915, 0.493]}
        marks={[[0.572, 0.452, 0.631, 0.4643]]}
        scanRow={{ label: "SCAN, 1771", before: "ERIE, a ", mark: "vast lake", after: " to the westward of Pensilvania" }}
        parseRow={{ label: "PARSE 3.5", before: "ERRI, a ", mark: "wall take", after: " to the wellhead of Penfilivana" }}
        modelRow={{ label: "SUPER VL", before: "ERIE, a ", mark: "salt", after: " lake to the westward of Pennsylvania" }}
        source="Raw reply: artifacts/correct/raw/crop_nothink/page-2473-b849fb7f25f2-b18.json"
        captionFirst="Our OCR corrector once made a fact up. The scan says “vast lake”. The model wrote “salt lake”."
        captionSecond="Lake Erie is fresh water. We found it because we keep the raw scan next to every corrected line."
        style={{ backgroundColor: colors.paper }}
      />
      <TitleCard
        name="Part 3 title"
        from={125 * fps}
        durationInFrames={2.5 * fps}
        kicker="Part 3"
        title="First run against now"
        note="First run: Parse text only, lexical title rule, no Nemotron retrieval models"
        style={{ backgroundColor: colors.paper, justifyContent: "center", alignItems: "center" }}
      />
      <BarsScene
        name="3.1 OCR"
        from={127.5 * fps}
        durationInFrames={10 * fps}
        kicker="Part 3 · OCR"
        title="Error rate on 29 hand-transcribed blocks"
        bars={[
          { label: "Parse 3.5 · CER", value: 12.2, color: "#9a9188" },
          { label: "+ Super VL · CER", value: 1.8, color: colors.good },
          { label: "Parse 3.5 · WER", value: 25.1, color: "#9a9188" },
          { label: "+ Super VL · WER", value: 3.0, color: colors.good },
        ]}
        max={26}
        unit="%"
        decimals={1}
        stat={null}
        footnote="Super VL reads the scan crop together with the Parse text. The character error rate falls 6.8 times."
        source="docs/evaluation/ocr-correction.md"
        caption="Super VL cut the OCR errors almost seven times."
        style={{ backgroundColor: colors.paper }}
      />
      <BarsScene
        name="3.2 Matching"
        from={137.5 * fps}
        durationInFrames={15 * fps}
        kicker="Part 3 · Matching"
        title="Right article ranked first"
        bars={[
          { label: "BM25 rank", value: 28, color: "#9a9188" },
          { label: "Embedder cosine", value: 49, color: "#5d86b0" },
          { label: "Reranker logit", value: 65, color: colors.wikipedia },
        ]}
        max={100}
        unit="%"
        decimals={0}
        stat={{ label: "Accepted matches", before: "57", after: "86" }}
        footnote="On 60 hand labels: F1 0.56 → 0.59 (cross-validated). Precision fell from 0.71 to 0.62."
        source="docs/evaluation/match-calibration.md (43 labelled entries) · artifacts/archive/2026-10-18-initial/match/summary.json"
        caption="The reranker puts the right article first two times out of three. We now accept 86 matches instead of 57."
        style={{ backgroundColor: colors.paper }}
      />
      <BeforeAfterScene
        name="3.3 Agent"
        from={152.5 * fps}
        durationInFrames={10 * fps}
        kicker="Part 3 · Agent"
        title="Evidence rules stop invented facts"
        before={{
          label: "FIRST TRIAL, NO RULES",
          text: "“the 1911 Encyclopaedia Britannica”",
          note: "No tool result gives an edition or a year.",
        }}
        after={{
          label: "WITH EVIDENCE RULES",
          text: "No edition or year without tool evidence",
          note: "Question q01-heat, runs 2026-10-18T114003Z and T115609Z",
        }}
        source="Case F3, docs/evaluation/cases.json"
        caption="Without rules, our agent invented an edition year. With evidence rules, it stopped."
        style={{ backgroundColor: colors.paper }}
      />
      <MissScene
        name="3.4 What still fails"
        from={162.5 * fps}
        durationInFrames={10 * fps}
        kicker="What still fails"
        title="Our matcher missed EXERCISE"
        candidates={[
          { title: "Exercise", logit: -2.719 },
          { title: "Exercise medicine", logit: -2.734 },
          { title: "Exercise prescription", logit: -2.898 },
        ]}
        margin={0.015}
        rule={0.5}
        scaleMax={0.6}
        source="artifacts/match/candidates/E0163.json · the same margin rule also rejects HEAT"
        caption="We show our misses too. Every claim on the site links to a scan or a Wikipedia revision."
        style={{ backgroundColor: colors.paper }}
      />
      <TitleCard
        name="Outro"
        from={172.5 * fps}
        durationInFrames={5 * fps}
        kicker="Nemotron Agentic AI Challenge"
        title="[Team name]"
        note="[Repository link] · Britannica scans: National Library of Scotland, CC0 1.0 · Wikipedia text: Wikipedia contributors, CC BY-SA 4.0"
        style={{ backgroundColor: colors.paper, justifyContent: "center", alignItems: "center" }}
      />
    </Track>
  );
};
