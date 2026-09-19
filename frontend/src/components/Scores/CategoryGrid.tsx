import { useState } from 'react';
import type { AnalysisCategory, Finding } from '@/src/types/analysis';
import { FindingsList } from '../Findings/FindingsList';
import { ScoreCategory } from './ScoreCategory';

interface CategoryGridProps {
  categories: AnalysisCategory[];
  findings: Finding[];
}

export function CategoryGrid({ categories, findings }: CategoryGridProps) {
  const [expandedCategoryId, setExpandedCategoryId] = useState<string>();

  return (
    <div className="space-y-2">
      {categories.map((category) => {
        const isExpanded = expandedCategoryId === category.id;
        const categoryFindings = findings.filter((finding) => finding.categoryId === category.id);

        return (
          <div key={category.id} className="space-y-2">
            <ScoreCategory
              category={category}
              isExpanded={isExpanded}
              onToggle={() =>
                setExpandedCategoryId((current) => (current === category.id ? undefined : category.id))
              }
            />
            {isExpanded && (
              <FindingsList
                categories={[category]}
                findings={categoryFindings}
                embedded
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
