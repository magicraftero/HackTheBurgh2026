import { useRef } from 'react';
import { showBuildNotes } from '../data/debug';
import type { AllFiles, Source } from '../data/source';
import { DataStatusDialog, Footer, Notice } from './Chrome';
import { Findings } from './Findings';
import { Hero, NextForecastBand, ResultsBand } from './Overview';

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
      <Notice files={files} source={source} />
      <main id="main">
        <Hero files={files} />
        <ResultsBand files={files} />
        <NextForecastBand files={files} />
        <Findings key={generation} files={files} source={source} />
      </main>
      <Footer files={files} onOpenStatus={openStatus} />
      {showBuildNotes() ? <DataStatusDialog dialogRef={dialogRef} files={files} onCheckAgain={onCheckAgain} /> : null}
    </>
  );
}
