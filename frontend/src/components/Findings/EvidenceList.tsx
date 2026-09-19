import type { Evidence } from '@/src/types/analysis';
import { EvidenceItem } from './EvidenceItem';

interface EvidenceListProps {
  evidence: Evidence[];
}

export function EvidenceList({ evidence }: EvidenceListProps) {
  if (evidence.length === 0) return null;

  return (
    <ul className="mt-3 space-y-2">
      {evidence.map((item) => (
        <EvidenceItem key={item.id} evidence={item} />
      ))}
    </ul>
  );
}
