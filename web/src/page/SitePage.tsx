import { useRef } from 'react';
import type { AllFiles, Source } from '../data/source';
import { DataStatusDialog, Footer, PromoStrip, TopNav } from './Chrome';
import { Findings } from './Findings';
import { ExploreGrid, Hero, PreregBand, ResultsBand, ScaleBand } from './Overview';

type Props = {
  files: AllFiles;
  source: Source;
  /** Bumped by "Check for new files"; remounts the findings so year files reload too. */
  generation: number;
  onCheckAgain: () => void;
};

/** Everything that rises out of the water: the whole site below the intro. */
export function SitePage({ files, source, generation, onCheckAgain }: Props) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const openStatus = () => dialogRef.current?.showModal();

  return (
    <>
      <PromoStrip files={files} source={source} />
      <TopNav files={files} onOpenStatus={openStatus} />
      <main id="main">
        <Hero files={files} />
        <ScaleBand files={files} />
        <ResultsBand files={files} />
        <ExploreGrid files={files} />
        <Findings key={generation} files={files} source={source} />
        <PreregBand />
      </main>
      <Footer onOpenStatus={openStatus} />
      <DataStatusDialog dialogRef={dialogRef} files={files} onCheckAgain={onCheckAgain} />
    </>
  );
}
